import { $, esc, api, stat, empty, toast, action, formData } from "./core.js";
let documents = [],
  q = "idempotency retries",
  mode = "any",
  request = 0;
$("#content").innerHTML = /* HTML */ `<div class="intro">
    <div>
      <div class="eyebrow">Your notes, within reach</div>
      <h1>Find the useful part.</h1>
      <p>
        Search your Markdown and text documents. Follow results to their source,
        and see exactly why each passage matched.
      </p>
    </div>
    <button id="add">+ Add document</button>
  </div>
  <section class="stats" id="stats"></section>
  <section class="panel search-panel" id="workspace">
    <form id="search-form">
      <label for="query">Search the knowledge base</label>
      <div class="search-row">
        <input
          id="query"
          value="idempotency retries"
          placeholder="Try: worker lease or inventory stock…"
          maxlength="500"
        /><select id="mode" aria-label="Search mode">
          <option value="any">Match any word</option>
          <option value="all">Match all words</option></select
        ><button>Search ↗</button>
      </div>
    </form>
    <div class="suggestions">
      <span class="muted">Explore:</span
      ><button class="secondary small" data-query="worker lease">
        worker lease</button
      ><button class="secondary small" data-query="inventory stock">
        inventory stock</button
      ><button class="secondary small" data-query="BM25">BM25</button>
    </div>
  </section>
  <div class="grid">
    <section>
      <div class="panel-head">
        <div>
          <h2>Search results</h2>
          <p id="result-info"></p>
        </div>
        <span class="pill">BM25 · lexical</span>
      </div>
      <div class="stack" id="results"></div>
    </section>
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>Document library</h2>
          <p>Local files, indexed into passages.</p>
        </div>
      </div>
      <div class="stack" id="documents"></div>
      <div class="notice">
        <b>Sources you can inspect.</b> Results are excerpts from your
        documents. This is word-based search with no generated answers or
        external AI service.
      </div>
    </section>
  </div>
  <dialog id="editor">
    <form id="doc-form" class="fields">
      <div class="eyebrow">Knowledge base</div>
      <h2 id="editor-title">Add document</h2>
      <input type="hidden" name="id" /><input type="hidden" name="version" />
      <div>
        <label for="file">Load a .md or .txt file (optional)</label
        ><input
          id="file"
          type="file"
          accept=".md,.txt,text/plain,text/markdown"
        />
      </div>
      <div>
        <label for="title">Document title</label
        ><input id="title" name="title" maxlength="200" required />
      </div>
      <div>
        <label for="content-text">Content</label
        ><textarea
          id="content-text"
          name="content"
          rows="12"
          maxlength="150000"
          required
        ></textarea>
      </div>
      <div class="actions">
        <button class="secondary" type="button" data-close>Cancel</button
        ><button>Save &amp; index</button>
      </div>
    </form>
  </dialog>
  <dialog id="reader">
    <div class="panel-head">
      <h2 id="reader-title"></h2>
      <button class="secondary small" data-close>Close</button>
    </div>
    <pre id="reader-content"></pre>
  </dialog>`;
async function load() {
  const [docs, s] = await Promise.all([api("/documents"), api("/stats")]);
  documents = docs;
  $("#stats").innerHTML =
    stat("Documents", s.documents, "Markdown & plain text") +
    stat("Indexed passages", s.chunks, "Heading-aware chunks") +
    stat("Unique terms", s.terms, "Unicode word tokenizer") +
    stat("Indexed tokens", s.tokens, "Includes titles & headings");
  $("#documents").innerHTML = documents.length
    ? documents
        .map(
          (d) =>
            `<div class="document"><h3>${esc(d.title)}</h3><p class="muted">${d.chunks} passages · v${d.version}</p><div class="actions"><button class="secondary small" data-read="${d.id}">Read</button><button class="secondary small" data-edit="${d.id}">Edit</button><button class="danger small" data-delete="${d.id}">Delete</button></div></div>`,
        )
        .join("")
    : empty("Add your first document.");
  await search();
}
function highlight(snippet, terms) {
  const safe = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!safe.length) return esc(snippet);
  const regex = new RegExp("(" + safe.join("|") + ")", "giu");
  return snippet
    .split(regex)
    .map((p, i) => (i % 2 ? `<mark>${esc(p)}</mark>` : esc(p)))
    .join("");
}
async function search() {
  const ticket = ++request;
  const result = await api(
    "/search?q=" + encodeURIComponent(q) + "&mode=" + mode,
  );
  if (ticket !== request) return;
  $("#result-info").textContent =
    `${result.total} matching passages · ${result.terms.length} query terms`;
  $("#results").innerHTML = result.results.length
    ? result.results
        .map(
          (r) =>
            `<article class="panel result"><div class="panel-head"><div><h2><button class="text-button" data-read="${r.document_id}" data-line="${r.start_line}">${esc(r.title)}</button></h2><p>${esc(r.section)} · lines ${r.start_line}–${r.end_line}</p></div><span class="pill">${r.score.toFixed(3)}</span></div><p class="snippet">${highlight(r.snippet, result.terms)}</p><details><summary>Why this result?</summary><div class="table-wrap"><table><thead><tr><th>Term</th><th>Frequency</th><th>IDF</th><th>Score</th></tr></thead><tbody>${r.explanation.map((e) => `<tr><td>${esc(e.term)}</td><td>${e.tf}</td><td>${e.idf.toFixed(3)}</td><td>${e.contribution.toFixed(3)}</td></tr>`).join("")}</tbody></table></div><p class="muted">Scores compare passages for this query. They are not confidence percentages.</p></details></article>`,
        )
        .join("")
    : empty(
        q
          ? "No matching passages. Try fewer words or add a document."
          : "Type a query to search your documents.",
      );
}
$("#search-form").onsubmit = (e) => {
  e.preventDefault();
  q = $("#query").value;
  mode = $("#mode").value;
  action(search);
};
$("#add").onclick = () => {
  $("#doc-form").reset();
  $("#editor-title").textContent = "Add document";
  $("#editor").showModal();
};
$("#file").onchange = (e) =>
  action(async () => {
    const f = e.target.files[0];
    if (!f) return;
    if (f.size > 150000) throw new Error("Choose a file smaller than 150 KB");
    $("#title").value = f.name.replace(/\.(md|txt)$/i, "");
    $("#content-text").value = await f.text();
  });
$("#doc-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const { id, version, ...data } = formData(e.target);
    await api(
      "/documents" + (id ? "/" + id : ""),
      id ? "PATCH" : "POST",
      id ? { ...data, version: Number(version) } : data,
    );
    $("#editor").close();
    await load();
    toast("Document indexed");
  });
};
document.addEventListener("click", (e) => {
  const b = e.target.closest(
    "[data-query],[data-read],[data-edit],[data-delete]",
  );
  if (!b) return;
  if (b.dataset.query) {
    q = b.dataset.query;
    $("#query").value = q;
    return action(search);
  }
  if (b.dataset.delete) {
    if (confirm("Delete this document and its index?"))
      action(async () => {
        await api("/documents/" + b.dataset.delete, "DELETE");
        await load();
      });
    return;
  }
  action(async () => {
    const d = await api("/documents/" + (b.dataset.read || b.dataset.edit));
    if (b.dataset.read) {
      $("#reader-title").textContent = d.title;
      $("#reader-content").textContent = d.content
        .split("\n")
        .map((line, i) => `${String(i + 1).padStart(3)}  ${line}`)
        .join("\n");
      $("#reader").showModal();
    } else {
      $("#doc-form").reset();
      for (const k of ["id", "version", "title", "content"])
        $("#doc-form").elements.namedItem(k).value = d[k];
      $("#editor-title").textContent = "Edit document";
      $("#editor").showModal();
    }
  });
});
action(load);
