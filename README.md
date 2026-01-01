# PCA301 Home Assistant Integration

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
