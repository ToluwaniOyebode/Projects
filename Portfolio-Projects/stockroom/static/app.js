import {
  $,
  esc,
  api,
  stat,
  empty,
  toast,
  action,
  formData,
  money,
} from "./core.js";
let products = [],
  reservations = [],
  movements = [],
  stats = {},
  key = crypto.randomUUID();
document.querySelector("footer span:last-child").textContent =
  "Node.js + SQLite + JavaScript";
$("#content").innerHTML = /* HTML */ `<div class="intro">
    <div>
      <div class="eyebrow">Every unit accounted for</div>
      <h1>Stock you can count on.</h1>
      <p>
        Reserve inventory, fulfill orders, and trace every movement. Keep
        available stock separate from what is already promised.
      </p>
    </div>
    <button id="add">+ Add product</button>
  </div>
  <section class="stats" id="stats"></section>
  <div class="grid" id="workspace">
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>Product catalog</h2>
          <p>Availability updates as reservations change.</p>
        </div>
        <span class="pill">Live inventory</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th>On hand</th>
              <th>Held</th>
              <th>Available</th>
              <th></th>
            </tr>
          </thead>
          <tbody id="products"></tbody>
        </table>
      </div>
      <div id="no-products"></div>
    </section>
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>Reserve stock</h2>
          <p>Hold units before fulfilling an order.</p>
        </div>
      </div>
      <form id="reserve" class="fields">
        <div>
          <label for="sku">Product</label
          ><select id="sku" name="sku" required></select>
        </div>
        <div>
          <label for="quantity">Quantity</label
          ><input
            id="quantity"
            name="quantity"
            type="number"
            min="1"
            max="1000000"
            value="1"
            required
          />
        </div>
        <button>Reserve units</button>
      </form>
      <div class="notice">
        <b>Retry-safe reservations.</b> The same request key reuses the original
        reservation. A transaction prevents overselling, even with simultaneous
        requests.
      </div>
    </section>
  </div>
  <section class="panel" style="margin-bottom:20px">
    <div class="panel-head">
      <div>
        <h2>Reservations</h2>
        <p>Ship to reduce on-hand stock, or release a hold.</p>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Reservation</th>
            <th>Product</th>
            <th>Quantity</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody id="reservations"></tbody>
      </table>
    </div>
    <div id="no-reservations"></div>
  </section>
  <section class="panel">
    <div class="panel-head">
      <div>
        <h2>Movement log</h2>
        <p>The latest 50 inventory actions. No entries are overwritten.</p>
      </div>
    </div>
    <div id="movements" class="stack"></div>
  </section>
  <dialog id="editor">
    <form id="product-form" class="fields">
      <div class="eyebrow">Catalog</div>
      <h2>New product</h2>
      <div class="field-row">
        <div>
          <label for="new-sku">SKU</label
          ><input
            id="new-sku"
            name="sku"
            pattern="[A-Za-z0-9_-]+"
            maxlength="32"
            required
          />
        </div>
        <div>
          <label for="name">Product name</label
          ><input id="name" name="name" maxlength="120" required />
        </div>
      </div>
      <div class="field-row">
        <div>
          <label for="on_hand">Opening stock</label
          ><input
            id="on_hand"
            name="on_hand"
            type="number"
            min="0"
            max="1000000"
            value="0"
            required
          />
        </div>
        <div>
          <label for="reorder_point">Reorder point</label
          ><input
            id="reorder_point"
            name="reorder_point"
            type="number"
            min="0"
            max="1000000"
            value="5"
            required
          />
        </div>
      </div>
      <div>
        <label for="price">Unit price (NGN)</label
        ><input
          id="price"
          name="price"
          inputmode="decimal"
          pattern="[0-9]+([.][0-9]{1,2})?"
          value="0"
          required
        />
      </div>
      <div class="actions">
        <button class="secondary" type="button" data-close>Cancel</button
        ><button>Add product</button>
      </div>
    </form>
  </dialog>
  <dialog id="adjuster">
    <form id="adjust-form" class="fields">
      <div class="eyebrow">Stock adjustment</div>
      <h2 id="adjust-title"></h2>
      <input type="hidden" name="sku" />
      <div>
        <label for="delta">Change in units</label
        ><input
          name="delta"
          id="delta"
          type="number"
          min="-1000000"
          max="1000000"
          placeholder="10 or -2"
          required
        />
      </div>
      <div>
        <label for="note">Reason</label
        ><input
          name="note"
          id="note"
          maxlength="300"
          required
          placeholder="New delivery, damaged unit…"
        />
      </div>
      <div class="actions">
        <button class="secondary" type="button" data-close>Cancel</button
        ><button>Record adjustment</button>
      </div>
    </form>
  </dialog>`;
async function load() {
  [products, reservations, movements, stats] = await Promise.all([
    api("/products"),
    api("/reservations"),
    api("/movements"),
    api("/stats"),
  ]);
  render();
}
function render() {
  $("#stats").innerHTML =
    stat("Available units", stats.available, "Ready to reserve") +
    stat("Units on hold", stats.reserved, "Promised, not shipped") +
    stat("Low-stock products", stats.low_stock, "At or below reorder point") +
    stat("Stock value", money(stats.value_cents), "On hand × unit price");
  $("#products").innerHTML = products
    .map(
      (p) =>
        `<tr><td><strong>${esc(p.name)}</strong><br><code>${esc(p.sku)}</code></td><td>${p.on_hand}</td><td>${p.reserved}</td><td><span class="pill ${p.available <= p.reorder_point ? "bad" : "good"}">${p.available}${p.available <= p.reorder_point ? " · Low" : ""}</span></td><td><button class="secondary small" data-adjust="${esc(p.sku)}">Adjust</button></td></tr>`,
    )
    .join("");
  $("#no-products").innerHTML = products.length
    ? ""
    : empty("Add a product to start tracking stock.");
  const selected = $("#sku").value;
  $("#sku").innerHTML = products
    .map(
      (p) =>
        `<option value="${esc(p.sku)}" ${p.sku === selected ? "selected" : ""}>${esc(p.name)} · ${p.available} available</option>`,
    )
    .join("");
  $("#reservations").innerHTML = reservations
    .map(
      (r) =>
        `<tr><td>#${r.id}</td><td>${esc(r.name)}</td><td>${r.quantity}</td><td><span class="pill ${r.status === "shipped" ? "good" : ""}">${esc(r.status)}</span></td><td>${r.status === "held" ? `<div class="actions"><button class="small" data-ship="${r.id}">Ship</button><button class="secondary small" data-release="${r.id}">Release</button></div>` : "—"}</td></tr>`,
    )
    .join("");
  $("#no-reservations").innerHTML = reservations.length
    ? ""
    : empty("Reservations will appear here.");
  $("#movements").innerHTML = movements.length
    ? movements
        .slice(0, 12)
        .map(
          (m) =>
            `<div class="movement"><span class="pill">${esc(m.kind)}</span><code>${esc(m.sku)}</code><span>${m.quantity} units</span><span class="muted">${esc(m.note)}</span><small class="muted">${esc(m.created_at.slice(0, 16).replace("T", " "))} UTC</small></div>`,
        )
        .join("")
    : empty("The movement log starts with your first action.");
}
$("#add").onclick = () => {
  $("#product-form").reset();
  $("#editor").showModal();
};
$("#product-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const d = formData(e.target);
    const [major, minor = ""] = d.price.split(".");
    await api("/products", "POST", {
      sku: d.sku,
      name: d.name,
      on_hand: Number(d.on_hand),
      reorder_point: Number(d.reorder_point),
      unit_price_cents: Number(major) * 100 + Number(minor.padEnd(2, "0")),
    });
    $("#editor").close();
    await load();
    toast("Product added");
  });
};
$("#reserve").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const d = formData(e.target);
    await api("/reservations", "POST", {
      sku: d.sku,
      quantity: Number(d.quantity),
      request_key: key,
    });
    key = crypto.randomUUID();
    await load();
    toast("Stock reserved");
  });
};
$("#reserve").onchange = () => {
  key = crypto.randomUUID();
};
$("#products").onclick = (e) => {
  const sku = e.target.dataset.adjust;
  if (!sku) return;
  const p = products.find((p) => p.sku === sku);
  $("#adjust-form").reset();
  $("#adjust-form").elements.sku.value = sku;
  $("#adjust-title").textContent = p.name;
  $("#adjuster").showModal();
};
$("#adjust-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const d = formData(e.target);
    await api("/products/" + encodeURIComponent(d.sku) + "/adjust", "POST", {
      delta: Number(d.delta),
      note: d.note,
    });
    $("#adjuster").close();
    await load();
    toast("Adjustment recorded");
  });
};
$("#reservations").onclick = (e) => {
  const id = e.target.dataset.ship || e.target.dataset.release;
  if (!id) return;
  action(async () => {
    await api(
      "/reservations/" +
        id +
        "/" +
        (e.target.dataset.ship ? "ship" : "release"),
      "POST",
      {},
    );
    await load();
    toast("Reservation updated");
  });
};
action(load);
