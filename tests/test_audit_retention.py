import os
import tempfile
import time
import unittest
from pathlib import Path

from core.audit import AuditLogger
from core.retention import RetentionManager


class AuditRetentionTests(unittest.TestCase):
    def test_audit_logger_writes_and_tails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "state" / "audit.log.jsonl"
            audit = AuditLogger(str(log_path))
            audit.log("test.event", severity="info", value=1)
            audit.log("test.event", severity="warning", value=2)
            entries = audit.tail(limit=10)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[-1]["severity"], "warning")

    def test_audit_logger_rotates_by_size_and_updates_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "state" / "audit.log.jsonl"
            audit = AuditLogger(str(log_path), max_bytes=180, backup_count=2)
            for _ in range(10):
                audit.log("security.intrusion_detected", severity="critical", details="x" * 40)

            rotated = list(log_path.parent.glob("audit.log.jsonl.*"))
            self.assertTrue(rotated)

            metrics = audit.metrics()
            self.assertEqual(metrics["total_events"], 10)
            self.assertEqual(metrics["critical_events"], 10)

    def test_audit_notifies_on_critical_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            notified = []
            log_path = Path(temp_dir) / "state" / "audit.log.jsonl"
            audit = AuditLogger(str(log_path), notify_callback=lambda entry: notified.append(entry))
            audit.log("agent.analysis", severity="info")
            audit.log("security.intrusion_detected", severity="critical")
            self.assertEqual(len(notified), 1)
            self.assertEqual(notified[0]["event"], "security.intrusion_detected")

    def test_retention_deletes_old_recordings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                recordings_dir = Path("recordings")
                recordings_dir.mkdir(parents=True, exist_ok=True)
                old_file = recordings_dir / "old.mp4"
                old_file.write_bytes(b"video")
                old_time = time.time() - (60 * 60 * 24 * 40)  # 40 days old
                os.utime(old_file, (old_time, old_time))

                settings = {
                    "recording": {"output_dir": "recordings"},
                    "retention": {
                        "enabled": True,
                        "max_age_days": 30,
                        "max_recordings": 100,
                        "max_faces": 100,
                    },
                }
                manager = RetentionManager(settings=settings)
                summary = manager.cleanup()
                self.assertGreaterEqual(summary["deleted"], 1)
                self.assertFalse(old_file.exists())
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
