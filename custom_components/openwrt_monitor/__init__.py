from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """设置OpenWrt Monitor集成"""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """设置OpenWrt Monitor配置条目"""
    try:
        from .coordinator import OpenWrtDataUpdateCoordinator

        # 创建协调器
        coordinator = OpenWrtDataUpdateCoordinator(hass, entry)

        # 执行首次数据刷新
        await coordinator.async_config_entry_first_refresh()

        # 存储协调器
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

        # 设置传感器、开关和按钮平台
        await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch", "button"])

        _LOGGER.info("OpenWrt Monitor integration setup completed for %s", entry.data.get("host", "unknown"))
        return True

    except Exception as e:
        _LOGGER.error("Failed to setup OpenWrt Monitor integration: %s", e)
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载OpenWrt Monitor配置条目"""
    try:
        # 卸载传感器、开关和按钮平台
        unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "switch", "button"])

        if unload_ok:
            # 清理协调器
            coordinator = hass.data[DOMAIN].pop(entry.entry_id)
            await coordinator.async_close()
            _LOGGER.info("OpenWrt Monitor integration unloaded for %s", entry.data.get("host", "unknown"))

        return unload_ok

    except Exception as e:
        _LOGGER.error("Failed to unload OpenWrt Monitor integration: %s", e)
        return False
