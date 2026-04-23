from tools.base import Tool


class HomeAutomationTool(Tool):
    name = "home_control"
    description = "Controla dispositivos de casa inteligente (luz, tomada e fechadura)."

    def __init__(self, dry_run: bool = False):
        # Estado interno simulado dos dispositivos da casa.
        self.dry_run = bool(dry_run)
        self.state = {
            "luz": "off",
            "tomada": "off",
            "fechadura": "locked",
        }

    def run(self, device="luz", action="on", dry_run=None, **kwargs):
        device = device.lower()
        action = action.lower()
        dry_run_mode = self.dry_run if dry_run is None else bool(dry_run)

        if device not in self.state:
            return {"error": f"Dispositivo '{device}' nao gerenciado."}

        allowed_actions = {
            "luz": {"on", "off", "toggle"},
            "tomada": {"on", "off", "toggle"},
            "fechadura": {"lock", "unlock", "toggle"},
        }

        if action not in allowed_actions[device]:
            return {"error": f"Acao '{action}' nao suportada para {device}."}

        current = self.state[device]
        next_status = current
        if action == "toggle":
            next_status = self._toggle_device(device)
        elif device == "fechadura":
            next_status = "locked" if action == "lock" else "unlocked"
        else:
            next_status = action

        if not dry_run_mode:
            self.state[device] = next_status

        return {
            "event": "home_control",
            "device": device,
            "action": action,
            "dry_run": dry_run_mode,
            "status": next_status,
            "message": self._build_message(device=device, status=next_status, dry_run=dry_run_mode),
        }

    def _toggle_device(self, device):
        if device == "fechadura":
            return "unlocked" if self.state[device] == "locked" else "locked"
        return "off" if self.state[device] == "on" else "on"

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

        return prefix + f"{device.capitalize()} atualizada."
