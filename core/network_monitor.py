import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from scapy.all import AsyncSniffer  # type: ignore
    from scapy.layers.inet import ICMP, IP, TCP, UDP  # type: ignore
    from scapy.layers.inet6 import IPv6  # type: ignore
    from scapy.utils import PcapWriter  # type: ignore
except Exception:  # pragma: no cover - fallback sem dependencias
    AsyncSniffer = None
    IP = None
    IPv6 = None
    TCP = None
    UDP = None
    ICMP = None
    PcapWriter = None


class NetworkMonitorService:
    def __init__(
        self,
        enabled: bool = False,
        interface: str | None = None,
        promiscuous: bool = True,
        bpf_filter: str = "",
        write_pcap: bool = True,
        metadata_log_path: str = "state/network_traffic.jsonl",
        pcap_dir: str = "state/network_captures",
        rotate_max_mb: int = 128,
        rotate_keep_files: int = 5,
        local_ips_provider=None,
        audit_logger=None,
        auto_start: bool = False,
    ):
        self.enabled = bool(enabled)
        self.interface = (interface or "").strip() or None
        self.promiscuous = bool(promiscuous)
        self.bpf_filter = str(bpf_filter or "").strip()
        self.write_pcap = bool(write_pcap)
        self.metadata_log_path = Path(metadata_log_path)
        self.pcap_dir = Path(pcap_dir)
        self.rotate_max_bytes = max(1, int(rotate_max_mb)) * 1024 * 1024
        self.rotate_keep_files = max(1, int(rotate_keep_files))
        self.local_ips_provider = local_ips_provider
        self.audit = audit_logger
        self.auto_start = bool(auto_start)

        self._lock = threading.Lock()
        self._running = False
        self._sniffer = None
        self._pcap_writer = None
        self._pcap_path = self.pcap_dir / "traffic.pcap"
        self._started_at = None
        self._packets = 0
        self._bytes = 0
        self._protocol_counts = {}
        self._ips = set()

        self.metadata_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.pcap_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        if not self.enabled:
            message = "Monitor de rede esta desabilitado na configuracao."
            self._warn(message)
            return {"error": message}
        if AsyncSniffer is None:
            message = "Dependencia indisponivel: instale 'scapy' e Npcap para monitorar rede."
            self._warn(message)
            return {"error": message}
        if self._running:
            return {"message": "Rastreamento de rede ja esta ativo.", "status": self.status()}

        try:
            with self._lock:
                self._open_writers()
                self._sniffer = AsyncSniffer(
                    prn=self._handle_packet,
                    store=False,
                    iface=self.interface,
                    filter=self.bpf_filter or None,
                    promisc=self.promiscuous,
                )
                self._sniffer.start()
                self._running = True
                self._started_at = time.time()
        except Exception as exc:
            self._warn(f"Falha ao iniciar monitor de rede: {exc}")
            with self._lock:
                self._running = False
                self._sniffer = None
                self._close_writers()
            return {"error": f"Falha ao iniciar monitor de rede: {exc}"}

        return {"message": "Rastreamento de rede iniciado.", "status": self.status()}

    def stop(self):
        if not self._running:
            return {"message": "Rastreamento de rede ja estava parado.", "status": self.status()}

        with self._lock:
            sniffer = self._sniffer
            self._sniffer = None
            self._running = False

        if sniffer is not None:
            try:
                sniffer.stop()
            except Exception as exc:
                self._warn(f"Falha ao parar sniffer de rede: {exc}")

        with self._lock:
            self._close_writers()

        return {"message": "Rastreamento de rede interrompido.", "status": self.status()}

    def status(self):
        uptime = 0.0
        if self._started_at and self._running:
            uptime = round(time.time() - self._started_at, 2)
        return {
            "running": self._running,
            "uptime_seconds": uptime,
            "packets": self._packets,
            "bytes": self._bytes,
            "unique_ips": len(self._ips),
            "protocols": dict(self._protocol_counts),
            "metadata_log_path": str(self.metadata_log_path),
            "pcap_path": str(self._pcap_path),
        }

    def summary(self):
        status = self.status()
        top_protocols = ", ".join(
            f"{name}:{count}" for name, count in sorted(status["protocols"].items(), key=lambda item: item[1], reverse=True)
        )
        if not top_protocols:
            top_protocols = "sem trafego capturado ainda"
        return {
            "message": (
                f"Resumo de rede: packets={status['packets']}, bytes={status['bytes']}, "
                f"ips_unicos={status['unique_ips']}, protocolos={top_protocols}."
            ),
            "status": status,
        }

    def handle_packet_for_test(self, packet):
        self._handle_packet(packet)

    def _handle_packet(self, packet):
        metadata = self.packet_to_metadata(packet, local_ips=self._local_ips())
        if not metadata:
            return

        with self._lock:
            self._rotate_if_needed()
            self._write_metadata(metadata)
            self._write_pcap(packet)
            self._packets += 1
            self._bytes += int(metadata.get("length", 0))
            protocol = metadata.get("protocol", "UNKNOWN")
            self._protocol_counts[protocol] = self._protocol_counts.get(protocol, 0) + 1
            for ip_key in ("src_ip", "dst_ip"):
                value = str(metadata.get(ip_key, "")).strip()
                if value:
                    self._ips.add(value)

        if self.audit is not None:
            try:
                self.audit.log(
                    "network.monitor_packet",
                    severity="info",
                    src_ip=metadata.get("src_ip"),
                    dst_ip=metadata.get("dst_ip"),
                    protocol=metadata.get("protocol"),
                    length=metadata.get("length"),
                    direction=metadata.get("direction"),
                )
            except Exception:
                pass

    @staticmethod
    def packet_to_metadata(packet, local_ips=None):
        if packet is None:
            return None
        local_ips = set(local_ips or [])

        ip_layer = NetworkMonitorService._get_layer(packet, "ip")
        ipv6_layer = None if ip_layer is not None else NetworkMonitorService._get_layer(packet, "ipv6")
        if ip_layer is None and ipv6_layer is None:
            return None

        layer = ip_layer or ipv6_layer
        src_ip = str(getattr(layer, "src", "") or "")
        dst_ip = str(getattr(layer, "dst", "") or "")

        tcp = NetworkMonitorService._get_layer(packet, "tcp")
        udp = NetworkMonitorService._get_layer(packet, "udp")
        icmp = NetworkMonitorService._get_layer(packet, "icmp")

        protocol = "IP"
        src_port = None
        dst_port = None
        tcp_flags = None
        if tcp is not None:
            protocol = "TCP"
            src_port = int(getattr(tcp, "sport", 0) or 0)
            dst_port = int(getattr(tcp, "dport", 0) or 0)
            tcp_flags = str(getattr(tcp, "flags", "") or "")
        elif udp is not None:
            protocol = "UDP"
            src_port = int(getattr(udp, "sport", 0) or 0)
            dst_port = int(getattr(udp, "dport", 0) or 0)
        elif icmp is not None:
            protocol = "ICMP"

        direction = "unknown"
        if src_ip in local_ips and dst_ip in local_ips:
            direction = "local"
        elif src_ip in local_ips:
            direction = "outbound"
        elif dst_ip in local_ips:
            direction = "inbound"

        try:
            packet_len = int(len(packet))
        except Exception:
            packet_len = int(getattr(layer, "len", 0) or 0)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "interface": str(getattr(packet, "sniffed_on", "") or getattr(packet, "iface", "") or ""),
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "src_port": src_port,
            "dst_port": dst_port,
            "protocol": protocol,
            "length": packet_len,
            "direction": direction,
            "tcp_flags": tcp_flags,
        }

    @staticmethod
    def _get_layer(packet, kind: str):
        candidates = {
            "ip": [IP, "IP"],
            "ipv6": [IPv6, "IPv6"],
            "tcp": [TCP, "TCP"],
            "udp": [UDP, "UDP"],
            "icmp": [ICMP, "ICMP"],
        }.get(kind, [])

        for candidate in candidates:
            if candidate is None:
                continue
            try:
                if hasattr(packet, "haslayer") and packet.haslayer(candidate):
                    return packet.getlayer(candidate)
            except Exception:
                continue
            try:
                if hasattr(packet, "getlayer"):
                    layer = packet.getlayer(candidate)
                    if layer is not None:
                        return layer
            except Exception:
                continue
        return None

    def _open_writers(self):
        self.metadata_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.pcap_dir.mkdir(parents=True, exist_ok=True)
        if self.write_pcap and self._pcap_writer is None and PcapWriter is not None:
            self._pcap_writer = PcapWriter(str(self._pcap_path), append=True, sync=True)

    def _close_writers(self):
        if self._pcap_writer is not None:
            try:
                self._pcap_writer.close()
            except Exception:
                pass
            self._pcap_writer = None

    def _write_metadata(self, metadata: dict):
        with self.metadata_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metadata, ensure_ascii=False) + "\n")

    def _write_pcap(self, packet):
        if not self.write_pcap or self._pcap_writer is None:
            return
        try:
            self._pcap_writer.write(packet)
        except Exception:
            pass

    def _rotate_if_needed(self):
        self._rotate_file(self.metadata_log_path)
        if self.write_pcap:
            rotated = self._rotate_file(self._pcap_path, close_writer=True)
            if rotated and PcapWriter is not None:
                self._pcap_writer = PcapWriter(str(self._pcap_path), append=True, sync=True)

    def _rotate_file(self, path: Path, close_writer: bool = False):
        if not path.exists():
            return False
        if path.stat().st_size <= self.rotate_max_bytes:
            return False

        if close_writer and self._pcap_writer is not None:
            try:
                self._pcap_writer.close()
            except Exception:
                pass
            self._pcap_writer = None

        oldest = path.with_name(f"{path.name}.{self.rotate_keep_files}")
        oldest.unlink(missing_ok=True)
        for index in range(self.rotate_keep_files - 1, 0, -1):
            src = path.with_name(f"{path.name}.{index}")
            dst = path.with_name(f"{path.name}.{index + 1}")
            if src.exists():
                src.rename(dst)
        path.rename(path.with_name(f"{path.name}.1"))
        return True

    def _local_ips(self):
        if callable(self.local_ips_provider):
            try:
                values = self.local_ips_provider() or []
                return [str(item) for item in values]
            except Exception:
                return []
        return []

    def _warn(self, message):
        if self.audit is not None:
            try:
                self.audit.log("network.monitor_error", severity="warning", message=str(message))
            except Exception:
                pass
