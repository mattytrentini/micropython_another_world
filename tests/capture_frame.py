"""Capture a frame from the game and save as PPM image.

Usage: python3 tests/capture_frame.py [data_dir] [num_frames] [output.ppm]
"""

import sys
sys.path.insert(0, ".")

from aw.vm import VM
from aw.video import Video
from aw.polygon import PolygonRenderer
from aw.resource import Resource
from aw.mixer import MixerStub
from aw.font import FONT
from aw.strings import STRINGS
from aw.consts import PART_INTRO, SCREEN_W, SCREEN_H
from hal_unix.file_unix import UnixFile

STRIDE = SCREEN_W // 2

# Default palette (will be overridden by game data)
DEFAULT_PAL = [(0, 0, 0)] * 16


def capture(data_dir, num_frames, part_id=PART_INTRO):
    """Run num_frames and return the final display buffer + palette."""
    file_hal = UnixFile(data_dir)
    res = Resource(file_hal)
    res.detect_format()
    res.read_memlist()
    res.setup_part(part_id)

    video = Video()
    polygon = PolygonRenderer(video)
    vm = VM()
    vm.video = video
    vm.resource = res
    vm.mixer = MixerStub()
    video.polygon = polygon
    video.font_data = FONT
    video.strings = STRINGS
    video.palette_data = res.seg_palette
    video.seg_video1 = res.seg_video1
    video.seg_video2 = res.seg_video2

    vm.restart_at(part_id)
    vm.set_code(res.seg_code)

    last_buf = [None]
    last_pal = [list(DEFAULT_PAL)]

    def on_display(buf, pal):
        last_buf[0] = bytes(buf)  # snapshot
        if pal:
            last_pal[0] = list(pal)

    video.on_display = on_display

    for frame in range(num_frames):
        vm.setup_tasks()
        vm.run_tasks()

    return last_buf[0], last_pal[0]


def save_ppm(filename, buf, palette, width=SCREEN_W, height=SCREEN_H):
    """Save a 4bpp buffer as a PPM image file."""
    with open(filename, "wb") as f:
        f.write("P6\n{} {}\n255\n".format(width, height).encode())
        for y in range(height):
            for x in range(width):
                byte_idx = y * STRIDE + x // 2
                if x & 1:
                    color_idx = buf[byte_idx] & 0x0F
                else:
                    color_idx = (buf[byte_idx] >> 4) & 0x0F
                r, g, b = palette[color_idx]
                f.write(bytes([r, g, b]))


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    num_frames = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    output = sys.argv[3] if len(sys.argv) > 3 else "frame.ppm"

    print("Capturing frame after {} frames...".format(num_frames))
    buf, pal = capture(data_dir, num_frames)

    if buf is None:
        print("No frame was rendered!")
        sys.exit(1)

    save_ppm(output, buf, pal)
    print("Saved to {}".format(output))
    print("Palette: {}".format(pal[:8]))


if __name__ == "__main__":
    main()
