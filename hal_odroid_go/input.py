"""ODROID Go input HAL — digital buttons + resistor-ladder d-pad.

D-pad uses a resistor ladder on two ADC pins:
  Rest=0, LEFT/UP=4095, RIGHT/DOWN=~1850

Buttons are active LOW (0 = pressed).
"""

from machine import Pin, ADC

from aw.hal import InputHAL, InputState
from .consts import (
    PIN_BTN_A, PIN_BTN_B, PIN_BTN_MENU, PIN_BTN_SELECT,
    PIN_BTN_START,
    PIN_JOY_X, PIN_JOY_Y,
    JOY_THRESH_MID_LOW, JOY_THRESH_MID_HIGH,
)


class OdroidGoInput(InputHAL):
    """Hardware button and d-pad input."""

    def __init__(self):
        # Digital buttons (active LOW)
        self._btn_a = Pin(PIN_BTN_A, Pin.IN, Pin.PULL_UP)
        self._btn_b = Pin(PIN_BTN_B, Pin.IN, Pin.PULL_UP)
        self._btn_menu = Pin(PIN_BTN_MENU, Pin.IN, Pin.PULL_UP)
        self._btn_select = Pin(PIN_BTN_SELECT, Pin.IN, Pin.PULL_UP)
        self._btn_start = Pin(PIN_BTN_START, Pin.IN)  # external pull-up

        # D-pad ADC (resistor ladder)
        self._joy_x = ADC(Pin(PIN_JOY_X))
        self._joy_x.atten(ADC.ATTN_11DB)
        self._joy_y = ADC(Pin(PIN_JOY_Y))
        self._joy_y.atten(ADC.ATTN_11DB)

        # Track previous state for edge detection (pause/step)
        self._prev_menu = 1
        self._prev_select = 1

    def poll(self):
        state = InputState()

        # D-pad (resistor ladder: rest=0, left/up=4095, right/down=~1850)
        x = self._joy_x.read()
        y = self._joy_y.read()
        state.left = x > JOY_THRESH_MID_HIGH
        state.right = x > JOY_THRESH_MID_LOW and x <= JOY_THRESH_MID_HIGH
        state.up = y > JOY_THRESH_MID_HIGH
        state.down = y > JOY_THRESH_MID_LOW and y <= JOY_THRESH_MID_HIGH

        # Action = A button (active LOW: 0 = pressed)
        state.action = self._btn_a.value() == 0

        # B button as secondary action
        if self._btn_b.value() == 0:
            state.action = True

        # Menu = pause (edge-triggered)
        menu = self._btn_menu.value()
        state.pause = (menu == 0 and self._prev_menu == 1)
        self._prev_menu = menu

        # Select = step (edge-triggered)
        sel = self._btn_select.value()
        state.step = (sel == 0 and self._prev_select == 1)
        self._prev_select = sel

        # Start = quit
        state.quit = self._btn_start.value() == 0

        return state

    def shutdown(self):
        pass
