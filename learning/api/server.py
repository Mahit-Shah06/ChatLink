"""
Local JSON API for the dashboard. Standard library only — no Flask, no FastAPI.

Binds to 127.0.0.1 by default: this is your data, it stays on your machine.
For phone access, put it behind Tailscale rather than opening a port.

    python -m learning.cli serve
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import parse_qs, urlparse

from ..capture import CaptureEngine, get_engine

log = logging.getLogger("learning.api")
STATIC_DIR = Path(__file__).parent / "static"


class Handler(BaseHTTPRequestHandler):
    engine: Optional[CaptureEngine] = None
    server_version = "LearningEngine/1.0"

    def log_message(self, fmt, *args):
        log.debug("%s - %s", self.address_string(), fmt % args)

    # ------------------------------------------------------------------ util
    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, ctype: str) -> None:
        if not path.exists():
            return self._json({"error": "not found"}, 404)
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _s(params, key, default=None):
        v = params.get(key, [None])[0]
        return v if v not in (None, "") else default

    @staticmethod
    def _i(params, key, default):
        try:
            return int(params.get(key, [default])[0])
        except (TypeError, ValueError):
            return default

    # ------------------------------------------------------------------- GET
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route, params = parsed.path, parse_qs(parsed.query)
        repo = self.engine.repo

        try:
            if route in ("/", "/index.html"):
                return self._file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            if not route.startswith("/api/"):
                return self._json({"error": "not found"}, 404)

            routes: Dict[str, Callable[[], Any]] = {
                "/api/meta": lambda: {
                    **self.engine.stats(),
                    "labels_available": ["question", "note", "idea", "progress",
                                         "revision", "resource", "random"],
                },
                "/api/summary": lambda: {**repo.summary(), "streak": repo.streak()},
                "/api/labels": lambda: repo.label_counts(),
                "/api/activity": lambda: repo.daily_activity(self._i(params, "days", 30)),
                "/api/hourly": repo.hourly_pattern,
                "/api/topics": lambda: repo.topic_stats(
                    self._s(params, "kind"), self._i(params, "limit", 60)),
                "/api/weak": lambda: repo.weak_topics(
                    self._i(params, "min", 2), self._i(params, "limit", 12)),
                "/api/stale": lambda: repo.stale_topics(
                    self._i(params, "days", 14), self._i(params, "limit", 12)),
                "/api/graph": lambda: repo.graph(self._i(params, "limit", 120)),
                "/api/candidates": lambda: repo.candidates(
                    self._i(params, "limit", 30), self._i(params, "min", 2)),
                "/api/channels": repo.per_channel,
                "/api/entries": lambda: repo.entries(
                    label=self._s(params, "label"),
                    node_key=self._s(params, "node"),
                    query=self._s(params, "q"),
                    needs_review=self._s(params, "review") == "1",
                    limit=self._i(params, "limit", 40),
                    offset=self._i(params, "offset", 0)),
            }

            handler = routes.get(route)
            if handler is None:
                return self._json({"error": "unknown endpoint", "path": route}, 404)
            return self._json(handler())

        except Exception as exc:
            log.exception("GET %s failed", route)
            return self._json({"error": str(exc)}, 500)

    # ------------------------------------------------------------------ POST
    def do_POST(self) -> None:
        route = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid json"}, 400)

        try:
            if route == "/api/label":
                ok = self.engine.repo.relabel(
                    int(payload["message_id"]), str(payload["label"]), "human")
                return self._json({"ok": ok})
            if route == "/api/reclassify":
                return self._json(self.engine.reclassify_all(payload.get("classifier")))
            return self._json({"error": "unknown endpoint"}, 404)
        except KeyError as exc:
            return self._json({"error": f"missing field: {exc}"}, 400)
        except Exception as exc:
            log.exception("POST %s failed", route)
            return self._json({"error": str(exc)}, 500)


def serve(host: str = "127.0.0.1", port: int = 8787, open_browser: bool = False) -> None:
    engine = get_engine()
    Handler.engine = engine

    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"\n  Learning Engine dashboard: {url}")
    print(f"  Reading: {engine.db.path.resolve()}\n")

    if open_browser:
        import webbrowser
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
