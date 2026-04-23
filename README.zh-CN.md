中文 | [English](README.md)

# nic

一个简洁的跨平台网卡查看 CLI，适合快速看当前真正工作的网卡。

`nic` 默认不是把系统所有网络细节都堆出来，而是让你一眼看到现在在工作的接口、它们属于什么类别，以及最关键的 IP、MAC、子网信息。

## 这个工具的特点

- 默认只看 active 网卡
  会隐藏 inactive 接口和一堆 helper/system 噪音。
- 自动分组
  默认按 `Physical / Host`、`VM / Virtual`、`Tunnel / VPN` 展示。
- 只保留关键信息
  默认列只有 `IFACE`、`TYPE`、`IPv4`、`MAC`、`Subnet`。
- 详细信息按需看
  需要展开时再用 `nic detail` 或 `nic show <iface>`。
- 真正跨平台
  macOS、Linux、Windows 共用同一套命令。
- 不引入运行时依赖
  直接调用系统原生命令采集信息。

## 安装

推荐直接用 PyPI：

```bash
pip install nic-cli
```

如果你的环境里 `pip` 不在 PATH，可以改用 `python -m pip install nic-cli` 或 `python3 -m pip install nic-cli`。

当前发布地址：

- PyPI：https://pypi.org/project/nic-cli/
- GitHub Release：https://github.com/Kidder1/nic/releases/tag/v0.1.3

## 用法

```bash
nic
nic detail
nic physical
nic all
nic show en0
nic --json
nic raw
```

## 默认输出长这样

```text
Network summary
  Primary       : 以太网 (Ethernet)
  Default route : 以太网 -> 192.168.5.1
  Active        : 1 physical, 2 vm/virtual

Physical / Host
  IFACE   TYPE      IPv4            MAC                Subnet
  以太网  Ethernet  192.168.5.12/24 e0:be:03:97:aa:b4 192.168.5.0/24

VM / Virtual
  IFACE   TYPE        IPv4              MAC                Subnet
  VMnet1  VM network  192.168.159.1/24  00:50:56:c0:00:01  192.168.159.0/24
  VMnet8  VM network  192.168.206.1/24  00:50:56:c0:00:08  192.168.206.0/24
```

默认紧凑视图只显示 active 且有意义的接口；如果你想看逐接口展开详情，用 `nic detail`。

## 命令说明

- `nic`
  默认紧凑摘要，只显示当前 active 的关键接口。
- `nic detail`
  分组详细视图，带逐接口详情。
- `nic physical`
  查看当前机器上的所有物理网卡。
- `nic all`
  查看完整接口清单，包括 system/helper 接口。
- `nic show <iface>`
  查看单个接口的详细信息。
- `nic --json`
  输出机器可读 JSON。
- `nic raw`
  直接运行当前平台的原生命令。

## 平台说明

- macOS
  使用 `ifconfig -a`、`netstat -rn -f inet` 和缓存后的 `system_profiler SPNetworkDataType -json`。
- Linux
  使用 `ip -j addr`、`ip -j route`、`/etc/resolv.conf`，JSON 不可用时回退到文本命令解析。
- Windows
  使用 `ipconfig /all`、`route print -4`，并在可用时补充 `getmac /v /fo csv`。

## 开发

```bash
python3 -m unittest discover -s tests -v
python3 -m nic --help
```

版本历史见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

MIT
