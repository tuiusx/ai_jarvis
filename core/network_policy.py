import ipaddress
import socket
import time


class NetworkPolicyGuard:
    def __init__(
        self,
        enabled: bool = False,
        mode: str = "block",
        allowed_cidrs=None,
        check_interval_seconds: int = 5,
        ip_provider=None,
        time_provider=None,
    ):
        self.enabled = bool(enabled)
        self.mode = str(mode or "block").strip().lower()
        if self.mode not in {"block", "warn"}:
            self.mode = "block"
        self.allowed_cidrs = list(allowed_cidrs or [])
        self.check_interval_seconds = max(1, int(check_interval_seconds))
        self.ip_provider = ip_provider
        self.time_provider = time_provider or time.time

        self._cached_at = 0.0
        self._cached_result = {"trusted": True, "ips": [], "allowed_cidrs": self.allowed_cidrs}

    def authorize_command(self, command_text: str):
        if not self.enabled:
            return {"allowed": True, "warning": False}

        if self._is_safe_command(command_text):
            return {"allowed": True, "warning": False, "bypass": "safe_command"}

        result = self.current_network_status()
        if result.get("trusted", False):
            return {"allowed": True, "warning": False, "status": result}

        message = (
            "Rede nao confiavel para comandos sensiveis. "
            f"IPs locais: {', '.join(result.get('ips', [])) or 'indisponivel'}. "
            f"Permitidas: {', '.join(result.get('allowed_cidrs', [])) or 'nenhuma'}."
        )
        if self.mode == "warn":
            return {"allowed": True, "warning": True, "message": message, "status": result}

        return {"allowed": False, "warning": False, "message": message, "status": result}

    def current_network_status(self):
        now = self.time_provider()
        if now - self._cached_at < self.check_interval_seconds:
            return dict(self._cached_result)

        ips = self._local_ipv4_addresses()
        trusted = self._is_trusted_ip_set(ips)
        result = {
            "trusted": trusted,
            "ips": ips,
            "allowed_cidrs": list(self.allowed_cidrs),
        }
        self._cached_at = now
        self._cached_result = result
        return dict(result)

    def _is_trusted_ip_set(self, ips):
        networks = []
        for cidr in self.allowed_cidrs:
            try:
                networks.append(ipaddress.ip_network(str(cidr), strict=False))
            except ValueError:
                continue

        if not networks:
            return False

        for value in ips:
            try:
                address = ipaddress.ip_address(value)
            except ValueError:
                continue
            for network in networks:
                if address in network:
                    return True
        return False

    def _local_ipv4_addresses(self):
        if callable(self.ip_provider):
            ips = self.ip_provider() or []
            return sorted({str(ip).strip() for ip in ips if str(ip).strip()})

        found = set()

        try:
            hostname = socket.gethostname()
            for item in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
                ip = item[4][0]
                if ip and not ip.startswith("127."):
                    found.add(ip)
        except Exception:
            pass

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                found.add(ip)
        except Exception:
            pass
        finally:
            try:
                sock.close()
            except Exception:
                pass

        return sorted(found)

    @staticmethod
    def _is_safe_command(text):
        normalized = str(text or "").strip().lower()
        if not normalized:
            return True
        first_token = normalized.split()[0]
        return first_token in {"sair", "exit", "quit", "status", "ajuda", "help", "?"}
