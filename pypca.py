"""PCA301 serial protocol handler for Home Assistant integration.

This module provides the PCA class for managing PCA301 smart plugs via serial communication,
including device discovery, state updates, and integration with Home Assistant registries.
"""

import logging
import re
import threading
from pathlib import Path
from time import time

import asyncio
import serial

from homeassistant.helpers import (
    entity_registry as er,
    device_registry as dr,
)

SEND_SUFFIX = "s"

_LOGGER = logging.getLogger(__name__)
home = str(Path.home())


class PCA:
    _hass = None
    _serial = None
    _stopevent = None
    _thread = None
    _re_reading = re.compile(
        r"OK 24 (\d+) 4 (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)"
    )
    _re_devices = re.compile(
        r"L 24 (\d+) (\d+) : (\d+) 4 (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)"
    )

    def __init__(self, hass, port, timeout=2):
        self._devices = {}
        self._hass = hass
        self._port = port
        self._baud = 57600
        self._timeout = timeout
        self._serial = serial.Serial(timeout=timeout)
        self._known_devices = {}  # deviceId: channel

    async def async_load_known_devices(self, hass):
        # No-op: Devices will be loaded from the Home Assistant device registry or entry.options.
        pass

    def open(self):
        _LOGGER.info(f"Opening serial port {self._port}")
        try:
            if self._serial.is_open:
                _LOGGER.warning(
                    f"Serial port {self._port} already open, closing first."
                )
                self._serial.close()
            self._serial.port = self._port
            self._serial.baudrate = self._baud
            self._serial.timeout = self._timeout
            self._serial.open()
            # self._serial.flushInput()
            # self._serial.flushOutput()
            self.get_ready()
            _LOGGER.info(f"Serial port {self._port} opened and ready.")
            self._start_worker()
        except serial.SerialException as e:
            _LOGGER.error(f"Error opening serial port {self._port}: {e}")
            try:
                self._serial.close()
            except Exception:
                pass
            raise

    def close(self):
        _LOGGER.info(f"Closing serial port {self._port}")
        self._stop_worker()
        try:
            if self._serial.is_open:
                self._serial.close()
                _LOGGER.info(f"Serial port {self._port} closed.")
        except Exception as e:
            _LOGGER.warning(f"Error closing serial port {self._port}: {e}")

    def get_ready(self):
        try:
            line = self._serial.readline().decode("utf-8")
            start = time()
            timeout = 2
            while self._re_reading.match(line) is None and time() - start < timeout:
                line = self._serial.readline().decode("utf-8")
            return True
        except serial.SerialException as e:
            _LOGGER.error(f"Error reading from serial port: {e}")
            try:
                self._serial.close()
            except Exception:
                pass
            raise

    def get_devices(self):
        """Gibt die aktuelle Geräteliste zurück (ohne Scan)."""
        # Wenn _devices leer ist, aus _known_devices bauen
        if not self._devices and self._known_devices:
            for device, channel in self._known_devices.items():
                self._devices[device] = {
                    "state": 0,
                    "consumption": 0,
                    "power": 0,
                    "channel": channel,
                }
        return self._devices

    def get_current_power(self, deviceId):
        return self._devices[deviceId]["power"]

    def get_total_consumption(self, deviceId):
        return self._devices[deviceId]["consumption"]

    def get_state(self, deviceId):
        # Return None if device or state is missing to avoid KeyError
        device = self._devices.get(deviceId)
        if device is None:
            return None
        return device.get("state")

    def _stop_worker(self):
        if self._stopevent is not None:
            self._stopevent.set()
        if self._thread is not None:
            self._thread.join()

    def start_scan(self, fast=0):
        """Starte das Scannen nach neuen Geräten (Discovery). Gibt Liste neuer Geräte-IDs zurück."""
        _LOGGER.info("Please press the button on your PCA")
        self._stop_worker()

        # Ensure serial port is open
        if not self._serial.is_open:
            try:
                self.open()
            except Exception as e:
                _LOGGER.error(f"Could not open serial port {self._port}: {e}")
                return []
        start = int(time())
        found = False
        DISCOVERY_TIME = 5 if fast else 15
        DISCOVERY_TIMEOUT = 5 if fast else 30
        _LOGGER.debug("Known devices before scan: %s", list(self._known_devices.keys()))
        _LOGGER.debug("Devices before scan: %s", list(self._devices.keys()))

        # Vorhandene Geräte initialisieren
        for device, channel in self._known_devices.items():
            self._devices[device] = {}
            self._devices[device]['state'] = 0
            self._devices[device]['consumption'] = 0
            self._devices[device]['power'] = 0
            self._devices[device]['channel'] = channel
        new_device_ids = []
        while not (int(time()) - start > DISCOVERY_TIMEOUT) or not (
            int(time()) - start > DISCOVERY_TIME or found
        ):
            try:
                raw_line = self._serial.readline().decode("utf-8")
            except Exception as e:
                _LOGGER.error(f"Error reading from serial port: {e}")
                continue
            line_stripped = raw_line.strip()
            if len(line_stripped) < 2:
                continue
            _LOGGER.debug(f"Received line: {line_stripped}")
            line = line_stripped.split(" ")
            _LOGGER.debug(f"Parsed line: {line}")

            if len(line) > 12:
                while line[0] != "OK" and len(line) >= 12:
                    line.pop(0)
                    continue

            if len(line) < 12:
                _LOGGER.warning(f"Malformed device response (too short): {line}")
                continue

            try:
                if line[8] != '170' or line[9] != '170':
                    deviceId = str(line[4]).zfill(3) + str(line[5]).zfill(3) + str(line[6]).zfill(3)
                    channel = line[2]  # Channel ist an Position 2 laut PCA301 Protokoll
                    self._devices[deviceId] = {}
                    self._devices[deviceId]["power"] = (int(line[8]) * 256 + int(line[9])) / 10.0
                    self._devices[deviceId]["state"] = int(line[7])
                    self._devices[deviceId]["consumption"] = (int(line[10]) * 256 + int(line[11])) / 100.0
                    self._devices[deviceId]["channel"] = channel
                    if deviceId in self._known_devices:
                        _LOGGER.info(f"Skip device with ID {deviceId}, because it's already known.")
                    else:
                        _LOGGER.info(f"New device found: {deviceId} (channel {channel}), will wait for another device for {DISCOVERY_TIME} seconds...")
                        self._known_devices[deviceId] = channel
                        new_device_ids.append(deviceId)
                        found = True
                        start = time()
            except Exception as e:
                _LOGGER.error(f"Error parsing device response: {line} - {e}")
                continue
        _LOGGER.info(f"Devices found: {list(self._devices.keys())}")
        self._start_worker()
        return new_device_ids

    def _write_cmd(self, cmd):
        _LOGGER.info(f"Sending command to PCA301: {cmd}")
        try:
            # Konvertiere die Bytes zu einem String mit Leerzeichen-Trennung, nur 's' als Suffix (kein Newline)
            cmd_str = ",".join(str(b) for b in cmd) + "s"
            _LOGGER.info(f"Command string to send: {repr(cmd_str)}")
            self._serial.write(cmd_str.encode('ascii'))
            _LOGGER.info(f"Command sent successfully")
        except Exception as e:
            _LOGGER.error(f"Error sending command: {e}")
            return

    def _start_worker(self):
        if self._thread is not None:
            return
        self._stopevent = threading.Event()
        self._thread = threading.Thread(target=self._refresh, args=())
        self._thread.daemon = True
        self._thread.start()

    def turn_off(self, deviceId):
        # deviceId ist ein 9-stelliger String, z.B. '009088163'
        channel = self._known_devices.get(deviceId, '01')
        addr1 = int(deviceId[0:3])
        addr2 = int(deviceId[3:6])
        addr3 = int(deviceId[6:9])
        chan = int(channel, 16) if isinstance(channel, str) else int(channel)
        cmd = [chan, 5, addr1, addr2, addr3, 0, 255, 255, 255, 255]
        _LOGGER.info(f"Turning OFF PCA301 device {deviceId} channel {channel} with command: {cmd}")
        self._write_cmd(cmd)
        self._devices[deviceId]["state"] = 0
        _LOGGER.info(f"PCA301 device {deviceId} state set to OFF")
        return True

    def turn_on(self, deviceId):
        # deviceId ist ein 9-stelliger String, z.B. '009088163'
        channel = self._known_devices.get(deviceId, '01')
        addr1 = int(deviceId[0:3])
        addr2 = int(deviceId[3:6])
        addr3 = int(deviceId[6:9])
        chan = int(channel, 16) if isinstance(channel, str) else int(channel)
        cmd = [chan, 5, addr1, addr2, addr3, 1, 255, 255, 255, 255]
        _LOGGER.info(f"Turning ON PCA301 device {deviceId} channel {channel} with command: {cmd}")
        self._write_cmd(cmd)
        self._devices[deviceId]["state"] = 1
        _LOGGER.info(f"PCA301 device {deviceId} state set to ON")
        return True

    def _refresh(self):
        while not self._stopevent.isSet():
            if not self._serial or not self._serial.is_open:
                _LOGGER.warning("Serial port closed, refresh thread exiting.")
                break
            try:
                line = self._serial.readline()
                try:
                    line = line.encode().decode("utf-8")
                except AttributeError:
                    line = line.decode("utf-8")
                if self._re_reading.match(line):
                    line = line.split(" ")
                    deviceId = (
                        str(line[4]).zfill(3)
                        + str(line[5]).zfill(3)
                        + str(line[6]).zfill(3)
                    )
                    # Ensure device dict exists
                    if deviceId not in self._devices:
                        self._devices[deviceId] = {
                            "state": None,
                            "power": None,
                            "consumption": None,
                            "channel": None,
                        }
                    self._devices[deviceId]["power"] = (
                        int(line[8]) * 256 + int(line[9])
                    ) / 10.0
                    self._devices[deviceId]["state"] = int(line[7])
                    self._devices[deviceId]["consumption"] = (
                        int(line[10]) * 256 + int(line[11])
                    ) / 100.0
                    # Notify Home Assistant to enable entities for this device
                    if hasattr(self, "_hass") and self._hass:
                        self.notify_new_data(self._hass, deviceId)
            except serial.SerialException as e:
                _LOGGER.warning(
                    f"Serial exception in refresh thread: {e}, exiting thread."
                )
                break
            except Exception as e:
                _LOGGER.error(f"Unexpected exception in refresh thread: {e}")

    def notify_new_data(self, hass, device_id):
        """Enable entities for a device when new data is received."""

        async def _enable_entities():
            entity_registry = er.async_get(hass)
            device_registry = dr.async_get(hass)
            # Find the device entry for this device_id
            target_device = None
            for device in device_registry.devices.values():
                for ident in device.identifiers:
                    if ident[0] == "pca301" and ident[1] == device_id:
                        target_device = device
                        break
                if target_device:
                    break
            if not target_device:
                return
            # Enable all entities for this device
            for entity in list(entity_registry.entities.values()):
                if (
                    entity.device_id == target_device.id
                    and entity.disabled_by is not None
                ):
                    entity_registry.async_update_entity(
                        entity.entity_id, disabled_by=None
                    )

        # Schedule the enabling in the event loop in a thread-safe way
        hass.loop.call_soon_threadsafe(lambda: asyncio.create_task(_enable_entities()))

    def status_request(self, deviceId, timeout=2):
        """Send a status request command to the device and wait for a fresh response."""
        channel = self._known_devices.get(deviceId, "01")
        addr1 = int(deviceId[0:3])
        addr2 = int(deviceId[3:6])
        addr3 = int(deviceId[6:9])
        chan = int(channel, 16) if isinstance(channel, str) else int(channel)
        # Command: [channel, 4, addr1, addr2, addr3, 0, 255, 255, 255, 255]
        cmd = [chan, 4, addr1, addr2, addr3, 0, 255, 255, 255, 255]
        self._write_cmd(cmd)
        # Wait for a new value in self._devices[deviceId]["state"]
        start = time()
        last_state = self._devices.get(deviceId, {}).get("state")
        while time.time() - start < timeout:
            new_state = self._devices.get(deviceId, {}).get("state")
            if new_state != last_state:
                return True
            time.sleep(0.05)
        return False
