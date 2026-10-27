"""Run all domain tests, JavaScript syntax checks and HTTP integration tests."""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECTS = [
    "applyboard",
    "ledgerlens",
    "stockroom",
    "signaldesk",
    "pitchside",
    "queuecraft",
]


def request(base, path, method="GET", body=None, headers=None, expected=200):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={
            **({"Content-Type": "application/json"} if body is not None else {}),
            **(headers or {}),
        },
    )
    try:
        res = urllib.request.urlopen(req, timeout=8)
    except urllib.error.HTTPError as error:
        res = error
    with res:
        content = res.read()
        assert res.status == expected, (path, res.status, expected, content[:500])
        assert res.headers.get("X-Content-Type-Options") == "nosniff"
        return (
            json.loads(content)
            if res.headers.get("Content-Type", "").startswith("application/json")
            else content
        )


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def http_check(slug):
    with tempfile.TemporaryDirectory() as tmp:
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        env = {
            **os.environ,
            "PORT": str(port),
            "DB_PATH": str(Path(tmp) / "test.sqlite3"),
        }
        command = (
            ["node", "server.js"]
            if slug == "stockroom"
            else [sys.executable, "server.py"]
        )
        with (Path(tmp) / "server.log").open("w+") as log:
            process = subprocess.Popen(
                command, cwd=ROOT / slug, env=env, stdout=log, stderr=log
            )
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        log.seek(0)
                        raise AssertionError(log.read())
                    try:
                        if request(base, "/api/health")["ok"]:
                            break
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.05)
                else:
                    raise AssertionError("Server did not become healthy")
                assert b'<html lang="en">' in request(base, "/")
                for asset in [
                    "/app.js",
                    "/core.js",
                    "/base.css",
                    "/theme.css",
                    "/app.css",
                    "/favicon.svg",
                ]:
                    assert len(request(base, asset)) > 0
                request(base, "/api/missing", expected=404)
                request(base, "/%2e%2e/server.py", expected=404)
                request(
                    base,
                    "/api/missing",
                    "POST",
                    {},
                    headers={"Origin": "https://untrusted.example"},
                    expected=403,
                )
                request(base, "/api/missing", "POST", [], expected=400)
                if slug == "applyboard":
                    item = request(
                        base,
                        "/api/applications",
                        "POST",
                        {
                            "company": "HTTP Test",
                            "role": "Engineer",
                            "stage": "applied",
                        },
                    )
                    updated = request(
                        base,
                        f"/api/applications/{item['id']}",
                        "PATCH",
                        {"stage": "interview", "version": 1},
                    )
                    assert updated["version"] == 2
                    request(
                        base,
                        f"/api/applications/{item['id']}",
                        "PATCH",
                        {"stage": "offer", "version": 1},
                        expected=409,
                    )
                    assert b"HTTP Test" in request(base, "/api/export.csv")
                    request(base, f"/api/applications/{item['id']}", "DELETE")
                elif slug == "ledgerlens":
                    source = "date,description,amount\n2026-01-01,HTTP expense,123.45"
                    assert (
                        request(base, "/api/import", "POST", {"csv": source})[
                            "inserted"
                        ]
                        == 1
                    )
                    assert (
                        request(base, "/api/import", "POST", {"csv": source})[
                            "duplicates"
                        ]
                        == 1
                    )
                    assert (
                        request(base, "/api/summary?month=2026-01")["net_cents"]
                        == 12345
                    )
                    request(
                        base,
                        "/api/import",
                        "POST",
                        {"csv": source.replace("123.45", "NaN")},
                        expected=400,
                    )
                elif slug == "stockroom":
                    r = request(
                        base,
                        "/api/reservations",
                        "POST",
                        {"sku": "KEY-01", "quantity": 2, "request_key": "http-test"},
                    )
                    again = request(
                        base,
                        "/api/reservations",
                        "POST",
                        {"sku": "KEY-01", "quantity": 2, "request_key": "http-test"},
                    )
                    assert r["id"] == again["id"]
                    request(base, f"/api/reservations/{r['id']}/ship", "POST", {})
                    request(base, f"/api/reservations/{r['id']}/ship", "POST", {})
                    assert (
                        next(
                            p
                            for p in request(base, "/api/products")
                            if p["sku"] == "KEY-01"
                        )["on_hand"]
                        == 30
                    )
                elif slug == "signaldesk":
                    d = request(
                        base,
                        "/api/documents",
                        "POST",
                        {
                            "title": "HTTP fixture",
                            "content": "A uniquelyfindable phrase in a source document.",
                        },
                    )
                    assert (
                        request(base, "/api/search?q=uniquelyfindable")["results"][0][
                            "document_id"
                        ]
                        == d["id"]
                    )
                    request(base, f"/api/documents/{d['id']}", "DELETE")
                    assert request(base, "/api/search?q=uniquelyfindable")["total"] == 0
                elif slug == "pitchside":
                    assert request(base, "/api/match")["count"] == 420
                    analysis = request(
                        base, "/api/analysis?team=Harbor%20FC&from=0&to=45"
                    )
                    assert 0 < analysis["events"] < 420
                    assert all(s["team"] == "Harbor FC" for s in analysis["shots"])
                    request(base, "/api/analysis?from=90&to=0", expected=400)
                elif slug == "queuecraft":
                    job = request(
                        base,
                        "/api/jobs",
                        "POST",
                        {"kind": "sum", "payload": {"numbers": [40, 2]}, "priority": 9},
                    )
                    for _ in range(100):
                        info = request(base, f"/api/jobs/{job['id']}")
                        if info["job"]["status"] == "succeeded":
                            break
                        time.sleep(0.05)
                    else:
                        raise AssertionError("Worker did not finish queued task")
                    assert info["job"]["result"]["sum"] == 42
                    assert any(h["event"] == "succeeded" for h in info["history"])
                print(f"HTTP integration: {slug} passed", flush=True)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--http-only", action="store_true")
    args = parser.parse_args()
    for slug in PROJECTS:
        if not args.http_only:
            command = (
                ["node", "--test", "tests/store.test.js"]
                if slug == "stockroom"
                else [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
            )
            subprocess.run(command, cwd=ROOT / slug, check=True)
            for source in (ROOT / slug / "static").glob("*.js"):
                subprocess.run(["node", "--check", str(source)], check=True)
        http_check(slug)
    print("All six projects verified.", flush=True)


if __name__ == "__main__":
    main()
