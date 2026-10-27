import re
from pathlib import Path
from search import index_document, search, tokenize
from webcore import Problem, connect, text


class App:
    name = "SignalDesk"

    def __init__(self, path, demo=True):
        self.path = path
        with connect(path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(
                """CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY,title TEXT NOT NULL,content TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,updated_at TEXT DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')));
              CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY,document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,section TEXT NOT NULL,body TEXT NOT NULL,start_line INTEGER NOT NULL,end_line INTEGER NOT NULL,length INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS postings(chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,term TEXT NOT NULL,tf INTEGER NOT NULL,PRIMARY KEY(chunk_id,term));
              CREATE INDEX IF NOT EXISTS postings_term ON postings(term);
              CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY);"""
            )
            if (
                demo
                and not db.execute(
                    "SELECT 1 FROM metadata WHERE key='seeded'"
                ).fetchone()
            ):
                for source in sorted((Path(__file__).parent / "demo").glob("*.md")):
                    content = source.read_text()
                    title = content.splitlines()[0].lstrip("# ")
                    cursor = db.execute(
                        "INSERT INTO documents(title,content) VALUES(?,?)",
                        (title, content),
                    )
                    index_document(db, cursor.lastrowid, title, content)
                db.execute("INSERT INTO metadata VALUES('seeded')")

    def save(self, data, doc_id=None):
        title = text(data.get("title"), "title", 200)
        content = text(data.get("content"), "content", 150000)
        if not tokenize(content):
            raise Problem("Document needs searchable text")
        with connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            if doc_id is None:
                doc_id = db.execute(
                    "INSERT INTO documents(title,content) VALUES(?,?)", (title, content)
                ).lastrowid
            else:
                version = data.get("version")
                if type(version) is not int or version < 1:
                    raise Problem("version must be a positive integer")
                if not db.execute(
                    "SELECT 1 FROM documents WHERE id=?", (doc_id,)
                ).fetchone():
                    raise Problem("Document not found", 404)
                result = db.execute(
                    "UPDATE documents SET title=?,content=?,version=version+1,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND version=?",
                    (title, content, doc_id, version),
                )
                if not result.rowcount:
                    raise Problem("Document changed. Refresh before editing.", 409)
            index_document(db, doc_id, title, content)
            return dict(
                db.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
            )

    def handle(self, method, path, query, body):
        if path == "/api/documents" and method == "POST":
            return self.save(body)
        if path == "/api/documents" and method == "GET":
            with connect(self.path) as db:
                return [
                    dict(r)
                    for r in db.execute(
                        "SELECT d.id,d.title,d.version,d.updated_at,count(c.id) chunks FROM documents d LEFT JOIN chunks c ON c.document_id=d.id GROUP BY d.id ORDER BY d.id DESC"
                    )
                ]
        if path == "/api/stats" and method == "GET":
            with connect(self.path) as db:
                return {
                    "documents": db.execute(
                        "SELECT count(*) FROM documents"
                    ).fetchone()[0],
                    "chunks": db.execute("SELECT count(*) FROM chunks").fetchone()[0],
                    "terms": db.execute(
                        "SELECT count(DISTINCT term) FROM postings"
                    ).fetchone()[0],
                    "tokens": db.execute(
                        "SELECT coalesce(sum(length),0) FROM chunks"
                    ).fetchone()[0],
                }
        if path == "/api/search" and method == "GET":
            query_text = text(query.get("q", ""), "q", 500, True)
            try:
                limit = int(query.get("limit", 10))
            except ValueError:
                raise Problem("limit must be an integer") from None
            with connect(self.path) as db:
                return search(db, query_text, query.get("mode", "any"), limit)
        match = re.fullmatch(r"/api/documents/(\d+)", path)
        if match:
            doc_id = int(match[1])
            if method == "PATCH":
                return self.save(body, doc_id)
            with connect(self.path) as db:
                row = db.execute(
                    "SELECT * FROM documents WHERE id=?", (doc_id,)
                ).fetchone()
                if not row:
                    raise Problem("Document not found", 404)
                if method == "GET":
                    return dict(row)
                if method == "DELETE":
                    db.execute("DELETE FROM documents WHERE id=?", (doc_id,))
                    return {"deleted": True}
        raise Problem("Not found", 404)
