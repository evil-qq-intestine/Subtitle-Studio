"""生成 MSI 安装向导用的位图（WiX 要求 24 位 BMP，尺寸固定）。

WixUIBannerBmp   493 x 58    大部分对话框顶部那条横幅
WixUIDialogBmp   493 x 312   欢迎页 / 完成页左侧大图
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QImage, QLinearGradient,
                           QPainter, QPainterPath, QRadialGradient)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
sys.path.insert(0, str(ROOT))

from app.ui.icon import paint_icon  # noqa: E402


BG = QColor("#14161f")
BG2 = QColor("#1b1f2b")
ACCENT = QColor("#5b8cff")
TEXT = QColor("#e9ecf4")
MUTED = QColor("#8a93a8")
family = "Microsoft YaHei UI"


def logo(p: QPainter, x: float, y: float, size: float) -> None:
    """直接贴应用图标，保证安装界面和程序图标是同一个样子。"""
    p.drawImage(QRectF(x, y, size, size), paint_icon(max(16, int(round(size)))))


def banner() -> QImage:
    """顶部横幅（许可协议 / 安装位置 / 进度 / 完成页）。

    注意：Windows Installer 会把该页的标题文字（黑色）画在横幅的
    x≈20–286px、y≈10–34px 区域，所以左侧必须留浅色空白，
    品牌元素只能放到右边，否则文字会和图标叠在一起。
    """
    w, h = 493, 66
    img = QImage(w, h, QImage.Format_RGB888)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    grad = QLinearGradient(0, 0, 0, h)
    grad.setColorAt(0.0, QColor("#ffffff"))
    grad.setColorAt(1.0, QColor("#eef1f7"))
    p.fillRect(0, 0, w, h, grad)

    # 右侧品牌区（x >= 320 才安全）
    logo(p, 338, 17, 32)

    f = QFont(family)
    f.setPixelSize(11)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#2b3243"))
    p.drawText(QRectF(378, 24, 112, 18), Qt.AlignLeft | Qt.AlignVCenter, "Subtitle Studio")

    p.fillRect(0, h - 2, w, 2, ACCENT)
    p.end()
    return img


def dialog() -> QImage:
    """欢迎页/完成页背景。

    注意：WiX 会把对话框标题和说明文字直接画在这张图上，系统默认是黑字，
    所以右侧必须留浅色区域，否则字看不清。左边 164px 放品牌，右边浅底。
    """
    w, h = 493, 312
    left = 164
    img = QImage(w, h, QImage.Format_RGB888)
    img.fill(QColor("#fbfbfd"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    # 左侧深色品牌区
    panel = QLinearGradient(0, 0, left, h)
    panel.setColorAt(0.0, QColor("#171b26"))
    panel.setColorAt(1.0, QColor("#0f1219"))
    p.fillRect(0, 0, left, h, panel)

    glow = QRadialGradient(left * 0.5, h * 0.1, 230)
    glow.setColorAt(0.0, QColor(91, 140, 255, 55))
    glow.setColorAt(1.0, QColor(91, 140, 255, 0))
    p.fillRect(0, 0, left, h, glow)

    logo(p, (left - 74) / 2, 96, 74)

    f = QFont(family)
    f.setPixelSize(15)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#e9ecf4"))
    p.drawText(QRectF(0, 184, left, 22), Qt.AlignCenter, "Subtitle Studio")

    f2 = QFont(family)
    f2.setPixelSize(10)
    p.setFont(f2)
    p.setPen(QColor("#7a8296"))
    p.drawText(QRectF(0, 206, left, 18), Qt.AlignCenter, "Subtitle translator")

    # 分隔线与右侧留白
    p.fillRect(left, 0, 1, h, QColor("#dfe3ea"))
    p.end()
    return img


def main() -> int:
    app = QGuiApplication(sys.argv)  # noqa: F841
    OUT.mkdir(parents=True, exist_ok=True)
    for name, gen, size in (("banner.bmp", banner, (493, 66)),
                            ("dialog.bmp", dialog, (493, 312))):
        img = gen()
        if (img.width(), img.height()) != size:
            print(f"{name} 尺寸不对", file=sys.stderr)
            return 1
        path = OUT / name
        if not img.save(str(path), "BMP"):
            print(f"{name} 保存失败", file=sys.stderr)
            return 1
        print(f"ok {path} {img.width()}x{img.height()} {path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




