from pathlib import Path

import pytest

from tools.human_progress.frame import render_frame
from tools.human_progress.layout import LAYOUTS
from tools.human_progress.scenes import SCENES
from tools.human_progress.script import load_script
from tools.human_progress.timeline import build_timeline

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "human-progress.md"
SECTIONS = load_script(SCRIPT)
# 用每句 2 秒的假时长，测试不依赖网络配音
TL = build_timeline(SECTIONS, {(s.id, i): 2.0 for s in SECTIONS for i in range(len(s.lines))})


def test_every_section_has_a_scene():
    assert set(SCENES) == {s.id for s in SECTIONS}


@pytest.mark.parametrize("layout", LAYOUTS.values(), ids=lambda l: l.name)
@pytest.mark.parametrize("span", TL.spans, ids=lambda s: s.section.id)
def test_frames_render_with_content(layout, span):
    for t in (span.start + 0.05, (span.start + span.end) / 2, span.end - 0.05):
        img = render_frame(TL, layout, t)
        assert img.shape == (layout.h, layout.w, 3) and img.dtype.name == "uint8"
        assert img.max() > 60  # 至少有时间轴 / 标题 / 主画面，不是全黑
