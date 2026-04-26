from core.app_factory import AppFactory
from core.dashboard import start_dashboard_in_background
from core.retention import RetentionManager
from core.settings import get_setting, load_settings
from interfaces.multimodal import MultiModalInterface


def main():
    settings = load_settings()
    app_mode = str(get_setting(settings, "app.mode", "dev"))
    rate_seconds = float(get_setting(settings, "security.min_command_interval_seconds", 0.8))
    wake_word = str(get_setting(settings, "voice.wake_word", "jarvis"))
    should_cleanup = bool(get_setting(settings, "retention.auto_cleanup_on_start", True))

    factory = AppFactory(settings=settings)
    interface = MultiModalInterface(wake_word=wake_word, min_command_interval=rate_seconds)
    context = factory.build(interface=interface, retention_summary={})
    audit = context.audit

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
        )
        print(f"Dashboard ativo em http://{dash_host}:{dash_port}")

    audit.log(
        "app.start",
        mode=app_mode,
        dry_run=context.dry_run,
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
        if context.network_monitor is not None:
            try:
                context.network_monitor.stop()
            except Exception:
                pass


if __name__ == "__main__":
    main()
