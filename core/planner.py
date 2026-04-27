import re
import unicodedata


class Planner:
    def create_plan(self, analysis):
        if not analysis:
            return None

        intent = analysis.get("intent", "unknown")
        response = analysis.get("response") or {
            "surveillance_start": "Vigilancia iniciada.",
            "intrusion_check": "Vigilancia iniciada.",
            "surveillance_stop": "Vigilancia interrompida.",
            "home_control": "Comando de automacao executado.",
            "network_scan": "Escaneando.",
            "network_search": "Pesquisando na internet.",
            "network_monitor_start": "Iniciando rastreamento de rede.",
            "network_monitor_stop": "Parando rastreamento de rede.",
            "network_monitor_status": "Consultando status do rastreamento de rede.",
            "network_monitor_summary": "Gerando resumo de trafego de rede.",
            "network_block_internet": "Bloqueando internet.",
            "network_unblock_internet": "Desbloqueando internet.",
            "network_block_machine_internet": "Bloqueando internet da maquina.",
            "network_unblock_machine_internet": "Desbloqueando internet da maquina.",
            "network_block_machine_isolate": "Isolando maquina da rede.",
            "network_unblock_machine": "Liberando maquina.",
            "network_list_blocks": "Listando bloqueios de rede.",
            "network_register_machine": "Registrando maquina.",
            "network_list_machines": "Listando maquinas cadastradas.",
            "home_register_device_commands": "Cadastrando novo dispositivo com comandos personalizados.",
            "home_device_wizard_start": "Iniciando assistente de dispositivo.",
            "home_device_wizard_set_open": "Definindo acao de abrir.",
            "home_device_wizard_set_close": "Definindo acao de fechar.",
            "home_device_wizard_finish": "Finalizando assistente de dispositivo.",
            "home_device_wizard_cancel": "Cancelando assistente de dispositivo.",
            "automation_scene_create": "Criando cena de automacao.",
            "automation_scene_run": "Executando cena.",
            "automation_scene_list": "Listando cenas.",
            "automation_scene_delete": "Removendo cena.",
            "automation_schedule_create": "Criando agendamento.",
            "automation_schedule_list": "Listando agendamentos.",
            "automation_schedule_cancel": "Cancelando agendamento.",
            "automation_rule_create": "Criando regra de automacao.",
            "automation_rule_list": "Listando regras.",
            "automation_rule_remove": "Removendo regra.",
            "automation_event_trigger": "Disparando evento para regras.",
            "backup_now": "Executando backup.",
            "backup_status": "Consultando status de backup.",
            "plugin_list": "Listando plugins.",
            "plugin_reload": "Recarregando plugins.",
            "confirm_critical_action": "Confirmando comando critico.",
            "question_answer": "Resposta direta.",
            "status": "Aqui esta o status atual.",
        }.get(intent, "Entendi.")

        if intent in {"surveillance_start", "intrusion_check"}:
            return {
                "steps": [
                    {"tool": "surveillance", "action": "start", "duration": analysis.get("duration", 20)},
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "surveillance_stop":
            return {"steps": [{"tool": "surveillance", "action": "stop"}, {"action": "respond", "message": response}]}

        if intent == "home_control":
            return {
                "steps": [
                    {
                        "tool": "home_control",
                        "device": analysis.get("device", "luz"),
                        "action": analysis.get("action", "on"),
                    },
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "record":
            return {"steps": [{"tool": "start_recording", "duration": analysis.get("duration", 10)}]}

        if intent == "network_scan":
            return {"steps": [{"tool": "network_scan", "limit": analysis.get("limit", 50)}, {"action": "respond", "message": response}]}

        if intent == "network_search":
            return {
                "steps": [
                    {"tool": "web_search", "query": analysis.get("query", ""), "limit": analysis.get("limit", 3)},
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "network_monitor_start":
            return {"steps": [{"tool": "network_monitor", "action": "start"}, {"action": "respond", "message": response}]}

        if intent == "network_monitor_stop":
            return {"steps": [{"tool": "network_monitor", "action": "stop"}, {"action": "respond", "message": response}]}

        if intent == "network_monitor_status":
            return {"steps": [{"tool": "network_monitor", "action": "status"}, {"action": "respond", "message": response}]}

        if intent == "network_monitor_summary":
            return {"steps": [{"tool": "network_monitor", "action": "summary"}, {"action": "respond", "message": response}]}

        if intent == "network_block_internet":
            return {"steps": [{"tool": "network_enforce", "action": "block_internet_global"}, {"action": "respond", "message": response}]}

        if intent == "network_unblock_internet":
            return {"steps": [{"tool": "network_enforce", "action": "unblock_internet_global"}, {"action": "respond", "message": response}]}

        if intent == "network_block_machine_internet":
            return {
                "steps": [
                    {"tool": "network_enforce", "action": "block_machine_internet", "alias": analysis.get("alias", "")},
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "network_unblock_machine_internet":
            return {
                "steps": [
                    {"tool": "network_enforce", "action": "unblock_machine_internet", "alias": analysis.get("alias", "")},
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "network_block_machine_isolate":
            return {
                "steps": [
                    {"tool": "network_enforce", "action": "block_machine_isolate", "alias": analysis.get("alias", "")},
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "network_unblock_machine":
            return {
                "steps": [
                    {"tool": "network_enforce", "action": "unblock_machine", "alias": analysis.get("alias", "")},
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "network_list_blocks":
            return {"steps": [{"tool": "network_enforce", "action": "list_blocks"}, {"action": "respond", "message": response}]}

        if intent == "network_register_machine":
            return {
                "steps": [
                    {
                        "tool": "network_enforce",
                        "action": "register_machine",
                        "alias": analysis.get("alias", ""),
                        "mac": analysis.get("mac", ""),
                    },
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "network_list_machines":
            return {"steps": [{"tool": "network_enforce", "action": "list_machines"}, {"action": "respond", "message": response}]}

        if intent == "home_register_device_commands":
            return {
                "steps": [
                    {
                        "tool": "home_control",
                        "action": "register_device",
                        "device": analysis.get("device", ""),
                        "open_action": analysis.get("open_action", ""),
                        "close_action": analysis.get("close_action", ""),
                    },
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "home_device_wizard_start":
            return {
                "steps": [
                    {"action": "device_wizard_start", "device": analysis.get("device", "")},
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "home_device_wizard_set_open":
            return {
                "steps": [
                    {"action": "device_wizard_set_open", "open_action": analysis.get("open_action", "")},
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "home_device_wizard_set_close":
            return {
                "steps": [
                    {"action": "device_wizard_set_close", "close_action": analysis.get("close_action", "")},
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "home_device_wizard_finish":
            return {"steps": [{"action": "device_wizard_finish"}]}

        if intent == "home_device_wizard_cancel":
            return {"steps": [{"action": "device_wizard_cancel"}]}

        if intent == "automation_scene_create":
            return {
                "steps": [
                    {
                        "tool": "automation_hub",
                        "action": "create_scene",
                        "scene": analysis.get("scene", ""),
                        "steps_payload": analysis.get("steps", []),
                    }
                ]
            }

        if intent == "automation_scene_run":
            return {"steps": [{"tool": "automation_hub", "action": "run_scene", "scene": analysis.get("scene", "")}]}

        if intent == "automation_scene_list":
            return {"steps": [{"tool": "automation_hub", "action": "list_scenes"}]}

        if intent == "automation_scene_delete":
            return {"steps": [{"tool": "automation_hub", "action": "delete_scene", "scene": analysis.get("scene", "")}]}

        if intent == "automation_schedule_create":
            return {
                "steps": [
                    {
                        "tool": "automation_hub",
                        "action": "schedule_scene",
                        "scene": analysis.get("scene", ""),
                        "delay_seconds": analysis.get("delay_seconds", 0),
                        "interval_seconds": analysis.get("interval_seconds", 0),
                    }
                ]
            }

        if intent == "automation_schedule_list":
            return {"steps": [{"tool": "automation_hub", "action": "list_schedules"}]}

        if intent == "automation_schedule_cancel":
            return {
                "steps": [
                    {
                        "tool": "automation_hub",
                        "action": "cancel_schedule",
                        "schedule_ref": analysis.get("schedule_ref", ""),
                    }
                ]
            }

        if intent == "automation_rule_create":
            return {
                "steps": [
                    {
                        "tool": "automation_hub",
                        "action": "create_rule",
                        "rule_name": analysis.get("rule_name", ""),
                        "event_name": analysis.get("event_name", ""),
                        "scene": analysis.get("scene", ""),
                        "contains": analysis.get("contains", ""),
                    }
                ]
            }

        if intent == "automation_rule_list":
            return {"steps": [{"tool": "automation_hub", "action": "list_rules"}]}

        if intent == "automation_rule_remove":
            return {
                "steps": [
                    {
                        "tool": "automation_hub",
                        "action": "remove_rule",
                        "rule_ref": analysis.get("rule_ref", ""),
                    }
                ]
            }

        if intent == "automation_event_trigger":
            return {
                "steps": [
                    {
                        "tool": "automation_hub",
                        "action": "trigger_event",
                        "event_name": analysis.get("event_name", ""),
                        "payload": analysis.get("payload", ""),
                    }
                ]
            }

        if intent == "backup_now":
            return {"steps": [{"tool": "backup_manager", "action": "run_now"}]}

        if intent == "backup_status":
            return {"steps": [{"tool": "backup_manager", "action": "status"}]}

        if intent == "plugin_list":
            return {"steps": [{"tool": "plugin_manager", "action": "list"}]}

        if intent == "plugin_reload":
            return {"steps": [{"tool": "plugin_manager", "action": "reload"}]}

        if intent == "confirm_critical_action":
            return {
                "steps": [
                    {
                        "action": "confirm_critical_action",
                        "token": analysis.get("token", ""),
                        "pin": analysis.get("pin", ""),
                    }
                ]
            }

        if intent == "question_answer":
            return {"steps": [{"action": "respond", "message": response}]}

        if intent == "remember":
            return {"steps": [{"action": "remember", "text": analysis.get("memory", "")}]}

        if intent == "recall":
            return {"steps": [{"action": "recall", "query": analysis.get("query", ""), "limit": analysis.get("limit", 2)}]}

        if intent == "status":
            return {"steps": [{"action": "status"}]}

        if intent == "memory_export":
            return {
                "steps": [
                    {
                        "action": "memory_export",
                        "path": analysis.get("path", "state/exports/memory-backup.enc"),
                        "password": analysis.get("password", ""),
                    }
                ]
            }

        if intent == "memory_import":
            return {
                "steps": [
                    {
                        "action": "memory_import",
                        "path": analysis.get("path", "state/exports/memory-backup.enc"),
                        "password": analysis.get("password", ""),
                    }
                ]
            }

        return {"steps": [{"action": "respond", "message": response}]}

    def decide(self, text: str):
        original = text.strip()
        if not original:
            return {"type": "ignore"}

        normalized = self._normalize(original)

        if "vigiar ambiente" in normalized or normalized in {"iniciar vigilancia", "iniciar vigia"}:
            return {"type": "start_surveillance"}

        if "parar vigilancia" in normalized or "interromper vigilancia" in normalized:
            return {"type": "stop_surveillance"}

        parts = original.split(maxsplit=3)
        if len(parts) == 4 and self._normalize(" ".join(parts[:3])) == "esse rosto e":
            return {"type": "label_face", "name": parts[3].strip()}

        label_match = re.match(r"^\s*esse rosto [eé]\s+(.+)$", original, flags=re.IGNORECASE)
        if label_match:
            return {"type": "label_face", "name": label_match.group(1).strip()}

        remember_match = re.match(r"^\s*(?:lembre|guarde|memorize)(?:\s+que)?\s+(.+)$", original, flags=re.IGNORECASE)
        if remember_match:
            return {"type": "remember", "memory": remember_match.group(1).strip()}

        for pattern in (
            r"^\s*o que voce sabe sobre\s+(.+)$",
            r"^\s*o que voce lembra sobre\s+(.+)$",
            r"^\s*procure na memoria\s+(.+)$",
        ):
            recall_match = re.match(pattern, normalized, flags=re.IGNORECASE)
            if recall_match:
                return {"type": "recall", "query": recall_match.group(1).strip()}

        if "rostos conhecidos" in normalized or "quem voce conhece" in normalized or "quais rostos conhecidos" in normalized:
            return {"type": "list_known_faces"}

        return {"type": "respond"}

    @staticmethod
    def _normalize(text: str):
        normalized = unicodedata.normalize("NFD", str(text).lower())
        return "".join(char for char in normalized if unicodedata.category(char) != "Mn")
