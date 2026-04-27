import threading
import time
from datetime import datetime, timezone

try:
    import psutil
except Exception:  # pragma: no cover - dependencia opcional
    psutil = None


class SystemMonitorService:
    def __init__(
        self,
        enabled: bool = False,
        interval_seconds: int = 10,
        history_size: int = 180,
        cpu_alert_percent: float = 90.0,
        memory_alert_percent: float = 90.0,
        alert_cooldown_seconds: int = 120,
        auto_start: bool = False,
        sampler=None,
        audit_logger=None,
    ):
        self.enabled = bool(enabled)
        self.interval_seconds = max(2, int(interval_seconds))
        self.history_size = max(10, int(history_size))
        self.cpu_alert_percent = float(cpu_alert_percent)
        self.memory_alert_percent = float(memory_alert_percent)
        self.alert_cooldown_seconds = max(10, int(alert_cooldown_seconds))
        self.auto_start = bool(auto_start)
        self.sampler = sampler or self._default_sample
        self.audit = audit_logger

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker = None
        self._history = []
        self._last_alert_at = 0.0
        self._last_error = ""

        if self.auto_start and self.enabled:
            self.start()

    def start(self):
        if not self.enabled:
            return {"error": "Monitor de sistema desabilitado na configuracao."}
        if not callable(self.sampler):
            return {"error": "Coletor de sistema indisponivel (instale psutil)."}

        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return {"message": "Monitor de sistema ja estava ativo.", "status": self.status()}
            self._stop_event.clear()
            self._worker = threading.Thread(target=self._loop, daemon=True)
            self._worker.start()
        return {"message": "Monitor de sistema iniciado.", "status": self.status()}

    def stop(self):
        self._stop_event.set()
        worker = self._worker
        self._worker = None
        if worker is not None and worker.is_alive():
            worker.join(timeout=2.0)
        return {"message": "Monitor de sistema interrompido.", "status": self.status()}

    def close(self):
        self.stop()

    def status(self):
        latest = self._latest_sample()
        if latest is None and self.enabled and callable(self.sampler):
            latest = self.collect_once().get("sample")

        return {
            "enabled": self.enabled,
            "running": self._worker is not None and self._worker.is_alive(),
            "interval_seconds": self.interval_seconds,
            "history_size": self.history_size,
            "cpu_alert_percent": self.cpu_alert_percent,
            "memory_alert_percent": self.memory_alert_percent,
            "last_error": self._last_error,
            "latest": latest,
            "samples": len(self._snapshot_history()),
        }

    def summary(self):
        history = self._snapshot_history()
        if not history:
            return {
                "message": "Sem amostras de CPU/RAM ainda.",
                "summary": {
                    "samples": 0,
                },
            }

        cpu_values = [float(item.get("cpu_percent", 0.0)) for item in history]
        mem_values = [float(item.get("memory_percent", 0.0)) for item in history]
        latest = history[-1]
        summary = {
            "samples": len(history),
            "cpu_avg_percent": round(sum(cpu_values) / len(cpu_values), 2),
            "cpu_max_percent": round(max(cpu_values), 2),
            "memory_avg_percent": round(sum(mem_values) / len(mem_values), 2),
            "memory_max_percent": round(max(mem_values), 2),
            "latest": latest,
        }
        return {
            "message": (
                f"CPU avg={summary['cpu_avg_percent']}% max={summary['cpu_max_percent']}% | "
                f"RAM avg={summary['memory_avg_percent']}% max={summary['memory_max_percent']}%"
            ),
            "summary": summary,
        }

    def collect_once(self):
        if not callable(self.sampler):
            return {"error": "Coletor de sistema indisponivel (instale psutil)."}

        try:
            sample = self.sampler()
        except Exception as exc:
            message = f"Falha ao coletar metricas de sistema: {exc}"
            self._last_error = message
            self._audit("system.monitor_error", severity="warning", error=str(exc))
            return {"error": message}

        with self._lock:
            self._history.append(sample)
            if len(self._history) > self.history_size:
                self._history = self._history[-self.history_size :]

        self._evaluate_alert(sample)
        return {"sample": sample}

    def _loop(self):
        while not self._stop_event.is_set():
            self._stop_event.wait(self.interval_seconds)
            if self._stop_event.is_set():
                break
            self.collect_once()

    def _evaluate_alert(self, sample):
        cpu = float(sample.get("cpu_percent", 0.0))
        mem = float(sample.get("memory_percent", 0.0))
        if cpu < self.cpu_alert_percent and mem < self.memory_alert_percent:
            return

        now = time.time()
        if now - self._last_alert_at < self.alert_cooldown_seconds:
            return
        self._last_alert_at = now

        self._audit(
            "system.resource_alert",
            severity="warning",
            cpu_percent=cpu,
            memory_percent=mem,
            cpu_alert_percent=self.cpu_alert_percent,
            memory_alert_percent=self.memory_alert_percent,
        )

    def _latest_sample(self):
        with self._lock:
            if not self._history:
                return None
            return dict(self._history[-1])

    def _snapshot_history(self):
        with self._lock:
            return [dict(item) for item in self._history]

    def _audit(self, event, severity="info", **data):
        if self.audit is not None:
            try:
                self.audit.log(event, severity=severity, **data)
            except Exception:
                pass

    @staticmethod
    def _default_sample():
        if psutil is None:
            raise RuntimeError("psutil nao esta instalado")

        memory = psutil.virtual_memory()
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": round(float(psutil.cpu_percent(interval=None)), 2),
            "memory_percent": round(float(memory.percent), 2),
            "memory_used_mb": round(float(memory.used) / (1024 * 1024), 2),
            "memory_total_mb": round(float(memory.total) / (1024 * 1024), 2),
        }
