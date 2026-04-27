import json
import os
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from core.machine_registry import MachineRegistry


class NetworkEnforcementService:
    def __init__(
        self,
        enabled: bool = False,
        registry: MachineRegistry | None = None,
        providers=None,
        provider_priority=None,
        state_path: str = "state/network_blocks.json",
        default_block_duration_seconds: int = 0,
        audit_logger=None,
    ):
        self.enabled = bool(enabled)
        self.registry = registry or MachineRegistry()
        self.providers = providers or {}
        self.provider_priority = list(provider_priority or ["openwrt", "local"])
        self.default_block_duration_seconds = max(0, int(default_block_duration_seconds))
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit = audit_logger
        self._lock = threading.Lock()
        self._state = {
            "global_internet_blocked": False,
            "machines": {},
            "updated_at": None,
        }
        self._load_state()

    def execute(self, action: str, alias: str | None = None, mac: str | None = None):
        if action in {"register_machine", "list_machines"}:
            return self._handle_registry(action=action, alias=alias, mac=mac)

        if not self.enabled:
            return {"error": "Bloqueio de rede desabilitado na configuracao."}

        action = str(action or "").strip().lower()
        try:
            if action == "block_internet_global":
                return self._block_global_internet()
            if action == "unblock_internet_global":
                return self._unblock_global_internet()
            if action == "block_machine_internet":
                return self._block_machine_internet(alias)
            if action == "unblock_machine_internet":
                return self._unblock_machine_internet(alias)
            if action == "block_machine_isolate":
                return self._block_machine_isolate(alias)
            if action == "unblock_machine":
                return self._unblock_machine(alias)
            if action == "list_blocks":
                return self._list_blocks()
            return {"error": f"Acao de bloqueio nao suportada: {action}"}
        except Exception as exc:
            if self.audit is not None:
                self.audit.log("security.network_block_failed", severity="error", action=action, target=alias, error=str(exc))
            return {"error": str(exc)}

    def _block_global_internet(self):
        with self._lock:
            if self._state.get("global_internet_blocked"):
                return {"message": "Bloqueio global de internet ja estava ativo.", "state": self._snapshot_state()}

            provider_name, provider = self._choose_provider()
            provider.block_internet_global()

            self._state["global_internet_blocked"] = True
            self._touch_unlocked()
            self._save_state_unlocked()

        self._audit_applied(action="block_internet_global", provider=provider_name, target="global")
        return {"message": f"Internet global bloqueada ({provider_name}).", "state": self._snapshot_state()}

    def _unblock_global_internet(self):
        with self._lock:
            if not self._state.get("global_internet_blocked"):
                return {"message": "Bloqueio global de internet ja estava inativo.", "state": self._snapshot_state()}

            provider_name, provider = self._choose_provider()
            provider.unblock_internet_global()

            self._state["global_internet_blocked"] = False
            self._touch_unlocked()
            self._save_state_unlocked()

        self._audit_applied(action="unblock_internet_global", provider=provider_name, target="global")
        return {"message": f"Internet global desbloqueada ({provider_name}).", "state": self._snapshot_state()}

    def _block_machine_internet(self, alias):
        target = self._resolve_machine(alias)
        machine_alias = target["alias"]
        machine_mac = target["mac"]
        with self._lock:
            machine_state = self._state.setdefault("machines", {}).setdefault(machine_alias, {})
            if machine_state.get("internet_blocked"):
                return {"message": f"Internet da maquina '{machine_alias}' ja estava bloqueada.", "state": self._snapshot_state()}

            provider_name, provider = self._choose_provider()
            provider.block_machine_internet(alias=machine_alias, mac=machine_mac)

            machine_state["internet_blocked"] = True
            machine_state["isolated"] = bool(machine_state.get("isolated", False))
            self._touch_unlocked()
            self._save_state_unlocked()

        self._audit_applied(action="block_machine_internet", provider=provider_name, target=machine_alias)
        return {"message": f"Internet da maquina '{machine_alias}' bloqueada ({provider_name}).", "state": self._snapshot_state()}

    def _unblock_machine_internet(self, alias):
        target = self._resolve_machine(alias)
        machine_alias = target["alias"]
        machine_mac = target["mac"]
        with self._lock:
            machine_state = self._state.setdefault("machines", {}).setdefault(machine_alias, {})
            if not machine_state.get("internet_blocked"):
                return {"message": f"Internet da maquina '{machine_alias}' ja estava liberada.", "state": self._snapshot_state()}

            provider_name, provider = self._choose_provider()
            provider.unblock_machine_internet(alias=machine_alias, mac=machine_mac)

            machine_state["internet_blocked"] = False
            self._touch_unlocked()
            self._save_state_unlocked()

        self._audit_applied(action="unblock_machine_internet", provider=provider_name, target=machine_alias)
        return {"message": f"Internet da maquina '{machine_alias}' desbloqueada ({provider_name}).", "state": self._snapshot_state()}

    def _block_machine_isolate(self, alias):
        target = self._resolve_machine(alias)
        machine_alias = target["alias"]
        machine_mac = target["mac"]
        with self._lock:
            machine_state = self._state.setdefault("machines", {}).setdefault(machine_alias, {})
            if machine_state.get("isolated"):
                return {"message": f"Maquina '{machine_alias}' ja estava isolada.", "state": self._snapshot_state()}

            provider_name, provider = self._choose_provider()
            provider.block_machine_isolate(alias=machine_alias, mac=machine_mac)

            machine_state["isolated"] = True
            machine_state["internet_blocked"] = True
            self._touch_unlocked()
            self._save_state_unlocked()

        self._audit_applied(action="block_machine_isolate", provider=provider_name, target=machine_alias)
        return {"message": f"Maquina '{machine_alias}' isolada da rede ({provider_name}).", "state": self._snapshot_state()}

    def _unblock_machine(self, alias):
        target = self._resolve_machine(alias)
        machine_alias = target["alias"]
        machine_mac = target["mac"]
        with self._lock:
            machine_state = self._state.setdefault("machines", {}).setdefault(machine_alias, {})
            if not machine_state.get("isolated") and not machine_state.get("internet_blocked"):
                return {"message": f"Maquina '{machine_alias}' ja estava liberada.", "state": self._snapshot_state()}

            provider_name, provider = self._choose_provider()
            provider.unblock_machine(alias=machine_alias, mac=machine_mac)

            machine_state["isolated"] = False
            machine_state["internet_blocked"] = False
            self._touch_unlocked()
            self._save_state_unlocked()

        self._audit_applied(action="unblock_machine", provider=provider_name, target=machine_alias)
        return {"message": f"Maquina '{machine_alias}' desbloqueada ({provider_name}).", "state": self._snapshot_state()}

    def _list_blocks(self):
        with self._lock:
            state = self._snapshot_state()
        return {"message": "Estado de bloqueios carregado.", "state": state}

    def _handle_registry(self, action: str, alias: str | None, mac: str | None):
        if action == "register_machine":
            if not alias or not mac:
                return {"error": "Para registrar maquina, informe alias e MAC."}
            item = self.registry.register(alias=alias, mac=mac)
            return {"message": f"Maquina '{item['alias']}' registrada com MAC {item['mac']}.", "machine": item}
        if action == "list_machines":
            items = self.registry.list_all()
            if not items:
                return {"message": "Nenhuma maquina registrada ainda.", "machines": []}
            preview = ", ".join(f"{item['alias']}({item['mac']})" for item in items)
            return {"message": f"Maquinas registradas: {preview}", "machines": items}
        return {"error": f"Acao de registry nao suportada: {action}"}

    def _resolve_machine(self, alias):
        normalized_alias = MachineRegistry.normalize_alias(alias or "")
        if not normalized_alias:
            raise ValueError("Alias de maquina invalido.")
        item = self.registry.resolve(normalized_alias)
        if item is None:
            raise ValueError(f"Maquina '{normalized_alias}' nao encontrada no cadastro.")
        return item

    def _choose_provider(self):
        for name in self.provider_priority:
            provider = self.providers.get(name)
            if provider is None:
                continue
            if getattr(provider, "available", True):
                return name, provider
        raise RuntimeError("Nenhum provider de bloqueio de rede disponivel.")

    def _audit_applied(self, action, provider, target):
        if self.audit is not None:
            self.audit.log("security.network_block_applied", action=action, provider=provider, target=target)

    def _snapshot_state(self):
        return {
            "global_internet_blocked": bool(self._state.get("global_internet_blocked", False)),
            "machines": json.loads(json.dumps(self._state.get("machines", {}))),
            "updated_at": self._state.get("updated_at"),
        }

    def _touch_unlocked(self):
        self._state["updated_at"] = datetime.now(timezone.utc).isoformat()

    def _load_state(self):
        if not self.state_path.exists():
            return
        try:
            with self.state_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle) or {}
            if isinstance(data, dict):
                self._state.update(data)
        except Exception:
            pass

    def _save_state_unlocked(self):
        with self.state_path.open("w", encoding="utf-8") as handle:
            json.dump(self._state, handle, ensure_ascii=False, indent=2)


class LocalFirewallProvider:
    def __init__(self, command_runner=None):
        self.available = os.name == "nt"
        self.command_runner = command_runner or _default_command_runner

    def block_internet_global(self):
        self._ensure_windows()
        self._add_rule("Jarvis_Block_Internet_Global", ["dir=out", "action=block", "remoteip=any"])

    def unblock_internet_global(self):
        self._ensure_windows()
        self._delete_rule("Jarvis_Block_Internet_Global")

    def block_machine_internet(self, alias: str, mac: str):
        self._ensure_windows()
        ip = self._lookup_ip_from_mac(mac)
        if not ip:
            raise RuntimeError(f"Nao foi possivel resolver IP local para MAC {mac}.")
        self._add_rule(
            f"Jarvis_Block_Internet_{alias}",
            ["dir=out", "action=block", f"remoteip={ip}"],
        )

    def unblock_machine_internet(self, alias: str, mac: str):
        self._ensure_windows()
        self._delete_rule(f"Jarvis_Block_Internet_{alias}")

    def block_machine_isolate(self, alias: str, mac: str):
        self._ensure_windows()
        ip = self._lookup_ip_from_mac(mac)
        if not ip:
            raise RuntimeError(f"Nao foi possivel resolver IP local para MAC {mac}.")
        self._add_rule(
            f"Jarvis_Isolate_In_{alias}",
            ["dir=in", "action=block", f"remoteip={ip}"],
        )
        self._add_rule(
            f"Jarvis_Isolate_Out_{alias}",
            ["dir=out", "action=block", f"remoteip={ip}"],
        )

    def unblock_machine(self, alias: str, mac: str):
        self._ensure_windows()
        self._delete_rule(f"Jarvis_Isolate_In_{alias}")
        self._delete_rule(f"Jarvis_Isolate_Out_{alias}")
        self._delete_rule(f"Jarvis_Block_Internet_{alias}")

    def _ensure_windows(self):
        if not self.available:
            raise RuntimeError("Provider LocalFirewall disponivel apenas em Windows.")

    def _rule_exists(self, name: str):
        result = self.command_runner(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"],
            check=False,
        )
        return result.returncode == 0 and "No rules match" not in (result.stdout or "")

    def _add_rule(self, name: str, extra_args):
        if self._rule_exists(name):
            return
        command = ["netsh", "advfirewall", "firewall", "add", "rule", f"name={name}", "enable=yes"] + list(extra_args)
        result = self.command_runner(command, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"Falha ao criar regra local '{name}': {result.stderr or result.stdout}")

    def _delete_rule(self, name: str):
        result = self.command_runner(
            ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"],
            check=False,
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError(f"Falha ao remover regra local '{name}': {result.stderr or result.stdout}")

    def _lookup_ip_from_mac(self, mac: str):
        normalized = str(mac or "").strip().lower().replace(":", "-")
        result = self.command_runner(["arp", "-a"], check=False)
        if result.returncode != 0:
            return ""
        pattern = re.compile(r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F\-]{17})\s+\w+\s*$")
        for line in (result.stdout or "").splitlines():
            match = pattern.match(line.strip())
            if not match:
                continue
            ip, current_mac = match.groups()
            if current_mac.lower() == normalized:
                return ip
        return ""


class OpenWrtProvider:
    def __init__(
        self,
        host: str = "",
        port: int = 22,
        username: str = "",
        ssh_key_path: str = "",
        lan_zone: str = "lan",
        wan_zone: str = "wan",
        apply_timeout_seconds: int = 12,
        command_runner=None,
    ):
        self.host = str(host or "").strip()
        self.port = int(port or 22)
        self.username = str(username or "").strip()
        self.ssh_key_path = str(ssh_key_path or "").strip()
        self.lan_zone = str(lan_zone or "lan").strip()
        self.wan_zone = str(wan_zone or "wan").strip()
        self.apply_timeout_seconds = max(3, int(apply_timeout_seconds))
        self.command_runner = command_runner or _default_command_runner
        self.available = bool(self.host and self.username)

    def block_internet_global(self):
        section = "jarvis_global_internet_block"
        script = self._build_set_rule_script(
            section=section,
            src=self.lan_zone,
            dest=self.wan_zone,
            src_mac=None,
        )
        self._apply_script_with_rollback(script)

    def unblock_internet_global(self):
        section = "jarvis_global_internet_block"
        script = self._build_delete_sections_script([section])
        self._apply_script_with_rollback(script)

    def block_machine_internet(self, alias: str, mac: str):
        section = f"jarvis_block_internet_{self._safe_alias(alias)}"
        script = self._build_set_rule_script(
            section=section,
            src=self.lan_zone,
            dest=self.wan_zone,
            src_mac=mac,
        )
        self._apply_script_with_rollback(script)

    def unblock_machine_internet(self, alias: str, mac: str):
        section = f"jarvis_block_internet_{self._safe_alias(alias)}"
        script = self._build_delete_sections_script([section])
        self._apply_script_with_rollback(script)

    def block_machine_isolate(self, alias: str, mac: str):
        base_alias = self._safe_alias(alias)
        section_wan = f"jarvis_isolate_wan_{base_alias}"
        section_lan = f"jarvis_isolate_lan_{base_alias}"
        script = "\n".join(
            [
                self._build_set_rule_script(section_wan, src=self.lan_zone, dest=self.wan_zone, src_mac=mac),
                self._build_set_rule_script(section_lan, src=self.lan_zone, dest=self.lan_zone, src_mac=mac),
            ]
        )
        self._apply_script_with_rollback(script)

    def unblock_machine(self, alias: str, mac: str):
        base_alias = self._safe_alias(alias)
        sections = [
            f"jarvis_block_internet_{base_alias}",
            f"jarvis_isolate_wan_{base_alias}",
            f"jarvis_isolate_lan_{base_alias}",
        ]
        script = self._build_delete_sections_script(sections)
        self._apply_script_with_rollback(script)

    def _build_set_rule_script(self, section: str, src: str, dest: str, src_mac: str | None):
        lines = [
            f"uci -q delete firewall.{section}",
            f"uci set firewall.{section}=rule",
            f"uci set firewall.{section}.name='{section}'",
            f"uci set firewall.{section}.src='{src}'",
            f"uci set firewall.{section}.dest='{dest}'",
            f"uci set firewall.{section}.proto='all'",
            f"uci set firewall.{section}.target='REJECT'",
        ]
        if src_mac:
            lines.append(f"uci set firewall.{section}.src_mac='{self._normalize_mac(src_mac)}'")
        return "\n".join(lines)

    @staticmethod
    def _build_delete_sections_script(sections):
        return "\n".join(f"uci -q delete firewall.{name}" for name in sections)

    def _apply_script_with_rollback(self, script_body: str):
        if not self.available:
            raise RuntimeError("Provider OpenWrt indisponivel: configure host e usuario.")

        backup_path = "/tmp/jarvis_firewall_backup.conf"
        self._ssh_command(f"uci export firewall > {backup_path}")
        script = "\n".join(
            [
                "set -e",
                script_body,
                "uci commit firewall",
                "/etc/init.d/firewall reload",
            ]
        )
        try:
            self._ssh_script(script)
        except Exception as exc:
            try:
                self._ssh_command(
                    f"test -f {backup_path} && uci import firewall < {backup_path} && uci commit firewall && /etc/init.d/firewall reload"
                )
            except Exception:
                pass
            raise RuntimeError(f"Falha ao aplicar regra no OpenWrt: {exc}") from exc

    def _ssh_command(self, remote_command: str):
        args = self._ssh_base_args() + [remote_command]
        result = self.command_runner(args, check=False, timeout=self.apply_timeout_seconds)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "ssh failure")
        return result.stdout or ""

    def _ssh_script(self, script: str):
        args = self._ssh_base_args() + ["sh", "-s"]
        result = self.command_runner(
            args,
            check=False,
            timeout=self.apply_timeout_seconds,
            input=script,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "ssh script failure")
        return result.stdout or ""

    def _ssh_base_args(self):
        args = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-p",
            str(self.port),
        ]
        if self.ssh_key_path:
            args.extend(["-i", self.ssh_key_path])
        args.append(f"{self.username}@{self.host}")
        return args

    @staticmethod
    def _safe_alias(alias):
        value = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(alias or "").strip().lower())
        return value.strip("_")

    @staticmethod
    def _normalize_mac(mac):
        value = str(mac or "").strip().lower().replace("-", ":")
        if not re.match(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$", value):
            raise RuntimeError(f"MAC invalido para OpenWrt: {mac}")
        return value


def _default_command_runner(args, check=False, timeout=15, input=None):
    return subprocess.run(
        args,
        check=check,
        timeout=timeout,
        text=True,
        encoding="utf-8",
        errors="ignore",
        capture_output=True,
        input=input,
    )
