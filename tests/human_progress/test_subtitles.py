from tools.human_progress.subtitles import format_ts, to_srt
from tools.human_progress.timeline import Cue


def test_format_ts():
    assert format_ts(3661.5) == "01:01:01,500"
    assert format_ts(0) == "00:00:00,000"
    assert format_ts(59.9996) == "00:01:00,000"


def test_to_srt():
    cues = [Cue(0.9, 2.9, "甲。", "A.", "S01", 0), Cue(3.35, 6.0, "乙。", "B.", "S01", 1)]
    assert to_srt(cues) == (
        "1\n00:00:00,900 --> 00:00:02,900\n甲。\nA.\n\n"
        "2\n00:00:03,350 --> 00:00:06,000\n乙。\nB.\n"
    )
