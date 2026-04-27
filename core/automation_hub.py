import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


class AutomationHubService:
    def __init__(
        self,
        home_tool=None,
        state_path: str = "state/automation_hub.json",
        scheduler_interval_seconds: float = 1.0,
        auto_start: bool = True,
        audit_logger=None,
    ):
        self.home_tool = home_tool
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.scheduler_interval_seconds = max(0.25, float(scheduler_interval_seconds))
        self.auto_start = bool(auto_start)
        self.audit = audit_logger
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker = None
        self._state = {
            "scenes": {},
            "schedules": [],
            "rules": [],
            "stats": {"scene_runs": 0, "triggered_rules": 0},
            "updated_at": None,
        }
        self._load_state()
        if self.auto_start:
            self.start_scheduler()

    def create_scene(self, scene: str, steps):
        scene_name = self._normalize_name(scene)
        normalized_steps = self._normalize_steps(steps)
        if not scene_name or not normalized_steps:
            return {"error": "Cena invalida. Informe nome e passos de dispositivo/acao."}

        with self._lock:
            self._state["scenes"][scene_name] = {
                "name": scene_name,
                "steps": normalized_steps,
                "updated_at": self._now_iso(),
            }
            self._touch_unlocked()
            self._save_unlocked()

        self._audit("automation.scene_created", scene=scene_name, steps=len(normalized_steps))
        return {"message": f"Cena '{scene_name}' criada com {len(normalized_steps)} passo(s).", "scene": scene_name}

    def list_scenes(self):
        with self._lock:
            scenes = [dict(item) for _, item in sorted(self._state["scenes"].items())]
        if not scenes:
            return {"message": "Nenhuma cena cadastrada.", "scenes": []}
        names = ", ".join(item["name"] for item in scenes)
        return {"message": f"Cenas cadastradas: {names}", "scenes": scenes}

    def delete_scene(self, scene: str):
        scene_name = self._normalize_name(scene)
        with self._lock:
            removed = self._state["scenes"].pop(scene_name, None)
            self._touch_unlocked()
            self._save_unlocked()
        if removed is None:
            return {"error": f"Cena '{scene_name}' nao encontrada."}
        self._audit("automation.scene_deleted", scene=scene_name)
        return {"message": f"Cena '{scene_name}' removida."}

    def run_scene(self, scene: str, reason: str = "manual"):
        scene_name = self._normalize_name(scene)
        with self._lock:
            config = dict(self._state["scenes"].get(scene_name, {}))
        if not config:
            return {"error": f"Cena '{scene_name}' nao encontrada."}
        if self.home_tool is None:
            return {"error": "Home automation nao configurada para executar cena."}

        results = []
        for item in config.get("steps", []):
            device = item.get("device", "")
            action = item.get("action", "")
            results.append(self.home_tool.run(device=device, action=action))

        with self._lock:
            self._state["stats"]["scene_runs"] = int(self._state["stats"].get("scene_runs", 0)) + 1
            self._touch_unlocked()
            self._save_unlocked()

        self._audit("automation.scene_executed", scene=scene_name, reason=reason, steps=len(results))
        return {
            "message": f"Cena '{scene_name}' executada com {len(results)} passo(s).",
            "scene": scene_name,
            "results": results,
        }

    def schedule_scene(self, scene: str, delay_seconds: int = 0, interval_seconds: int = 0):
        scene_name = self._normalize_name(scene)
        with self._lock:
            if scene_name not in self._state["scenes"]:
                return {"error": f"Cena '{scene_name}' nao encontrada para agendamento."}

            now = time.time()
            job = {
                "id": uuid.uuid4().hex[:8],
                "scene": scene_name,
                "next_run_at": now + max(1, int(delay_seconds or 1)),
                "interval_seconds": max(0, int(interval_seconds or 0)),
                "enabled": True,
                "created_at": self._now_iso(),
            }
            self._state["schedules"].append(job)
            self._touch_unlocked()
            self._save_unlocked()

        self._audit(
            "automation.schedule_created",
            schedule_id=job["id"],
            scene=scene_name,
            delay_seconds=delay_seconds,
            interval_seconds=interval_seconds,
        )
        return {"message": f"Agendamento criado ({job['id']}) para cena '{scene_name}'.", "schedule": job}

    def list_schedules(self):
        with self._lock:
            schedules = [dict(item) for item in self._state["schedules"]]
        if not schedules:
            return {"message": "Nenhum agendamento ativo.", "schedules": []}
        preview = ", ".join(f"{item['id']}->{item['scene']}" for item in schedules)
        return {"message": f"Agendamentos: {preview}", "schedules": schedules}

    def cancel_schedule(self, schedule_ref: str):
        normalized = self._normalize_name(schedule_ref)
        with self._lock:
            before = len(self._state["schedules"])
            self._state["schedules"] = [
                item
                for item in self._state["schedules"]
                if self._normalize_name(item.get("id", "")) != normalized
                and self._normalize_name(item.get("scene", "")) != normalized
            ]
            removed = before - len(self._state["schedules"])
            self._touch_unlocked()
            self._save_unlocked()
        if removed <= 0:
            return {"error": f"Agendamento '{schedule_ref}' nao encontrado."}
        self._audit("automation.schedule_canceled", schedule_ref=schedule_ref, removed=removed)
        return {"message": f"Agendamento '{schedule_ref}' cancelado.", "removed": removed}

    def create_rule(self, rule_name: str, event_name: str, scene: str, contains: str = "", cooldown_seconds: int = 60):
        name = self._normalize_name(rule_name)
        event = self._normalize_name(event_name)
        scene_name = self._normalize_name(scene)
        contains_norm = self._normalize_name(contains)
        if not name or not event or not scene_name:
            return {"error": "Regra invalida. Informe nome, evento e cena."}

        with self._lock:
            if scene_name not in self._state["scenes"]:
                return {"error": f"Cena '{scene_name}' nao encontrada para regra."}

            rule = {
                "id": uuid.uuid4().hex[:8],
                "name": name,
                "event": event,
                "scene": scene_name,
                "contains": contains_norm,
                "cooldown_seconds": max(0, int(cooldown_seconds)),
                "last_trigger_at": 0.0,
                "enabled": True,
                "created_at": self._now_iso(),
            }
            self._state["rules"] = [item for item in self._state["rules"] if self._normalize_name(item.get("name", "")) != name]
            self._state["rules"].append(rule)
            self._touch_unlocked()
            self._save_unlocked()

        self._audit("automation.rule_created", rule=name, trigger_event=event, scene=scene_name)
        return {"message": f"Regra '{name}' criada para evento '{event}'.", "rule": rule}

    def list_rules(self):
        with self._lock:
            rules = [dict(item) for item in self._state["rules"]]
        if not rules:
            return {"message": "Nenhuma regra cadastrada.", "rules": []}
        preview = ", ".join(f"{item['name']}:{item['event']}->{item['scene']}" for item in rules)
        return {"message": f"Regras: {preview}", "rules": rules}

    def remove_rule(self, rule_ref: str):
        normalized = self._normalize_name(rule_ref)
        with self._lock:
            before = len(self._state["rules"])
            self._state["rules"] = [
                item
                for item in self._state["rules"]
                if self._normalize_name(item.get("name", "")) != normalized
                and self._normalize_name(item.get("id", "")) != normalized
            ]
            removed = before - len(self._state["rules"])
            self._touch_unlocked()
            self._save_unlocked()
        if removed <= 0:
            return {"error": f"Regra '{rule_ref}' nao encontrada."}
        self._audit("automation.rule_removed", rule_ref=rule_ref, removed=removed)
        return {"message": f"Regra '{rule_ref}' removida.", "removed": removed}

    def trigger_event(self, event_name: str, payload: str = ""):
        event = self._normalize_name(event_name)
        payload_norm = self._normalize_name(payload)
        if not event:
            return {"error": "Evento invalido para trigger."}

        triggered = []
        now = time.time()
        with self._lock:
            for rule in self._state["rules"]:
                if not rule.get("enabled", True):
                    continue
                if self._normalize_name(rule.get("event", "")) != event:
                    continue

                contains = self._normalize_name(rule.get("contains", ""))
                if contains and contains not in payload_norm:
                    continue

                cooldown = max(0, int(rule.get("cooldown_seconds", 0)))
                if cooldown > 0 and now - float(rule.get("last_trigger_at", 0.0)) < cooldown:
                    continue

                rule["last_trigger_at"] = now
                triggered.append(dict(rule))

            self._state["stats"]["triggered_rules"] = int(self._state["stats"].get("triggered_rules", 0)) + len(triggered)
            self._touch_unlocked()
            self._save_unlocked()

        results = []
        for rule in triggered:
            scene_name = rule.get("scene", "")
            results.append(self.run_scene(scene_name, reason=f"rule:{rule.get('name', 'unknown')}"))

        self._audit("automation.event_triggered", trigger_event=event, payload=payload, triggered=len(triggered))
        return {
            "message": f"Evento '{event}' processado. Regras acionadas: {len(triggered)}.",
            "triggered_rules": triggered,
            "results": results,
        }

    def status(self):
        with self._lock:
            return {
                "scheduler_running": self._worker is not None and self._worker.is_alive(),
                "scenes": len(self._state.get("scenes", {})),
                "schedules": len(self._state.get("schedules", [])),
                "rules": len(self._state.get("rules", [])),
                "stats": dict(self._state.get("stats", {})),
                "state_path": str(self.state_path),
            }

    def start_scheduler(self):
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return {"message": "Scheduler de automacao ja estava ativo."}
            self._stop_event.clear()
            self._worker = threading.Thread(target=self._loop, daemon=True)
            self._worker.start()
        return {"message": "Scheduler de automacao iniciado."}

    def stop_scheduler(self):
        self._stop_event.set()
        worker = self._worker
        self._worker = None
        if worker is not None and worker.is_alive():
            worker.join(timeout=2.0)
        return {"message": "Scheduler de automacao interrompido."}

    def close(self):
        self.stop_scheduler()

    def _loop(self):
        while not self._stop_event.is_set():
            try:
                self._run_due_schedules()
            except Exception:
                pass
            self._stop_event.wait(self.scheduler_interval_seconds)

    def _run_due_schedules(self):
        due = []
        now = time.time()
        with self._lock:
            for job in self._state["schedules"]:
                if not job.get("enabled", True):
                    continue
                if float(job.get("next_run_at", 0.0)) <= now:
                    due.append(dict(job))

            for job in self._state["schedules"]:
                if self._normalize_name(job.get("id", "")) not in {self._normalize_name(item.get("id", "")) for item in due}:
                    continue
                interval = max(0, int(job.get("interval_seconds", 0)))
                if interval > 0:
                    job["next_run_at"] = now + interval
                else:
                    job["enabled"] = False
            self._touch_unlocked()
            self._save_unlocked()

        for job in due:
            self.run_scene(job.get("scene", ""), reason=f"schedule:{job.get('id', '')}")

    def _load_state(self):
        if not self.state_path.exists():
            return
        try:
            with self.state_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle) or {}
            if not isinstance(payload, dict):
                return
            self._state["scenes"] = payload.get("scenes", {}) if isinstance(payload.get("scenes"), dict) else {}
            self._state["schedules"] = payload.get("schedules", []) if isinstance(payload.get("schedules"), list) else []
            self._state["rules"] = payload.get("rules", []) if isinstance(payload.get("rules"), list) else []
            self._state["stats"] = payload.get("stats", {}) if isinstance(payload.get("stats"), dict) else {"scene_runs": 0, "triggered_rules": 0}
            self._state["updated_at"] = payload.get("updated_at")
        except Exception:
            pass

    def _save_unlocked(self):
        with self.state_path.open("w", encoding="utf-8") as handle:
            json.dump(self._state, handle, ensure_ascii=False, indent=2)

    def _touch_unlocked(self):
        self._state["updated_at"] = self._now_iso()

    def _audit(self, event, **data):
        if self.audit is not None:
            try:
                self.audit.log(event, **data)
            except Exception:
                pass

    @staticmethod
    def _normalize_steps(steps):
        normalized = []
        if not isinstance(steps, list):
            return normalized
        for step in steps:
            if not isinstance(step, dict):
                continue
            device = AutomationHubService._normalize_name(step.get("device", ""))
            action = AutomationHubService._normalize_name(step.get("action", ""))
            if not device or not action:
                continue
            normalized.append({"device": device, "action": action})
        return normalized

    @staticmethod
    def _normalize_name(value):
        text = str(value or "").strip().lower()
        normalized = "".join(char for char in text if char.isalnum() or char in {"_", "-", " "})
        normalized = " ".join(normalized.split())
        normalized = normalized.replace(" ", "_")
        return normalized

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).isoformat()
