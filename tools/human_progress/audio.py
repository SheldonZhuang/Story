"""音频：WAV 读写、旁白摆放、铺底音合成与混音。全部为 48kHz 单声道 float32。"""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

from .timeline import Timeline

SR = 48_000
PEAK = 0.98


def read_wav(path: str | Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, SR):
            raise ValueError(f"{path} 需要 {SR}Hz 16bit 单声道")
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    return data.astype(np.float32) / 32768.0


def write_wav(path: str | Path, signal: np.ndarray) -> None:
    pcm = (np.clip(signal, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def trim_silence(signal: np.ndarray, threshold: float = 0.01, lead: float = 0.04,
                 trail: float = 0.12) -> np.ndarray:
    """裁掉首尾静音（10ms 平滑包络低于阈值的部分），两端各保留一点余量。"""
    env = np.convolve(np.abs(signal), np.ones(480) / 480, mode="same")
    loud = np.nonzero(env > threshold)[0]
    if len(loud) == 0:
        return signal[:0]
    i0 = max(0, loud[0] - round(lead * SR))
    i1 = min(len(signal), loud[-1] + round(trail * SR))
    return signal[i0:i1]


def place_narration(tl: Timeline, clips: dict[tuple[str, int], np.ndarray]) -> np.ndarray:
    out = np.zeros(round(tl.duration * SR), np.float32)
    for cue in tl.cues:
        clip = clips[(cue.section_id, cue.index)]
        i = round(cue.start * SR)
        n = min(len(clip), len(out) - i)
        out[i:i + n] += clip[:n]
    return out


def mix(narration: np.ndarray, music: np.ndarray, duck: np.ndarray, music_db: float = -12.0) -> np.ndarray:
    """配乐整体响度比旁白发声部分低 music_db，再乘以压低曲线；峰值限制在 PEAK。"""
    speech = narration[np.abs(narration) > 0.01]
    speech_rms = float(np.sqrt(np.mean(speech.astype(np.float64) ** 2))) if len(speech) else 0.1
    music_rms = float(np.sqrt(np.mean(music.astype(np.float64) ** 2))) or 1.0
    gain = speech_rms / music_rms * 10 ** (music_db / 20)
    out = narration + music[: len(narration)] * duck[: len(narration)] * gain
    peak = np.abs(out).max()
    if peak > PEAK:
        out *= PEAK / peak
    return out.astype(np.float32)


TARGET_LUFS = -16.0  # 主流视频平台的常用响度


def normalize_loudness(src: str | Path, dst: str | Path, lufs: float = TARGET_LUFS) -> None:
    """轻度压缩 + FFmpeg loudnorm 统一响度（真峰值 ≤ -1.5dBTP），输出 48kHz 单声道 16bit WAV。"""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src),
         # 先轻度压缩人声峰值，否则真峰值限制会让 loudnorm 达不到目标响度
         "-af", "acompressor=threshold=0.1:ratio=3:attack=5:release=120:makeup=2,"
                f"loudnorm=I={lufs}:TP=-1.5:LRA=11",
         "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16",
         str(dst)],
        check=True,
    )
