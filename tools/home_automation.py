from tools.base import Tool


class HomeAutomationTool(Tool):
    name = "home_control"
    description = "Controla dispositivos de casa inteligente (luz, tomada e fechadura)."

    def __init__(self):
        # Estado interno simulado dos dispositivos da casa.
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
