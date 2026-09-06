
# Home Assistant Integration for ELV PCA301 smart plugs

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/Zwer2k/ha-pca301.svg)](https://github.com/Zwer2k/ha-pca301/releases)
[![License](https://img.shields.io/github/license/Zwer2k/ha-pca301.svg)](LICENSE)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/Zwer2k/ha-pca301/graphs/commit-activity)

## Installation via HACS
1. Go to HACS → Integrations in Home Assistant.
2. Click the three dots in the top right → "Custom repositories".
3. Enter `https://github.com/Zwer2k/ha-pca301` as the repository URL and select "Integration".
4. Click "Add" and install the integration.
5. Restart Home Assistant.

---

This integration allows you to control and monitor ELV PCA301 smart plugs via a serial interface in Home Assistant.

## Setup (Initial Installation)
1. Connect the PCA301 USB receiver to your Home Assistant system.
2. Add the integration via Settings → Devices & Services → Add Integration and select the correct serial port.
3. During setup, you will be prompted to press the button on each PCA301 plug to pair it.
4. After the scan, entities for all discovered devices are created automatically.

## Add Devices Later (Subentry Flow)
To add more PCA301 plugs later, use the new **Subentry Flow**:
- Open the integration in Home Assistant (Settings → Devices & Services).
- Click the three dots at the top right of the PCA301 integration.
- Select **"Scan for devices"**.
- During the scan window, press the button on each new plug you want to add.
- After the scan completes, the new devices will automatically appear as entities.

**Note:** The classic options dialog is no longer used. Device scanning is now available directly via the subentry button next to the integration title.

## Notes
- Device scanning is possible at any time via the subentry button.
- Channel mapping is stored persistently.
- For troubleshooting, see the Home Assistant log.

## Supported Entities
- Switch: On/Off control for each plug
- Sensor: Power (W), Consumption (kWh), Channel (diagnostic)
- Switch: Always Power On (per-device setting, visible in device controls)
- Number: Auto On Delay (1-60s, per-device setting, visible in device controls)
- Number: Availability Timeout (10-600s, per-device setting, hidden by default)

## Features

### Always Power On
Each PCA301 device can be configured to automatically turn back ON when it reports OFF:
- Enable the **Always Power On** switch in the device controls
- Configure the **Auto On Delay** (default: 5 seconds)
- The device will automatically turn back on after the delay if it reports OFF and was not manually turned off

### Availability Timeout
The integration tracks when each device was last seen:
- If no message is received within the timeout, the entity becomes **unavailable**
- This prevents stale states when a device loses power
- The timeout is configurable per device (default: 120 seconds)
- The **Availability Timeout** number entity is hidden by default and can be enabled manually if needed

### Persistent Serial Paths
The integration supports persistent serial device paths:
- `/dev/serial/by-id/*` paths are preferred over `/dev/ttyUSB*` or `/dev/ttyACM*`
- This prevents issues when USB device numbers change after reboots or replugging

## Limitations
- Only PCA301 devices are supported
- Serial port must be accessible to Home Assistant

---

For more information, see the code comments or the documentation in this repository.
