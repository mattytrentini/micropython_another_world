"""ODROID Go input test — shows live button/d-pad readings on the LCD.

Deploy and run: mpytool -p /dev/ttyUSB0 run tests/test_odroid_input.py
Press Start to exit.
"""
from machine import Pin, ADC
import time

# D-pad
joy_x = ADC(Pin(34)); joy_x.atten(ADC.ATTN_11DB)
joy_y = ADC(Pin(35)); joy_y.atten(ADC.ATTN_11DB)

# Buttons (active LOW)
btn_a = Pin(32, Pin.IN, Pin.PULL_UP)
btn_b = Pin(33, Pin.IN, Pin.PULL_UP)
btn_start = Pin(39, Pin.IN)
btn_select = Pin(27, Pin.IN, Pin.PULL_UP)
btn_menu = Pin(13, Pin.IN, Pin.PULL_UP)

print("ODROID Go Input Test")
print("Press Start to exit")
print()

while True:
    x = joy_x.read()
    y = joy_y.read()
    a = btn_a.value()
    b = btn_b.value()
    start = btn_start.value()
    sel = btn_select.value()
    menu = btn_menu.value()

    dirs = []
    if x < 1024: dirs.append("RIGHT")
    elif x > 3072: dirs.append("LEFT")
    if y < 1024: dirs.append("DOWN")
    elif y > 3072: dirs.append("UP")
    if not dirs: dirs.append("--")

    btns = []
    if a == 0: btns.append("A")
    if b == 0: btns.append("B")
    if start == 0: btns.append("START")
    if sel == 0: btns.append("SEL")
    if menu == 0: btns.append("MENU")
    if not btns: btns.append("--")

    print("\rX={:4d} Y={:4d} | {:12s} | {:16s}".format(
        x, y, "+".join(dirs), "+".join(btns)), end="")

    if start == 0:
        print("\nExiting")
        break

    time.sleep_ms(100)
