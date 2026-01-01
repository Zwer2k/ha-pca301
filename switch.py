from __future__ import annotations
from datetime import timedelta
"""Support for PCA 301 smart switch."""

import asyncio
import logging
from typing import Any

from . import pypca
from serial import SerialException

from homeassistant.components.switch import SwitchEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "PCA 301"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the PCA switch platform (YAML)."""

    pca_lock = asyncio.Lock()
    if discovery_info is None:
        return
    serial_device = discovery_info["device"]
    try:
        pca = pypca.PCA(serial_device)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(pca.async_load_known_devices(hass))
        pca.open()
        # Blockierende Aufrufe auslagern
        devices = loop.run_until_complete(hass.async_add_executor_job(pca.get_devices))
        entities = [SmartPlugSwitch(hass, pca, pca_lock, device) for device in devices]
        add_entities(entities, True)
    except SerialException as exc:
        _LOGGER.warning("Unable to open serial port: %s", exc)
        return


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up PCA301 switch platform from a config entry."""
    _LOGGER.info(f"async_setup_entry: {entry.data.get('device')}")
    try:
        pca = hass.data["pca301"][entry.entry_id]
        pca_lock = asyncio.Lock()

        # Prefer devices from config entry options (from scan)
        device_ids = entry.options.get("devices")
        if device_ids is None:
            # Fallback: Get devices from registry (populated in __init__.py)
            registry_devices = hass.data["pca301"].get(f"{entry.entry_id}_devices", [])
            device_ids = []
            for device in registry_devices:
                for ident in device.identifiers:
                    if ident[0] == "pca301":
                        device_ids.append(ident[1])

        entities = []
        for device_id in device_ids:
            device_data = pca._devices.get(device_id, {})
            initial_state = device_data.get("state", None)
            switch = SmartPlugSwitch(
                hass, pca, pca_lock, device_id, initial_value=initial_state
            )
            switch._attr_entity_registry_enabled_default = False
            entities.append(switch)
        async_add_entities(entities)
        # Force state update for initial values
        for entity in entities:
            entity.async_write_ha_state()

        # Listen for new devices via dispatcher
        from homeassistant.helpers.dispatcher import async_dispatcher_connect

        async def async_add_new_devices(new_device_ids):
            for device_id in new_device_ids:
                switch = SmartPlugSwitch(hass, pca, pca_lock, device_id)
                switch._attr_entity_registry_enabled_default = False
                async_add_entities([switch])

        async_dispatcher_connect(
            hass,
            f"pca301_new_devices_{entry.entry_id}",
            async_add_new_devices,
        )
    except SerialException as exc:
        _LOGGER.warning("Unable to open serial port: %s", exc)
        return
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, pca.close)


class SmartPlugSwitch(SwitchEntity):
    SCAN_INTERVAL = timedelta(seconds=10)

    """Representation of a PCA Smart Plug switch."""

    def __init__(self, hass, pca, pca_lock, device_id, initial_value=None):
        """Initialize the switch."""
        self.hass = hass
        self._device_id = device_id
        self._name = f"PCA301 {device_id} Switch"
        self._state = initial_value
        self._available = initial_value is not None
        self._pca = pca
        self._pca_lock = pca_lock
        self._attr_icon = "mdi:power"

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.async_write_ha_state()

    @property
    def unique_id(self):
        return f"pca301_switch_{self._device_id}"

    @property
    def device_info(self):
        return {
            "identifiers": {("pca301", self._device_id)},
            "name": f"PCA301 {self._device_id}",
            "manufacturer": "ELV",
            "model": "PCA301",
        }

    @property
    def name(self):
        """Return the name of the Smart Plug, if any."""
        return self._name

    @property
    def available(self) -> bool:
        """Return if switch is available (Home Assistant shows device as grey if False)."""
        return self._available

    @property
    def is_on(self):
        """Return true if switch is on."""
        return bool(self._state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            _LOGGER.info(f"Turning on PCA301 device {self._device_id}")
            async with self._pca_lock:
                await self.hass.async_add_executor_job(self._pca.turn_on, self._device_id)
            self._state = True
            self._available = True
            self.async_write_ha_state()
            _LOGGER.info(f"PCA301 device {self._device_id} turned on successfully")
        except Exception as ex:
            _LOGGER.error(f"Could not turn on PCA301 device {self._device_id}: {ex}")
            self._available = False
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            _LOGGER.info(f"Turning off PCA301 device {self._device_id}")
            async with self._pca_lock:
                await self.hass.async_add_executor_job(self._pca.turn_off, self._device_id)
            self._state = False
            self._available = True
            self.async_write_ha_state()
            _LOGGER.info(f"PCA301 device {self._device_id} turned off successfully")
        except Exception as ex:
            _LOGGER.error(f"Could not turn off PCA301 device {self._device_id}: {ex}")
            self._available = False
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the PCA switch's state."""
        try:
            async with self._pca_lock:
                self._state = await self.hass.async_add_executor_job(self._pca.get_state, self._device_id)
            self._available = True
        except OSError as ex:
            if self._available:
                _LOGGER.warning("Could not read state for %s: %s", self.name, ex)
                self._available = False
