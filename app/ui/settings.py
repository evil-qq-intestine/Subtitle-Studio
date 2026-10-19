"""设置对话框：常规 / 翻译引擎 / 工具 / 下载。"""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QSpinBox,
                               QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

from ..config import TARGET_LANGS, Settings
from ..core import backends, env as toolenv
from ..i18n import LANGUAGES, coverage, get_language, set_language, tr
from . import theme
from .widgets import divider

SRC_LANGS = ["en", "ja", "ko", "zh", "fr", "de", "es", "ru"]
SRC_LANG_LABELS = {
    "en": ("英语", "English"), "ja": ("日语", "Japanese"), "ko": ("韩语", "Korean"),
    "zh": ("中文", "Chinese"), "fr": ("法语", "French"), "de": ("德语", "German"),
    "es": ("西班牙语", "Spanish"), "ru": ("俄语", "Russian"),
}
QUALITY = [("1080p", "1080"), ("720p", "720"), ("480p", "480"), ("4K", "2160"),
           ("best", "best")]
COOKIE_BROWSERS = ["chrome", "edge", "firefox", "brave", "chromium", "opera", "vivaldi"]
IMPERSONATE = ["chrome", "safari", "edge", "firefox"]


def _row(widgets: list[QWidget]) -> QHBoxLayout:
    """输入框/下拉框占满剩余宽度，按钮保持自然宽度。"""
    lay = QHBoxLayout()
    lay.setSpacing(8)
    expandable = (QLineEdit, QComboBox)
    for w in widgets:
        lay.addWidget(w, 1 if isinstance(w, expandable) else 0)
    if not any(isinstance(w, expandable) for w in widgets):
        lay.addStretch(1)
    return lay


class SettingsDialog(QDialog):
    """语言切换会即时预览，点保存才写回配置。"""

    def __init__(self, settings: Settings, parent: QWidget | None = None):
        super().__init__(parent)
        self.s = replace(settings)
        self.setMinimumSize(700, 600)
        self.setModal(True)

        self._labels: list[tuple[QLabel, str]] = []
        self._buttons: list[tuple[QPushButton, str]] = []
        self._placeholders: list[tuple[QLineEdit, str]] = []
        self._hints: list[tuple[QLabel, str]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 16)
        root.setSpacing(14)

        self.title = QLabel()
        self.title.setObjectName("Title")
        self._labels.append((self.title, "set.title"))
        root.addWidget(self.title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_general(), "")
        self.tabs.addTab(self._tab_engine(), "")
        self.tabs.addTab(self._tab_tools(), "")
        self.tabs.addTab(self._tab_download(), "")
        root.addWidget(self.tabs, 1)

        root.addWidget(divider())
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.cancel_btn = QPushButton()
        self.cancel_btn.setObjectName("Ghost")
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton()
        self.save_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(self._save)
        self._buttons.append((self.cancel_btn, "common.cancel"))
        self._buttons.append((self.save_btn, "common.save"))
        bottom.addWidget(self.cancel_btn)
        bottom.addWidget(self.save_btn)
        root.addLayout(bottom)

        self._sync_backend_page()
        self.retranslate()

    # ------------------------------------------------------------ 小工具
    def _lab(self, key: str) -> QLabel:
        lab = QLabel()
        self._labels.append((lab, key))
        return lab

    def _btn(self, key: str) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("Ghost")
        self._buttons.append((btn, key))
        return btn

    def _hint(self, key: str) -> QLabel:
        lab = QLabel()
        lab.setObjectName("Hint")
        lab.setWordWrap(True)
        self._hints.append((lab, key))
        return lab

    # ------------------------------------------------------------ 常规
    def _tab_general(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(4, 16, 4, 4)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight)

        self.ui_lang = QComboBox()
        self.ui_lang.addItem("", "")
        for code, _label in LANGUAGES:
            self.ui_lang.addItem("", code)
        self.ui_lang.setCurrentIndex(max(0, self.ui_lang.findData(self.s.ui_lang)))
        self.ui_lang.currentIndexChanged.connect(self._preview_language)
        form.addRow(self._lab("set.ui_lang"), self.ui_lang)

        self.workdir = QLineEdit(self.s.workdir)
        browse = self._btn("common.browse")
        browse.clicked.connect(self._pick_workdir)
        form.addRow(self._lab("set.workdir"), _row([self.workdir, browse]))

        self.proxy = QLineEdit(self.s.proxy)
        self._placeholders.append((self.proxy, "set.proxy_hint"))
        form.addRow(self._lab("set.proxy"), self.proxy)

        self.target = QComboBox()
        self.target.addItems(TARGET_LANGS)
        self.target.setEditable(False)
        idx = self.target.findText(self.s.target_lang)
        self.target.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow(self._lab("set.target_lang"), self.target)

        self.src = QComboBox()
        for code in SRC_LANGS:
            self.src.addItem("", code)
        self.src.setCurrentIndex(max(0, self.src.findData(self.s.src_lang)))
        form.addRow(self._lab("set.src_lang"), self.src)

        self.max_chars = QSpinBox()
        self.max_chars.setRange(0, 120)
        self.max_chars.setValue(self.s.max_chars)
        form.addRow(self._lab("set.max_chars"), self.max_chars)

        self.merge = QCheckBox()
        self.merge.setChecked(self.s.merge_sentences)
        self._labels.append((self.merge, "set.merge"))
        form.addRow("", self.merge)

        self.dl_video = QCheckBox()
        self.dl_video.setChecked(self.s.download_video)
        self._labels.append((self.dl_video, "set.download_video"))
        form.addRow("", self.dl_video)

        self.quality = QComboBox()
        for label, code in QUALITY:
            self.quality.addItem(label, code)
        self.quality.setCurrentIndex(max(0, self.quality.findData(self.s.video_format)))
        form.addRow(self._lab("set.quality"), self.quality)

        form.addRow("", self._hint("set.output_hint"))
        return page

    def _pick_workdir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr("set.workdir"), self.workdir.text())
        if d:
            self.workdir.setText(d)

    def _preview_language(self) -> None:
        code = self.ui_lang.currentData()
        set_language(code if code else "zh")
        self.retranslate()

    # ------------------------------------------------------------ 引擎
    def _tab_engine(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 16, 4, 4)
        lay.setSpacing(12)

        row = QHBoxLayout()
        self.backend = QComboBox()
        self.backend.addItem("", "ollama")
        self.backend.addItem("", "api")
        self.backend.setCurrentIndex(0 if self.s.backend == "ollama" else 1)
        self.backend.currentIndexChanged.connect(self._sync_backend_page)
        row.addWidget(self._lab("set.backend"))
        row.addWidget(self.backend, 1)
        auto = self._btn("set.autodetect")
        auto.clicked.connect(self._autodetect)
        row.addWidget(auto)
        lay.addLayout(row)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_ollama())
        self.stack.addWidget(self._page_api())
        lay.addWidget(self.stack, 1)

        self.engine_status = QLabel()
        self.engine_status.setObjectName("Hint")
        self.engine_status.setWordWrap(True)
        lay.addWidget(self.engine_status)
        return page

    def _page_ollama(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(0, 8, 0, 0)
        form.setSpacing(14)

        self.ollama_url = QLineEdit(self.s.ollama_url)
        self.ollama_url.setPlaceholderText("http://127.0.0.1:11434")
        form.addRow(self._lab("set.service_url"), self.ollama_url)

        self.ollama_model = QComboBox()
        self.ollama_model.setEditable(True)
        if self.s.ollama_model:
            self.ollama_model.addItem(self.s.ollama_model)
        self.ollama_model.setCurrentText(self.s.ollama_model)

        refresh = self._btn("set.refresh_models")
        refresh.clicked.connect(self._refresh_ollama)
        form.addRow(self._lab("set.model"), _row([self.ollama_model, refresh]))

        test = self._btn("set.test_translate")
        test.clicked.connect(self._test_engine)
        form.addRow("", _row([test]))
        return page

    def _page_api(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(0, 8, 0, 0)
        form.setSpacing(14)

        self.api_base = QLineEdit(self.s.api_base)
        self.api_base.setPlaceholderText("https://api.deepseek.com/v1")
        form.addRow(self._lab("set.base_url"), self.api_base)

        self.api_key = QLineEdit(self.s.api_key)
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("sk-…")
        form.addRow(self._lab("set.api_key"), self.api_key)

        self.api_model = QComboBox()
        self.api_model.setEditable(True)
        if self.s.api_model:
            self.api_model.addItem(self.s.api_model)
        self.api_model.setCurrentText(self.s.api_model)
        form.addRow(self._lab("set.model"), self.api_model)

        btns = QHBoxLayout()
        fetch = self._btn("set.fetch_models")
        fetch.clicked.connect(self._refresh_api)
        test = self._btn("set.test_translate")
        test.clicked.connect(self._test_engine)
        btns.addWidget(fetch)
        btns.addWidget(test)
        btns.addStretch(1)
        form.addRow("", btns)

        form.addRow("", self._hint("set.api_hint"))
        return page

    def _sync_backend_page(self) -> None:
        self.stack.setCurrentIndex(0 if self.backend.currentData() == "ollama" else 1)

    def _refresh_ollama(self) -> None:
        url = self.ollama_url.text().strip()
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            models = backends.probe_ollama(url)
        finally:
            QGuiApplication.restoreOverrideCursor()
        if not models:
            QMessageBox.warning(self, tr("set.conn_failed"),
                                tr("set.conn_failed_body", url=url))
            return
        current = self.ollama_model.currentText()
        self.ollama_model.clear()
        self.ollama_model.addItems(models)
        self.ollama_model.setCurrentText(current if current in models
                                         else backends.pick_model(models))
        self.engine_status.setText(tr("set.found_models", n=len(models)))

    def _refresh_api(self) -> None:
        base = self.api_base.text().strip()
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            models = backends.probe_openai(base, self.api_key.text().strip(),
                                           self.proxy.text().strip())
        finally:
            QGuiApplication.restoreOverrideCursor()
        if not models:
            QMessageBox.warning(self, tr("set.fetch_failed"), tr("set.fetch_failed_body"))
            return
        current = self.api_model.currentText()
        self.api_model.clear()
        self.api_model.addItems(models)
        self.api_model.setCurrentText(current or models[0])
        self.engine_status.setText(tr("set.found_models", n=len(models)))

    def _autodetect(self) -> None:
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            found = backends.autodetect(self.s)
        finally:
            QGuiApplication.restoreOverrideCursor()
        if not found:
            QMessageBox.information(self, tr("set.nothing_found"),
                                    tr("set.nothing_found_body"))
            return
        best = found[0]
        if best.kind == "ollama":
            self.backend.setCurrentIndex(0)
            self.ollama_url.setText(best.base)
            self.ollama_model.clear()
            self.ollama_model.addItems(best.models)
            self.ollama_model.setCurrentText(best.best_model)
        else:
            self.backend.setCurrentIndex(1)
            self.api_base.setText(best.base)
            self.api_model.clear()
            self.api_model.addItems(best.models)
            self.api_model.setCurrentText(best.best_model)
        names = "、".join(f"{d.name}({len(d.models)})" for d in found)
        self.engine_status.setText(tr("set.detected", names=names))

    def _test_engine(self) -> None:
        tmp = self._collect()
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok, msg = backends.build_translator(tmp).test()
        except Exception as exc:  # noqa: BLE001
            ok, msg = False, str(exc)
        finally:
            QGuiApplication.restoreOverrideCursor()
        self.engine_status.setText(tr("set.test_ok" if ok else "set.test_fail", msg=msg))
        self.engine_status.setStyleSheet(f"color:{theme.OK if ok else theme.ERR};")

    # ------------------------------------------------------------ 工具
    def _tab_tools(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 16, 4, 4)
        lay.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(12)

        self.ytdlp = QLineEdit(self.s.ytdlp_path)
        self._placeholders.append((self.ytdlp, "set.ytdlp_hint"))
        det = self._btn("common.detect")
        det.clicked.connect(self._detect_tools)
        dl = self._btn("set.download_update")
        dl.clicked.connect(self._download_ytdlp)
        form.addRow(self._lab("set.ytdlp"), _row([self.ytdlp, det, dl]))

        self.ffmpeg = QLineEdit(self.s.ffmpeg_path)
        self._placeholders.append((self.ffmpeg, "set.ffmpeg_hint"))
        det2 = self._btn("common.detect")
        det2.clicked.connect(self._detect_tools)
        form.addRow(self._lab("set.ffmpeg"), _row([self.ffmpeg, det2]))
        lay.addLayout(form)

        self.tool_status = QLabel()
        self.tool_status.setObjectName("Hint")
        self.tool_status.setWordWrap(True)
        lay.addWidget(self.tool_status)

        lay.addWidget(divider())
        asr_title = self._lab("set.asr_title")
        asr_title.setStyleSheet("font-weight:600;")
        lay.addWidget(asr_title)

        self.asr_enabled = QCheckBox()
        self.asr_enabled.setChecked(self.s.asr_enabled)
        self._labels.append((self.asr_enabled, "set.asr_enable"))
        lay.addWidget(self.asr_enabled)

        asr_row = QHBoxLayout()
        asr_row.addWidget(self._lab("set.asr_model"))
        self.asr_model = QComboBox()
        self.asr_model.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self.asr_model.setEditable(False)
        asr_idx = self.asr_model.findText(self.s.asr_model)
        self.asr_model.setCurrentIndex(asr_idx if asr_idx >= 0 else 2)
        asr_row.addWidget(self.asr_model, 1)
        lay.addLayout(asr_row)

        lay.addWidget(self._hint("set.asr_hint"))
        lay.addStretch(1)
        return page

    def _detect_tools(self) -> None:
        tmp = self._collect()
        info = toolenv.probe_tools(tmp)
        lines = []
        for key in ("ytdlp", "ffmpeg"):
            d = info[key]
            if d["ok"]:
                lines.append(tr("set.tool_ok", name=key, ver=d["version"]))
                if key == "ytdlp" and not self.ytdlp.text().strip():
                    self.ytdlp.setText(d["path"])
                if key == "ffmpeg" and not self.ffmpeg.text().strip():
                    self.ffmpeg.setText(d["path"])
            else:
                lines.append(tr("set.tool_missing", name=key))
        self.tool_status.setText("\n".join(lines))
        self.tool_status.setStyleSheet(
            f"color:{theme.OK if info['ytdlp']['ok'] else theme.WARN};")

    def _download_ytdlp(self) -> None:
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            path = toolenv.download_ytdlp(self.proxy.text().strip(),
                                          progress=lambda p, m: self.tool_status.setText(m))
            self.ytdlp.setText(str(path))
            self.tool_status.setText(tr("set.installed_to", path=path))
            self.tool_status.setStyleSheet(f"color:{theme.OK};")
        except Exception as exc:  # noqa: BLE001
            self.tool_status.setText(tr("set.download_failed", err=exc))
            self.tool_status.setStyleSheet(f"color:{theme.ERR};")
        finally:
            QGuiApplication.restoreOverrideCursor()

    # ------------------------------------------------------------ 下载
    def _tab_download(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 16, 4, 4)
        lay.setSpacing(12)

        title = self._lab("set.cookies_title")
        title.setStyleSheet("font-weight:600;")
        lay.addWidget(title)
        lay.addWidget(self._hint("set.cookies_hint"))

        form = QFormLayout()
        form.setSpacing(12)

        self.cookies_browser = QComboBox()
        self.cookies_browser.addItem("", "")
        for b in COOKIE_BROWSERS:
            self.cookies_browser.addItem(b.capitalize(), b)
        self.cookies_browser.setCurrentIndex(
            max(0, self.cookies_browser.findData(self.s.cookies_browser)))
        form.addRow(self._lab("set.cookies_browser"), self.cookies_browser)

        self.cookies_file = QLineEdit(self.s.cookies_file)
        self.cookies_file.setPlaceholderText("cookies.txt")
        pick = self._btn("common.browse")
        pick.clicked.connect(self._pick_cookies)
        form.addRow(self._lab("set.cookies_file"), _row([self.cookies_file, pick]))

        self.impersonate = QComboBox()
        self.impersonate.addItem("", "")
        for b in IMPERSONATE:
            self.impersonate.addItem(b.capitalize(), b)
        self.impersonate.setCurrentIndex(
            max(0, self.impersonate.findData(self.s.impersonate)))
        form.addRow(self._lab("set.impersonate"), self.impersonate)
        lay.addLayout(form)
        lay.addWidget(self._hint("set.impersonate_hint"))

        self.extra_args = QLineEdit(self.s.extra_args)
        self._placeholders.append((self.extra_args, "set.extra_args_ph"))
        form2 = QFormLayout()
        form2.setSpacing(12)
        form2.addRow(self._lab("set.extra_args"), self.extra_args)
        lay.addLayout(form2)
        lay.addWidget(self._hint("set.extra_args_hint"))

        lay.addWidget(divider())
        preset_lbl = self._lab("set.preset_title")
        preset_lbl.setStyleSheet("font-weight:600;")
        lay.addWidget(preset_lbl)

        preset_row = QHBoxLayout()
        bot = self._btn("set.preset_botguard")
        bot.clicked.connect(self._preset_botguard)
        fast = self._btn("set.preset_fast")
        fast.clicked.connect(self._preset_fast)
        preset_row.addWidget(bot)
        preset_row.addWidget(fast)
        preset_row.addStretch(1)
        lay.addLayout(preset_row)
        lay.addStretch(1)
        return page

    def _pick_cookies(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "cookies.txt", "",
                                              "cookies.txt (*.txt);;所有文件 (*)")
        if path:
            self.cookies_file.setText(path)

    def _preset_botguard(self) -> None:
        # Chrome/Edge 的 Cookie 解不开，默认建议 Firefox；伪装对 YouTube 有害，清空
        idx = self.cookies_browser.findData("firefox")
        if idx >= 0:
            self.cookies_browser.setCurrentIndex(idx)
        self.impersonate.setCurrentIndex(0)

    def _preset_fast(self) -> None:
        self.dl_video.setChecked(False)

    # ------------------------------------------------------------ 语言
    def retranslate(self) -> None:
        self.setWindowTitle(tr("set.title"))
        for widget, key in self._labels:
            widget.setText(tr(key))
        for widget, key in self._buttons:
            widget.setText(tr(key))
        for widget, key in self._placeholders:
            widget.setPlaceholderText(tr(key))
        for widget, key in self._hints:
            widget.setText(tr(key))

        self.tabs.setTabText(0, tr("set.tab_general"))
        self.tabs.setTabText(1, tr("set.tab_engine"))
        self.tabs.setTabText(2, tr("set.tab_tools"))
        self.tabs.setTabText(3, tr("set.tab_download"))

        self.ui_lang.setItemText(0, tr("set.lang_auto"))
        for i, (code, label) in enumerate(LANGUAGES, start=1):
            # 标出完成度，半成品语言一眼可见
            self.ui_lang.setItemText(i, f"{label}  {coverage(code)}%")

        self.backend.setItemText(0, tr("set.backend_ollama"))
        self.backend.setItemText(1, tr("set.backend_api"))

        en = get_language() == "en"
        for i, code in enumerate(SRC_LANGS):
            zh_label, en_label = SRC_LANG_LABELS.get(code, (code, code))
            self.src.setItemText(i, f"{en_label if en else zh_label} ({code})")

        self.cookies_browser.setItemText(0, tr("set.cookies_none"))
        self.impersonate.setItemText(0, tr("set.cookies_none"))

        for i, (_label, code) in enumerate(QUALITY):
            if code == "best":
                self.quality.setItemText(i, "Best" if en else "最高")

        self.max_chars.setSpecialValueText(tr("set.auto"))

    # ------------------------------------------------------------ 保存
    def _collect(self) -> Settings:
        s = replace(self.s)
        s.ui_lang = self.ui_lang.currentData() or ""
        s.workdir = self.workdir.text().strip() or self.s.workdir
        s.proxy = self.proxy.text().strip()
        s.target_lang = self.target.currentText().strip() or "简体中文"
        s.src_lang = self.src.currentData() or "en"
        s.max_chars = self.max_chars.value()
        s.merge_sentences = self.merge.isChecked()
        s.download_video = self.dl_video.isChecked()
        s.video_format = self.quality.currentData() or "1080"

        s.backend = self.backend.currentData() or "ollama"
        s.ollama_url = self.ollama_url.text().strip() or "http://127.0.0.1:11434"
        s.ollama_model = self.ollama_model.currentText().strip()
        s.api_base = self.api_base.text().strip()
        s.api_key = self.api_key.text().strip()
        s.api_model = self.api_model.currentText().strip()

        s.ytdlp_path = self.ytdlp.text().strip()
        s.ffmpeg_path = self.ffmpeg.text().strip()
        s.asr_enabled = self.asr_enabled.isChecked()
        s.asr_model = self.asr_model.currentText()

        s.cookies_browser = self.cookies_browser.currentData() or ""
        s.cookies_file = self.cookies_file.text().strip()
        s.impersonate = self.impersonate.currentData() or ""
        s.extra_args = self.extra_args.text().strip()
        return s

    def _save(self) -> None:
        self.s = self._collect()
        self.accept()

    def result_settings(self) -> Settings:
        return self.s



