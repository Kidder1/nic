from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import locale
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unicodedata
from pathlib import Path
from typing import Optional

from . import __version__


SYSTEM_PROFILER_CACHE = Path(tempfile.gettempdir()) / "nic-system-profiler.json"
SYSTEM_PROFILER_CACHE_TTL = 30
WINDOWS_KEY_ALIASES = {
    "description": "description",
    "描述": "description",
    "physicaladdress": "physicaladdress",
    "物理地址": "physicaladdress",
    "mediastate": "mediastate",
    "媒体状态": "mediastate",
    "ipv4address": "ipv4address",
    "ipv4地址": "ipv4address",
    "autoconfigurationipv4address": "autoconfigurationipv4address",
    "自动配置ipv4地址": "autoconfigurationipv4address",
    "subnetmask": "subnetmask",
    "子网掩码": "subnetmask",
    "ipv6address": "ipv6address",
    "ipv6地址": "ipv6address",
    "temporaryipv6address": "temporaryipv6address",
    "临时ipv6地址": "temporaryipv6address",
    "linklocalipv6address": "linklocalipv6address",
    "本地链接ipv6地址": "linklocalipv6address",
    "本地链路ipv6地址": "linklocalipv6address",
    "defaultgateway": "defaultgateway",
    "默认网关": "defaultgateway",
    "dnsservers": "dnsservers",
    "dns服务器": "dnsservers",
}


def decode_command_output(output: bytes, platform_name: Optional[str] = None) -> str:
    if not output:
        return ""

    candidates: list[str] = []
    if output.startswith((b"\xff\xfe", b"\xfe\xff")) or output[:4].count(b"\x00") >= 2:
        candidates.extend(["utf-16", "utf-16le", "utf-16be"])

    candidates.extend(["utf-8-sig", "utf-8"])

    platform_key = detect_platform(platform_name)
    if platform_key == "windows":
        candidates.extend(["cp936", "gbk", "cp950", "big5", "cp932", "shift_jis", "cp949", "euc_kr"])

    preferred_encodings = [
        locale.getpreferredencoding(False),
        getattr(locale, "getencoding", lambda: "")(),
    ]
    if platform_key == "windows":
        preferred_encodings.extend(["mbcs", "oem"])

    seen: set[str] = set()
    for encoding in preferred_encodings:
        normalized = str(encoding or "").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(normalized)

    for encoding in candidates:
        try:
            return output.decode(encoding)
        except Exception:
            continue

    return output.decode("utf-8", errors="ignore")


def run(command: list[str]) -> str:
    try:
        output = subprocess.check_output(
            command,
            text=False,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return ""
    return decode_command_output(output)


def run_passthrough(command: list[str]) -> int:
    try:
        return subprocess.run(command, check=False).returncode
    except Exception:
        return 1


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def read_cached(command: list[str], cache_path: Path, ttl: int, refresh: bool = False) -> str:
    if not refresh:
        try:
            if cache_path.exists() and time.time() - cache_path.stat().st_mtime < ttl:
                return cache_path.read_text(encoding="utf-8")
        except OSError:
            pass

    fresh = run(command)
    if fresh:
        try:
            cache_path.write_text(fresh, encoding="utf-8")
        except OSError:
            pass
        return fresh

    try:
        return cache_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def detect_platform(value: Optional[str] = None) -> str:
    current = value or sys.platform
    if current in {"macos", "linux", "windows"}:
        return current
    if current.startswith("darwin"):
        return "macos"
    if current.startswith("linux"):
        return "linux"
    if current.startswith(("win32", "cygwin", "msys")):
        return "windows"
    return "unknown"


def raw_command(platform_name: Optional[str] = None) -> list[str]:
    platform_key = detect_platform(platform_name)
    if platform_key == "macos":
        return ["ifconfig", "-a"]
    if platform_key == "linux":
        return ["ip", "addr"]
    if platform_key == "windows":
        return ["ipconfig", "/all"]
    return []


def normalize_mac(value: str) -> str:
    cleaned = value.strip().replace("-", ":").lower()
    if not cleaned or cleaned in {"n/a", "not available", "none"}:
        return ""
    return cleaned


def strip_annotations(value: str) -> str:
    return re.sub(r"\s*[\(（].*?[\)）]\s*", "", value).strip()


def strip_linux_alias(name: str) -> str:
    return name.split("@", 1)[0]


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def prefix_to_netmask(prefix: str) -> str:
    if not prefix:
        return ""
    try:
        return str(ipaddress.IPv4Network(f"0.0.0.0/{prefix}").netmask)
    except Exception:
        return ""


def normalize_netmask(value: str) -> tuple[str, str]:
    if not value:
        return "", ""

    try:
        if value.startswith("0x"):
            mask_int = int(value, 16) & 0xFFFFFFFF
            dotted = str(ipaddress.IPv4Address(mask_int))
        else:
            dotted = str(ipaddress.IPv4Address(value))
            mask_int = int(ipaddress.IPv4Address(dotted))
        prefix = str(bin(mask_int).count("1"))
        return dotted, prefix
    except Exception:
        return value, ""


def ipv4_item(address: str, prefix: str = "", netmask: str = "") -> dict[str, str]:
    cleaned_address = strip_annotations(address)
    dotted_mask, dotted_prefix = normalize_netmask(netmask) if netmask else ("", "")
    normalized_prefix = prefix or dotted_prefix
    normalized_netmask = dotted_mask or prefix_to_netmask(normalized_prefix)
    return {
        "address": cleaned_address,
        "netmask": normalized_netmask,
        "prefix": normalized_prefix,
    }


def parse_ifconfig(output: str) -> dict[str, dict]:
    interfaces: dict[str, dict] = {}
    current: Optional[dict] = None

    for raw_line in output.splitlines():
        if raw_line and not raw_line[0].isspace() and ":" in raw_line:
            name, header = raw_line.split(":", 1)
            current = {
                "name": name,
                "header": header,
                "status": "",
                "mac": "",
                "ipv4": [],
                "ipv6": [],
            }
            interfaces[name] = current
            continue

        if current is None:
            continue

        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("ether "):
            current["mac"] = normalize_mac(line.split()[1])
            continue

        if line.startswith("inet "):
            parts = line.split()
            address = parts[1]
            netmask = parts[parts.index("netmask") + 1] if "netmask" in parts else ""
            current["ipv4"].append(ipv4_item(address, netmask=netmask))
            continue

        if line.startswith("inet6 "):
            parts = line.split()
            address = strip_annotations(parts[1])
            prefix = parts[parts.index("prefixlen") + 1] if "prefixlen" in parts else ""
            current["ipv6"].append({"address": address, "prefix": prefix})
            continue

        if line.startswith("status: "):
            current["status"] = line.split()[1]

    return interfaces


def parse_system_profiler(output: str) -> dict[str, dict]:
    if not output:
        return {}

    try:
        payload = json.loads(output)
    except Exception:
        return {}

    metadata = {}
    for item in payload.get("SPNetworkDataType", []):
        interface = item.get("interface")
        if not interface:
            continue

        label = item.get("_name") or interface
        dns = item.get("DNS", {}).get("ServerAddresses", []) or []
        gateway = item.get("IPv4", {}).get("Router", "")
        hardware_mac = normalize_mac(item.get("Ethernet", {}).get("MAC Address", ""))
        kind = infer_kind(interface, item=item, label=label)
        type_label = ""
        if kind == "Ethernet" and label and not re.match(r"^Ethernet Adapter \(en\d+\)$", label):
            type_label = label

        metadata[interface] = {
            "label": label,
            "kind": kind,
            "dns": dns,
            "gateway": gateway,
            "hardware_mac": hardware_mac,
            "type_label": type_label,
        }

    return metadata


def parse_default_route(output: str) -> dict[str, str]:
    for line in output.splitlines():
        fields = line.split()
        if fields[:1] == ["default"] and len(fields) >= 4:
            return {"gateway": fields[1], "interface": fields[-1]}
    return {"gateway": "", "interface": ""}


def parse_ip_addr_json(output: str) -> dict[str, dict]:
    if not output:
        return {}

    try:
        payload = json.loads(output)
    except Exception:
        return {}

    interfaces: dict[str, dict] = {}
    for item in payload:
        name = strip_linux_alias(item.get("ifname", ""))
        if not name:
            continue

        flags = " ".join(item.get("flags", []) or [])
        operstate = str(item.get("operstate", "")).upper()
        header = " ".join(part for part in [flags, operstate] if part).strip()
        info = {
            "name": name,
            "header": header,
            "status": "",
            "mac": "",
            "ipv4": [],
            "ipv6": [],
        }

        link_type = item.get("link_type", "")
        address = normalize_mac(item.get("address", ""))
        if address and link_type != "loopback":
            info["mac"] = address

        for addr_info in item.get("addr_info", []) or []:
            family = addr_info.get("family")
            local = strip_annotations(addr_info.get("local", ""))
            prefix = str(addr_info.get("prefixlen", "")) if addr_info.get("prefixlen", "") != "" else ""
            if family == "inet" and local:
                info["ipv4"].append(ipv4_item(local, prefix=prefix))
            elif family == "inet6" and local:
                info["ipv6"].append({"address": local, "prefix": prefix})

        interfaces[name] = info

    return interfaces


def parse_ip_addr_output(output: str) -> dict[str, dict]:
    interfaces: dict[str, dict] = {}
    current: Optional[dict] = None

    for raw_line in output.splitlines():
        header_match = re.match(r"^\d+:\s+([^:]+):\s+<([^>]*)>(.*)$", raw_line)
        if header_match:
            name = strip_linux_alias(header_match.group(1))
            flags = header_match.group(2)
            tail = header_match.group(3)
            state_match = re.search(r"\bstate\s+(\S+)", tail)
            header = " ".join(
                part for part in [flags, state_match.group(1).upper() if state_match else ""] if part
            )
            current = {
                "name": name,
                "header": header,
                "status": "",
                "mac": "",
                "ipv4": [],
                "ipv6": [],
            }
            interfaces[name] = current
            continue

        if current is None:
            continue

        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("link/ether "):
            current["mac"] = normalize_mac(line.split()[1])
            continue

        if line.startswith("inet "):
            address = line.split()[1]
            host, prefix = address.split("/", 1)
            current["ipv4"].append(ipv4_item(host, prefix=prefix))
            continue

        if line.startswith("inet6 "):
            address = line.split()[1]
            host, prefix = (address.split("/", 1) + [""])[:2]
            current["ipv6"].append({"address": strip_annotations(host), "prefix": prefix})

    return interfaces


def parse_ip_route_json(output: str) -> dict[str, str]:
    if not output:
        return {"gateway": "", "interface": ""}

    try:
        payload = json.loads(output)
    except Exception:
        return {"gateway": "", "interface": ""}

    for item in payload:
        if item.get("dst") != "default":
            continue
        return {
            "gateway": item.get("gateway", "") or "",
            "interface": strip_linux_alias(item.get("dev", "") or ""),
        }

    return {"gateway": "", "interface": ""}


def parse_ip_route_output(output: str) -> dict[str, str]:
    for line in output.splitlines():
        if not line.startswith("default"):
            continue
        gateway_match = re.search(r"\bvia\s+(\S+)", line)
        dev_match = re.search(r"\bdev\s+(\S+)", line)
        return {
            "gateway": gateway_match.group(1) if gateway_match else "",
            "interface": strip_linux_alias(dev_match.group(1)) if dev_match else "",
        }
    return {"gateway": "", "interface": ""}


def parse_linux_resolv_conf(output: str) -> list[str]:
    servers = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("nameserver"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            servers.append(parts[1])
    return dedupe(servers)


def normalize_windows_key(value: str) -> str:
    compact = re.sub(r"[\s\.\:：·•。．]+", "", value.lower())
    compact = re.sub(r"[^\w\u4e00-\u9fff]+", "", compact)
    return WINDOWS_KEY_ALIASES.get(compact, re.sub(r"[^a-z0-9]+", "", compact))


def extract_windows_interface_name(block_label: str) -> str:
    match = re.search(r"adapter\s+(.+)$", block_label, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    match = re.search(r"适配器\s+(.+)$", block_label)
    if match:
        return match.group(1).strip()

    return block_label.strip()


def parse_windows_ipv6(value: str) -> dict[str, str]:
    address = strip_annotations(value)
    return {"address": address, "prefix": ""}


def parse_ipconfig_all(output: str) -> tuple[dict[str, dict], dict[str, dict]]:
    interfaces: dict[str, dict] = {}
    metadata: dict[str, dict] = {}
    current: Optional[dict] = None
    current_name = ""
    last_key = ""

    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            last_key = ""
            continue

        if line and not line.startswith(" "):
            if stripped.endswith(":") and "configuration" not in stripped.lower():
                block_label = stripped[:-1]
                current_name = extract_windows_interface_name(block_label)
                current = {
                    "name": current_name,
                    "header": block_label,
                    "status": "",
                    "mac": "",
                    "ipv4": [],
                    "ipv6": [],
                    "_ipv4_values": [],
                    "_ipv4_masks": [],
                }
                interfaces[current_name] = current
                metadata[current_name] = {
                    "label": block_label,
                    "kind": infer_kind(current_name, label=block_label),
                    "dns": [],
                    "gateway": "",
                    "hardware_mac": "",
                    "type_label": "",
                }
            else:
                current = None
                current_name = ""
            last_key = ""
            continue

        if current is None:
            continue

        if ":" in stripped:
            key_raw, value = stripped.split(":", 1)
            key = normalize_windows_key(key_raw)
            value = value.strip()
            last_key = key

            if key == "description":
                metadata[current_name]["label"] = value or metadata[current_name]["label"]
                metadata[current_name]["kind"] = infer_kind(current_name, label=metadata[current_name]["label"])
                continue

            if key == "physicaladdress":
                mac = normalize_mac(value)
                current["mac"] = mac
                metadata[current_name]["hardware_mac"] = mac
                continue

            if key == "mediastate" and "disconnected" in value.lower():
                current["status"] = "inactive"
                continue

            if key in {"ipv4address", "autoconfigurationipv4address"} and value:
                current["_ipv4_values"].append(strip_annotations(value))
                continue

            if key == "subnetmask" and value:
                current["_ipv4_masks"].append(value)
                continue

            if key in {"ipv6address", "temporaryipv6address", "linklocalipv6address"} and value:
                current["ipv6"].append(parse_windows_ipv6(value))
                continue

            if key == "defaultgateway":
                gateway = strip_annotations(value)
                if gateway and not metadata[current_name]["gateway"]:
                    metadata[current_name]["gateway"] = gateway
                continue

            if key == "dnsservers":
                dns_value = strip_annotations(value)
                if dns_value:
                    metadata[current_name]["dns"].append(dns_value)
                continue

            continue

        if last_key == "defaultgateway":
            gateway = strip_annotations(stripped)
            if gateway and not metadata[current_name]["gateway"]:
                metadata[current_name]["gateway"] = gateway
            continue

        if last_key == "dnsservers":
            dns_value = strip_annotations(stripped)
            if dns_value:
                metadata[current_name]["dns"].append(dns_value)

    for name, info in interfaces.items():
        masks = info.pop("_ipv4_masks")
        values = info.pop("_ipv4_values")
        for index, address in enumerate(values):
            mask = masks[index] if index < len(masks) else (masks[-1] if masks else "")
            info["ipv4"].append(ipv4_item(address, netmask=mask))

        if not info["mac"]:
            info["mac"] = metadata[name].get("hardware_mac", "")

        metadata[name]["dns"] = dedupe(metadata[name]["dns"])
        metadata[name]["hardware_mac"] = metadata[name].get("hardware_mac") or info["mac"]
        metadata[name]["kind"] = infer_kind(name, label=metadata[name].get("label", name))

    return interfaces, metadata


def parse_route_print(output: str) -> dict[str, str]:
    best_route: Optional[dict[str, str]] = None

    for raw_line in output.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        fields = stripped.split()
        if len(fields) < 5:
            continue
        if fields[0] != "0.0.0.0" or fields[1] != "0.0.0.0":
            continue

        route = {
            "gateway": fields[2],
            "interface_ip": fields[3],
            "metric": fields[4],
        }
        if best_route is None:
            best_route = route
            continue

        try:
            if int(route["metric"]) < int(best_route["metric"]):
                best_route = route
        except ValueError:
            pass

    if not best_route:
        return {"gateway": "", "interface_ip": ""}

    return {
        "gateway": best_route["gateway"],
        "interface_ip": best_route["interface_ip"],
    }


def parse_getmac_csv(output: str) -> dict[str, dict]:
    metadata: dict[str, dict] = {}
    for row in csv.reader(output.splitlines()):
        if not row:
            continue
        if len(row) >= 4:
            connection_name = row[0].strip()
            description = row[1].strip()
            mac = normalize_mac(row[2].strip())
        elif len(row) >= 2:
            connection_name = row[0].strip()
            description = ""
            mac = normalize_mac(row[1].strip())
        else:
            continue

        if not connection_name or connection_name.lower() == "n/a":
            continue

        metadata[connection_name] = {
            "label": description or connection_name,
            "hardware_mac": mac,
        }

    return metadata


def infer_kind(interface: str, item: Optional[dict] = None, label: str = "") -> str:
    if item:
        reported_type = item.get("type") or item.get("hardware") or ""
        if reported_type == "AirPort":
            return "Wi-Fi"
        if interface.startswith("bridge"):
            return "Bridge"
        if reported_type == "Ethernet":
            return "Ethernet"
        if reported_type:
            return reported_type

    name = interface.lower()
    combined = f"{interface} {label}".lower()

    if name in {"lo", "lo0"} or "loopback" in combined:
        return "Loopback"
    if name.startswith("awdl"):
        return "AirDrop/Continuity"
    if name.startswith("llw"):
        return "Wi-Fi helper"
    if name.startswith("ap"):
        return "Hotspot helper"
    if name.startswith("anpi"):
        return "Apple internal"
    if name in {"gif0", "stf0"}:
        return "Legacy tunnel"
    if name.startswith("veth"):
        return "Container veth"
    if any(token in combined for token in ("wi-fi", "wifi", "wireless lan", "wireless")) or name.startswith(
        ("wlan", "wlp", "wlx")
    ):
        return "Wi-Fi"
    if any(token in combined for token in ("无线局域网", "无线网络", "无线")):
        return "Wi-Fi"
    if "bluetooth" in combined:
        return "Bluetooth"
    if "蓝牙" in combined:
        return "Bluetooth"
    if any(token in combined for token in ("hyper-v", "vmware", "virtualbox", "wsl")) or name.startswith(
        ("vmenet", "vmnet", "vboxnet")
    ):
        return "VM network"
    if any(token in combined for token in ("虚拟", "hyper-v", "wsl")):
        return "VM network"
    if name.startswith(("bridge", "br-", "virbr", "docker", "cni", "flannel", "lxcbr", "podman")):
        return "Bridge"
    if any(token in combined for token in ("桥接",)):
        return "Bridge"
    if name.startswith(("utun", "tun", "tap", "wg", "ppp", "tailscale", "zt", "isatap")) or any(
        token in combined for token in ("vpn", "wireguard", "tunnel", "tailscale", "zerotier")
    ):
        return "Tunnel/VPN"
    if any(token in combined for token in ("隧道", "vpn")):
        return "Tunnel/VPN"
    if name.startswith(("en", "eth", "eno", "ens", "enp", "em", "bond", "team", "ib", "wwan", "wwp")):
        return "Ethernet"
    if any(token in combined for token in ("ethernet", "lan", "以太网", "局域网")):
        return "Ethernet"
    return "System"


def infer_family(interface: str, interface_type: str, label: str = "") -> str:
    name = interface.lower()
    combined = f"{interface} {interface_type} {label}".lower()

    if interface_type in {
        "Loopback",
        "AirDrop/Continuity",
        "Wi-Fi helper",
        "Hotspot helper",
        "Apple internal",
        "Legacy tunnel",
        "Container veth",
        "System",
    } or name in {"lo", "lo0"}:
        return "system"

    if interface_type == "Tunnel/VPN":
        return "tunnel"

    if interface_type in {"Bridge", "VM network"} or any(
        token in combined for token in ("bridge", "hyper-v", "vmware", "virtualbox", "wsl", "docker", "virbr")
    ):
        return "virtual"

    if interface_type in {"Wi-Fi", "Ethernet", "Bluetooth"} or name.startswith(
        ("en", "eth", "eno", "ens", "enp", "em", "wlan", "wlp", "wlx", "wwan", "wwp")
    ) or any(
        token in combined
        for token in ("ethernet", "wifi", "wi-fi", "wireless", " lan", "bluetooth", "以太网", "局域网", "无线", "蓝牙")
    ):
        return "physical"

    return "system"


def state_for(info: dict, default_interface: str) -> str:
    status = info.get("status", "").lower()
    if status in {"active", "inactive", "up", "down"}:
        return status
    if info["name"] == default_interface:
        return "active"
    if info.get("ipv4"):
        return "active"
    if "UP" in info.get("header", "").upper():
        return "up"
    return "down"


def first_ipv4(info: dict, include_loopback: bool = False) -> Optional[dict]:
    for item in info.get("ipv4", []):
        if include_loopback or item["address"] != "127.0.0.1":
            return item
    return None


def first_ipv6(info: dict) -> Optional[dict]:
    non_local = []
    link_local = []
    for item in info.get("ipv6", []):
        address = item["address"]
        if address == "::1":
            continue
        if address.startswith("fe80::"):
            link_local.append(item)
        else:
            non_local.append(item)
    return (non_local or link_local or [None])[0]


def format_ipv4(item: Optional[dict]) -> str:
    if not item:
        return "-"
    if item.get("prefix"):
        return f"{item['address']}/{item['prefix']}"
    return item["address"]


def format_ipv6(item: Optional[dict]) -> str:
    if not item:
        return "-"
    prefix = f"/{item['prefix']}" if item.get("prefix") else ""
    return f"{item['address']}{prefix}"


def derive_subnet(ipv4: Optional[dict]) -> str:
    if not ipv4 or not ipv4.get("netmask"):
        return ""
    try:
        network = ipaddress.IPv4Network((ipv4["address"], ipv4["netmask"]), strict=False)
        return str(network)
    except Exception:
        return ""


def sort_key(name: str, interfaces: dict[str, dict], default_interface: str) -> tuple:
    match = re.match(r"([a-zA-Z]+)(\d+)$", name)
    if match:
        base_key = (match.group(1).lower(), int(match.group(2)))
    else:
        base_key = (name.lower(), -1)

    return (
        0 if name == default_interface else 1,
        0 if state_for(interfaces[name], default_interface) == "active" else 1,
        base_key,
    )


def build_row(name: str, info: dict, meta: dict, default_route: dict[str, str]) -> dict:
    label = meta.get("label", "") or name
    interface_type = meta.get("kind") or infer_kind(name, label=label)
    if interface_type == "Ethernet" and meta.get("type_label"):
        interface_type = meta["type_label"]

    family = infer_family(name, interface_type, label=label)
    ipv4 = first_ipv4(info, include_loopback=(interface_type == "Loopback"))
    current_mac = info.get("mac") or meta.get("hardware_mac") or "-"
    hardware_mac = meta.get("hardware_mac") or current_mac

    return {
        "iface": name,
        "label": label,
        "type": interface_type,
        "family": family,
        "state": state_for(info, default_route.get("interface", "")),
        "primary": name == default_route.get("interface", ""),
        "ipv4": format_ipv4(ipv4),
        "ipv4_item": ipv4,
        "ipv6": format_ipv6(first_ipv6(info)),
        "current_mac": current_mac or "-",
        "hardware_mac": hardware_mac or "",
        "gateway": default_route.get("gateway", "") if name == default_route.get("interface", "") else meta.get("gateway", ""),
        "dns": meta.get("dns", []),
        "netmask": ipv4.get("netmask", "") if ipv4 else "",
        "subnet": derive_subnet(ipv4),
        "private_mac": bool(
            current_mac
            and hardware_mac
            and current_mac != "-"
            and hardware_mac != "-"
            and current_mac.lower() != hardware_mac.lower()
        ),
    }


def parse_collect_result(
    interfaces: dict[str, dict], metadata: dict[str, dict], default_route: dict[str, str]
) -> dict[str, object]:
    physical = []
    system = []
    tunnels = []
    rows = []
    default_interface = default_route.get("interface", "")

    for name in sorted(interfaces, key=lambda current: sort_key(current, interfaces, default_interface)):
        row = build_row(name, interfaces[name], metadata.get(name, {}), default_route)
        rows.append(row)
        if row["family"] == "physical":
            physical.append(row)
        elif row["family"] == "tunnel":
            tunnels.append(row)
        else:
            system.append(row)

    primary = next((row for row in rows if row["primary"]), None)
    if primary is None:
        primary = next((row for row in physical if row["state"] == "active"), None)
    if primary is None:
        primary = next((row for row in rows if row["state"] == "active"), None)

    return {
        "default_route": default_route,
        "physical": physical,
        "system": system,
        "tunnels": tunnels,
        "primary": primary,
    }


def collect_macos(refresh: bool = False) -> dict[str, object]:
    interfaces = parse_ifconfig(run(["ifconfig", "-a"]))
    metadata = parse_system_profiler(
        read_cached(
            ["system_profiler", "SPNetworkDataType", "-json"],
            cache_path=SYSTEM_PROFILER_CACHE,
            ttl=SYSTEM_PROFILER_CACHE_TTL,
            refresh=refresh,
        )
    )
    default_route = parse_default_route(run(["netstat", "-rn", "-f", "inet"]))
    return parse_collect_result(interfaces, metadata, default_route)


def collect_linux(refresh: bool = False) -> dict[str, object]:
    del refresh
    if not command_exists("ip"):
        return parse_collect_result({}, {}, {"gateway": "", "interface": ""})

    interfaces = parse_ip_addr_json(run(["ip", "-j", "addr"]))
    if not interfaces:
        interfaces = parse_ip_addr_output(run(["ip", "addr"]))

    default_route = parse_ip_route_json(run(["ip", "-j", "route", "show", "default"]))
    if not default_route.get("interface"):
        default_route = parse_ip_route_output(run(["ip", "route", "show", "default"]))

    resolv_conf = ""
    try:
        resolv_conf = Path("/etc/resolv.conf").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        pass
    dns_servers = parse_linux_resolv_conf(resolv_conf)

    metadata = {}
    for name in interfaces:
        metadata[name] = {
            "label": name,
            "kind": infer_kind(name),
            "dns": dns_servers if name == default_route.get("interface", "") else [],
            "gateway": default_route.get("gateway", "") if name == default_route.get("interface", "") else "",
            "hardware_mac": interfaces[name].get("mac", ""),
            "type_label": "",
        }

    return parse_collect_result(interfaces, metadata, default_route)


def collect_windows(refresh: bool = False) -> dict[str, object]:
    del refresh
    interfaces, metadata = parse_ipconfig_all(run(["ipconfig", "/all"]))

    getmac_output = run(["getmac", "/v", "/fo", "csv", "/nh"])
    for name, extra in parse_getmac_csv(getmac_output).items():
        metadata.setdefault(
            name,
            {
                "label": name,
                "kind": infer_kind(name),
                "dns": [],
                "gateway": "",
                "hardware_mac": "",
                "type_label": "",
            },
        )
        if extra.get("label"):
            metadata[name]["label"] = metadata[name].get("label") or extra["label"]
        if extra.get("hardware_mac") and not metadata[name].get("hardware_mac"):
            metadata[name]["hardware_mac"] = extra["hardware_mac"]

    route_info = parse_route_print(run(["route", "print", "-4"]))
    interface_ip_map = {}
    for name, info in interfaces.items():
        for item in info.get("ipv4", []):
            interface_ip_map[item["address"]] = name

    default_interface = interface_ip_map.get(route_info.get("interface_ip", ""), "")
    default_route = {
        "gateway": route_info.get("gateway", ""),
        "interface": default_interface,
    }

    if not default_interface:
        gateway_candidates = [
            name
            for name, meta in metadata.items()
            if meta.get("gateway") and interfaces.get(name, {}).get("ipv4")
        ]
        if gateway_candidates:
            default_interface = gateway_candidates[0]
            default_route = {
                "gateway": metadata[default_interface].get("gateway", ""),
                "interface": default_interface,
            }

    if default_interface:
        metadata.setdefault(
            default_interface,
            {
                "label": default_interface,
                "kind": infer_kind(default_interface),
                "dns": [],
                "gateway": "",
                "hardware_mac": interfaces.get(default_interface, {}).get("mac", ""),
                "type_label": "",
            },
        )
        if not metadata[default_interface].get("gateway"):
            metadata[default_interface]["gateway"] = default_route["gateway"]

    return parse_collect_result(interfaces, metadata, default_route)


def collect(refresh: bool = False) -> dict[str, object]:
    platform_key = detect_platform()
    if platform_key == "macos":
        return collect_macos(refresh=refresh)
    if platform_key == "linux":
        return collect_linux(refresh=refresh)
    if platform_key == "windows":
        return collect_windows(refresh=refresh)
    return parse_collect_result({}, {}, {"gateway": "", "interface": ""})


def display_width(value: object) -> int:
    width = 0
    for char in str(value):
        if unicodedata.combining(char):
            continue
        if unicodedata.category(char) == "Cf":
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


def pad_display(value: object, width: int) -> str:
    text = str(value)
    return text + (" " * max(width - display_width(text), 0))


def render_table(title: str, rows: list[dict], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return ""

    widths = []
    for key, label in columns:
        width = display_width(label)
        for row in rows:
            width = max(width, display_width(row.get(key, "")))
        widths.append(width)

    lines = [title]
    lines.append("  " + "  ".join(pad_display(label, widths[index]) for index, (_, label) in enumerate(columns)))
    for row in rows:
        lines.append(
            "  "
            + "  ".join(pad_display(row.get(key, ""), widths[index]) for index, (key, _) in enumerate(columns))
        )
    return "\n".join(lines)


def render_pairs(title: str, pairs: list[tuple[str, str]]) -> str:
    if not pairs:
        return ""

    width = max(display_width(label) for label, _ in pairs)
    lines = [title]
    for label, value in pairs:
        lines.append(f"  {pad_display(label, width)}  {value}")
    return "\n".join(lines)


def compact_interface_list(rows: list[dict]) -> str:
    if not rows:
        return ""

    items = [f"{row['iface']} {row['type']}" for row in rows]
    return textwrap.fill(
        ", ".join(items),
        width=88,
        initial_indent="  ",
        subsequent_indent="  ",
    )


def summary_visible(row: dict) -> bool:
    if row["state"] != "active":
        return False

    if row["type"] in {
        "AirDrop/Continuity",
        "Wi-Fi helper",
        "Loopback",
        "Hotspot helper",
        "Apple internal",
        "Legacy tunnel",
        "Container veth",
        "System",
    }:
        return False

    if row["type"] == "Tunnel/VPN":
        return row["ipv4"] != "-" or row["primary"]

    return True


def summary_group(row: dict) -> tuple[str, str, str]:
    if row.get("family") == "tunnel" or row["type"] == "Tunnel/VPN":
        return ("tunnel", "Tunnel / VPN", "tunnel/VPN")

    if row.get("family") == "virtual" or row["type"] in {"Bridge", "VM network"} or row["iface"].startswith(
        ("bridge", "vmenet", "vmnet", "vboxnet", "docker", "virbr")
    ):
        return ("virtual", "VM / Virtual", "vm/virtual")

    if row.get("family") == "physical" or row["type"] in {"Wi-Fi", "Ethernet", "Bluetooth"}:
        return ("physical", "Physical / Host", "physical")

    return ("other", "Other active", "other")


def group_summary_rows(rows: list[dict]) -> list[tuple[str, str, list[dict]]]:
    groups = [
        ("physical", "Physical / Host", "physical"),
        ("virtual", "VM / Virtual", "vm/virtual"),
        ("tunnel", "Tunnel / VPN", "tunnel/VPN"),
        ("other", "Other active", "other"),
    ]
    grouped = {key: [] for key, _, _ in groups}

    for row in rows:
        key, _, _ = summary_group(row)
        grouped[key].append(row)

    return [(label, count_label, grouped[key]) for key, label, count_label in groups if grouped[key]]


def summary_context(data: dict[str, object]) -> dict[str, object]:
    physical = data["physical"]
    system = data["system"]
    tunnels = data["tunnels"]
    active_rows = [row for row in [*physical, *system, *tunnels] if summary_visible(row)]

    return {
        "active_groups": group_summary_rows(active_rows),
        "inactive_physical": [row for row in physical if row["state"] != "active"],
        "hidden_system": [row for row in system if not summary_visible(row)],
        "hidden_tunnels": [row for row in tunnels if not summary_visible(row)],
    }


def interface_details(row: dict) -> list[tuple[str, str]]:
    details = [
        ("Interface", row["iface"]),
        ("Type", row["type"]),
        ("State", row["state"]),
        ("IPv4", row["ipv4"]),
    ]
    if row["subnet"]:
        details.append(("Subnet", row["subnet"]))
    if row["netmask"]:
        details.append(("Netmask", row["netmask"]))
    if row["gateway"]:
        details.append(("Gateway", row["gateway"]))
    if row["dns"]:
        details.append(("DNS", ", ".join(row["dns"])))
    if row["ipv6"] != "-":
        details.append(("IPv6", row["ipv6"]))
    details.append(("Current MAC", row["current_mac"]))
    if row["hardware_mac"] and row["hardware_mac"] != row["current_mac"]:
        details.append(("Hardware MAC", row["hardware_mac"]))
    if row["private_mac"]:
        details.append(("Private MAC", "enabled"))
    return details


def render_summary(data: dict[str, object]) -> str:
    primary = data["primary"]
    default_route = data["default_route"]
    context = summary_context(data)
    active_groups = context["active_groups"]

    lines = ["Network summary"]
    if primary:
        lines.append(f"  Primary       : {primary['iface']} ({primary['type']})")
    else:
        lines.append("  Primary       : unavailable")

    if default_route.get("interface") and default_route.get("gateway"):
        lines.append(f"  Default route : {default_route['interface']} -> {default_route['gateway']}")
    else:
        lines.append("  Default route : unavailable")

    if active_groups:
        counts = ", ".join(f"{len(rows)} {count_label}" for _, count_label, rows in active_groups)
        lines.append(f"  Active        : {counts}")
    else:
        lines.append("  Active        : none")

    for label, _, rows in active_groups:
        summary_rows = [
            {
                "iface": row["iface"],
                "type": row["type"],
                "ipv4": row["ipv4"],
                "mac": row["current_mac"],
                "subnet": row["subnet"] or "-",
            }
            for row in rows
        ]
        lines.append("")
        lines.append(
            render_table(
                label,
                summary_rows,
                [
                    ("iface", "IFACE"),
                    ("type", "TYPE"),
                    ("ipv4", "IPv4"),
                    ("mac", "MAC"),
                    ("subnet", "Subnet"),
                ],
            )
        )

    if not active_groups:
        lines.append("")
        lines.append("No active interfaces matched the default summary filter.")

    return "\n".join(lines)


def render_detail(data: dict[str, object]) -> str:
    primary = data["primary"]
    default_route = data["default_route"]
    context = summary_context(data)
    active_groups = context["active_groups"]
    inactive_physical = context["inactive_physical"]
    hidden_system = context["hidden_system"]
    hidden_tunnels = context["hidden_tunnels"]

    lines = ["Network summary"]
    if primary:
        lines.append(f"  Primary       : {primary['iface']} ({primary['type']})")
    else:
        lines.append("  Primary       : unavailable")

    if default_route.get("interface") and default_route.get("gateway"):
        lines.append(f"  Default route : {default_route['interface']} -> {default_route['gateway']}")
    else:
        lines.append("  Default route : unavailable")

    if active_groups:
        counts = ", ".join(f"{len(rows)} {count_label}" for _, count_label, rows in active_groups)
        lines.append(f"  Active        : {counts}")
    else:
        lines.append("  Active        : none")

    lines.append(
        f"  Hidden        : {len(hidden_system)} system helper, {len(hidden_tunnels)} tunnel/VPN, {len(inactive_physical)} inactive physical"
    )

    for label, _, rows in active_groups:
        summary_rows = [
            {
                "primary": "*" if row["primary"] else "",
                "iface": row["iface"],
                "type": row["type"],
                "state": row["state"],
                "ipv4": row["ipv4"],
                "mac": row["current_mac"],
            }
            for row in rows
        ]
        lines.append("")
        lines.append(
            render_table(
                f"Active {label}",
                summary_rows,
                [
                    ("primary", "PRI"),
                    ("iface", "IFACE"),
                    ("type", "TYPE"),
                    ("state", "STATE"),
                    ("ipv4", "IPv4"),
                    ("mac", "MAC"),
                ],
            )
        )

        lines.append("")
        lines.append(f"{label} details")
        for index, row in enumerate(rows):
            if index:
                lines.append("")
            title = f"Interface {row['iface']}"
            if row["primary"]:
                title += " (primary)"
            lines.append(render_pairs(title, interface_details(row)))

    if inactive_physical:
        lines.append("")
        lines.append("Other physical adapters")
        lines.append(compact_interface_list(inactive_physical))

    lines.append("")
    lines.append("Tip: use 'nic' for the compact summary, 'nic physical', 'nic all', 'nic show <iface>', or 'nic raw'.")
    return "\n".join(lines)


def render_physical(data: dict[str, object]) -> str:
    rows = [
        {
            "primary": "*" if row["primary"] else "",
            "iface": row["iface"],
            "type": row["type"],
            "state": row["state"],
            "ipv4": row["ipv4"],
            "mac": row["current_mac"],
        }
        for row in data["physical"]
    ]
    return render_table(
        "Physical adapters",
        rows,
        [
            ("primary", "PRI"),
            ("iface", "IFACE"),
            ("type", "TYPE"),
            ("state", "STATE"),
            ("ipv4", "IPv4"),
            ("mac", "MAC"),
        ],
    )


def render_all(data: dict[str, object]) -> str:
    lines = [render_physical(data)]

    if data["system"]:
        lines.append("")
        lines.append(
            render_table(
                "System interfaces",
                [
                    {
                        "iface": row["iface"],
                        "type": row["type"],
                        "state": row["state"],
                        "ipv4": row["ipv4"],
                        "mac": row["current_mac"],
                    }
                    for row in data["system"]
                ],
                [
                    ("iface", "IFACE"),
                    ("type", "TYPE"),
                    ("state", "STATE"),
                    ("ipv4", "IPv4"),
                    ("mac", "MAC"),
                ],
            )
        )

    if data["tunnels"]:
        lines.append("")
        lines.append(
            render_table(
                "Tunnel interfaces",
                [
                    {
                        "iface": row["iface"],
                        "type": row["type"],
                        "state": row["state"],
                        "ipv4": row["ipv4"],
                        "mac": row["current_mac"],
                    }
                    for row in data["tunnels"]
                ],
                [
                    ("iface", "IFACE"),
                    ("type", "TYPE"),
                    ("state", "STATE"),
                    ("ipv4", "IPv4"),
                    ("mac", "MAC"),
                ],
            )
        )

    return "\n".join(lines)


def render_interface(data: dict[str, object], interface_name: str) -> str:
    for group in ("physical", "system", "tunnels"):
        for row in data[group]:
            if row["iface"] != interface_name:
                continue
            return render_pairs(f"Interface {interface_name}", interface_details(row))

    return f"Interface '{interface_name}' not found."


def json_payload(data: dict[str, object]) -> dict[str, object]:
    return {
        "default_route": data["default_route"],
        "counts": {
            "physical": len(data["physical"]),
            "active_physical": len([row for row in data["physical"] if row["state"] == "active"]),
            "inactive_physical": len([row for row in data["physical"] if row["state"] != "active"]),
            "system": len(data["system"]),
            "tunnels": len(data["tunnels"]),
        },
        "primary": data["primary"],
        "physical": data["physical"],
        "system": data["system"],
        "tunnels": data["tunnels"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nic",
        description="Readable cross-platform network interface overview. Run without a subcommand for the compact active summary.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of formatted text.")
    parser.add_argument("--refresh", action="store_true", help="Refresh cached network metadata when supported.")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("summary", help="Alias for the compact active summary.")
    subparsers.add_parser("detail", help="Show the verbose active summary with per-interface details.")
    subparsers.add_parser("physical", help="Show all physical adapters.")
    subparsers.add_parser("all", help="Show physical, system, and tunnel interfaces.")
    subparsers.add_parser("raw", help="Run the platform-native raw network command.")
    subparsers.add_parser("json", help="Emit JSON output.")

    show_parser = subparsers.add_parser("show", help="Show detailed information for one interface.")
    show_parser.add_argument("interface", help="Interface name, for example en0, eth0, or Wi-Fi.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    command = args.command or "summary"
    if command == "raw":
        raw = raw_command()
        if not raw:
            print("Raw mode is unavailable on this platform.", file=sys.stderr)
            return 1
        return run_passthrough(raw)

    if command == "json":
        args.json = True

    data = collect(refresh=args.refresh)

    if command == "show":
        output = render_interface(data, args.interface)
        stream = sys.stderr if output.endswith("not found.") else sys.stdout
        print(output, file=stream)
        return 1 if stream is sys.stderr else 0

    if args.json:
        print(json.dumps(json_payload(data), indent=2, ensure_ascii=False))
        return 0

    if command == "physical":
        print(render_physical(data))
        return 0

    if command == "all":
        print(render_all(data))
        return 0

    if command == "detail":
        print(render_detail(data))
        return 0

    print(render_summary(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
