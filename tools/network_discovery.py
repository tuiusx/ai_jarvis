import re
import subprocess
from typing import List, Dict

from tools.base import Tool


class NetworkDiscoveryTool(Tool):
    name = "network_scan"
    description = "Descobre dispositivos visiveis na rede local usando tabela ARP."

    _ARP_LINE_RE = re.compile(r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F\-]{17})\s+(\w+)\s*$")

    def run(self, limit: int = 50, **kwargs):
        try:
            output = subprocess.check_output(["arp", "-a"], text=True, encoding="utf-8", errors="ignore")
        except Exception as exc:
            return {
                "event": "network_scan",
                "devices": [],
                "count": 0,
                "message": f"Nao foi possivel ler a rede local: {exc}",
                "error": str(exc),
            }

        devices = self._parse_arp(output)
        devices = [d for d in devices if d["mac"] != "ff-ff-ff-ff-ff-ff"]
        if isinstance(limit, int) and limit > 0:
            devices = devices[:limit]

        if devices:
            preview = ", ".join(f"{d['ip']} ({d['mac']})" for d in devices[:5])
            message = f"Encontrei {len(devices)} dispositivo(s) na rede: {preview}"
        else:
            message = "Nao encontrei dispositivos ativos na tabela ARP agora."

        return {
            "event": "network_scan",
            "devices": devices,
            "count": len(devices),
            "message": message,
        }

    @classmethod
    def _parse_arp(cls, output: str) -> List[Dict[str, str]]:
        devices = []
        current_interface = ""

        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if line.lower().startswith("interface:"):
                current_interface = line
                continue

            match = cls._ARP_LINE_RE.match(line)
            if not match:
                continue

            ip, mac, entry_type = match.groups()
            devices.append(
                {
                    "ip": ip,
                    "mac": mac.lower(),
                    "type": entry_type.lower(),
                    "interface": current_interface,
                }
            )

        return devices
