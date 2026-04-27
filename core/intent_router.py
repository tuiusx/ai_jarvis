import json
import re
import unicodedata
from pathlib import Path

from core.plugin_registry import PluginRegistry


class IntentRouter:
    MEMORY_EXPORT_RE = re.compile(r"^\s*exportar memoria(?: para)?\s+(\S+)(?:\s+senha\s+(.+))?\s*$", flags=re.IGNORECASE)
    MEMORY_IMPORT_RE = re.compile(r"^\s*importar memoria(?: de)?\s+(\S+)(?:\s+senha\s+(.+))?\s*$", flags=re.IGNORECASE)
    WEB_SEARCH_PATTERNS = [
        re.compile(r"^\s*(?:pesquise|pesquisar|procure|busque)\s+(?:na|no)\s+(?:internet|web|net|google)\s+(.+)$", flags=re.IGNORECASE),
        re.compile(r"^\s*(?:pesquise|pesquisar)\s+sobre\s+(.+)$", flags=re.IGNORECASE),
    ]
    MONITOR_START_RE = re.compile(
        r"^\s*(?:iniciar|ativar|ligar|comecar)\s+(?:rastreamento|monitoramento)\s+de\s+rede\s*$",
        flags=re.IGNORECASE,
    )
    MONITOR_STOP_RE = re.compile(
        r"^\s*(?:parar|desativar|desligar)\s+(?:rastreamento|monitoramento)\s+de\s+rede\s*$",
        flags=re.IGNORECASE,
    )
    MONITOR_STATUS_RE = re.compile(r"^\s*status\s+(?:do\s+)?(?:rastreamento|monitoramento)\s+de\s+rede\s*$", flags=re.IGNORECASE)
    MONITOR_SUMMARY_RE = re.compile(r"^\s*resumo\s+(?:de\s+)?trafego\s+de\s+rede\s*$", flags=re.IGNORECASE)
    BACKUP_NOW_RE = re.compile(r"^\s*(?:executar|rodar|fazer)\s+backup(?:\s+agora)?\s*$", flags=re.IGNORECASE)
    BACKUP_STATUS_RE = re.compile(r"^\s*status\s+(?:do\s+)?backup\s*$", flags=re.IGNORECASE)
    TESTS_NOW_RE = re.compile(r"^\s*(?:executar|rodar|fazer)\s+testes(?:\s+agora)?\s*$", flags=re.IGNORECASE)
    TESTS_STATUS_RE = re.compile(r"^\s*status\s+(?:dos\s+)?testes\s*$", flags=re.IGNORECASE)
    SYSTEM_MONITOR_START_RE = re.compile(
        r"^\s*(?:iniciar|ativar|ligar|comecar)\s+monitoramento\s+de\s+sistema\s*$",
        flags=re.IGNORECASE,
    )
    SYSTEM_MONITOR_STOP_RE = re.compile(
        r"^\s*(?:parar|desativar|desligar)\s+monitoramento\s+de\s+sistema\s*$",
        flags=re.IGNORECASE,
    )
    SYSTEM_MONITOR_STATUS_RE = re.compile(
        r"^\s*status\s+(?:do\s+)?monitoramento\s+de\s+sistema\s*$",
        flags=re.IGNORECASE,
    )
    SYSTEM_MONITOR_SUMMARY_RE = re.compile(
        r"^\s*resumo\s+(?:de\s+)?(?:recursos|cpu|ram)\s+do\s+sistema\s*$",
        flags=re.IGNORECASE,
    )
    PLUGIN_LIST_RE = re.compile(r"^\s*listar\s+plugins\s*$", flags=re.IGNORECASE)
    PLUGIN_RELOAD_RE = re.compile(r"^\s*(?:recarregar|atualizar)\s+plugins\s*$", flags=re.IGNORECASE)
    WIZARD_START_RE = re.compile(
        r"^\s*(?:iniciar|abrir|comecar)\s+assistente\s+de\s+dispositivo\s+([a-z0-9_\-\s]+)\s*$",
        flags=re.IGNORECASE,
    )
    WIZARD_SET_OPEN_RE = re.compile(
        r"^\s*definir\s+acao\s+abrir\s+([a-z0-9_\-\s]+)\s*$",
        flags=re.IGNORECASE,
    )
    WIZARD_SET_CLOSE_RE = re.compile(
        r"^\s*definir\s+acao\s+fechar\s+([a-z0-9_\-\s]+)\s*$",
        flags=re.IGNORECASE,
    )
    WIZARD_FINISH_RE = re.compile(
        r"^\s*(?:finalizar|concluir)\s+assistente\s+de\s+dispositivo\s*$",
        flags=re.IGNORECASE,
    )
    WIZARD_CANCEL_RE = re.compile(
        r"^\s*(?:cancelar|encerrar)\s+assistente\s+de\s+dispositivo\s*$",
        flags=re.IGNORECASE,
    )
    CREATE_SCENE_RE = re.compile(
        r"^\s*criar\s+cena\s+([a-z0-9_\-\s]+)\s+com\s+(.+)\s*$",
        flags=re.IGNORECASE,
    )
    RUN_SCENE_RE = re.compile(
        r"^\s*(?:executar|rodar|ativar)\s+cena\s+([a-z0-9_\-\s]+)\s*$",
        flags=re.IGNORECASE,
    )
    LIST_SCENES_RE = re.compile(r"^\s*listar\s+cenas\s*$", flags=re.IGNORECASE)
    DELETE_SCENE_RE = re.compile(
        r"^\s*(?:remover|apagar|deletar)\s+cena\s+([a-z0-9_\-\s]+)\s*$",
        flags=re.IGNORECASE,
    )
    SCHEDULE_SCENE_RE = re.compile(
        r"^\s*agendar\s+cena\s+([a-z0-9_\-\s]+)\s+em\s+(\d+)\s*(s|segundos|min|minutos|h|horas)\s*(?:a\s+cada\s+(\d+)\s*(s|segundos|min|minutos|h|horas))?\s*$",
        flags=re.IGNORECASE,
    )
    LIST_SCHEDULES_RE = re.compile(r"^\s*listar\s+agendamentos\s*$", flags=re.IGNORECASE)
    CANCEL_SCHEDULE_RE = re.compile(
        r"^\s*(?:cancelar|remover|deletar)\s+agendamento\s+([a-z0-9_\-\s]+)\s*$",
        flags=re.IGNORECASE,
    )
    CREATE_RULE_RE = re.compile(
        r"^\s*criar\s+regra\s+([a-z0-9_\-\s]+)\s+quando\s+([a-z0-9_\-\s]+)\s+executar\s+cena\s+([a-z0-9_\-\s]+)(?:\s+se\s+contiver\s+(.+))?\s*$",
        flags=re.IGNORECASE,
    )
    LIST_RULES_RE = re.compile(r"^\s*listar\s+regras\s*$", flags=re.IGNORECASE)
    REMOVE_RULE_RE = re.compile(
        r"^\s*(?:remover|apagar|deletar)\s+regra\s+([a-z0-9_\-\s]+)\s*$",
        flags=re.IGNORECASE,
    )
    TRIGGER_EVENT_RE = re.compile(
        r"^\s*disparar\s+evento\s+([a-z0-9_\-\s]+)(?:\s+(.+))?\s*$",
        flags=re.IGNORECASE,
    )
    MACHINE_REGISTER_RE = re.compile(
        r"^\s*(?:registrar|cadastrar)\s+maquina\s+([a-z0-9_\-\s]+)\s+([0-9a-f:\-]{17})\s*$",
        flags=re.IGNORECASE,
    )
    LIST_MACHINES_RE = re.compile(r"^\s*listar\s+maquinas(?:\s+de\s+rede)?\s*$", flags=re.IGNORECASE)
    BLOCK_INTERNET_RE = re.compile(
        r"^\s*bloquear\s+internet(?:\s+da\s+maquina\s+([a-z0-9_\-\s]+))?\s*$",
        flags=re.IGNORECASE,
    )
    UNBLOCK_INTERNET_RE = re.compile(
        r"^\s*desbloquear\s+internet(?:\s+da\s+maquina\s+([a-z0-9_\-\s]+))?\s*$",
        flags=re.IGNORECASE,
    )
    BLOCK_MACHINE_RE = re.compile(r"^\s*bloquear\s+maquina\s+([a-z0-9_\-\s]+)\s*$", flags=re.IGNORECASE)
    UNBLOCK_MACHINE_RE = re.compile(r"^\s*desbloquear\s+maquina\s+([a-z0-9_\-\s]+)\s*$", flags=re.IGNORECASE)
    LIST_BLOCKS_RE = re.compile(r"^\s*listar\s+bloqueios\s+de\s+rede\s*$", flags=re.IGNORECASE)
    REMEMBER_RE = re.compile(r"^\s*(?:lembre|guarde|memorize)(?:\s+que)?\s+(.+)$", flags=re.IGNORECASE)
    RECALL_RE = re.compile(r"^\s*o que voce sabe sobre\s+(.+?)[\?]?\s*$", flags=re.IGNORECASE)
    CONFIRM_CRITICAL_RE = re.compile(
        r"^\s*(?:confirmar|confirmo)\s+(?:comando\s+)?([a-f0-9]{6,12})(?:\s+(?:pin|codigo)\s+([a-zA-Z0-9_\-]{4,32}))?\s*$",
        flags=re.IGNORECASE,
    )
    CUSTOM_DEVICE_PATTERNS = (
        re.compile(
            r"^\s*(?:jarvis[\s,]+)?(?:adicionar|adiciona|cadastrar|registrar)\s+(?:o\s+)?comando(?:s)?\s+"
            r"(?:pra|para)\s+(?:o\s+)?dispositivo\s+([a-z0-9_\-\s]+?)\s+"
            r"(?:para\s+)?([a-z0-9_\-\s]+?)\s+e\s+([a-z0-9_\-\s]+)\s*$",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"^\s*(?:jarvis[\s,]+)?(?:adicionar|adiciona|cadastrar|registrar)\s+(?:o\s+)?dispositivo\s+"
            r"([a-z0-9_\-\s]+?)\s+(?:com\s+)?comando(?:s)?\s+([a-z0-9_\-\s]+?)\s+e\s+([a-z0-9_\-\s]+)\s*$",
            flags=re.IGNORECASE,
        ),
    )

    NETWORK_SCAN_TOKENS = [
        "escanear rede",
        "scanear rede",
        "varrer rede",
        "dispositivos na rede",
        "quem esta na rede",
        "quem esta conectado",
        "rede da casa",
        "wifi da casa",
    ]
    INTRUSION_TOKENS = ["invas", "intrus", "estranh", "desconhec", "parede", "escura"]
    SURVEILLANCE_START_TOKENS = ["iniciar vigilancia", "ligar vigilancia", "comecar vigilancia", "vigiar ambiente"]
    SURVEILLANCE_STOP_TOKENS = ["parar vigilancia", "desligar vigilancia", "pausar vigilancia"]
    STATUS_TOKENS = ["status", "como esta", "tudo bem", "resumo do sistema"]
    GREETING_TOKENS = ["ola", "oi", "bom dia", "boa tarde", "boa noite"]
    QUESTION_STARTERS = (
        "o que",
        "qual",
        "quais",
        "como",
        "quando",
        "onde",
        "por que",
        "porque",
        "quem",
        "quanto",
        "me explica",
        "explique",
    )

    def __init__(
        self,
        custom_commands_path: str = "state/home_custom_devices.json",
        plugin_registry=None,
        plugin_directory: str = "state/plugins",
        plugins_enabled: bool = True,
    ):
        self.custom_commands_path = Path(custom_commands_path)
        self._custom_devices_cache = {}
        self._custom_devices_mtime_ns = None
        self.plugin_registry = plugin_registry or PluginRegistry(
            directory=plugin_directory,
            enabled=plugins_enabled,
        )

    def route(self, content_raw: str):
        content = self.normalize(content_raw)

        confirm_match = self.CONFIRM_CRITICAL_RE.match(content)
        if confirm_match:
            token = confirm_match.group(1).strip().lower()
            pin = (confirm_match.group(2) or "").strip()
            return {
                "intent": "confirm_critical_action",
                "token": token,
                "pin": pin,
                "response": f"Confirmando comando critico {token}.",
                "needs_action": True,
                "action": "confirm_critical_action",
            }

        if self.BACKUP_NOW_RE.match(content):
            return {
                "intent": "backup_now",
                "response": "Executando backup seguro agora.",
                "needs_action": True,
                "action": "backup_now",
            }

        if self.BACKUP_STATUS_RE.match(content):
            return {
                "intent": "backup_status",
                "response": "Consultando status do backup.",
                "needs_action": True,
                "action": "backup_status",
            }

        if self.TESTS_NOW_RE.match(content):
            return {
                "intent": "tests_run_now",
                "response": "Executando testes agora.",
                "needs_action": True,
                "action": "tests_run_now",
            }

        if self.TESTS_STATUS_RE.match(content):
            return {
                "intent": "tests_status",
                "response": "Consultando status dos testes periodicos.",
                "needs_action": True,
                "action": "tests_status",
            }

        if self.SYSTEM_MONITOR_START_RE.match(content):
            return {
                "intent": "system_monitor_start",
                "response": "Iniciando monitoramento de CPU/RAM.",
                "needs_action": True,
                "action": "system_monitor_start",
            }

        if self.SYSTEM_MONITOR_STOP_RE.match(content):
            return {
                "intent": "system_monitor_stop",
                "response": "Parando monitoramento de CPU/RAM.",
                "needs_action": True,
                "action": "system_monitor_stop",
            }

        if self.SYSTEM_MONITOR_STATUS_RE.match(content):
            return {
                "intent": "system_monitor_status",
                "response": "Consultando status de CPU e memoria.",
                "needs_action": True,
                "action": "system_monitor_status",
            }

        if self.SYSTEM_MONITOR_SUMMARY_RE.match(content):
            return {
                "intent": "system_monitor_summary",
                "response": "Gerando resumo de uso de CPU e RAM.",
                "needs_action": True,
                "action": "system_monitor_summary",
            }

        if self.PLUGIN_LIST_RE.match(content):
            return {
                "intent": "plugin_list",
                "response": "Listando plugins ativos.",
                "needs_action": True,
                "action": "plugin_list",
            }

        if self.PLUGIN_RELOAD_RE.match(content):
            return {
                "intent": "plugin_reload",
                "response": "Recarregando plugins locais.",
                "needs_action": True,
                "action": "plugin_reload",
            }

        wizard_start = self.WIZARD_START_RE.match(content)
        if wizard_start:
            return {
                "intent": "home_device_wizard_start",
                "device": self._normalize_identifier(wizard_start.group(1)),
                "response": "Assistente de dispositivo iniciado.",
                "needs_action": True,
                "action": "home_device_wizard_start",
            }

        wizard_open = self.WIZARD_SET_OPEN_RE.match(content)
        if wizard_open:
            return {
                "intent": "home_device_wizard_set_open",
                "open_action": self.normalize(wizard_open.group(1)).strip(),
                "response": "Acao de abrir registrada no assistente.",
                "needs_action": True,
                "action": "home_device_wizard_set_open",
            }

        wizard_close = self.WIZARD_SET_CLOSE_RE.match(content)
        if wizard_close:
            return {
                "intent": "home_device_wizard_set_close",
                "close_action": self.normalize(wizard_close.group(1)).strip(),
                "response": "Acao de fechar registrada no assistente.",
                "needs_action": True,
                "action": "home_device_wizard_set_close",
            }

        if self.WIZARD_FINISH_RE.match(content):
            return {
                "intent": "home_device_wizard_finish",
                "response": "Concluindo assistente de dispositivo.",
                "needs_action": True,
                "action": "home_device_wizard_finish",
            }

        if self.WIZARD_CANCEL_RE.match(content):
            return {
                "intent": "home_device_wizard_cancel",
                "response": "Cancelando assistente de dispositivo.",
                "needs_action": True,
                "action": "home_device_wizard_cancel",
            }

        create_scene = self.CREATE_SCENE_RE.match(content)
        if create_scene:
            scene_name = self._normalize_identifier(create_scene.group(1))
            steps = self._parse_scene_steps(create_scene.group(2))
            if not steps:
                return {
                    "intent": "question_answer",
                    "response": "Cena invalida. Use formato: criar cena <nome> com luz:on, fechadura:lock.",
                    "needs_action": False,
                }
            return {
                "intent": "automation_scene_create",
                "scene": scene_name,
                "steps": steps,
                "response": f"Criando cena {scene_name}.",
                "needs_action": True,
                "action": "automation_scene_create",
            }

        run_scene = self.RUN_SCENE_RE.match(content)
        if run_scene:
            scene_name = self._normalize_identifier(run_scene.group(1))
            return {
                "intent": "automation_scene_run",
                "scene": scene_name,
                "response": f"Executando cena {scene_name}.",
                "needs_action": True,
                "action": "automation_scene_run",
            }

        if self.LIST_SCENES_RE.match(content):
            return {
                "intent": "automation_scene_list",
                "response": "Listando cenas.",
                "needs_action": True,
                "action": "automation_scene_list",
            }

        delete_scene = self.DELETE_SCENE_RE.match(content)
        if delete_scene:
            scene_name = self._normalize_identifier(delete_scene.group(1))
            return {
                "intent": "automation_scene_delete",
                "scene": scene_name,
                "response": f"Removendo cena {scene_name}.",
                "needs_action": True,
                "action": "automation_scene_delete",
            }

        schedule_scene = self.SCHEDULE_SCENE_RE.match(content)
        if schedule_scene:
            scene_name = self._normalize_identifier(schedule_scene.group(1))
            delay_seconds = self._duration_to_seconds(schedule_scene.group(2), schedule_scene.group(3))
            interval_raw = schedule_scene.group(4)
            interval_unit = schedule_scene.group(5)
            interval_seconds = self._duration_to_seconds(interval_raw, interval_unit) if interval_raw else 0
            return {
                "intent": "automation_schedule_create",
                "scene": scene_name,
                "delay_seconds": delay_seconds,
                "interval_seconds": interval_seconds,
                "response": f"Agendando cena {scene_name}.",
                "needs_action": True,
                "action": "automation_schedule_create",
            }

        if self.LIST_SCHEDULES_RE.match(content):
            return {
                "intent": "automation_schedule_list",
                "response": "Listando agendamentos.",
                "needs_action": True,
                "action": "automation_schedule_list",
            }

        cancel_schedule = self.CANCEL_SCHEDULE_RE.match(content)
        if cancel_schedule:
            schedule_ref = self._normalize_identifier(cancel_schedule.group(1))
            return {
                "intent": "automation_schedule_cancel",
                "schedule_ref": schedule_ref,
                "response": f"Cancelando agendamento {schedule_ref}.",
                "needs_action": True,
                "action": "automation_schedule_cancel",
            }

        create_rule = self.CREATE_RULE_RE.match(content)
        if create_rule:
            rule_name = self._normalize_identifier(create_rule.group(1))
            event_name = self._normalize_identifier(create_rule.group(2))
            scene_name = self._normalize_identifier(create_rule.group(3))
            contains = self._normalize_identifier(create_rule.group(4) or "")
            return {
                "intent": "automation_rule_create",
                "rule_name": rule_name,
                "event_name": event_name,
                "scene": scene_name,
                "contains": contains,
                "response": f"Criando regra {rule_name}.",
                "needs_action": True,
                "action": "automation_rule_create",
            }

        if self.LIST_RULES_RE.match(content):
            return {
                "intent": "automation_rule_list",
                "response": "Listando regras.",
                "needs_action": True,
                "action": "automation_rule_list",
            }

        remove_rule = self.REMOVE_RULE_RE.match(content)
        if remove_rule:
            rule_ref = self._normalize_identifier(remove_rule.group(1))
            return {
                "intent": "automation_rule_remove",
                "rule_ref": rule_ref,
                "response": f"Removendo regra {rule_ref}.",
                "needs_action": True,
                "action": "automation_rule_remove",
            }

        trigger_event = self.TRIGGER_EVENT_RE.match(content)
        if trigger_event:
            event_name = self._normalize_identifier(trigger_event.group(1))
            payload = str(trigger_event.group(2) or "").strip()
            return {
                "intent": "automation_event_trigger",
                "event_name": event_name,
                "payload": payload,
                "response": f"Disparando evento {event_name}.",
                "needs_action": True,
                "action": "automation_event_trigger",
            }

        custom_registration = self._match_custom_device_registration(content)
        if custom_registration is not None:
            return custom_registration

        plugin_match = self._match_plugin_command(content_raw)
        if plugin_match is not None:
            return plugin_match

        memory_export = self.MEMORY_EXPORT_RE.match(content)
        if memory_export:
            password = (memory_export.group(2) or "").strip()
            if not password:
                return {
                    "intent": "question_answer",
                    "response": "Para exportar a memoria com seguranca, informe uma senha no comando.",
                    "needs_action": False,
                }
            return {
                "intent": "memory_export",
                "path": memory_export.group(1).strip(),
                "password": password,
                "response": "Gerando backup seguro da memoria.",
                "needs_action": True,
                "action": "memory_export",
            }

        memory_import = self.MEMORY_IMPORT_RE.match(content)
        if memory_import:
            password = (memory_import.group(2) or "").strip()
            if not password:
                return {
                    "intent": "question_answer",
                    "response": "Para importar a memoria com seguranca, informe a senha do backup.",
                    "needs_action": False,
                }
            return {
                "intent": "memory_import",
                "path": memory_import.group(1).strip(),
                "password": password,
                "response": "Importando backup seguro da memoria.",
                "needs_action": True,
                "action": "memory_import",
            }

        for pattern in self.WEB_SEARCH_PATTERNS:
            web_search_match = pattern.match(content)
            if web_search_match:
                query = web_search_match.group(1).strip(" .?!")
                return {
                    "intent": "network_search",
                    "query": query,
                    "response": f"Vou pesquisar na internet sobre {query}.",
                    "needs_action": True,
                    "action": "network_search",
                }

        if any(token in content for token in self.INTRUSION_TOKENS):
            return {
                "intent": "intrusion_check",
                "response": "Detectei um possivel risco. Vou ligar a vigilancia e monitorar rostos desconhecidos.",
                "needs_action": True,
                "action": "surveillance_start",
            }

        if any(token in content for token in self.SURVEILLANCE_START_TOKENS):
            return {
                "intent": "surveillance_start",
                "response": "Vigilancia ativada. Monitorando ambiente.",
                "needs_action": True,
                "action": "surveillance_start",
            }

        if any(token in content for token in self.SURVEILLANCE_STOP_TOKENS):
            return {
                "intent": "surveillance_stop",
                "response": "Vigilancia pausada.",
                "needs_action": True,
                "action": "surveillance_stop",
            }

        if any(token in content for token in self.NETWORK_SCAN_TOKENS):
            return {
                "intent": "network_scan",
                "response": "Vou identificar os dispositivos visiveis na rede da casa.",
                "needs_action": True,
                "action": "network_scan",
            }

        if self.MONITOR_START_RE.match(content):
            return {
                "intent": "network_monitor_start",
                "response": "Iniciando rastreamento de rede.",
                "needs_action": True,
                "action": "network_monitor_start",
            }

        if self.MONITOR_STOP_RE.match(content):
            return {
                "intent": "network_monitor_stop",
                "response": "Parando rastreamento de rede.",
                "needs_action": True,
                "action": "network_monitor_stop",
            }

        if self.MONITOR_STATUS_RE.match(content):
            return {
                "intent": "network_monitor_status",
                "response": "Consultando status do rastreamento de rede.",
                "needs_action": True,
                "action": "network_monitor_status",
            }

        if self.MONITOR_SUMMARY_RE.match(content):
            return {
                "intent": "network_monitor_summary",
                "response": "Gerando resumo do trafego de rede.",
                "needs_action": True,
                "action": "network_monitor_summary",
            }

        machine_register = self.MACHINE_REGISTER_RE.match(content)
        if machine_register:
            alias = machine_register.group(1).strip()
            mac = machine_register.group(2).strip()
            return {
                "intent": "network_register_machine",
                "alias": alias,
                "mac": mac,
                "response": f"Registrando maquina {alias}.",
                "needs_action": True,
                "action": "network_register_machine",
            }

        if self.LIST_MACHINES_RE.match(content):
            return {
                "intent": "network_list_machines",
                "response": "Listando maquinas cadastradas.",
                "needs_action": True,
                "action": "network_list_machines",
            }

        block_internet_match = self.BLOCK_INTERNET_RE.match(content)
        if block_internet_match:
            alias = (block_internet_match.group(1) or "").strip()
            if alias:
                return {
                    "intent": "network_block_machine_internet",
                    "alias": alias,
                    "response": f"Bloqueando internet da maquina {alias}.",
                    "needs_action": True,
                    "action": "network_block_machine_internet",
                }
            return {
                "intent": "network_block_internet",
                "response": "Bloqueando internet.",
                "needs_action": True,
                "action": "network_block_internet",
            }

        unblock_internet_match = self.UNBLOCK_INTERNET_RE.match(content)
        if unblock_internet_match:
            alias = (unblock_internet_match.group(1) or "").strip()
            if alias:
                return {
                    "intent": "network_unblock_machine_internet",
                    "alias": alias,
                    "response": f"Desbloqueando internet da maquina {alias}.",
                    "needs_action": True,
                    "action": "network_unblock_machine_internet",
                }
            return {
                "intent": "network_unblock_internet",
                "response": "Desbloqueando internet.",
                "needs_action": True,
                "action": "network_unblock_internet",
            }

        block_machine_match = self.BLOCK_MACHINE_RE.match(content)
        if block_machine_match:
            alias = block_machine_match.group(1).strip()
            return {
                "intent": "network_block_machine_isolate",
                "alias": alias,
                "response": f"Isolando maquina {alias} da rede.",
                "needs_action": True,
                "action": "network_block_machine_isolate",
            }

        unblock_machine_match = self.UNBLOCK_MACHINE_RE.match(content)
        if unblock_machine_match:
            alias = unblock_machine_match.group(1).strip()
            return {
                "intent": "network_unblock_machine",
                "alias": alias,
                "response": f"Liberando maquina {alias}.",
                "needs_action": True,
                "action": "network_unblock_machine",
            }

        if self.LIST_BLOCKS_RE.match(content):
            return {
                "intent": "network_list_blocks",
                "response": "Listando bloqueios de rede.",
                "needs_action": True,
                "action": "network_list_blocks",
            }

        remember_match = self.REMEMBER_RE.match(content)
        if remember_match:
            return {
                "intent": "remember",
                "memory": remember_match.group(1).strip(),
                "response": "Posso guardar isso na memoria.",
                "needs_action": True,
            }

        recall_match = self.RECALL_RE.match(content)
        if recall_match:
            return {
                "intent": "recall",
                "query": recall_match.group(1).strip(),
                "limit": 2,
                "response": "Vou consultar minha memoria sobre isso.",
                "needs_action": True,
            }

        home_command = self._match_home_command(content)
        if home_command:
            return home_command

        if any(token in content for token in self.STATUS_TOKENS):
            return {
                "intent": "status",
                "response": "Vou montar um resumo do status atual.",
                "needs_action": True,
                "action": "status",
            }

        if any(token in content for token in self.GREETING_TOKENS):
            return {
                "intent": "greeting",
                "response": "Ola! Estou pronto para proteger sua casa e controlar seus dispositivos.",
                "needs_action": False,
            }

        return None

    def _match_home_command(self, content):
        device_aliases = {
            "luz": ["luz", "lampada", "iluminacao", "iluminacao da casa"],
            "tomada": ["tomada", "plug", "energia da tomada"],
            "fechadura": ["fechadura", "porta", "porta da casa", "tranca"],
        }
        action_aliases = {
            "on": ["ligar", "acender", "ativar"],
            "off": ["desligar", "apagar", "desativar"],
            "lock": ["trancar", "fechar", "bloquear"],
            "unlock": ["destrancar", "abrir", "liberar"],
        }
        responses = {
            ("luz", "on"): "Ligando a luz da casa.",
            ("luz", "off"): "Desligando a luz da casa.",
            ("tomada", "on"): "Ligando a tomada da casa.",
            ("tomada", "off"): "Desligando a tomada da casa.",
            ("fechadura", "lock"): "Trancando a fechadura da casa.",
            ("fechadura", "unlock"): "Destrancando a fechadura da casa.",
        }

        for device, aliases in device_aliases.items():
            if not any(alias in content for alias in aliases):
                continue
            candidate_actions = ("unlock", "lock") if device == "fechadura" else ("off", "on")
            for action in candidate_actions:
                if any(alias in content for alias in action_aliases[action]):
                    return {
                        "intent": "home_control",
                        "device": device,
                        "action": action,
                        "response": responses[(device, action)],
                        "needs_action": True,
                    }

        custom_devices = self._load_custom_devices()
        for device, config in custom_devices.items():
            if device not in content:
                continue

            open_action = str(config.get("open_action", "")).strip().lower()
            close_action = str(config.get("close_action", "")).strip().lower()
            matched_action = None
            if open_action and open_action in content:
                matched_action = open_action
            elif close_action and close_action in content:
                matched_action = close_action
            if not matched_action:
                continue

            return {
                "intent": "home_control",
                "device": device,
                "action": matched_action,
                "response": f"Executando '{matched_action}' no dispositivo {device}.",
                "needs_action": True,
            }
        return None

    def looks_like_question(self, content):
        normalized = self.normalize(content)
        if not normalized:
            return False
        if "?" in normalized:
            return True
        return normalized.strip().startswith(self.QUESTION_STARTERS)

    @staticmethod
    def normalize(text: str):
        normalized = unicodedata.normalize("NFD", str(text).lower())
        return "".join(char for char in normalized if unicodedata.category(char) != "Mn")

    def _match_custom_device_registration(self, content):
        for pattern in self.CUSTOM_DEVICE_PATTERNS:
            match = pattern.match(content)
            if not match:
                continue

            device = self.normalize(match.group(1)).strip()
            open_action = self.normalize(match.group(2)).strip()
            close_action = self.normalize(match.group(3)).strip()
            if not device or not open_action or not close_action:
                return None
            if open_action == close_action:
                return {
                    "intent": "question_answer",
                    "response": "As duas acoes do dispositivo precisam ser diferentes.",
                    "needs_action": False,
                }

            return {
                "intent": "home_register_device_commands",
                "device": device,
                "open_action": open_action,
                "close_action": close_action,
                "response": (
                    f"Comando de administrador recebido. Vou cadastrar '{device}' com "
                    f"'{open_action}' e '{close_action}'."
                ),
                "needs_action": True,
                "action": "home_register_device_commands",
            }
        return None

    def _match_plugin_command(self, content_raw):
        if self.plugin_registry is None:
            return None
        matched = self.plugin_registry.match(content_raw)
        if not isinstance(matched, dict):
            return None
        matched.setdefault("needs_action", True)
        matched.setdefault("response", "Comando de plugin identificado.")
        return matched

    def _parse_scene_steps(self, raw_steps):
        chunks = re.split(r"[,;|]+", str(raw_steps or ""))
        steps = []
        for chunk in chunks:
            piece = str(chunk).strip()
            if not piece or ":" not in piece:
                continue
            device_raw, action_raw = piece.split(":", 1)
            device = self.normalize(device_raw).strip()
            action = self.normalize(action_raw).strip()
            if not device or not action:
                continue
            steps.append({"device": device, "action": action})
        return steps

    @staticmethod
    def _duration_to_seconds(amount, unit):
        if amount is None:
            return 0
        try:
            value = int(amount)
        except Exception:
            return 0
        if value <= 0:
            return 0
        normalized = str(unit or "s").strip().lower()
        if normalized in {"h", "hora", "horas"}:
            return value * 3600
        if normalized in {"min", "mins", "minuto", "minutos"}:
            return value * 60
        return value

    def _normalize_identifier(self, value):
        normalized = self.normalize(value).strip()
        normalized = re.sub(r"\s+", "_", normalized)
        return normalized.strip("_")

    def _load_custom_devices(self):
        try:
            if not self.custom_commands_path.exists():
                self._custom_devices_cache = {}
                self._custom_devices_mtime_ns = None
                return {}

            stat = self.custom_commands_path.stat()
            mtime_ns = int(stat.st_mtime_ns)
            if self._custom_devices_mtime_ns == mtime_ns:
                return dict(self._custom_devices_cache)

            with self.custom_commands_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle) or {}
            devices = payload.get("devices", {}) if isinstance(payload, dict) else {}
            normalized_devices = {}
            for raw_device, raw_cfg in devices.items():
                device = self.normalize(raw_device).strip()
                if not device or not isinstance(raw_cfg, dict):
                    continue
                open_action = self.normalize(str(raw_cfg.get("open_action", ""))).strip()
                close_action = self.normalize(str(raw_cfg.get("close_action", ""))).strip()
                if not open_action or not close_action or open_action == close_action:
                    continue
                normalized_devices[device] = {
                    "open_action": open_action,
                    "close_action": close_action,
                }

            self._custom_devices_cache = normalized_devices
            self._custom_devices_mtime_ns = mtime_ns
            return dict(normalized_devices)
        except Exception:
            self._custom_devices_cache = {}
            self._custom_devices_mtime_ns = None
            return {}
