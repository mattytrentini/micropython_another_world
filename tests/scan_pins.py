"""Scan all GPIO pins and report changes. Run on ODROID Go.

mpytool -p /dev/ttyUSB0 run tests/scan_pins.py

Press buttons and d-pad to see which pins change.
Press Ctrl-C to exit.
"""
from machine import Pin
import time

# All usable GPIO pins on ESP32
test_pins = [0, 2, 4, 5, 12, 13, 14, 15, 25, 26, 27, 32, 33, 34, 35, 36, 39]
pins = {}
for p in test_pins:
    try:
        pins[p] = Pin(p, Pin.IN)
    except:
        pass

# Read initial state
prev = {}
for p, pin in pins.items():
    prev[p] = pin.value()

print("Scanning pins... press buttons to see changes")
print("Initial state:")
for p in sorted(prev):
    print("  Pin {:2d}: {}".format(p, prev[p]))
print()

while True:
    changed = False
    for p, pin in pins.items():
        v = pin.value()
        if v != prev[p]:
            print("Pin {:2d}: {} -> {}".format(p, prev[p], v))
            prev[p] = v
            changed = True
    time.sleep_ms(50)
