"""导出中英双语 SRT。"""
from __future__ import annotations

from collections.abc import Iterable

from .timeline import Cue


def format_ts(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: Iterable[Cue]) -> str:
    blocks = [
        f"{i}\n{format_ts(c.start)} --> {format_ts(c.end)}\n{c.zh}\n{c.en}\n"
        for i, c in enumerate(cues, start=1)
    ]
    return "\n".join(blocks)
