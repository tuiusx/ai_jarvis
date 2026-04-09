from datetime import datetime, timedelta
from pathlib import Path


class RetentionManager:
    def __init__(self, settings: dict, audit_logger=None):
        self.settings = settings
        self.audit = audit_logger

    def cleanup(self):
        retention_cfg = self.settings.get("retention", {})
        if not retention_cfg.get("enabled", True):
            return {"enabled": False, "deleted": 0}

        deleted = 0
        deleted += self._cleanup_recordings()
        deleted += self._cleanup_faces()

        summary = {"enabled": True, "deleted": deleted}
        if self.audit:
            self.audit.log("retention.cleanup", deleted=deleted)
        return summary

    def _cleanup_recordings(self):
        recording_cfg = self.settings.get("recording", {})
        retention_cfg = self.settings.get("retention", {})
        output_dir = Path(recording_cfg.get("output_dir", "recordings"))
        max_files = int(retention_cfg.get("max_recordings", 200))
        max_age_days = int(retention_cfg.get("max_age_days", 30))
        return self._cleanup_directory(
            folder=output_dir,
            max_files=max_files,
            max_age_days=max_age_days,
            patterns={".mp4", ".avi", ".mov", ".mkv"},
        )

    def _cleanup_faces(self):
        retention_cfg = self.settings.get("retention", {})
        faces_dir = Path("faces")
        max_files = int(retention_cfg.get("max_faces", 2000))
        max_age_days = int(retention_cfg.get("max_age_days", 30))
        return self._cleanup_directory(
            folder=faces_dir,
            max_files=max_files,
            max_age_days=max_age_days,
            patterns={".jpg", ".jpeg", ".png"},
        )

    @staticmethod
    def _cleanup_directory(folder: Path, max_files: int, max_age_days: int, patterns: set[str]):
        if not folder.exists():
            return 0

        deleted = 0
        now = datetime.now()
        cutoff = now - timedelta(days=max(0, max_age_days))

        files = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in patterns]

        for file_path in files:
            modified = datetime.fromtimestamp(file_path.stat().st_mtime)
            if modified < cutoff:
                file_path.unlink(missing_ok=True)
                deleted += 1

        files = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in patterns]
        if max_files > 0 and len(files) > max_files:
            files.sort(key=lambda p: p.stat().st_mtime)
            to_delete = files[: len(files) - max_files]
            for file_path in to_delete:
                file_path.unlink(missing_ok=True)
                deleted += 1

        return deleted
