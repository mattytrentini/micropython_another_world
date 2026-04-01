"""Visual demo of the terminal display backend.

Fills the screen with a color gradient, draws some text, and renders
to the terminal. This validates the full Video -> TerminalDisplay pipeline.

Run with: python3 tests/demo_terminal.py
"""

import sys
import time
sys.path.insert(0, ".")

from aw.video import Video, STRIDE
from aw.font import FONT
from aw.strings import STRINGS
from aw.consts import SCREEN_W, SCREEN_H
from hal_unix.display_terminal import TerminalDisplay


def main():
    video = Video()
    video.font_data = FONT
    video.strings = STRINGS

    display = TerminalDisplay(scale=4)  # 80 columns
    display.init(SCREEN_W, SCREEN_H)

    # Draw a color gradient: 16 horizontal bands
    buf = video.page_bufs[0]
    band_h = SCREEN_H // 16
    for color in range(16):
        fill = (color << 4) | color
        y_start = color * band_h
        for y in range(y_start, min(y_start + band_h, SCREEN_H)):
            for x in range(STRIDE):
                buf[y * STRIDE + x] = fill

    # Draw some text
    video.buffers[0] = 0
    video.draw_string(0x049, 5, 4, 15)   # "Delphine Software"
    video.draw_string(0x04A, 6, 16, 14)  # "By Eric Chahi"

    # Set up a palette with distinct colors
    palette = [
        (0, 0, 0),       # 0: black
        (0, 0, 170),     # 1: blue
        (0, 170, 0),     # 2: green
        (0, 170, 170),   # 3: cyan
        (170, 0, 0),     # 4: red
        (170, 0, 170),   # 5: magenta
        (170, 85, 0),    # 6: brown
        (170, 170, 170), # 7: light gray
        (85, 85, 85),    # 8: dark gray
        (85, 85, 255),   # 9: light blue
        (85, 255, 85),   # 10: light green
        (85, 255, 255),  # 11: light cyan
        (255, 85, 85),   # 12: light red
        (255, 85, 255),  # 13: light magenta
        (255, 255, 85),  # 14: yellow
        (255, 255, 255), # 15: white
    ]
    display.update_palette(palette)
    display.present(buf)

    time.sleep(3)
    display.shutdown()
    print("\nDemo complete.")


if __name__ == "__main__":
    main()
