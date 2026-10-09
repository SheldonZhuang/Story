import numpy as np

from tools.human_progress import narration
from tools.human_progress.audio import SR, write_wav
from tools.human_progress.narration import cache_key, clip_duration, synthesize
from tools.human_progress.script import Line, Section

SECTIONS = [Section("S01", "", "", "", "", None, 5, False, (Line("甲", "a"), Line("乙", "b")))]


def fake_synth(calls):
    def run(text, out):
        calls.append(text)
        write_wav(out, np.zeros(SR // 2, np.float32))
    return run


def test_cache_key_stable_and_sensitive():
    k = cache_key("你好", "v", "+0%")
    assert k == cache_key("你好", "v", "+0%")
    assert len({k, cache_key("你好!", "v", "+0%"), cache_key("你好", "w", "+0%"),
                cache_key("你好", "v", "+5%")}) == 4


def test_synthesize_uses_cache(tmp_path):
    calls = []
    first = synthesize(SECTIONS, tmp_path, synth=fake_synth(calls))
    assert calls == ["甲", "乙"]
    second = synthesize(SECTIONS, tmp_path, synth=fake_synth(calls))
    assert calls == ["甲", "乙"] and first == second
    assert clip_duration(first[("S01", 0)]) == 0.5


def test_retries_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(narration.time, "sleep", lambda s: None)
    attempts = []

    def flaky(text, out):
        attempts.append(text)
        if len(attempts) < 3:
            raise OSError("network")
        write_wav(out, np.zeros(10, np.float32))

    synthesize(SECTIONS[:1], tmp_path, synth=flaky)
    assert attempts[:3] == ["甲", "甲", "甲"]
