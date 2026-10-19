"""Serve the DDoS visualizer frontend and the combined flow data."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
DATA_PATH = BACKEND_DIR / "data" / "combined_ddos_flows.json"


class VisualizerRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path in {"/api/combined-ddos-flows", "/api/flows"}:
            self._serve_combined_flows()
            return

        if self.path == "/api/health":
            self._send_json({"status": "ok"})
            return

        if self.path == "/":
            self.path = "/index.html"

        return super().do_GET()

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def _serve_combined_flows(self):
        if not DATA_PATH.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "combined_ddos_flows.json not found")
            return

        payload = DATA_PATH.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, data):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the DDoS attack visualizer.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to.")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to.")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), VisualizerRequestHandler)
    print(f"Serving {FRONTEND_DIR} at http://{args.host}:{args.port}")
    print(f"Flow data endpoint: http://{args.host}:{args.port}/api/combined-ddos-flows")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()