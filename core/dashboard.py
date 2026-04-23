import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _tail_events(log_file: Path, limit: int, severity: str | None = None):
    if not log_file.exists():
        return []
    with log_file.open("r", encoding="utf-8", errors="ignore") as handle:
        lines = handle.readlines()
    events = []
    severity_filter = str(severity).lower() if severity else None
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if severity_filter and str(event.get("severity", "")).lower() != severity_filter:
            continue
        events.append(event)
        if len(events) >= max(1, int(limit)):
            break
    events.reverse()
    return events


def _fallback_metrics(log_file: Path):
    if not log_file.exists():
        return {
            "total_events": 0,
            "critical_events": 0,
            "error_events": 0,
            "rate_limited_events": 0,
            "tool_errors": 0,
        }

    total = 0
    critical = 0
    errors = 0
    rate_limited = 0
    tool_errors = 0
    with log_file.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            total += 1
            severity = str(item.get("severity", "info")).lower()
            event = str(item.get("event", ""))
            if severity == "critical":
                critical += 1
            if severity == "error":
                errors += 1
            if event == "security.rate_limit_blocked":
                rate_limited += 1
            if event == "tool.execute" and severity == "error":
                tool_errors += 1
    return {
        "total_events": total,
        "critical_events": critical,
        "error_events": errors,
        "rate_limited_events": rate_limited,
        "tool_errors": tool_errors,
    }


def build_dashboard_server(
    host: str,
    port: int,
    audit_log_path: str,
    app_mode: str = "dev",
    max_events: int = 200,
    metrics_provider=None,
):
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
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)

            if parsed.path == "/api/health":
                uptime = round(time.time() - started_at, 2)
                self._write_json({"status": "ok", "mode": app_mode, "uptime_seconds": uptime})
                return

            if parsed.path == "/api/events":
                severity = (query.get("severity", [None])[0] or None)
                limit = int(query.get("limit", [str(max_events)])[0])
                events = _tail_events(log_file, limit=limit, severity=severity)
                self._write_json({"count": len(events), "events": events, "severity": severity})
                return

            if parsed.path == "/api/metrics":
                payload = metrics_provider() if callable(metrics_provider) else _fallback_metrics(log_file)
                payload = dict(payload or {})
                payload["mode"] = app_mode
                payload["uptime_seconds"] = round(time.time() - started_at, 2)
                self._write_json(payload)
                return

            if parsed.path in {"/", "/index.html"}:
                self._write_html(_dashboard_html())
                return

            self._write_json({"error": "not_found"}, status=404)

        def log_message(self, format, *args):  # noqa: A003
            return

    return ThreadingHTTPServer((host, int(port)), Handler)


def start_dashboard_in_background(
    host: str,
    port: int,
    audit_log_path: str,
    app_mode: str = "dev",
    max_events: int = 200,
    metrics_provider=None,
):
    server = build_dashboard_server(
        host=host,
        port=port,
        audit_log_path=audit_log_path,
        app_mode=app_mode,
        max_events=max_events,
        metrics_provider=metrics_provider,
    )
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
    .row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
    .muted { color: #94a3b8; font-size: 12px; }
    select { background: #020617; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; padding: 4px 6px; }
  </style>
</head>
<body>
  <h1>Jarvis Security Dashboard</h1>
  <div class="card"><h2>Health</h2><pre id="health">loading...</pre></div>
  <div class="card"><h2>Metrics</h2><pre id="metrics">loading...</pre></div>
  <div class="card">
    <h2>Events</h2>
    <div class="row">
      <label for="severity">severity:</label>
      <select id="severity">
        <option value="">all</option>
        <option value="info">info</option>
        <option value="warning">warning</option>
        <option value="error">error</option>
        <option value="critical">critical</option>
      </select>
    </div>
    <pre id="events">loading...</pre>
    <p class="muted">auto-refresh: 5s</p>
  </div>
  <script>
    async function load() {
      const severity = document.getElementById('severity').value;
      const suffix = severity ? ('?severity=' + encodeURIComponent(severity)) : '';
      const health = await fetch('/api/health').then(r => r.json()).catch(e => ({error: String(e)}));
      document.getElementById('health').textContent = JSON.stringify(health, null, 2);
      const metrics = await fetch('/api/metrics').then(r => r.json()).catch(e => ({error: String(e)}));
      document.getElementById('metrics').textContent = JSON.stringify(metrics, null, 2);
      const events = await fetch('/api/events' + suffix).then(r => r.json()).catch(e => ({error: String(e)}));
      document.getElementById('events').textContent = JSON.stringify(events, null, 2);
    }
    document.getElementById('severity').addEventListener('change', load);
    load();
    setInterval(load, 5000);
  </script>
</body>
</html>
"""
