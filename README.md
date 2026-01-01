# PCA301 Home Assistant Integration

## Installation via HACS
This integration can be installed using [HACS](https://hacs.xyz/):

1. Go to HACS → Integrations in your Home Assistant UI.
2. Click the three dots (menu) in the top right and select "Custom repositories".
3. Enter `https://github.com/Zwer2k/ha-pca301` as the repository URL and select "Integration" as the category.
4. Click "Add". The PCA301 integration will now appear in the HACS list.
5. Click "Install" on the PCA301 integration entry.
6. Restart Home Assistant after installation.
7. Continue with the setup as described below.

---

This integration allows you to control and monitor ELV PCA301 smart plugs via a serial interface in Home Assistant.

## Setup (Standard Method)
1. Connect the PCA301 USB receiver to your Home Assistant host.
2. Add the integration via the Home Assistant UI (Settings → Devices & Services → Add Integration) and select the correct serial port.
3. During setup, you will be prompted to press the button on each PCA301 plug to pair it.
4. After the scan, entities for each discovered device are created automatically.

## Add Devices Later (via Options/Gear)
If you want to add more PCA301 plugs later, you do not need to remove the integration. Instead, open the integration in Home Assistant and click the gear (Options) icon. There you can start a new scan:

- Click the gear icon on the PCA301 integration.
- Start the scan for new devices.
- During the scan window, press the button on each new plug you want to add.
- After the scan completes, the new devices will appear as entities automatically.

Alternatively, you can use the service:

### Scan for New Devices (Service)
You can trigger a scan for new PCA301 plugs at any time using the built-in service:

- **Service:** `pca301.scan_for_new_devices`

**How to use:**
1. Go to Developer Tools → Services in Home Assistant.
2. Select `pca301.scan_for_new_devices`.
3. Start the service. The serial port from the integration settings will always be used automatically.
4. During the scan window, press the button on each plug you want to add.
5. Wait for the notification that the scan is complete. New devices will appear as entities.

## Notes
- Device state (power, consumption) is only shown immediately after a scan or switching, not persisted across restarts.
- Channel mapping is stored for device identification.
- For troubleshooting, detailed logs are available in the Home Assistant log.

## Supported Entities
- Switch: On/Off control for each plug
- Sensor: Power (W), Consumption (kWh), Channel (diagnostic)

## Limitations
- Only PCA301 devices are supported
- Serial port must be accessible to Home Assistant

---
For more information, see the integration documentation or the code comments.
