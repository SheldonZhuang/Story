"""程序作曲的原创配乐：C 大调，92 BPM，随段落增减乐器，在旁白下自动压低。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .audio import SR
from .timeline import Timeline

BPM = 92
BEAT = 60 / BPM
BAR = 4 * BEAT
DUCK_DB = -10.0  # 旁白时音乐压低的幅度

# 和弦：名称 → MIDI 音高（低到高）
CHORDS = {
    "C": (48, 55, 60, 64), "G": (43, 55, 59, 62), "Am": (45, 57, 60, 64), "F": (41, 57, 60, 65),
    "Fmaj7": (41, 57, 64, 65), "Em7": (40, 55, 59, 62), "Am7": (45, 55, 60, 64),
}
MAIN_LOOP = ("C", "G", "Am", "F")
FUTURE_LOOP = ("Fmaj7", "G", "Em7", "Am7")
CADENCE = ("F", "G", "C")

# 各段各声部的音量（铺底、钟琴、琶音、低音、沙锤）
LAYERS = ("pad", "bell", "arp", "bass", "shaker")
INTENSITY = {
    "S01": (0.8, 0.25, 0.0, 0.0, 0.0),
    "S02": (0.8, 0.45, 0.0, 0.0, 0.0),
    "S03": (0.8, 0.5, 0.15, 0.0, 0.0),
    "S04": (0.8, 0.55, 0.3, 0.2, 0.0),
    "S05": (0.8, 0.6, 0.4, 0.35, 0.0),
    "S06": (0.75, 0.6, 0.7, 0.6, 0.35),
    "S07": (0.75, 0.65, 0.8, 0.7, 0.45),
    "S08": (0.75, 0.6, 0.8, 0.75, 0.45),
    "S09": (0.7, 0.7, 0.9, 0.8, 0.55),
    "S10": (0.7, 0.75, 1.0, 0.85, 0.6),
    "S11": (1.0, 0.8, 0.35, 0.0, 0.0),
    "S12": (1.0, 0.6, 0.2, 0.3, 0.0),
}
LEVEL = {"pad": 0.08, "bell": 0.2, "arp": 0.12, "bass": 0.22, "shaker": 0.035}

# 钟琴旋律：4 小节一句，每项为（拍位置, 和弦内音序号, 八度偏移, 时值拍数）
MELODY = (
    ((0, 2, 1, 1.5), (1.5, 3, 1, 0.5), (2, 1, 1, 2)),
    ((0, 3, 1, 1), (1, 2, 1, 1), (2, 1, 1, 2)),
    ((0, 2, 1, 1.5), (1.5, 3, 1, 0.5), (2, 3, 1, 1), (3, 2, 1, 1)),
    ((0, 1, 1, 3),),
)


def midi_hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _chord_name(tl: Timeline, bar: int, n_bars: int) -> str:
    if bar >= n_bars - len(CADENCE):
        return CADENCE[min(len(CADENCE) - 1, bar - (n_bars - len(CADENCE)))]
    span = tl.span_at(bar * BAR + 0.01)
    loop = FUTURE_LOOP if span.section.speculative else MAIN_LOOP
    return loop[bar % len(loop)]


def _n_bars(tl: Timeline) -> int:
    return max(len(CADENCE), int(np.ceil(tl.duration / BAR)))


def chord_at(tl: Timeline, t: float) -> tuple[str, tuple[int, ...]]:
    name = _chord_name(tl, int(t // BAR), _n_bars(tl))
    return name, CHORDS[name]


def _env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def _tone(freq: float, dur: float, partials, attack: float, decay: float) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = sum(a * np.sin(2 * np.pi * freq * r * t) for r, a in partials)
    tail = np.minimum(1, (n - np.arange(n)) / (0.05 * SR))  # 结尾 50ms 收尾防爆音
    return (out * _env(n, attack, decay) * tail).astype(np.float32)


def _add(buf: np.ndarray, start: float, sig: np.ndarray) -> None:
    i = int(start * SR)
    if i >= len(buf):
        return
    n = min(len(sig), len(buf) - i)
    buf[i:i + n] += sig[:n]


def _echo(sig: np.ndarray, delay: float = 0.36, feedback: float = 0.35, taps: int = 4) -> np.ndarray:
    out = sig.copy()
    d = int(delay * SR)
    for k in range(1, taps + 1):
        out[d * k:] += sig[:len(sig) - d * k] * feedback ** k
    return out


def _layers(tl: Timeline, n: int) -> dict[str, np.ndarray]:
    bufs = {name: np.zeros(n, np.float32) for name in LAYERS}
    rng = np.random.default_rng(3)
    n_bars = _n_bars(tl)
    for bar in range(n_bars):
        t0 = bar * BAR
        name = _chord_name(tl, bar, n_bars)
        notes = CHORDS[name]
        last = bar == n_bars - 1
        hold = max(BAR, tl.duration - t0) if last else BAR * 1.15
        # 铺底：柔和和弦，慢起音
        for m in notes[1:]:
            _add(bufs["pad"], t0, _tone(midi_hz(m), hold, ((1, 1), (2, 0.25), (3, 0.08)), 0.6, 3.5))
        # 低音：第 1、3 拍
        for beat in (0, 2):
            _add(bufs["bass"], t0 + beat * BEAT,
                 _tone(midi_hz(notes[0] - 12 if notes[0] > 45 else notes[0]), BEAT * 1.8,
                       ((1, 1), (2, 0.3)), 0.01, 0.5))
        # 琶音：八分音符循环和弦内音
        pattern = (notes[1], notes[2], notes[3], notes[2] + 12, notes[3], notes[2], notes[1] + 12, notes[3])
        for k, m in enumerate(pattern):
            _add(bufs["arp"], t0 + k * BEAT / 2,
                 _tone(midi_hz(m), BEAT * 1.2, ((1, 1), (2, 0.5), (3, 0.25), (4, 0.1)), 0.004, 0.28))
        # 钟琴旋律：非整数倍泛音的钟声音色
        for beat, idx, octave, length in MELODY[bar % len(MELODY)]:
            if last and beat > 0:
                break
            m = notes[idx] + 12 * octave
            _add(bufs["bell"], t0 + beat * BEAT,
                 _tone(midi_hz(m), BEAT * length + 1.2, ((1, 1), (2.76, 0.3), (5.4, 0.12)), 0.003, 0.9))
        # 沙锤：八分音符的高频噪声短促声
        for k in range(8):
            burst = int(0.06 * SR)
            noise = rng.standard_normal(burst).astype(np.float32)
            noise = np.diff(noise, prepend=0)  # 一阶差分 = 简单高通
            _add(bufs["shaker"], t0 + k * BEAT / 2, noise * _env(burst, 0.003, 0.02) * (1.0 if k % 2 else 0.6))
    bufs["bell"] = _echo(bufs["bell"])
    return bufs


def _smooth(x: np.ndarray, seconds: float) -> np.ndarray:
    w = max(1, int(seconds * SR))
    c = np.cumsum(np.concatenate([np.zeros(w, np.float64), x.astype(np.float64), np.full(w, x[-1])]))
    return ((c[2 * w:] - c[:-2 * w]) / (2 * w))[: len(x)].astype(np.float32)


def _section_gain(tl: Timeline, n: int, layer: int) -> np.ndarray:
    g = np.zeros(n, np.float32)
    for span in tl.spans:
        g[int(span.start * SR):int(span.end * SR) + 1] = INTENSITY[span.section.id][layer]
    return _smooth(g, 1.5)


def duck_curve(tl: Timeline, n: int) -> np.ndarray:
    """旁白时为 DUCK_DB，静默时为 1，过渡平滑。"""
    speech = np.zeros(n, np.float32)
    for cue in tl.cues:
        speech[max(0, int((cue.start - 0.15) * SR)):int((cue.end + 0.1) * SR)] = 1
    speech = np.clip(_smooth(speech, 0.15) * 1.6, 0, 1)  # 平滑后在句中保持完全压低
    low = 10 ** (DUCK_DB / 20)
    return 1 - (1 - low) * speech


def compose(tl: Timeline) -> np.ndarray:
    """整段配乐（未压低），峰值归一化到 0.9。"""
    n = round(tl.duration * SR)
    bufs = _layers(tl, n)
    out = np.zeros(n, np.float32)
    for i, name in enumerate(LAYERS):
        out += bufs[name] * LEVEL[name] * _section_gain(tl, n, i)
    t = np.arange(n) / SR
    out *= np.clip(np.minimum(t / 2.0, (tl.duration - t) / 2.5), 0, 1)  # 首尾淡入淡出
    return (out / (np.abs(out).max() + 1e-9) * 0.9).astype(np.float32)


def load_track(path: str | Path, duration: float, fade_in: float = 1.5, fade_out: float = 3.0) -> np.ndarray:
    """读取外部音乐文件（任意格式，转为 48kHz 单声道），循环或截断到 duration，首尾淡入淡出。"""
    pcm = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
        check=True, capture_output=True,
    ).stdout
    track = np.frombuffer(pcm, "<i2").astype(np.float32) / 32768.0
    if len(track) == 0:
        raise ValueError(f"{path} 没有可用的音频")
    n = round(duration * SR)
    out = np.resize(track, n)  # 短于视频时从头循环
    t = np.arange(n) / SR
    out *= np.clip(np.minimum(t / fade_in, (duration - t) / fade_out), 0, 1)
    return out.astype(np.float32)
