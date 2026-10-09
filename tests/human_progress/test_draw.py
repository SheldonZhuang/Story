import numpy as np
import pytest

from tools.human_progress.draw import add_glow, ease, fade, font, wrap_text
from tools.human_progress.layout import LAYOUTS, SUB_BLOCK_H, TITLE_BLOCK_H


@pytest.mark.parametrize("layout", LAYOUTS.values(), ids=lambda l: l.name)
def test_layout_regions_inside_frame_and_not_overlapping(layout):
    title = (layout.title_y, layout.title_y + TITLE_BLOCK_H[layout.name])
    stage = (layout.stage_cy - layout.unit, layout.stage_cy + layout.unit)
    sub = (layout.sub_y, layout.sub_y + SUB_BLOCK_H[layout.name])
    axis = (layout.axis_y - 20, layout.axis_y + 30)
    regions = [title, stage, sub, axis]
    assert all(0 <= a < b <= layout.h for a, b in regions)
    for (a0, a1), (b0, b1) in zip(regions, regions[1:]):
        assert a1 <= b0, (a1, b0)
    assert layout.stage_cx - layout.unit >= 0 and layout.stage_cx + layout.unit <= layout.w
    assert layout.sub_max_w <= layout.w and 0 <= layout.axis_x0 < layout.axis_x1 <= layout.w


def test_ease_and_fade_endpoints():
    assert (ease(-1), ease(0), ease(0.5), ease(1), ease(2)) == (0, 0, 0.5, 1, 1)
    assert fade(0, 1, 2) == 0 and fade(3, 1, 2) == 1 and fade(5, 5, 0) == 1


def test_add_glow_touches_only_bounding_box():
    arr = np.zeros((200, 200, 3), np.float32)
    add_glow(arr, 100, 100, 10, (1, 0.5, 0))
    assert arr[100, 100, 0] == pytest.approx(1) and arr[100, 100, 2] == 0
    mask = arr.sum(axis=2) > 0
    ys, xs = np.nonzero(mask)
    assert ys.min() >= 70 and ys.max() <= 130 and xs.min() >= 70 and xs.max() <= 130


@pytest.mark.parametrize("text", [
    "芯片上的晶体管，从几个变成了数百亿个，",
    "In the 2020s, artificial intelligence learned to understand language, write, and code.",
    "如果核聚变这颗“人造太阳”能够点亮， mixed English words",
])
def test_wrap_text_fits_and_preserves_text(text):
    fnt = font(40)
    lines = wrap_text(text, fnt, 300)
    assert "".join(lines) == text
    assert all(fnt.getlength(l.rstrip()) <= 300 for l in lines)
