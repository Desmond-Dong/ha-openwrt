from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import (
    UnitOfDataRate, UnitOfInformation, UnitOfTemperature,
    UnitOfTime, PERCENTAGE
)
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

def get_cpu_icon():
    return "mdi:cpu-64-bit"

def get_memory_icon():
    return "mdi:memory"

def get_network_icon():
    return "mdi:network"

def get_system_icon():
    return "mdi:server"

def get_wireless_icon():
    return "mdi:wifi"

def get_temperature_icon():
    return "mdi:thermometer"

def get_time_icon():
    return "mdi:clock-outline"

def get_process_icon():
    return "mdi:process"

def get_led_icon():
    return "mdi:led-on"

def get_watchdog_icon():
    return "mdi:dog-service"

def get_upgrade_icon():
    return "mdi:update"

def get_firewall_icon():
    return "mdi:shield-check"

class OpenWrtSensor(CoordinatorEntity, SensorEntity):
    """OpenWrt传感器实体"""

    def __init__(self, coordinator, name, value_fn, unit=None, icon=None, state_class=None, device_class=None, entity_category=None):
        super().__init__(coordinator)
        self._name = f"{name}"
        self._value_fn = value_fn
        self._unit = unit
        self._attr_unique_id = f"{coordinator.host}_{name.lower().replace(' ', '_')}"
        self._attr_name = self._name
        self._attr_native_unit_of_measurement = unit
        # 将所有实体关联到同一个设备（路由器），在 HA 中统一展示
        try:
            self._attr_device_info = {
                "identifiers": {(DOMAIN, coordinator.host)},
                "name": f"{coordinator.host}",
            }
        except Exception:
            pass
        if icon:
            self._attr_icon = icon
        if state_class:
            self._attr_state_class = state_class
        if device_class:
            self._attr_device_class = device_class
        # optional entity category (diagnostic/info)
        if entity_category:
            try:
                self._attr_entity_category = entity_category
            except Exception:
                pass

    @property
    def native_value(self):
        """获取传感器值"""
        try:
            return self._value_fn(self.coordinator.data)
        except Exception as e:
            _LOGGER.warning("Error getting value for %s: %s", self._name, e)
            return None

    @property
    def available(self):
        """检查传感器是否可用"""
        return self.coordinator.data is not None

async def async_setup_entry(hass, config_entry, async_add_entities):
    """设置OpenWrt传感器 - 针对OpenWrt 24.10+优化"""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    data = coordinator.data
    
    if not data:
        _LOGGER.warning("No data available from coordinator")
        return
    
    entities = []

    # 系统信息传感器
    entities.extend([
        OpenWrtSensor(
            coordinator, "Hostname", 
            lambda d: d.get("system_board", {}).get("hostname", "N/A"),
            icon=get_system_icon(),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        OpenWrtSensor(
            coordinator, "Version", 
            lambda d: d.get("system_board", {}).get("release", {}).get("version", "N/A"),
            icon=get_system_icon(),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        OpenWrtSensor(
            coordinator, "Description", 
            lambda d: d.get("system_board", {}).get("release", {}).get("description", "N/A"),
            icon=get_system_icon(),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        OpenWrtSensor(
            coordinator, "Distribution", 
            lambda d: d.get("system_board", {}).get("release", {}).get("distribution", "N/A"),
            icon=get_system_icon(),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        OpenWrtSensor(
            coordinator, "Revision", 
            lambda d: d.get("system_board", {}).get("release", {}).get("revision", "N/A"),
            icon=get_system_icon(),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        OpenWrtSensor(
            coordinator, "Architecture", 
            lambda d: d.get("system_board", {}).get("system", "N/A"),
            icon=get_system_icon(),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        OpenWrtSensor(
            coordinator, "CPU Cores", 
            lambda d: d.get("cpu_count", 1),
            icon=get_cpu_icon(),
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ])

    # 系统运行时间传感器
    if data.get("uptime"):
        entities.append(OpenWrtSensor(
            coordinator, "Uptime", 
            lambda d: d.get("uptime", {}).get("seconds", 0),
            unit=UnitOfTime.SECONDS,
            icon=get_time_icon(),
            state_class=SensorStateClass.TOTAL_INCREASING
        ))

    # CPU负载传感器（百分比显示）
    if data.get("load"):
        entities.extend([
            OpenWrtSensor(
                coordinator, "CPU Load 1min", 
                lambda d: d.get("load", [0, 0, 0])[0],
                unit=PERCENTAGE,
                icon=get_cpu_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
            OpenWrtSensor(
                coordinator, "CPU Load 5min", 
                lambda d: d.get("load", [0, 0, 0])[1],
                unit=PERCENTAGE,
                icon=get_cpu_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
            OpenWrtSensor(
                coordinator, "CPU Load 15min", 
                lambda d: d.get("load", [0, 0, 0])[2],
                unit=PERCENTAGE,
                icon=get_cpu_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
        ])

    # 内存传感器（MB显示）
    if data.get("memory"):
        entities.extend([
            OpenWrtSensor(
                coordinator, "Memory Total", 
                lambda d: d.get("memory", {}).get("total_mb", 0),
                unit=UnitOfInformation.MEGABYTES,
                icon=get_memory_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
            OpenWrtSensor(
                coordinator, "Memory Free", 
                lambda d: d.get("memory", {}).get("free_mb", 0),
                unit=UnitOfInformation.MEGABYTES,
                icon=get_memory_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
            OpenWrtSensor(
                coordinator, "Memory Available", 
                lambda d: d.get("memory", {}).get("available_mb", 0),
                unit=UnitOfInformation.MEGABYTES,
                icon=get_memory_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
            OpenWrtSensor(
                coordinator, "Memory Cached", 
                lambda d: d.get("memory", {}).get("cached_mb", 0),
                unit=UnitOfInformation.MEGABYTES,
                icon=get_memory_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
            OpenWrtSensor(
                coordinator, "Memory Buffered", 
                lambda d: d.get("memory", {}).get("buffered_mb", 0),
                unit=UnitOfInformation.MEGABYTES,
                icon=get_memory_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
            OpenWrtSensor(
                coordinator, "Memory Shared", 
                lambda d: d.get("memory", {}).get("shared_mb", 0),
                unit=UnitOfInformation.MEGABYTES,
                icon=get_memory_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
        ])

    # 文件系统传感器
    if data.get("rootfs"):
        entities.extend([
            OpenWrtSensor(
                coordinator, "RootFS Total", 
                lambda d: d.get("rootfs", {}).get("total", 0),
                unit=UnitOfInformation.MEGABYTES,
                icon=get_system_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
            OpenWrtSensor(
                coordinator, "RootFS Free", 
                lambda d: d.get("rootfs", {}).get("free", 0),
                unit=UnitOfInformation.MEGABYTES,
                icon=get_system_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
            OpenWrtSensor(
                coordinator, "RootFS Used", 
                lambda d: d.get("rootfs", {}).get("used", 0),
                unit=UnitOfInformation.MEGABYTES,
                icon=get_system_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
        ])

    if data.get("tmpfs"):
        entities.extend([
            OpenWrtSensor(
                coordinator, "TmpFS Total", 
                lambda d: d.get("tmpfs", {}).get("total", 0),
                unit=UnitOfInformation.MEGABYTES,
                icon=get_system_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
            OpenWrtSensor(
                coordinator, "TmpFS Free", 
                lambda d: d.get("tmpfs", {}).get("free", 0),
                unit=UnitOfInformation.MEGABYTES,
                icon=get_system_icon(),
                state_class=SensorStateClass.MEASUREMENT
            ),
        ])

    # OpenWrt 24.10+ 新增功能传感器
    
    # LED状态传感器
    if data.get("leds"):
        if isinstance(data["leds"], dict):
            for led_name, led_data in data["leds"].items():
                if isinstance(led_data, dict):
                    entities.append(OpenWrtSensor(
                        coordinator, f"LED {led_name.title()}", 
                        lambda d, n=led_name: d.get("leds", {}).get(n, {}).get("status", "N/A"),
                        icon=get_led_icon()
                    ))
                    # LED亮度
                    if "brightness" in led_data:
                        entities.append(OpenWrtSensor(
                            coordinator, f"LED {led_name.title()} Brightness", 
                            lambda d, n=led_name: d.get("leds", {}).get(n, {}).get("brightness", 0),
                            unit=PERCENTAGE,
                            icon=get_led_icon(),
                            state_class=SensorStateClass.MEASUREMENT,
                            entity_category=EntityCategory.DIAGNOSTIC,
                        ))

    # 看门狗传感器
    if data.get("watchdog"):
        if isinstance(data["watchdog"], dict):
            entities.append(OpenWrtSensor(
                coordinator, "Watchdog Status", 
                lambda d: d.get("watchdog", {}).get("status", "N/A"),
                icon=get_watchdog_icon()
            ))
            entities.append(OpenWrtSensor(
                coordinator, "Watchdog Timeout", 
                lambda d: d.get("watchdog", {}).get("timeout", 0),
                unit=UnitOfTime.SECONDS,
                icon=get_watchdog_icon(),
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            ))

    # 系统升级传感器
    if data.get("sysupgrade"):
        if isinstance(data["sysupgrade"], dict):
            entities.append(OpenWrtSensor(
                coordinator, "Sysupgrade Available", 
                lambda d: "Yes" if d.get("sysupgrade", {}).get("available", False) else "No",
                icon=get_upgrade_icon()
            ))
            entities.append(OpenWrtSensor(
                coordinator, "Sysupgrade Version", 
                lambda d: d.get("sysupgrade", {}).get("version", "N/A"),
                icon=get_upgrade_icon()
            ))

            # mark sysupgrade info as diagnostic
            entities[-2]._attr_entity_category = EntityCategory.DIAGNOSTIC
            entities[-1]._attr_entity_category = EntityCategory.DIAGNOSTIC

    # 网络接口传感器
    if data.get("interfaces"):
        for iface, iface_data in data.get("interfaces", {}).items():
            iface_upper = iface.upper()
            
            # 接口状态
            entities.append(OpenWrtSensor(
                coordinator, f"{iface_upper} Status", 
                lambda d, i=iface: "Up" if d.get("interfaces", {}).get(i, {}).get("up", False) else "Down",
                icon=get_network_icon(),
                entity_category=EntityCategory.DIAGNOSTIC,
            ))
            
            # 接口协议
            if "proto" in iface_data:
                entities.append(OpenWrtSensor(
                    coordinator, f"{iface_upper} Protocol", 
                    lambda d, i=iface: d.get("interfaces", {}).get(i, {}).get("proto", "N/A"),
                    icon=get_network_icon(),
                    entity_category=EntityCategory.DIAGNOSTIC,
                ))
            
            # 接口运行时间
            if "uptime" in iface_data:
                entities.append(OpenWrtSensor(
                    coordinator, f"{iface_upper} Uptime", 
                    lambda d, i=iface: d.get("interfaces", {}).get(i, {}).get("uptime", 0),
                    unit=UnitOfTime.SECONDS,
                    icon=get_network_icon(),
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    entity_category=EntityCategory.DIAGNOSTIC,
                ))
            
            # IPv4地址
            if "ipv4-address" in iface_data and iface_data["ipv4-address"]:
                for i, addr in enumerate(iface_data["ipv4-address"]):
                    entities.append(OpenWrtSensor(
                        coordinator, f"{iface_upper} IPv4 {i+1}", 
                        lambda d, i=iface, idx=i: d.get("interfaces", {}).get(i, {}).get("ipv4-address", [])[idx].get("address", "N/A") if len(d.get("interfaces", {}).get(i, {}).get("ipv4-address", [])) > idx else "N/A",
                        icon=get_network_icon(),
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ))
            
            # IPv6地址
            if "ipv6-address" in iface_data and iface_data["ipv6-address"]:
                for i, addr in enumerate(iface_data["ipv6-address"]):
                    entities.append(OpenWrtSensor(
                        coordinator, f"{iface_upper} IPv6 {i+1}", 
                        lambda d, i=iface, idx=i: d.get("interfaces", {}).get(i, {}).get("ipv6-address", [])[idx].get("address", "N/A") if len(d.get("interfaces", {}).get(i, {}).get("ipv6-address", [])) > idx else "N/A",
                        icon=get_network_icon(),
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ))
            
            # DNS服务器
            if "dns-server" in iface_data and iface_data["dns-server"]:
                for i, dns in enumerate(iface_data["dns-server"]):
                    entities.append(OpenWrtSensor(
                        coordinator, f"{iface_upper} DNS {i+1}", 
                        lambda d, i=iface, idx=i: d.get("interfaces", {}).get(i, {}).get("dns-server", [])[idx] if len(d.get("interfaces", {}).get(i, {}).get("dns-server", [])) > idx else "N/A",
                        icon=get_network_icon(),
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ))

    # 网络设备传感器
    if data.get("devices"):
        for dev, dev_data in data.get("devices", {}).items():
            dev_upper = dev.upper()
            
            # 设备类型
            if "type" in dev_data:
                entities.append(OpenWrtSensor(
                    coordinator, f"{dev_upper} Type", 
                    lambda d, n=dev: d.get("devices", {}).get(n, {}).get("type", "N/A"),
                    icon=get_network_icon()
                ))
            
            # 设备状态
            if "up" in dev_data:
                entities.append(OpenWrtSensor(
                    coordinator, f"{dev_upper} Status", 
                    lambda d, n=dev: "Up" if d.get("devices", {}).get(n, {}).get("up", False) else "Down",
                    icon=get_network_icon()
                ))
            
            # MTU
            if "mtu" in dev_data:
                entities.append(OpenWrtSensor(
                    coordinator, f"{dev_upper} MTU", 
                    lambda d, n=dev: d.get("devices", {}).get(n, {}).get("mtu", 0),
                    icon=get_network_icon(),
                    state_class=SensorStateClass.MEASUREMENT
                ))

    # 无线传感器
    if data.get("wireless"):
        for radio, radio_data in data.get("wireless", {}).items():
            if isinstance(radio_data, dict) and "interfaces" in radio_data:
                for iface in radio_data["interfaces"]:
                    if isinstance(iface, dict):
                        iface_name = iface.get("ifname", "unknown")
                        iface_upper = iface_name.upper()

                        # 无线状态
                        entities.append(OpenWrtSensor(
                            coordinator, f"{iface_upper} Wireless Status", 
                            lambda d, r=radio, i=iface_name: "Up" if d.get("wireless", {}).get(r, {}).get("interfaces", []) and any(iface.get("ifname") == i and iface.get("up", False) for iface in d.get("wireless", {}).get(r, {}).get("interfaces", [])) else "Down",
                            icon=get_wireless_icon()
                        ))

                        # 无线模式
                        if "mode" in iface:
                            entities.append(OpenWrtSensor(
                                coordinator, f"{iface_upper} Wireless Mode", 
                                lambda d, r=radio, i=iface_name: next((iface.get("mode", "N/A") for iface in d.get("wireless", {}).get(r, {}).get("interfaces", []) if iface.get("ifname") == i), "N/A"),
                                icon=get_wireless_icon()
                            ))

    # 如果 network.wireless 不可用，使用 UCI 配置 (wireless_config) 来显示 SSID/模式等
    if data.get("wireless_config"):
        for name, cfg in data.get("wireless_config", {}).items():
            # wifi-iface 表示逻辑接口，wifi-device 表示 radio
            if cfg.get(".type") == "wifi-iface":
                display = cfg.get(".name", name)
                ssid = cfg.get("ssid")
                mode = cfg.get("mode")
                encryption = cfg.get("encryption")

                entities.append(OpenWrtSensor(
                    coordinator, f"{display} SSID",
                    lambda d, n=name: d.get("wireless_config", {}).get(n, {}).get("ssid", "N/A"),
                    icon=get_wireless_icon()
                ))

                entities.append(OpenWrtSensor(
                    coordinator, f"{display} Mode",
                    lambda d, n=name: d.get("wireless_config", {}).get(n, {}).get("mode", "N/A"),
                    icon=get_wireless_icon(),
                        entity_category=EntityCategory.DIAGNOSTIC,
                ))

                entities.append(OpenWrtSensor(
                    coordinator, f"{display} Encryption",
                    lambda d, n=name: d.get("wireless_config", {}).get(n, {}).get("encryption", "N/A"),
                    icon=get_wireless_icon(),
                        entity_category=EntityCategory.DIAGNOSTIC,
                ))

    # 使用 wireless_by_ifname 索引展示更贴近 LuCI 的接口名（如果可用）
    if data.get("wireless_by_ifname"):
        for ifname, entry in data.get("wireless_by_ifname", {}).items():
            display = entry.get("name") or ifname
            # 若 entry 包含 ssid/device/channel/txpower，显示为传感器
            if entry.get("ssid"):
                entities.append(OpenWrtSensor(
                    coordinator, f"{display} SSID",
                    lambda d, i=ifname: d.get("wireless_by_ifname", {}).get(i, {}).get("ssid", "N/A"),
                    icon=get_wireless_icon(),
                        entity_category=EntityCategory.DIAGNOSTIC,
                ))
            if entry.get("device"):
                entities.append(OpenWrtSensor(
                    coordinator, f"{display} Device",
                    lambda d, i=ifname: d.get("wireless_by_ifname", {}).get(i, {}).get("device", "N/A"),
                    icon=get_wireless_icon(),
                        entity_category=EntityCategory.DIAGNOSTIC,
                ))
            # channel/txpower 可能在 wifi-device 条目（在 wireless_config 中）
            if entry.get("channel"):
                entities.append(OpenWrtSensor(
                    coordinator, f"{display} Channel",
                    lambda d, i=ifname: d.get("wireless_by_ifname", {}).get(i, {}).get("channel", "N/A"),
                    icon=get_wireless_icon(),
                    state_class=SensorStateClass.MEASUREMENT
                ))
            if entry.get("txpower"):
                entities.append(OpenWrtSensor(
                    coordinator, f"{display} TX Power",
                    lambda d, i=ifname: d.get("wireless_by_ifname", {}).get(i, {}).get("txpower", "N/A"),
                    icon=get_wireless_icon(),
                    unit="dBm",
                    device_class="signal_strength",
                    state_class=SensorStateClass.MEASUREMENT
                ))

    # 防火墙传感器
    if data.get("firewall_status"):
        if isinstance(data["firewall_status"], dict):
            entities.append(OpenWrtSensor(
                coordinator, "Firewall Status", 
                lambda d: "Active" if d.get("firewall_status", {}).get("enabled", False) else "Inactive",
                icon=get_firewall_icon()
            ))
            # 防火墙规则数量
            if "rules" in data["firewall_status"]:
                entities.append(OpenWrtSensor(
                    coordinator, "Firewall Rules", 
                    lambda d: len(d.get("firewall_status", {}).get("rules", [])),
                    icon=get_firewall_icon(),
                    state_class=SensorStateClass.MEASUREMENT
                ))

    # DHCP 租约（使用 LuCI RPC getDHCPLeases 的统计结果，如果 coordinator 提供）
    entities.append(OpenWrtSensor(
        coordinator, "DHCP Clients",
        lambda d: d.get("dhcp_leases_count", 0),
        icon=get_network_icon(),
        state_class=SensorStateClass.MEASUREMENT
    ))

    # WiFi 客户端统计（优先使用 iwinfo/hostapd 的统计）
    entities.append(OpenWrtSensor(
        coordinator, "WiFi Clients",
        lambda d: d.get("iw_clients_count", d.get("clients_count", 0)),
        icon=get_wireless_icon(),
        state_class=SensorStateClass.MEASUREMENT,
    ))

    # 进程传感器
    if data.get("processes"):
        if isinstance(data["processes"], dict) and "processes" in data["processes"]:
            process_list = data["processes"]["processes"]
            if isinstance(process_list, list):
                entities.append(OpenWrtSensor(
                    coordinator, "Process Count", 
                    lambda d: len(d.get("processes", {}).get("processes", [])),
                    icon=get_process_icon(),
                    state_class=SensorStateClass.MEASUREMENT
                ))

    # 服务传感器
    if data.get("services"):
        if isinstance(data["services"], dict) and "services" in data["services"]:
            service_list = data["services"]["services"]
            if isinstance(service_list, list):
                entities.append(OpenWrtSensor(
                    coordinator, "Service Count", 
                    lambda d: len(d.get("services", {}).get("services", [])),
                    icon=get_system_icon(),
                    state_class=SensorStateClass.MEASUREMENT
                ))

    # 运行中服务传感器
    if data.get("running_services"):
        if isinstance(data["running_services"], dict) and "services" in data["running_services"]:
            running_list = data["running_services"]["services"]
            if isinstance(running_list, list):
                entities.append(OpenWrtSensor(
                    coordinator, "Running Services", 
                    lambda d: len(d.get("running_services", {}).get("services", [])),
                    icon=get_system_icon(),
                    state_class=SensorStateClass.MEASUREMENT
                ))

    # 日志传感器
    if data.get("logs"):
        if isinstance(data["logs"], dict) and "data" in data["logs"]:
            log_data = data["logs"]["data"]
            if isinstance(log_data, list):
                entities.append(OpenWrtSensor(
                    coordinator, "Log Count", 
                    lambda d: len(d.get("logs", {}).get("data", [])),
                    icon=get_system_icon(),
                    state_class=SensorStateClass.MEASUREMENT
                ))

    # Ubus服务传感器
    if data.get("ubus_services"):
        if isinstance(data["ubus_services"], dict) and "services" in data["ubus_services"]:
            ubus_services = data["ubus_services"]["services"]
            if isinstance(ubus_services, list):
                entities.append(OpenWrtSensor(
                    coordinator, "Ubus Services", 
                    lambda d: len(d.get("ubus_services", {}).get("services", [])),
                    icon=get_system_icon(),
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_category=EntityCategory.DIAGNOSTIC,
                ))

    # 系统监控传感器
    if data.get("system_monitor"):
        if isinstance(data["system_monitor"], dict):
            entities.append(OpenWrtSensor(
                coordinator, "System Monitor Status", 
                lambda d: d.get("system_monitor", {}).get("status", "N/A"),
                icon=get_system_icon()
            ))
            # diagnostic
            entities[-1]._attr_entity_category = EntityCategory.DIAGNOSTIC

    # 系统统计传感器
    if data.get("system_stats"):
        if isinstance(data["system_stats"], dict):
            for stat_name, stat_value in data["system_stats"].items():
                if isinstance(stat_value, (int, float)):
                    entities.append(OpenWrtSensor(
                        coordinator, f"System {stat_name.title()}", 
                        lambda d, n=stat_name: d.get("system_stats", {}).get(n, 0),
                        icon=get_system_icon(),
                        state_class=SensorStateClass.MEASUREMENT
                    ))

    _LOGGER.info("创建了 %d 个OpenWrt传感器", len(entities))
    # 从 coordinator.data 中为每个发现的 thermal zone 创建温度传感器
    try:
        temps = data.get("temperatures", {})
        if temps and isinstance(temps, dict):
            for key, info in temps.items():
                label = info.get("label") or f"Temperature {info.get('zone')}"
                zone = info.get("zone")
                entities.append(OpenWrtSensor(
                    coordinator,
                    f"{label} ({zone})",
                    lambda d, k=key: d.get("temperatures", {}).get(k, {}).get("celsius"),
                    unit=UnitOfTemperature.CELSIUS,
                    icon=get_temperature_icon(),
                    state_class=SensorStateClass.MEASUREMENT,
                ))
    except Exception:
        pass
    async_add_entities(entities)
