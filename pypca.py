from pathlib import Path
from time import time
import logging
import serial
import re
import threading
import json

SEND_SUFFIX = "s"

_LOGGER = logging.getLogger(__name__)
home = str(Path.home())

class PCA:
    _serial = None
    _stopevent = None
    _thread = None
    _re_reading = re.compile(r"OK 24 (\d+) 4 (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)")
    _re_devices = re.compile(r"L 24 (\d+) (\d+) : (\d+) 4 (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)")
    DEVICES_FILE = None  # Wird dynamisch gesetzt

    def __init__(self, port, timeout=2):
        self._devices = {}
        self._port = port
        self._baud = 57600
        self._timeout = timeout
        self._serial = serial.Serial(timeout=timeout)
        self._known_devices = {}  # deviceId: channel

    async def async_load_known_devices(self, hass):
        # Setze DEVICES_FILE auf das HA-Config-Verzeichnis
        self.DEVICES_FILE = hass.config.path(".pca_devices.json")
        def _load_known_devices():
            try:
                _LOGGER.info(f"Trying to read PCA devices file at: {self.DEVICES_FILE}")
                with open(self.DEVICES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                _LOGGER.info(f"Successfully read PCA devices file at: {self.DEVICES_FILE}")
                return data
            except Exception as e:
                _LOGGER.warning(f"Could not read PCA devices file at: {self.DEVICES_FILE}: {e}")
                return {}
        def _write_known_devices():
            try:
                _LOGGER.info(f"Writing PCA devices file at: {self.DEVICES_FILE}")
                with open(self.DEVICES_FILE, "w", encoding="utf-8") as f:
                    json.dump(self._known_devices, f, ensure_ascii=False, indent=2)
                _LOGGER.info(f"Successfully wrote PCA devices file at: {self.DEVICES_FILE}")
            except Exception as e:
                _LOGGER.error(f"Could not write PCA devices file at: {self.DEVICES_FILE}: {e}")
        self._known_devices = await hass.async_add_executor_job(_load_known_devices)
        if not self._known_devices:
            # Datei anlegen, falls sie nicht existiert
            await hass.async_add_executor_job(_write_known_devices)

    def open(self):
        _LOGGER.info(f"Opening serial port {self._port}")
        self._serial.port = self._port
        self._serial.baudrate = self._baud
        self._serial.timeout = self._timeout
        self._serial.open()
        self._serial.flushInput()
        self._serial.flushOutput()
        self.get_ready()
        _LOGGER.info(f"Serial port {self._port} opened and ready.")
        self._start_worker()

    def close(self):
        _LOGGER.info(f"Closing serial port {self._port}")
        self._stop_worker()
        self._serial.close()
        _LOGGER.info(f"Serial port {self._port} closed.")

    def get_ready(self):
        line = self._serial.readline().decode("utf-8")
        start = time()
        timeout = 2
        while self._re_reading.match(line) is None and time() - start < timeout:
            line = self._serial.readline().decode("utf-8")
        return True

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
        return self._devices[deviceId]["state"]

    def _stop_worker(self):
        if self._stopevent is not None:
            self._stopevent.set()
        if self._thread is not None:
            self._thread.join()

    def start_scan(self, fast=0):
        """Starte das Scannen nach neuen Geräten (Discovery)."""
        _LOGGER.info("Please press the button on your PCA")
        self._stop_worker()

        # Ensure serial port is open
        if not self._serial.is_open:
            try:
                self.open()
            except Exception as e:
                _LOGGER.error(f"Could not open serial port {self._port}: {e}")
                return
        line = []
        start = int(time())
        found = False
        DISCOVERY_TIME = 5 if fast else 15
        DISCOVERY_TIMEOUT = 5 if fast else 30
        # Vorhandene Geräte initialisieren
        for device, channel in self._known_devices.items():
            self._devices[device] = {}
            self._devices[device]['state'] = 0
            self._devices[device]['consumption'] = 0
            self._devices[device]['power'] = 0
            self._devices[device]['channel'] = channel
        while not (int(time()) - start > DISCOVERY_TIMEOUT) or not (int(time()) - start > DISCOVERY_TIME or found):
            line = self._serial.readline().decode("utf-8")
            _LOGGER.debug(f"Received line: {line.strip()}")
            if len(line) > 1:
                line = line.split(" ")
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
                        found = True
                        start = time()
        try:
            _LOGGER.info(f"Writing PCA devices file at: {self.DEVICES_FILE}")
            with open(self.DEVICES_FILE, "w", encoding="utf-8") as f:
                json.dump(self._known_devices, f, ensure_ascii=False, indent=2)
            _LOGGER.info(f"Successfully wrote PCA devices file at: {self.DEVICES_FILE}")
        except Exception as e:
            _LOGGER.error(f"Could not write PCA devices file at: {self.DEVICES_FILE}: {e}")
        _LOGGER.info(f"Devices found: {list(self._devices.keys())}")
        self._start_worker()

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
                    self._devices[deviceId]["power"] = (
                        int(line[8]) * 256 + int(line[9])
                    ) / 10.0
                    self._devices[deviceId]["state"] = int(line[7])
                    self._devices[deviceId]["consumption"] = (
                        int(line[10]) * 256 + int(line[11])
                    ) / 100.0
            except serial.SerialException as e:
                _LOGGER.warning(
                    f"Serial exception in refresh thread: {e}, exiting thread."
                )
                break
            except Exception as e:
                _LOGGER.error(f"Unexpected exception in refresh thread: {e}")
