import pytest

from tools.human_progress.script import Line, Section
from tools.human_progress.timeline import (
    GAP, HEAD, TAIL, build_timeline, duration_warnings, load_timeline,
    save_timeline, year_to_axis,
)


def section(sid, n_lines, target=10.0, year=None):
    lines = tuple(Line(f"{sid}中{i}", f"{sid} en {i}") for i in range(n_lines))
    return Section(sid, sid, sid, "", "", year, target, False, lines)


SECTIONS = [section("S01", 2), section("S02", 1, year=1769)]
DURATIONS = {("S01", 0): 2.0, ("S01", 1): 3.0, ("S02", 0): 4.0}


def test_spans_and_cues_follow_padding_rules():
    tl = build_timeline(SECTIONS, DURATIONS)
    s1, s2 = tl.spans
    assert s1.start == 0
    c0, c1, c2 = tl.cues
    assert (c0.start, c0.end) == pytest.approx((HEAD, HEAD + 2))
    assert c1.start == pytest.approx(c0.end + GAP)
    assert s1.end == pytest.approx(c1.end + TAIL)
    assert s2.start == s1.end
    assert c2.start == pytest.approx(s2.start + HEAD)
    assert tl.duration == pytest.approx(s2.end)
    assert (c2.zh, c2.en) == ("S02中0", "S02 en 0")


def test_span_at_boundaries():
    tl = build_timeline(SECTIONS, DURATIONS)
    s1, s2 = tl.spans
    assert tl.span_at(-1) is s1
    assert tl.span_at(s1.end - 1e-6) is s1
    assert tl.span_at(s1.end) is s2
    assert tl.span_at(tl.duration + 5) is s2


def test_missing_duration_raises():
    with pytest.raises(KeyError):
        build_timeline(SECTIONS, {("S01", 0): 1.0})


def test_year_to_axis_endpoints_and_monotonic():
    assert year_to_axis(-3_300_000) == pytest.approx(0.0)
    assert year_to_axis(2056) == pytest.approx(1.0)
    years = [-3_300_000, -1_000_000, -10_000, -3000, 1769, 1882, 1942, 1947, 2022, 2026, 2056]
    xs = [year_to_axis(y) for y in years]
    assert xs == sorted(xs) and len(set(xs)) == len(xs)


def test_json_round_trip(tmp_path):
    tl = build_timeline(SECTIONS, DURATIONS)
    path = tmp_path / "timeline.json"
    save_timeline(tl, path)
    assert load_timeline(path) == tl


def test_duration_warnings():
    off = build_timeline([section("S01", 1, target=10)], {("S01", 0): 16 - HEAD - TAIL})
    ok = build_timeline([section("S01", 1, target=10)], {("S01", 0): 11 - HEAD - TAIL})
    assert len(duration_warnings(off)) == 1 and "S01" in duration_warnings(off)[0]
    assert duration_warnings(ok) == []
