"""解析旁白稿（scripts/human-progress.md）。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_HEADER = re.compile(r"^##\s+(S\d+)\s+(.+?)\s*\|\s*(.+?)\s*$")
_META = re.compile(r"^-\s*(\w+)\s*:\s*(.*?)\s*$")


@dataclass(frozen=True)
class Line:
    zh: str
    en: str


@dataclass(frozen=True)
class Section:
    id: str
    title_zh: str
    title_en: str
    era_zh: str
    era_en: str
    year: float | None
    target: float
    speculative: bool
    lines: tuple[Line, ...]


def _split_pair(text: str, lineno: int) -> tuple[str, str]:
    if " | " not in text:
        raise ValueError(f"第 {lineno} 行缺少“中文 | English”分隔符：{text}")
    zh, en = text.split(" | ", 1)
    return zh.strip(), en.strip()


def _build(header: tuple[str, str, str], meta: dict[str, str], lines: list[Line]) -> Section:
    sid, title_zh, title_en = header
    if not lines:
        raise ValueError(f"{sid} 没有旁白句子")
    era_zh, era_en = _split_pair(meta["era"], 0) if "era" in meta else ("", "")
    return Section(
        id=sid,
        title_zh=title_zh,
        title_en=title_en,
        era_zh=era_zh,
        era_en=era_en,
        year=float(meta["year"]) if "year" in meta else None,
        target=float(meta.get("target", 10)),
        speculative=meta.get("speculative", "false").lower() == "true",
        lines=tuple(lines),
    )


def parse_script(text: str) -> list[Section]:
    sections: list[Section] = []
    header: tuple[str, str, str] | None = None
    meta: dict[str, str] = {}
    lines: list[Line] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        row = raw.strip()
        if m := _HEADER.match(row):
            if header:
                sections.append(_build(header, meta, lines))
            header, meta, lines = (m[1], m[2], m[3]), {}, []
        elif header is None or not row:
            continue  # 文件开头的说明文字与空行
        elif m := _META.match(row):
            meta[m[1]] = m[2]
        else:
            lines.append(Line(*_split_pair(row, lineno)))
    if header:
        sections.append(_build(header, meta, lines))
    return sections


def load_script(path: str | Path) -> list[Section]:
    return parse_script(Path(path).read_text(encoding="utf-8"))
