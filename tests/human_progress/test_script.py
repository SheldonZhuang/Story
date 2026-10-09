from pathlib import Path

import pytest

from tools.human_progress.script import Line, load_script, parse_script

SAMPLE = """# 标题

说明文字会被忽略。

## S01 序章 | Prologue
- target: 10

第一句。 | First line.

## S02 石器 | Stone Tools
- era: 约 330 万年前 | ~3.3 million years ago
- year: -3300000
- target: 12
- speculative: true

甲。 | A.
乙。 | B.
"""

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "human-progress.md"


def test_parse_fields_and_lines():
    s1, s2 = parse_script(SAMPLE)
    assert (s1.id, s1.title_zh, s1.title_en) == ("S01", "序章", "Prologue")
    assert s1.year is None and s1.era_zh == "" and s1.target == 10.0
    assert s1.speculative is False
    assert s1.lines == (Line("第一句。", "First line."),)
    assert (s2.era_zh, s2.era_en) == ("约 330 万年前", "~3.3 million years ago")
    assert s2.year == -3300000.0 and s2.target == 12.0 and s2.speculative is True
    assert [line.en for line in s2.lines] == ["A.", "B."]


def test_line_without_separator_reports_line_number():
    with pytest.raises(ValueError, match="第 4 行"):
        parse_script("## S01 序章 | Prologue\n- target: 5\n\n没有分隔符\n")


def test_section_without_lines_is_rejected():
    with pytest.raises(ValueError, match="S01"):
        parse_script("## S01 序章 | Prologue\n- target: 5\n")


def test_real_script_has_12_sections_totalling_180s():
    sections = load_script(SCRIPT_PATH)
    assert [s.id for s in sections] == [f"S{i:02d}" for i in range(1, 13)]
    assert sum(s.target for s in sections) == 180
    assert [s.id for s in sections if s.speculative] == ["S11"]
