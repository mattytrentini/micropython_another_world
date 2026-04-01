"""Tests for the polygon renderer.

Run with: python3 tests/test_polygon.py
"""

import sys
sys.path.insert(0, ".")

from aw.video import Video, STRIDE
from aw.polygon import PolygonRenderer
from aw.consts import SCREEN_W, SCREEN_H, PAGE_SIZE


def make_renderer():
    """Create a Video + PolygonRenderer pair."""
    video = Video()
    poly = PolygonRenderer(video)
    video.polygon = poly
    return video, poly


def test_draw_point():
    """Draw a single point (degenerate polygon)."""
    video, poly = make_renderer()
    video.fill_page(0, 0)  # clear
    video.buffers[0] = 0

    # Shape data for a degenerate polygon: bbw=0, bbh=1, 4 vertices all at origin
    # preceded by the shape type byte >= 0xC0
    shape = bytearray([
        0xC0,        # type byte >= 0xC0 -> simple polygon, color from data = 0
        0x00,        # bbw = 0
        0x01,        # bbh = 1
        0x04,        # numVertices = 4
        0x00, 0x00,  # vertex 0
        0x00, 0x00,  # vertex 1
        0x00, 0x00,  # vertex 2
        0x00, 0x00,  # vertex 3
    ])

    poly.set_data(shape, 0)
    # color=0xFF means take from data (0xC0 & 0x3F = 0)
    # But let's use a direct color for testing
    poly.draw_shape(5, 64, 100, 50)

    buf = video.page_bufs[0]
    off = 50 * STRIDE + 100 // 2  # 50
    # Pixel at x=100 (even), should be in high nibble
    assert (buf[off] >> 4) == 5, "Expected color 5 at pixel (100,50), got {}".format(buf[off] >> 4)


def test_draw_small_quad():
    """Draw a small 4-vertex polygon (rectangle)."""
    video, poly = make_renderer()
    video.fill_page(0, 0)
    video.buffers[0] = 0

    # A 10x10 rectangle centered at (100, 50)
    # Quad-strip vertex order: the algorithm takes first vertex as right start,
    # last vertex as left start, then steps right edge forward (i++) and left
    # edge backward (j--) in pairs.
    # Order: [0]=top-right, [1]=bottom-right, [2]=bottom-left, [3]=top-left
    shape = bytearray([
        0xC0,        # type: simple polygon
        10,          # bbw = 10 (before zoom)
        10,          # bbh = 10
        4,           # numVertices = 4
        10, 0,       # vertex 0: (10, 0) - top right
        10, 10,      # vertex 1: (10, 10) - bottom right
        0, 10,       # vertex 2: (0, 10) - bottom left
        0, 0,        # vertex 3: (0, 0) - top left
    ])

    poly.set_data(shape, 0)
    poly.draw_shape(3, 64, 100, 50)  # color=3, zoom=1:1

    buf = video.page_bufs[0]
    # Check that pixels within the rectangle area are set
    # Rectangle should be centered at (100,50), spanning ~(95,45) to (105,55)
    center_off = 50 * STRIDE + 100 // 2
    # At minimum the center pixel should be drawn
    center_val = buf[center_off]
    assert center_val != 0, "Expected non-zero pixels at center of rectangle"


def test_draw_shape_color_from_data():
    """When color has bit 7 set (0xFF), color is taken from shape data."""
    video, poly = make_renderer()
    video.fill_page(0, 0)
    video.buffers[0] = 0

    # 0xC7 -> type >= 0xC0, color from data = 0xC7 & 0x3F = 7
    shape = bytearray([
        0xC7,        # type: simple polygon, embedded color = 7
        0x00, 0x01, 0x04,
        0x00, 0x00,
        0x00, 0x00,
        0x00, 0x00,
        0x00, 0x00,
    ])

    poly.set_data(shape, 0)
    poly.draw_shape(0xFF, 64, 50, 50)  # 0xFF -> take color from data

    buf = video.page_bufs[0]
    off = 50 * STRIDE + 50 // 2
    pixel = (buf[off] >> 4) & 0x0F  # x=50 is even -> high nibble
    assert pixel == 7, "Expected color 7, got {}".format(pixel)


def test_draw_blend_point():
    """Blend mode sets bit 3 of the nibble."""
    video, poly = make_renderer()
    # Fill page with color 1 (0x11 per byte)
    video.fill_page(0, 1)
    video.buffers[0] = 0

    shape = bytearray([
        0xC0, 0x00, 0x01, 0x04,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ])

    poly.set_data(shape, 0)
    poly.draw_shape(0x10, 64, 50, 50)  # blend mode

    buf = video.page_bufs[0]
    off = 50 * STRIDE + 50 // 2
    # Blend on color 1 (0x01 nibble): should set bit 3 -> 0x09
    pixel = (buf[off] >> 4) & 0x0F  # even pixel
    assert pixel & 0x08, "Expected bit 3 set, got 0x{:X}".format(pixel)


def test_hierarchical_shape():
    """Test hierarchical shape with child sub-shapes."""
    video, poly = make_renderer()
    video.fill_page(0, 0)
    video.buffers[0] = 0

    # Build a hierarchical shape:
    # At offset 0: hierarchy header
    # At offset N: child shape (simple point)
    #
    # Hierarchy format (after the type byte is read by draw_shape):
    #   byte: origin_x offset from parent
    #   byte: origin_y offset from parent
    #   byte: numChildren (0 = 1 child, loop: for ; n >= 0; --n)
    #   word: child offset (word offset, *2 for byte offset)
    #   byte: child_x offset from hierarchy origin
    #   byte: child_y offset from hierarchy origin

    # Child shape at byte offset 20 (= word offset 10)
    child_word_offset = 10  # byte offset = 10 * 2 = 20

    shape = bytearray(40)
    # Hierarchy at offset 0 (type byte 0x02 read by draw_shape)
    shape[0] = 0x02      # type = hierarchy (& 0x3F == 2)
    shape[1] = 0         # origin_x offset
    shape[2] = 0         # origin_y offset
    shape[3] = 0         # numChildren = 0 means 1 child
    shape[4] = (child_word_offset >> 8) & 0xFF  # offset high byte
    shape[5] = child_word_offset & 0xFF          # offset low byte
    shape[6] = 0         # child x offset
    shape[7] = 0         # child y offset

    # Child at byte offset 20 (word_offset * 2)
    shape[20] = 0xC5     # simple polygon, color = 5
    shape[21] = 0        # bbw
    shape[22] = 1        # bbh
    shape[23] = 4        # numPoints
    # 4 vertices at (0,0) - 8 more bytes
    shape[24] = 0; shape[25] = 0
    shape[26] = 0; shape[27] = 0
    shape[28] = 0; shape[29] = 0
    shape[30] = 0; shape[31] = 0

    poly.set_data(shape, 0)
    poly.draw_shape(0xFF, 64, 80, 80)

    buf = video.page_bufs[0]
    off = 80 * STRIDE + 80 // 2
    pixel = (buf[off] >> 4) & 0x0F
    assert pixel == 5, "Expected color 5 from child shape, got {}".format(pixel)


def test_zoom():
    """Test that zoom scales a quad to larger size."""
    video, poly = make_renderer()
    video.fill_page(0, 0)
    video.buffers[0] = 0

    # A 10x10 quad at zoom=128 (2x) should become 20x20
    # Quad-strip order: top-right, bottom-right, bottom-left, top-left
    shape = bytearray([
        0xC0,        # type: simple polygon
        10, 10,      # bbw=10, bbh=10
        4,           # numVertices
        10, 0,       # vertex 0: top right
        10, 10,      # vertex 1: bottom right
        0, 10,       # vertex 2: bottom left
        0, 0,        # vertex 3: top left
    ])

    poly.set_data(shape, 0)
    poly.draw_shape(7, 128, 100, 100)  # zoom 128 = 2x

    buf = video.page_bufs[0]
    # At 2x zoom, bbw=20, bbh=20, centered at (100,100)
    # So rectangle spans (90,90) to (110,110)
    # Check center pixel
    off = 100 * STRIDE + 100 // 2
    center = (buf[off] >> 4) & 0x0F
    assert center == 7, "Expected color 7 at center, got {}".format(center)
    # Check a pixel that should be inside at 2x but outside at 1x
    off2 = 92 * STRIDE + 92 // 2
    edge = (buf[off2] >> 4) & 0x0F
    assert edge == 7, "Expected color 7 at (92,92) with 2x zoom, got {}".format(edge)


def test_out_of_bounds():
    """Polygon fully off-screen should not crash."""
    video, poly = make_renderer()
    video.fill_page(0, 0)
    video.buffers[0] = 0

    shape = bytearray([
        0xC0, 10, 10, 4,
        10, 0, 0, 0, 0, 10, 10, 10,
    ])

    poly.set_data(shape, 0)
    # Draw way off-screen
    poly.draw_shape(5, 64, -100, -100)
    poly.set_data(shape, 0)
    poly.draw_shape(5, 64, 500, 500)
    # Should not crash


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
