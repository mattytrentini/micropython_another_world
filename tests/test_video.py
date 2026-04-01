"""Tests for the video system and VM-Video integration.

Run with: python3 tests/test_video.py
"""

import sys
sys.path.insert(0, ".")

from aw.video import Video, STRIDE
from aw.vm import VM
from aw.font import FONT
from aw.strings import STRINGS
from aw.mixer import MixerStub
from aw.consts import (
    SCREEN_W, SCREEN_H, PAGE_SIZE, STATE_ACTIVE,
    VAR_SCROLL_Y,
)


def make_integrated_vm(code_bytes, regs=None):
    """Create a VM connected to a Video system."""
    code = bytearray(code_bytes) + bytearray([0x06])  # append yield
    vm = VM()
    video = Video()
    video.font_data = FONT
    video.strings = STRINGS
    vm.video = video
    vm.mixer = MixerStub()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    if regs:
        for k, v in regs.items():
            vm.regs[k] = v
    return vm, video


# --- Video unit tests ---

def test_fill_page():
    """Fill a page with a color and verify."""
    video = Video()
    video.fill_page(0, 5)
    buf = video.page_bufs[0]
    expected = (5 << 4) | 5  # 0x55
    assert buf[0] == expected
    assert buf[PAGE_SIZE - 1] == expected


def test_fill_page_zero():
    """Fill with color 0 (black)."""
    video = Video()
    # First fill with non-zero
    video.fill_page(1, 0x0F)
    assert video.page_bufs[1][0] == 0xFF
    # Then fill with zero
    video.fill_page(1, 0)
    assert video.page_bufs[1][0] == 0x00


def test_copy_page_simple():
    """Simple page copy."""
    video = Video()
    video.fill_page(0, 3)
    video.copy_page(0, 1)
    assert video.page_bufs[1][0] == 0x33
    assert video.page_bufs[1][PAGE_SIZE - 1] == 0x33


def test_copy_page_scroll_down():
    """Copy with positive scroll (scroll content down)."""
    video = Video()
    # Fill source page with a pattern: row 0 = 0x11, row 1 = 0x22, etc.
    buf = video.page_bufs[0]
    for y in range(SCREEN_H):
        val = (y & 0x0F)
        fill = (val << 4) | val
        for x in range(STRIDE):
            buf[y * STRIDE + x] = fill

    # Scroll down by 10 pixels: src rows 0-189 -> dst rows 10-199
    # We need to set the scroll flag: src_id with bit 6+7 set
    # Actually the scroll path is triggered by src having bits set
    # Let's test _copy_scroll directly
    video._copy_scroll(0, 1, 10)

    dst = video.page_bufs[1]
    # Row 10 in dst should have row 0 data from src
    src_row0_val = (0 << 4) | 0
    assert dst[10 * STRIDE] == src_row0_val
    # Row 199 in dst should have row 189 data
    val189 = 189 & 0x0F
    expected = (val189 << 4) | val189
    assert dst[199 * STRIDE] == expected


def test_copy_page_scroll_up():
    """Copy with negative scroll (scroll content up)."""
    video = Video()
    buf = video.page_bufs[0]
    for y in range(SCREEN_H):
        val = (y & 0x0F)
        fill = (val << 4) | val
        for x in range(STRIDE):
            buf[y * STRIDE + x] = fill

    video._copy_scroll(0, 1, -10)
    dst = video.page_bufs[1]
    # Row 0 in dst should have row 10 data from src
    val10 = 10 & 0x0F
    expected = (val10 << 4) | val10
    assert dst[0] == expected


def test_select_page():
    """Select draw page."""
    video = Video()
    assert video.buffers[0] == 0  # default draw page
    video.select_page(2)
    assert video.buffers[0] == 2


def test_select_page_special():
    """Select page with special IDs."""
    video = Video()
    video.buffers[0] = 1  # current draw = page 1
    video.select_page(0xFE)  # 0xFE = keep current
    assert video.buffers[0] == 1


def test_update_display_swap():
    """updateDisplay with 0xFF swaps display and back pages."""
    video = Video()
    assert video.buffers[1] == 1  # display
    assert video.buffers[2] == 2  # back
    video.update_display(0xFF)
    assert video.buffers[1] == 2
    assert video.buffers[2] == 1


def test_update_display_direct():
    """updateDisplay with direct page sets display page."""
    video = Video()
    video.update_display(3)
    assert video.buffers[1] == 3


def test_palette_deferred():
    """Palette changes are deferred until updateDisplay."""
    video = Video()
    # Create fake palette data (32 palettes x 16 colors x 2 bytes)
    pal_data = bytearray(32 * 32)
    # Set palette 2, color 0 to red (R=15, G=0, B=0)
    pal_data[2 * 32 + 0] = 0x0F  # 0x0R
    pal_data[2 * 32 + 1] = 0x00  # 0xGB
    video.palette_data = pal_data

    video.set_palette_request(2)
    assert video.palette_rgb is None  # not applied yet

    video.update_display(0xFE)
    assert video.palette_rgb is not None
    assert video.palette_rgb[0] == (255, 0, 0)  # red, scaled 15->255


def test_palette_color_conversion():
    """Test palette color format conversion."""
    video = Video()
    pal_data = bytearray(32 * 32)
    # Palette 0, color 1: R=8, G=12, B=4
    pal_data[0 * 32 + 2] = 0x08  # R=8
    pal_data[0 * 32 + 3] = 0xC4  # G=12, B=4
    video.palette_data = pal_data

    video.set_palette_request(0)
    video.update_display(0xFE)
    r, g, b = video.palette_rgb[1]
    assert r == 8 * 17   # 136
    assert g == 12 * 17  # 204
    assert b == 4 * 17   # 68


# --- Text rendering tests ---

def test_draw_string():
    """Draw a simple string and verify pixels are set."""
    video = Video()
    video.font_data = FONT
    video.strings = STRINGS
    video.fill_page(0, 0)  # clear to black
    video.buffers[0] = 0   # draw on page 0

    # Draw string 0x049 "Delphine Software" at x=1, y=10, color=15
    video.draw_string(0x049, 1, 10, 15)

    buf = video.page_bufs[0]
    # The 'D' character should have some non-zero pixels at row 10
    # x=1 means byte offset 1*4 = 4 in each row
    # Check that something was drawn (not all zeros in the character area)
    has_pixels = False
    for row in range(8):
        for col in range(4):
            if buf[(10 + row) * STRIDE + 4 + col] != 0:
                has_pixels = True
                break
    assert has_pixels, "Expected font pixels to be drawn"


def test_draw_char_color():
    """Verify drawn character uses correct color."""
    video = Video()
    video.font_data = FONT
    video.strings = {0x999: "A"}
    video.fill_page(0, 0)
    video.buffers[0] = 0

    video.draw_string(0x999, 0, 0, 7)  # color 7

    buf = video.page_bufs[0]
    # Check that any set pixel uses color 7
    for i in range(8 * STRIDE):
        byte = buf[i]
        hi = (byte >> 4) & 0x0F
        lo = byte & 0x0F
        if hi != 0:
            assert hi == 7, "Expected color 7, got {}".format(hi)
        if lo != 0:
            assert lo == 7, "Expected color 7, got {}".format(lo)


# --- VM-Video integration tests ---

def test_vm_fill_page():
    """VM opcode 0x0E fills a page."""
    vm, video = make_integrated_vm([
        0x0E, 0x00, 0x05,  # fillPage page=0, color=5
    ])
    vm.run_tasks()
    assert video.page_bufs[0][0] == 0x55


def test_vm_select_and_fill():
    """VM selects a page then fills it."""
    vm, video = make_integrated_vm([
        0x0D, 0x02,         # selectPage page=2
        0x0E, 0xFE, 0x0A,   # fillPage page=0xFE (current=2), color=10
    ])
    vm.run_tasks()
    assert video.page_bufs[2][0] == 0xAA


def test_vm_copy_page():
    """VM copies one page to another."""
    vm, video = make_integrated_vm([
        0x0E, 0x00, 0x03,  # fillPage page=0, color=3
        0x0F, 0x00, 0x01,  # copyPage src=0, dst=1
    ])
    vm.run_tasks()
    assert video.page_bufs[1][0] == 0x33


def test_vm_update_display():
    """VM updateDisplay swaps pages and yields."""
    vm, video = make_integrated_vm([
        0x00, 0x10, 0x00, 0x01,  # movConst var[0x10] = 1
        0x10, 0xFF,               # updateDisplay 0xFF (swap)
        0x00, 0x20, 0x00, 0x02,  # movConst var[0x20] = 2 (next frame)
        0x06,
    ])
    vm.run_tasks()
    assert vm.regs[0x10] == 1
    assert vm.regs[0x20] == 0  # updateDisplay yields
    assert video.buffers[1] == 2  # swapped
    assert video.buffers[2] == 1


def test_vm_draw_string():
    """VM draws a string via opcode 0x12."""
    vm, video = make_integrated_vm([
        0x0E, 0x00, 0x00,              # fillPage page=0, color=0
        0x12, 0x00, 0x49, 0x01, 0x0A, 0x0F,  # drawString id=0x49, x=1, y=10, color=15
    ])
    vm.run_tasks()
    # Verify some pixels were drawn
    buf = video.page_bufs[0]
    has_pixels = any(buf[10 * STRIDE + i] != 0 for i in range(4, 20))
    assert has_pixels


def test_vm_set_palette():
    """VM sets palette (deferred)."""
    vm, video = make_integrated_vm([
        0x0B, 0x03, 0x00,  # setPalette pal_id = 0x0300 >> 8 = 3
    ])
    vm.run_tasks()
    assert video.next_palette == 3


# --- Run all tests ---

def run_tests():
    import gc
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for t in tests:
        name = t.__name__
        try:
            t()
            passed += 1
            print("  PASS: {}".format(name))
        except Exception as e:
            failed += 1
            print("  FAIL: {} - {}".format(name, e))
        gc.collect()

    print("\n{} passed, {} failed out of {} tests".format(passed, failed, passed + failed))
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
