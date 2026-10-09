import numpy as np
import pytest

from tools.human_progress.audio import SR, write_wav
from tools.human_progress.layout import PORTRAIT
from tools.human_progress.render import probe, render_video
from tools.human_progress.script import Line, Section
from tools.human_progress.timeline import build_timeline, save_timeline


def test_render_short_video(tmp_path):
    sec = Section("S01", "序章", "Prologue", "", "", None, 2, False, (Line("测试。", "Test."),))
    tl = build_timeline([sec], {("S01", 0): 2.0 - 0.9 - 1.4 + 0.5})  # 总长 2.5s
    save_timeline(tl, tmp_path / "tl.json")
    write_wav(tmp_path / "a.wav", np.zeros(round(tl.duration * SR), np.float32))
    out = tmp_path / "v.mp4"
    render_video(tmp_path / "tl.json", PORTRAIT, tmp_path / "a.wav", out, workers=2)
    info = probe(out)
    assert (info["width"], info["height"]) == (1080, 1920)
    assert info["duration"] == pytest.approx(tl.duration, abs=0.1)
