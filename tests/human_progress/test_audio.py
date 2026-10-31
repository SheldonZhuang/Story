import numpy as np
import pytest

from tools.human_progress.audio import (
    SR, mix, place_narration, read_wav, trim_silence, write_wav,
)
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


def test_trim_silence_keeps_speech_with_small_margins():
    sig = np.zeros(3 * SR, np.float32)
    sig[SR:2 * SR] = 0.5  # 中间 1 秒有声
    out = trim_silence(sig)
    assert 1.0 < len(out) / SR < 1.0 + 0.04 + 0.12 + 0.02
    assert np.abs(out).max() == pytest.approx(0.5)
    assert len(trim_silence(np.zeros(SR, np.float32))) == 0


def test_mix_limits_peak():
    loud = np.ones(SR, np.float32) * 1.5
    out = mix(loud, np.ones(SR, np.float32), np.ones(SR, np.float32))
    assert np.abs(out).max() <= 0.98 + 1e-6 and len(out) == SR


def test_mix_sets_music_level_relative_to_speech():
    speech = np.zeros(2 * SR, np.float32)
    speech[:SR] = 0.2  # 前 1 秒说话
    music = np.full(2 * SR, 0.5, np.float32)
    out = mix(speech, music, np.ones(2 * SR, np.float32), music_db=-12)
    assert out[SR + 10] == pytest.approx(0.2 * 10 ** (-12 / 20), rel=1e-3)


def test_wav_round_trip(tmp_path):
    sig = (np.sin(np.linspace(0, 100, SR)) * 0.5).astype(np.float32)
    write_wav(tmp_path / "x.wav", sig)
    back = read_wav(tmp_path / "x.wav")
    assert len(back) == SR and np.abs(back - sig).max() < 1e-3


def test_normalize_loudness_raises_quiet_audio(tmp_path):
    from tools.human_progress.audio import normalize_loudness
    t = np.arange(5 * SR) / SR
    quiet = (0.02 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    write_wav(tmp_path / "q.wav", quiet)
    normalize_loudness(tmp_path / "q.wav", tmp_path / "n.wav")
    out = read_wav(tmp_path / "n.wav")
    rms_db = 20 * np.log10(np.sqrt(np.mean(out[SR:-SR] ** 2)))
    assert -19 < rms_db < -13  # 正弦波 RMS 约等于 -16 LUFS 附近
    assert np.abs(out).max() <= 10 ** (-1.4 / 20)
