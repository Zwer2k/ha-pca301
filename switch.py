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
    if discovery_info is None:
        return
    serial_device = discovery_info["device"]
    try:
        pca = pypca.PCA(serial_device)
        pca.open()
        # Blockierende Aufrufe auslagern
        import asyncio
        loop = asyncio.get_event_loop()
        devices = loop.run_until_complete(hass.async_add_executor_job(pca.get_devices))
        entities = [SmartPlugSwitch(hass, pca, device) for device in devices]
        add_entities(entities, True)
    except SerialException as exc:
        _LOGGER.warning("Unable to open serial port: %s", exc)
        return
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, pca.close)
    loop.run_until_complete(hass.async_add_executor_job(pca.start_scan))


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up PCA301 switch platform from a config entry."""
    serial_device = entry.data.get("device")
    try:
        pca = pypca.PCA(serial_device)
        await pca.async_load_known_devices(hass)
        pca.open()
        devices = await hass.async_add_executor_job(pca.get_devices)

        # Create a lock for serial communication
        pca_lock = asyncio.Lock()

        # Store pca and lock in hass.data for access by all entities
        if "pca301" not in hass.data:
            hass.data["pca301"] = {}
        hass.data["pca301"][serial_device] = {"pca": pca, "lock": pca_lock}

        entities = []
        for device in devices.keys():
            # Prüfe, ob das Gerät erreichbar ist (Statusabfrage)
            try:
                state = await hass.async_add_executor_job(pca.get_state, device)
            except Exception:
                _LOGGER.warning(f"PCA301 device {device} not reachable, skipping.")
                continue
            switch = SmartPlugSwitch(hass, pca, pca_lock, device)
            power = PowerSensor(hass, pca, pca_lock, device)
            consumption = ConsumptionSensor(hass, pca, pca_lock, device)
            entities.append(switch)
            entities.append(power)
            entities.append(consumption)
        async_add_entities(entities, True)
    except SerialException as exc:
        _LOGGER.warning("Unable to open serial port: %s", exc)
        return
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, pca.close)
    await hass.async_add_executor_job(pca.start_scan)
class PowerSensor(SensorEntity):
    SCAN_INTERVAL = timedelta(seconds=10)
    
    def __init__(self, hass, pca, pca_lock, device_id):
        self.hass = hass
        self._pca = pca
        self._pca_lock = pca_lock
        self._device_id = device_id
        self._attr_name = f"PCA301 Power {device_id}"
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = "power"
        self._attr_state_class = "measurement"
        self._attr_icon = "mdi:flash"
        self._state = None
        self._available = True

    async def async_update(self):
        try:
            async with self._pca_lock:
                self._state = await self.hass.async_add_executor_job(self._pca.get_current_power, self._device_id)
            self._available = True
        except Exception as ex:
            if self._available:
                _LOGGER.warning("Could not read power for %s: %s", self._device_id, ex)
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def native_value(self):
        return self._state

    @property
    def unique_id(self):
        return f"pca301_power_{self._device_id}"

    @property
    def device_info(self):
        return {
            "identifiers": {("pca301", self._device_id)},
            "name": f"PCA301 {self._device_id}",
            "manufacturer": "ELV",
            "model": "PCA301",
        }

class ConsumptionSensor(SensorEntity):
    SCAN_INTERVAL = timedelta(seconds=10)
    
    def __init__(self, hass, pca, pca_lock, device_id):
        self.hass = hass
        self._pca = pca
        self._pca_lock = pca_lock
        self._device_id = device_id
        self._attr_name = f"PCA301 Consumption {device_id}"
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_device_class = "energy"
        self._attr_state_class = "total_increasing"
        self._attr_icon = "mdi:counter"
        self._state = None
        self._available = True

    async def async_update(self):
        try:
            async with self._pca_lock:
                self._state = await self.hass.async_add_executor_job(self._pca.get_total_consumption, self._device_id)
            self._available = True
        except Exception as ex:
            if self._available:
                _LOGGER.warning("Could not read consumption for %s: %s", self._device_id, ex)
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def native_value(self):
        return self._state

    @property
    def unique_id(self):
        return f"pca301_consumption_{self._device_id}"

    @property
    def device_info(self):
        return {
            "identifiers": {("pca301", self._device_id)},
            "name": f"PCA301 {self._device_id}",
            "manufacturer": "ELV",
            "model": "PCA301",
        }


class SmartPlugSwitch(SwitchEntity):
    SCAN_INTERVAL = timedelta(seconds=10)
    
    """Representation of a PCA Smart Plug switch."""
    def __init__(self, hass, pca, pca_lock, device_id):
        """Initialize the switch."""
        self.hass = hass
        self._device_id = device_id
        self._name = f"PCA301 Switch {device_id}"
        self._state = None
        self._available = True
        self._pca = pca
        self._pca_lock = pca_lock
        self._attr_icon = "mdi:power"
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
