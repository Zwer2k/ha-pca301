"""Config flow for PCA301 integration."""

import voluptuous as vol
import glob
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_DEVICE
from .const import DOMAIN, DEFAULT_DEVICE

class PCA301ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PCA301."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

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
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE, default=port_options[0]): vol.In(port_options)
            }),
            errors=errors,
        )
