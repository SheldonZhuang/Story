"""多进程逐帧渲染，通过管道交给 FFmpeg 编码。"""
from __future__ import annotations

import json
import os
import subprocess
from collections import deque
from multiprocessing import Pool
from pathlib import Path

from PIL import Image

from .frame import render_frame
from .layout import LAYOUTS, Layout
from .timeline import Timeline, load_timeline

FPS = 30
MAX_INFLIGHT_PER_WORKER = 3
WORKER_MB = 600  # 实测单个渲染进程峰值约 440MB，留余量
RESERVE_MB = 2000  # 留给 FFmpeg 编码和系统


def available_commit_mb() -> float | None:
    """Windows 上剩余可提交内存（物理内存 + 页面文件）；其他系统返回 None。"""
    if os.name != "nt":
        return None
    import ctypes

    class MemStatus(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [
            (n, ctypes.c_ulonglong) for n in (
                "ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile",
                "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")
        ]

    st = MemStatus()
    st.dwLength = ctypes.sizeof(st)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        return None
    return st.ullAvailPageFile / 2**20


def default_workers(cpu: int | None = None, avail_mb: float | None = None) -> int:
    """渲染进程数：不超过 CPU 核数，也不超过剩余内存能容纳的数量。"""
    cpu = cpu or os.cpu_count() or 1
    if avail_mb is None:
        return cpu
    return max(1, min(cpu, int((avail_mb - RESERVE_MB) // WORKER_MB)))
_worker: tuple[Timeline, Layout] | None = None


def _init(timeline_path: str, layout_name: str) -> None:
    global _worker
    _worker = (load_timeline(timeline_path), LAYOUTS[layout_name])


def _frame(i: int) -> bytes:
    tl, layout = _worker
    return render_frame(tl, layout, i / FPS).tobytes()


def render_video(timeline_path: str | Path, layout: Layout, audio_path: str | Path,
                 out_path: str | Path, workers: int | None = None) -> None:
    tl = load_timeline(timeline_path)
    n = round(tl.duration * FPS)
    workers = workers or default_workers(avail_mb=available_commit_mb())
    print(f"  {layout.name}: {workers} 个渲染进程", flush=True)
    out_path = Path(out_path)
    part = out_path.with_name(out_path.stem + ".part.mp4")  # 成功后再改名，失败不覆盖旧成片
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{layout.w}x{layout.h}", "-r", str(FPS), "-i", "-",
        "-i", str(audio_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest",
        str(part),
    ]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ok = False
    try:
        with Pool(workers, _init, (str(timeline_path), layout.name)) as pool:
            # 限制在途帧数：Pool.imap 没有背压，编码慢于渲染时帧会无限堆积在内存里
            window: deque = deque()
            for i in range(n):
                window.append(pool.apply_async(_frame, (i,)))
                if len(window) >= workers * MAX_INFLIGHT_PER_WORKER:
                    _write(ff, window.popleft().get(), i - len(window), layout, tl)
            while window:
                _write(ff, window.popleft().get(), n - len(window) - 1, layout, tl)
        ok = True
    finally:
        ff.stdin.close()
        code = ff.wait()
    if code != 0:
        raise RuntimeError(f"FFmpeg 编码失败：{out_path}")
    if ok:
        part.replace(out_path)


def _write(ff: subprocess.Popen, data: bytes, k: int, layout: Layout, tl: Timeline) -> None:
    ff.stdin.write(data)
    if k % (FPS * 10) == 0:
        print(f"  {layout.name}: {k / FPS:5.0f}s / {tl.duration:.0f}s", flush=True)


def remux_audio(video_path: str | Path, audio_path: str | Path) -> None:
    """保留画面（不重新编码），只替换音轨；同样先写临时文件再改名。"""
    video_path = Path(video_path)
    part = video_path.with_name(video_path.stem + ".part.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video_path), "-i", str(audio_path),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", "-shortest", str(part)],
        check=True,
    )
    part.replace(video_path)


def export_keyframes(tl: Timeline, layout: Layout, out_dir: str | Path) -> list[Path]:
    """每段的开头、中间、结尾各一帧。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for span in tl.spans:
        for tag, f in (("start", 0.15), ("mid", 0.55), ("end", 0.9)):
            path = out / f"{layout.name}-{span.section.id}-{tag}.jpg"
            Image.fromarray(render_frame(tl, layout, span.start + span.duration * f)).save(path, quality=90)
            paths.append(path)
    return paths


def probe(path: str | Path) -> dict:
    """返回 {duration, width, height}。"""
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:format=duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(res.stdout)
    st = data["streams"][0]
    return {"duration": float(data["format"]["duration"]), "width": st["width"], "height": st["height"]}
