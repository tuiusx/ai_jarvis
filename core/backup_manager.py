import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


class BackupManagerService:
    def __init__(
        self,
        long_memory=None,
        output_dir: str = "state/exports",
        password_env: str = "JARVIS_BACKUP_PASSWORD",
        interval_minutes: int = 0,
        audit_logger=None,
    ):
        self.long_memory = long_memory
        self.output_dir = Path(output_dir)
        self.password_env = str(password_env or "JARVIS_BACKUP_PASSWORD")
        self.interval_minutes = max(0, int(interval_minutes))
        self.audit = audit_logger
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker = None
        self.last_backup = {
            "path": "",
            "at": "",
            "status": "never",
            "reason": "",
        }
        if self.interval_minutes > 0:
            self.start()

    def run_now(self, reason: str = "manual"):
        if self.long_memory is None:
            return {"error": "Memoria de longo prazo nao configurada para backup."}

        password = os.getenv(self.password_env, "").strip()
        if not password:
            return {
                "error": (
                    f"Senha de backup nao configurada. Defina a variavel de ambiente {self.password_env}."
                )
            }

        file_name = f"memory-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.enc"
        target_path = self.output_dir / file_name
        try:
            saved = self.long_memory.export_encrypted(str(target_path), password=password)
        except Exception as exc:
            with self._lock:
                self.last_backup = {
                    "path": str(target_path),
                    "at": self._now_iso(),
                    "status": "error",
                    "reason": str(exc),
                }
            self._audit("backup.failed", severity="error", reason=reason, error=str(exc))
            return {"error": f"Falha no backup: {exc}"}

        with self._lock:
            self.last_backup = {
                "path": str(saved),
                "at": self._now_iso(),
                "status": "ok",
                "reason": reason,
            }
        self._audit("backup.completed", reason=reason, path=str(saved))
        return {"message": f"Backup criptografado criado em {saved}.", "path": str(saved)}

    def status(self):
        with self._lock:
            snapshot = dict(self.last_backup)
        snapshot.update(
            {
                "interval_minutes": self.interval_minutes,
                "running": self._worker is not None and self._worker.is_alive(),
                "output_dir": str(self.output_dir),
                "password_env": self.password_env,
            }
        )
        return snapshot

    def start(self):
        if self.interval_minutes <= 0:
            return {"message": "Backup automatico desabilitado (intervalo=0)."}
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return {"message": "Backup automatico ja estava ativo."}
            self._stop_event.clear()
            self._worker = threading.Thread(target=self._loop, daemon=True)
            self._worker.start()
        return {"message": "Backup automatico iniciado."}

    def stop(self):
        self._stop_event.set()
        worker = self._worker
        self._worker = None
        if worker is not None and worker.is_alive():
            worker.join(timeout=2.0)
        return {"message": "Backup automatico interrompido."}

    def close(self):
        self.stop()

    def _loop(self):
        interval = max(60, int(self.interval_minutes * 60))
        while not self._stop_event.is_set():
            self._stop_event.wait(interval)
            if self._stop_event.is_set():
                break
            self.run_now(reason="auto")

    def _audit(self, event, severity="info", **data):
        if self.audit is not None:
            try:
                self.audit.log(event, severity=severity, **data)
            except Exception:
                pass

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).isoformat()
