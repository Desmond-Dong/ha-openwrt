from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
import logging
import asyncio

_LOGGER = logging.getLogger(__name__)


class OpenWrtRestartButton(CoordinatorEntity, ButtonEntity):
    """Restart button for a specific OpenWrt interface."""

    def __init__(self, coordinator, interface_name: str):
        super().__init__(coordinator)
        # Buttons (restart per-interface) are disabled by default; user must enable them
        try:
            self._attr_entity_registry_enabled_default = False
        except Exception:
            pass
        self._interface = interface_name
        # Display name: do not prefix with integration name
        # Display name: use translation key with placeholder
        # Determine a friendly interface display name from coordinator data when available
        iface_data = {}
        try:
            iface_data = coordinator.data.get("interfaces", {}).get(interface_name, {}) or {}
        except Exception:
            iface_data = {}
        display = iface_data.get("ifname") or iface_data.get("name") or iface_data.get("l3_device") or interface_name
        # Set translation key and also set an explicit fallback name so
        # integrations that don't use translation or for new entities
        # will display a friendly name instead of the raw iface key/IP.
        try:
            self._attr_translation_key = "restart"
            self._attr_translation_placeholders = {"interface": display}
        except Exception:
            pass
        # Always set a readable name fallback (won't override entity registry)
        try:
            self._attr_name = f"Restart {display}"
        except Exception:
            self._attr_name = f"Restart {interface_name}"
        self._attr_unique_id = f"{coordinator.host}_restart_{interface_name}"
        try:
            # Prefer a hostname from coordinator data when available, fall back to host
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

    async def async_press(self) -> None:
        """Press the button to restart the interface."""
        iface = self._interface
        _LOGGER.info("Restart button pressed for interface %s", iface)
        try:
            # Try the same sequence as the service: down -> wait -> up with fallbacks
            result = await self.coordinator.call_ubus("network.interface", "down", {"interface": iface})
            if result is None:
                _LOGGER.debug("network.interface.down not available, trying network.ifdown for %s", iface)
                result = await self.coordinator.call_ubus("network", "ifdown", {"interface": iface})

            if result is None:
                try:
                    _LOGGER.debug("Trying file.exec '/sbin/wifi down %s' via ubus for restart", iface)
                    await self.coordinator.call_ubus("file", "exec", {"command": "/sbin/wifi", "params": ["down", iface]})
                except Exception:
                    _LOGGER.debug("file.exec wifi down failed for %s", iface)

            await asyncio.sleep(1)

            result = await self.coordinator.call_ubus("network.interface", "up", {"interface": iface})
            if result is None:
                _LOGGER.debug("network.interface.up not available, trying network.ifup for %s", iface)
                result = await self.coordinator.call_ubus("network", "ifup", {"interface": iface})

            if result is None:
                try:
                    _LOGGER.debug("Trying file.exec '/sbin/wifi up %s' via ubus for restart", iface)
                    await self.coordinator.call_ubus("file", "exec", {"command": "/sbin/wifi", "params": ["up", iface]})
                except Exception:
                    _LOGGER.debug("file.exec wifi up failed for %s", iface)

            await self.coordinator.async_request_refresh()
        except Exception as e:
            _LOGGER.error("Failed to restart interface %s via button: %s", iface, e)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    """Set up Restart buttons for each interface."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}

    # ensure storage for created buttons
    if not hasattr(coordinator, "_button_entities"):
        coordinator._button_entities = {}

    existing = coordinator._button_entities
    new = []
    for iface in (data.get("interfaces") or {}).keys():
        if iface in existing:
            continue
        ent = OpenWrtRestartButton(coordinator, iface)
        existing[iface] = ent
        new.append(ent)

    if new:
        async_add_entities(new)
        _LOGGER.info("Created %d Restart buttons", len(new))
    else:
        _LOGGER.debug("No new Restart buttons to create at setup")

    # dynamic listener to add buttons when new interfaces appear
    # DataUpdateCoordinator calls listeners synchronously. Use a synchronous
    # wrapper that schedules the async handler to avoid creating coroutine
    # objects that are never awaited.
    async def _async_handle_update():
        try:
            data = coordinator.data or {}
            added = []
            for iface in (data.get("interfaces") or {}).keys():
                if iface in coordinator._button_entities:
                    continue
                ent = OpenWrtRestartButton(coordinator, iface)
                coordinator._button_entities[iface] = ent
                added.append(ent)
            if added:
                _LOGGER.info("Dynamically adding %d Restart buttons", len(added))
                async_add_entities(added)
        except Exception as e:
            _LOGGER.debug("Error while dynamically adding Restart buttons: %s", e)

    def _handle_update():
        try:
            coordinator.hass.async_create_task(_async_handle_update())
        except Exception as e:
            _LOGGER.debug("Failed to schedule dynamic button add handler: %s", e)

    remove_listener = coordinator.async_add_listener(_handle_update)
    try:
        entry.async_on_unload(remove_listener)
    except Exception:
        pass

    # Create a global Reboot Router button (one per config entry)
    if not hasattr(coordinator, "_reboot_button_created") or not coordinator._reboot_button_created:
        try:
            reboot_ent = OpenWrtRebootButton(coordinator)
            # Ensure created reboot button is disabled by default
            try:
                reboot_ent._attr_entity_registry_enabled_default = False
            except Exception:
                pass
            coordinator._button_entities["__reboot__"] = reboot_ent
            async_add_entities([reboot_ent])
            coordinator._reboot_button_created = True
            _LOGGER.info("Created Reboot Router button")
        except Exception as e:
            _LOGGER.debug("Failed to create reboot button: %s", e)


class OpenWrtRebootButton(CoordinatorEntity, ButtonEntity):
    """Button entity to reboot the router."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        try:
            self._attr_translation_key = "reboot"
        except Exception:
            self._attr_name = "Reboot Router"
        self._attr_unique_id = f"{coordinator.host}_reboot"
        # Reboot button is disabled by default; require manual enable in entity registry
        try:
            self._attr_entity_registry_enabled_default = False
        except Exception:
            pass
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
            # Also set an explicit readable entity name fallback so new entities
            # will show a friendly label (e.g. "Reboot <hostname>") instead of raw IP.
            try:
                self._attr_name = f"Reboot System"
            except Exception:
                pass
        except Exception:
            pass

    async def async_press(self) -> None:
        _LOGGER.info("Reboot Router button pressed")
        try:
            result = await self.coordinator.call_ubus("system", "reboot", {})
            if result is None:
                try:
                    _LOGGER.debug("system.reboot not available, trying file.exec /sbin/reboot")
                    await self.coordinator.call_ubus("file", "exec", {"command": "/sbin/reboot", "params": []})
                except Exception:
                    try:
                        await self.coordinator.call_ubus("file", "exec", {"command": "reboot", "params": []})
                    except Exception as e:
                        _LOGGER.error("All reboot methods failed: %s", e)
        except Exception as e:
            _LOGGER.error("Failed to trigger reboot via button: %s", e)
