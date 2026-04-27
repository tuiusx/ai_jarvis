import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib import request

from tools.base import Tool


class HomeAutomationTool(Tool):
    name = "home_control"
    description = "Controla dispositivos de casa inteligente (luz, tomada e fechadura)."

    BUILTIN_ACTIONS = {
        "luz": {"on", "off", "toggle"},
        "tomada": {"on", "off", "toggle"},
        "fechadura": {"lock", "unlock", "toggle"},
    }

    BUILTIN_DEFAULT_STATE = {
        "luz": "off",
        "tomada": "off",
        "fechadura": "locked",
    }

    def __init__(
        self,
        dry_run: bool = False,
        custom_devices_path: str = "state/home_custom_devices.json",
        iot_webhook_enabled: bool = False,
        iot_webhook_url: str = "",
        iot_webhook_timeout_seconds: int = 4,
        webhook_sender=None,
    ):
        self.dry_run = bool(dry_run)
        self.custom_devices_path = Path(custom_devices_path)
        self.iot_webhook_enabled = bool(iot_webhook_enabled)
        self.iot_webhook_url = str(iot_webhook_url or "").strip()
        self.iot_webhook_timeout_seconds = max(2, int(iot_webhook_timeout_seconds))
        self.webhook_sender = webhook_sender or self._default_webhook_sender
        self.custom_devices = {}
        self.state = dict(self.BUILTIN_DEFAULT_STATE)
        self._load_custom_devices()

    def run(self, device="luz", action="on", dry_run=None, **kwargs):
        device = self._normalize_phrase(device)
        action = self._normalize_phrase(action)
        dry_run_mode = self.dry_run if dry_run is None else bool(dry_run)

        if action == "register_device":
            return self._register_device(
                device=device or kwargs.get("device", ""),
                open_action=kwargs.get("open_action", ""),
                close_action=kwargs.get("close_action", ""),
            )

        if not device:
            return {"error": "Informe um dispositivo para executar o comando."}

        allowed_actions = self._allowed_actions(device)
        if allowed_actions is None:
            return {"error": f"Dispositivo '{device}' nao gerenciado."}

        if action not in allowed_actions:
            return {"error": f"Acao '{action}' nao suportada para {device}."}

        current = self.state.get(device, self._default_status_for(device))
        next_status = self._next_status(device=device, action=action, current=current)

        if not dry_run_mode:
            self.state[device] = next_status
            if device in self.custom_devices:
                self._save_custom_devices()

        iot_result = None
        if not dry_run_mode:
            iot_result = self._dispatch_iot_event(device=device, action=action, status=next_status)

        payload = {
            "event": "home_control",
            "device": device,
            "action": action,
            "dry_run": dry_run_mode,
            "status": next_status,
            "message": self._build_message(device=device, status=next_status, dry_run=dry_run_mode),
        }
        if iot_result is not None:
            payload["iot"] = iot_result
        return payload

    def _next_status(self, device, action, current):
        if action == "toggle":
            return self._toggle_device(device=device, current=current)

        if device == "fechadura":
            return "locked" if action == "lock" else "unlocked"

        if device in {"luz", "tomada"}:
            return action

        config = self.custom_devices.get(device)
        if config is None:
            return current
        if action == config.get("open_action"):
            return config.get("open_status", "ativo")
        return config.get("close_status", "inativo")

    def _toggle_device(self, device, current):
        if device == "fechadura":
            return "unlocked" if current == "locked" else "locked"

        if device in {"luz", "tomada"}:
            return "off" if current == "on" else "on"

        config = self.custom_devices.get(device)
        if config is None:
            return current
        open_status = config.get("open_status", "ativo")
        close_status = config.get("close_status", "inativo")
        return close_status if current == open_status else open_status

    def _allowed_actions(self, device):
        if device in self.BUILTIN_ACTIONS:
            return set(self.BUILTIN_ACTIONS[device])

        config = self.custom_devices.get(device)
        if config is None:
            return None

        actions = {
            str(config.get("open_action", "")).strip(),
            str(config.get("close_action", "")).strip(),
            "toggle",
        }
        return {item for item in actions if item}

    def _default_status_for(self, device):
        if device in self.BUILTIN_DEFAULT_STATE:
            return self.BUILTIN_DEFAULT_STATE[device]

        config = self.custom_devices.get(device)
        if config is not None:
            return str(config.get("close_status", "inativo"))
        return "inativo"

    def _register_device(self, device, open_action, close_action):
        device = self._normalize_phrase(device)
        open_action = self._normalize_phrase(open_action)
        close_action = self._normalize_phrase(close_action)

        if not device or not open_action or not close_action:
            return {"error": "Informe dispositivo e duas acoes validas para cadastro."}

        if open_action == close_action:
            return {"error": "As duas acoes precisam ser diferentes para o dispositivo."}

        if device in self.BUILTIN_ACTIONS:
            return {"error": f"O dispositivo '{device}' ja e nativo do JARVIS e nao pode ser sobrescrito."}

        config = {
            "open_action": open_action,
            "close_action": close_action,
            "open_status": self._verb_to_status(open_action),
            "close_status": self._verb_to_status(close_action),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.custom_devices[device] = config
        if device not in self.state:
            self.state[device] = config["close_status"]

        self._save_custom_devices()
        return {
            "event": "home_control_register",
            "device": device,
            "open_action": open_action,
            "close_action": close_action,
            "message": (
                f"Comandos cadastrados para {device}: '{open_action}' e '{close_action}'. "
                f"Agora voce pode controlar esse dispositivo por voz ou texto."
            ),
        }

    def _build_message(self, device, status, dry_run=False):
        prefix = "[SIMULACAO] " if dry_run else ""

        if device == "luz":
            return prefix + ("A luz da casa esta ligada." if status == "on" else "A luz da casa esta desligada.")

        if device == "tomada":
            return prefix + ("A tomada da casa esta ligada." if status == "on" else "A tomada da casa esta desligada.")

        if device == "fechadura":
            return prefix + (
                "A fechadura da casa esta trancada." if status == "locked" else "A fechadura da casa esta destrancada."
            )

        device_name = self._display_name(device)
        return prefix + f"A {device_name} esta {status}."

    def _load_custom_devices(self):
        if not self.custom_devices_path.exists():
            return

        try:
            with self.custom_devices_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle) or {}
            devices = payload.get("devices", {}) if isinstance(payload, dict) else {}
            saved_state = payload.get("state", {}) if isinstance(payload, dict) else {}
            if not isinstance(devices, dict):
                return

            for raw_name, raw_config in devices.items():
                device = self._normalize_phrase(raw_name)
                if not device or not isinstance(raw_config, dict):
                    continue
                open_action = self._normalize_phrase(raw_config.get("open_action", ""))
                close_action = self._normalize_phrase(raw_config.get("close_action", ""))
                if not open_action or not close_action or open_action == close_action:
                    continue

                config = {
                    "open_action": open_action,
                    "close_action": close_action,
                    "open_status": self._normalize_phrase(raw_config.get("open_status", "")) or self._verb_to_status(open_action),
                    "close_status": self._normalize_phrase(raw_config.get("close_status", "")) or self._verb_to_status(close_action),
                    "updated_at": str(raw_config.get("updated_at", "")),
                }
                self.custom_devices[device] = config

                custom_status = self._normalize_phrase(saved_state.get(device, "")) if isinstance(saved_state, dict) else ""
                self.state[device] = custom_status or config["close_status"]
        except Exception:
            self.custom_devices = {}

    def _save_custom_devices(self):
        self.custom_devices_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "devices": self.custom_devices,
            "state": {device: self.state.get(device, config.get("close_status", "inativo")) for device, config in self.custom_devices.items()},
        }
        with self.custom_devices_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _dispatch_iot_event(self, device, action, status):
        if not self.iot_webhook_enabled or not self.iot_webhook_url:
            return None
        payload = {
            "device": str(device),
            "action": str(action),
            "status": str(status),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.webhook_sender(url=self.iot_webhook_url, payload=payload, timeout=self.iot_webhook_timeout_seconds)
            return {"sent": True, "url": self.iot_webhook_url}
        except Exception as exc:
            return {"sent": False, "url": self.iot_webhook_url, "error": str(exc)}

    @staticmethod
    def _default_webhook_sender(url, payload, timeout):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(str(url), data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        with request.urlopen(req, timeout=timeout):  # nosec B310
            return True

    @staticmethod
    def _normalize_phrase(value):
        normalized = unicodedata.normalize("NFKD", str(value or "").lower())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"[^a-z0-9_\-\s]+", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @staticmethod
    def _verb_to_status(verb):
        mapping = {
            "abrir": "aberta",
            "fechar": "fechada",
            "ligar": "ligada",
            "desligar": "desligada",
            "trancar": "trancada",
            "destrancar": "destrancada",
            "ativar": "ativada",
            "desativar": "desativada",
        }
        verb = str(verb or "").strip().lower()
        if verb in mapping:
            return mapping[verb]
        if verb.endswith("ar") and len(verb) > 2:
            return verb[:-1] + "do"
        return "ajustada"

    @staticmethod
    def _display_name(device):
        return str(device or "").replace("_", " ").strip()
