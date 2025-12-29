"""Config flow for PCA301 integration."""

import voluptuous as vol
import glob
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_DEVICE
from .const import DOMAIN, DEFAULT_DEVICE
from homeassistant.helpers.translation import async_get_cached_translations
from homeassistant.helpers.selector import TextSelector

class PCA301ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PCA301."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PCA301OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}
        from .serial_helper import list_serial_ports
        hass = self.hass
        usb_ports = await hass.async_add_executor_job(glob.glob, '/dev/ttyUSB*')
        acm_ports = await hass.async_add_executor_job(glob.glob, '/dev/ttyACM*')
        serial_ports = usb_ports + acm_ports
        port_options = serial_ports if serial_ports else [DEFAULT_DEVICE]

        if user_input is not None:
            return self.async_create_entry(title="PCA301", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE, default=port_options[0]): vol.In(
                        port_options
                    )
                }
            ),
            errors=errors,
        )


class PCA301OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init", menu_options=["scan_for_new_devices"]
        )

    async def async_step_scan_for_new_devices(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data={})

        await self.hass.services.async_call(
            DOMAIN,
            "scan_for_new_devices",
            {"entry_id": self._config_entry.entry_id},
            blocking=True,
        )
        # Always show all known devices after scan
        pca = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id)
        all_devices = []
        if pca and hasattr(pca, "get_devices"):
            all_devices = list(pca.get_devices().keys())

        language = self.hass.config.language or "en"
        translations = async_get_cached_translations(
            self.hass, language, "options", DOMAIN
        )
        found_devices_text = translations.get(
            f"component.{DOMAIN}.options.step.scan_for_new_devices.found_devices",
            "Gefundene Geräte:",
        )
        no_devices_text = translations.get(
            f"component.{DOMAIN}.options.step.scan_for_new_devices.no_devices",
            "Keine Geräte gefunden.",
        )
        if all_devices:
            info_text = found_devices_text + "\n" + "\n".join(all_devices)
        else:
            info_text = no_devices_text
        return self.async_show_form(
            step_id="scan_for_new_devices",
            data_schema=vol.Schema(
                {
                    vol.Optional("info", default=info_text): TextSelector(
                        {"multiline": True}
                    )
                }
            ),
        )
