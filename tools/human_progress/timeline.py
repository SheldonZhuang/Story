"""由逐句配音时长排出全片时间线；两个画幅共用同一份时间线。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .script import Line, Section

HEAD = 1.2  # 段首留白（秒）
GAP = 0.8  # 句间留白
TAIL = 2.2  # 段尾留白

# 压缩时间轴锚点（年份 → 轴上位置 0–1）。远古段压缩、现代段展开，效果近似对数刻度，
# 但保证 1942/1947、2022/2026 这类相邻节点不会重叠。2026 之后是推测区间。
AXIS_ANCHORS = (
    (-3_300_000, 0.00), (-1_000_000, 0.10), (-10_000, 0.24), (-3000, 0.33),
    (1769, 0.46), (1882, 0.54), (1942, 0.61), (1947, 0.65), (2022, 0.73),
    (2026, 0.77), (2056, 1.00),
)
FUTURE_FROM = 2026


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    zh: str
    en: str
    section_id: str
    index: int


@dataclass(frozen=True)
class Span:
    section: Section
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class Timeline:
    spans: tuple[Span, ...]
    cues: tuple[Cue, ...]
    duration: float

    def span_at(self, t: float) -> Span:
        for span in self.spans:
            if t < span.end:
                return span
        return self.spans[-1]


def build_timeline(sections: list[Section], durations: dict[tuple[str, int], float]) -> Timeline:
    spans, cues, t = [], [], 0.0
    for sec in sections:
        start, cursor = t, t + HEAD
        for i, line in enumerate(sec.lines):
            if i:
                cursor += GAP
            end = cursor + durations[(sec.id, i)]
            cues.append(Cue(cursor, end, line.zh, line.en, sec.id, i))
            cursor = end
        t = cursor + TAIL
        spans.append(Span(sec, start, t))
    return Timeline(tuple(spans), tuple(cues), t)


def year_to_axis(year: float) -> float:
    years, xs = zip(*AXIS_ANCHORS)
    return float(np.interp(year, years, xs))


def duration_warnings(tl: Timeline, tolerance: float = 0.5) -> list[str]:
    return [
        f"{s.section.id} 实际 {s.duration:.1f}s，目标 {s.section.target:.0f}s，偏离超过 {tolerance:.0%}"
        for s in tl.spans
        if abs(s.duration - s.section.target) > tolerance * s.section.target
    ]


def save_timeline(tl: Timeline, path: str | Path) -> None:
    Path(path).write_text(json.dumps(asdict(tl), ensure_ascii=False, indent=1), encoding="utf-8")


def load_timeline(path: str | Path) -> Timeline:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    spans = tuple(
        Span(
            Section(**{**s["section"], "lines": tuple(Line(**l) for l in s["section"]["lines"])}),
            s["start"], s["end"],
        )
        for s in data["spans"]
    )
    cues = tuple(Cue(**c) for c in data["cues"])
    return Timeline(spans, cues, data["duration"])
