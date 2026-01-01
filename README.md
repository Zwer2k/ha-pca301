# PCA301 Home Assistant Integration

This integration allows you to control and monitor ELV PCA301 smart plugs via a serial interface in Home Assistant.

## Features
- Automatic device discovery via serial scan
- Switch control (on/off) for each PCA301 plug
- Power and energy consumption sensors per device
- Channel assignment and diagnostics
- Real-time state updates after switching
- No persistence of device state across restarts (only channel mapping is stored)

## Setup
- Connect your PCA301 USB receiver to the Home Assistant host
- Add the integration via the Home Assistant UI and select the serial port
- Press the button on each PCA301 plug during the scan to pair
- After scan, entities for each device are created automatically

## Notes
- Device state (power, consumption) is only shown immediately after a scan or switching, not persisted across restarts
- Channel mapping is stored for device identification
- For troubleshooting, detailed logs are available in the Home Assistant log

## Supported Entities
- Switch: On/Off control for each plug
- Sensor: Power (W), Consumption (kWh), Channel (diagnostic)

## Limitations
- Only PCA301 devices are supported
- Serial port must be accessible to Home Assistant
- Device state is not restored after Home Assistant restart

---
For more information, see the integration documentation or the code comments.
