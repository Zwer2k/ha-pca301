"""The PCA301 integration."""

import voluptuous as vol

from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

DOMAIN = "pca301"

DEFAULT_DEVICE = "/dev/ttyUSB0"

PCA301_PLATFORMS = [Platform.SWITCH]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the PCA switch platform via YAML."""
    if DOMAIN not in config:
        # Keine YAML-Konfiguration vorhanden, Integration wird ignoriert
        return True

    for platform in PCA301_PLATFORMS:
        discovery.load_platform(
            hass, platform, DOMAIN, {"device": config[DOMAIN][CONF_DEVICE]}, config
        )

    return True


async def async_setup_entry(hass, entry):
    """Set up PCA301 from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PCA301_PLATFORMS)
    return True
