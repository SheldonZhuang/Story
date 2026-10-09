"""音频：WAV 读写、旁白摆放、铺底音合成与混音。全部为 48kHz 单声道 float32。"""
from __future__ import annotations

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


def ambient(duration: float, seed: int = 7) -> np.ndarray:
    """低频和弦铺底 + 缓慢起伏 + 少量柔化噪声；固定种子保证可复现。"""
    n = round(duration * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    for freq, amp in ((55.0, 0.5), (82.4, 0.32), (110.0, 0.25), (164.8, 0.12), (220.0, 0.06)):
        lfo = 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(0.02, 0.06) * t + rng.uniform(0, 2 * np.pi))
        out += amp * lfo * np.sin(2 * np.pi * freq * t + rng.uniform(0, 2 * np.pi))
    noise = np.convolve(rng.standard_normal(n), np.ones(400) / 400, mode="same")
    out += 0.4 * noise / (np.abs(noise).max() + 1e-9)
    fade = np.minimum(1, np.minimum(t, duration - t) / 3.0)
    out *= np.clip(fade, 0, 1)
    return (out / (np.abs(out).max() + 1e-9)).astype(np.float32)


def mix(narration: np.ndarray, bed: np.ndarray, bed_db: float = -18.0) -> np.ndarray:
    n = len(narration)
    out = narration + np.resize(bed, n) * 10 ** (bed_db / 20)
    peak = np.abs(out).max()
    if peak > PEAK:
        out *= PEAK / peak
    return out.astype(np.float32)
