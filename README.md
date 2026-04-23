[中文](README.zh-CN.md) | English

# nic

Minimal network interface CLI for macOS, Linux, and Windows.

`nic` is built for the common case: you want to see the interfaces that are actually working right now, not pages of raw `ifconfig` or `ipconfig` output.

## Why nic

- Active-first default view
  `nic` hides inactive and helper noise in the default summary.
- Grouped by role
  Interfaces are grouped into `Physical / Host`, `VM / Virtual`, and `Tunnel / VPN`.
- Key fields only
  Default output shows `IFACE`, `TYPE`, `IPv4`, `MAC`, and `Subnet`.
- Detail on demand
  Use `nic detail` or `nic show <iface>` when you need the verbose view.
- Cross-platform
  The same CLI works on macOS, Linux, and Windows.
- Native collection
  `nic` uses built-in OS tools instead of third-party runtime dependencies.

## Install

Recommended:

```bash
pip install nic-cli
```

If `pip` is not on your PATH, use `python -m pip install nic-cli` or `python3 -m pip install nic-cli`.

Current release:

- PyPI: https://pypi.org/project/nic-cli/
- GitHub Release: https://github.com/Kidder1/nic/releases/tag/v0.1.4

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

## Default view

```text
Network summary
  Primary       : Ethernet (Ethernet)
  Default route : Ethernet -> 192.168.5.1
  Active        : 1 physical, 2 vm/virtual

Physical / Host
  IFACE     TYPE      IPv4            MAC                Subnet
  Ethernet  Ethernet  192.168.5.12/24 e0:be:03:97:aa:b4 192.168.5.0/24

VM / Virtual
  IFACE   TYPE        IPv4              MAC                Subnet
  VMnet1  VM network  192.168.159.1/24  00:50:56:c0:00:01  192.168.159.0/24
  VMnet8  VM network  192.168.206.1/24  00:50:56:c0:00:08  192.168.206.0/24
```

The compact summary only shows active, meaningful interfaces. For the expanded multi-interface view, use `nic detail`.

## Commands

- `nic`
  Compact summary of active interfaces only.
- `nic detail`
  Grouped verbose view with per-interface details.
- `nic physical`
  All physical adapters on the current machine.
- `nic all`
  Full inventory, including system and helper interfaces.
- `nic show <iface>`
  Detailed view for one interface.
- `nic --json`
  Machine-readable payload.
- `nic raw`
  Native raw network command for the current platform.

## Platform Notes

- macOS
  Uses `ifconfig -a`, `netstat -rn -f inet`, and cached `system_profiler SPNetworkDataType -json`.
- Linux
  Uses `ip -j addr`, `ip -j route`, and `/etc/resolv.conf`, with text fallback when JSON output is unavailable.
- Windows
  Uses `ipconfig /all`, `route print -4`, and `getmac /v /fo csv` when available.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 -m nic --help
```

Version history is in [CHANGELOG.md](CHANGELOG.md).

## License

MIT
