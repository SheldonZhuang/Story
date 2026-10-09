"""绘图基础：画布（发光层 + 线条层）、缓动、文字换行、虚线。"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .layout import Layout

FONT_REGULAR = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

Color = tuple[float, float, float]  # 0–1 浮点 RGB


@lru_cache(maxsize=64)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease(x: float) -> float:
    """smoothstep：0→0，1→1，两端平滑。"""
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def fade(t: float, start: float, dur: float) -> float:
    return ease((t - start) / dur) if dur > 0 else float(t >= start)


def rgb255(c: Color, alpha: float = 1.0) -> tuple[int, int, int, int]:
    return (*(round(255 * clamp01(v)) for v in c), round(255 * clamp01(alpha)))


def add_glow(arr: np.ndarray, cx: float, cy: float, r: float, color: Color, strength: float = 1.0) -> None:
    """在 float32 画布上加一团高斯光；只计算 3r 包围盒内的像素。"""
    if r <= 0 or strength <= 0:
        return
    h, w = arr.shape[:2]
    x0, x1 = max(0, int(cx - 3 * r)), min(w, int(cx + 3 * r) + 1)
    y0, y1 = max(0, int(cy - 3 * r)), min(h, int(cy + 3 * r) + 1)
    if x0 >= x1 or y0 >= y1:
        return
    ys = np.arange(y0, y1, dtype=np.float32)[:, None] - cy
    xs = np.arange(x0, x1, dtype=np.float32)[None, :] - cx
    g = np.exp(-(xs * xs + ys * ys) / (2 * r * r)) * strength
    arr[y0:y1, x0:x1] += g[..., None] * np.asarray(color, np.float32)


def _is_cjk(ch: str) -> bool:
    return ord(ch) > 0x2E80


def _tokens(text: str) -> list[str]:
    """中文按字切分，英文按词（保留词后空格），保证拼回去等于原文。"""
    out, word = [], ""
    for ch in text:
        if _is_cjk(ch):
            if word:
                out.append(word)
                word = ""
            out.append(ch)
        else:
            word += ch
            if ch == " ":
                out.append(word)
                word = ""
    if word:
        out.append(word)
    return out


def wrap_text(text: str, fnt: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines, cur = [], ""
    for tok in _tokens(text):
        if cur and fnt.getlength((cur + tok).rstrip()) > max_w:
            lines.append(cur)
            cur = tok
        else:
            cur += tok
    if cur:
        lines.append(cur)
    return lines


class Canvas:
    """一帧画布：light 为加法发光层（float32），ink 为 RGBA 线条/文字层。"""

    def __init__(self, layout: Layout):
        self.layout = layout
        self.light = np.zeros((layout.h, layout.w, 3), np.float32)
        self.ink = Image.new("RGBA", (layout.w, layout.h), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.ink)

    # 舞台坐标的便捷方法（x, y ∈ -1..1；尺寸以 unit 为单位）
    def px(self, x: float, y: float) -> tuple[float, float]:
        return self.layout.to_px(x, y)

    def glow(self, x: float, y: float, r: float, color: Color, strength: float = 1.0) -> None:
        cx, cy = self.px(x, y)
        add_glow(self.light, cx, cy, r * self.layout.unit, color, strength)

    def line(self, pts, color: Color, width: float = 0.01, alpha: float = 1.0) -> None:
        w = max(1, round(width * self.layout.unit))
        self.draw.line([self.px(*p) for p in pts], fill=rgb255(color, alpha), width=w, joint="curve")

    def polygon(self, pts, fill: Color | None = None, outline: Color | None = None,
                alpha: float = 1.0, width: float = 0.008) -> None:
        self.draw.polygon(
            [self.px(*p) for p in pts],
            fill=rgb255(fill, alpha) if fill else None,
            outline=rgb255(outline, alpha) if outline else None,
            width=max(1, round(width * self.layout.unit)),
        )

    def circle(self, x: float, y: float, r: float, fill: Color | None = None,
               outline: Color | None = None, alpha: float = 1.0, width: float = 0.008) -> None:
        cx, cy = self.px(x, y)
        rr = r * self.layout.unit
        self.draw.ellipse(
            (cx - rr, cy - rr, cx + rr, cy + rr),
            fill=rgb255(fill, alpha) if fill else None,
            outline=rgb255(outline, alpha) if outline else None,
            width=max(1, round(width * self.layout.unit)),
        )

    def dashed_circle(self, x: float, y: float, r: float, color: Color, alpha: float = 1.0,
                      width: float = 0.008, dashes: int = 36, phase: float = 0.0) -> None:
        for i in range(dashes):
            a0 = 2 * math.pi * (i + phase) / dashes
            a1 = a0 + math.pi / dashes
            self.line([(x + r * math.cos(a), y + r * math.sin(a)) for a in np.linspace(a0, a1, 5)],
                      color, width, alpha)

    def compose(self, background: np.ndarray) -> np.ndarray:
        """背景 + 发光层（加法）+ 线条层（alpha 混合）→ uint8 RGB。"""
        base = background + self.light
        ink = np.asarray(self.ink, np.float32) / 255.0
        a = ink[..., 3:4]
        out = base * (1 - a) + ink[..., :3] * a
        return (np.clip(out, 0, 1) * 255).astype(np.uint8)
