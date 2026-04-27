import time


class CommandPrecheckPipeline:
    def __init__(
        self,
        rate_limiter=None,
        access_controller=None,
        network_guard=None,
        audit_logger=None,
    ):
        self.rate_limiter = rate_limiter
        self.access_controller = access_controller
        self.network_guard = network_guard
        self.audit = audit_logger

    def evaluate(self, content: str, *, skip_access_network: bool = False):
        command_user = None
        messages = []
        warnings = []

        if self.rate_limiter is not None:
            allowed, wait_seconds = self.rate_limiter.allow()
            if not allowed:
                if self.audit:
                    self.audit.log("security.rate_limit_blocked", severity="warning", wait_seconds=wait_seconds)
                return {
                    "status": "deny",
                    "reason": "rate_limit",
                    "wait_seconds": wait_seconds,
                    "messages": [f"Comando ignorado para evitar spam. Aguarde {wait_seconds:.2f}s."],
                    "warnings": [],
                    "user": None,
                }

        if skip_access_network:
            return {
                "status": "allow",
                "reason": "ok",
                "messages": [],
                "warnings": [],
                "user": command_user,
            }

        if self.access_controller is not None:
            access = self.access_controller.authorize_command(content)
            command_user = access.get("user")
            access_message = access.get("message")
            if access_message:
                messages.append(access_message)
            if access.get("handled"):
                if self.audit:
                    self.audit.log(
                        "security.owner_permission_action",
                        severity="info",
                        user=command_user,
                        command=content,
                    )
                return {
                    "status": "deny",
                    "reason": "handled",
                    "messages": messages,
                    "warnings": warnings,
                    "user": command_user,
                    "handled": True,
                }
            if not access.get("allowed", False):
                if self.audit:
                    self.audit.log(
                        "security.access_denied",
                        severity="warning",
                        user=command_user,
                        command=content,
                        reason=access_message or "access_denied",
                    )
                return {
                    "status": "deny",
                    "reason": "access_denied",
                    "messages": messages,
                    "warnings": warnings,
                    "user": command_user,
                }

        if self.network_guard is not None:
            network_access = self.network_guard.authorize_command(content)
            network_message = network_access.get("message")
            if network_message:
                if network_access.get("warning"):
                    warnings.append(network_message)
                else:
                    messages.append(network_message)
            if not network_access.get("allowed", False):
                if self.audit:
                    self.audit.log(
                        "security.network_untrusted_blocked",
                        severity="warning",
                        user=command_user,
                        command=content,
                        reason=network_message or "network_untrusted",
                    )
                return {
                    "status": "deny",
                    "reason": "network_untrusted",
                    "messages": messages,
                    "warnings": warnings,
                    "user": command_user,
                }

        status = "warn" if warnings else "allow"
        return {
            "status": status,
            "reason": "ok",
            "messages": messages,
            "warnings": warnings,
            "user": command_user,
        }


class CommandFlowPipeline:
    EXIT_COMMANDS = {"sair", "exit", "quit"}

    def parse_input(self, data):
        if not data:
            return None
        if not isinstance(data, dict):
            data = {"mode": "text", "content": str(data), "confidence": 1.0}

        content = str(data.get("content", "")).strip()
        if not content:
            return None

        return {
            "type": str(data.get("mode", "unknown")),
            "content": content,
            "confidence": float(data.get("confidence", 1.0)),
            "timestamp": time.time(),
        }

    def is_exit_command(self, content: str):
        return str(content or "").strip().lower() in self.EXIT_COMMANDS
