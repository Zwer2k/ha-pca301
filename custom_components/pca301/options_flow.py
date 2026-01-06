from homeassistant.config_entries import OptionsFlow
from homeassistant.const import CONF_DEVICE
import voluptuous as vol
import glob
from .const import DEFAULT_DEVICE


class PCA301OptionsFlowHandler(OptionsFlow):
    """Handle an options flow for PCA301."""

    async def async_step_init(self, user_input=None):
        """Manage the options for the serial device."""
        hass = self.hass
        errors = {}
        usb_ports = await hass.async_add_executor_job(glob.glob, "/dev/ttyUSB*")
        acm_ports = await hass.async_add_executor_job(glob.glob, "/dev/ttyACM*")
        serial_ports = usb_ports + acm_ports
        port_options = serial_ports if serial_ports else [DEFAULT_DEVICE]
        # Erst in options, dann in data, dann default
        current_device = self.config_entry.options.get(
            CONF_DEVICE,
            self.config_entry.data.get(CONF_DEVICE, DEFAULT_DEVICE)
        )

        if user_input is not None:
            # Only update if device changed
            if user_input[CONF_DEVICE] != current_device:
                return self.async_create_entry(data={CONF_DEVICE: user_input[CONF_DEVICE]})
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE, default=current_device): vol.In(port_options)
            }),
            errors=errors,
        )
