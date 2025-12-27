import glob

def list_serial_ports():
    """List available serial ports on Linux (sync)."""
    return glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
