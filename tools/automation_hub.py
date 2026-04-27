from tools.base import Tool


class AutomationHubTool(Tool):
    name = "automation_hub"
    description = "Gerencia cenas, agendamentos e regras de automacao."

    def __init__(self, service=None):
        self.service = service

    def run(self, action="", **kwargs):
        if self.service is None:
            return {"error": "Servico de automacao nao configurado."}

        normalized = str(action or "").strip().lower()
        if normalized == "create_scene":
            return self.service.create_scene(
                scene=kwargs.get("scene", ""),
                steps=kwargs.get("steps_payload", []),
            )
        if normalized == "run_scene":
            return self.service.run_scene(scene=kwargs.get("scene", ""))
        if normalized == "list_scenes":
            return self.service.list_scenes()
        if normalized == "delete_scene":
            return self.service.delete_scene(scene=kwargs.get("scene", ""))
        if normalized == "schedule_scene":
            return self.service.schedule_scene(
                scene=kwargs.get("scene", ""),
                delay_seconds=int(kwargs.get("delay_seconds", 0) or 0),
                interval_seconds=int(kwargs.get("interval_seconds", 0) or 0),
            )
        if normalized == "list_schedules":
            return self.service.list_schedules()
        if normalized == "cancel_schedule":
            return self.service.cancel_schedule(schedule_ref=kwargs.get("schedule_ref", ""))
        if normalized == "create_rule":
            return self.service.create_rule(
                rule_name=kwargs.get("rule_name", ""),
                event_name=kwargs.get("event_name", ""),
                scene=kwargs.get("scene", ""),
                contains=kwargs.get("contains", ""),
            )
        if normalized == "list_rules":
            return self.service.list_rules()
        if normalized == "remove_rule":
            return self.service.remove_rule(rule_ref=kwargs.get("rule_ref", ""))
        if normalized == "trigger_event":
            return self.service.trigger_event(
                event_name=kwargs.get("event_name", ""),
                payload=kwargs.get("payload", ""),
            )
        if normalized == "status":
            status = self.service.status()
            return {"message": "Status da automacao carregado.", "status": status}
        if normalized == "start_scheduler":
            return self.service.start_scheduler()
        if normalized == "stop_scheduler":
            return self.service.stop_scheduler()
        return {"error": f"Acao de automacao nao suportada: {action}"}
