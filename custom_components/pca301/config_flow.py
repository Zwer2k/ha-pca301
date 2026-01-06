"""Config flow for PCA301 integration."""

import asyncio
import contextlib
import glob
import logging


import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigEntry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)


from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE
from homeassistant.core import callback
from homeassistant.data_entry_flow import progress_step
from homeassistant.helpers.selector import TextSelector
from homeassistant.helpers.translation import async_get_cached_translations

from .const import DOMAIN, DEFAULT_DEVICE
from .pypca import PCA
from .options_flow import PCA301OptionsFlowHandler

_LOGGER = logging.getLogger(__name__)


class PCA301ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PCA301."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""
        super().__init__()
        self._selected_device = None

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {"scan_device": PCA301ScanDeviceFlowHandler}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get the options flow handler for PCA301."""
        return PCA301OptionsFlowHandler()

    async def async_step_user(self, user_input=None):
        """Handle the initial step of the config flow."""
        errors = {}
        hass = self.hass
        usb_ports = await hass.async_add_executor_job(glob.glob, "/dev/ttyUSB*")
        acm_ports = await hass.async_add_executor_job(glob.glob, "/dev/ttyACM*")
        serial_ports = usb_ports + acm_ports
        port_options = serial_ports if serial_ports else [DEFAULT_DEVICE]

        if user_input is not None:
            if CONF_DEVICE in user_input:
                self._selected_device = user_input[CONF_DEVICE]
                return await self.async_step_scan_press_button()
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

    async def async_step_scan_press_button(self, user_input=None):
        """Show instructions to press the button on PCA301 before scan."""
        if user_input is not None:
            return await self.async_step_scan()
        return self.async_show_form(
            step_id="scan_press_button",
            description_placeholders={},
            last_step=False,
        )

    @progress_step()
    async def async_step_scan(self, user_input=None):
        """Show sandglass and start scan in background using progress_step decorator."""
        device = getattr(self, "_selected_device", None)
        if device is None:
            return self.async_show_form(
                step_id="user",
                errors={"base": "no_device_selected"},
            )

        # Suche existierenden ConfigEntry für das gewählte device
        config_entries_list = self.hass.config_entries.async_entries(DOMAIN)
        entry_to_reload = None
        for config_entry in config_entries_list:
            if config_entry.data.get(CONF_DEVICE) == device:
                entry_to_reload = config_entry
                break

        # Wenn Integration geladen, temporär entladen
        if entry_to_reload:
            _LOGGER.info(
                f"[PCA301] entry_to_reload.state vor Unload: {entry_to_reload.state}"
            )
        if entry_to_reload and entry_to_reload.state == entry_to_reload.State.LOADED:
            _LOGGER.info(
                f"[PCA301] Unloading integration for port {device} before scan..."
            )
            await self.hass.config_entries.async_unload_entry(entry_to_reload.entry_id)
            _LOGGER.info(
                f"[PCA301] entry_to_reload.state nach Unload: {entry_to_reload.state}"
            )
            # Warten, damit der Port wirklich freigegeben ist
            await asyncio.sleep(1)

        try:
            logger = _LOGGER
            logger.info(f"Starting direct scan for new devices on {device}")
            pca = PCA(self.hass, device)
            await pca.async_load_known_devices(self.hass)
            new_device_ids = await self.hass.async_add_executor_job(pca.start_scan)
            logger.info(f"Direct scan complete, found: {new_device_ids}")
            try:
                pca.close()
            except Exception as close_err:
                logger.warning(f"Error closing serial port after scan: {close_err}")

            # Speichere Channel-Mapping direkt
            if entry_to_reload:
                new_channels = pca.known_devices.copy()
                _LOGGER.info(
                    f"[PCA301] Speichere Channel-Mapping in entry.options: {new_channels}"
                )
                options = dict(entry_to_reload.options)
                options["channels"] = new_channels
                self.hass.config_entries.async_update_entry(
                    entry_to_reload, options=options
                )

            _LOGGER.info(
                f"[PCA301] Gerätezustände nach Scan (ConfigFlow): _devices={pca._devices}"
            )
        except Exception as err:
            _LOGGER.error("Direct scan failed: %s", err)
            # Nach Fehler Integration ggf. wieder laden
            if (
                entry_to_reload
                and entry_to_reload.state == entry_to_reload.State.NOT_LOADED
            ):
                await self.hass.config_entries.async_setup(entry_to_reload.entry_id)
            return self.async_show_form(
                step_id="user",
                errors={"base": "scan_failed"},
            )

        # Nach Scan Integration wieder laden
        if (
            entry_to_reload
            and entry_to_reload.state == entry_to_reload.State.NOT_LOADED
        ):
            _LOGGER.info(
                f"[PCA301] entry_to_reload.state vor Reload: {entry_to_reload.state}"
            )
            _LOGGER.info(
                f"[PCA301] Reloading integration for port {device} after scan..."
            )
            await self.hass.config_entries.async_setup(entry_to_reload.entry_id)
            _LOGGER.info(
                f"[PCA301] entry_to_reload.state nach Reload: {entry_to_reload.state}"
            )

        return self.async_create_entry(
            title="PCA301",
            data={CONF_DEVICE: self._selected_device},
            options={
                "devices": new_device_ids,
                "channels": pca.known_devices.copy(),
            },
        )

    # The scan_for_new_devices step is not needed with progress_step pattern and can be removed.


class PCA301ScanDeviceFlowHandler(ConfigSubentryFlow):
    """Handle PCA301 scan device subentry flow."""

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> SubentryFlowResult:
        """Start the scan flow - redirects to scan_device step."""
        return await self.async_step_scan_device(user_input)

    async def async_step_scan_device(
        self, user_input: dict | None = None
    ) -> SubentryFlowResult:
        """Show instructions to press the button on PCA301 before scan."""
        if user_input is not None:
            return await self.async_step_scan_for_new_devices()

        return self.async_show_form(
            step_id="scan_device",
            description_placeholders={},
            last_step=False,
        )

    @progress_step()
    async def async_step_scan_for_new_devices(
        self, user_input: dict | None = None
    ) -> SubentryFlowResult:
        """Scan and show device list directly after scan."""
        # Get parent config entry using _get_entry()
        config_entry = self._get_entry()

        device = config_entry.data.get(CONF_DEVICE)
        if not device:
            return self.async_abort(reason="no_device")

        # Unload integration before scan to free serial port
        await self.hass.config_entries.async_unload(config_entry.entry_id)
        await asyncio.sleep(1)

        try:
            pca = PCA(self.hass, device)
            # Load existing channel mapping
            existing_channels = config_entry.options.get("channels", {}).copy()
            if existing_channels:
                pca.known_devices = existing_channels.copy()
                _LOGGER.info(f"Loaded existing channel mapping: {pca.known_devices}")

            new_device_ids = await self.hass.async_add_executor_job(pca.start_scan)
            _LOGGER.info(f"Scan complete, found: {new_device_ids}")

            # Merge new channels with existing channels
            merged_channels = existing_channels.copy()
            merged_channels.update(pca.known_devices)

            new_options = dict(config_entry.options)
            new_options["channels"] = merged_channels

            self.hass.config_entries.async_update_entry(
                config_entry, options=new_options
            )

            with contextlib.suppress(Exception):
                pca.close()

        except Exception as err:
            _LOGGER.error("Scan failed: %s", err)
        finally:
            # Reload integration after scan only if NOT_LOADED
            if config_entry.state == ConfigEntryState.NOT_LOADED:
                await self.hass.config_entries.async_setup(config_entry.entry_id)

        # Always show all known devices after scan
        pca = self.hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
        all_devices = []
        if pca and hasattr(pca, "get_devices"):
            all_devices = list(pca.get_devices().keys())

        device_list = "\n".join(all_devices) if all_devices else ""

        return self.async_abort(
            reason="scan_result",
            description_placeholders={"device_list": device_list},
        )

