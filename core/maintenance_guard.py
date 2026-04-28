import os
import threading
from datetime import datetime, timezone


class MaintenanceGuardService:
    def __init__(
        self,
        enabled: bool = True,
        auto_start: bool = True,
        check_interval_seconds: int = 300,
        auto_repair: bool = True,
        max_backup_age_minutes: int = 1440,
        max_tests_age_minutes: int = 720,
        admin_pin_env: str = "JARVIS_ADMIN_PIN",
        backup_manager=None,
        system_monitor=None,
        audit_logger=None,
    ):
        self.enabled = bool(enabled)
        self.auto_start = bool(auto_start)
        self.check_interval_seconds = max(30, int(check_interval_seconds))
        self.auto_repair = bool(auto_repair)
        self.max_backup_age_minutes = max(0, int(max_backup_age_minutes))
        self.max_tests_age_minutes = max(0, int(max_tests_age_minutes))
        self.admin_pin_env = str(admin_pin_env or "JARVIS_ADMIN_PIN")
        self.backup_manager = backup_manager
        self.system_monitor = system_monitor
        self.audit = audit_logger

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker = None
        self._last_report = {}

        if self.enabled and self.auto_start:
            self.start()
            self.check_now(reason="startup")

    def start(self):
        if not self.enabled:
            return {"error": "Maintenance guard desabilitado na configuracao."}

        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return {"message": "Maintenance guard ja estava ativo.", "status": self.status()}
            self._stop_event.clear()
            self._worker = threading.Thread(target=self._loop, daemon=True)
            self._worker.start()
        return {"message": "Maintenance guard iniciado.", "status": self.status()}

    def stop(self):
        self._stop_event.set()
        worker = self._worker
        self._worker = None
        if worker is not None and worker.is_alive():
            worker.join(timeout=2.0)
        return {"message": "Maintenance guard interrompido.", "status": self.status()}

    def close(self):
        self.stop()

    def status(self):
        with self._lock:
            report = dict(self._last_report)
        return {
            "enabled": self.enabled,
            "running": self._worker is not None and self._worker.is_alive(),
            "auto_repair": self.auto_repair,
            "check_interval_seconds": self.check_interval_seconds,
            "max_backup_age_minutes": self.max_backup_age_minutes,
            "max_tests_age_minutes": self.max_tests_age_minutes,
            "admin_pin_env": self.admin_pin_env,
            "last_report": report,
        }

    def check_now(self, reason: str = "manual"):
        report = self._build_report(reason=reason)
        if self.auto_repair:
            auto_repair = self._apply_auto_repair(report)
            report["auto_repair_result"] = auto_repair
        else:
            report["auto_repair_result"] = {"attempted": False, "actions": []}

        with self._lock:
            self._last_report = dict(report)

        severity = "warning" if report.get("overall_status") == "degraded" else "info"
        self._audit(
            "maintenance.check",
            severity=severity,
            reason=reason,
            overall_status=report.get("overall_status"),
            issues=report.get("issues", []),
        )
        if report.get("overall_status") == "degraded":
            self._audit(
                "maintenance.degraded",
                severity="warning",
                reason=reason,
                issues=report.get("issues", []),
            )
        return {"message": self._report_message(report), "report": report}

    def _loop(self):
        while not self._stop_event.is_set():
            self._stop_event.wait(self.check_interval_seconds)
            if self._stop_event.is_set():
                break
            self.check_now(reason="auto")

    def _build_report(self, reason: str):
        checks = {}
        issues = []

        backup_password_ok = self._has_backup_password()
        checks["backup_password"] = {
            "ok": backup_password_ok,
            "message": "Senha de backup configurada." if backup_password_ok else "Senha de backup ausente.",
        }
        if not backup_password_ok:
            issues.append("backup_password_missing")

        admin_pin_ok = bool(os.getenv(self.admin_pin_env, "").strip())
        checks["admin_pin"] = {
            "ok": admin_pin_ok,
            "message": "PIN administrativo configurado." if admin_pin_ok else "PIN administrativo ausente.",
        }
        if not admin_pin_ok:
            issues.append("admin_pin_missing")

        backup_health = self._evaluate_backup_health()
        checks["backup_freshness"] = backup_health
        if not backup_health.get("ok", True):
            issues.append(backup_health.get("issue", "backup_unhealthy"))

        tests_health = self._evaluate_tests_health()
        checks["tests_freshness"] = tests_health
        if not tests_health.get("ok", True):
            issues.append(tests_health.get("issue", "tests_unhealthy"))

        monitor_health = self._evaluate_monitor_health()
        checks["system_monitor"] = monitor_health
        if not monitor_health.get("ok", True):
            issues.append(monitor_health.get("issue", "system_monitor_unhealthy"))

        overall = "ok" if not issues else "degraded"
        return {
            "checked_at": self._now_iso(),
            "reason": reason,
            "overall_status": overall,
            "issues": issues,
            "checks": checks,
        }

    def _evaluate_backup_health(self):
        if self.backup_manager is None:
            return {"ok": True, "skipped": True, "message": "Backup manager nao configurado."}

        try:
            status = self.backup_manager.status()
        except Exception as exc:
            return {"ok": False, "issue": "backup_status_error", "message": str(exc)}

        last_at = self._parse_iso(status.get("at"))
        last_state = str(status.get("status", "")).strip().lower()
        if last_state != "ok" or last_at is None:
            return {
                "ok": False,
                "issue": "backup_not_recent",
                "message": "Nenhum backup valido encontrado.",
                "status": last_state or "unknown",
            }

        age_minutes = self._age_minutes(last_at)
        if self.max_backup_age_minutes > 0 and age_minutes > self.max_backup_age_minutes:
            return {
                "ok": False,
                "issue": "backup_stale",
                "message": f"Ultimo backup com {age_minutes:.1f} min (limite {self.max_backup_age_minutes}).",
                "age_minutes": round(age_minutes, 2),
            }

        return {
            "ok": True,
            "status": last_state,
            "age_minutes": round(age_minutes, 2),
            "message": f"Backup valido ha {age_minutes:.1f} min.",
        }

    def _evaluate_tests_health(self):
        if self.backup_manager is None:
            return {"ok": True, "skipped": True, "message": "Backup manager nao configurado."}

        try:
            status = self.backup_manager.status()
        except Exception as exc:
            return {"ok": False, "issue": "tests_status_error", "message": str(exc)}

        periodic_enabled = bool(status.get("periodic_tests_enabled", False))
        tests_data = status.get("tests", {}) if isinstance(status.get("tests"), dict) else {}
        tests_status = str(tests_data.get("status", "never")).strip().lower()
        tests_at = self._parse_iso(tests_data.get("at"))

        if not periodic_enabled:
            return {"ok": True, "skipped": True, "message": "Testes periodicos desabilitados."}

        if tests_status != "ok" or tests_at is None:
            return {
                "ok": False,
                "issue": "tests_not_recent",
                "message": "Nenhuma execucao de testes periodicos com sucesso.",
                "status": tests_status,
            }

        age_minutes = self._age_minutes(tests_at)
        if self.max_tests_age_minutes > 0 and age_minutes > self.max_tests_age_minutes:
            return {
                "ok": False,
                "issue": "tests_stale",
                "message": f"Ultimos testes com {age_minutes:.1f} min (limite {self.max_tests_age_minutes}).",
                "age_minutes": round(age_minutes, 2),
            }

        return {
            "ok": True,
            "status": tests_status,
            "age_minutes": round(age_minutes, 2),
            "message": f"Testes periodicos OK ha {age_minutes:.1f} min.",
        }

    def _evaluate_monitor_health(self):
        if self.system_monitor is None:
            return {"ok": True, "skipped": True, "message": "Monitor de sistema nao configurado."}

        try:
            status = self.system_monitor.status()
        except Exception as exc:
            return {"ok": False, "issue": "system_monitor_status_error", "message": str(exc)}

        enabled = bool(status.get("enabled", False))
        running = bool(status.get("running", False))
        if enabled and not running:
            return {
                "ok": False,
                "issue": "system_monitor_stopped",
                "message": "Monitor de sistema habilitado, mas parado.",
            }

        return {
            "ok": True,
            "enabled": enabled,
            "running": running,
            "message": "Monitor de sistema operacional.",
        }

    def _apply_auto_repair(self, report):
        actions = []
        if self.backup_manager is not None:
            try:
                backup_status = self.backup_manager.status()
                backup_has_schedule = bool(int(backup_status.get("interval_minutes", 0)) > 0)
                tests_has_schedule = bool(
                    bool(backup_status.get("periodic_tests_enabled", False))
                    and int(backup_status.get("tests_interval_minutes", 0)) > 0
                )
                if backup_has_schedule or tests_has_schedule:
                    actions.append({"target": "backup_manager", "result": self.backup_manager.start()})
            except Exception as exc:
                actions.append({"target": "backup_manager", "error": str(exc)})

        if self.system_monitor is not None:
            try:
                actions.append({"target": "system_monitor", "result": self.system_monitor.start()})
            except Exception as exc:
                actions.append({"target": "system_monitor", "error": str(exc)})

        for action in actions:
            if "error" in action:
                self._audit(
                    "maintenance.autofix_failed",
                    severity="warning",
                    target=action.get("target"),
                    error=action.get("error"),
                )
            else:
                self._audit(
                    "maintenance.autofix_applied",
                    severity="info",
                    target=action.get("target"),
                    result=action.get("result"),
                )

        return {
            "attempted": True,
            "actions": actions,
            "issues_before_repair": list(report.get("issues", [])),
        }

    def _has_backup_password(self):
        if self.backup_manager is None:
            return True
        env_name = str(getattr(self.backup_manager, "password_env", "JARVIS_BACKUP_PASSWORD"))
        return bool(os.getenv(env_name, "").strip())

    def _audit(self, event, severity="info", **data):
        if self.audit is not None:
            try:
                self.audit.log(event, severity=severity, **data)
            except Exception:
                pass

    @staticmethod
    def _parse_iso(value):
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _age_minutes(value: datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - value.astimezone(timezone.utc)
        return max(0.0, delta.total_seconds() / 60.0)

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _report_message(report):
        issues = report.get("issues", [])
        if not issues:
            return "Checklist de manutencao OK. Sem riscos pendentes."
        joined = ", ".join(issues)
        return f"Checklist de manutencao com pendencias: {joined}."
