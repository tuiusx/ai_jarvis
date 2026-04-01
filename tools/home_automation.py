import json
import ssl
import urllib.error
import urllib.request

from tools.base import Tool


class HomeAutomationTool(Tool):
    name = "home_control"
    description = "Controla dispositivos de casa inteligente (luz, tomada e fechadura)."

    def __init__(self, home_assistant=None):
        self.home_assistant = home_assistant or {}
        self.state = {
            "luz": "off",
            "tomada": "off",
            "fechadura": "locked",
        }

    def run(self, device="luz", action="on", **kwargs):
        device = device.lower()
        action = action.lower()

        if device not in self.state:
            return {"error": f"Dispositivo '{device}' nao gerenciado."}

        allowed_actions = {
            "luz": {"on", "off", "toggle"},
            "tomada": {"on", "off", "toggle"},
            "fechadura": {"lock", "unlock", "toggle"},
        }
        if action not in allowed_actions[device]:
            return {"error": f"Acao '{action}' nao suportada para {device}."}

        ha_result = self._try_home_assistant(device=device, action=action)
        if "error" in ha_result:
            return ha_result

        if ha_result.get("used"):
            new_status = self._status_from_ha(ha_result.get("state"), device, action)
            if new_status:
                self.state[device] = new_status
            elif action == "toggle":
                self.state[device] = self._toggle_device(device)
            elif device == "fechadura":
                self.state[device] = "locked" if action == "lock" else "unlocked"
            else:
                self.state[device] = action
        else:
            if action == "toggle":
                self.state[device] = self._toggle_device(device)
            elif device == "fechadura":
                self.state[device] = "locked" if action == "lock" else "unlocked"
            else:
                self.state[device] = action

        return {
            "event": "home_control",
            "device": device,
            "action": action,
            "status": self.state[device],
            "message": self._build_message(device),
            "source": "home_assistant" if ha_result.get("used") else "simulated",
        }

    def _toggle_device(self, device):
        if device == "fechadura":
            return "unlocked" if self.state[device] == "locked" else "locked"
        return "off" if self.state[device] == "on" else "on"

    def _build_message(self, device):
        status = self.state[device]
        if device == "luz":
            return "A luz da casa esta ligada." if status == "on" else "A luz da casa esta desligada."
        if device == "tomada":
            return "A tomada da casa esta ligada." if status == "on" else "A tomada da casa esta desligada."
        if device == "fechadura":
            return "A fechadura da casa esta trancada." if status == "locked" else "A fechadura da casa esta destrancada."
        return f"{device.capitalize()} atualizada."

    def _try_home_assistant(self, device, action):
        base_url = (self.home_assistant.get("base_url") or "").strip().rstrip("/")
        token = (self.home_assistant.get("token") or "").strip()
        devices = self.home_assistant.get("devices") or {}
        entity_id = (devices.get(device) or "").strip()

        # Fallback para modo simulado quando HA nao estiver configurado.
        if not base_url or not token or not entity_id:
            return {"used": False}

        domain, service = self._service_for(device=device, action=action)
        if domain is None or service is None:
            return {"error": f"Acao '{action}' nao suportada para {device} no Home Assistant."}

        verify_ssl = bool(self.home_assistant.get("verify_ssl", True))
        ssl_context = None if verify_ssl else ssl._create_unverified_context()

        try:
            self._ha_post(
                url=f"{base_url}/api/services/{domain}/{service}",
                token=token,
                payload={"entity_id": entity_id},
                ssl_context=ssl_context,
            )
            state = self._ha_get_state(base_url=base_url, token=token, entity_id=entity_id, ssl_context=ssl_context)
            return {"used": True, "state": state}
        except urllib.error.HTTPError as exc:
            return {"error": f"Falha no Home Assistant ({exc.code}) ao controlar {device}."}
        except urllib.error.URLError as exc:
            return {"error": f"Falha de conexao com Home Assistant: {exc.reason}"}
        except Exception as exc:
            return {"error": f"Erro ao controlar Home Assistant: {exc}"}

    def _service_for(self, device, action):
        if device == "fechadura":
            if action == "lock":
                return ("lock", "lock")
            if action == "unlock":
                return ("lock", "unlock")
            if action == "toggle":
                # Para lock, usa lock.toggle quando disponivel.
                return ("lock", "toggle")
            return (None, None)

        domain = "light" if device == "luz" else "switch"
        if action == "on":
            return (domain, "turn_on")
        if action == "off":
            return (domain, "turn_off")
        if action == "toggle":
            return (domain, "toggle")
        return (None, None)

    @staticmethod
    def _ha_post(url, token, payload, ssl_context=None):
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, context=ssl_context, timeout=8):
            return

    @staticmethod
    def _ha_get_state(base_url, token, entity_id, ssl_context=None):
        request = urllib.request.Request(
            url=f"{base_url}/api/states/{entity_id}",
            method="GET",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(request, context=ssl_context, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("state")

    @staticmethod
    def _status_from_ha(state, device, action):
        if not state:
            return None

        normalized = str(state).lower().strip()
        if device == "fechadura":
            if normalized in {"locked", "locking"}:
                return "locked"
            if normalized in {"unlocked", "unlocking"}:
                return "unlocked"
            if action == "lock":
                return "locked"
            if action == "unlock":
                return "unlocked"
            return None

        if normalized in {"on"}:
            return "on"
        if normalized in {"off"}:
            return "off"
        if action in {"on", "off"}:
            return action
        return None
