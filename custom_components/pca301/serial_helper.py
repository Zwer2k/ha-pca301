"""Serial port helper utilities."""

from pathlib import Path


def list_serial_ports():
    """List available serial ports on Linux (sync)."""
    return [str(p) for p in Path("/dev").glob("ttyUSB*")] + [str(p) for p in Path("/dev").glob("ttyACM*")]
