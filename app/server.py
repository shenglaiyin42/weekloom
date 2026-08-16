#!/usr/bin/env python3
"""Run the Weekloom local MVP server."""

from __future__ import annotations

import json
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from data_store import create_action, create_inbox_item, create_project, create_review_request, default_data_dir, summary, update_action_status, update_week, upsert_review


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = default_data_dir()


class WeekloomHandler(BaseHTTPRequestHandler):
    server_version = "WeekloomMVP/0.1"

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def send_json(self, payload: object, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("request body is too large")
        raw = self.rfile.read(length)
        value = json.loads(raw or b"{}")
        if not isinstance(value, dict):
            raise ValueError("request body must be an object")
        return value

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/summary":
            try:
                self.send_json(summary(DATA_DIR))
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if parsed.path in {"/", "/index.html"}:
            body = (APP_DIR / "index.html").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self.read_json()
            if parsed.path == "/api/inbox":
                record = create_inbox_item(DATA_DIR, str(payload.get("title", "")), str(payload.get("notes", "")))
                self.send_json(record, HTTPStatus.CREATED)
                return

            if parsed.path == "/api/projects":
                record = create_project(DATA_DIR, payload)
                self.send_json(record, HTTPStatus.CREATED)
                return

            if parsed.path == "/api/actions":
                record = create_action(DATA_DIR, payload)
                self.send_json(record, HTTPStatus.CREATED)
                return

            if parsed.path == "/api/requests/review":
                record = create_review_request(DATA_DIR, payload.get("week_id"), str(payload.get("note", "")))
                self.send_json(record, HTTPStatus.CREATED)
                return

            week_match = re.fullmatch(r"/api/weeks/([0-9]{4}-W[0-9]{2})", parsed.path)
            if week_match:
                record = update_week(DATA_DIR, week_match.group(1), payload)
                self.send_json(record)
                return

            action_match = re.fullmatch(r"/api/actions/([a-z][a-z0-9_-]{2,80})/status", parsed.path)
            if action_match:
                record = update_action_status(DATA_DIR, action_match.group(1), str(payload.get("status", "")))
                self.send_json(record)
                return

            review_match = re.fullmatch(r"/api/reviews/([0-9]{4}-W[0-9]{2})", parsed.path)
            if review_match:
                record = upsert_review(DATA_DIR, review_match.group(1), payload)
                self.send_json(record)
                return
        except FileNotFoundError:
            self.send_json({"error": "record not found"}, HTTPStatus.NOT_FOUND)
            return
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), WeekloomHandler)
    print(f"Weekloom running at http://127.0.0.1:{port}")
    print(f"Data directory: {DATA_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Weekloom")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
