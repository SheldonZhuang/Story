"""S01–S12 主画面。舞台坐标 x, y ∈ -1..1（y 向下），p = 段内进度 0–1，t = 段内秒数。"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from .draw import Canvas, clamp01, ease, fade

ORANGE = (1.0, 0.55, 0.15)
EMBER = (1.0, 0.35, 0.08)
STONE = (0.62, 0.6, 0.56)
WHEAT = (0.95, 0.78, 0.35)
BRONZE = (0.85, 0.55, 0.3)
COPPER = (0.9, 0.5, 0.3)
SMOKE = (0.75, 0.75, 0.78)
WARM = (1.0, 0.92, 0.7)
ELECTRIC = (0.4, 0.7, 1.0)
CYAN = (0.5, 0.95, 1.0)
GREEN = (0.35, 1.0, 0.6)
VIOLET = (0.7, 0.45, 1.0)
FUTURE = (0.45, 0.8, 1.0)
SUN = (1.0, 0.9, 0.6)


@dataclass
class Ctx:
    c: Canvas
    t: float  # 段内秒数
    dur: float  # 段长
    cues: tuple[float, ...]  # 各句相对段首的开始时间

    @property
    def p(self) -> float:
        return clamp01(self.t / self.dur) if self.dur else 1.0

    def at(self, i: int, ramp: float = 0.8) -> float:
        """第 i 句开始后的淡入程度 0–1（与旁白同步出场）。"""
        i = min(i, len(self.cues) - 1)
        return fade(self.t, self.cues[i], ramp)


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def flame(c: Canvas, x: float, y: float, size: float, t: float, strength: float = 1.0) -> None:
    """多层光团叠出跳动的火焰。"""
    for k, (col, r, dy) in enumerate(((EMBER, 0.32, 0.0), (ORANGE, 0.2, -0.08), (WARM, 0.09, -0.12))):
        jitter = 0.04 * math.sin(t * (7 + 3 * k) + k)
        c.glow(x + jitter * size, y + dy * size, r * size, col, strength * (0.85 + 0.15 * math.sin(t * 11 + k)))


def embers(c: Canvas, cx: float, cy: float, t: float, n: int, spread: float, seed: int, alpha: float) -> None:
    rng = _rng(seed)
    for _ in range(n):
        speed, phase, dx = rng.uniform(0.08, 0.2), rng.uniform(0, 1), rng.uniform(-spread, spread)
        life = (t * speed + phase) % 1.0
        c.glow(cx + dx + 0.05 * math.sin(t + phase * 9), cy - life * 0.9,
               0.012, EMBER, alpha * (1 - life) * 1.5)


def s01(ctx: Ctx) -> None:
    c, t = ctx.c, ctx.t
    k = ease(t / 3.0)
    flame(c, 0, 0.1, 0.35 + 0.65 * k, t, k)
    embers(c, 0, 0.05, t, 10, 0.12, 1, k)


def _rock(cx: float, cy: float, r: float, seed: int, n: int = 9):
    rng = _rng(seed)
    return [(cx + r * rng.uniform(0.75, 1.1) * math.cos(a), cy + r * 0.7 * rng.uniform(0.75, 1.1) * math.sin(a))
            for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]


def s02(ctx: Ctx) -> None:
    c, t = ctx.c, ctx.t
    hit = 2.2  # 撞击时刻（秒）
    fall = ease(min(t, hit) / hit)
    top_y = -0.75 + fall * 0.5
    c.polygon(_rock(0, 0.35, 0.42, 2), fill=(0.16, 0.15, 0.14), outline=STONE)
    c.polygon(_rock(0.05, top_y, 0.22, 3, 7), fill=(0.2, 0.19, 0.17), outline=STONE)
    if t > hit:
        dt = t - hit
        rng = _rng(4)
        for _ in range(18):
            a, v = rng.uniform(-math.pi, 0), rng.uniform(0.4, 1.0)
            x, y = 0.05 + math.cos(a) * v * dt, -0.08 + math.sin(a) * v * dt + 0.5 * dt * dt
            c.glow(x, y, 0.015, ORANGE, max(0, 1.6 - dt * 1.4))
    # 后半段：打制手斧轮廓
    axe = ctx.at(2)
    if axe:
        pts = [(0.62, -0.45), (0.78, -0.1), (0.74, 0.3), (0.62, 0.42), (0.5, 0.3), (0.46, -0.1)]
        c.polygon(pts, fill=(0.22, 0.2, 0.17), outline=WARM, alpha=axe)
        for a, b in (((0.62, -0.3), (0.55, 0.0)), ((0.7, -0.15), (0.6, 0.2)), ((0.6, 0.05), (0.66, 0.32))):
            c.line([a, b], STONE, 0.006, axe * 0.8)


def s03(ctx: Ctx) -> None:
    c, t = ctx.c, ctx.t
    reach = 0.3 + 0.7 * ease(ctx.p)
    c.glow(0, 0.2, 1.1 * reach, EMBER, 0.18)  # 被照亮的范围逐渐扩大
    for a, b in (((-0.4, 0.42), (0.35, 0.3)), ((0.4, 0.42), (-0.35, 0.3)), ((-0.1, 0.45), (0.15, 0.28))):
        c.line([a, b], (0.45, 0.28, 0.15), 0.05)
    flame(c, 0, 0.12, 1.1, t, 1.1)
    embers(c, 0, 0.05, t, 18, 0.25, 5, 1.0)
    # 围坐的人影
    for x in (-0.75, 0.75):
        side = 1 if x < 0 else -1
        c.circle(x, 0.02, 0.07, fill=(0.05, 0.04, 0.04), outline=(0.5, 0.3, 0.15), alpha=ctx.at(1))
        c.polygon([(x - 0.12, 0.45), (x + 0.12 * side * 0.2, 0.1), (x + 0.12, 0.45)],
                  fill=(0.05, 0.04, 0.04), outline=(0.5, 0.3, 0.15), alpha=ctx.at(1))


def s04(ctx: Ctx) -> None:
    c, t = ctx.c, ctx.t
    c.line([(-1, 0.5), (1, 0.5)], WHEAT, 0.006, 0.6)
    grow = ease(ctx.p * 1.6)
    for i, x in enumerate(np.linspace(-0.9, 0.9, 13)):
        h = 0.32 * clamp01(grow * 1.4 - i * 0.04) * (1 + 0.1 * math.sin(i * 2.3))
        if h <= 0:
            continue
        sway = 0.02 * math.sin(t * 1.5 + i)
        c.line([(x, 0.5), (x + sway, 0.5 - h)], WHEAT, 0.007, 0.9)
        for j in range(4):  # 麦粒
            yy = 0.5 - h + j * 0.035
            c.line([(x + sway, yy), (x + sway - 0.03, yy - 0.03)], WHEAT, 0.006, 0.9)
            c.line([(x + sway, yy), (x + sway + 0.03, yy - 0.03)], WHEAT, 0.006, 0.9)
    # 房屋 → 城市天际线
    rng = _rng(6)
    city = ease((ctx.p - 0.3) / 0.6)
    for i, x in enumerate(np.linspace(-0.85, 0.85, 9)):
        a = clamp01(city * 9 - i)
        if a <= 0:
            continue
        w, h = 0.08 + rng.uniform(0, 0.05), 0.15 + rng.uniform(0, 0.35) * city
        base = 0.12
        c.polygon([(x - w, base), (x - w, base - h), (x, base - h - 0.07), (x + w, base - h), (x + w, base)],
                  fill=(0.12, 0.1, 0.07), outline=WHEAT, alpha=a)
        c.glow(x, base - h * 0.5, 0.025, WARM, a * 0.8)


def s05(ctx: Ctx) -> None:
    c, t = ctx.c, ctx.t
    c.line([(-1, 0.52), (1, 0.52)], BRONZE, 0.006, 0.5)
    x = -0.8 + 1.6 * ease(ctx.p)
    r = 0.42
    angle = (x + 0.8) / r  # 无滑动滚动
    cy = 0.52 - r
    c.circle(x, cy, r, outline=BRONZE, width=0.03)
    c.circle(x, cy, r * 0.12, fill=BRONZE)
    for k in range(8):
        a = angle + k * math.pi / 4
        c.line([(x, cy), (x + r * math.cos(a), cy + r * math.sin(a))], BRONZE, 0.015)
    # 金属高光在轮缘上移动
    ha = angle * 0.5 - math.pi / 3
    c.glow(x + r * math.cos(ha), cy + r * math.sin(ha), 0.05, WARM, 0.9)
    c.glow(x, cy, 0.5, BRONZE, 0.08)


def s06(ctx: Ctx) -> None:
    c, t = ctx.c, ctx.t
    a = ctx.at(0, 1.0)
    speed = 1.0 + 3.0 * ctx.at(2, 2.0)  # “一台机器顶上百人”时加速
    ang = t * speed * 2.2
    fx, fy, fr = 0.35, 0.1, 0.36
    c.circle(fx, fy, fr, outline=COPPER, width=0.035, alpha=a)
    for k in range(6):
        aa = ang + k * math.pi / 3
        c.line([(fx, fy), (fx + fr * math.cos(aa), fy + fr * math.sin(aa))], COPPER, 0.012, a)
    # 气缸与活塞：曲柄连杆
    crank = (fx + 0.12 * math.cos(ang), fy + 0.12 * math.sin(ang))
    piston_x = -0.45 + 0.12 * math.cos(ang)
    c.polygon([(-0.85, 0.0), (-0.3, 0.0), (-0.3, 0.2), (-0.85, 0.2)], outline=COPPER, alpha=a, width=0.012)
    c.polygon([(piston_x - 0.08, 0.02), (piston_x + 0.08, 0.02), (piston_x + 0.08, 0.18), (piston_x - 0.08, 0.18)],
              fill=COPPER, alpha=a)
    c.line([(piston_x + 0.08, 0.1), crank], WARM, 0.014, a)
    c.glow(-0.6, 0.1, 0.12, ORANGE, 0.4 * a)  # 炉火
    # 烟囱与烟
    c.polygon([(-0.75, 0.0), (-0.75, -0.55), (-0.62, -0.55), (-0.62, 0.0)], fill=(0.15, 0.1, 0.08),
              outline=COPPER, alpha=a, width=0.01)
    rng = _rng(7)
    for _ in range(14):
        ph, dx = rng.uniform(0, 1), rng.uniform(-0.05, 0.05)
        life = (t * 0.25 * speed ** 0.5 + ph) % 1.0
        c.glow(-0.685 + dx + life * 0.35, -0.6 - life * 0.45, 0.04 + 0.1 * life, SMOKE, a * 0.35 * (1 - life))


def s07(ctx: Ctx) -> None:
    c, t = ctx.c, ctx.t
    poles = [-0.85, -0.3, 0.25, 0.8]
    a = ctx.at(0, 1.0)
    for x in poles:
        c.line([(x, 0.55), (x, -0.35)], (0.5, 0.45, 0.4), 0.018, a)
        c.line([(x - 0.08, -0.3), (x + 0.08, -0.3)], (0.5, 0.45, 0.4), 0.014, a)
    # 下垂的电线
    wire = []
    for i in range(len(poles) - 1):
        for s in np.linspace(0, 1, 16):
            wire.append((poles[i] + (poles[i + 1] - poles[i]) * s, -0.3 + 0.08 * math.sin(math.pi * s)))
    c.line(wire, (0.55, 0.55, 0.6), 0.006, a)
    # 电脉冲沿电线传播（第三句“交流电送往远方”后更快更亮）
    boost = ctx.at(2)
    for k in range(3):
        s = ((t * (0.35 + 0.35 * boost)) + k / 3) % 1.0
        x, y = wire[min(len(wire) - 1, int(s * len(wire)))]
        c.glow(x, y, 0.03, ELECTRIC, a * (1.2 + boost))
    # 灯泡依次点亮
    lit = ease((ctx.p - 0.15) / 0.5)
    for i, x in enumerate(poles):
        on = clamp01(lit * len(poles) - i)
        c.circle(x, -0.15, 0.06, outline=WARM, alpha=a, width=0.008)
        c.glow(x, -0.15, 0.06 + 0.25 * on, WARM, on * (0.9 + 0.05 * math.sin(t * 30 + i)))


def s08(ctx: Ctx) -> None:
    c, t = ctx.c, ctx.t
    a = ctx.at(0, 1.0)
    c.glow(0, 0, 0.12, CYAN, 1.2 * a)
    for k in range(3):
        tilt = k * math.pi / 3
        pts = [(0.75 * math.cos(s) * math.cos(tilt) - 0.28 * math.sin(s) * math.sin(tilt),
                0.75 * math.cos(s) * math.sin(tilt) + 0.28 * math.sin(s) * math.cos(tilt))
               for s in np.linspace(0, 2 * math.pi, 64)]
        c.line(pts, CYAN, 0.005, 0.5 * a)
        s = t * (1.6 + 0.4 * k) + k
        ex = 0.75 * math.cos(s) * math.cos(tilt) - 0.28 * math.sin(s) * math.sin(tilt)
        ey = 0.75 * math.cos(s) * math.sin(tilt) + 0.28 * math.sin(s) * math.cos(tilt)
        c.glow(ex, ey, 0.035, CYAN, 1.3 * a)
    # “释放原子内部的能量”：中心闪光与扩散光环
    if ctx.at(1):
        dt = ctx.t - ctx.cues[min(1, len(ctx.cues) - 1)]
        c.glow(0, 0, 0.15 + 0.6 * ease(dt / 1.5), (1, 1, 0.95), max(0, 1.5 - dt * 0.6))
        c.circle(0, 0, min(0.98, 0.1 + dt * 0.5), outline=CYAN, alpha=max(0, 1 - dt * 0.35), width=0.01)


def s09(ctx: Ctx) -> None:
    c, t = ctx.c, ctx.t
    split = ctx.cues[min(3, len(ctx.cues) - 1)]  # 第四句“互联网”起切换到网络
    net = fade(t, split - 0.3, 1.2)
    chip = 1 - net
    if chip > 0:
        n = 4 + int(20 * ease(t / max(split, 1e-6)))  # 网格越来越密
        c.polygon([(-0.7, -0.7), (0.7, -0.7), (0.7, 0.7), (-0.7, 0.7)], fill=(0.03, 0.08, 0.05),
                  outline=GREEN, alpha=chip, width=0.012)
        for k in range(8):  # 引脚
            o = -0.6 + k * 1.2 / 7
            for p0, p1 in (((o, -0.7), (o, -0.82)), ((o, 0.7), (o, 0.82)), ((-0.7, o), (-0.82, o)), ((0.7, o), (0.82, o))):
                c.line([p0, p1], GREEN, 0.012, chip * 0.8)
        rng = _rng(9)
        cell = 1.2 / n
        for i in range(n):
            for j in range(n):
                if rng.random() < 0.45:
                    x, y = -0.6 + (i + 0.5) * cell, -0.6 + (j + 0.5) * cell
                    on = 0.5 + 0.5 * math.sin(t * 3 + i * 1.7 + j * 2.9)
                    c.glow(x, y, cell * 0.25, GREEN, chip * on * 0.7)
    if net > 0:
        rng = _rng(10)
        nodes = [(rng.uniform(-0.9, 0.9), rng.uniform(-0.8, 0.8)) for _ in range(22)]
        edges = [(i, j) for i in range(len(nodes)) for j in range(i + 1, len(nodes))
                 if math.dist(nodes[i], nodes[j]) < 0.5]
        for i, j in edges:
            c.line([nodes[i], nodes[j]], CYAN, 0.004, net * 0.45)
        for k, (i, j) in enumerate(edges):
            s = (t * 0.6 + k * 0.137) % 1.0
            (x0, y0), (x1, y1) = nodes[i], nodes[j]
            c.glow(x0 + (x1 - x0) * s, y0 + (y1 - y0) * s, 0.012, CYAN, net * 0.9)
        for x, y in nodes:
            c.glow(x, y, 0.03, GREEN, net)


def s10(ctx: Ctx) -> None:
    c, t = ctx.c, ctx.t
    a = ctx.at(0, 1.0)
    layers = [np.linspace(-0.6, 0.6, n) for n in (4, 6, 6, 3)]
    xs = np.linspace(-0.75, 0.75, len(layers))
    for li in range(len(layers) - 1):
        for y0 in layers[li]:
            for y1 in layers[li + 1]:
                c.line([(xs[li], y0), (xs[li + 1], y1)], VIOLET, 0.003, 0.35 * a)
    wave_x = -0.9 + ((t * 0.45) % 1.0) * 1.8  # 信号从左向右流过
    for li, ys in enumerate(layers):
        near = math.exp(-((xs[li] - wave_x) / 0.18) ** 2)
        for k, y in enumerate(ys):
            c.circle(xs[li], y, 0.045, fill=(0.08, 0.04, 0.14), outline=VIOLET, alpha=a, width=0.006)
            c.glow(xs[li], y, 0.06, CYAN if near > 0.5 else VIOLET, a * (0.3 + 1.2 * near))


def s11(ctx: Ctx) -> None:
    """推测段：虚线、半透明、整体呼吸。三个意象按旁白顺序出现。"""
    c, t = ctx.c, ctx.t
    breathe = 0.75 + 0.25 * math.sin(t * 1.3)
    fusion, ai, space = ctx.at(2, 1.2), ctx.at(4, 1.2), ctx.at(6, 1.2)
    # 核聚变：托卡马克环 + 中心等离子
    fx, fy = (-0.5, -0.35)
    if fusion:
        c.dashed_circle(fx, fy, 0.32, FUTURE, 0.7 * fusion, 0.008, 32, t * 0.6)
        c.dashed_circle(fx, fy, 0.2, FUTURE, 0.5 * fusion, 0.006, 24, -t * 0.9)
        c.glow(fx, fy, 0.16, (1.0, 0.85, 0.6), fusion * breathe * 0.9)
    # AI：环形节点
    ax, ay = (0.5, -0.3)
    if ai:
        pts = [(ax + 0.26 * math.cos(k * math.pi / 3 + t * 0.3), ay + 0.26 * math.sin(k * math.pi / 3 + t * 0.3))
               for k in range(6)]
        for i in range(6):
            c.line([pts[i], pts[(i + 2) % 6]], VIOLET, 0.004, 0.5 * ai)
            c.glow(*pts[i], 0.04, FUTURE, ai * breathe)
        c.glow(ax, ay, 0.07, VIOLET, ai * breathe)
    # 太空：月球 + 火箭轨道
    if space:
        mx, my = (0.0, 0.45)
        c.dashed_circle(mx, my, 0.17, FUTURE, 0.8 * space, 0.008, 28)
        c.glow(mx, my, 0.15, (0.8, 0.85, 0.95), 0.35 * space)
        orbit = [(mx + 0.4 * math.cos(s), my + 0.16 * math.sin(s)) for s in np.linspace(0, 2 * math.pi, 48)]
        for i in range(0, len(orbit) - 1, 2):
            c.line([orbit[i], orbit[i + 1]], FUTURE, 0.004, 0.6 * space)
        s = t * 0.9
        c.glow(mx + 0.4 * math.cos(s), my + 0.16 * math.sin(s), 0.03, WARM, space * 1.3)
    # 开头两句：未知的星空
    rng = _rng(11)
    for _ in range(40):
        x, y, ph = rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0, 6.3)
        c.glow(x, y, 0.006, FUTURE, 0.5 * (0.5 + 0.5 * math.sin(t * 2 + ph)))


def s12(ctx: Ctx) -> None:
    c, t = ctx.c, ctx.t
    fly = ease(t / 3.0)
    sx = -0.85 + 0.85 * fly
    if fly < 1:
        flame(c, sx, 0.0, 0.35, t, 1 - fly * 0.5)
    sun = ease((t - 2.4) / 3.5)
    if sun:
        r = 0.18 + 0.35 * sun
        c.glow(0, 0, r * 1.6, ORANGE, 0.35 * sun)
        c.glow(0, 0, r, SUN, 1.1 * sun)
        c.glow(0, 0, r * 0.4, (1, 1, 1), sun)
        for k in range(12):
            a = k * math.pi / 6 + t * 0.15
            c.line([(r * 1.15 * math.cos(a), r * 1.15 * math.sin(a)), (r * 1.6 * math.cos(a), r * 1.6 * math.sin(a))],
                   SUN, 0.006, 0.6 * sun)


SCENES: dict[str, Callable[[Ctx], None]] = {
    "S01": s01, "S02": s02, "S03": s03, "S04": s04, "S05": s05, "S06": s06,
    "S07": s07, "S08": s08, "S09": s09, "S10": s10, "S11": s11, "S12": s12,
}
