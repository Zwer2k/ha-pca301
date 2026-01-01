import asyncio

async def save_channel_mapping(hass, device, known_devices):
    """Speichere das Channel-Mapping für das passende ConfigEntry in entry.options."""
    from logging import getLogger

    _LOGGER = getLogger(__name__)
    config_entries = hass.config_entries.async_entries(DOMAIN)
    for config_entry in config_entries:
        if (
            config_entry.data.get("port") == device
            or config_entry.data.get("device") == device
        ):
            new_channels = known_devices.copy()
            _LOGGER.info(
                f"[PCA301] Speichere Channel-Mapping in entry.options: {new_channels}"
            )
            options = dict(config_entry.options)
            options["channels"] = new_channels
            await hass.config_entries.async_update_entry(config_entry, options=options)
            break


"""The PCA301 integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from .pypca import PCA
from homeassistant.helpers import device_registry as dr

DOMAIN = "pca301"
PLATFORMS = [Platform.SWITCH, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PCA301 from a config entry."""

    _LOGGER = logging.getLogger(__name__)
    port = entry.data.get("port") or entry.data.get("device") or "/dev/ttyUSB0"
    pca = PCA(hass, port)
    # Lade Channel-Mapping aus entry.options, falls vorhanden
    channel_map = entry.options.get("channels")
    if channel_map:
        _LOGGER.info(f"[PCA301] Lade Channel-Mapping aus entry.options: {channel_map}")
        pca._known_devices = channel_map.copy()
    else:
        _LOGGER.info("[PCA301] Kein Channel-Mapping in entry.options gefunden.")
    await pca.async_load_known_devices(hass)
    # Store hass reference for entity enabling
    pca.open()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = pca

    device_registry = dr.async_get(hass)
    devices = [
        device
        for device in device_registry.devices.values()
        if entry.entry_id in device.config_entries
        and DOMAIN in [id[0] for id in device.identifiers]
    ]
    hass.data[DOMAIN][f"{entry.entry_id}_devices"] = devices

    # Register scan_for_new_devices service here as well

    async def async_scan_for_new_devices_service(call):
        _LOGGER.info("Service pca301.scan_for_new_devices called, starting scan...")
        device = call.data.get("device")
        if not device:
            _LOGGER.warning(
                "No device specified for scan_for_new_devices service call."
            )
            return
        pca = PCA(hass, device)
        await pca.async_load_known_devices(hass)
        hass.async_create_task(
            hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "PCA301 Scan",
                    "message": "Scanning for new PCA301 devices. This may take up to 30 seconds. Please wait...",
                    "notification_id": "pca301_scan_in_progress",
                },
                blocking=False,
            )
        )
        new_device_ids = await hass.async_add_executor_job(pca.start_scan)
        # Debug log before saving channel mapping
        _LOGGER.debug(
            f"[PCA301] Vor save_channel_mapping: device={device}, known_devices={pca._known_devices}"
        )
        # Nach Scan: Channel-Mapping in entry.options speichern
        await save_channel_mapping(hass, device, pca._known_devices)
        hass.async_create_task(
            hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": "pca301_scan_in_progress"},
                blocking=False,
            )
        )
        _LOGGER.info("Scan complete, found: %s", new_device_ids)

    _LOGGER.info("Registering scan_for_new_devices service in async_setup_entry")
    hass.services.async_register(
        DOMAIN, "scan_for_new_devices", async_scan_for_new_devices_service
    )

    # Register platforms (e.g. switch)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

# async def async_setup(hass: HomeAssistant, config):
#     """Set up the PCA301 integration (register services globally)."""
#     from .pypca import PCA as ServicePCA

#     _LOGGER = logging.getLogger(__name__)

#     async def async_scan_for_new_devices_service(call):
#         _LOGGER.info("Service pca301.scan_for_new_devices called, starting scan...")
#         device = call.data.get("device")
#         if not device:
#             _LOGGER.warning(
#                 "No device specified for scan_for_new_devices service call."
#             )
#             return
#         pca = ServicePCA(device)
#         await pca.async_load_known_devices(hass)
#         hass.async_create_task(
#             hass.services.async_call(
#                 "persistent_notification",
#                 "create",
#                 {
#                     "title": "PCA301 Scan",
#                     "message": "Scanning for new PCA301 devices. This may take up to 30 seconds. Please wait...",
#                     "notification_id": "pca301_scan_in_progress",
#                 },
#                 blocking=False,
#             )
#         )
#         new_device_ids = await hass.async_add_executor_job(pca.start_scan)
#         hass.async_create_task(
#             hass.services.async_call(
#                 "persistent_notification",
#                 "dismiss",
#                 {"notification_id": "pca301_scan_in_progress"},
#                 blocking=False,
#             )
#         )
#         _LOGGER.info("Scan complete, found: %s", new_device_ids)

#     _LOGGER.info("Registering scan_for_new_devices service in async_setup")
#     hass.services.async_register(
#         DOMAIN, "scan_for_new_devices", async_scan_for_new_devices_service
#     )
#     return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    pca = hass.data[DOMAIN].pop(entry.entry_id, None)
    if pca is not None:
        pca.close()
    return True
