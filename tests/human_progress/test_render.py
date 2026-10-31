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


def test_failed_render_keeps_previous_output(tmp_path):
    out = tmp_path / "v.mp4"
    out.write_bytes(b"previous good video")
    sec = Section("S01", "", "", "", "", None, 2, False, (Line("测试。", "Test."),))
    tl = build_timeline([sec], {("S01", 0): 0.5})
    save_timeline(tl, tmp_path / "tl.json")
    with pytest.raises(Exception):
        # 音频文件不存在 → FFmpeg 失败
        render_video(tmp_path / "tl.json", PORTRAIT, tmp_path / "missing.wav", out, workers=1)
    assert out.read_bytes() == b"previous good video"


def test_default_workers_respects_cpu_and_memory():
    from tools.human_progress.render import RESERVE_MB, WORKER_MB, default_workers
    assert default_workers(cpu=8, avail_mb=None) == 8
    assert default_workers(cpu=8, avail_mb=RESERVE_MB + 3.5 * WORKER_MB) == 3
    assert default_workers(cpu=8, avail_mb=100_000) == 8
    assert default_workers(cpu=8, avail_mb=500) == 1


def test_remux_audio_keeps_video_and_replaces_audio(tmp_path):
    from tools.human_progress.render import remux_audio
    sec = Section("S01", "", "", "", "", None, 2, False, (Line("测试。", "Test."),))
    tl = build_timeline([sec], {("S01", 0): 0.5})
    save_timeline(tl, tmp_path / "tl.json")
    n = round(tl.duration * SR)
    write_wav(tmp_path / "silent.wav", np.zeros(n, np.float32))
    out = tmp_path / "v.mp4"
    render_video(tmp_path / "tl.json", PORTRAIT, tmp_path / "silent.wav", out, workers=1)
    tone = (0.5 * np.sin(2 * np.pi * 440 * np.arange(n) / SR)).astype(np.float32)
    write_wav(tmp_path / "tone.wav", tone)
    remux_audio(out, tmp_path / "tone.wav")
    import subprocess
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-f", "s16le", "-ac", "1", "-"],
                         capture_output=True, check=True).stdout
    assert np.abs(np.frombuffer(pcm, "<i2")).max() > 8000  # 新音轨确实换进去了
    assert probe(out)["width"] == 1080
