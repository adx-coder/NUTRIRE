"""
Analytics server — lightweight HTTP endpoint for frontend search analytics.

Receives anonymized events (ZIP searched, filters used, org clicked) and
writes them to logs/analytics.jsonl for offline analysis.

Usage:
  python scripts/analytics_server.py              # default port 3001
  python scripts/analytics_server.py --port 8080

The frontend sends POST /api/analytics with JSON body:
  { "event": "search", "zip": "20010", "filters": ["food_pantry"], "ts": "..." }
  { "event": "click", "orgId": "cafb-123", "zip": "20010", "ts": "..." }
  { "event": "filter", "filter": "nearby", "value": true, "ts": "..." }

Also serves GET /api/analytics/summary for a quick dashboard.
"""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
LOG_DIR = PIPELINE / "logs"
LOG_FILE = LOG_DIR / "analytics.jsonl"
LOG_DIR.mkdir(parents=True, exist_ok=True)


class AnalyticsHandler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/analytics":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"

        try:
            event = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        # Add server timestamp
        event["receivedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Append to JSONL log
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_GET(self):
        if self.path != "/api/analytics/summary":
            self.send_response(404)
            self.end_headers()
            return

        summary = _build_summary()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(summary, indent=2).encode())

    def log_message(self, format, *args):
        # Quiet logging
        pass


def _build_summary() -> dict:
    """Build analytics summary from the JSONL log."""
    if not LOG_FILE.exists():
        return {"totalEvents": 0, "searches": 0, "clicks": 0}

    events = []
    for line in LOG_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    zip_searches = Counter()
    org_clicks = Counter()
    filter_usage = Counter()
    event_types = Counter()

    for e in events:
        etype = e.get("event", "unknown")
        event_types[etype] += 1

        if etype == "search" and e.get("zip"):
            zip_searches[e["zip"]] += 1
        elif etype == "click" and e.get("orgId"):
            org_clicks[e["orgId"]] += 1
        elif etype == "filter" and e.get("filter"):
            filter_usage[e["filter"]] += 1

    return {
        "totalEvents": len(events),
        "eventTypes": dict(event_types),
        "topSearchedZips": dict(zip_searches.most_common(20)),
        "topClickedOrgs": dict(org_clicks.most_common(20)),
        "filterUsage": dict(filter_usage.most_common(20)),
        "zipsWithFewResults": {
            z: c for z, c in zip_searches.most_common(50)
            if c >= 3  # searched 3+ times — may indicate a gap
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Analytics server")
    parser.add_argument("--port", type=int, default=3001)
    args = parser.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), AnalyticsHandler)
    print(f"Analytics server listening on http://localhost:{args.port}")
    print(f"  POST /api/analytics       — log events")
    print(f"  GET  /api/analytics/summary — view summary")
    print(f"  Log file: {LOG_FILE}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
