import {
  $,
  esc,
  api,
  stat,
  empty,
  toast,
  action,
  formData,
  download,
} from "./core.js";
const stages = ["saved", "applied", "interview", "offer", "closed"];
let items = [],
  stats = {},
  activity = [],
  filter = "",
  stageFilter = "";
$("#content").innerHTML = /* HTML */ `<div class="intro">
    <div>
      <div class="eyebrow">Your next chapter</div>
      <h1>A calmer job search.</h1>
      <p>
        Keep opportunities moving. See what needs attention, prepare for
        interviews, and make your next move.
      </p>
    </div>
    <button id="add">+ Add application</button>
  </div>
  <section class="stats" id="stats"></section>
  <div class="notice">
    <b>A workspace to make your own.</b> The first run includes fictional
    companies. Edit or delete them and start tracking your real applications.
  </div>
  <section id="workspace">
    <div class="panel-head">
      <div>
        <h2>Application pipeline</h2>
        <p>Move applications as your search progresses.</p>
      </div>
      <button class="secondary small" id="export">Export CSV ↓</button>
    </div>
    <div class="toolbar">
      <input
        id="search"
        aria-label="Search applications"
        placeholder="Search company, role or notes…"
      /><select id="stage-filter" aria-label="Filter stage">
        <option value="">All stages</option>
        ${stages.map((s) => `<option>${s}</option>`).join("")}
      </select>
    </div>
    <div class="board" id="board"></div>
  </section>
  <div class="grid" style="margin-top:26px">
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>Follow-ups due</h2>
          <p>Open applications with a follow-up date today or earlier.</p>
        </div>
      </div>
      <div id="due" class="stack"></div>
    </section>
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>Recent activity</h2>
          <p>A history of changes you make.</p>
        </div>
      </div>
      <div id="activity" class="stack"></div>
    </section>
  </div>
  <dialog id="editor">
    <form id="edit-form">
      <div class="eyebrow">Application details</div>
      <h2 id="edit-title">New opportunity</h2>
      <input type="hidden" name="id" /><input type="hidden" name="version" />
      <div class="fields">
        <div class="field-row">
          <div>
            <label for="company">Company</label
            ><input id="company" name="company" required maxlength="500" />
          </div>
          <div>
            <label for="role">Role</label
            ><input id="role" name="role" required maxlength="500" />
          </div>
        </div>
        <div class="field-row">
          <div>
            <label for="stage">Stage</label
            ><select id="stage" name="stage">
              ${stages.map((s) => `<option>${s}</option>`).join("")}
            </select>
          </div>
          <div>
            <label for="applied_on">Application date</label
            ><input id="applied_on" name="applied_on" type="date" />
          </div>
        </div>
        <div class="field-row">
          <div>
            <label for="followup_on">Follow-up date</label
            ><input id="followup_on" name="followup_on" type="date" />
          </div>
          <div>
            <label for="url">Job URL (optional)</label
            ><input id="url" name="url" type="url" maxlength="500" />
          </div>
        </div>
        <div>
          <label for="notes">Notes</label
          ><textarea id="notes" name="notes" maxlength="4000"></textarea>
        </div>
      </div>
      <div class="actions">
        <button class="secondary" type="button" data-close>Cancel</button
        ><button type="submit">Save application</button>
      </div>
    </form>
  </dialog>`;
function render() {
  $("#stats").innerHTML =
    stat(
      "Active opportunities",
      stats.active,
      "Saved, applied & interviewing",
    ) +
    stat("Interviews", stats.counts.interview, "Keep preparing") +
    stat("Offers", stats.counts.offer, "Decisions ahead") +
    stat(
      "Follow-ups due",
      stats.followups_due.length,
      "A little momentum goes a long way",
    );
  $("#board").innerHTML = stages
    .filter((s) => !stageFilter || s === stageFilter)
    .map((stage) => {
      const rows = items.filter((x) => x.stage === stage);
      return `<div class="lane"><div class="lane-title"><span>${stage}</span><span>${rows.length}</span></div><div class="stack">${rows.length ? rows.map((x) => `<article class="card"><span class="company-icon">${esc(x.company[0].toUpperCase())}</span><h3>${esc(x.company)}</h3><p>${esc(x.role)}</p><span class="muted tiny">${x.followup_on ? "Follow up " + esc(x.followup_on) : "No follow-up set"}</span><div class="actions"><button class="secondary small" data-edit="${x.id}">Details</button><button class="danger small" data-delete="${x.id}" aria-label="Delete ${esc(x.company)}">×</button></div><label class="sr-only" for="move-${x.id}">Move ${esc(x.company)} to stage</label><select class="move" id="move-${x.id}" data-move="${x.id}">${stages.map((s) => `<option ${s === x.stage ? "selected" : ""}>${s}</option>`).join("")}</select></article>`).join("") : empty("No applications here")}</div></div>`;
    })
    .join("");
  $("#due").innerHTML = stats.followups_due.length
    ? stats.followups_due
        .map(
          (x) =>
            `<div class="due-row"><div><h3>${esc(x.company)}</h3><span class="muted tiny">${esc(x.role)} · ${esc(x.followup_on)}</span></div><button class="secondary small" data-edit="${x.id}">Review</button></div>`,
        )
        .join("")
    : empty("All caught up. Set a follow-up date on an application.");
  $("#activity").innerHTML = activity.length
    ? activity
        .slice(0, 5)
        .map(
          (x) =>
            `<div><h3>${esc(x.company)}</h3><p class="muted tiny">${esc(x.message)} · ${esc(x.created_at.slice(0, 10))}</p></div>`,
        )
        .join("")
    : empty("Your changes will appear here.");
}
async function load() {
  [items, stats, activity] = await Promise.all([
    api("/applications?q=" + encodeURIComponent(filter)),
    api("/stats"),
    api("/activity"),
  ]);
  render();
}
function edit(id) {
  const item =
    items.find((x) => x.id === id) ||
    stats.followups_due.find((x) => x.id === id) ||
    {};
  const form = $("#edit-form");
  form.reset();
  for (const [k, v] of Object.entries(item)) {
    if (form.elements.namedItem(k)) form.elements.namedItem(k).value = v;
  }
  $("#edit-title").textContent = id ? "Edit opportunity" : "New opportunity";
  $("#editor").showModal();
}
$("#add").onclick = () => edit();
$("#export").onclick = () =>
  download(
    "/export.csv?q=" + encodeURIComponent(filter) + "&stage=" + stageFilter,
  );
$("#search").oninput = (e) => {
  filter = e.target.value;
  clearTimeout(window.searchTimer);
  window.searchTimer = setTimeout(() => action(load), 220);
};
$("#stage-filter").onchange = (e) => {
  stageFilter = e.target.value;
  render();
};
$("#edit-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const d = formData(e.target);
    const { id, version, ...body } = d;
    await api(
      "/applications" + (id ? "/" + id : ""),
      id ? "PATCH" : "POST",
      id ? { ...body, version: Number(version) } : body,
    );
    $("#editor").close();
    await load();
    toast("Application saved");
  });
};
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-edit],[data-delete]");
  if (!b) return;
  if (b.dataset.edit) edit(Number(b.dataset.edit));
  else if (confirm("Delete this application?"))
    action(async () => {
      await api("/applications/" + b.dataset.delete, "DELETE");
      await load();
      toast("Application deleted");
    });
});
document.addEventListener("change", (e) => {
  if (!e.target.dataset.move) return;
  action(async () => {
    const x = items.find((x) => x.id === Number(e.target.dataset.move));
    try {
      await api("/applications/" + x.id, "PATCH", {
        stage: e.target.value,
        version: x.version,
      });
    } finally {
      await load();
    }
  });
});
action(load);
