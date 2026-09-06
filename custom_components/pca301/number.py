"""PCA301 number platform for device configuration (Auto On Delay, Availability Timeout)."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    CONF_AUTO_ON_DELAY,
    CONF_AVAILABILITY_TIMEOUT,
    DEFAULT_AUTO_ON_DELAY,
    DEFAULT_AVAILABILITY_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up PCA301 number entities from a config entry."""
    pca = hass.data["pca301"][entry.entry_id]

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

    entities = []
    for device_id in device_ids:
        entities.append(
            PCA301Number(
                hass,
                pca,
                entry,
                device_id,
                config_key=CONF_AUTO_ON_DELAY,
                name="Auto On Delay",
                unique_suffix="auto_on_delay",
                min_value=1,
                max_value=60,
                default=DEFAULT_AUTO_ON_DELAY,
                unit="s",
                icon="mdi:timer-outline",
            )
        )
        entities.append(
            PCA301Number(
                hass,
                pca,
                entry,
                device_id,
                config_key=CONF_AVAILABILITY_TIMEOUT,
                name="Availability Timeout",
                unique_suffix="availability_timeout",
                min_value=10,
                max_value=300,
                default=DEFAULT_AVAILABILITY_TIMEOUT,
                unit="s",
                icon="mdi:lan-disconnect",
                enabled_by_default=False,
            )
        )

    async_add_entities(entities)

    # Listen for new devices via dispatcher
    async def async_add_new_devices(new_device_ids):
        for device_id in new_device_ids:
            async_add_entities(
                [
                    PCA301Number(
                        hass, pca, entry, device_id,
                        config_key=CONF_AUTO_ON_DELAY,
                        name="Auto On Delay",
                        unique_suffix="auto_on_delay",
                        min_value=1, max_value=60,
                        default=DEFAULT_AUTO_ON_DELAY,
                        unit="s", icon="mdi:timer-outline",
                    ),
                    PCA301Number(
                        hass, pca, entry, device_id,
                        config_key=CONF_AVAILABILITY_TIMEOUT,
                        name="Availability Timeout",
                        unique_suffix="availability_timeout",
                        min_value=10, max_value=300,
                        default=DEFAULT_AVAILABILITY_TIMEOUT,
                        unit="s", icon="mdi:lan-disconnect",
                        enabled_by_default=False,
                    ),
                ]
            )

    async_dispatcher_connect(
        hass,
        f"pca301_new_devices_{entry.entry_id}",
        async_add_new_devices,
    )
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, pca.close)


class PCA301Number(NumberEntity):
    """Number entity for per-device numeric configuration."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        hass,
        pca,
        entry,
        device_id,
        *,
        config_key,
        name,
        unique_suffix,
        min_value,
        max_value,
        default,
        unit,
        icon,
        enabled_by_default=True,
    ):
        """Initialize the number entity."""
        self.hass = hass
        self._pca = pca
        self._entry = entry
        self._device_id = device_id
        self._config_key = config_key
        self._default = default
        self._attr_name = name
        self._attr_unique_id = f"pca301_{device_id}_{unique_suffix}"
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_entity_registry_enabled_default = enabled_by_default
        self._attr_device_info = {
            "identifiers": {("pca301", device_id)},
        }

    async def async_added_to_hass(self):
        """Disable availability_timeout entity by default when first added."""
        if not self._attr_entity_registry_enabled_default:
            # Nur beim allerersten Hinzufügen deaktivieren, nicht bei Neustart/Reload
            # Wir prüfen, ob die Entity bereits einen State hat (dann war sie schon mal da)
            last_state = await self.async_get_last_state()
            if last_state is None:
                # Erstmalig hinzugefügt: explizit deaktivieren
                entity_registry = er.async_get(self.hass)
                entity_registry.async_update_entity(
                    self.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
                )
        await super().async_added_to_hass()

    @property
    def native_value(self) -> float:
        """Return current configured value."""
        return self._pca._device_config.get(self._device_id, {}).get(
            self._config_key, self._default
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value, store in runtime config and persist."""
        int_value = int(value)
        self._pca._device_config.setdefault(self._device_id, {})[
            self._config_key
        ] = int_value

        # Persistieren, damit die Einstellung einen Neustart überlebt
        new_options = dict(self._entry.options)
        device_config = dict(new_options.get("device_config", {}))
        device_config[self._device_id] = {
            **device_config.get(self._device_id, {}),
            self._config_key: int_value,
        }
        new_options["device_config"] = device_config
        self.hass.config_entries.async_update_entry(
            self._entry, options=new_options
        )
        self.async_write_ha_state()
