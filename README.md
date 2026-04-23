English | [中文](README.zh-CN.md)

# nic

[![Release](https://img.shields.io/github/v/release/Kidder1/nic)](https://github.com/Kidder1/nic/releases)
[![CI](https://github.com/Kidder1/nic/actions/workflows/ci.yml/badge.svg)](https://github.com/Kidder1/nic/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/Kidder1/nic)](LICENSE)

`nic` is a cross-platform CLI that turns native network tooling into a compact interface view you can scan quickly.

It keeps the default output focused on the active interfaces that matter right now: physical adapters, VM or virtual networks, and VPN or tunnel interfaces. Detailed per-interface data is still available when you explicitly ask for it.

## Features

- compact default summary for active interfaces only
- grouped tables for `Physical / Host`, `VM / Virtual`, and `Tunnel / VPN`
- `detail`, `physical`, `all`, `show <iface>`, and `--json` modes
- platform-native collection on macOS, Linux, and Windows
- stable output shape with graceful fallback when a field is unavailable
- no third-party runtime dependencies

## Platform Support

- macOS
  Uses `ifconfig -a`, `netstat -rn -f inet`, and cached `system_profiler SPNetworkDataType -json`.
- Linux
  Uses `ip -j addr`, `ip -j route`, and `/etc/resolv.conf`, with text-command fallback when JSON output is unavailable.
- Windows
  Uses `ipconfig /all`, `route print -4`, and `getmac /v /fo csv` when available.

`nic raw` runs the native raw command for the current platform:

- macOS: `ifconfig -a`
- Linux: `ip addr`
- Windows: `ipconfig /all`

## Install

Latest release:

- Release page: https://github.com/Kidder1/nic/releases/tag/v0.1.1
- Wheel: `nic_cli-0.1.1-py3-none-any.whl`

### Option 1: install from GitHub Release

Recommended for normal users.

macOS / Linux:

```bash
python3 -m pip install --upgrade https://github.com/Kidder1/nic/releases/download/v0.1.1/nic_cli-0.1.1-py3-none-any.whl
```

Windows:

```powershell
python -m pip install --upgrade https://github.com/Kidder1/nic/releases/download/v0.1.1/nic_cli-0.1.1-py3-none-any.whl
```

### Option 2: pip install from source

Works on macOS, Linux, and Windows.

```bash
git clone https://github.com/<your-name>/nic.git
cd nic
python3 -m pip install .
```

On Windows, use `python -m pip install .` if `python3` is not available.

## Releases

`nic` is a pure Python CLI, so the best release format is not per-platform binaries.
Each GitHub release publishes:

- a source tarball
- a universal wheel: `py3-none-any.whl`

The same wheel works on macOS, Linux, and Windows as long as the target machine has a supported Python version.

Version history is also tracked in [CHANGELOG.md](CHANGELOG.md).

### Option 3: local launcher

For macOS and Linux shells, you can install the repo launcher into `~/.local/bin`:

```bash
git clone https://github.com/<your-name>/nic.git
cd nic
./scripts/install.sh
```

## Usage

```bash
nic
nic detail
nic physical
nic all
nic show en0
nic --json
nic raw
```

## Commands

- `nic`
  Compact grouped summary of active interfaces with `IFACE`, `TYPE`, `IPv4`, `MAC`, and `Subnet`.
- `nic detail`
  Verbose active summary with per-interface detail sections.
- `nic physical`
  All physical adapters on the current platform.
- `nic all`
  Full inventory of physical, system or virtual, and tunnel interfaces.
- `nic show <iface>`
  Detailed view for one interface.
- `nic --json`
  Machine-readable JSON payload.
- `nic raw`
  Native raw network command for the current platform.
- `nic --refresh`
  Refreshes cached metadata when the platform supports it. Today this mainly affects macOS.

## Example

```text
Network summary
  Primary       : en0 (Wi-Fi)
  Default route : en0 -> 172.17.6.1
  Active        : 1 physical, 3 vm/virtual, 1 tunnel/VPN

Physical / Host
  IFACE  TYPE   IPv4             MAC                Subnet
  en0    Wi-Fi  172.17.6.246/23  5a:41:83:8a:50:40  172.17.6.0/23

VM / Virtual
  IFACE      TYPE        IPv4            MAC                Subnet
  bridge100  Bridge      10.211.55.2/24  be:d0:74:73:20:64  10.211.55.0/24
  bridge101  Bridge      10.37.129.2/24  be:d0:74:73:20:65  10.37.129.0/24
  vmenet1    VM network  -               ce:8a:fb:1c:07:34  -

Tunnel / VPN
  IFACE  TYPE        IPv4           MAC  Subnet
  utun4  Tunnel/VPN  198.18.0.1/30  -    198.18.0.0/30
```

## Notes

- The default view is optimized for human scanning, not full completeness.
- Interface names and adapter labels vary by platform.
- Some fields such as hardware MAC, DNS, or gateway may be unavailable on certain systems; `nic` degrades gracefully.
- macOS can show different current and hardware MAC addresses when Private Wi-Fi Address is enabled.

## Local Development

```bash
python3 -m unittest discover -s tests -v
python3 -m nic --help
```

## License

MIT
