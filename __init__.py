
"""The PCA301 integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from .pypca import PCA

DOMAIN = "pca301"
PLATFORMS = [Platform.SWITCH]
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PCA301 from a config entry."""
    port = entry.data.get("port") or entry.data.get("device") or "/dev/ttyUSB0"
    pca = PCA(port)
    await pca.async_load_known_devices(hass)
    pca.open()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = pca

    async def async_scan_for_new_devices_service(call):
        _LOGGER.info("Service pca301.scan_for_new_devices called, starting scan...")
        await hass.async_add_executor_job(pca.start_scan)

    hass.services.async_register(
        DOMAIN, "scan_for_new_devices", async_scan_for_new_devices_service
    )

    # Register platforms (e.g. switch)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
