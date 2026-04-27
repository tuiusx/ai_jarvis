import os
import shlex
import subprocess
import sys
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
        periodic_tests_enabled: bool = False,
        tests_interval_minutes: int = 0,
        tests_command: str = "",
        tests_timeout_seconds: int = 1200,
        tests_workdir: str = ".",
        command_runner=None,
        audit_logger=None,
    ):
        self.long_memory = long_memory
        self.output_dir = Path(output_dir)
        self.password_env = str(password_env or "JARVIS_BACKUP_PASSWORD")
        self.interval_minutes = max(0, int(interval_minutes))
        self.periodic_tests_enabled = bool(periodic_tests_enabled)
        self.tests_interval_minutes = max(0, int(tests_interval_minutes))
        self.tests_command = str(tests_command or "").strip() or f"{sys.executable} -m pytest -q"
        self.tests_timeout_seconds = max(30, int(tests_timeout_seconds))
        self.tests_workdir = Path(tests_workdir)
        self.command_runner = command_runner or _default_command_runner
        self.audit = audit_logger
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tests_workdir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker = None
        self.last_backup = {
            "path": "",
            "at": "",
            "status": "never",
            "reason": "",
        }
        self.last_tests = {
            "status": "never",
            "at": "",
            "reason": "",
            "returncode": None,
            "duration_seconds": 0.0,
            "summary": "",
            "command": self.tests_command,
        }

        if self._has_periodic_work():
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
            tests_snapshot = dict(self.last_tests)
        snapshot.update(
            {
                "interval_minutes": self.interval_minutes,
                "running": self._worker is not None and self._worker.is_alive(),
                "output_dir": str(self.output_dir),
                "password_env": self.password_env,
                "periodic_tests_enabled": self.periodic_tests_enabled,
                "tests_interval_minutes": self.tests_interval_minutes,
                "tests_timeout_seconds": self.tests_timeout_seconds,
                "tests_workdir": str(self.tests_workdir),
                "tests": tests_snapshot,
            }
        )
        return snapshot

    def run_tests_now(self, reason: str = "manual"):
        args = self._build_tests_args()
        if not args:
            return {"error": "Comando de testes invalido para execucao periodica."}

        started = time.perf_counter()
        try:
            result = self.command_runner(
                args=args,
                timeout=self.tests_timeout_seconds,
                workdir=str(self.tests_workdir),
            )
            duration = round(time.perf_counter() - started, 3)
            output = f"{result.stdout or ''}\n{result.stderr or ''}".strip()
            status = "ok" if int(result.returncode) == 0 else "failed"
            summary = self._summarize_test_output(output=output, status=status, returncode=int(result.returncode))
            with self._lock:
                self.last_tests = {
                    "status": status,
                    "at": self._now_iso(),
                    "reason": reason,
                    "returncode": int(result.returncode),
                    "duration_seconds": duration,
                    "summary": summary,
                    "command": self.tests_command,
                }
        except Exception as exc:
            duration = round(time.perf_counter() - started, 3)
            with self._lock:
                self.last_tests = {
                    "status": "error",
                    "at": self._now_iso(),
                    "reason": reason,
                    "returncode": None,
                    "duration_seconds": duration,
                    "summary": str(exc),
                    "command": self.tests_command,
                }
            self._audit("tests.periodic_failed", severity="error", reason=reason, error=str(exc))
            return {"error": f"Falha ao executar testes periodicos: {exc}"}

        current = self.status().get("tests", {})
        severity = "info" if current.get("status") == "ok" else "warning"
        self._audit(
            "tests.periodic_completed",
            severity=severity,
            reason=reason,
            status=current.get("status"),
            duration_seconds=current.get("duration_seconds"),
            returncode=current.get("returncode"),
        )
        if current.get("status") == "ok":
            return {"message": "Testes executados com sucesso.", "report": current}
        return {"message": "Testes executados com falhas.", "report": current}

    def start(self):
        if not self._has_periodic_work():
            return {
                "message": (
                    "Execucao periodica desabilitada. Ajuste backup.interval_minutes "
                    "ou backup.periodic_tests.interval_minutes."
                )
            }
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
        backup_interval = max(60, int(self.interval_minutes * 60)) if self.interval_minutes > 0 else 0
        tests_interval = (
            max(60, int(self.tests_interval_minutes * 60))
            if self.periodic_tests_enabled and self.tests_interval_minutes > 0
            else 0
        )
        next_backup_at = time.time() + backup_interval if backup_interval > 0 else None
        next_tests_at = time.time() + tests_interval if tests_interval > 0 else None

        while not self._stop_event.is_set():
            now = time.time()
            due = [value for value in (next_backup_at, next_tests_at) if value is not None]
            wait_seconds = 60.0
            if due:
                wait_seconds = max(1.0, min(due) - now)

            self._stop_event.wait(wait_seconds)
            if self._stop_event.is_set():
                break

            now = time.time()
            if next_backup_at is not None and now >= next_backup_at:
                self.run_now(reason="auto")
                while next_backup_at is not None and next_backup_at <= now:
                    next_backup_at += backup_interval

            if next_tests_at is not None and now >= next_tests_at:
                self.run_tests_now(reason="auto")
                while next_tests_at is not None and next_tests_at <= now:
                    next_tests_at += tests_interval

    def _audit(self, event, severity="info", **data):
        if self.audit is not None:
            try:
                self.audit.log(event, severity=severity, **data)
            except Exception:
                pass

    def _has_periodic_work(self):
        has_backup = self.interval_minutes > 0
        has_tests = self.periodic_tests_enabled and self.tests_interval_minutes > 0
        return bool(has_backup or has_tests)

    def _build_tests_args(self):
        command = str(self.tests_command or "").strip()
        if not command:
            return []
        try:
            return shlex.split(command, posix=os.name != "nt")
        except Exception:
            return command.split()

    @staticmethod
    def _summarize_test_output(output: str, status: str, returncode: int):
        content = str(output or "").strip()
        if not content:
            return f"status={status} returncode={returncode}"
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        tail = lines[-6:] if lines else []
        summary = " | ".join(tail)
        if len(summary) > 500:
            summary = summary[-500:]
        return summary

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).isoformat()


def _default_command_runner(args, timeout: int, workdir: str):
    return subprocess.run(
        args,
        check=False,
        timeout=timeout,
        text=True,
        encoding="utf-8",
        errors="ignore",
        capture_output=True,
        cwd=workdir,
    )
