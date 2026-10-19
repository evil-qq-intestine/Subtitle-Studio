"""应用图标绘制。

同一份绘制代码同时供：窗口图标（运行时）和 .ico 文件（打包/安装包）使用，
避免两处样式跑偏。

设计：蓝色圆角底 + 播放三角 + 字幕条，用来表达「视频字幕」。
不放文字，小尺寸下也认得出来。
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen)

BG_TOP = QColor("#7c9dff")
BG_BOTTOM = QColor("#3f5cd6")
FG = QColor("#ffffff")


def paint_icon(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)

    s = float(size)

    # 底板：圆角方块 + 斜向渐变
    radius = s * 0.225
    rect = QRectF(s * 0.03, s * 0.03, s * 0.94, s * 0.94)
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0.0, BG_TOP)
    grad.setColorAt(1.0, BG_BOTTOM)
    p.setPen(Qt.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(rect, radius, radius)

    # 顶部高光，让方块不那么平
    if size >= 32:
        gloss = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.center().y()))
        gloss.setColorAt(0.0, QColor(255, 255, 255, 46))
        gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(gloss)
        p.drawRoundedRect(rect, radius, radius)

    # 播放三角（圆角三角，比尖角更耐看）
    tri = QPainterPath()
    cx, cy = s * 0.5, s * 0.435
    w, h = s * 0.30, s * 0.34
    tri.moveTo(cx - w * 0.55, cy - h * 0.62)
    tri.lineTo(cx - w * 0.55, cy + h * 0.62)
    tri.lineTo(cx + w * 0.72, cy)
    tri.closeSubpath()
    p.setBrush(FG)
    if size >= 24:
        pen = QPen(FG)
        pen.setWidthF(max(1.0, s * 0.055))
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
    p.drawPath(tri)

    # 字幕条
    p.setPen(Qt.NoPen)
    bar_h = max(1.0, s * 0.062)
    bar_r = bar_h / 2
    y1 = s * 0.685
    y2 = s * 0.805
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawRoundedRect(QRectF(s * 0.245, y1, s * 0.51, bar_h), bar_r, bar_r)
    p.setBrush(QColor(255, 255, 255, 150))
    p.drawRoundedRect(QRectF(s * 0.245, y2, s * 0.31, bar_h), bar_r, bar_r)

    p.end()
    return img
