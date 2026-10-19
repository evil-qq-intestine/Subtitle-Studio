"""主窗口。"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox,
                               QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QMessageBox, QPushButton,
                               QScrollArea, QSizePolicy, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..config import TARGET_LANGS, Settings
from ..core import backends, env as toolenv
from ..core.pipeline import Cancelled, JobResult, JobSpec, Pipeline, PipelineError
from ..i18n import get_language, set_language, tr
from . import theme
from .icon import paint_icon
from .settings import SettingsDialog
from .widgets import Card, DropZone, TaskCard, divider, open_in_explorer

VIDEO_EXTS = ".mp4 .mkv .mov .webm .avi .flv .m4v .ts"


# ---------------------------------------------------------------- 线程
class JobThread(QThread):
    sig_status = Signal(str)
    sig_progress = Signal(float)
    sig_log = Signal(str)
    sig_done = Signal(object)
    sig_fail = Signal(str)

    def __init__(self, settings: Settings, spec: JobSpec):
        super().__init__()
        self.spec = spec
        self.pipeline = Pipeline(settings, self.sig_status.emit,
                                 self.sig_progress.emit, self.sig_log.emit)

    def run(self) -> None:  # noqa: D401
        try:
            self.sig_done.emit(self.pipeline.run(self.spec))
        except Cancelled:
            self.sig_fail.emit("__cancelled__")
        except PipelineError as exc:
            self.sig_fail.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.sig_fail.emit(f"{type(exc).__name__}: {exc}")

    def cancel(self) -> None:
        self.pipeline.cancel()


class BootstrapThread(QThread):
    """启动时检查工具；缺 yt-dlp 就下。"""
    sig_status = Signal(str)
    sig_done = Signal(dict)

    def __init__(self, settings: Settings):
        super().__init__()
        self.s = settings

    def run(self) -> None:  # noqa: D401
        info: dict = {}
        # 首次启动：本地有 Ollama 就自动挑一个模型
        if self.s.backend == "ollama" and not self.s.ollama_model:
            try:
                self.sig_status.emit(tr("main.engine_detecting"))
                models = backends.probe_ollama(self.s.ollama_url)
                if models:
                    self.s.ollama_model = backends.pick_model(models)
                    self.s.save()
            except Exception:  # noqa: BLE001
                pass
        try:
            self.sig_status.emit(tr("st.tools"))
            path = toolenv.ensure_ytdlp(
                self.s,
                log=lambda m: self.sig_status.emit(m),
                progress=lambda p, m: self.sig_status.emit(m),
            )
            info["ytdlp"] = str(path)
        except Exception as exc:  # noqa: BLE001
            info["ytdlp_error"] = str(exc)
        try:
            if not self.s.proxy:
                guess = toolenv.detect_local_proxy()
                if guess:
                    self.s.proxy = guess
                    self.s.save()
                    self.sig_status.emit(f"proxy: {guess}")
        except Exception:  # noqa: BLE001
            pass
        try:
            ff = toolenv.find_ffmpeg(self.s)
            info["ffmpeg"] = str(ff) if ff else ""
        except Exception:  # noqa: BLE001
            info["ffmpeg"] = ""
        self.sig_done.emit(info)


class Segmented(QWidget):
    """链接 / 本地文件 切换。"""

    changed = Signal(int)

    def __init__(self, labels: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: list[QPushButton] = []
        for i, text in enumerate(labels):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setChecked(i == 0)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent; border: 1px solid transparent;
                    border-radius: 8px; padding: 7px 18px; color: #8a93a8;
                }
                QPushButton:hover { color: #e9ecf4; }
                QPushButton:checked {
                    background: #232838; border-color: #2f3749; color: #e9ecf4;
                    font-weight: 600;
                }
            """)
            self.group.addButton(btn, i)
            lay.addWidget(btn)
            self.buttons.append(btn)
        self.group.idClicked.connect(self.changed.emit)

    def set_labels(self, labels: list[str]) -> None:
        for btn, text in zip(self.buttons, labels):
            btn.setText(text)


# ---------------------------------------------------------------- 窗口
class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.s = settings
        self.tasks: dict[str, tuple[JobThread, TaskCard]] = {}
        self._bootstrap: BootstrapThread | None = None
        self._pages: list[TaskCard] = []

        self.resize(1060, 780)
        self.setMinimumSize(880, 640)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(26, 22, 26, 20)
        root.setSpacing(16)

        root.addWidget(self._build_header())
        root.addWidget(self._build_input())
        root.addWidget(self._build_tasks(), 1)

        self._apply_settings_to_ui()
        self.retranslate()

    # ------------------------------------------------------------ 头部
    def _build_header(self) -> QWidget:
        head = QWidget()
        head.setObjectName("Header")
        lay = QHBoxLayout(head)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        # 和 exe 图标用同一份绘制代码，保证是一致的标识
        logo = QLabel()
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignCenter)
        pix = QPixmap.fromImage(paint_icon(80))
        pix.setDevicePixelRatio(2.0)
        logo.setPixmap(pix)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.app_title = QLabel("Subtitle Studio")
        self.app_title.setObjectName("Title")
        self.tagline = QLabel()
        self.tagline.setObjectName("Subtitle")
        titles.addWidget(self.app_title)
        titles.addWidget(self.tagline)

        lay.addWidget(logo)
        lay.addLayout(titles)
        lay.addStretch(1)

        self.engine_chip = QPushButton()
        self.engine_chip.setObjectName("Chip")
        self.engine_chip.setCursor(Qt.PointingHandCursor)
        self.engine_chip.clicked.connect(self._open_settings)
        lay.addWidget(self.engine_chip)

        self.folder_btn = QPushButton()
        self.folder_btn.setObjectName("Ghost")
        self.folder_btn.setCursor(Qt.PointingHandCursor)
        self.folder_btn.clicked.connect(lambda: open_in_explorer(str(self.s.workdir_path())))
        lay.addWidget(self.folder_btn)

        self.gear_btn = QPushButton()
        self.gear_btn.setObjectName("Ghost")
        self.gear_btn.setCursor(Qt.PointingHandCursor)
        self.gear_btn.clicked.connect(self._open_settings)
        lay.addWidget(self.gear_btn)
        return head

    # ------------------------------------------------------------ 输入
    def _build_input(self) -> QWidget:
        card = Card()
        body = card.body
        body.setSpacing(14)

        top = QHBoxLayout()
        self.seg = Segmented(["", ""])
        self.seg.changed.connect(self._switch_mode)
        top.addWidget(self.seg)
        top.addStretch(1)
        body.addLayout(top)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_url())
        self.stack.addWidget(self._page_local())
        self.stack.currentChanged.connect(self._fit_stack)
        body.addWidget(self.stack)

        opts = QHBoxLayout()
        opts.setSpacing(14)
        self.target_caption = QLabel()
        self.target_caption.setObjectName("Muted")
        opts.addWidget(self.target_caption)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(TARGET_LANGS)
        self.lang_combo.setEditable(False)
        self.lang_combo.setFixedWidth(160)
        self.lang_combo.currentTextChanged.connect(self._on_lang_change)
        opts.addWidget(self.lang_combo)

        self.fmt_combo = QComboBox()
        for label, code in (("1080p", "1080"), ("720p", "720"), ("480p", "480"),
                            ("4K", "2160")):
            self.fmt_combo.addItem(label, code)
        self.fmt_combo.addItem("", "best")
        self.fmt_combo.setFixedWidth(100)
        opts.addWidget(self.fmt_combo)

        self.chk_video = QCheckBox()
        self.chk_video.setChecked(self.s.download_video)
        opts.addWidget(self.chk_video)

        self.chk_merge = QCheckBox()
        self.chk_merge.setChecked(self.s.merge_sentences)
        opts.addWidget(self.chk_merge)

        opts.addStretch(1)
        body.addLayout(opts)
        return card

    def _page_url(self) -> QWidget:
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.url_edit = QLineEdit()
        self.url_edit.setMinimumHeight(42)
        self.url_edit.returnPressed.connect(self._start_url)

        self.go_btn = QPushButton()
        self.go_btn.setObjectName("Primary")
        self.go_btn.setMinimumHeight(42)
        self.go_btn.setCursor(Qt.PointingHandCursor)
        self.go_btn.clicked.connect(self._start_url)

        lay.addWidget(self.url_edit, 1)
        lay.addWidget(self.go_btn)
        return page

    def _page_local(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        self.drop = DropZone()
        self.drop.fileDropped.connect(self._start_local)
        self.drop.clicked.connect(self._pick_file)
        lay.addWidget(self.drop)
        return page

    # ------------------------------------------------------------ 任务区
    def _build_tasks(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        row = QHBoxLayout()
        self.task_title = QLabel()
        self.task_title.setObjectName("SectionTitle")
        row.addWidget(self.task_title)
        row.addStretch(1)
        lay.addLayout(row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        container = QWidget()
        self.task_layout = QVBoxLayout(container)
        self.task_layout.setContentsMargins(0, 0, 6, 0)
        self.task_layout.setSpacing(10)
        self.task_layout.addStretch(1)
        self.scroll.setWidget(container)
        lay.addWidget(self.scroll, 1)

        self.empty = QLabel()
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet(f"color:{theme.MUTED}; font-size:11pt;")
        lay.addWidget(self.empty, 1)
        self._update_empty()
        return wrap

    def _update_empty(self) -> None:
        has_tasks = self.task_layout.count() > 1
        self.scroll.setVisible(has_tasks)
        self.empty.setVisible(not has_tasks)

    # ------------------------------------------------------------ 交互
    def _switch_mode(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        is_url = index == 0
        self.fmt_combo.setVisible(is_url)
        self.chk_video.setVisible(is_url)
        self._fit_stack()
        if is_url:
            self.url_edit.setFocus()

    def _fit_stack(self, *_args) -> None:
        page = self.stack.currentWidget()
        if page is None:
            return
        height = page.sizeHint().height()
        if height > 0:
            self.stack.setFixedHeight(height)

    # ------------------------------------------------------------ 窗口
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if getattr(self, "_placed", False):
            return
        self._placed = True
        self._apply_dark_titlebar()
        QTimer.singleShot(0, self._center_on_screen)
        QTimer.singleShot(0, self._fit_stack)

    def _center_on_screen(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        width = min(self.width(), int(geo.width() * 0.92))
        height = min(self.height(), int(geo.height() * 0.92))
        self.resize(width, height)
        frame = self.frameGeometry()
        frame.moveCenter(geo.center())
        self.move(max(frame.left(), geo.left()), max(frame.top(), geo.top()))

    def _apply_dark_titlebar(self) -> None:
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            value = ctypes.c_int(1)
            for attr in (20, 19):
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                    break
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ 配置 → UI
    def _apply_settings_to_ui(self) -> None:
        idx = self.lang_combo.findText(self.s.target_lang)
        if idx < 0:
            idx = 0
            self.s.target_lang = self.lang_combo.itemText(0)
        self.lang_combo.setCurrentIndex(idx)
        self.fmt_combo.setCurrentIndex(max(0, self.fmt_combo.findData(self.s.video_format)))
        self.chk_video.setChecked(self.s.download_video)
        self.chk_merge.setChecked(self.s.merge_sentences)
        self._refresh_engine_chip()

    def _on_lang_change(self, text: str) -> None:
        text = text.strip()
        if text and text != self.s.target_lang:
            self.s.target_lang = text
            self.s.save()

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("main.tab_local"), str(Path.home()),
            f"Video (*{VIDEO_EXTS.replace(' ', ' *')});;All files (*)")
        if path:
            self._start_local(path)

    # ------------------------------------------------------------ 启动任务
    def _validate(self) -> bool:
        if self._bootstrap and self._bootstrap.isRunning():
            QMessageBox.information(self, tr("msg.busy_title"), tr("msg.busy_body"))
            return False
        try:
            backends.build_translator(self.s)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("msg.no_engine_title"),
                                tr("msg.no_engine_body", err=exc))
            self._open_settings()
            return False
        return True

    def _start_url(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            self.url_edit.setFocus()
            return
        if not url.lower().startswith(("http://", "https://")):
            QMessageBox.warning(self, tr("msg.bad_url_title"), tr("msg.bad_url_body"))
            return
        if not self._validate():
            return
        self.s.download_video = self.chk_video.isChecked()
        self.s.merge_sentences = self.chk_merge.isChecked()
        self.s.video_format = self.fmt_combo.currentData() or "1080"
        self.s.target_lang = self.lang_combo.currentText().strip() or "简体中文"
        self.s.save()

        spec = JobSpec(source=url, is_url=True, target_lang=self.s.target_lang,
                       download_video=self.s.download_video,
                       video_format=self.s.video_format)
        self._spawn(spec, title=url, subtitle=tr("task.queued"))
        self.url_edit.clear()

    def _start_local(self, path: str) -> None:
        p = Path(path)
        if not p.is_file():
            return
        if not self._validate():
            return
        self.s.merge_sentences = self.chk_merge.isChecked()
        self.s.target_lang = self.lang_combo.currentText().strip() or "简体中文"
        self.s.save()
        spec = JobSpec(source=str(p), is_url=False, target_lang=self.s.target_lang,
                       download_video=False)
        self._spawn(spec, title=p.name, subtitle=tr("task.queued"))

    def _spawn(self, spec: JobSpec, title: str, subtitle: str) -> None:
        tid = uuid.uuid4().hex[:10]
        card = TaskCard(tid, self._short(title), subtitle)
        card.cancelRequested.connect(self._cancel_task)
        card.openRequested.connect(open_in_explorer)

        self.task_layout.insertWidget(self.task_layout.count() - 1, card)
        self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum())

        thread = JobThread(self.s, spec)
        thread.sig_status.connect(lambda m, t=tid: self._on_status(t, m))
        thread.sig_progress.connect(lambda v, t=tid: self._on_progress(t, v))
        thread.sig_done.connect(lambda r, t=tid: self._on_done(t, r))
        thread.sig_fail.connect(lambda m, t=tid: self._on_fail(t, m))
        thread.finished.connect(lambda t=tid: self.tasks.pop(t, None))
        self.tasks[tid] = (thread, card)
        self._pages.append(card)
        card.running()
        self._update_empty()
        thread.start()

    def _short(self, text: str, limit: int = 64) -> str:
        return text if len(text) <= limit else text[: limit - 1] + "…"

    # ------------------------------------------------------------ 回调
    def _on_status(self, tid: str, message: str) -> None:
        item = self.tasks.get(tid)
        if item:
            item[1].set_status(message)

    def _on_progress(self, tid: str, ratio: float) -> None:
        item = self.tasks.get(tid)
        if item:
            item[1].set_progress(ratio)

    def _on_done(self, tid: str, result: JobResult) -> None:
        item = self.tasks.get(tid)
        if not item:
            return
        card = item[1]
        card.set_title(result.title)
        folder = str(result.subtitle_files[0].parent) if result.subtitle_files else ""
        parts = [tr("task.summary", cues=result.cue_count), f"{result.seconds:.0f}s"]
        if result.video_path:
            parts.insert(0, tr("task.summary_video"))
        card.finish(folder, "  ·  ".join(parts))

    def _on_fail(self, tid: str, message: str) -> None:
        item = self.tasks.get(tid)
        if not item:
            return
        if message == "__cancelled__":
            item[1].cancelled()
        else:
            item[1].fail(message)

    def _cancel_task(self, tid: str) -> None:
        item = self.tasks.get(tid)
        if item:
            item[1].set_status(tr("task.cancelling"))
            item[0].cancel()

    # ------------------------------------------------------------ 设置
    def _open_settings(self) -> None:
        before = get_language()
        dlg = SettingsDialog(self.s, self)
        if dlg.exec() == SettingsDialog.Accepted:
            self.s = dlg.result_settings()
            self.s.save()
            if self.s.ui_lang:
                set_language(self.s.ui_lang)
            else:
                from ..i18n import detect_language
                set_language(detect_language())
            self._apply_settings_to_ui()
            if get_language() != before:
                self.retranslate()
            else:
                self._refresh_engine_chip()

    def _refresh_engine_chip(self) -> None:
        try:
            backends.build_translator(self.s)
            ok = True
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            self.engine_chip.setText(f"●  {self.s.backend_label}")
            self.engine_chip.setStyleSheet(
                f"QPushButton#Chip{{color:{theme.OK}; border-color:{theme.OK}44;}}")
        else:
            self.engine_chip.setText(f"●  {tr('main.engine_missing')}")
            self.engine_chip.setStyleSheet(
                f"QPushButton#Chip{{color:{theme.WARN}; border-color:{theme.WARN}44;}}")
        self.engine_chip.setToolTip(tr("main.engine_tip"))

    # ------------------------------------------------------------ 文案
    def retranslate(self) -> None:
        self.setWindowTitle(f"Subtitle Studio · {tr('app.tagline')}")
        self.tagline.setText(tr("app.tagline"))
        self.folder_btn.setText(tr("main.folder"))
        self.gear_btn.setText(tr("main.settings"))

        self.seg.set_labels([tr("main.tab_url"), tr("main.tab_local")])
        self.url_edit.setPlaceholderText(tr("main.url_placeholder"))
        self.go_btn.setText(tr("main.start"))
        self.target_caption.setText(tr("main.target"))
        self.chk_video.setText(tr("main.download_video"))
        self.chk_merge.setText(tr("main.merge"))
        self.chk_merge.setToolTip(tr("main.merge_tip"))
        self.task_title.setText(tr("main.tasks"))
        self.empty.setText(tr("main.empty"))

        # “最高”这个选项没有固定文字
        best_index = self.fmt_combo.findData("best")
        if best_index >= 0:
            self.fmt_combo.setItemText(best_index, "Best" if get_language() == "en" else "最高")

        self.drop.retranslate()
        for card in self._pages:
            card.retranslate()
        self._refresh_engine_chip()

    # ------------------------------------------------------------ 启动自检
    def start_bootstrap(self) -> None:
        self._bootstrap = BootstrapThread(self.s)
        self._bootstrap.sig_status.connect(lambda m: self.engine_chip.setText(m))
        self._bootstrap.sig_done.connect(self._on_bootstrap_done)
        self._bootstrap.start()

    def _on_bootstrap_done(self, info: dict) -> None:
        self._refresh_engine_chip()
        if info.get("ytdlp_error"):
            QMessageBox.warning(self, tr("msg_ytdlp_title"),
                                tr("msg_ytdlp_body", err=info["ytdlp_error"]))

    # ------------------------------------------------------------ 关闭
    def closeEvent(self, event) -> None:  # noqa: N802
        running = [t for t, _ in self.tasks.values() if t.isRunning()]
        if running:
            reply = QMessageBox.question(
                self, tr("msg.quitting_title"),
                tr("msg.quitting_body", n=len(running)),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                event.ignore()
                return
            for t in running:
                t.cancel()
            for t in running:
                if not t.wait(4000):
                    t.terminate()
                    t.wait(1500)
        self.s.save()
        event.accept()


