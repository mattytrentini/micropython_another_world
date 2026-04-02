"""ODROID Go display HAL — ILI9341 320x240 LCD over SPI.

Converts the engine's 320x200 4bpp packed framebuffer to RGB565 and
pushes it to the display. The game image is centered vertically with
20 pixels of black border (top and bottom).

The palette is pre-converted to RGB565 on each change, and a row-level
LUT is used to convert 4bpp→RGB565 efficiently.
"""

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
        # For each possible 4bpp packed byte value, store 2 RGB565 pixels
        self._lut = bytearray(256 * 4)
        # Row buffer for one scanline of RGB565 data (320 pixels × 2 bytes)
        self._row_buf = bytearray(SCREEN_W * 2)
        # Black row for top/bottom borders
        self._black_row = bytearray(SCREEN_W * 2)

    def init(self, width, height):
        self._spi = SPI(SPI_ID, baudrate=SPI_BAUD, polarity=0, phase=0,
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
        self._cmd(_CMD_MADCTL, bytes([_MADCTL_MX | _MADCTL_MV | _MADCTL_BGR]))

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

    def present(self, framebuf_4bpp):
        """Convert 4bpp buffer to RGB565 and push to display."""
        lut = self._lut
        row_buf = self._row_buf
        buf = framebuf_4bpp

        # Set window for the full display
        self._set_window(0, 0, DISPLAY_W - 1, DISPLAY_H - 1)
        self._dc.value(1)
        self._cs.value(0)

        # Top border (black)
        for _ in range(_Y_OFFSET):
            self._spi.write(self._black_row)

        # Game area (320x200)
        for y in range(SCREEN_H):
            src_off = y * STRIDE
            dst = 0
            for x in range(STRIDE):
                off = buf[src_off + x] * 4
                row_buf[dst] = lut[off]
                row_buf[dst + 1] = lut[off + 1]
                row_buf[dst + 2] = lut[off + 2]
                row_buf[dst + 3] = lut[off + 3]
                dst += 4
            self._spi.write(row_buf)

        # Bottom border (black)
        for _ in range(DISPLAY_H - SCREEN_H - _Y_OFFSET):
            self._spi.write(self._black_row)

        self._cs.value(1)

    def shutdown(self):
        # Turn off backlight
        Pin(PIN_BACKLIGHT, Pin.OUT).value(0)
