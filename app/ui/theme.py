"""深色主题：配色、字体、QSS。"""
from __future__ import annotations

import sys

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

# ------------------------------------------------------------------ 调色板
BG = "#0f1117"
SURFACE = "#161922"
SURFACE_2 = "#1c202b"
SURFACE_3 = "#232838"
BORDER = "#272d3c"
TEXT = "#e9ecf4"
MUTED = "#8a93a8"
ACCENT = "#5b8cff"
ACCENT_DIM = "#3f68c8"
OK = "#37d399"
WARN = "#f2b544"
ERR = "#ff6b6b"

FONT_CANDIDATES = [
    "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
    "Noto Sans CJK SC", "Source Han Sans SC", "Segoe UI", "Helvetica Neue",
]


def pick_font_family() -> str:
    try:
        available = set(QFontDatabase.families())
    except Exception:  # noqa: BLE001
        available = set()
    for name in FONT_CANDIDATES:
        if name in available:
            return name
    return "sans-serif"


def _make_icons() -> dict[str, str]:
    """生成几个小图标给 QSS 用（QSS 没法直接画图形）。"""
    from pathlib import Path

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

    from ..config import app_data_dir

    out = {}
    base = Path(app_data_dir())

    def save(name: str, draw) -> str:
        target = base / name
        if not target.exists():
            pm = QPixmap(28, 28)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor("#8a93a8"))
            pen.setWidth(4)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            draw(p)
            p.end()
            pm.save(str(target))
        return target.as_posix()

    out["check"] = save("check.png", lambda p: p.drawPolyline(
        [QPoint(6, 15), QPoint(12, 21), QPoint(22, 8)]))

    def chevron(p):
        p.drawPolyline([QPoint(8, 11), QPoint(14, 18), QPoint(20, 11)])

    out["chevron"] = save("chevron.png", chevron)
    return out


def apply_theme(app: QApplication) -> None:
    family = pick_font_family()
    font = QFont(family, 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    try:
        icons = _make_icons()
    except Exception:  # noqa: BLE001
        icons = {"check": "", "chevron": ""}
    sheet = (STYLESHEET
             .replace("__FONT__", family)
             .replace("__CHECK__", icons["check"])
             .replace("__CHEVRON__", icons["chevron"]))
    app.setStyleSheet(sheet)


STYLESHEET = """
* { outline: none; }

QWidget {
    background: %(bg)s;
    color: %(text)s;
    font-family: "__FONT__";
    font-size: 10pt;
}

QLabel { background: transparent; }

QToolTip {
    background: %(surface3)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 6px 8px;
}

/* ---------------------------------------------------------------- 容器 */
#Header { background: transparent; }
#Card {
    background: %(surface)s;
    border: 1px solid %(border)s;
    border-radius: 14px;
}
#CardInner {
    background: %(surface2)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
}
#TaskCard {
    background: %(surface)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
}
#TaskCard:hover { border-color: #323a4d; }

#Divider { background: %(border)s; max-height: 1px; min-height: 1px; border: none; }

/* ---------------------------------------------------------------- 文字 */
#Title { font-size: 17pt; font-weight: 600; }
#Subtitle { color: %(muted)s; font-size: 9pt; }
#SectionTitle { font-size: 10pt; font-weight: 600; color: %(text)s; }
#Hint { color: %(muted)s; font-size: 9pt; }
#Mono { font-family: "Consolas", "Menlo", "DejaVu Sans Mono", monospace; font-size: 9pt; }
#Danger { color: %(err)s; }
#OkText { color: %(ok)s; }
#Muted { color: %(muted)s; }

/* ---------------------------------------------------------------- 按钮 */
QPushButton {
    background: %(surface3)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 9px;
    padding: 8px 16px;
}
QPushButton:hover { background: #2b3244; border-color: #3a4358; }
QPushButton:pressed { background: #1c2029; }
QPushButton:disabled { color: #5d6579; background: #191d26; border-color: #222734; }

QPushButton#Primary {
    background: %(accent)s;
    border: 1px solid %(accent)s;
    color: #0d1020;
    font-weight: 600;
    padding: 9px 22px;
}
QPushButton#Primary:hover { background: #7ba2ff; border-color: #7ba2ff; }
QPushButton#Primary:pressed { background: %(accent_dim)s; }
QPushButton#Primary:disabled { background: #2a3350; border-color: #2a3350; color: #7d87a5; }

QPushButton#Ghost {
    background: transparent;
    border: 1px solid %(border)s;
}
QPushButton#Ghost:hover { background: %(surface2)s; border-color: #3a4358; }

QPushButton#Danger:hover { background: #3a2126; border-color: %(err)s; color: %(err)s; }

QPushButton#Chip {
    background: %(surface2)s;
    border: 1px solid %(border)s;
    border-radius: 13px;
    padding: 4px 12px;
    font-size: 9pt;
    color: %(muted)s;
}
QPushButton#Chip:hover { color: %(text)s; border-color: #3a4358; }

QToolButton {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 6px;
}
QToolButton:hover { background: %(surface2)s; }

/* ---------------------------------------------------------------- 输入 */
QLineEdit, QComboBox, QSpinBox {
    background: %(bg)s;
    border: 1px solid %(border)s;
    border-radius: 9px;
    padding: 9px 12px;
    selection-background-color: %(accent)s;
    selection-color: #0d1020;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: %(accent)s; }
QLineEdit:hover, QComboBox:hover { border-color: #37405a; }
QLineEdit:disabled { color: #5d6579; }

QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url("__CHEVRON__"); width: 14px; height: 14px; }
QSpinBox::up-button, QSpinBox::down-button {
    width: 0px; height: 0px; border: none; background: transparent;
}
QComboBox QAbstractItemView {
    background: %(surface2)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    selection-background-color: %(accent)s;
    selection-color: #0d1020;
    padding: 4px;
}

QCheckBox { spacing: 8px; color: %(text)s; }
QCheckBox::indicator {
    width: 17px; height: 17px;
    border-radius: 5px;
    border: 1px solid #3a4358;
    background: %(bg)s;
}
QCheckBox::indicator:hover { border-color: %(accent)s; }
QCheckBox::indicator:checked {
    background: %(accent)s;
    border-color: %(accent)s;
    image: url("__CHECK__");
}
QRadioButton { spacing: 8px; }

/* ---------------------------------------------------------------- 进度 */
QProgressBar {
    background: #202632;
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}
QProgressBar::chunk {
    background: %(accent)s;
    border-radius: 4px;
}

/* ---------------------------------------------------------------- 滚动 */
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #2c3446;
    border-radius: 5px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover { background: #3a4358; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 10px; background: transparent; }
QScrollBar::handle:horizontal { background: #2c3446; border-radius: 5px; min-width: 32px; }

/* ---------------------------------------------------------------- 其他 */
QTabWidget::pane { border: none; }
QTabBar::tab {
    background: transparent;
    color: %(muted)s;
    padding: 9px 18px;
    border-radius: 8px;
    margin-right: 4px;
}
QTabBar::tab:selected { background: %(surface2)s; color: %(text)s; }
QTabBar::tab:hover { color: %(text)s; }

QSplitter::handle { background: %(border)s; }
QDialog { background: %(bg)s; }
QSplitter::handle:hover { background: %(accent)s; }

#DropZone {
    background: #12151d;
    border: 1px dashed #333c52;
    border-radius: 12px;
}
#DropZone:hover {
    border-color: %(accent)s;
    background: #141826;
}
""" % {
    "bg": BG, "surface": SURFACE, "surface2": SURFACE_2, "surface3": SURFACE_3,
    "border": BORDER, "text": TEXT, "muted": MUTED,
    "accent": ACCENT, "accent_dim": ACCENT_DIM,
    "ok": OK, "warn": WARN, "err": ERR,
}
