from core.settings import load_settings
from core.dashboard import build_dashboard_server


def main():
    settings = load_settings()
    security_cfg = settings.get("security", {})
    dashboard_cfg = settings.get("dashboard", {})
    app_mode = settings.get("app", {}).get("mode", "dev")

    host = dashboard_cfg.get("host", "127.0.0.1")
    port = int(dashboard_cfg.get("port", 8787))
    max_events = int(dashboard_cfg.get("max_events", 200))
    audit_log = security_cfg.get("audit_log_file", "state/audit.log.jsonl")

    server = build_dashboard_server(
        host=host,
        port=port,
        audit_log_path=audit_log,
        app_mode=app_mode,
        max_events=max_events,
    )
    print(f"Dashboard online at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
