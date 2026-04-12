"""Continuously read ADC on pins 34/35. Shows values for d-pad.

mpytool -p /dev/ttyUSB0 run tests/scan_adc.py
Press each d-pad direction to see the ADC values.
Press A button to exit.
"""
from machine import Pin, ADC
import time

adc_x = ADC(Pin(34)); adc_x.atten(ADC.ATTN_11DB)
adc_y = ADC(Pin(35)); adc_y.atten(ADC.ATTN_11DB)
btn_a = Pin(32, Pin.IN, Pin.PULL_UP)

prev_x = -1
prev_y = -1

print("D-pad ADC test - press each direction")
print("Press A to exit")
print()

while btn_a.value() == 1:
    x = adc_x.read()
    y = adc_y.read()
    # Only print when values change significantly
    if abs(x - prev_x) > 50 or abs(y - prev_y) > 50:
        dirs = []
        if x > 2048: dirs.append("LEFT?")
        elif x > 500: dirs.append("MID-X")
        if y > 2048: dirs.append("UP?")
        elif y > 500: dirs.append("MID-Y")
        if x < 500 and y < 500: dirs.append("rest/RIGHT?/DOWN?")
        print("X={:4d} Y={:4d}  {}".format(x, y, " ".join(dirs)))
        prev_x = x
        prev_y = y
    time.sleep_ms(50)

print("Exiting")
