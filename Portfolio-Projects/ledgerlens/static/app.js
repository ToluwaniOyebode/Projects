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
  download,
} from "./core.js";
const categories = [
  "food",
  "groceries",
  "transport",
  "bills",
  "shopping",
  "health",
  "learning",
  "other",
];
const options = categories.map((c) => `<option>${c}</option>`).join("");
const now = new Date();
let month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`,
  transactions = [],
  summary = {};
$("#content").innerHTML = /* HTML */ `<div class="intro">
    <div>
      <div class="eyebrow">Know where it goes</div>
      <h1>Give every naira a story.</h1>
      <p>
        Turn a CSV into a clear picture of spending. Set category budgets and
        keep the small purchases in view.
      </p>
    </div>
    <div class="actions">
      <button class="secondary" id="import">Import CSV ↑</button
      ><button id="add">+ Add expense</button>
    </div>
  </div>
  <div class="toolbar">
    <label for="month">Reporting month</label
    ><input id="month" type="month" value="${month}" style="width:180px" /><a
      href="/sample.csv"
      download
      >Download sample CSV</a
    >
  </div>
  <section class="stats" id="stats"></section>
  <div class="grid" id="workspace">
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>Spending by category</h2>
          <p>Net expenses after refunds, for the selected month.</p>
        </div>
        <span class="pill">NGN</span>
      </div>
      <div id="categories"></div>
    </section>
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>Set a monthly budget</h2>
          <p>Apply a limit to one category.</p>
        </div>
      </div>
      <form id="budget" class="fields">
        <div>
          <label for="budget-category">Category</label
          ><select id="budget-category" name="category">
            ${options}
          </select>
        </div>
        <div>
          <label for="budget-amount">Monthly limit (NGN)</label
          ><input
            id="budget-amount"
            name="amount"
            inputmode="decimal"
            placeholder="25000.00"
            pattern="[0-9]+([.][0-9]{1,2})?"
            required
          />
        </div>
        <button>Save budget</button>
      </form>
      <div class="notice">
        Amounts stay in <b>integer kobo</b> to avoid floating-point rounding.
        This ledger tracks expenses and refunds in NGN.
      </div>
    </section>
  </div>
  <section class="panel" style="margin-bottom:20px">
    <div class="panel-head">
      <div>
        <h2>Monthly rhythm</h2>
        <p>Up to six months with recorded transactions, across the ledger.</p>
      </div>
    </div>
    <div id="trend" class="trend"></div>
  </section>
  <section class="panel">
    <div class="panel-head">
      <div>
        <h2>Transactions</h2>
        <p>Change a category to refine the picture.</p>
      </div>
      <button class="secondary small" id="export">Export this month ↓</button>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Description</th>
            <th>Category</th>
            <th>Amount</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
    <div id="no-rows"></div>
  </section>
  <dialog id="editor">
    <form id="expense" class="fields">
      <div class="eyebrow">New entry</div>
      <h2>Add an expense or refund</h2>
      <div class="field-row">
        <div>
          <label for="day">Date</label
          ><input name="date" id="day" type="date" required />
        </div>
        <div>
          <label for="amount">Amount (NGN)</label
          ><input
            name="amount"
            id="amount"
            inputmode="decimal"
            placeholder="2500.00"
            pattern="-?[0-9]+([.][0-9]{1,2})?"
            required
          />
        </div>
      </div>
      <div>
        <label for="description">Description</label
        ><input id="description" name="description" maxlength="300" required />
      </div>
      <div>
        <label for="category">Category</label
        ><select id="category" name="category">
          <option value="">Auto-categorize</option>
          ${options}
        </select>
      </div>
      <p class="muted">Use a negative amount for a refund.</p>
      <div class="actions">
        <button type="button" class="secondary" data-close>Cancel</button
        ><button>Save entry</button>
      </div>
    </form>
  </dialog>
  <dialog id="importer">
    <form id="csv-form" class="fields">
      <div class="eyebrow">Bring your data</div>
      <h2>Import expense CSV</h2>
      <p class="muted">
        Required: date, description, amount. Optional: category. Dates use
        YYYY-MM-DD. Maximum 2,000 rows.
      </p>
      <label for="csv-file">Choose a CSV file</label
      ><input id="csv-file" type="file" accept=".csv,text/csv" /><label
        for="csv-text"
        >Or paste CSV</label
      ><textarea
        id="csv-text"
        rows="8"
        placeholder="date,description,amount&#10;2026-10-01,Bus ride,500.00"
      ></textarea>
      <p class="muted">
        All rows are validated before saving. Identical date, description and
        amount combinations are skipped.
      </p>
      <div class="actions">
        <button type="button" class="secondary" data-close>Cancel</button
        ><button>Validate &amp; import</button>
      </div>
    </form>
  </dialog>`;
async function load() {
  [transactions, summary] = await Promise.all([
    api("/transactions?month=" + month),
    api("/summary?month=" + month),
  ]);
  render();
}
function render() {
  $("#stats").innerHTML =
    stat(
      "Net spending",
      money(summary.net_cents),
      `${summary.count} transactions`,
    ) +
    stat("Gross expenses", money(summary.gross_cents), "Before refunds") +
    stat("Refunds", money(summary.refund_cents), "Returned to your ledger") +
    stat(
      "Category budgets",
      money(summary.budget_cents),
      "Combined limits this month",
    );
  const max = Math.max(1, ...summary.categories.map((c) => c.cents));
  $("#categories").innerHTML = summary.categories
    .map(
      (c) =>
        `<div class="category-row"><div class="bar-row"><span>${esc(c.category)}</span><div class="progress"><i style="width:${(Math.max(0, c.cents) / max) * 100}%"></i></div><strong>${esc(money(c.cents))}</strong></div>${c.budget_cents ? `<div class="budget-note ${c.cents > c.budget_cents ? "error" : "muted"}">${Math.round((c.cents / c.budget_cents) * 100)}% of ${esc(money(c.budget_cents))} budget${c.cents > c.budget_cents ? " · Over budget" : ""}</div>` : ""}</div>`,
    )
    .join("");
  const top = Math.max(1, ...summary.trend.map((t) => t.cents));
  $("#trend").innerHTML = summary.trend.length
    ? summary.trend
        .map(
          (t) =>
            `<div class="month-bar"><small>${esc(money(t.cents))}</small><div class="column-space"><i style="height:${Math.max(1, (t.cents / top) * 100)}%"></i></div><span>${esc(t.month)}</span></div>`,
        )
        .join("")
    : empty("Import a CSV or add a transaction to see the trend.");
  $("#rows").innerHTML = transactions
    .map(
      (x) =>
        `<tr><td>${esc(x.date)}</td><td>${esc(x.description)}</td><td><select class="small" data-category="${x.id}" aria-label="Category for ${esc(x.description)}">${categories.map((c) => `<option ${c === x.category ? "selected" : ""}>${c}</option>`).join("")}</select></td><td class="${x.cents < 0 ? "success" : ""}">${esc(money(x.cents))}</td><td><button class="danger small" data-delete="${x.id}" aria-label="Delete ${esc(x.description)}">×</button></td></tr>`,
    )
    .join("");
  $("#no-rows").innerHTML = transactions.length
    ? ""
    : empty("No transactions in this month.");
}
$("#month").onchange = (e) => {
  if (e.target.value) {
    month = e.target.value;
    action(load);
  }
};
$("#add").onclick = () => {
  $("#expense").reset();
  $("#day").value = `${month}-01`;
  $("#editor").showModal();
};
$("#import").onclick = () => $("#importer").showModal();
$("#export").onclick = () => download("/export.csv?month=" + month);
$("#csv-file").onchange = (e) =>
  action(async () => {
    if (e.target.files[0])
      $("#csv-text").value = await e.target.files[0].text();
  });
$("#csv-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const result = await api("/import", "POST", { csv: $("#csv-text").value });
    $("#importer").close();
    await load();
    toast(
      `${result.inserted} imported · ${result.duplicates} duplicates skipped`,
    );
  });
};
$("#expense").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const data = formData(e.target);
    await api("/transactions", "POST", data);
    month = data.date.slice(0, 7);
    $("#month").value = month;
    $("#editor").close();
    await load();
    toast("Entry saved");
  });
};
$("#budget").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    await api("/budgets", "POST", { ...formData(e.target), month });
    await load();
    toast("Budget updated");
  });
};
$("#rows").onchange = (e) => {
  if (e.target.dataset.category)
    action(async () => {
      await api("/transactions/" + e.target.dataset.category, "PATCH", {
        category: e.target.value,
      });
      await load();
    });
};
$("#rows").onclick = (e) => {
  if (e.target.dataset.delete && confirm("Delete this transaction?"))
    action(async () => {
      await api("/transactions/" + e.target.dataset.delete, "DELETE");
      await load();
    });
};
action(load);
