"""一键构建：python -m tools.human_progress.build [--keyframes] [--offline] [--only landscape|portrait]"""
from __future__ import annotations

import argparse
from pathlib import Path

from .audio import mix, normalize_loudness, place_narration, read_wav, write_wav
from .layout import LAYOUTS
from .music import compose, duck_curve, load_track
from .narration import clip_duration, synthesize
from .render import export_keyframes, probe, remux_audio, render_video
from .script import load_script
from .subtitles import to_srt
from .timeline import build_timeline, duration_warnings, save_timeline

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "human-progress.md"
OUT = ROOT / "output"
NAME = "human-progress"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="生成人类进步历程视频")
    ap.add_argument("--keyframes", action="store_true", help="只导出关键帧，不渲染视频")
    ap.add_argument("--offline", action="store_true", help="使用 Windows 离线语音")
    ap.add_argument("--only", choices=sorted(LAYOUTS), help="只渲染一个画幅")
    ap.add_argument("--audio-only", action="store_true",
                    help="只重做音轨（配音、配乐、混音）并替换进已有成片，不重新渲染画面")
    ap.add_argument("--workers", type=int, help="渲染进程数（默认按 CPU 和剩余内存自动决定）")
    ap.add_argument("--music", type=Path, help="用外部音乐文件做背景音乐（默认使用程序作曲的原创配乐）")
    ap.add_argument("--music-db", type=float, default=-12.0,
                    help="配乐比旁白低多少 dB（默认 -12；越接近 0 音乐越响）")
    args = ap.parse_args(argv)

    OUT.mkdir(exist_ok=True)
    sections = load_script(SCRIPT)
    print(f"配音：{sum(len(s.lines) for s in sections)} 句")
    clips = synthesize(sections, OUT / "cache" / "tts", offline=args.offline)
    tl = build_timeline(sections, {k: clip_duration(p) for k, p in clips.items()})
    timeline_path = OUT / "timeline.json"
    save_timeline(tl, timeline_path)
    print(f"时间线：{len(tl.spans)} 段，{tl.duration:.1f}s")
    for w in duration_warnings(tl):
        print("警告：" + w)

    layouts = [LAYOUTS[args.only]] if args.only else list(LAYOUTS.values())
    if args.keyframes:
        for layout in layouts:
            paths = export_keyframes(tl, layout, OUT / "keyframes")
            print(f"关键帧：{layout.name} {len(paths)} 张 → {OUT / 'keyframes'}")
        return

    audio_path = OUT / f"{NAME}.wav"
    narration = place_narration(tl, {k: read_wav(p) for k, p in clips.items()})
    raw_mix = OUT / "cache" / f"{NAME}-mix.wav"
    music = load_track(args.music, tl.duration) if args.music else compose(tl)
    write_wav(raw_mix, mix(narration, music, duck_curve(tl, len(narration)), music_db=args.music_db))
    normalize_loudness(raw_mix, audio_path)
    (OUT / f"{NAME}.srt").write_text(to_srt(tl.cues), encoding="utf-8")

    sizes = {"landscape": "16x9", "portrait": "9x16"}
    for layout in layouts:
        video = OUT / f"{NAME}-{sizes[layout.name]}.mp4"
        if args.audio_only:
            if not video.exists():
                raise SystemExit(f"{video.name} 不存在，请先完整构建")
            print(f"替换音轨：{video.name}")
            remux_audio(video, audio_path)
        else:
            print(f"渲染：{video.name}")
            render_video(timeline_path, layout, audio_path, video, workers=args.workers)
        info = probe(video)
        print(f"完成：{video.name} {info['width']}x{info['height']} {info['duration']:.2f}s")


if __name__ == "__main__":
    main()
