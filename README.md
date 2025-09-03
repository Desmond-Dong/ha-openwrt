
![OpenWrt Monitor - Home Assistant](https://img.shields.io/badge/OpenWrt%20Monitor-Home%20Assistant-blue?style=for-the-badge&logo=home-assistant)

# OpenWrt Monitor - Home Assistant 集成  [English](./README_EN.md)

**专为 [OpenWrt](https://openwrt.org/) 路由器设计的 Home Assistant 集成，基于 Ubus API，提供全面的系统监控功能。**  
**支持 _OpenWrt 版本 24.10+_**

![OpenWrt 24.10+](https://img.shields.io/badge/OpenWrt-24.10%2B-green?style=flat-square)
![Home Assistant 2025.8.0+](https://img.shields.io/badge/Home%20Assistant-2025.8.0%2B-blue?style=flat-square)
![License MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)


> 理论支持所有 OpenWrt 变体的版本或者第三方编译的版本
```bash 
# OpenWrt需要安装以下包,可以直接复制到命令行运行
opkg update
opkg install rpcd-mod-file uhttpd-mod-ubus rpcd-mod-iwinfo rpcd-mod-luci ubusd rpcd uhttpd-mod-ubus ucode-mod-ubus rpcd-mod-rpcsys
```
---

## ✨ 主要功能

| 🖥️ 系统信息 | 🌐 网络监控 | 📊 系统状态 | 🆕 24.10+ 新增功能 |
|:---|:---|:---|:---|
| 主机名、型号、架构、版本、发行版 | 网络接口状态、协议、运行时间、IP | 进程数、服务数、日志数、Ubus服务数 | LED状态、看门狗、系统升级、防火墙、DHCP租约、系统监控 |
| CPU核心数、负载（%） | 网络设备类型、状态、MTU |  |  |
| 内存总量/可用/缓存/缓冲/共享（MB） | 无线接口状态、模式 |  |  |
| 文件系统使用（MB） | DNS服务器配置 |  |  |
| 系统运行时间（s） |  |  |  |
| 系统温度（℃） |  |  |  |

---

## 🚀 安装方法


<summary>方法1: 手动安装</summary>

1. 下载整个 `openwrt_monitor` 文件夹
2. 放入 Home Assistant 配置目录下的 `custom_components/` 文件夹
3. 重启 Home Assistant
4. 在集成页面中添加 **OpenWrt Monitor**



<summary>方法2: HACS 一键安装</summary>



  [![OpenWrt Monitor](https://img.shields.io/badge/HACS-OpenWrt__Monitor-41BDF5?style=for-the-badge&logo=home-assistant&logoColor=white)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Desmond-Dong&repository=ha-openwrt&category=integration)

---

## ⚙️ 配置说明

<details>
<summary>基本配置项</summary>

- **Host**: OpenWrt 路由器的 IP 地址
- **Username**: 路由器用户名
- **Password**: 路由器密码
- **Scan Interval**: 数据更新间隔（10-300秒）

</details>

<details>
<summary>连接测试</summary>

集成会在配置时自动测试连接，确保能够成功连接到 OpenWrt 路由器。

</details>

---

## 🕹️ 控制按钮 (Button platform)

- 每个网络接口自动创建 `Restart <interface>` 按钮实体
- 全局 `Reboot System` 按钮实体

<details>
<summary>按钮说明</summary>

- **Restart 按钮**：依次尝试接口重启（down → up），多种回退方式（ifdown/ifup、`/sbin/wifi down|up`、`network.reload`）
- **Reboot Router 按钮**：优先使用 ubus 的 `system.reboot`，不可用时回退到 `/sbin/reboot` 或 `reboot` 命令

**实体名称示例：**
- `Restart radio0`
- `Reboot System`

**服务调用：**

| 服务 | service data 示例 |
|:---|:---|
| `ubus.restart_interface` | `{ "interface": "radio0" }` |
| `ubus.reboot_router` | `{}` |

</details>

---

## 🛠️ 技术特性

<details>
<summary>API 支持</summary>

- **Ubus API**：主要数据源，提供系统级信息
- **OpenWrt 24.10+ 优化**：支持最新 Ubus 接口
- **自动协议检测**：自动尝试 HTTPS 和 HTTP
- **SSL 证书处理**：忽略自签名证书错误
- **连接重试**：自动重试失败连接

</details>

<details>
<summary>数据处理</summary>

- **单位转换**：字节转 MB，负载转百分比
- **并行 API 调用**：提升效率
- **错误处理**：优雅处理 API 失败
- **数据缓存**：智能缓存减少请求

</details>

---

## 📋 系统要求

| 设备 | 要求 |
|:---|:---|
| **OpenWrt 路由器** | - OpenWrt 24.10 或更高版本<br>- 启用 Ubus 服务<br>- 网络访问权限 |
| **Home Assistant** | - Core 2025.8.0 或更高版本<br>- 支持自定义集成 |

---

## 🐛 故障排除

<details>
<summary>常见问题</summary>

- **1. 连接失败**
  - 检查路由器 IP 是否正确
  - 确认用户名和密码
  - 检查网络连接

- **2. 数据不完整**
  - 确认 Ubus 服务正在运行
  - 检查路由器权限设置
  - 查看 Home Assistant 日志

</details>

<details>
<summary>调试工具</summary>

使用 `debug_api.py` 脚本测试 API 连接：
