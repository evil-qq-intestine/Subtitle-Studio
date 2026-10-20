"""通用界面组件。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from ..i18n import tr
from . import theme


class Card(QFrame):
    """圆角卡片容器。"""

    def __init__(self, parent: QWidget | None = None, inner: bool = False):
        super().__init__(parent)
        self.setObjectName("CardInner" if inner else "Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 18, 20, 18)
        self.body.setSpacing(12)


class Badge(QLabel):
    COLORS = {
        "run": (theme.ACCENT, "#1b2540"),
        "ok": (theme.OK, "#14291f"),
        "err": (theme.ERR, "#2b1a1e"),
        "idle": (theme.MUTED, "#1a1e28"),
    }

    def __init__(self, text: str = "", state: str = "idle", parent: QWidget | None = None):
        super().__init__(text, parent)
        self._state = state
        self.set_state(state, text)
        self.setAlignment(Qt.AlignCenter)

    def set_state(self, state: str, text: str | None = None) -> None:
        self._state = state
        if text is not None:
            self.setText(text)
        fg, bg = self.COLORS.get(state, self.COLORS["idle"])
        self.setStyleSheet(
            f"color:{fg}; background:{bg}; border:1px solid {fg}33;"
            f"border-radius:9px; padding:2px 9px; font-size:8.5pt; font-weight:600;"
        )


class TaskCard(QFrame):
    """任务条目：标题 / 状态 / 进度 / 操作。"""

    cancelRequested = Signal(str)
    openRequested = Signal(str)
    retryRequested = Signal(str)

    def __init__(self, task_id: str, title: str, subtitle: str = "",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.task_id = task_id
        self._folder = ""
        self._state = "idle"
        self.setObjectName("TaskCard")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(9)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("SectionTitle")
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.badge = Badge(tr("task.preparing"), "idle")
        top.addWidget(self.title_label, 1)
        top.addWidget(self.badge, 0, Qt.AlignTop)

        self.open_btn = QPushButton(tr("common.open_folder"))
        self.open_btn.setObjectName("Ghost")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.clicked.connect(lambda: self.openRequested.emit(self._folder))
        self.open_btn.setVisible(False)

        self.cancel_btn = QPushButton(tr("task.cancel"))
        self.cancel_btn.setObjectName("Ghost")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(lambda: self.cancelRequested.emit(self.task_id))

        self.retry_btn = QPushButton(tr("task.retry"))
        self.retry_btn.setObjectName("Ghost")
        self.retry_btn.setCursor(Qt.PointingHandCursor)
        self.retry_btn.clicked.connect(lambda: self.retryRequested.emit(self.task_id))
        self.retry_btn.setVisible(False)

        top.addWidget(self.open_btn, 0, Qt.AlignTop)
        top.addWidget(self.retry_btn, 0, Qt.AlignTop)
        top.addWidget(self.cancel_btn, 0, Qt.AlignTop)
        root.addLayout(top)

        self.status_label = QLabel(subtitle or tr("task.queued"))
        self.status_label.setObjectName("Hint")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        root.addWidget(self.bar)

    # ------------------------------------------------------------- 状态
    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_title(self, text: str) -> None:
        if text:
            self.title_label.setText(text)
            self.title_label.setToolTip(text)

    def set_progress(self, ratio: float) -> None:
        self.bar.setValue(max(0, min(1000, int(ratio * 1000))))

    def finish(self, folder: str, summary: str) -> None:
        self._folder = folder
        self._state = "ok"
        self.badge.set_state("ok", tr("task.done"))
        self.status_label.setText(summary)
        self.set_progress(1.0)
        self.bar.setStyleSheet("QProgressBar::chunk{background:%s;border-radius:4px;}" % theme.OK)
        self.cancel_btn.setVisible(False)
        self.retry_btn.setVisible(False)
        if folder:
            self.open_btn.setVisible(True)

    def fail(self, message: str) -> None:
        self._state = "err"
        self.badge.set_state("err", tr("task.failed"))
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color:{theme.ERR};")
        self.bar.setStyleSheet("QProgressBar::chunk{background:%s;border-radius:4px;}" % theme.ERR)
        self.cancel_btn.setVisible(False)
        self.retry_btn.setVisible(True)

    def cancelled(self) -> None:
        self._state = "idle"
        self.badge.set_state("idle", tr("task.cancelled"))
        self.status_label.setText(tr("task.cancelled_body"))
        self.bar.setStyleSheet("")
        self.cancel_btn.setVisible(False)
        self.retry_btn.setVisible(True)

    def running(self) -> None:
        self._state = "run"
        self.badge.set_state("run", tr("task.running"))
        self.retry_btn.setVisible(False)
        self.cancel_btn.setVisible(True)

    def reset_for_retry(self) -> None:
        """重试用：把卡片恢复到刚开始跑的样子。"""
        self.status_label.setStyleSheet("")
        self.status_label.setText(tr("task.queued"))
        self.bar.setStyleSheet("")
        self.set_progress(0)
        self.open_btn.setVisible(False)
        self.retry_btn.setVisible(False)
        self.running()

    def retranslate(self) -> None:
        self.open_btn.setText(tr("common.open_folder"))
        self.cancel_btn.setText(tr("task.cancel"))
        self.retry_btn.setText(tr("task.retry"))
        if self._state == "run":
            self.badge.set_state("run", tr("task.running"))
        elif self._state == "ok":
            self.badge.set_state("ok", tr("task.done"))
        elif self._state == "err":
            self.badge.set_state("err", tr("task.failed"))


class DropZone(QFrame):
    """拖拽 / 点击选择本地视频。"""

    fileDropped = Signal(str)
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(104)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignCenter)

        self.icon = QLabel("↓")
        self.icon.setStyleSheet(f"color:{theme.ACCENT}; font-size:22pt; font-weight:600;")
        self.icon.setAlignment(Qt.AlignCenter)

        self.title = QLabel(tr("drop.title"))
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size:10.5pt; font-weight:600;")

        self.hint = QLabel(tr("drop.hint"))
        self.hint.setObjectName("Hint")
        self.hint.setAlignment(Qt.AlignCenter)

        lay.addWidget(self.icon)
        lay.addWidget(self.title)
        lay.addWidget(self.hint)

    def retranslate(self) -> None:
        self.title.setText(tr("drop.title"))
        self.hint.setText(tr("drop.hint"))

    # ---------------------------------------------------------- 拖拽
    def dragEnterEvent(self, event):  # noqa: N802
        mime = event.mimeData()
        if mime.hasUrls() and any(u.isLocalFile() for u in mime.urls()):
            event.acceptProposedAction()
            self.setStyleSheet(
                f"#DropZone{{border-color:{theme.ACCENT}; background:#141a2b;}}")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):  # noqa: N802
        self.setStyleSheet("")

    def dropEvent(self, event):  # noqa: N802
        self.setStyleSheet("")
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.fileDropped.emit(url.toLocalFile())
                break

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


def open_in_explorer(path: str) -> None:
    p = Path(path)
    if p.exists():
        QDesktopServices.openUrl(p.as_uri() if p.is_dir() else p.parent.as_uri())


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line

