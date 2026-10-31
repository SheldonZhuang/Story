import numpy as np

from tools.human_progress.audio import SR
from tools.human_progress.music_rnb import BAR, chord_at, compose, reverb
from tools.human_progress.script import Line, Section
from tools.human_progress.timeline import build_timeline


def _timeline():
    secs = [Section(sid, "", "", "", "", None, 10, sid == "S11", (Line("甲", "a"), Line("乙", "b")))
            for sid in ("S02", "S07", "S11", "S12")]
    return build_timeline(secs, {(s.id, i): 3.0 for s in secs for i in range(2)})


def _rms(x):
    return float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))


def _mid(music, span):
    return music[round((span.start + 2) * SR):round((span.end - 2) * SR)]


def test_compose_length_deterministic_and_bounded():
    tl = _timeline()
    a, b = compose(tl), compose(tl)
    assert len(a) == round(tl.duration * SR)
    assert np.array_equal(a, b)
    assert 0 < np.abs(a).max() <= 1


def test_drums_build_in_industrial_and_drop_in_future():
    tl = _timeline()
    music = compose(tl)
    s02, s07, s11 = tl.spans[0], tl.spans[1], tl.spans[2]
    assert _rms(_mid(music, s07)) > 1.5 * _rms(_mid(music, s02))

    def low_band(x):  # 底鼓 / 低音所在的 40–120Hz 能量
        spec = np.abs(np.fft.rfft(x))
        f = np.fft.rfftfreq(len(x), 1 / SR)
        return spec[(f > 40) & (f < 120)].sum() / spec.sum()

    assert low_band(_mid(music, s07)) > 2 * low_band(_mid(music, s11))


def test_chords_follow_sections_and_resolve():
    tl = _timeline()
    assert chord_at(tl, tl.duration - 0.5)[0] == "Cmaj9"
    future = tl.spans[2]
    first_future_bar = np.ceil(future.start / BAR) * BAR + 0.1  # 整小节都落在未来段内
    assert chord_at(tl, first_future_bar)[0] in {"Dm9", "Bbmaj7", "Fmaj9", "C6"}


def test_reverb_extends_tail_and_keeps_length():
    impulse = np.zeros(SR * 3, np.float32)
    impulse[0] = 1
    wet = reverb(impulse, decay=0.8, wet=1.0)
    assert len(wet) == len(impulse)
    early, late = _rms(wet[SR // 10:SR // 5]), _rms(wet[SR * 2 // 5:SR // 2])
    assert early > late > 0  # 有尾音，且随时间衰减
    assert _rms(wet[2 * SR:]) < early / 100  # 2 秒后基本消失
    assert np.abs(wet).max() <= 1.5
