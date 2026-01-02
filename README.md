
# PCA301 Home Assistant Integration

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

## Limitations
- Only PCA301 devices are supported
- Serial port must be accessible to Home Assistant

---

For more information, see the code comments or the documentation in this repository.
