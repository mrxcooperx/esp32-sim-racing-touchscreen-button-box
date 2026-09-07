"""
Flag-Only Broadcaster
------------------------
Reads live flag state from iRacing and sends it to all connected CYD
boards (works with flag_display_only.ino, and also works fine with
button_box_8btn.ino since it listens for the same FLAG: commands).

No vJoy, no button handling - just flags. Use this if you only care
about the flag display, or while troubleshooting flag behavior
separately from button/joystick stuff.

SETUP
-----
pip install pyserial pyirsdk
"""

import sys
import time
import serial
import serial.tools.list_ports
import irsdk

BAUD_RATE = 115200
PORT_HINTS = ["CP210", "CH340", "Silicon Labs", "USB-SERIAL", "USB2.0-Serial"]
FLAG_POLL_INTERVAL = 0.5


def find_esp32_ports():
    found = []
    for port in serial.tools.list_ports.comports():
        desc = (port.description or "") + " " + (port.manufacturer or "")
        if any(hint.lower() in desc.lower() for hint in PORT_HINTS):
            found.append(port.device)
    return found


def flag_bit(name):
    """Safely get a flag bit by name - returns 0 if this version of
    pyirsdk doesn't have that attribute, instead of crashing."""
    return getattr(irsdk.Flags, name, 0)


def current_flag_name(ir):
    if not ir.is_connected:
        return "NONE"
    flags = ir["SessionFlags"]
    if flags is None:
        return "NONE"
    if flags & flag_bit('checkered'):
        return "CHECKERED"
    if flags & flag_bit('black') or flags & flag_bit('disqualify'):
        return "BLACK"
    if flags & flag_bit('red'):
        return "RED"
    if flags & (flag_bit('caution') | flag_bit('cautionWaving') | flag_bit('yellow') | flag_bit('yellowWaving')):
        return "YELLOW"
    if flags & flag_bit('debris'):
        return "DEBRIS"
    if flags & flag_bit('blue'):
        return "BLUE"
    if flags & flag_bit('white'):
        return "WHITE"
    if flags & flag_bit('green') or flags & flag_bit('greenHeld'):
        return "GREEN"
    return "NONE"


def main():
    print("Flag broadcaster starting...")
    ir = irsdk.IRSDK()

    connections = {}
    last_flag = None
    last_flag_check = 0.0

    print("Waiting for boards and iRacing... (Ctrl+C to quit)\n")

    try:
        while True:
            # Discover / open any new boards
            for port in find_esp32_ports():
                if port not in connections:
                    try:
                        ser = serial.Serial(port, BAUD_RATE, timeout=0.05)
                        time.sleep(2)
                        connections[port] = ser
                        print(f"[+] Connected to board on {port}")
                    except serial.SerialException:
                        pass

            # Check iRacing flag state
            now = time.time()
            if (now - last_flag_check) >= FLAG_POLL_INTERVAL:
                last_flag_check = now
                if not ir.is_connected:
                    ir.startup()
                flag = current_flag_name(ir) if ir.is_connected else "NONE"
                if flag != last_flag:
                    print(f"[flag] {last_flag} -> {flag} (sending to {len(connections)} board(s))")
                    last_flag = flag
                    dead_ports = []
                    for port, ser in connections.items():
                        try:
                            ser.write(f"FLAG:{flag}\n".encode("utf-8"))
                        except (serial.SerialException, OSError):
                            dead_ports.append(port)
                    for port in dead_ports:
                        connections[port].close()
                        del connections[port]

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping.")
        for ser in connections.values():
            ser.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
