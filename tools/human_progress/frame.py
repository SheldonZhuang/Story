"""合成一帧：背景 → 主画面 → 段落标题 → 时间轴 → 双语字幕。"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

from .draw import Canvas, add_glow, clamp01, ease, fade, font, rgb255, wrap_text
from .layout import Layout
from .scenes import FUTURE, SCENES, Ctx
from .timeline import FUTURE_FROM, Timeline, year_to_axis

XFADE = 0.5  # 段落切换时主画面的淡出 / 淡入时长
GOLD = (0.95, 0.75, 0.4)
TEXT = (0.96, 0.95, 0.92)
DIM = (0.7, 0.7, 0.72)


@lru_cache(maxsize=4)
def _vignette(w: int, h: int) -> np.ndarray:
    ys = np.linspace(-1, 1, h, dtype=np.float32)[:, None]
    xs = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
    return np.clip(1 - 0.55 * np.sqrt(xs * xs * (w / h) ** 0.5 + ys * ys), 0, 1)[..., None]


def background(layout: Layout, progress: float) -> np.ndarray:
    """深色背景，亮度和色温随历史推进逐渐提高（progress 为全片进度 0–1）。"""
    dark = np.array((0.012, 0.012, 0.02), np.float32)
    lit = np.array((0.05, 0.065, 0.1), np.float32)
    color = dark + (lit - dark) * ease(progress)
    return _vignette(layout.w, layout.h) * color


def _text(draw: ImageDraw.ImageDraw, xy, text: str, size: int, color, alpha: float,
          anchor: str, bold: bool = False, stroke: int = 0) -> None:
    draw.text(xy, text, font=font(size, bold), fill=rgb255(color, alpha), anchor=anchor,
              stroke_width=stroke, stroke_fill=(0, 0, 0, round(200 * alpha)))


def draw_title(draw: ImageDraw.ImageDraw, layout: Layout, sec, alpha: float) -> None:
    anchor = "la" if layout.title_align == "left" else "ma"
    x, y = layout.title_x, layout.title_y
    if sec.era_zh:
        _text(draw, (x, y), f"{sec.era_zh}  ·  {sec.era_en}", layout.era_size, GOLD, alpha, anchor)
        y += round(layout.era_size * 1.6)
    _text(draw, (x, y), sec.title_zh, layout.title_zh_size, TEXT, alpha, anchor, bold=True)
    y += round(layout.title_zh_size * 1.3)
    _text(draw, (x, y), sec.title_en, layout.title_en_size, DIM, alpha, anchor)


def draw_axis(c: Canvas, tl: Timeline, layout: Layout, t: float) -> None:
    draw, y = c.draw, layout.axis_y
    x0, x1 = layout.axis_x0, layout.axis_x1
    to_x = lambda year: x0 + (x1 - x0) * year_to_axis(year)
    xf = to_x(FUTURE_FROM)
    draw.line([(x0, y), (xf, y)], fill=rgb255(DIM, 0.55), width=2)
    for xa in range(round(xf), x1, 16):  # 推测区间：虚线
        draw.line([(xa, y), (min(xa + 8, x1), y)], fill=rgb255(FUTURE, 0.55), width=2)
    current = tl.span_at(t)
    for span in tl.spans:
        year = span.section.year
        if year is None:
            continue
        x = to_x(year)
        reached = span.start <= t
        is_now = span is current
        color = FUTURE if span.section.speculative else GOLD
        r = 7 if is_now else 5
        draw.ellipse((x - r, y - r, x + r, y + r),
                     fill=rgb255(color, 1.0 if reached else 0.0), outline=rgb255(color, 0.8 if reached else 0.35),
                     width=2)
        if is_now:
            add_glow(c.light, x, y, 18, color, 0.6 * fade(t, span.start, XFADE))
    # 端点标注
    size = max(18, layout.era_size - 8)
    _text(draw, (x0, y + 14), "-330万年", size, DIM, 0.7, "la")
    _text(draw, (x1, y + 14), "2056", size, FUTURE, 0.8, "ra")


def draw_subtitle(draw: ImageDraw.ImageDraw, layout: Layout, cue, alpha: float) -> None:
    y = layout.sub_y
    cx = layout.w / 2
    for size, text, color in ((layout.sub_zh_size, cue.zh, TEXT), (layout.sub_en_size, cue.en, DIM)):
        for line in wrap_text(text, font(size), layout.sub_max_w):
            _text(draw, (cx, y), line.rstrip(), size, color, alpha, "ma", stroke=max(2, size // 16))
            y += round(size * 1.35)
        y += round(size * 0.25)


def _cue_at(tl: Timeline, t: float):
    for cue in tl.cues:
        if cue.start - 0.15 <= t < cue.end + 0.25:
            return cue
    return None


def render_frame(tl: Timeline, layout: Layout, t: float) -> np.ndarray:
    span = tl.span_at(t)
    local = t - span.start
    c = Canvas(layout)
    cue_starts = tuple(cue.start - span.start for cue in tl.cues if cue.section_id == span.section.id)
    SCENES[span.section.id](Ctx(c, local, span.duration, cue_starts))
    # 段落切换：主画面在段首淡入、段尾淡出（第一段不淡入，最后一段在片尾淡出）
    k = min(fade(local, 0, XFADE) if span is not tl.spans[0] else 1.0,
            1 - fade(local, span.duration - XFADE, XFADE))
    if k < 1:
        c.light *= k
        alpha = np.asarray(c.ink.getchannel("A"), np.float32) * k
        c.ink.putalpha(Image.fromarray(alpha.astype(np.uint8)))
    title_alpha = fade(local, 0.2, 0.6) * (1 - fade(local, span.duration - XFADE, XFADE))
    draw_title(c.draw, layout, span.section, title_alpha)
    draw_axis(c, tl, layout, t)
    cue = _cue_at(tl, t)
    if cue:
        a = min(fade(t, cue.start - 0.15, 0.2), 1 - fade(t, cue.end + 0.05, 0.2))
        draw_subtitle(c.draw, layout, cue, a)
    return c.compose(background(layout, clamp01(t / tl.duration)))
