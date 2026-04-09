import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def _tail_events(log_file: Path, limit: int):
    if not log_file.exists():
        return []
    with log_file.open("r", encoding="utf-8", errors="ignore") as handle:
        lines = handle.readlines()[-max(1, int(limit)):]
    events = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def build_dashboard_server(host: str, port: int, audit_log_path: str, app_mode: str = "dev", max_events: int = 200):
    started_at = time.time()
    log_file = Path(audit_log_path)

    class Handler(BaseHTTPRequestHandler):
        def _write_json(self, payload: dict, status: int = 200):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _write_html(self, html: str):
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            if self.path == "/api/health":
                uptime = round(time.time() - started_at, 2)
                self._write_json({"status": "ok", "mode": app_mode, "uptime_seconds": uptime})
                return

            if self.path == "/api/events":
                events = _tail_events(log_file, max_events)
                self._write_json({"count": len(events), "events": events})
                return

            if self.path in {"/", "/index.html"}:
                self._write_html(_dashboard_html())
                return

            self._write_json({"error": "not_found"}, status=404)

        def log_message(self, format, *args):  # noqa: A003
            return

    return ThreadingHTTPServer((host, int(port)), Handler)


def start_dashboard_in_background(host: str, port: int, audit_log_path: str, app_mode: str = "dev", max_events: int = 200):
    server = build_dashboard_server(host, port, audit_log_path, app_mode=app_mode, max_events=max_events)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _dashboard_html():
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Jarvis Dashboard</title>
  <style>
    body { font-family: Segoe UI, Arial, sans-serif; margin: 24px; background: #0f172a; color: #e2e8f0; }
    .card { background: #111827; border: 1px solid #1f2937; border-radius: 10px; padding: 16px; margin-bottom: 16px; }
    pre { white-space: pre-wrap; word-break: break-word; background: #020617; padding: 12px; border-radius: 8px; }
    .muted { color: #94a3b8; font-size: 12px; }
  </style>
</head>
<body>
  <h1>Jarvis Security Dashboard</h1>
  <div class="card"><h2>Health</h2><pre id="health">loading...</pre></div>
  <div class="card"><h2>Events</h2><pre id="events">loading...</pre><p class="muted">auto-refresh: 5s</p></div>
  <script>
    async function load() {
      const health = await fetch('/api/health').then(r => r.json()).catch(e => ({error: String(e)}));
      document.getElementById('health').textContent = JSON.stringify(health, null, 2);
      const events = await fetch('/api/events').then(r => r.json()).catch(e => ({error: String(e)}));
      document.getElementById('events').textContent = JSON.stringify(events, null, 2);
    }
    load();
    setInterval(load, 5000);
  </script>
</body>
</html>
"""
