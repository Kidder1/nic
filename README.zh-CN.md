[English](README.md) | 中文

# nic

`nic` 是一个跨平台网络接口 CLI，用系统自带命令收集网卡信息，然后整理成适合快速查看的紧凑视图。

默认输出只关注当前真正有意义的激活接口：物理网卡、虚拟机或虚拟网络接口、VPN 或隧道接口。只有在你明确需要时，才进入详细的逐接口信息展示。

## 特性

- 默认输出是紧凑版 active 网卡摘要
- 按 `Physical / Host`、`VM / Virtual`、`Tunnel / VPN` 分组表格展示
- 提供 `detail`、`physical`、`all`、`show <iface>`、`--json` 等模式
- 支持 macOS、Linux、Windows 三个平台
- 字段缺失时稳定降级，不因为平台不同改变输出结构
- 无第三方运行时依赖

## 平台支持

- macOS
  使用 `ifconfig -a`、`netstat -rn -f inet` 和缓存后的 `system_profiler SPNetworkDataType -json`
- Linux
  使用 `ip -j addr`、`ip -j route`、`/etc/resolv.conf`，如果 JSON 输出不可用则回退到文本命令解析
- Windows
  使用 `ipconfig /all`、`route print -4`，并在可用时补充 `getmac /v /fo csv`

`nic raw` 会按平台直接输出原生命令结果：

- macOS：`ifconfig -a`
- Linux：`ip addr`
- Windows：`ipconfig /all`

## 安装

### 方式 1：pip 安装

适用于 macOS、Linux、Windows。

```bash
git clone https://github.com/<your-name>/nic.git
cd nic
python3 -m pip install .
```

如果在 Windows 上没有 `python3`，请改用：

```bash
python -m pip install .
```

## Release 打包方式

`nic` 是纯 Python CLI，所以最合适的发布方式不是分别做三平台二进制。
每个 GitHub Release 会发布：

- 源码包
- 通用 wheel：`py3-none-any.whl`

也就是说，只要目标机器的 Python 版本受支持，同一个 wheel 就能在 macOS、Linux、Windows 上安装使用。

### 方式 2：本地启动脚本

适用于 macOS 和 Linux shell：

```bash
git clone https://github.com/<your-name>/nic.git
cd nic
./scripts/install.sh
```

这会把仓库里的 `nic` 启动脚本链接到 `~/.local/bin/nic`。

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

## 命令说明

- `nic`
  默认紧凑摘要，只显示当前 active 且有意义的接口，列为 `IFACE`、`TYPE`、`IPv4`、`MAC`、`Subnet`
- `nic detail`
  详细模式，保留分组并展开每个接口的详细信息
- `nic physical`
  查看当前平台上的所有物理网卡
- `nic all`
  查看完整接口清单，包括物理、系统或虚拟、隧道接口
- `nic show <iface>`
  查看单个接口的详细信息
- `nic --json`
  输出机器可读 JSON
- `nic raw`
  直接运行当前平台的原生命令
- `nic --refresh`
  刷新缓存的元数据；目前主要对 macOS 生效

## 示例

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

## 说明

- 默认视图强调“快速扫一眼”，不是完整调试信息。
- 不同平台的接口名称和适配器标签差异很大。
- 某些字段如硬件 MAC、DNS、网关在部分系统上可能拿不到，`nic` 会自动降级。
- 在 macOS 上开启 Private Wi‑Fi Address 时，当前 MAC 和硬件 MAC 可能不同。

## 本地开发

```bash
python3 -m unittest discover -s tests -v
python3 -m nic --help
```

## 许可证

MIT
