![OpenWrt Monitor - Home Assistant](https://img.shields.io/badge/OpenWrt%20Monitor-Home%20Assistant-blue?style=for-the-badge&logo=home-assistant)

# OpenWrt Monitor - Home Assistant Integration

**A Home Assistant integration designed for [OpenWrt](https://openwrt.org/) routers, based on the Ubus API, providing comprehensive system monitoring features.**  
**Supports _OpenWrt version 24.10+_**

![OpenWrt 24.10+](https://img.shields.io/badge/OpenWrt-24.10%2B-green?style=flat-square)
![Home Assistant 2025.8.0+](https://img.shields.io/badge/Home%20Assistant-2025.8.0%2B-blue?style=flat-square)
![License MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

> Theoretically supports all OpenWrt variants or third-party builds
```bash 
# The following packages need to be installed on OpenWrt. You can copy and run the commands directly in the terminal.
opkg update
opkg install rpcd-mod-file uhttpd-mod-ubus
```
---

## ✨ Main Features

| 🖥️ System Info | 🌐 Network Monitoring | 📊 System Status | 🆕 New in 24.10+ |
|:---|:---|:---|:---|
| Hostname, Model, Architecture, Version, Distribution | Network interface status, protocol, uptime, IP | Process count, service count, log count, Ubus service count | LED status, watchdog, system upgrade, firewall, DHCP leases, system monitoring |
| CPU cores, load (%) | Network device type, status, MTU |  |  |
| Total/available/cached/buffered/shared memory (MB) | Wireless interface status, mode |  |  |
| Filesystem usage (MB) | DNS server configuration |  |  |
| System uptime (seconds) |  |  |  |

---

## 🚀 Installation

<details>
<summary>Method 1: Manual Installation</summary>

1. Download the entire `openwrt_monitor` folder
2. Place it into the `custom_components/` folder under your Home Assistant config directory
3. Restart Home Assistant
4. Add **OpenWrt Monitor** from the Integrations page

</details>

<details>
<summary>Method 2: HACS Installation</summary>

1. Add this repository as a custom repository in HACS
2. Search for and install **OpenWrt Monitor**
3. Restart Home Assistant
4. Add **OpenWrt Monitor** from the Integrations page

</details>

---

## ⚙️ Configuration

<details>
<summary>Basic Options</summary>

- **Host**: IP address of your OpenWrt router
- **Username**: Router username
- **Password**: Router password
- **Scan Interval**: Data update interval (10-300 seconds)

</details>

<details>
<summary>Connection Test</summary>

The integration will automatically test the connection during setup to ensure it can connect to the OpenWrt router successfully.

</details>

---

## 🕹️ Control Buttons (Button platform)

- Automatically creates a `Restart <interface>` button entity for each network interface
- A global `Reboot System` button entity

<details>
<summary>Button Details</summary>

- **Restart Button**: Attempts to restart the interface in order (down → up), with multiple fallback methods (`ifdown/ifup`, `/sbin/wifi down|up`, `network.reload`)
- **Reboot Router Button**: Prefers ubus `system.reboot`, falls back to `/sbin/reboot` or `reboot` command if unavailable

**Example entity names:**
- `Restart radio0`
- `Reboot System`

**Service calls:**

| Service | Example service data |
|:---|:---|
| `ubus.restart_interface` | `{ "interface": "radio0" }` |
| `ubus.reboot_router` | `{}` |

</details>

---

## 🛠️ Technical Features

<details>
<summary>API Support</summary>

- **Ubus API**: Main data source, provides system-level information
- **Optimized for OpenWrt 24.10+**: Supports the latest Ubus interfaces
- **Automatic protocol detection**: Tries HTTPS and HTTP automatically
- **SSL certificate handling**: Ignores self-signed certificate errors
- **Connection retry**: Automatically retries failed connections

</details>

<details>
<summary>Data Processing</summary>

- **Unit conversion**: Bytes to MB, load to percentage
- **Parallel API calls**: Improves efficiency
- **Error handling**: Gracefully handles API failures
- **Data caching**: Smart caching to reduce requests

</details>

---

## 📋 System Requirements

| Device | Requirement |
|:---|:---|
| **OpenWrt Router** | - OpenWrt 24.10 or later<br>- Ubus service enabled<br>- Network access |
| **Home Assistant** | - Core 2025.8.0 or later<br>- Supports custom integrations |

---

## 🐛 Troubleshooting

<details>
<summary>Common Issues</summary>

- **1. Connection failed**
  - Check if the router IP is correct
  - Confirm username and password
  - Check network connectivity

- **2. Incomplete data**
  - Make sure the Ubus service is running
  - Check router permission settings
  - View Home Assistant logs

</details>

<details>
<summary>Debug Tools</summary>

Use the `debug_api.py` script to test API connectivity:
