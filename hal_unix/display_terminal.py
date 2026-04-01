"""Terminal display backend using ANSI escape sequences.

Renders a 320x200 4bpp framebuffer to the terminal using Unicode half-block
characters. Each terminal cell represents 2 vertical pixels (upper and lower),
giving an effective resolution of up to 320x100 character cells.

The display is scaled down horizontally to fit typical terminals (80-160 cols).
"""

import sys

try:
    from aw.hal import DisplayHAL
    from aw.consts import SCREEN_W, SCREEN_H
except ImportError:
    sys.path.insert(0, ".")
    from aw.hal import DisplayHAL
    from aw.consts import SCREEN_W, SCREEN_H


# Unicode half-block characters
_UPPER_HALF = "\u2580"  # upper half block
_LOWER_HALF = "\u2584"  # lower half block
_FULL_BLOCK = "\u2588"  # full block

# Row stride in bytes
_STRIDE = SCREEN_W // 2  # 160


# Default 16-color palette (approximation of the intro palette)
_DEFAULT_PALETTE = [
    (0, 0, 0),       # 0: black
    (34, 34, 136),    # 1: dark blue
    (34, 136, 34),    # 2: dark green
    (34, 136, 136),   # 3: dark cyan
    (136, 34, 34),    # 4: dark red
    (136, 34, 136),   # 5: dark magenta
    (136, 136, 34),   # 6: dark yellow
    (170, 170, 170),  # 7: light gray
    (85, 85, 85),     # 8: dark gray
    (85, 85, 255),    # 9: blue
    (85, 255, 85),    # 10: green
    (85, 255, 255),   # 11: cyan
    (255, 85, 85),    # 12: red
    (255, 85, 255),   # 13: magenta
    (255, 255, 85),   # 14: yellow
    (255, 255, 255),  # 15: white
]


def _rgb_escape_fg(r, g, b):
    return "\x1b[38;2;{};{};{}m".format(r, g, b)


def _rgb_escape_bg(r, g, b):
    return "\x1b[48;2;{};{};{}m".format(r, g, b)


_RESET = "\x1b[0m"
_HIDE_CURSOR = "\x1b[?25l"
_SHOW_CURSOR = "\x1b[?25h"
_HOME = "\x1b[H"
_CLEAR = "\x1b[2J"


class TerminalDisplay(DisplayHAL):
    """Renders 4bpp framebuffer to terminal using ANSI true-color and half-blocks."""

    def __init__(self, scale=2):
        """
        Args:
            scale: horizontal pixel grouping. scale=2 means every 2 horizontal
                   pixels are merged into one character cell, giving 160 columns.
                   scale=4 gives 80 columns.
        """
        self.scale = scale
        self.palette = list(_DEFAULT_PALETTE)
        self._cols = SCREEN_W // scale
        self._rows = SCREEN_H // 2  # half-block = 2 vertical pixels per cell
        self._prev_frame = None

    def init(self, width, height):
        sys.stdout.write(_HIDE_CURSOR + _CLEAR + _HOME)
        sys.stdout.flush()

    def update_palette(self, palette):
        if palette:
            self.palette = list(palette)

    def present(self, framebuf_4bpp):
        """Render the 4bpp framebuffer to terminal."""
        pal = self.palette
        scale = self.scale
        cols = self._cols
        buf = framebuf_4bpp
        lines = []

        lines.append(_HOME)

        for row in range(self._rows):
            y_top = row * 2
            y_bot = y_top + 1

            top_off = y_top * _STRIDE
            bot_off = y_bot * _STRIDE

            line_parts = []
            prev_fg = None
            prev_bg = None

            for col in range(cols):
                # Sample pixel at the center of the horizontal group
                px = col * scale + scale // 2
                byte_idx = px >> 1
                if px & 1:
                    top_color = buf[top_off + byte_idx] & 0x0F
                    bot_color = buf[bot_off + byte_idx] & 0x0F
                else:
                    top_color = (buf[top_off + byte_idx] >> 4) & 0x0F
                    bot_color = (buf[bot_off + byte_idx] >> 4) & 0x0F

                tr, tg, tb = pal[top_color]
                br, bg_val, bb = pal[bot_color]

                if top_color == bot_color:
                    # Both pixels same color: use full block with fg color
                    fg = (tr, tg, tb)
                    if fg != prev_fg:
                        line_parts.append(_rgb_escape_fg(tr, tg, tb))
                        prev_fg = fg
                    # Reset bg if it was set
                    if prev_bg is not None:
                        line_parts.append("\x1b[49m")
                        prev_bg = None
                    line_parts.append(_FULL_BLOCK)
                else:
                    # Upper half block: fg = top color, bg = bottom color
                    fg = (tr, tg, tb)
                    bg = (br, bg_val, bb)
                    if fg != prev_fg:
                        line_parts.append(_rgb_escape_fg(tr, tg, tb))
                        prev_fg = fg
                    if bg != prev_bg:
                        line_parts.append(_rgb_escape_bg(br, bg_val, bb))
                        prev_bg = bg
                    line_parts.append(_UPPER_HALF)

            line_parts.append(_RESET)
            prev_fg = None
            prev_bg = None
            lines.append("".join(line_parts))
            lines.append("\n")

        sys.stdout.write("".join(lines))
        sys.stdout.flush()

    def shutdown(self):
        sys.stdout.write(_SHOW_CURSOR + _RESET + "\n")
        sys.stdout.flush()
