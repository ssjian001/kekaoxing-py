"""生成 CheckBox / RadioButton 的 indicator 图标（PNG）。

必须在 QGuiApplication 构造之后调用（QPixmap 依赖）。
"""

from __future__ import annotations

import os
import tempfile

from src.styles.theme import ACCENT, BG_INPUT

_CACHE_DIR = os.path.join(tempfile.gettempdir(), "reliatrack_assets")


def _gen_check_png(path: str) -> None:
    """蓝底白色 ✓ 的 16×16 PNG。"""
    from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QPen, QBrush, QColor
    from PySide6.QtCore import Qt, QRectF

    px = QPixmap(16, 16)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 蓝色圆角矩形
    r = QRectF(0.5, 0.5, 15, 15)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(ACCENT)))
    p.drawRoundedRect(r, 3, 3)

    # 白色 ✓
    pen = QPen(QColor("#ffffff"))
    pen.setWidth(2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    path_obj = QPainterPath()
    path_obj.moveTo(3.5, 8.5)
    path_obj.lineTo(6.5, 11.5)
    path_obj.lineTo(12.5, 4.5)
    p.drawPath(path_obj)

    p.end()
    px.save(path, "PNG")


def _gen_radio_png(path: str) -> None:
    """蓝环蓝色圆点的 16×16 PNG。"""
    from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor
    from PySide6.QtCore import Qt, QRectF

    px = QPixmap(16, 16)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 白底蓝边圆
    r = QRectF(0.5, 0.5, 15, 15)
    from PySide6.QtGui import QPen
    p.setPen(QPen(QColor(ACCENT), 1.5))
    p.setBrush(QBrush(QColor(BG_INPUT)))
    p.drawEllipse(r)

    # 蓝色实心圆点
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(ACCENT)))
    p.drawEllipse(QRectF(4.5, 4.5, 7, 7))

    p.end()
    px.save(path, "PNG")


def ensure_indicator_icons() -> tuple[str, str]:
    """确保 PNG 图标存在，返回 (check_png, radio_png) 绝对路径。"""
    os.makedirs(_CACHE_DIR, exist_ok=True)

    check_path = os.path.join(_CACHE_DIR, "check.png")
    radio_path = os.path.join(_CACHE_DIR, "radio.png")

    # 每次都重新生成（确保主题色变化后正确）
    _gen_check_png(check_path)
    _gen_radio_png(radio_path)

    return check_path, radio_path
