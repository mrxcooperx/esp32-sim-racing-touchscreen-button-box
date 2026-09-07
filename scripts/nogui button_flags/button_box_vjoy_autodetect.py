"""
Button Box vJoy Listener - Plug and Play version, with iRacing flag display
------------------------------------------------------------------------------
Supports MULTIPLE connected CYD boards at once - e.g. one running the
button box firmware, another running the flag-only display firmware.
  - Auto-detects every board plugged in (no COM port editing)
  - Real press-and-hold: reads "PRESS:<code>" / "RELEASE:<code>" from
    the board and holds/releases the matching vJoy button for exactly
    as long as the screen is actually being touched
  - Broadcasts "FLAG:<NAME>" updates to ALL connected boards
  - Keeps retrying/reconnecting in the background if a board is
    unplugged or plugged in later

SETUP (one-time)
------------------
1. Install the vJoy driver: https://vjoystick.sourceforge.io
2. Open "Configure vJoy" and set Device 1 to have at least 21 buttons.
3. pip install pyserial pyvjoy pyirsdk
"""

import sys
import time
import serial
import serial.tools.list_ports
import pyvjoy

try:
    import irsdk
    IRSDK_AVAILABLE = True
except ImportError:
    IRSDK_AVAILABLE = False

VJOY_DEVICE_ID = 1
BAUD_RATE = 115200

CODE_TO_BUTTON = {
    # Page 1 - D-pad
    "UP": 1,
    "DOWN": 2,
    "LEFT": 3,
    "RIGHT": 4,
    # Page 2
    "BTN_RESET": 5,
    "BTN_TORTOISE": 6,
    "BTN_WHEEL_REPAIR": 7,
    "BTN_BATTERY": 8,
    # Page 3
    "autotogglefuel": 9,
    "8gallons": 10,
    "TIRE_LF": 11,
    "TIRE_RF": 12,
    "TIRE_RR": 13,
    "TIRE_LR": 14,
    # Page 1 - D-pad center button
    "BTN_CENTER": 15,
    # Page 5 - adjuster pairs
    "ADJ1_UP": 16,
    "ADJ1_DOWN": 17,
    "ADJ2_UP": 18,
    "ADJ2_DOWN": 19,
    "ADJ3_UP": 20,
    "ADJ3_DOWN": 21,
}

PORT_HINTS = ["CP210", "CH340", "Silicon Labs", "USB-SERIAL", "USB2.0-Serial"]
FLAG_POLL_INTERVAL = 0.5


def find_esp32_ports():
    """Returns a list of every serial port that looks like one of our boards."""
    found = []
    for port in serial.tools.list_ports.comports():
        desc = (port.description or "") + " " + (port.manufacturer or "")
        if any(hint.lower() in desc.lower() for hint in PORT_HINTS):
            found.append(port.device)
    return found


def connect_vjoy():
    while True:
        try:
            return pyvjoy.VJoyDevice(VJOY_DEVICE_ID)
        except Exception as e:
            print(f"[!] vJoy not ready ({e}) - is the driver installed? Retrying in 5s...")
            time.sleep(5)


def flag_bit(name):
    """Safely get a flag bit by name - returns 0 (never matches) if this
    version of pyirsdk doesn't have that particular attribute, instead
    of crashing."""
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
    print("Button box listener starting - waiting for vJoy...")
    j = connect_vjoy()
    print("vJoy connected.")

    ir = None
    last_flag = None
    last_flag_check = 0.0
    last_best_lap = None
    if IRSDK_AVAILABLE:
        ir = irsdk.IRSDK()
        print("iRacing flag broadcast enabled (connects whenever iRacing is running).")
    else:
        print("[!] pyirsdk not installed - flag display disabled. Run: pip install pyirsdk")

    connections = {}  # port name -> serial.Serial

    print("Waiting for boards... (checking every 2s)\n")

    try:
        while True:
            # --- Discover / open any new boards ---
            for port in find_esp32_ports():
                if port not in connections:
                    try:
                        ser = serial.Serial(port, BAUD_RATE, timeout=0.05)
                        time.sleep(2)  # let the board finish resetting
                        connections[port] = ser
                        print(f"[+] Connected to board on {port}")
                    except serial.SerialException:
                        pass  # port busy or briefly unavailable - try again next loop

            # --- Read from each connected board ---
            dead_ports = []
            for port, ser in connections.items():
                try:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        if line.startswith("PRESS:"):
                            code = line[len("PRESS:"):]
                            button_num = CODE_TO_BUTTON.get(code)
                            if button_num is None:
                                print(f"[!] ({port}) No vJoy button mapped for '{code}'")
                            else:
                                try:
                                    j.set_button(button_num, 1)
                                    print(f"[>] ({port}) PRESS {code} -> vJoy button {button_num} down")
                                except Exception as e:
                                    print(f"[!] vJoy error on button {button_num} ('{code}'): {e} - "
                                          f"is vJoy Device 1 configured with at least {button_num} buttons?")
                        elif line.startswith("RELEASE:"):
                            code = line[len("RELEASE:"):]
                            button_num = CODE_TO_BUTTON.get(code)
                            if button_num is None:
                                print(f"[!] ({port}) No vJoy button mapped for '{code}'")
                            else:
                                try:
                                    j.set_button(button_num, 0)
                                    print(f"[>] ({port}) RELEASE {code} -> vJoy button {button_num} up")
                                except Exception as e:
                                    print(f"[!] vJoy error on button {button_num} ('{code}'): {e} - "
                                          f"is vJoy Device 1 configured with at least {button_num} buttons?")
                        elif line.startswith("PAGE:"):
                            pass  # only the GUI version's Display Preview needs this
                        elif not line.startswith("FLAG:") and line != "Button box ready.":
                            print(f"[?] ({port}) Unrecognized line: '{line}'")
                except (serial.SerialException, OSError):
                    print(f"[!] Lost connection to {port}")
                    dead_ports.append(port)

            for port in dead_ports:
                connections[port].close()
                del connections[port]

            # --- Check iRacing flag state and broadcast to all boards ---
            now = time.time()
            if ir is not None and (now - last_flag_check) >= FLAG_POLL_INTERVAL:
                last_flag_check = now
                if not ir.is_connected:
                    ir.startup()
                flag = current_flag_name(ir) if ir.is_connected else "NONE"
                if flag != last_flag:
                    print(f"[flag] {last_flag} -> {flag} (broadcasting to {len(connections)} board(s))")
                    last_flag = flag
                    for port, ser in list(connections.items()):
                        try:
                            ser.write(f"FLAG:{flag}\n".encode("utf-8"))
                        except (serial.SerialException, OSError):
                            pass  # will be cleaned up next loop

                if ir.is_connected:
                    best_lap = ir["LapBestLapTime"]
                    if best_lap is not None and best_lap != last_best_lap:
                        last_best_lap = best_lap
                        print(f"[laptime] Best lap: {best_lap:.3f}s (broadcasting to {len(connections)} board(s))")
                        for port, ser in list(connections.items()):
                            try:
                                ser.write(f"LAPTIME:{best_lap}\n".encode("utf-8"))
                            except (serial.SerialException, OSError):
                                pass
                elif last_best_lap is not None:
                    last_best_lap = None
                    for port, ser in list(connections.items()):
                        try:
                            ser.write("LAPTIME:-1\n".encode("utf-8"))
                        except (serial.SerialException, OSError):
                            pass

            if not connections:
                time.sleep(2)
            else:
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nStopping.")
        for ser in connections.values():
            ser.close()
        sys.exit(0)


if __name__ == "__main__":
    main()


