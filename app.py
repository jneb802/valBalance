#!/usr/bin/env python3
"""Run with python3 app.py; no third-party dependencies."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from model import DEFAULTS, analyze


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, kind="application/json"):
        raw = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/":
            self.send(200, Path(__file__).with_name("index.html").read_text(), "text/html")
        elif self.path == "/defaults":
            self.send(200, json.dumps(DEFAULTS))
        else:
            self.send(404, json.dumps({"error": "Not found"}))

    def do_POST(self):
        if self.path != "/analyze":
            self.send(404, json.dumps({"error": "Not found"}))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 200_000:
                raise ValueError("Scenario must be smaller than 200 KB")
            data = json.loads(self.rfile.read(length))
            result = analyze(data)
            self.send(200, json.dumps(result, allow_nan=False))
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            self.send(400, json.dumps({"error": f"Invalid scenario: {exc}"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Shrine Balance: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
