import numpy as np
import pytest

from tools.human_progress.audio import SR, ambient, mix, place_narration, read_wav, write_wav
from tools.human_progress.script import Line, Section
from tools.human_progress.timeline import build_timeline


def _timeline():
    sec = Section("S01", "", "", "", "", None, 5, False, (Line("a", "a"), Line("b", "b")))
    return build_timeline([sec], {("S01", 0): 1.0, ("S01", 1): 0.5})


def test_place_narration_positions_clips_at_cue_starts():
    tl = _timeline()
    clips = {("S01", 0): np.full(SR, 0.5, np.float32), ("S01", 1): np.full(SR // 2, -0.25, np.float32)}
    out = place_narration(tl, clips)
    assert len(out) == round(tl.duration * SR)
    for cue, value in zip(tl.cues, (0.5, -0.25)):
        i = round(cue.start * SR)
        assert out[i - 1] == 0 and out[i] == pytest.approx(value)


def test_ambient_length_and_reproducible():
    a, b = ambient(2.0), ambient(2.0)
    assert len(a) == 2 * SR and np.array_equal(a, b)
    assert 0 < np.abs(a).max() <= 1


def test_mix_limits_peak():
    loud = np.ones(SR, np.float32) * 1.5
    out = mix(loud, np.ones(SR, np.float32))
    assert np.abs(out).max() <= 0.98 + 1e-6 and len(out) == SR


def test_wav_round_trip(tmp_path):
    sig = (np.sin(np.linspace(0, 100, SR)) * 0.5).astype(np.float32)
    write_wav(tmp_path / "x.wav", sig)
    back = read_wav(tmp_path / "x.wav")
    assert len(back) == SR and np.abs(back - sig).max() < 1e-3
