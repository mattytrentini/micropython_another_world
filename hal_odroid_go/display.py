"""ODROID Go display HAL — ILI9341 320x240 LCD over SPI.

Converts the engine's 320x200 4bpp packed framebuffer to RGB565 and
pushes it to the display. The game image is centered vertically with
20 pixels of black border (top and bottom).

The palette is pre-converted to RGB565 on each change, and a row-level
LUT is used to convert 4bpp→RGB565 efficiently. The conversion inner
loop uses @micropython.viper for near-C speed.
"""

import micropython

from machine import Pin, SPI
import struct

from aw.hal import DisplayHAL
from aw.consts import SCREEN_W, SCREEN_H
from .consts import (
    SPI_ID, SPI_BAUD, PIN_MOSI, PIN_MISO, PIN_SCLK,
    PIN_DC, PIN_CS_LCD, PIN_BACKLIGHT, DISPLAY_W, DISPLAY_H,
)

STRIDE = SCREEN_W // 2  # 160 bytes per row

# ILI9341 commands
_CMD_SWRESET = 0x01
_CMD_SLPOUT = 0x11
_CMD_DISPON = 0x29
_CMD_CASET = 0x2A
_CMD_RASET = 0x2B
_CMD_RAMWR = 0x2C
_CMD_MADCTL = 0x36
_CMD_COLMOD = 0x3A

# MADCTL flags
_MADCTL_BGR = 0x08
_MADCTL_MX = 0x40   # mirror X
_MADCTL_MY = 0x80   # mirror Y
_MADCTL_MV = 0x20   # swap X/Y

# Vertical offset to center 200 rows in 240
_Y_OFFSET = (DISPLAY_H - SCREEN_H) // 2  # 20


class OdroidGoDisplay(DisplayHAL):
    """ILI9341 display driver for ODROID Go."""

    def __init__(self):
        self._spi = None
        self._dc = None
        self._cs = None
        # Pre-built RGB565 LUT: 256 entries × 4 bytes (2 pixels × 2 bytes)
        self._lut = bytearray(256 * 4)
        # Full frame buffer for RGB565 (320*240*2 = 153,600 bytes)
        # One large SPI write is much faster than 240 small ones
        self._frame_buf = bytearray(DISPLAY_W * DISPLAY_H * 2)

    def init(self, width, height):
        # Reconfigure SPI for display (may have been set to low speed by SD card)
        self._spi = SPI(SPI_ID, baudrate=40_000_000, polarity=0, phase=0,
                        sck=Pin(PIN_SCLK), mosi=Pin(PIN_MOSI), miso=Pin(PIN_MISO))
        self._dc = Pin(PIN_DC, Pin.OUT)
        self._cs = Pin(PIN_CS_LCD, Pin.OUT, value=1)

        # Enable backlight
        Pin(PIN_BACKLIGHT, Pin.OUT).value(1)

        # Initialize ILI9341
        self._init_lcd()

        # Set the draw window to full screen
        self._set_window(0, 0, DISPLAY_W - 1, DISPLAY_H - 1)

    def _init_lcd(self):
        """Initialize the ILI9341 controller."""
        import time

        self._cmd(_CMD_SWRESET)
        time.sleep_ms(150)
        self._cmd(_CMD_SLPOUT)
        time.sleep_ms(150)

        # Pixel format: 16-bit RGB565
        self._cmd(_CMD_COLMOD, bytes([0x55]))

        # Memory access control: landscape, BGR panel
        self._cmd(_CMD_MADCTL, bytes([_MADCTL_MX | _MADCTL_MY | _MADCTL_MV | _MADCTL_BGR]))

        self._cmd(_CMD_DISPON)
        time.sleep_ms(100)

        # Clear screen to black
        self._set_window(0, 0, DISPLAY_W - 1, DISPLAY_H - 1)
        self._dc.value(1)
        self._cs.value(0)
        black = bytearray(SCREEN_W * 2)
        for _ in range(DISPLAY_H):
            self._spi.write(black)
        self._cs.value(1)

    def _cmd(self, cmd, data=None):
        """Send a command (and optional data) to the LCD."""
        self._dc.value(0)
        self._cs.value(0)
        self._spi.write(bytes([cmd]))
        self._cs.value(1)
        if data:
            self._dc.value(1)
            self._cs.value(0)
            self._spi.write(data)
            self._cs.value(1)

    def _set_window(self, x0, y0, x1, y1):
        """Set the drawing window (column and row address)."""
        self._cmd(_CMD_CASET, struct.pack(">HH", x0, x1))
        self._cmd(_CMD_RASET, struct.pack(">HH", y0, y1))
        self._cmd(_CMD_RAMWR)

    def update_palette(self, palette):
        """Convert palette to RGB565 and rebuild the byte→RGB565 LUT."""
        if not palette:
            return

        # Convert each palette color to RGB565 (BGR panel order)
        pal565 = []
        for r, g, b in palette:
            # RGB565: RRRRRGGGGGGBBBBB (big-endian for SPI)
            c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            pal565.append(c)

        # Build LUT: for each possible byte value (2 packed 4bpp pixels),
        # store 4 bytes of RGB565 (high pixel then low pixel, big-endian)
        lut = self._lut
        for byte_val in range(256):
            hi = (byte_val >> 4) & 0x0F
            lo = byte_val & 0x0F
            off = byte_val * 4
            c_hi = pal565[hi]
            c_lo = pal565[lo]
            lut[off] = c_hi >> 8
            lut[off + 1] = c_hi & 0xFF
            lut[off + 2] = c_lo >> 8
            lut[off + 3] = c_lo & 0xFF

    @staticmethod
    @micropython.viper
    def _convert_frame(src: ptr8, lut: ptr8, dst: ptr8,
                       src_rows: int, src_stride: int, dst_offset: int):
        """Convert full 4bpp frame to RGB565 in the frame buffer (viper)."""
        d = dst_offset
        for y in range(src_rows):
            s = y * src_stride
            for x in range(src_stride):
                off = int(src[s + x]) * 4
                dst[d] = lut[off]
                dst[d + 1] = lut[off + 1]
                dst[d + 2] = lut[off + 2]
                dst[d + 3] = lut[off + 3]
                d += 4

    def present(self, framebuf_4bpp):
        """Convert 4bpp buffer to RGB565 and push to display in one SPI write."""
        fb = self._frame_buf

        # Convert game area into frame buffer (after top border offset)
        dst_offset = _Y_OFFSET * DISPLAY_W * 2
        try:
            self._convert_frame(framebuf_4bpp, self._lut, fb,
                                SCREEN_H, STRIDE, dst_offset)
        except Exception:
            # Viper fallback
            lut = self._lut
            buf = framebuf_4bpp
            d = dst_offset
            for y in range(SCREEN_H):
                s = y * STRIDE
                for x in range(STRIDE):
                    off = buf[s + x] * 4
                    fb[d] = lut[off]
                    fb[d + 1] = lut[off + 1]
                    fb[d + 2] = lut[off + 2]
                    fb[d + 3] = lut[off + 3]
                    d += 4

        # Single SPI write for the entire frame
        self._set_window(0, 0, DISPLAY_W - 1, DISPLAY_H - 1)
        self._dc.value(1)
        self._cs.value(0)
        self._spi.write(fb)
        self._cs.value(1)

    def shutdown(self):
        # Turn off backlight
        Pin(PIN_BACKLIGHT, Pin.OUT).value(0)
