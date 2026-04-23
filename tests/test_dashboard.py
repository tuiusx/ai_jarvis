import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import urlopen

from core.dashboard import build_dashboard_server


class DashboardTests(unittest.TestCase):
    def test_health_events_filter_and_metrics_endpoints(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "audit.log.jsonl"
            entries = [
                {"event": "agent.perception", "severity": "info", "data": {}},
                {"event": "security.intrusion_detected", "severity": "critical", "data": {}},
            ]
            log_path.write_text("\n".join(json.dumps(item) for item in entries) + "\n", encoding="utf-8")

            server = build_dashboard_server(
                host="127.0.0.1",
                port=0,
                audit_log_path=str(log_path),
                app_mode="dev",
                max_events=10,
                metrics_provider=lambda: {"total_events": 2, "critical_events": 1},
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address

            try:
                time.sleep(0.1)

                with urlopen(f"http://{host}:{port}/api/health", timeout=3) as response:
                    health = json.loads(response.read().decode("utf-8"))
                self.assertEqual(health["status"], "ok")

                with urlopen(f"http://{host}:{port}/api/events?severity=critical", timeout=3) as response:
                    events = json.loads(response.read().decode("utf-8"))
                self.assertEqual(events["count"], 1)
                self.assertEqual(events["events"][0]["event"], "security.intrusion_detected")

                with urlopen(f"http://{host}:{port}/api/metrics", timeout=3) as response:
                    metrics = json.loads(response.read().decode("utf-8"))
                self.assertEqual(metrics["total_events"], 2)
                self.assertEqual(metrics["critical_events"], 1)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
