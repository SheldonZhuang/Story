import numpy as np
import pytest

from tools.human_progress.audio import SR
from tools.human_progress.music import chord_at, compose, duck_curve
from tools.human_progress.script import Line, Section
from tools.human_progress.timeline import build_timeline


def _timeline():
    secs = [Section(sid, "", "", "", "", None, 10, sid == "S11", (Line("甲", "a"), Line("乙", "b")))
            for sid in ("S02", "S07", "S11", "S12")]
    return build_timeline(secs, {(s.id, i): 3.0 for s in secs for i in range(2)})


def _rms(x):
    return float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))


def test_compose_length_and_deterministic():
    tl = _timeline()
    a, b = compose(tl), compose(tl)
    assert len(a) == round(tl.duration * SR)
    assert np.array_equal(a, b)
    assert 0 < np.abs(a).max() <= 1


def test_industrial_section_is_fuller_than_ancient():
    tl = _timeline()
    music = compose(tl)
    s02, s07 = tl.spans[0], tl.spans[1]

    def mid(span):  # 段落中间，避开过渡
        return music[round((span.start + 2) * SR):round((span.end - 2) * SR)]

    assert _rms(mid(s07)) > 1.5 * _rms(mid(s02))


def test_music_ducks_under_speech():
    tl = _timeline()
    curve = duck_curve(tl, len(compose(tl)))
    cue = tl.cues[0]
    speaking = curve[round((cue.start + 1) * SR)]
    gap = curve[round((tl.cues[0].end + tl.cues[1].start) / 2 * SR)]
    silent_head = curve[round(0.3 * SR)]
    assert speaking == pytest.approx(10 ** (-10 / 20), rel=0.05)
    assert silent_head == pytest.approx(1.0, rel=0.05)
    assert speaking < gap <= 1.0


def test_ending_resolves_to_tonic():
    tl = _timeline()
    assert chord_at(tl, tl.duration - 0.5)[0] == "C"
    future = tl.spans[2]
    assert chord_at(tl, (future.start + future.end) / 2)[0] in {"Fmaj7", "G", "Em7", "Am7"}
