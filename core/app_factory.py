import os
from dataclasses import dataclass

from core.access_control import AccessController
from core.agent import Agent
from core.automation_hub import AutomationHubService
from core.audit import AuditLogger
from core.backup_manager import BackupManagerService
from core.intent_router import IntentRouter
from core.maintenance_guard import MaintenanceGuardService
from core.machine_registry import MachineRegistry
from core.memory import LongTermMemory, ShortTermMemory
from core.network_enforcement import LocalFirewallProvider, NetworkEnforcementService, OpenWrtProvider
from core.network_policy import NetworkPolicyGuard
from core.notifications import CriticalNotifier
from core.planner import Planner
from core.plugin_registry import PluginRegistry
from core.rate_limit import CommandRateLimiter
from core.settings import get_setting, load_settings
from core.system_monitor import SystemMonitorService
from tools.automation_hub import AutomationHubTool
from tools.backup_manager import BackupManagerTool
from tools.home_automation import HomeAutomationTool
from tools.maintenance_guard import MaintenanceGuardTool
from tools.manager import ToolManager
from tools.network_discovery import NetworkDiscoveryTool
from tools.plugin_manager import PluginManagerTool
from tools.recorder import RecorderTool
from tools.surveillance_tool import SurveillanceTool
from tools.system_monitor import SystemMonitorTool
from tools.web_search import WebSearchTool


@dataclass
class AppContext:
    settings: dict
    app_mode: str
    dry_run: bool
    audit: AuditLogger
    agent: Agent
    tools: ToolManager
    memory: ShortTermMemory
    long_memory: LongTermMemory
    rate_limiter: CommandRateLimiter
    network_monitor: object | None
    network_enforcement: object | None
    plugin_registry: object | None
    automation_hub: object | None
    backup_manager: object | None
    system_monitor: object | None
    maintenance_guard: object | None


class AppFactory:
    def __init__(self, settings: dict | None = None):
        self.settings = settings or load_settings()
        self.lazy_init_enabled = bool(get_setting(self.settings, "performance.lazy_init_enabled", True))

    def build(self, interface=None, retention_summary=None, include_camera_tools=True):
        settings = self.settings
        app_mode = str(get_setting(settings, "app.mode", "dev"))
        dry_run = bool(get_setting(settings, "home_automation.dry_run", False))

        short_limit = int(get_setting(settings, "memory.short_term_limit", 10))
        long_path = str(get_setting(settings, "memory.long_term_file", "state/memory.json"))
        long_limit = int(get_setting(settings, "memory.long_term_limit", 100))
        key_env = str(get_setting(settings, "memory.encryption_key_env", "JARVIS_MEMORY_KEY"))
        semantic_cfg = dict(get_setting(settings, "memory.semantic", {}) or {})

        audit_path = str(get_setting(settings, "security.audit_log_file", "state/audit.log.jsonl"))
        audit_max_bytes = int(get_setting(settings, "security.audit_max_bytes", 5_242_880))
        audit_backup_count = int(get_setting(settings, "security.audit_backup_count", 3))
        rate_seconds = float(get_setting(settings, "security.min_command_interval_seconds", 0.8))
        performance_cfg = dict(get_setting(settings, "performance", {}) or {})

        from core.llm import LocalLLM

        custom_commands_path = str(get_setting(settings, "home_automation.custom_devices_path", "state/home_custom_devices.json"))
        plugins_cfg = dict(get_setting(settings, "plugins", {}) or {})
        plugin_registry = PluginRegistry(
            directory=str(plugins_cfg.get("directory", "state/plugins")),
            enabled=bool(plugins_cfg.get("enabled", True)),
        )
        router = IntentRouter(
            custom_commands_path=custom_commands_path,
            plugin_registry=plugin_registry,
        )
        llm = LocalLLM(settings=settings, router=router)
        memory = ShortTermMemory(limit=short_limit)
        long_memory = LongTermMemory(
            file_path=long_path,
            limit=long_limit,
            encryption_key_env=key_env,
            semantic_config=semantic_cfg,
        )
        planner = Planner()
        rate_limiter = CommandRateLimiter(min_interval_seconds=rate_seconds)

        notifier = CriticalNotifier(
            enabled=bool(get_setting(settings, "notifications.enabled", False)),
            channel=str(get_setting(settings, "notifications.channel", "console")),
            telegram_token_env=str(get_setting(settings, "notifications.telegram_bot_token_env", "JARVIS_TELEGRAM_BOT_TOKEN")),
            telegram_chat_id_env=str(get_setting(settings, "notifications.telegram_chat_id_env", "JARVIS_TELEGRAM_CHAT_ID")),
            min_severity=str(get_setting(settings, "notifications.min_severity", "critical")),
            webhook_url=str(get_setting(settings, "notifications.webhook_url", "")),
            webhook_token_env=str(get_setting(settings, "notifications.webhook_token_env", "JARVIS_WEBHOOK_TOKEN")),
        )
        audit = AuditLogger(
            path=audit_path,
            max_bytes=audit_max_bytes,
            backup_count=audit_backup_count,
            notify_callback=notifier.notify,
            notify_min_severity=str(get_setting(settings, "notifications.min_severity", "critical")),
        )

        access_controller = AccessController(
            enabled=bool(get_setting(settings, "security.access_control.enabled", False)),
            owner_name=str(get_setting(settings, "security.access_control.owner_name", "owner")),
            permission_ttl_seconds=int(get_setting(settings, "security.access_control.permission_ttl_seconds", 900)),
            min_confidence=float(get_setting(settings, "security.access_control.min_confidence", 0.75)),
            camera_index=int(get_setting(settings, "security.access_control.camera_index", get_setting(settings, "camera.default_index", 0))),
            auto_reload_gallery_seconds=int(get_setting(settings, "security.access_control.auto_reload_gallery_seconds", 30)),
            liveness_enabled=bool(get_setting(settings, "security.access_control.liveness_enabled", True)),
            liveness_min_movement_pixels=int(get_setting(settings, "security.access_control.liveness_min_movement_pixels", 4)),
            roles_file_path=str(get_setting(settings, "security.access_control.roles_file", "state/access_roles.json")),
        )
        network_guard_cfg = dict(get_setting(settings, "security.network_verification", {}) or {})
        network_guard = NetworkPolicyGuard(
            enabled=bool(network_guard_cfg.get("enabled", False)),
            mode=str(network_guard_cfg.get("mode", "block")),
            allowed_cidrs=list(network_guard_cfg.get("allowed_cidrs", []) or []),
            check_interval_seconds=int(network_guard_cfg.get("check_interval_seconds", 5)),
        )
        critical_confirmation_cfg = dict(get_setting(settings, "security.critical_confirmation", {}) or {})

        network_enforcement_cfg = dict(get_setting(settings, "security.network_enforcement", {}) or {})
        network_enforcement = self._build_network_enforcement(
            cfg=network_enforcement_cfg,
            audit=audit,
        )

        network_monitor_cfg = dict(get_setting(settings, "security.network_monitor", {}) or {})
        network_monitor = self._build_network_monitor(
            cfg=network_monitor_cfg,
            network_guard=network_guard,
            audit=audit,
        )

        tools = ToolManager()
        if include_camera_tools:
            from tools.camera import CameraTool

            tools.register(CameraTool())
        tools.register(RecorderTool(output_dir=str(get_setting(settings, "recording.output_dir", "recordings"))))
        iot_cfg = dict(get_setting(settings, "home_automation.iot_webhook", {}) or {})
        home_tool = HomeAutomationTool(
            dry_run=dry_run,
            custom_devices_path=custom_commands_path,
            iot_webhook_enabled=bool(iot_cfg.get("enabled", False)),
            iot_webhook_url=str(iot_cfg.get("url", "")),
            iot_webhook_timeout_seconds=int(iot_cfg.get("timeout_seconds", 4)),
        )
        tools.register(home_tool)

        automation_cfg = dict(get_setting(settings, "automation", {}) or {})
        automation_hub = None
        if not self.lazy_init_enabled or bool(automation_cfg.get("enabled", True)):
            automation_hub = AutomationHubService(
                home_tool=home_tool,
                state_path=str(automation_cfg.get("state_path", "state/automation_hub.json")),
                scheduler_interval_seconds=float(automation_cfg.get("scheduler_interval_seconds", 1.0)),
                auto_start=bool(automation_cfg.get("auto_start_scheduler", True)),
                audit_logger=audit,
            )
        tools.register(AutomationHubTool(service=automation_hub))

        backup_cfg = dict(get_setting(settings, "backup", {}) or {})
        backup_manager = None
        if not self.lazy_init_enabled or bool(backup_cfg.get("enabled", True)):
            periodic_tests_cfg = dict(backup_cfg.get("periodic_tests", {}) or {})
            backup_manager = BackupManagerService(
                long_memory=long_memory,
                output_dir=str(backup_cfg.get("output_dir", "state/exports")),
                password_env=str(backup_cfg.get("password_env", "JARVIS_BACKUP_PASSWORD")),
                interval_minutes=int(backup_cfg.get("interval_minutes", 0)),
                periodic_tests_enabled=bool(periodic_tests_cfg.get("enabled", False)),
                tests_interval_minutes=int(periodic_tests_cfg.get("interval_minutes", 0)),
                tests_command=str(periodic_tests_cfg.get("command", "python -m pytest -q")),
                tests_timeout_seconds=int(periodic_tests_cfg.get("timeout_seconds", 1200)),
                tests_workdir=str(periodic_tests_cfg.get("workdir", ".")),
                audit_logger=audit,
            )
        tools.register(BackupManagerTool(service=backup_manager))

        system_monitor_cfg = dict(get_setting(settings, "monitoring.system_resources", {}) or {})
        system_monitor = self._build_system_monitor(
            cfg=system_monitor_cfg,
            audit=audit,
        )
        tools.register(SystemMonitorTool(service=system_monitor))

        maintenance_cfg = dict(get_setting(settings, "maintenance", {}) or {})
        maintenance_guard = self._build_maintenance_guard(
            cfg=maintenance_cfg,
            backup_manager=backup_manager,
            system_monitor=system_monitor,
            critical_confirmation_cfg=critical_confirmation_cfg,
            audit=audit,
        )
        tools.register(MaintenanceGuardTool(service=maintenance_guard))

        tools.register(PluginManagerTool(registry=plugin_registry))
        tools.register(NetworkDiscoveryTool())
        tools.register(SurveillanceTool(callback=lambda evt: print(f"Evento de vigilancia: {evt}")))
        tools.register(WebSearchTool(timeout=int(get_setting(settings, "internet.search_timeout_seconds", 8))))

        from tools.network_enforcement import NetworkEnforcementTool
        from tools.network_monitor import NetworkMonitorTool

        tools.register(NetworkMonitorTool(service=network_monitor))
        tools.register(NetworkEnforcementTool(service=network_enforcement))

        agent = Agent(
            llm=llm,
            memory=memory,
            long_memory=long_memory,
            planner=planner,
            tools=tools,
            interface=interface,
            rate_limiter=rate_limiter,
            audit_logger=audit,
            app_mode=app_mode,
            retention_summary=retention_summary,
            access_controller=access_controller,
            network_guard=network_guard,
            performance_config=performance_cfg,
            critical_confirmation_enabled=bool(critical_confirmation_cfg.get("enabled", True)),
            critical_confirmation_ttl_seconds=int(critical_confirmation_cfg.get("ttl_seconds", 90)),
            critical_confirmation_pin_env=str(critical_confirmation_cfg.get("pin_env", "JARVIS_ADMIN_PIN")),
            critical_confirmation_require_pin=bool(critical_confirmation_cfg.get("require_pin", True)),
            tool_retry_attempts=int(performance_cfg.get("tool_retry_attempts", 1)),
            tool_retry_backoff_seconds=float(performance_cfg.get("tool_retry_backoff_seconds", 0.2)),
            system_monitor=system_monitor,
        )

        return AppContext(
            settings=settings,
            app_mode=app_mode,
            dry_run=dry_run,
            audit=audit,
            agent=agent,
            tools=tools,
            memory=memory,
            long_memory=long_memory,
            rate_limiter=rate_limiter,
            network_monitor=network_monitor,
            network_enforcement=network_enforcement,
            plugin_registry=plugin_registry,
            automation_hub=automation_hub,
            backup_manager=backup_manager,
            system_monitor=system_monitor,
            maintenance_guard=maintenance_guard,
        )

    def _build_network_enforcement(self, cfg, audit):
        enabled = bool(cfg.get("enabled", False))
        if self.lazy_init_enabled and not enabled:
            return None

        machine_registry = MachineRegistry(path=str(cfg.get("machine_registry_path", "state/machine_registry.json")))
        openwrt_cfg = dict(cfg.get("openwrt", {}) or {})
        openwrt_host = os.getenv("JARVIS_OPENWRT_HOST") or str(openwrt_cfg.get("host", ""))
        openwrt_user = os.getenv("JARVIS_OPENWRT_USERNAME") or str(openwrt_cfg.get("username", ""))
        openwrt_key = os.getenv("JARVIS_OPENWRT_SSH_KEY_PATH") or str(openwrt_cfg.get("ssh_key_path", ""))
        openwrt_provider = OpenWrtProvider(
            host=openwrt_host,
            port=int(openwrt_cfg.get("port", 22)),
            username=openwrt_user,
            ssh_key_path=openwrt_key,
            lan_zone=str(openwrt_cfg.get("lan_zone", "lan")),
            wan_zone=str(openwrt_cfg.get("wan_zone", "wan")),
            apply_timeout_seconds=int(openwrt_cfg.get("apply_timeout_seconds", 12)),
        )
        local_provider = LocalFirewallProvider()
        return NetworkEnforcementService(
            enabled=enabled,
            registry=machine_registry,
            providers={
                "openwrt": openwrt_provider,
                "local": local_provider,
            },
            provider_priority=list(cfg.get("provider_priority", ["openwrt", "local"]) or ["openwrt", "local"]),
            state_path=str(cfg.get("state_path", "state/network_blocks.json")),
            default_block_duration_seconds=int(cfg.get("default_block_duration_seconds", 0)),
            audit_logger=audit,
        )

    def _build_network_monitor(self, cfg, network_guard, audit):
        enabled = bool(cfg.get("enabled", False))
        auto_start = bool(cfg.get("auto_start", False))
        if self.lazy_init_enabled and not enabled and not auto_start:
            return None

        from core.network_monitor import NetworkMonitorService

        interface = str(cfg.get("interface", "auto")).strip()
        return NetworkMonitorService(
            enabled=enabled,
            interface=None if interface.lower() == "auto" else interface,
            promiscuous=bool(cfg.get("promiscuous", True)),
            bpf_filter=str(cfg.get("bpf_filter", "")),
            write_pcap=bool(cfg.get("write_pcap", True)),
            metadata_log_path=str(cfg.get("metadata_log_path", "state/network_traffic.jsonl")),
            pcap_dir=str(cfg.get("pcap_dir", "state/network_captures")),
            rotate_max_mb=int(cfg.get("rotate_max_mb", 128)),
            rotate_keep_files=int(cfg.get("rotate_keep_files", 5)),
            local_ips_provider=lambda: (network_guard.current_network_status().get("ips") or []),
            audit_logger=audit,
            auto_start=auto_start,
        )

    def _build_system_monitor(self, cfg, audit):
        enabled = bool(cfg.get("enabled", False))
        auto_start = bool(cfg.get("auto_start", False))
        if self.lazy_init_enabled and not enabled and not auto_start:
            return None

        return SystemMonitorService(
            enabled=enabled,
            interval_seconds=int(cfg.get("interval_seconds", 10)),
            history_size=int(cfg.get("history_size", 180)),
            cpu_alert_percent=float(cfg.get("cpu_alert_percent", 90)),
            memory_alert_percent=float(cfg.get("memory_alert_percent", 90)),
            alert_cooldown_seconds=int(cfg.get("alert_cooldown_seconds", 120)),
            auto_start=auto_start,
            audit_logger=audit,
        )

    def _build_maintenance_guard(self, cfg, backup_manager, system_monitor, critical_confirmation_cfg, audit):
        enabled = bool(cfg.get("enabled", True))
        auto_start = bool(cfg.get("auto_start", True))
        if self.lazy_init_enabled and not enabled and not auto_start:
            return None

        admin_pin_env = str(cfg.get("admin_pin_env") or critical_confirmation_cfg.get("pin_env", "JARVIS_ADMIN_PIN"))
        return MaintenanceGuardService(
            enabled=enabled,
            auto_start=auto_start,
            check_interval_seconds=int(cfg.get("check_interval_seconds", 300)),
            auto_repair=bool(cfg.get("auto_repair", True)),
            max_backup_age_minutes=int(cfg.get("max_backup_age_minutes", 1440)),
            max_tests_age_minutes=int(cfg.get("max_tests_age_minutes", 720)),
            admin_pin_env=admin_pin_env,
            backup_manager=backup_manager,
            system_monitor=system_monitor,
            audit_logger=audit,
        )
