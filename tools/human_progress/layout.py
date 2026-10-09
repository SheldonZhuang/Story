"""横屏 / 竖屏布局参数。主画面在以 (stage_cx, stage_cy) 为中心、半径 unit 的方形区域内绘制。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Layout:
    name: str
    w: int
    h: int
    stage_cx: int
    stage_cy: int
    unit: int
    title_x: int  # 标题锚点（align=left 时为左边缘，center 时为中心）
    title_y: int
    title_align: str
    era_size: int
    title_zh_size: int
    title_en_size: int
    axis_y: int
    axis_x0: int
    axis_x1: int
    sub_y: int  # 字幕块顶部
    sub_zh_size: int
    sub_en_size: int
    sub_max_w: int

    def to_px(self, x: float, y: float) -> tuple[float, float]:
        """舞台坐标（-1..1，y 向下）→ 像素。"""
        return self.stage_cx + x * self.unit, self.stage_cy + y * self.unit


LANDSCAPE = Layout(
    name="landscape", w=1920, h=1080,
    stage_cx=960, stage_cy=530, unit=280,
    title_x=96, title_y=72, title_align="left",
    era_size=28, title_zh_size=56, title_en_size=28,
    axis_y=1020, axis_x0=160, axis_x1=1760,
    sub_y=820, sub_zh_size=46, sub_en_size=30, sub_max_w=1500,
)

PORTRAIT = Layout(
    name="portrait", w=1080, h=1920,
    stage_cx=540, stage_cy=860, unit=420,
    title_x=540, title_y=150, title_align="center",
    era_size=34, title_zh_size=72, title_en_size=34,
    axis_y=1780, axis_x0=110, axis_x1=970,
    sub_y=1420, sub_zh_size=52, sub_en_size=34, sub_max_w=940,
)

LAYOUTS = {l.name: l for l in (LANDSCAPE, PORTRAIT)}

# 各区域的垂直范围，供测试检查是否重叠
TITLE_BLOCK_H = {"landscape": 170, "portrait": 230}
SUB_BLOCK_H = {"landscape": 170, "portrait": 260}
