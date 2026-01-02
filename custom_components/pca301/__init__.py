"""The PCA301 integration."""


from homeassistant.const import CONF_DEVICE
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .pypca import PCA

DOMAIN = "pca301"
PLATFORMS = [Platform.SWITCH, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PCA301 from a config entry."""
    port = entry.data.get(CONF_DEVICE) or "/dev/ttyUSB0"
    pca = PCA(hass, port)
    # Load channel mapping from entry.options, if present
    channel_map = entry.options.get("channels")
    if channel_map:
        _LOGGER.info(f"[PCA301] Lade Channel-Mapping aus entry.options: {channel_map}")
        pca.known_devices = channel_map.copy()
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
        # Always use the port from the first loaded config entry
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            _LOGGER.warning("No config entry found for PCA301 scan service.")
            return
        device = entries[0].data.get(CONF_DEVICE) or "/dev/ttyUSB0"
        _LOGGER.info(f"Using port from config entry: {device}")

        # Find the matching config entry to load existing known devices
        config_entry = None
        for entry_tmp in entries:
            if entry.data.get(CONF_DEVICE) == device:
                config_entry = entry_tmp
                break

        pca = PCA(hass, device)

        # Load existing channel mapping from entry.options
        if config_entry and config_entry.options.get("channels"):
            pca.known_devices = config_entry.options["channels"].copy()
            _LOGGER.info(f"Loaded existing channel mapping: {pca.known_devices}")

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
            f"[PCA301] Vor save_channel_mapping: device={device}, known_devices={pca.known_devices}"
        )
        # After scan: Save channel mapping in entry.options
        save_channel_mapping(hass, device, pca.known_devices)
        hass.async_create_task(
            hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": "pca301_scan_in_progress"},
                blocking=False,
            )
        )
        _LOGGER.info("Scan complete, found: %s", new_device_ids)

    # _LOGGER.info("Registering scan_for_new_devices service in async_setup_entry")
    hass.services.async_register(
        DOMAIN, "scan_for_new_devices", async_scan_for_new_devices_service
    )

    # Register platforms (e.g. switch, sensor)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms first
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Then clean up PCA instance
    if unload_ok:
        pca = hass.data[DOMAIN].pop(entry.entry_id, None)
        if pca is not None:
            pca.close()

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a device from the config entry."""
    # Extract device_id from device identifiers
    device_id = None
    for identifier in device_entry.identifiers:
        if identifier[0] == DOMAIN:
            device_id = identifier[1]
            break

    if not device_id:
        return True

    # Remove device from known_devices and channel mapping
    pca = hass.data[DOMAIN].get(config_entry.entry_id)
    if pca and device_id in pca.known_devices:
        del pca.known_devices[device_id]
        _LOGGER.info(f"Removed device {device_id} from known_devices")

    # Update channel mapping in config entry options
    if device_id in config_entry.options.get("channels", {}):
        new_options = dict(config_entry.options)
        new_channels = new_options.get("channels", {}).copy()
        del new_channels[device_id]
        new_options["channels"] = new_channels
        hass.config_entries.async_update_entry(config_entry, options=new_options)
        _LOGGER.info(f"Removed device {device_id} from channel mapping")

    # Device removal from registry is handled automatically by Home Assistant
    return True


def save_channel_mapping(hass, device, known_devices):
    """Speichere das Channel-Mapping für das passende ConfigEntry in entry.options."""
    config_entries = hass.config_entries.async_entries(DOMAIN)
    for config_entry in config_entries:
        if config_entry.data.get(CONF_DEVICE) == device:
            new_channels = known_devices.copy()
            _LOGGER.info(
                f"[PCA301] Speichere Channel-Mapping in entry.options: {new_channels}"
            )
            options = dict(config_entry.options)
            options["channels"] = new_channels
            hass.config_entries.async_update_entry(config_entry, options=options)
            break