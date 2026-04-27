import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.network_monitor as network_monitor_module
from core.network_monitor import NetworkMonitorService


class FakeLayer:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakePacket:
    def __init__(self, layers, length=64, sniffed_on="Ethernet"):
        self.layers = dict(layers)
        self.length = length
        self.sniffed_on = sniffed_on

    def haslayer(self, candidate):
        return self._layer_key(candidate) in self.layers

    def getlayer(self, candidate):
        return self.layers.get(self._layer_key(candidate))

    def __len__(self):
        return self.length

    @staticmethod
    def _layer_key(candidate):
        if isinstance(candidate, str):
            return candidate
        return getattr(candidate, "__name__", str(candidate))


class NetworkMonitorTests(unittest.TestCase):
    def test_packet_to_metadata_parses_tcp(self):
        packet = FakePacket(
            {
                "IP": FakeLayer(src="10.0.0.2", dst="8.8.8.8"),
                "TCP": FakeLayer(sport=55000, dport=443, flags="PA"),
            },
            length=120,
        )

        metadata = NetworkMonitorService.packet_to_metadata(packet, local_ips=["10.0.0.2"])

        self.assertEqual(metadata["protocol"], "TCP")
        self.assertEqual(metadata["src_port"], 55000)
        self.assertEqual(metadata["dst_port"], 443)
        self.assertEqual(metadata["direction"], "outbound")
        self.assertEqual(metadata["interface"], "Ethernet")

    def test_packet_to_metadata_parses_udp_and_icmp(self):
        udp_packet = FakePacket(
            {
                "IP": FakeLayer(src="1.1.1.1", dst="10.0.0.3"),
                "UDP": FakeLayer(sport=53, dport=55001),
            }
        )
        icmp_packet = FakePacket(
            {
                "IP": FakeLayer(src="10.0.0.3", dst="8.8.4.4"),
                "ICMP": FakeLayer(type=8),
            }
        )

        udp_meta = NetworkMonitorService.packet_to_metadata(udp_packet, local_ips=["10.0.0.3"])
        icmp_meta = NetworkMonitorService.packet_to_metadata(icmp_packet, local_ips=["10.0.0.3"])

        self.assertEqual(udp_meta["protocol"], "UDP")
        self.assertEqual(udp_meta["direction"], "inbound")
        self.assertEqual(icmp_meta["protocol"], "ICMP")

    def test_writes_metadata_and_rotates_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_path = Path(temp_dir) / "traffic.jsonl"
            pcap_dir = Path(temp_dir) / "pcap"
            service = NetworkMonitorService(
                enabled=True,
                write_pcap=False,
                metadata_log_path=str(metadata_path),
                pcap_dir=str(pcap_dir),
                local_ips_provider=lambda: ["10.0.0.9"],
                rotate_max_mb=1,
                rotate_keep_files=2,
            )
            service.rotate_max_bytes = 30
            metadata_path.write_text("x" * 100, encoding="utf-8")

            packet = FakePacket(
                {
                    "IP": FakeLayer(src="10.0.0.9", dst="8.8.8.8"),
                    "TCP": FakeLayer(sport=12345, dport=80, flags="S"),
                },
                length=70,
            )
            service.handle_packet_for_test(packet)

            rotated = Path(str(metadata_path) + ".1")
            self.assertTrue(rotated.exists())
            self.assertTrue(metadata_path.exists())
            self.assertGreater(service.status()["packets"], 0)

    def test_start_logs_warning_when_dependency_missing(self):
        with patch.object(network_monitor_module, "AsyncSniffer", None):
            events = []

            class FakeAudit:
                def log(self, event, severity="info", **data):
                    events.append({"event": event, "severity": severity, "data": data})

            service = NetworkMonitorService(
                enabled=True,
                audit_logger=FakeAudit(),
            )

            result = service.start()

            self.assertIn("error", result)
            self.assertTrue(any(item["event"] == "network.monitor_error" for item in events))


if __name__ == "__main__":
    unittest.main()
