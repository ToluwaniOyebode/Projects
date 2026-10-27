import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Worker } from "node:worker_threads";
import { Store } from "../store.js";

function setup(t) {
  const s = new Store(":memory:", false);
  t.after(() => s.close());
  s.createProduct({
    sku: "A",
    name: "Widget",
    on_hand: 10,
    reorder_point: 2,
    unit_price_cents: 100,
  });
  return s;
}
test("reservation is retry-safe but rejects key reuse for a different payload", (t) => {
  const s = setup(t);
  const r = s.reserve({ sku: "A", quantity: 4, request_key: "first" });
  assert.equal(
    s.reserve({ sku: "A", quantity: 4, request_key: "first" }).id,
    r.id,
  );
  assert.throws(
    () => s.reserve({ sku: "A", quantity: 5, request_key: "first" }),
    /different input/,
  );
  assert.equal(s.product("A").available, 6);
});
test("oversell rolls back without an audit entry", (t) => {
  const s = setup(t);
  assert.throws(
    () => s.reserve({ sku: "A", quantity: 11, request_key: "bad" }),
    /available/,
  );
  assert.equal(s.reservations().length, 0);
  assert.equal(s.movements().length, 1);
});
test("shipping consumes stock exactly once", (t) => {
  const s = setup(t);
  const r = s.reserve({ sku: "A", quantity: 4, request_key: "ship" });
  s.transition(r.id, "shipped");
  s.transition(r.id, "shipped");
  assert.equal(s.product("A").on_hand, 6);
  assert.equal(s.product("A").reserved, 0);
  assert.throws(() => s.transition(r.id, "released"), /already shipped/);
});
test("release restores availability without changing on-hand stock", (t) => {
  const s = setup(t);
  const r = s.reserve({ sku: "A", quantity: 3, request_key: "release" });
  s.transition(r.id, "released");
  assert.equal(s.product("A").available, 10);
  assert.equal(s.product("A").on_hand, 10);
});
test("adjustments cannot consume held units", (t) => {
  const s = setup(t);
  s.reserve({ sku: "A", quantity: 8, request_key: "hold" });
  assert.throws(
    () => s.adjust("A", { delta: -3, note: "Damaged" }),
    /reserved stock/,
  );
  assert.equal(s.product("A").on_hand, 10);
  s.adjust("A", { delta: 3, note: "Delivery" });
  assert.equal(s.product("A").available, 5);
});
test("invalid quantities and prices are rejected", (t) => {
  const s = setup(t);
  for (const quantity of [0, -1, 1.5, true])
    assert.throws(() => s.reserve({ sku: "A", quantity, request_key: "bad" }));
  assert.throws(() =>
    s.createProduct({
      sku: "B",
      name: "B",
      on_hand: 1,
      reorder_point: 0,
      unit_price_cents: NaN,
    }),
  );
});
test("concurrent processes cannot oversell", async (t) => {
  const dir = mkdtempSync(join(tmpdir(), "stockroom-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const path = join(dir, "stock.db");
  const s = new Store(path, false);
  s.createProduct({
    sku: "A",
    name: "Widget",
    on_hand: 10,
    reorder_point: 1,
    unit_price_cents: 1,
  });
  s.close();
  const module = new URL("../store.js", import.meta.url).href;
  const worker = (i) =>
    new Promise((resolve, reject) => {
      const w = new Worker(
        `const {parentPort,workerData}=require('node:worker_threads');(async()=>{const {Store}=await import(workerData.module);const s=new Store(workerData.path,false);try{s.reserve({sku:'A',quantity:4,request_key:String(workerData.i)});parentPort.postMessage(200)}catch(e){parentPort.postMessage(e.status||500)}finally{s.close()}})().catch(e=>{throw e})`,
        { eval: true, workerData: { module, path, i } },
      );
      w.once("message", resolve);
      w.once("error", reject);
    });
  const results = await Promise.all([0, 1, 2, 3].map(worker));
  assert.deepEqual(results.sort(), [200, 200, 409, 409]);
  const final = new Store(path, false);
  assert.equal(final.product("A").available, 2);
  final.close();
});
