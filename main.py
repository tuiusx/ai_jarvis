from core.app_factory import AppFactory
from core.dashboard import start_dashboard_in_background
from core.first_run_setup import ensure_first_run_setup
from core.retention import RetentionManager
from core.settings import get_setting, load_settings
from interfaces.multimodal import MultiModalInterface


def main():
    settings = load_settings()
    try:
        setup_summary = ensure_first_run_setup(settings=settings, root_dir=".")
    except Exception as exc:
        print(f"Falha na configuracao inicial do JARVIS: {exc}")
        print("Corrija o cadastro do administrador e tente novamente.")
        return

    if setup_summary.get("status") == "configured":
        print(f"Administrador configurado: {setup_summary.get('owner_name')}")
    elif setup_summary.get("status") == "deferred":
        print("Configuracao inicial pendente (terminal nao interativo).")

    app_mode = str(get_setting(settings, "app.mode", "dev"))
    rate_seconds = float(get_setting(settings, "security.min_command_interval_seconds", 0.8))
    wake_word = str(get_setting(settings, "voice.wake_word", "jarvis"))
    should_cleanup = bool(get_setting(settings, "retention.auto_cleanup_on_start", True))

    factory = AppFactory(settings=settings)
    interface = MultiModalInterface(wake_word=wake_word, min_command_interval=rate_seconds)
    context = factory.build(interface=interface, retention_summary={})
    audit = context.audit

    def admin_provider(action="diagnostics", payload=None):
        payload = payload or {}
        normalized = str(action or "").strip().lower()
        if normalized == "capabilities":
            return {
                "capabilities": [
                    "diagnostics",
                    "run_backup_now",
                    "run_tests_now",
                    "reload_plugins",
                    "list_blocks",
                    "automation_status",
                    "system_monitor_status",
                    "maintenance_status",
                    "maintenance_run_now",
                ]
            }

        if normalized == "diagnostics":
            data = {
                "mode": app_mode,
                "agent_status": context.agent.runtime_status(),
                "network_monitor": context.network_monitor.status() if context.network_monitor is not None else None,
                "network_enforcement": (
                    context.network_enforcement.execute(action="list_blocks")
                    if context.network_enforcement is not None
                    else None
                ),
                "plugins": context.plugin_registry.status() if context.plugin_registry is not None else None,
                "automation": context.automation_hub.status() if context.automation_hub is not None else None,
                "backup": context.backup_manager.status() if context.backup_manager is not None else None,
                "system_monitor": context.system_monitor.status() if getattr(context, "system_monitor", None) is not None else None,
                "maintenance": context.maintenance_guard.status() if getattr(context, "maintenance_guard", None) is not None else None,
            }
            return data

        if normalized == "run_backup_now":
            if context.backup_manager is None:
                return {"error": "backup_manager_not_configured"}
            return context.backup_manager.run_now(reason="dashboard")

        if normalized == "reload_plugins":
            if context.plugin_registry is None:
                return {"error": "plugin_registry_not_configured"}
            return context.plugin_registry.reload()

        if normalized == "run_tests_now":
            if context.backup_manager is None:
                return {"error": "backup_manager_not_configured"}
            return context.backup_manager.run_tests_now(reason="dashboard")

        if normalized == "list_blocks":
            if context.network_enforcement is None:
                return {"error": "network_enforcement_not_configured"}
            return context.network_enforcement.execute(action="list_blocks")

        if normalized == "automation_status":
            if context.automation_hub is None:
                return {"error": "automation_not_configured"}
            return context.automation_hub.status()

        if normalized == "system_monitor_status":
            if getattr(context, "system_monitor", None) is None:
                return {"error": "system_monitor_not_configured"}
            return context.system_monitor.status()

        if normalized == "maintenance_status":
            if getattr(context, "maintenance_guard", None) is None:
                return {"error": "maintenance_guard_not_configured"}
            return context.maintenance_guard.status()

        if normalized == "maintenance_run_now":
            if getattr(context, "maintenance_guard", None) is None:
                return {"error": "maintenance_guard_not_configured"}
            return context.maintenance_guard.check_now(reason="dashboard")

        return {"error": f"admin_action_not_supported:{normalized}"}

    if should_cleanup:
        retention_summary = RetentionManager(settings=settings, audit_logger=audit).cleanup()
        context.agent.last_cleanup = retention_summary

    if bool(get_setting(settings, "dashboard.enabled", True)):
        dash_host = str(get_setting(settings, "dashboard.host", "127.0.0.1"))
        dash_port = int(get_setting(settings, "dashboard.port", 8787))
        dash_max_events = int(get_setting(settings, "dashboard.max_events", 200))
        start_dashboard_in_background(
            host=dash_host,
            port=dash_port,
            audit_log_path=str(get_setting(settings, "security.audit_log_file", "state/audit.log.jsonl")),
            app_mode=app_mode,
            max_events=dash_max_events,
            metrics_provider=audit.metrics,
            admin_provider=admin_provider,
        )
        print(f"Dashboard ativo em http://{dash_host}:{dash_port}")

    audit.log(
        "app.start",
        mode=app_mode,
        dry_run=context.dry_run,
        first_run_setup=setup_summary.get("status"),
        access_control=bool(get_setting(settings, "security.access_control.enabled", False)),
        network_guard=bool(get_setting(settings, "security.network_verification.enabled", False)),
        network_monitor=bool(get_setting(settings, "security.network_monitor.enabled", False)),
        network_enforcement=bool(get_setting(settings, "security.network_enforcement.enabled", False)),
    )

    if context.network_monitor is not None and getattr(context.network_monitor, "auto_start", False):
        result = context.network_monitor.start()
        if "error" in result:
            audit.log("network.monitor_autostart_failed", severity="warning", error=result.get("error"))

    try:
        context.agent.run()
    finally:
        network_monitor = getattr(context, "network_monitor", None)
        if network_monitor is not None:
            try:
                network_monitor.stop()
            except Exception:
                pass
        automation_hub = getattr(context, "automation_hub", None)
        if automation_hub is not None:
            try:
                automation_hub.close()
            except Exception:
                pass
        backup_manager = getattr(context, "backup_manager", None)
        if backup_manager is not None:
            try:
                backup_manager.close()
            except Exception:
                pass
        system_monitor = getattr(context, "system_monitor", None)
        if system_monitor is not None:
            try:
                system_monitor.close()
            except Exception:
                pass
        maintenance_guard = getattr(context, "maintenance_guard", None)
        if maintenance_guard is not None:
            try:
                maintenance_guard.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
