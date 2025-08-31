from __future__ import annotations

import asyncio
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

class OpenWrtInterfaceSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to control a network interface on OpenWrt"""

    def __init__(self, coordinator, interface_name: str):
        super().__init__(coordinator)
        # Disable switch entities by default; user must enable them in the entity registry
        try:
            self._attr_entity_registry_enabled_default = False
        except Exception:
            pass
        self._interface = interface_name
        # Display name: do not prefix with integration name
        self._attr_name = f"{interface_name}"
        self._attr_unique_id = f"{coordinator.host}_iface_{interface_name}"
        # 将实体关联到路由器设备，便于在HA中统一展示
        try:
            dev_name = coordinator.host
            try:
                dev_name = coordinator.data.get("system_info", {}).get("hostname", coordinator.host)
            except Exception:
                dev_name = coordinator.host
            self._attr_device_info = {
                "identifiers": {(DOMAIN, coordinator.host)},
                "name": dev_name,
            }
        except Exception:
            pass
        self._is_on = None

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        iface = data.get("interfaces", {}).get(self._interface, {})
        return iface.get("up", None)

    async def async_turn_on(self, **kwargs) -> None:
        """Bring interface up (if supported)"""
        try:
            # Common RPC - some systems implement network.interface up/down
            result = await self.coordinator.call_ubus("network.interface", "up", {"interface": self._interface})
            if result is None:
                # Try older/alternate RPC names
                _LOGGER.debug("network.interface.up returned no result for %s, trying network.ifup", self._interface)
                result = await self.coordinator.call_ubus("network", "ifup", {"interface": self._interface})

            if result is None:
                # Fallback for wireless-only devices: try invoking /sbin/wifi up <iface> via ubus file.exec
                try:
                    _LOGGER.debug("Attempting file.exec '/sbin/wifi up %s' via ubus as fallback", self._interface)
                    await self.coordinator.call_ubus("file", "exec", {"command": "/sbin/wifi", "params": ["up", self._interface]})
                    result = True
                except Exception:  # best-effort
                    result = None

            if result is None:
                # Final fallback: reload network (may apply interface changes)
                _LOGGER.debug("Final fallback: calling network.reload to bring up %s", self._interface)
                await self.coordinator.call_ubus("network", "reload", {})
        except Exception as e:
            _LOGGER.error("Failed to bring up interface %s: %s", self._interface, e)
        finally:
            # Request a refresh
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Bring interface down"""
        try:
            result = await self.coordinator.call_ubus("network.interface", "down", {"interface": self._interface})
            if result is None:
                # Try alternate method
                _LOGGER.debug("network.interface.down returned no result for %s, trying network.ifdown", self._interface)
                result = await self.coordinator.call_ubus("network", "ifdown", {"interface": self._interface})

            if result is None:
                # Fallback for wireless-only: try invoking /sbin/wifi down <iface>
                try:
                    _LOGGER.debug("Attempting file.exec '/sbin/wifi down %s' via ubus as fallback", self._interface)
                    await self.coordinator.call_ubus("file", "exec", {"command": "/sbin/wifi", "params": ["down", self._interface]})
                    result = True
                except Exception:
                    result = None

            if result is None:
                _LOGGER.debug("Final fallback: calling network.reload to bring down %s", self._interface)
                await self.coordinator.call_ubus("network", "reload", {})
        except Exception as e:
            _LOGGER.error("Failed to bring down interface %s: %s", self._interface, e)
        finally:
            await self.coordinator.async_request_refresh()

    async def async_toggle(self, **kwargs) -> None:
        """Toggle interface state"""
        if self.is_on:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_restart(self) -> None:
        """Restart interface (down -> up)"""
        try:
            await self.async_turn_off()
            # slight delay to ensure interface is down
            await self.coordinator.hass.async_add_executor_job(lambda: None)
            await self.async_turn_on()
        except Exception as e:
            _LOGGER.error("Failed to restart interface %s: %s", self._interface, e)

    async def async_update(self) -> None:
        """Update state from coordinator data (no-op, coordinator handles polling)"""
        # Coordinator will update and push state
        pass


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    """Set up switch entities for interfaces"""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    _LOGGER.debug("switch.async_setup_entry: discovered interfaces: %s", list(data.get("interfaces", {}).keys()))
    entities = []
    interfaces = data.get("interfaces", {})
    # Ensure coordinator has a place to keep created switch entities
    if not hasattr(coordinator, "_switch_entities"):
        coordinator._switch_entities = {}

    # Create switches for existing interfaces
    new_entities = []
    for iface in interfaces.keys():
        if iface in coordinator._switch_entities:
            continue
        ent = OpenWrtInterfaceSwitch(coordinator, iface)
        coordinator._switch_entities[iface] = ent
        new_entities.append(ent)

    if new_entities:
        async_add_entities(new_entities)
        _LOGGER.info("Created %d OpenWrt interface switches", len(new_entities))
    else:
        _LOGGER.info("No new OpenWrt interface switches created at setup")

    # Register a listener to add switches dynamically when new interfaces appear
    # Keep the actual update handler async but register a synchronous wrapper
    # with the coordinator. DataUpdateCoordinator calls listeners synchronously,
    # so registering an `async def` directly creates coroutine objects that are
    # never awaited. The wrapper schedules the coroutine on the event loop.
    async def _async_handle_coordinator_update():
        try:
            data = coordinator.data or {}
            interfaces = data.get("interfaces", {})
            added = []
            for iface in interfaces.keys():
                if iface in coordinator._switch_entities:
                    continue
                ent = OpenWrtInterfaceSwitch(coordinator, iface)
                coordinator._switch_entities[iface] = ent
                added.append(ent)
            if added:
                _LOGGER.info("Dynamically adding %d OpenWrt interface switches", len(added))
                async_add_entities(added)
        except Exception as e:
            _LOGGER.debug("Error while adding dynamic switches: %s", e)

    def _handle_coordinator_update():
        # Schedule the async handler on HA's event loop
        try:
            coordinator.hass.async_create_task(_async_handle_coordinator_update())
        except Exception as e:
            _LOGGER.debug("Failed to schedule coordinator update handler: %s", e)

    remove_listener = coordinator.async_add_listener(_handle_coordinator_update)
    # Ensure listener is removed when config entry is unloaded
    try:
        entry.async_on_unload(remove_listener)
    except Exception:
        # Older HA versions may not support entry.async_on_unload
        pass

    # 注册重启接口的服务：domain: ubus, service: restart_interface
    async def _handle_restart(call):
        iface = call.data.get("interface")
        if not iface:
            _LOGGER.warning("restart_interface called without 'interface' parameter")
            return
        try:
            # 尝试 down -> small delay -> up
            result = await coordinator.call_ubus("network.interface", "down", {"interface": iface})
            if result is None:
                _LOGGER.debug("network.interface.down failed for %s, trying network.ifdown", iface)
                result = await coordinator.call_ubus("network", "ifdown", {"interface": iface})

            if result is None:
                # Try wireless-specific wifi down
                try:
                    _LOGGER.debug("Trying file.exec '/sbin/wifi down %s' via ubus for restart", iface)
                    await coordinator.call_ubus("file", "exec", {"command": "/sbin/wifi", "params": ["down", iface]})
                except Exception:
                    _LOGGER.debug("file.exec wifi down failed for %s", iface)

            await asyncio.sleep(1)

            result = await coordinator.call_ubus("network.interface", "up", {"interface": iface})
            if result is None:
                _LOGGER.debug("network.interface.up failed for %s, trying network.ifup", iface)
                result = await coordinator.call_ubus("network", "ifup", {"interface": iface})

            if result is None:
                try:
                    _LOGGER.debug("Trying file.exec '/sbin/wifi up %s' via ubus for restart", iface)
                    await coordinator.call_ubus("file", "exec", {"command": "/sbin/wifi", "params": ["up", iface]})
                except Exception:
                    _LOGGER.debug("file.exec wifi up failed for %s", iface)

            await coordinator.async_request_refresh()
        except Exception as e:
            _LOGGER.error("Failed to restart interface %s: %s", iface, e)

    hass.services.async_register(DOMAIN, "restart_interface", _handle_restart)
    # 注册重启路由器服务 (reboot)
    async def _handle_reboot(call):
        try:
            # Prefer ubus system.reboot
            result = await coordinator.call_ubus("system", "reboot", {})
            if result is None:
                # Fallback: try invoking reboot binary via ubus file.exec
                try:
                    _LOGGER.debug("system.reboot not available, trying file.exec '/sbin/reboot'")
                    await coordinator.call_ubus("file", "exec", {"command": "/sbin/reboot", "params": []})
                except Exception:
                    _LOGGER.debug("file.exec /sbin/reboot failed, trying 'reboot' command")
                    try:
                        await coordinator.call_ubus("file", "exec", {"command": "reboot", "params": []})
                    except Exception as e:
                        _LOGGER.error("All reboot methods failed: %s", e)
        except Exception as e:
            _LOGGER.error("Failed to reboot router: %s", e)

    hass.services.async_register(DOMAIN, "reboot_router", _handle_reboot)
