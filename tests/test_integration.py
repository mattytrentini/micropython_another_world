"""Integration test: load real game data and run a few frames.

Usage: python3 tests/test_integration.py [data_dir]
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
from aw.consts import PART_INTRO, STATE_ACTIVE, THREAD_INACTIVE
from hal_unix.file_unix import UnixFile


def test_load_and_run(data_dir):
    """Load the intro part and run a few VM frames."""
    file_hal = UnixFile(data_dir)
    res = Resource(file_hal)
    res.detect_format()
    print("Data format: {}".format(res.data_format))

    res.read_memlist()
    res.setup_part(PART_INTRO)

    print("seg_palette: {} bytes".format(len(res.seg_palette) if res.seg_palette else 0))
    print("seg_code:    {} bytes".format(len(res.seg_code) if res.seg_code else 0))
    print("seg_video1:  {} bytes".format(len(res.seg_video1) if res.seg_video1 else 0))
    print("seg_video2:  {} bytes".format(len(res.seg_video2) if res.seg_video2 else 0))

    # Set up VM + Video
    video = Video()
    polygon = PolygonRenderer(video)
    mixer = MixerStub()
    vm = VM()

    vm.video = video
    vm.resource = res
    vm.mixer = mixer
    video.polygon = polygon
    video.font_data = FONT
    video.strings = STRINGS
    video.palette_data = res.seg_palette
    video.seg_video1 = res.seg_video1
    video.seg_video2 = res.seg_video2

    vm.restart_at(PART_INTRO)
    vm.set_code(res.seg_code)

    # Count display updates
    display_count = [0]
    def on_display(buf, pal):
        display_count[0] += 1

    video.on_display = on_display

    # Run frames
    num_frames = 50
    print("\nRunning {} frames...".format(num_frames))

    for frame in range(num_frames):
        vm.setup_tasks()
        vm.run_tasks()

        # Count active threads
        active = sum(1 for i in range(64)
                     if vm.task_state[0][i] == STATE_ACTIVE
                     and vm.task_pc[0][i] != THREAD_INACTIVE)

        if frame < 5 or frame % 10 == 0:
            print("  Frame {:3d}: {} active threads, {} display updates so far".format(
                frame, active, display_count[0]))

    print("\nCompleted {} frames, {} display updates".format(num_frames, display_count[0]))
    print("PASS")


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    test_load_and_run(data_dir)


if __name__ == "__main__":
    main()
