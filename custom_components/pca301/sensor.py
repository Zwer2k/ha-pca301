"""PCA301 sensor platform for Home Assistant."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up PCA301 sensor platform from a config entry."""
    pca = hass.data["pca301"][entry.entry_id]
    pca_lock = asyncio.Lock()

    # Get devices from channel mapping in options
    channel_mapping = entry.options.get("channels", {})
    device_ids = list(channel_mapping.keys())

    # If no channel mapping, fallback to registry
    if not device_ids:
        device_registry = dr.async_get(hass)
        registry_devices = [
            device
            for device in device_registry.devices.values()
            if entry.entry_id in device.config_entries
            and "pca301" in [id[0] for id in device.identifiers]
        ]
        device_ids = []
        for device in registry_devices:
            for ident in device.identifiers:
                if ident[0] == "pca301":
                    device_ids.append(ident[1])

    # --- Device Registry: Geräte explizit anlegen (wie UniFi) ---
    device_registry = dr.async_get(hass)
    for device_id in device_ids:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("pca301", device_id)},
            manufacturer="ELV",
            model="PCA301",
            name=f"PCA301 {device_id}",
        )

    _LOGGER.info(
        f"[PCA301] Gerätezustände in async_setup_entry: _devices={pca._devices}"
    )
    entities = []
    for device_id in device_ids:
        # Ensure device exists in pca._devices
        if device_id not in pca._devices and device_id in pca._known_devices:
            pca._devices[device_id] = {
                "state": 0,
                "consumption": 0,
                "power": 0,
                "channel": pca._known_devices[device_id],
            }

        device_data = pca._devices.get(device_id, {})
        power = device_data.get("power", 0)
        consumption = device_data.get("consumption", 0)
        channel_val = pca._known_devices.get(device_id)
        _LOGGER.debug(f"Setting up sensors for device {device_id}: power={power}, consumption={consumption}, channel={channel_val}")
        entities.append(PowerSensor(hass, pca, pca_lock, device_id, initial_value=power))
        entities.append(ConsumptionSensor(hass, pca, pca_lock, device_id, initial_value=consumption))
        entities.append(ChannelDiagnosticSensor(hass, pca, device_id, initial_value=channel_val))
    async_add_entities(entities)
    for entity in entities:
        entity.async_write_ha_state()

    # Listen for new devices via dispatcher
    async def async_add_new_devices(new_device_ids):
        for device_id in new_device_ids:
            # Device Registry: auch für neue Geräte anlegen
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={("pca301", device_id)},
                manufacturer="ELV",
                model="PCA301",
                name=f"PCA301 {device_id}",
            )
            async_add_entities([
                PowerSensor(hass, pca, pca_lock, device_id),
                ConsumptionSensor(hass, pca, pca_lock, device_id),
                ChannelDiagnosticSensor(hass, pca, device_id),
            ])
    async_dispatcher_connect(
        hass,
        f"pca301_new_devices_{entry.entry_id}",
        async_add_new_devices,
    )
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, pca.close)


class ChannelDiagnosticSensor(SensorEntity):
    """Diagnostic sensor for PCA301 channel."""
    _attr_icon = "mdi:lan"
    _attr_native_unit_of_measurement = None
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass, pca, device_id, initial_value=None):
        self.hass = hass
        self._pca = pca
        self._device_id = device_id
        self._attr_name = f"PCA301 {device_id} Channel"
        self._attr_unique_id = f"pca301_{device_id}_channel"
        self._attr_device_info = {
            "identifiers": {("pca301", self._device_id)},
            "name": f"PCA301 {self._device_id}",
            "manufacturer": "ELV",
            "model": "PCA301",
        }
        self._state = initial_value
        self._available = initial_value is not None

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.async_write_ha_state()

    async def async_update(self):
        try:
            # Channel direkt aus _known_devices (persistente Quelle)
            channel = self._pca._known_devices.get(self._device_id)
            self._state = channel
            self._available = channel is not None
        except Exception:
            self._available = False

    @property
    def native_value(self):
        return self._state

    @property
    def available(self) -> bool:
        return self._available

    @property
    def extra_state_attributes(self):
        # Channel immer aus _known_devices (persistente Quelle)
        channel = self._pca._known_devices.get(self._device_id)
        return {"channel": channel}


class PowerSensor(SensorEntity):
    SCAN_INTERVAL = timedelta(seconds=10)

    def __init__(self, hass, pca, pca_lock, device_id, initial_value=None):
        self.hass = hass
        self._pca = pca
        self._pca_lock = pca_lock
        self._device_id = device_id
        self._attr_name = f"PCA301 {device_id} Power"
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = "measurement"
        self._attr_icon = "mdi:flash"
        self._state = initial_value
        self._available = initial_value is not None

    async def async_update(self):
        try:
            async with self._pca_lock:
                self._state = await self.hass.async_add_executor_job(
                    self._pca.get_current_power, self._device_id
                )
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
        if not self._available:
            return None
        return self._state

    @property
    def unique_id(self):
        return f"pca301_{self._device_id}_power"


    @property
    def device_info(self):
        return {
            "identifiers": {("pca301", self._device_id)},
            "name": f"PCA301 {self._device_id}",
            "manufacturer": "ELV",
            "model": "PCA301",
        }

    @property
    def extra_state_attributes(self):
        # Channel immer aus _known_devices (persistente Quelle)
        channel = self._pca._known_devices.get(self._device_id)
        return {"channel": channel}


class ConsumptionSensor(SensorEntity):
    SCAN_INTERVAL = timedelta(seconds=10)

    def __init__(self, hass, pca, pca_lock, device_id, initial_value=None):
        self.hass = hass
        self._pca = pca
        self._pca_lock = pca_lock
        self._device_id = device_id
        self._attr_name = f"PCA301 {device_id} Consumption"
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = "total_increasing"
        self._attr_icon = "mdi:counter"
        self._state = initial_value
        self._available = initial_value is not None

    async def async_update(self):
        try:
            async with self._pca_lock:
                self._state = await self.hass.async_add_executor_job(
                    self._pca.get_total_consumption, self._device_id
                )
            self._available = True
        except Exception as ex:
            if self._available:
                _LOGGER.warning(
                    "Could not read consumption for %s: %s", self._device_id, ex
                )
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def native_value(self):
        if not self._available:
            return None
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

    @property
    def extra_state_attributes(self):
        channel = None
        if self._device_id in self._pca._devices:
            channel = self._pca._devices[self._device_id].get("channel")
        return {"channel": channel}
