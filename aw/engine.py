"""Top-level Another World game engine.

Ties together the VM, Video, Resource, and Polygon subsystems
with the HAL abstractions.
"""

from .vm import VM
from .video import Video
from .polygon import PolygonRenderer
from .resource import Resource
from .mixer import MixerStub
from .font import FONT
from .strings import STRINGS
from .consts import (
    FRAME_MS, VAR_PAUSE_SLICES, PART_INTRO,
)


class Engine:
    """Another World game engine."""

    def __init__(self, display_hal, input_hal, timer_hal, file_hal):
        self.display = display_hal
        self.input = input_hal
        self.timer = timer_hal

        # Core subsystems
        self.resource = Resource(file_hal)
        self.video = Video()
        self.vm = VM()
        self.polygon = PolygonRenderer(self.video)
        self.mixer = MixerStub()

        # Wire subsystems together
        self.vm.video = self.video
        self.vm.resource = self.resource
        self.vm.mixer = self.mixer
        self.video.polygon = self.polygon
        self.video.font_data = FONT
        self.video.strings = STRINGS

        # Display callback — defers actual presentation to end of frame
        self.video.on_display = self._on_display
        self._display_pending = False

        self._quit = False
        self._last_timestamp = 0

    def init(self, start_part=PART_INTRO):
        """Initialize the engine and load the starting game part."""
        self.display.init(320, 200)
        self.resource.read_memlist()
        self.resource.setup_part(start_part)

        # Connect loaded data to subsystems
        self._apply_part_data()

        # Initialize VM
        self.vm.restart_at(start_part)
        self.vm.set_code(self.resource.seg_code)

        self._last_timestamp = self.timer.ticks_ms()

    def _apply_part_data(self):
        """Connect loaded resource data to video/polygon subsystems."""
        self.video.palette_data = self.resource.seg_palette
        self.video.seg_video1 = self.resource.seg_video1
        self.video.seg_video2 = self.resource.seg_video2

    def run(self):
        """Main game loop. Runs until quit."""
        while not self._quit:
            self._frame()

        self.display.shutdown()

    def _frame(self):
        """Execute one frame: input, VM tasks, timing."""
        # Poll input
        input_state = self.input.poll()
        if input_state.quit:
            self._quit = True
            return
        self.vm.update_input(input_state)

        # Check if a new part needs to be loaded
        if self.resource.current_part != self.vm.resource.current_part:
            self._apply_part_data()
            self.vm.set_code(self.resource.seg_code)

        # Run VM
        self._display_pending = False
        self.vm.setup_tasks()
        self.vm.run_tasks()

        # Present the last display update from this frame (if any)
        if self._display_pending:
            self._present()

        # Frame timing
        pause_slices = self.vm.regs[VAR_PAUSE_SLICES]
        if pause_slices == 0:
            pause_slices = 1
        target_delay = pause_slices * FRAME_MS

        now = self.timer.ticks_ms()
        elapsed = now - self._last_timestamp
        remaining = target_delay - elapsed
        if remaining > 0:
            self.timer.sleep_ms(remaining)
        self._last_timestamp = self.timer.ticks_ms()

    def _on_display(self, framebuf_4bpp, palette_rgb):
        """Called by video.update_display — defers to end of frame.

        Multiple updateDisplay calls can happen per VM frame (e.g. during
        initialization). We only present the last one to avoid showing
        intermediate compositing states.
        """
        if palette_rgb:
            self.display.update_palette(palette_rgb)
        self._display_pending = True

    def _present(self):
        """Actually push the current display page to the terminal."""
        display_buf = self.video.page_bufs[self.video.buffers[1]]
        self.display.present(display_buf)
