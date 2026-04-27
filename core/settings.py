import os
from copy import deepcopy
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


DEFAULT_SETTINGS = {
    "app": {
        "mode": "dev",
    },
    "openai": {
        "api_key": "",
        "model": "gpt-3.5-turbo",
    },
    "voice": {
        "wake_word": "jarvis",
        "language": "pt-BR",
        "timeout": 8,
    },
    "memory": {
        "short_term_limit": 10,
        "long_term_file": "state/memory.json",
        "long_term_limit": 100,
        "encryption_key_env": "JARVIS_MEMORY_KEY",
        "semantic": {
            "enabled": True,
            "model_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "index_path": "state/memory_semantic.faiss",
            "db_path": "state/memory_semantic.db",
            "top_k": 8,
            "response_k": 3,
            "batch_size": 256,
            "mask_sensitive": True,
            "score_threshold": 0.45,
            "hnsw_m": 32,
            "hnsw_ef_search": 128,
        },
    },
    "camera": {
        "default_index": 0,
        "detection_duration": 5,
    },
    "recording": {
        "default_duration": 10,
        "output_dir": "recordings",
    },
    "home_automation": {
        "dry_run": False,
        "custom_devices_path": "state/home_custom_devices.json",
        "iot_webhook": {
            "enabled": False,
            "url": "",
            "timeout_seconds": 4,
        },
    },
    "security": {
        "enforce_env_secrets": False,
        "min_command_interval_seconds": 0.8,
        "audit_log_file": "state/audit.log.jsonl",
        "audit_max_bytes": 5_242_880,
        "audit_backup_count": 3,
        "access_control": {
            "enabled": False,
            "owner_name": "owner",
            "permission_ttl_seconds": 900,
            "min_confidence": 0.75,
            "camera_index": 0,
            "auto_reload_gallery_seconds": 30,
            "roles_file": "state/access_roles.json",
            "liveness_enabled": True,
            "liveness_min_movement_pixels": 4,
        },
        "network_verification": {
            "enabled": False,
            "mode": "block",
            "allowed_cidrs": [],
            "check_interval_seconds": 5,
        },
        "network_monitor": {
            "enabled": False,
            "backend": "scapy",
            "scope": "lan",
            "interface": "auto",
            "promiscuous": True,
            "bpf_filter": "",
            "write_pcap": True,
            "metadata_log_path": "state/network_traffic.jsonl",
            "pcap_dir": "state/network_captures",
            "rotate_max_mb": 128,
            "rotate_keep_files": 5,
            "auto_start": False,
        },
        "network_enforcement": {
            "enabled": False,
            "default_block_duration_seconds": 0,
            "machine_registry_path": "state/machine_registry.json",
            "state_path": "state/network_blocks.json",
            "provider_priority": ["openwrt", "local"],
            "openwrt": {
                "host": "",
                "port": 22,
                "username": "",
                "ssh_key_path": "",
                "lan_zone": "lan",
                "wan_zone": "wan",
                "apply_timeout_seconds": 12,
            },
        },
        "critical_confirmation": {
            "enabled": True,
            "ttl_seconds": 90,
            "pin_env": "JARVIS_ADMIN_PIN",
            "require_pin": True,
        },
    },
    "notifications": {
        "enabled": False,
        "channel": "console",
        "min_severity": "critical",
        "telegram_bot_token_env": "JARVIS_TELEGRAM_BOT_TOKEN",
        "telegram_chat_id_env": "JARVIS_TELEGRAM_CHAT_ID",
        "webhook_url": "",
        "webhook_token_env": "JARVIS_WEBHOOK_TOKEN",
    },
    "plugins": {
        "enabled": True,
        "directory": "state/plugins",
    },
    "automation": {
        "enabled": True,
        "state_path": "state/automation_hub.json",
        "scheduler_interval_seconds": 1.0,
        "auto_start_scheduler": True,
    },
    "backup": {
        "enabled": True,
        "output_dir": "state/exports",
        "password_env": "JARVIS_BACKUP_PASSWORD",
        "interval_minutes": 0,
        "periodic_tests": {
            "enabled": True,
            "interval_minutes": 0,
            "command": "python -m pytest -q",
            "timeout_seconds": 1200,
            "workdir": ".",
        },
    },
    "monitoring": {
        "system_resources": {
            "enabled": False,
            "auto_start": False,
            "interval_seconds": 10,
            "history_size": 180,
            "cpu_alert_percent": 90,
            "memory_alert_percent": 90,
            "alert_cooldown_seconds": 120,
        },
    },
    "retention": {
        "enabled": True,
        "auto_cleanup_on_start": True,
        "max_age_days": 30,
        "max_recordings": 200,
        "max_faces": 2000,
    },
    "dashboard": {
        "enabled": True,
        "host": "127.0.0.1",
        "port": 8787,
        "max_events": 200,
    },
    "performance": {
        "enabled_metrics": True,
        "slow_command_threshold_ms": 700,
        "lazy_init_enabled": True,
        "tool_retry_attempts": 1,
        "tool_retry_backoff_seconds": 0.2,
    },
    "internet": {
        "search_timeout_seconds": 8,
    },
    "setup": {
        "first_run_enabled": True,
        "state_file": "state/first_run_setup.json",
        "face_base_dir": "faces",
        "capture_timeout_seconds": 20,
    },
}


def _deep_merge(base: dict, override: dict):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _parse_scalar(value: str):
    token = value.strip()
    if not token:
        return ""

    lowered = token.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None

    if (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
        return token[1:-1]

    try:
        if "." in token:
            return float(token)
        return int(token)
    except ValueError:
        return token


def _read_simple_yaml(path: Path):
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.split("#", 1)[0].rstrip()
            if not line.strip():
                continue

            indent = len(line) - len(line.lstrip(" "))
            content = line.strip()
            if ":" not in content:
                continue

            key, value = content.split(":", 1)
            key = key.strip()
            value = value.strip()

            while len(stack) > 1 and indent <= stack[-1][0]:
                stack.pop()

            parent = stack[-1][1]
            if value == "":
                node: dict = {}
                parent[key] = node
                stack.append((indent, node))
            else:
                parent[key] = _parse_scalar(value)

    return root


def _read_yaml(path: Path):
    if not path.exists():
        return {}

    if yaml is not None:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return data if isinstance(data, dict) else {}

    data = _read_simple_yaml(path)
    return data if isinstance(data, dict) else {}


def load_settings(root_dir: str | None = None):
    base_dir = Path(root_dir or ".")
    config_dir = base_dir / "config"
    merged = deepcopy(DEFAULT_SETTINGS)

    for candidate in ("settings.example.yaml", "settings.yaml", "settings.local.yaml"):
        _deep_merge(merged, _read_yaml(config_dir / candidate))

    env_mode = os.getenv("JARVIS_MODE")
    if env_mode:
        merged.setdefault("app", {})["mode"] = env_mode.strip().lower()

    env_model = os.getenv("OPENAI_MODEL")
    if env_model:
        merged.setdefault("openai", {})["model"] = env_model.strip()

    env_rate_limit = os.getenv("JARVIS_MIN_COMMAND_INTERVAL")
    if env_rate_limit:
        try:
            merged.setdefault("security", {})["min_command_interval_seconds"] = max(0.0, float(env_rate_limit))
        except ValueError:
            pass

    app_mode = str(merged.get("app", {}).get("mode", "dev")).lower()
    merged.setdefault("app", {})["mode"] = "prod" if app_mode == "prod" else "dev"
    return merged


def get_setting(settings: dict, path: str, default=None):
    cursor = settings
    for token in path.split("."):
        if not isinstance(cursor, dict) or token not in cursor:
            return default
        cursor = cursor[token]
    return cursor
