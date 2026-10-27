"""Small local HTTP adapter shared by value; projects remain independently runnable."""

import argparse
import json
import mimetypes
import os
import sqlite3
import traceback
from contextlib import contextmanager
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Raw:
    def __init__(self, body, content_type, filename=None):
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.content_type, self.filename = content_type, filename


def text(value, name, maximum=200, optional=False):
    if not isinstance(value, str):
        raise Problem(f"{name} must be text")
    value = value.strip()
    if (not value and not optional) or len(value) > maximum:
        raise Problem(
            f"{name} must contain {0 if optional else 1}–{maximum} characters"
        )
    return value


def integer(value, name, minimum=0, maximum=1_000_000):
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise Problem(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def iso_date(value, name, optional=False):
    value = text(value, name, 10, optional)
    if not value and optional:
        return ""
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
    except ValueError:
        raise Problem(f"{name} must use YYYY-MM-DD") from None
    return value


@contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def csv_cell(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def make_server(app, port=0, host="127.0.0.1"):
    static = Path(__file__).parent / "static"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if os.environ.get("HTTP_LOG"):
                super().log_message(fmt, *args)

        def respond(
            self,
            status,
            body,
            content_type="application/json; charset=utf-8",
            filename=None,
        ):
            if not isinstance(body, bytes):
                body = json.dumps(body, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            )
            if filename:
                self.send_header(
                    "Content-Disposition", f'attachment; filename="{filename}"'
                )
            self.end_headers()
            self.wfile.write(body)

        def dispatch(self):
            try:
                url = urlsplit(self.path)
                path = unquote(url.path)
                if self.command == "GET" and path == "/api/health":
                    return self.respond(200, {"ok": True, "project": app.name})
                if not path.startswith("/api/"):
                    if self.command != "GET":
                        raise Problem("Method not allowed", 405)
                    target = (static / (path.lstrip("/") or "index.html")).resolve()
                    if (
                        not target.is_relative_to(static.resolve())
                        or not target.is_file()
                    ):
                        raise Problem("Not found", 404)
                    mime = (
                        mimetypes.guess_type(target.name)[0]
                        or "application/octet-stream"
                    )
                    return self.respond(
                        200, target.read_bytes(), mime + "; charset=utf-8"
                    )
                body = {}
                if self.command in ("POST", "PATCH", "DELETE"):
                    origin = self.headers.get("Origin")
                    if origin and origin not in (
                        "http://" + self.headers.get("Host", ""),
                        "https://" + self.headers.get("Host", ""),
                    ):
                        raise Problem("Cross-origin writes are not allowed", 403)
                    if self.headers.get("Transfer-Encoding"):
                        raise Problem("Transfer encoding is not supported")
                    length = int(self.headers.get("Content-Length", "0"))
                    if length < 0 or length > 1_048_576:
                        raise Problem("Request exceeds 1 MiB", 413)
                    if length:
                        if (
                            self.headers.get("Content-Type", "").split(";")[0]
                            != "application/json"
                        ):
                            raise Problem("Use application/json", 415)
                        try:
                            body = json.loads(
                                self.rfile.read(length),
                                parse_constant=lambda v: (_ for _ in ()).throw(
                                    ValueError(v)
                                ),
                            )
                        except (ValueError, UnicodeDecodeError):
                            raise Problem("Invalid JSON") from None
                        if not isinstance(body, dict):
                            raise Problem("JSON body must be an object")
                query = {
                    k: v[-1]
                    for k, v in parse_qs(url.query, keep_blank_values=True).items()
                }
                result = app.handle(self.command, path, query, body)
                if isinstance(result, Raw):
                    return self.respond(
                        200, result.body, result.content_type, result.filename
                    )
                return self.respond(200, result)
            except Problem as error:
                self.respond(error.status, {"error": str(error)})
            except (ValueError, TypeError) as error:
                self.respond(400, {"error": str(error) or "Invalid request"})
            except Exception:
                traceback.print_exc()
                self.respond(500, {"error": "Internal server error; see server log"})

        do_GET = do_POST = do_PATCH = do_DELETE = dispatch

    return ThreadingHTTPServer((host, port), Handler)


def run(factory, default_port):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("PORT", default_port))
    )
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument(
        "--db",
        default=os.environ.get("DB_PATH", str(Path(__file__).parent / "data.sqlite3")),
    )
    args = parser.parse_args()
    Path(args.db).resolve().parent.mkdir(parents=True, exist_ok=True)
    app = factory(args.db)
    server = make_server(app, args.port, args.host)
    print(f"{app.name}: http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if hasattr(app, "close"):
            app.close()
