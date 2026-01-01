"""Config flow for PCA301 integration."""

import glob
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_DEVICE
from .const import DOMAIN, DEFAULT_DEVICE

from homeassistant.helpers.translation import async_get_cached_translations
from homeassistant.helpers.selector import TextSelector
from homeassistant.data_entry_flow import progress_step


class PCA301ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PCA301."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler for PCA301."""
        return PCA301OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step of the config flow."""
        errors = {}
        hass = self.hass
        usb_ports = await hass.async_add_executor_job(glob.glob, '/dev/ttyUSB*')
        acm_ports = await hass.async_add_executor_job(glob.glob, '/dev/ttyACM*')
        serial_ports = usb_ports + acm_ports
        port_options = serial_ports if serial_ports else [DEFAULT_DEVICE]

        if user_input is not None:
            if CONF_DEVICE in user_input:
                # After selecting device, go to scan step
                self._selected_device = user_input[CONF_DEVICE]
                return await self.async_step_scan()
            else:
                errors["base"] = "no_device_selected"

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

    @progress_step()
    async def async_step_scan(self, user_input=None):
        """Show sandglass and start scan in background using progress_step decorator."""
        device = getattr(self, "_selected_device", None)
        if device is None:
            # Show error if device is not set
            return self.async_show_form(
                step_id="user",
                errors={"base": "no_device_selected"},
            )
        try:
            from .pypca import PCA
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"Starting direct scan for new devices on {device}")
            pca = PCA(self.hass, device)
            await pca.async_load_known_devices(self.hass)
            new_device_ids = await self.hass.async_add_executor_job(pca.start_scan)
            logger.info(f"Direct scan complete, found: {new_device_ids}")
            # Ensure serial port is closed after scan to avoid multiple access
            try:
                pca.close()
            except Exception as close_err:
                logger.warning(f"Error closing serial port after scan: {close_err}")
            # Persistiere Channel-Mapping (auch für initialen Flow!)
            from . import save_channel_mapping

            logger.debug(
                f"[PCA301] Vor save_channel_mapping (ConfigFlow): device={device}, known_devices={pca._known_devices}"
            )
            await save_channel_mapping(self.hass, device, pca._known_devices)
        except Exception as err:
            import logging

            logging.getLogger(__name__).error("Direct scan failed: %s", err)
            return self.async_show_form(
                step_id="user",
                errors={"base": "scan_failed"},
            )
        # Persist found devices and channel mapping to options so async_setup_entry kann sie nutzen
        return self.async_create_entry(
            title="PCA301",
            data={CONF_DEVICE: self._selected_device},
            options={
                "devices": new_device_ids,
                "channels": pca._known_devices.copy(),
            },
        )

    # The scan_for_new_devices step is not needed with progress_step pattern and can be removed.


class PCA301OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler for PCA301 integration."""

    def __init__(self, config_entry):
        """Initialize the options flow handler."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Show the options menu."""
        return self.async_show_menu(
            step_id="init", menu_options=["scan_for_new_devices"]
        )

    async def async_step_scan_for_new_devices(self, user_input=None):
        """Handle scanning for new devices in options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data={})

        device = self._config_entry.data.get("device")
        if device:
            await self.hass.services.async_call(
                DOMAIN,
                "scan_for_new_devices",
                {"device": device},
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
