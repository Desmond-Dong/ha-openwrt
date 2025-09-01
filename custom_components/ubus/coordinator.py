import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
import aiohttp
import asyncio
import ssl

_LOGGER = logging.getLogger(__name__)

# 某些 ubus 方法在不同固件/版本上并非必定存在，这些调用失败不应每次都写 WARNING
OPTIONAL_UBUS_METHODS = {
    ("dhcp", "leases"),
    ("dhcp", "get_leases"),
    ("dnsmasq", "leases"),
    ("dnsmasq", "get_leases"),
    ("odhcpd", "leases"),
    ("network.wireless", "status"),
}

class OpenWrtDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.host = entry.data[CONF_HOST]
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]
        self.session_id = None
        self.entry = entry
        
        # 创建SSL上下文，忽略自签名证书错误
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # 创建连接器，支持HTTP和HTTPS
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self._session = aiohttp.ClientSession(connector=connector)
        
        self._previous_data = {}  # 用于计算速率
        update_interval = timedelta(seconds=entry.data.get(CONF_SCAN_INTERVAL, 30))

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _login(self):
        """登录OpenWrt并获取session"""
        try:
            # 尝试HTTPS Ubus登录
            if await self._try_ubus_login("https"):
                return
            
            # 如果HTTPS失败，尝试HTTP Ubus登录
            if await self._try_ubus_login("http"):
                return
                
        except Exception as e:
            _LOGGER.error("Ubus登录失败: %s", e)
            raise

    async def _try_ubus_login(self, protocol):
        """尝试指定协议的Ubus登录"""
        try:
            url = f"{protocol}://{self.host}/ubus"
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "call",
                "params": [
                    "00000000000000000000000000000000",
                    "session",
                    "login",
                    {
                        "username": self.username,
                        "password": self.password
                    }
                ]
            }
            
            _LOGGER.info("尝试 %s Ubus登录: %s", protocol.upper(), url)
            
            async with self._session.post(url, json=payload, timeout=10) as resp:
                if resp.status != 200:
                    _LOGGER.warning("%s Ubus登录失败，状态码: %s", protocol.upper(), resp.status)
                    return False
                data = await resp.json()
                if "result" in data and len(data["result"]) > 1:
                    self.session_id = data["result"][1]["ubus_rpc_session"]
                    _LOGGER.info("%s Ubus登录成功", protocol.upper())
                    return True
                else:
                    _LOGGER.warning("%s Ubus登录响应无效", protocol.upper())
                    return False
        except Exception as e:
            _LOGGER.warning("%s Ubus登录异常: %s", protocol.upper(), e)
            return False

    async def _ubus_call(self, namespace, method, params=None):
        """调用OpenWrt Ubus API"""
        if not self.session_id:
            await self._login()
        
        # 尝试HTTPS和HTTP
        for protocol in ["https", "http"]:
            try:
                url = f"{protocol}://{self.host}/ubus"
                payload = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "call",
                    "params": [
                        self.session_id,
                        namespace,
                        method,
                        params or {}
                    ]
                }
                
                async with self._session.post(url, json=payload, timeout=10) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    if "result" in data and len(data["result"]) > 1:
                        return data["result"][1]
                    else:
                        continue
            except Exception as e:
                _LOGGER.debug("Ubus调用失败 %s.%s via %s: %s", namespace, method, protocol, e)
                continue
        
        # 对于可选的 ubus 方法，使用 DEBUG 级别以避免日志噪音；其它情况保留 WARNING
        # 把 Ubus 调用失败都记录为 DEBUG（避免在正常运行时刷屏），只有在需要时开启 debug 日志查看详情
        # 动态的 hostapd 对象（如 hostapd.phy0-ap0）调用 get_clients 也视为可选
        if isinstance(namespace, str) and namespace.startswith("hostapd.") and method == "get_clients":
            _LOGGER.debug("可选 Ubus 方法不可用 %s.%s", namespace, method)
        else:
            _LOGGER.debug("Ubus调用失败 %s.%s", namespace, method)
        return None

    def _convert_bytes_to_mb(self, bytes_value):
        """将字节转换为MB"""
        if bytes_value is None:
            return 0
        return round(bytes_value / (1024 * 1024), 2)

    def _calculate_cpu_load_percentage(self, load_value):
        """将CPU负载转换为百分比"""
        if load_value is None:
            return 0
        # OpenWrt 24.10+ 的负载值通常是整数，需要转换为百分比
        # 根据实际测试调整最大负载值
        max_load = 100000
        percentage = min((load_value / max_load) * 100, 100)
        return round(percentage, 2)

    def _get_cpu_count_from_system_info(self, system_info):
        """从系统信息中获取CPU核心数"""
        if not system_info:
            return 1
        
        # 尝试从不同字段获取CPU信息
        if "cpu" in system_info:
            cpu_info = system_info["cpu"]
            if isinstance(cpu_info, list):
                return len(cpu_info)
            elif isinstance(cpu_info, dict) and "count" in cpu_info:
                return cpu_info["count"]
        
        # 从system字段推断
        if "system" in system_info:
            system_str = system_info["system"]
            if "ARMv7" in system_str:
                return 2  # ARMv7通常是双核
            elif "ARMv8" in system_str or "aarch64" in system_str:
                return 4  # ARMv8通常是四核
            elif "x86_64" in system_str:
                return 4  # x86_64通常是四核或更多
            elif "mips" in system_str:
                return 2  # MIPS通常是双核
        
        return 1

    async def _async_update_data(self):
        """更新数据 - 针对OpenWrt 24.10+优化"""
        try:
            # 并行调用多个Ubus API - OpenWrt 24.10+支持的接口
            tasks = [
                # 系统信息
                self._ubus_call("system", "board"),
                self._ubus_call("system", "info"),
                self._ubus_call("system", "processes"),
                self._ubus_call("system", "uptime"),
                self._ubus_call("system", "load"),
                self._ubus_call("system", "memory"),
                self._ubus_call("system", "swap"),
                self._ubus_call("system", "cpu"),
                
                # 网络信息
                self._ubus_call("network.interface", "dump"),
                self._ubus_call("network.device", "status"),
                self._ubus_call("network.wireless", "status"),
                self._ubus_call("network", "status"),
                
                # 服务信息
                self._ubus_call("service", "list"),
                self._ubus_call("service", "running"),
                
                # 系统状态
                self._ubus_call("log", "read"),
                self._ubus_call("ubus", "list"),
                
                # OpenWrt 24.10+ 新增接口
                self._ubus_call("system", "led"),
                self._ubus_call("system", "watchdog"),
                self._ubus_call("system", "sysupgrade"),
                self._ubus_call("system", "upgrade"),
                
                # 网络高级功能
                self._ubus_call("network", "dump"),
                self._ubus_call("network", "reload"),
                self._ubus_call("network.interface", "status"),
                self._ubus_call("network.device", "dump"),
                
                # 防火墙和DHCP
                self._ubus_call("firewall", "status"),
                self._ubus_call("firewall", "dump"),
                self._ubus_call("dhcp", "status"),
                self._ubus_call("dhcp", "leases"),
                
                # 无线高级功能
                self._ubus_call("network.wireless", "dump"),
                self._ubus_call("network.wireless", "reload"),
                
                # 系统监控
                self._ubus_call("system", "monitor"),
                self._ubus_call("system", "stats"),
            
                # 尝试获取 UCI 中的 wireless 配置（用于获取 SSID/mode 等静态配置）
                self._ubus_call("uci", "get_all", {"config": "wireless"}),
                self._ubus_call("uci", "get", {"config": "wireless"}),
                self._ubus_call("uci", "show", {"package": "wireless"}),
                # LuCI RPC: 获取 DHCP 租约清单（用于更可靠的租约列表）
                self._ubus_call("luci-rpc", "getDHCPLeases"),
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            data = {}
            
            # system.board
            if isinstance(results[0], dict):
                data["system_board"] = results[0]
            else:
                data["system_board"] = {}
            
            # system.info
            if isinstance(results[1], dict):
                data["system_info"] = results[1]
                # 处理内存数据，转换为MB
                if "memory" in results[1]:
                    memory = results[1]["memory"]
                    data["memory"] = {
                        "total_mb": self._convert_bytes_to_mb(memory.get("total", 0)),
                        "free_mb": self._convert_bytes_to_mb(memory.get("free", 0)),
                        "shared_mb": self._convert_bytes_to_mb(memory.get("shared", 0)),
                        "buffered_mb": self._convert_bytes_to_mb(memory.get("buffered", 0)),
                        "available_mb": self._convert_bytes_to_mb(memory.get("available", 0)),
                        "cached_mb": self._convert_bytes_to_mb(memory.get("cached", 0))
                    }
                
                # 处理CPU负载，转换为百分比
                if "load" in results[1]:
                    load = results[1]["load"]
                    data["load"] = [
                        self._calculate_cpu_load_percentage(load[0]) if len(load) > 0 else 0,
                        self._calculate_cpu_load_percentage(load[1]) if len(load) > 1 else 0,
                        self._calculate_cpu_load_percentage(load[2]) if len(load) > 2 else 0
                    ]
                
                # 处理运行时间
                if "uptime" in results[1]:
                    data["uptime"] = {
                        "seconds": results[1]["uptime"]
                    }
                
                # 处理根文件系统
                if "root" in results[1]:
                    data["rootfs"] = results[1]["root"]
                
                # 处理临时文件系统
                if "tmp" in results[1]:
                    data["tmpfs"] = results[1]["tmp"]
                
                # 处理交换分区
                if "swap" in results[1]:
                    data["swap"] = results[1]["swap"]
            else:
                data["system_info"] = {}
                data["memory"] = {}
                data["load"] = [0, 0, 0]
                data["uptime"] = {"seconds": 0}
                data["rootfs"] = {}
                data["tmpfs"] = {}
                data["swap"] = {}
            
            # system.processes
            if isinstance(results[2], dict):
                data["processes"] = results[2]
            else:
                data["processes"] = {}
            
            # system.uptime
            if isinstance(results[3], dict):
                data["system_uptime"] = results[3]
            else:
                data["system_uptime"] = {}
            
            # system.load
            if isinstance(results[4], dict):
                data["system_load"] = results[4]
            else:
                data["system_load"] = {}
            
            # system.memory
            if isinstance(results[5], dict):
                data["system_memory"] = results[5]
            else:
                data["system_memory"] = {}
            
            # system.swap
            if isinstance(results[6], dict):
                data["system_swap"] = results[6]
            else:
                data["system_swap"] = {}
            
            # system.cpu
            if isinstance(results[7], dict):
                data["system_cpu"] = results[7]
            else:
                data["system_cpu"] = {}
            
            # network.interface.dump
            if isinstance(results[8], dict) and "interface" in results[8]:
                data["interfaces"] = {}
                for iface in results[8]["interface"]:
                    iface_name = iface.get("interface", "unknown")
                    data["interfaces"][iface_name] = iface
            else:
                data["interfaces"] = {}
            
            # network.device.status
            if isinstance(results[9], dict):
                data["devices"] = results[9]
            else:
                data["devices"] = {}
            
            # network.wireless.status
            if isinstance(results[10], dict):
                data["wireless"] = results[10]
            else:
                data["wireless"] = {}
            
            # network.status
            if isinstance(results[11], dict):
                data["network_status"] = results[11]
            else:
                data["network_status"] = {}
            
            # service.list
            if isinstance(results[12], dict):
                data["services"] = results[12]
            else:
                data["services"] = {}
            
            # service.running
            if isinstance(results[13], dict):
                data["running_services"] = results[13]
            else:
                data["running_services"] = {}
            
            # log.read
            if isinstance(results[14], dict):
                data["logs"] = results[14]
            else:
                data["logs"] = {}
            
            # ubus.list
            if isinstance(results[15], dict):
                data["ubus_services"] = results[15]
            else:
                data["ubus_services"] = {}
            
            # OpenWrt 24.10+ 新增功能
            # system.led
            if isinstance(results[16], dict):
                data["leds"] = results[16]
            else:
                data["leds"] = {}
            
            # system.watchdog
            if isinstance(results[17], dict):
                data["watchdog"] = results[17]
            else:
                data["watchdog"] = {}
            
            # system.sysupgrade
            if isinstance(results[18], dict):
                data["sysupgrade"] = results[18]
            else:
                data["sysupgrade"] = {}
            
            # system.upgrade
            if isinstance(results[19], dict):
                data["upgrade"] = results[19]
            else:
                data["upgrade"] = {}
            
            # network.dump
            if isinstance(results[20], dict):
                data["network_dump"] = results[20]
            else:
                data["network_dump"] = {}
            
            # network.reload
            if isinstance(results[21], dict):
                data["network_reload"] = results[21]
            else:
                data["network_reload"] = {}
            
            # network.interface.status
            if isinstance(results[22], dict):
                data["interface_status"] = results[22]
            else:
                data["interface_status"] = {}
            
            # network.device.dump
            if isinstance(results[23], dict):
                data["device_dump"] = results[23]
            else:
                data["device_dump"] = {}
            
            # firewall.status
            if isinstance(results[24], dict):
                data["firewall_status"] = results[24]
            else:
                data["firewall_status"] = {}
            
            # firewall.dump
            if isinstance(results[25], dict):
                data["firewall_dump"] = results[25]
            else:
                data["firewall_dump"] = {}
            
            # dhcp.status
            if isinstance(results[26], dict):
                data["dhcp_status"] = results[26]
            else:
                data["dhcp_status"] = {}
            
            # dhcp.leases
            if isinstance(results[27], dict):
                data["dhcp_leases"] = results[27]
            else:
                data["dhcp_leases"] = {}
            
            # network.wireless.dump
            if isinstance(results[28], dict):
                data["wireless_dump"] = results[28]
            else:
                data["wireless_dump"] = {}
            
            # network.wireless.reload
            if isinstance(results[29], dict):
                data["wireless_reload"] = results[29]
            else:
                data["wireless_reload"] = {}
            
            # system.monitor
            if isinstance(results[30], dict):
                data["system_monitor"] = results[30]
            else:
                data["system_monitor"] = {}
            
            # system.stats
            if isinstance(results[31], dict):
                data["system_stats"] = results[31]
            else:
                data["system_stats"] = {}

            # 解析可能存在的 UCI wireless 配置（不依赖固定索引）
            try:
                wireless_config = {}
                for res in results:
                    if not isinstance(res, dict):
                        continue
                    # UCI 风格调用通常返回包含 'values' 的字典
                    values = res.get("values") if isinstance(res.get("values"), dict) else None
                    if not values:
                        continue

                    # 判断是否包含 wifi-device / wifi-iface 条目
                    has_wifi = False
                    for k, v in values.items():
                        if isinstance(v, dict) and v.get(".type") in ("wifi-device", "wifi-iface"):
                            has_wifi = True
                            break
                    if not has_wifi:
                        continue

                    # 将 values 中的 wifi 配置合并到 wireless_config
                    for name, entry in values.items():
                        if not isinstance(entry, dict):
                            continue
                        wireless_config[name] = entry

                if wireless_config:
                    data["wireless_config"] = wireless_config

                    # 将 wifi-iface 条目映射到一个便捷的 by_name 索引
                    data.setdefault("wireless_by_ifname", {})
                    for name, entry in wireless_config.items():
                        t = entry.get(".type")
                        if t == "wifi-iface":
                            # 可能的字段: device (radioX), ssid, mode, encryption
                            dev = entry.get("device")
                            ssid = entry.get("ssid")
                            data["wireless_by_ifname"][name] = {
                                "name": name,
                                "device": dev,
                                "ssid": ssid,
                                **entry,
                            }

            except Exception:
                # 不影响主流程
                pass
            
            # 计算CPU核心数
            data["cpu_count"] = self._get_cpu_count_from_system_info(data.get("system_board", {}))
            
            # 如果 wireless 为空但 wireless_dump 有数据，尝试合并以提供无线信息
            if not data.get("wireless") and data.get("wireless_dump"):
                # 某些路由器将详细无线信息放在 dump 中，这里做一次简单合并
                data["wireless"] = data.get("wireless_dump", {})

            # 规范化 wireless 结构，保证每个 radio 对应 dict 且包含 interfaces 列表
            try:
                wireless_raw = data.get("wireless") or {}
                wired = {}
                if isinstance(wireless_raw, dict):
                    for radio, radio_data in wireless_raw.items():
                        # radio_data 可能为 dict 或 list，处理常见情况
                        interfaces = []
                        if isinstance(radio_data, dict):
                            if "interfaces" in radio_data and isinstance(radio_data["interfaces"], list):
                                interfaces = radio_data["interfaces"]
                            else:
                                # 有些固件直接把接口信息放在 radio_data 本身
                                # 检查字段 ifname 或 name
                                if "ifname" in radio_data or "name" in radio_data:
                                    interfaces = [radio_data]
                                else:
                                    # 尝试把 dict 的 values 转为列表形式
                                    for v in radio_data.values():
                                        if isinstance(v, dict) and ("ifname" in v or "up" in v or "mode" in v):
                                            interfaces.append(v)
                        elif isinstance(radio_data, list):
                            interfaces = radio_data

                        # 清理 interfaces 中的键，确保每项是 dict
                        cleaned = [i for i in interfaces if isinstance(i, dict)]
                        if cleaned:
                            wired[radio] = {"interfaces": cleaned}

                # 使用规范化后的结构替换
                if wired:
                    data["wireless"] = wired

            except Exception:
                # 保守降级，不中断主流程
                pass

            # 构建按 ifname 的快速索引，方便 platform 使用真实接口名（匹配 LuCI）
            data["wireless_by_ifname"] = {}
            try:
                for radio, radio_data in (data.get("wireless") or {}).items():
                    for iface in radio_data.get("interfaces", []):
                        if not isinstance(iface, dict):
                            continue
                        ifname = iface.get("ifname") or iface.get("name") or iface.get("device")
                        if not ifname:
                            # 有时接口名放在 "ifname" 内嵌或为 key，尽量尝试其他字段
                            continue
                        data["wireless_by_ifname"][ifname] = {**iface, "radio": radio}
            except Exception:
                pass

            # 尝试通过 hostapd 获取实时连接客户端（优先）
            data["clients"] = {}
            try:
                # 根据 wireless_config 中的 wifi-iface 推断 hostapd 对象名
                wireless_cfg = data.get("wireless_config") or {}
                hostapd_objs = set()
                for name, entry in wireless_cfg.items():
                    if entry.get(".type") != "wifi-iface":
                        continue
                    dev = entry.get("device") or ""
                    # 常见映射: radio0 -> phy0 -> hostapd.phy0-ap0
                    idx = None
                    if dev.startswith("radio") and dev[5:].isdigit():
                        idx = dev[5:]
                    if idx is not None:
                        hostapd_objs.add(f"hostapd.phy{idx}-ap0")
                        hostapd_objs.add(f"hostapd.phy{idx}")
                    # 也尝试直接使用 device 名
                    if dev:
                        hostapd_objs.add(f"hostapd.{dev}")

                # 如果 ubus 的 hostapd 顶层存在，尝试该对象
                for obj in list(hostapd_objs):
                    try:
                        res = await self._ubus_call(obj, "get_clients")
                        if res and isinstance(res, dict):
                            clients = res.get("clients") or res.get("stations") or res.get("clients_list") or []
                            # 将 client 列表分配到所有相关 iface names（保守做法）
                            name_key = obj.split(".", 1)[-1]
                            data["clients"][name_key] = clients
                    except Exception:
                        continue
            except Exception:
                pass

            # 汇总客户端数量
            total_clients = 0
            try:
                for k, v in data.get("clients", {}).items():
                    if isinstance(v, list):
                        total_clients += len(v)
                data["clients_count"] = total_clients
            except Exception:
                data["clients_count"] = 0

            # 使用 iwinfo assoclist 补充/验证无线客户端列表并统计
            try:
                iw_clients_by_device = {}
                devices_to_probe = set()
                # 从 wireless_by_ifname 中收集可能的 device 名称
                for ifname, entry in (data.get("wireless_by_ifname") or {}).items():
                    dev = entry.get("device") or entry.get("ifname") or entry.get("name")
                    if dev:
                        devices_to_probe.add(dev)
                        # 也尝试常见的 ap 后缀形式
                        devices_to_probe.add(f"{dev}-ap0")

                # 也包含已知的 clients 键（例如 hostapd 返回的 phy0-ap0）
                for k in data.get("clients", {}).keys():
                    devices_to_probe.add(k)

                total_iw_clients = 0
                for dev in devices_to_probe:
                    try:
                        res = await self._ubus_call("iwinfo", "assoclist", {"device": dev})
                        if not res:
                            continue

                        # 解析返回结构，兼容 dict/list
                        count = 0
                        if isinstance(res, dict):
                            # 有些实现返回 'assoclist' 或 'stations' 或直接为列表字段
                            if "assoclist" in res and isinstance(res["assoclist"], list):
                                count = len(res["assoclist"])
                            elif "stations" in res and isinstance(res["stations"], list):
                                count = len(res["stations"])
                            else:
                                # 查找首个为 list 的字段
                                for v in res.values():
                                    if isinstance(v, list):
                                        count = len(v)
                                        break
                        elif isinstance(res, list):
                            count = len(res)

                        if count:
                            iw_clients_by_device[dev] = count
                            total_iw_clients += count
                    except Exception:
                        continue

                data["iw_clients_by_device"] = iw_clients_by_device
                data["iw_clients_count"] = total_iw_clients
            except Exception:
                data["iw_clients_by_device"] = {}
                data["iw_clients_count"] = 0

            # 尝试通过多个可能的 ubus 接口获取 DHCP 租约数量
            dhcp_count = None
            try:
                # 优先使用 LuCI RPC 返回的租约列表（如果可用）
                try:
                    luci_res = results[-1] if results else None
                except Exception:
                    luci_res = None

                if luci_res:
                    # 尝试解析 luci-rpc 返回的租约结构，兼容 dict/list 等多种格式
                    leases = None
                    if isinstance(luci_res, dict):
                        if "data" in luci_res and isinstance(luci_res["data"], list):
                            leases = luci_res["data"]
                        elif "leases" in luci_res and isinstance(luci_res["leases"], list):
                            leases = luci_res["leases"]
                        else:
                            vals = [v for v in luci_res.values() if isinstance(v, (list, dict))]
                            if vals and isinstance(vals[0], list):
                                leases = vals[0]
                    elif isinstance(luci_res, list):
                        leases = luci_res

                    if leases is not None:
                        seen_ips = set()
                        for item in leases:
                            ips = []
                            if isinstance(item, str):
                                ips.append(item)
                            elif isinstance(item, dict):
                                for k in ("ip", "ipaddr", "address", "ipv4", "ipv6", "lease"):
                                    v = item.get(k) if isinstance(item.get(k), str) else None
                                    if v:
                                        ips.append(v)
                                if not ips:
                                    for v in item.values():
                                        if isinstance(v, str) and ('.' in v or ':' in v):
                                            ips.append(v)
                            for ip in ips:
                                if ip and ip not in seen_ips:
                                    seen_ips.add(ip)
                        dhcp_count = len(seen_ips)
                        data["dhcp_leases_raw"] = luci_res

                dhcp_candidates = [
                    ("dhcp", "leases"),
                    ("dhcp", "get_leases"),
                    ("dnsmasq", "leases"),
                    ("odhcpd", "leases"),
                    ("dnsmasq", "get_leases"),
                ]
                for ns, method in dhcp_candidates:
                    try:
                        res = await self._ubus_call(ns, method)
                        if not res:
                            continue

                        # 常见结构：{"leases": [...] } 或直接为 list
                        if isinstance(res, dict):
                            # 直接包含 leases 字段
                            if "leases" in res and isinstance(res["leases"], list):
                                dhcp_count = len(res["leases"])
                                break

                            # 有时返回的字典中某个 value 就是租约列表
                            found = False
                            for v in res.values():
                                if isinstance(v, list):
                                    dhcp_count = len(v)
                                    found = True
                                    break
                            if found:
                                break

                        elif isinstance(res, list):
                            dhcp_count = len(res)
                            break
                    except Exception:
                        continue
            except Exception:
                dhcp_count = None

            # 如果通过 ubus 未能获取到租约信息，回退为读取常见租约文件
            if dhcp_count is None:
                lease_files = ["/tmp/dhcp.leases", "/var/lib/misc/dnsmasq.leases", "/var/lib/dhcp/dhcpd.leases"]
                for lf in lease_files:
                    try:
                        _LOGGER.debug("尝试通过 file.exec 读取租约文件: %s", lf)
                        res = await self._ubus_call("file", "exec", {"command": "cat", "params": [lf]})
                        # 处理多种可能的返回结构
                        content = None
                        if res is None:
                            continue
                        if isinstance(res, dict):
                            # 常见情况下执行结果可能放在 stdout / output / data 字段
                            for key in ("stdout", "output", "data", "return"):
                                if key in res and isinstance(res[key], str):
                                    content = res[key]
                                    break
                            # 有些实现直接把文本作为 values 的某个字段
                            if content is None:
                                for v in res.values():
                                    if isinstance(v, str) and " " in v:
                                        content = v
                                        break
                        elif isinstance(res, str):
                            content = res

                        if not content:
                            continue

                        # 解析 lease 文件，每行一个租约；忽略空行
                        lines = [l for l in content.splitlines() if l.strip()]
                        if lines:
                            dhcp_count = len(lines)
                            data["dhcp_leases_source"] = lf
                            _LOGGER.debug("从租约文件 %s 解析到 %s 条租约", lf, dhcp_count)
                            break
                    except Exception as e:
                        _LOGGER.debug("读取租约文件 %s 失败: %s", lf, e)

            data["dhcp_leases_count"] = dhcp_count if dhcp_count is not None else 0

            # 读取所有 thermal_zone 温度（通过 ubus file read），自动发现任意数量的 thermal_zoneN
            temperatures = {}
            try:
                async def _read_zone(idx: int):
                    path_temp = f"/sys/class/thermal/thermal_zone{idx}/temp"
                    path_type = f"/sys/class/thermal/thermal_zone{idx}/type"
                    try:
                        tmp = await self._ubus_call("file", "read", {"path": path_temp})
                        if not tmp or not isinstance(tmp, dict):
                            return None
                        temp_raw = tmp.get("data", "").strip()
                        t = await self._ubus_call("file", "read", {"path": path_type})
                        type_name = None
                        if t and isinstance(t, dict):
                            type_name = t.get("data", "").strip()
                        return (idx, type_name or f"thermal_zone{idx}", temp_raw)
                    except Exception:
                        return None

                # probe a reasonable range of possible zones (0..31)
                zone_tasks = [_read_zone(i) for i in range(0, 32)]
                zone_results = await asyncio.gather(*zone_tasks, return_exceptions=True)
                for res in zone_results:
                    if not res or isinstance(res, Exception):
                        continue
                    idx, name, temp_raw = res
                    try:
                        # temperature usually in millidegrees
                        val = int(temp_raw)
                        celsius = round(val / 1000.0, 2)
                    except Exception:
                        try:
                            celsius = float(temp_raw)
                        except Exception:
                            continue
                    label = (name or f"thermal_zone{idx}").replace(" ", "_").replace("/", "_")
                    key = f"{label}_{idx}"
                    temperatures[key] = {
                        "label": name,
                        "celsius": celsius,
                        "raw": temp_raw,
                        "zone": idx
                    }
            except Exception as e:
                _LOGGER.debug("Error probing thermal zones: %s", e)

            data["temperatures"] = temperatures

            # 计算速率（如果有之前的数据）
            if self._previous_data:
                data["rates"] = self._calculate_rates(data, self._previous_data)
            
            self._previous_data = data.copy()
            
            _LOGGER.debug("数据更新完成: %s", list(data.keys()))
            return data
            
        except Exception as e:
            _LOGGER.error("更新数据时出错: %s", e)
            return {}

    def _calculate_rates(self, current_data, previous_data):
        """计算速率"""
        rates = {}
        
        # 计算网络接口速率
        if "interfaces" in current_data and "interfaces" in previous_data:
            for iface_name, iface_data in current_data["interfaces"].items():
                if iface_name in previous_data["interfaces"]:
                    prev_iface = previous_data["interfaces"][iface_name]
                    # 这里可以添加速率计算逻辑
                    pass
        
        return rates

    async def async_close(self):
        """关闭连接"""
        if self._session:
            await self._session.close()

    async def call_ubus(self, namespace: str, method: str, params: dict | None = None):
        """公共方法，供其他平台调用 ubus API（封装 _ubus_call）。返回调用结果或 None。"""
        return await self._ubus_call(namespace, method, params)
