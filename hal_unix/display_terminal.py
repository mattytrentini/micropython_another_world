"""Terminal display backend using ANSI escape sequences.

Renders a 320x200 4bpp framebuffer to the terminal using Unicode half-block
characters. Each terminal cell represents 2 vertical pixels (upper and lower),
giving an effective resolution of up to 320x100 character cells.

Uses synchronized output (mode 2026) to eliminate flicker on modern terminals.
"""

import sys
import os

try:
    from aw.hal import DisplayHAL
    from aw.consts import SCREEN_W, SCREEN_H
except ImportError:
    sys.path.insert(0, ".")
    from aw.hal import DisplayHAL
    from aw.consts import SCREEN_W, SCREEN_H


# Unicode half-block characters
_UPPER_HALF = "\u2580"
_FULL_BLOCK = "\u2588"

# Row stride in bytes
_STRIDE = SCREEN_W // 2  # 160

# ANSI escape sequences
_HIDE_CURSOR = "\x1b[?25l"
_SHOW_CURSOR = "\x1b[?25h"
_HOME = "\x1b[H"
_CLEAR = "\x1b[2J"
_RESET = "\x1b[0m"

# Synchronized output: tells the terminal to batch all writes between
# BEGIN and END, then render in one pass. Eliminates flicker.
_SYNC_BEGIN = "\x1b[?2026h"
_SYNC_END = "\x1b[?2026l"

# stdout file descriptor for raw writes
_FD = 1


class TerminalDisplay(DisplayHAL):
    """Renders 4bpp framebuffer to terminal using ANSI true-color and half-blocks."""

    def __init__(self, scale=2, show_frame=False):
        """
        Args:
            scale: horizontal pixel grouping. scale=2 means every 2 horizontal
                   pixels are merged into one character cell, giving 160 columns.
                   scale=4 gives 80 columns.
            show_frame: if True, display frame counter below the image.
        """
        self.scale = scale
        self.show_frame = show_frame
        self.paused = False
        self._frame_num = 0
        self._cols = SCREEN_W // scale
        self._rows = SCREEN_H // 2  # half-block = 2 vertical pixels per cell
        # Pre-computed fg/bg escape strings per palette color (set in update_palette)
        self._fg = [None] * 16
        self._bg = [None] * 16
        self._set_palette([(0, 0, 0)] * 16)

    def _set_palette(self, palette):
        """Pre-compute escape strings for each palette color."""
        for i in range(16):
            r, g, b = palette[i]
            self._fg[i] = "\x1b[38;2;{};{};{}m".format(r, g, b)
            self._bg[i] = "\x1b[48;2;{};{};{}m".format(r, g, b)

    def init(self, width, height):
        os.write(_FD, (_HIDE_CURSOR + _CLEAR + _HOME).encode())

    def update_palette(self, palette):
        if palette:
            self._set_palette(palette)

    def present(self, framebuf_4bpp):
        """Render the 4bpp framebuffer to terminal."""
        fg = self._fg
        bg = self._bg
        scale = self.scale
        cols = self._cols
        buf = framebuf_4bpp
        parts = [_SYNC_BEGIN, _HOME]

        prev_fg_idx = -1
        prev_bg_idx = -1

        for row in range(self._rows):
            y_top = row * 2
            y_bot = y_top + 1
            top_off = y_top * _STRIDE
            bot_off = y_bot * _STRIDE

            for col in range(cols):
                px = col * scale + scale // 2
                byte_idx = px >> 1
                if px & 1:
                    tc = buf[top_off + byte_idx] & 0x0F
                    bc = buf[bot_off + byte_idx] & 0x0F
                else:
                    tc = (buf[top_off + byte_idx] >> 4) & 0x0F
                    bc = (buf[bot_off + byte_idx] >> 4) & 0x0F

                if tc == bc:
                    # Same color top and bottom: full block, fg only
                    if tc != prev_fg_idx:
                        parts.append(fg[tc])
                        prev_fg_idx = tc
                    if prev_bg_idx != -1:
                        parts.append("\x1b[49m")
                        prev_bg_idx = -1
                    parts.append(_FULL_BLOCK)
                else:
                    # Upper half block: fg=top, bg=bottom
                    if tc != prev_fg_idx:
                        parts.append(fg[tc])
                        prev_fg_idx = tc
                    if bc != prev_bg_idx:
                        parts.append(bg[bc])
                        prev_bg_idx = bc
                    parts.append(_UPPER_HALF)

            parts.append(_RESET)
            parts.append("\n")
            prev_fg_idx = -1
            prev_bg_idx = -1

        if self.show_frame:
            self._frame_num += 1
            status = " PAUSED (N=step)" if self.paused else ""
            parts.append("\x1b[37mFrame {:d}{}\x1b[0m\x1b[K\n".format(
                self._frame_num, status))

        parts.append(_SYNC_END)

        # Single raw write — avoids Python text-mode overhead
        os.write(_FD, "".join(parts).encode())

    def shutdown(self):
        os.write(_FD, (_SHOW_CURSOR + _RESET + "\n").encode())
