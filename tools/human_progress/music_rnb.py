"""氛围感 R&B 风格的原创配乐：72 BPM，电钢琴 + 铺底 + 哼唱式旋律 + 低音 + R&B 鼓组，带混响。"""
from __future__ import annotations

import numpy as np

from .audio import SR
from .music import _add, _env, _section_gain, midi_hz
from .timeline import Timeline

BPM = 72
BEAT = 60 / BPM
BAR = 4 * BEAT

# 和弦：根音 + 上方声部（MIDI）
CHORDS = {
    "Fmaj9": (41, (57, 60, 64, 67)), "Em7": (40, (55, 59, 62, 64)),
    "Am9": (45, (60, 64, 67, 71)), "G6": (43, (59, 62, 64, 67)),
    "Dm9": (38, (53, 57, 60, 64)), "Bbmaj7": (46, (57, 62, 65, 69)),
    "C6": (48, (55, 60, 64, 69)), "Cmaj9": (48, (64, 67, 71, 74)),
}
MAIN_LOOP = ("Fmaj9", "Em7", "Am9", "G6")
FUTURE_LOOP = ("Dm9", "Bbmaj7", "Fmaj9", "C6")
CADENCE = ("Fmaj9", "G6", "Cmaj9")

LAYERS = ("pad", "ep", "lead", "bass", "kick", "snare", "hat")
INTENSITY = {
    "S01": (0.7, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0),
    "S02": (0.7, 0.7, 0.3, 0.0, 0.0, 0.0, 0.0),
    "S03": (0.7, 0.8, 0.4, 0.3, 0.0, 0.0, 0.0),
    "S04": (0.6, 0.8, 0.5, 0.5, 0.0, 0.0, 0.3),
    "S05": (0.6, 0.8, 0.5, 0.6, 0.5, 0.3, 0.4),
    "S06": (0.5, 0.8, 0.6, 0.8, 0.8, 0.7, 0.6),
    "S07": (0.5, 0.8, 0.6, 0.85, 0.9, 0.8, 0.7),
    "S08": (0.5, 0.8, 0.7, 0.85, 0.9, 0.8, 0.7),
    "S09": (0.5, 0.8, 0.7, 0.9, 1.0, 0.9, 0.8),
    "S10": (0.5, 0.85, 0.8, 0.9, 1.0, 0.9, 0.9),
    "S11": (1.0, 0.7, 0.8, 0.3, 0.0, 0.0, 0.2),
    "S12": (0.9, 0.8, 0.4, 0.4, 0.0, 0.0, 0.0),
}
LEVEL = {"pad": 0.05, "ep": 0.1, "lead": 0.09, "bass": 0.2, "kick": 0.5, "snare": 0.12, "hat": 0.03}
REVERB_SEND = {"pad": 0.5, "ep": 0.35, "lead": 0.6, "snare": 0.3}

# 电钢琴节奏：（拍位置, 是否全和弦, 力度）
EP_RHYTHM = ((0, True, 1.0), (1.5, False, 0.6), (2.5, True, 0.75), (3.5, False, 0.5))
# 哼唱旋律：4 小节一句，（拍位置, 从最高声部往下数第几个音, 时值拍数）
LEAD = (
    ((0.5, 1, 1.0), (1.5, 0, 1.5), (3.0, 1, 1.0)),
    ((0.0, 2, 2.0), (2.5, 1, 1.5)),
    ((0.5, 0, 1.0), (1.5, 1, 1.0), (2.5, 0, 1.5)),
    ((0.0, 1, 3.5),),
)
# 鼓：底鼓与军鼓所在拍位；踩镲为八分音符，每 4 小节最后一拍加十六分滚奏
KICK_BEATS = (0, 1.75, 2.5)
SNARE_BEATS = (1, 3)


def _n_bars(tl: Timeline) -> int:
    return max(len(CADENCE), int(np.ceil(tl.duration / BAR)))


def _chord_name(tl: Timeline, bar: int, n_bars: int) -> str:
    if bar >= n_bars - len(CADENCE):
        return CADENCE[min(len(CADENCE) - 1, bar - (n_bars - len(CADENCE)))]
    span = tl.span_at(bar * BAR + 0.01)
    return (FUTURE_LOOP if span.section.speculative else MAIN_LOOP)[bar % 4]


def chord_at(tl: Timeline, t: float) -> tuple[str, tuple[int, tuple[int, ...]]]:
    name = _chord_name(tl, int(t // BAR), _n_bars(tl))
    return name, CHORDS[name]


def _rhodes(freq: float, dur: float, vel: float) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * 2 * freq * t) * np.exp(-t / 0.3)
    tone += 0.08 * np.sin(2 * np.pi * 3 * freq * t) * np.exp(-t / 0.15)  # 起音时的“叮”声
    trem = 1 - 0.12 * (0.5 + 0.5 * np.sin(2 * np.pi * 4.5 * t))
    tail = np.minimum(1, (n - np.arange(n)) / (0.08 * SR))
    return (vel * tone * trem * _env(n, 0.004, 1.6) * tail).astype(np.float32)


def _hum(freq: float, dur: float) -> np.ndarray:
    """哼唱式旋律：慢起音，0.25 秒后加入颤音。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 0.25 * np.clip((t - 0.25) / 0.3, 0, 1) * np.sin(2 * np.pi * 5.0 * t)
    f = freq * 2 ** (vib / 12)
    phase = 2 * np.pi * np.cumsum(f) / SR
    tone = np.sin(phase) + 0.18 * np.sin(2 * phase) + 0.05 * np.sin(3 * phase)
    env = np.minimum(1, t / 0.09) * np.minimum(1, (dur - t) / 0.25).clip(0, 1)
    return (tone * env).astype(np.float32)


def _pad(notes: tuple[int, ...], dur: float) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in notes:
        for detune in (-0.06, 0.06):  # 轻微失谐，让铺底更宽
            out += np.sin(2 * np.pi * midi_hz(m + 12 + detune) * t)
    env = np.minimum(1, t / 1.2) * np.minimum(1, (dur - t) / 1.0).clip(0, 1)
    return (out * env / (2 * len(notes))).astype(np.float32)


def _kick() -> np.ndarray:
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    f = 45 + 75 * np.exp(-t / 0.04)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.28)
    click = np.exp(-t / 0.004) * 0.3
    return (body + click).astype(np.float32)


def _snare(rng: np.random.Generator) -> np.ndarray:
    """拍手式军鼓：三次快速的噪声脉冲 + 一点鼓身。"""
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    noise = np.diff(rng.standard_normal(n + 1))
    env = np.zeros(n)
    for k, d in enumerate((0.0, 0.011, 0.022)):
        env += np.where(t >= d, np.exp(-(t - d) / (0.012 if k < 2 else 0.14)), 0)
    body = 0.4 * np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.06)
    return (0.5 * noise * env + body).astype(np.float32)


def _hat(rng: np.random.Generator, length: float = 0.035) -> np.ndarray:
    n = int(length * SR)
    noise = np.diff(np.diff(rng.standard_normal(n + 2)))  # 二阶差分 = 更强的高通
    return (noise * _env(n, 0.001, length / 3) * 0.5).astype(np.float32)


def reverb(sig: np.ndarray, decay: float = 1.1, length: float = 2.6, wet: float = 0.3,
           seed: int = 5, block: int = 1 << 19) -> np.ndarray:
    """合成混响：用指数衰减的噪声作冲激响应，分块 FFT 卷积，控制内存占用。"""
    rng = np.random.default_rng(seed)
    m = int(length * SR)
    t = np.arange(m) / SR
    ir = rng.standard_normal(m) * np.exp(-t / (decay / 6.9))  # decay 为 -60dB 时间
    ir[: int(0.012 * SR)] = 0  # 12ms 预延迟
    ir /= np.sqrt(np.sum(ir ** 2))
    nfft = 1 << int(np.ceil(np.log2(block + m - 1)))
    ir_f = np.fft.rfft(ir, nfft)
    out = np.zeros(len(sig) + m, np.float64)
    for i in range(0, len(sig), block):
        seg = sig[i:i + block].astype(np.float64)
        conv = np.fft.irfft(np.fft.rfft(seg, nfft) * ir_f, nfft)[: len(seg) + m - 1]
        out[i:i + len(conv)] += conv
    return (sig + wet * out[: len(sig)]).astype(np.float32)


def _layers(tl: Timeline, n: int) -> dict[str, np.ndarray]:
    bufs = {name: np.zeros(n, np.float32) for name in LAYERS}
    rng = np.random.default_rng(11)
    n_bars = _n_bars(tl)
    kick = _kick()
    for bar in range(n_bars):
        t0 = bar * BAR
        root, upper = CHORDS[_chord_name(tl, bar, n_bars)]
        last = bar == n_bars - 1
        span_len = max(BAR, tl.duration - t0) if last else BAR * 1.1
        _add(bufs["pad"], t0, _pad(upper, span_len))
        for beat, full, vel in (EP_RHYTHM[:1] if last else EP_RHYTHM):
            notes = upper if full else upper[2:]
            for m in notes:
                _add(bufs["ep"], t0 + beat * BEAT, _rhodes(midi_hz(m), span_len if last else 2.2, vel))
        if not last:
            for beat, voice, length in LEAD[bar % len(LEAD)]:
                m = sorted(upper, reverse=True)[voice] + 12
                _add(bufs["lead"], t0 + beat * BEAT, _hum(midi_hz(m), length * BEAT))
        bass_f = midi_hz(root if root >= 40 else root + 12)
        for beat, length in (((0, span_len / BEAT),) if last else ((0, 2.4), (2.5, 1.4))):
            nb = int(length * BEAT * SR)
            tb = np.arange(nb) / SR
            note = (np.sin(2 * np.pi * bass_f * tb) + 0.35 * np.sin(4 * np.pi * bass_f * tb))  # 二次谐波让小喇叭也听得见
            note *= np.minimum(1, tb / 0.01) * np.minimum(1, (length * BEAT - tb) / 0.1).clip(0, 1)
            _add(bufs["bass"], t0 + beat * BEAT, note.astype(np.float32))
        if last:
            continue
        for beat in KICK_BEATS:
            _add(bufs["kick"], t0 + beat * BEAT, kick)
        for beat in SNARE_BEATS:
            _add(bufs["snare"], t0 + beat * BEAT, _snare(rng))
        for k in range(8):
            _add(bufs["hat"], t0 + k * BEAT / 2, _hat(rng) * (1.0 if k % 2 == 0 else 0.6))
        if bar % 4 == 3:  # 句尾踩镲滚奏
            for k in range(4):
                _add(bufs["hat"], t0 + 3 * BEAT + k * BEAT / 4, _hat(rng, 0.02) * (0.5 + 0.12 * k))
    return bufs


def compose(tl: Timeline) -> np.ndarray:
    """整段配乐（未压低），峰值归一化到 0.9。"""
    n = round(tl.duration * SR)
    bufs = _layers(tl, n)
    dry = np.zeros(n, np.float32)
    send = np.zeros(n, np.float32)
    for i, name in enumerate(LAYERS):
        layer = bufs[name] * LEVEL[name] * _section_gain(tl, n, INTENSITY, i)
        dry += layer
        send += layer * REVERB_SEND.get(name, 0.0)
    out = dry + reverb(send, wet=1.0) - send  # reverb() 返回 干+湿，这里只取湿声
    t = np.arange(n) / SR
    out *= np.clip(np.minimum(t / 2.0, (tl.duration - t) / 3.0), 0, 1)
    return (out / (np.abs(out).max() + 1e-9) * 0.9).astype(np.float32)
