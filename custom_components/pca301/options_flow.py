from homeassistant.config_entries import OptionsFlow
from homeassistant.const import CONF_DEVICE
import voluptuous as vol
import glob
from .const import (
    DEFAULT_DEVICE,
    CONF_ALWAYS_POWER_ON,
    CONF_AUTO_ON_DELAY,
    DEFAULT_AUTO_ON_DELAY,
    CONF_AVAILABILITY_TIMEOUT,
    DEFAULT_AVAILABILITY_TIMEOUT,
)


class PCA301OptionsFlowHandler(OptionsFlow):
    """Handle an options flow for PCA301."""

    async def async_step_init(self, user_input=None):
        """Manage the options for the serial device."""
        hass = self.hass
        errors = {}
        # Persistente /dev/serial/by-id Pfade bevorzugen
        byid_ports = await hass.async_add_executor_job(glob.glob, "/dev/serial/by-id/*")
        usb_ports = await hass.async_add_executor_job(glob.glob, "/dev/ttyUSB*")
        acm_ports = await hass.async_add_executor_job(glob.glob, "/dev/ttyACM*")
        # by-id zuerst, dann ttyUSB, dann ttyACM — und Duplikate entfernen
        serial_ports = list(dict.fromkeys(byid_ports + usb_ports + acm_ports))
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
            return await self.async_step_device_options()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE, default=current_device): vol.In(port_options)
            }),
            errors=errors,
        )

    async def async_step_device_options(self, user_input=None):
        """Configure device-specific options (Always Power On, Availability)."""
        channels = self.config_entry.options.get("channels", {})
        device_ids = list(channels.keys())

        if not device_ids:
            return self.async_show_form(
                step_id="device_options",
                data_schema=vol.Schema({}),
                errors={"base": "no_devices"},
            )

        # Für jedes Gerät eine eigene Sektion mit Optionen
        schema = {}
        for device_id in device_ids:
            current_config = channels.get(device_id, {})
            if not isinstance(current_config, dict):
                current_config = {}

            key_prefix = f"{device_id}_"
            schema[vol.Required(
                f"{key_prefix}{CONF_ALWAYS_POWER_ON}",
                default=current_config.get(CONF_ALWAYS_POWER_ON, False)
            )] = bool
            schema[vol.Optional(
                f"{key_prefix}{CONF_AUTO_ON_DELAY}",
                default=current_config.get(CONF_AUTO_ON_DELAY, DEFAULT_AUTO_ON_DELAY)
            )] = vol.All(vol.Coerce(int), vol.Range(min=1, max=60))
            schema[vol.Optional(
                f"{key_prefix}{CONF_AVAILABILITY_TIMEOUT}",
                default=current_config.get(CONF_AVAILABILITY_TIMEOUT, DEFAULT_AVAILABILITY_TIMEOUT)
            )] = vol.All(vol.Coerce(int), vol.Range(min=10, max=300))

        if user_input is not None:
            # Neue Optionen speichern
            new_options = dict(self.config_entry.options)
            new_channels = {}

            for device_id in device_ids:
                key_prefix = f"{device_id}_"
                new_channels[device_id] = {
                    CONF_ALWAYS_POWER_ON: user_input.get(
                        f"{key_prefix}{CONF_ALWAYS_POWER_ON}", False
                    ),
                    CONF_AUTO_ON_DELAY: user_input.get(
                        f"{key_prefix}{CONF_AUTO_ON_DELAY}", DEFAULT_AUTO_ON_DELAY
                    ),
                    CONF_AVAILABILITY_TIMEOUT: user_input.get(
                        f"{key_prefix}{CONF_AVAILABILITY_TIMEOUT}", DEFAULT_AVAILABILITY_TIMEOUT
                    ),
                }

            new_options["channels"] = new_channels
            return self.async_create_entry(data=new_options)

        return self.async_show_form(
            step_id="device_options",
            data_schema=vol.Schema(schema),
            description_placeholders={"device_count": str(len(device_ids))},
        )
