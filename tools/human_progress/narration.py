"""逐句配音：edge-tts（默认）或 Windows 离线语音，输出 48kHz 单声道 WAV，按内容哈希缓存。"""
from __future__ import annotations

import asyncio
import hashlib
import subprocess
import tempfile
import time
import wave
from collections.abc import Callable
from pathlib import Path

from .audio import SR
from .script import Section

VOICE = "zh-CN-YunxiNeural"
RATE = "+0%"
RETRIES = 3

Synth = Callable[[str, Path], None]  # (文本, 输出 WAV 路径) -> None


def cache_key(text: str, voice: str, rate: str) -> str:
    return hashlib.sha256(f"{voice}\n{rate}\n{text}".encode("utf-8")).hexdigest()[:16]


def _to_wav(src: Path, dst: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", str(SR),
         "-sample_fmt", "s16", str(dst)],
        check=True,
    )


def edge_synth(voice: str = VOICE, rate: str = RATE) -> Synth:
    import edge_tts

    def run(text: str, out: Path) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / "a.mp3"
            asyncio.run(edge_tts.Communicate(text, voice, rate=rate).save(str(mp3)))
            _to_wav(mp3, out)

    return run


def offline_synth() -> Synth:
    """Windows 自带的 System.Speech；文本经环境变量传入，避免命令拼接。"""
    ps = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.SetOutputToWaveFile($env:HP_OUT); $s.Speak($env:HP_TEXT); $s.Dispose()"
    )

    def run(text: str, out: Path) -> None:
        import os
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.wav"
            env = {**os.environ, "HP_TEXT": text, "HP_OUT": str(raw)}
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, env=env)
            _to_wav(raw, out)

    return run


def _with_retry(synth: Synth, text: str, out: Path) -> None:
    for attempt in range(1, RETRIES + 1):
        try:
            synth(text, out)
            return
        except Exception as exc:  # 网络错误等，重试后仍失败才抛出
            if attempt == RETRIES:
                raise RuntimeError(f"配音失败（已重试 {RETRIES} 次）：{text}") from exc
            time.sleep(2 * attempt)


def synthesize(
    sections: list[Section],
    cache_dir: str | Path,
    voice: str = VOICE,
    rate: str = RATE,
    offline: bool = False,
    synth: Synth | None = None,
) -> dict[tuple[str, int], Path]:
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    if offline:
        voice = "offline"
    synth = synth or (offline_synth() if offline else edge_synth(voice, rate))
    paths = {}
    for sec in sections:
        for i, line in enumerate(sec.lines):
            path = cache / f"{cache_key(line.zh, voice, rate)}.wav"
            if not path.exists():
                tmp = path.with_suffix(".part.wav")
                _with_retry(synth, line.zh, tmp)
                tmp.replace(path)  # 写完再改名，中断时不留下半个文件
            paths[(sec.id, i)] = path
    return paths


def clip_duration(path: str | Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()
