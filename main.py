#!/usr/bin/env python3
"""Subtitle Studio 入口。

GUI:
    python main.py

命令行（无需界面，便于批处理 / 排错）：
    python main.py --cli "https://www.youtube.com/watch?v=xxxx" --model hy-mt2
    python main.py --cli "D:\\movie.mkv" --target 简体中文
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def make_icon():
    """窗口/任务栏图标，和 .ico 用同一份绘制代码。"""
    from PySide6.QtGui import QIcon, QPixmap

    from app.ui.icon import paint_icon

    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(paint_icon(size)))
    return icon


def run_cli(args: argparse.Namespace) -> int:
    from app.config import Settings
    from app.core.pipeline import JobSpec, Pipeline, PipelineError

    settings = Settings.load()
    if args.workdir:
        settings.workdir = args.workdir
    if args.proxy:
        settings.proxy = args.proxy
    if args.model:
        settings.backend = "ollama"
        settings.ollama_model = args.model
    if args.ollama_url:
        settings.ollama_url = args.ollama_url
    if args.api_base:
        settings.backend = "api"
        settings.api_base = args.api_base
        settings.api_key = args.api_key or ""
        settings.api_model = args.api_model or ""
    if args.target:
        settings.target_lang = args.target
    if args.src:
        settings.src_lang = args.src
    settings.download_video = not args.no_video
    if args.quality:
        settings.video_format = args.quality
    if args.no_merge:
        settings.merge_sentences = False
    settings.save()

    source = args.cli
    spec = JobSpec(source=source, is_url=source.lower().startswith(("http://", "https://")),
                   target_lang=settings.target_lang,
                   download_video=settings.download_video,
                   video_format=settings.video_format)

    pipe = Pipeline(settings,
                    on_status=lambda m: print(f"[状态] {m}", flush=True),
                    on_progress=lambda p: None,
                    on_log=lambda m: print(f"       {m}", flush=True))
    try:
        result = pipe.run(spec)
    except PipelineError as exc:
        print(f"失败：{exc}", file=sys.stderr)
        return 1
    print("\n完成：")
    print(f"  标题   {result.title}")
    print(f"  字幕   {result.cue_count} 条 · {result.seconds:.1f}s")
    for f in result.subtitle_files:
        print(f"  输出   {f}")
    if result.video_path:
        print(f"  视频   {result.video_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Subtitle Studio")
    parser.add_argument("--cli", metavar="SOURCE", help="命令行模式：URL 或本地视频")
    parser.add_argument("--model", help="Ollama 模型名")
    parser.add_argument("--ollama-url")
    parser.add_argument("--api-base", help="OpenAI 兼容 Base URL")
    parser.add_argument("--api-key")
    parser.add_argument("--api-model")
    parser.add_argument("--target", help="目标语言")
    parser.add_argument("--src", help="原字幕语言，默认 en")
    parser.add_argument("--quality", help="1080 / 720 / best …")
    parser.add_argument("--workdir")
    parser.add_argument("--proxy")
    parser.add_argument("--no-video", action="store_true", help="只取字幕，不下载视频")
    parser.add_argument("--no-merge", action="store_true")
    args = parser.parse_args()

    if args.cli:
        return run_cli(args)

    from PySide6.QtWidgets import QApplication

    from app.config import APP_NAME, Settings
    from app.i18n import detect_language, set_language
    from app.ui.main_window import MainWindow
    from app.ui.theme import apply_theme

    settings = Settings.load()
    # 界面语言：设置里指定优先，否则跟随系统；SS_LANG 可强制（截图/调试用）
    set_language(os.environ.get("SS_LANG") or settings.ui_lang or detect_language())

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setWindowIcon(make_icon())
    apply_theme(app)

    window = MainWindow(settings)
    window.show()
    window.start_bootstrap()

    # 开发辅助：SS_SHOT=<png> 时自动截窗口图后退出，便于视觉回归
    #   SS_MODE=url|local|settings 选择要截的界面
    shot = os.environ.get("SS_SHOT")
    if shot:
        from PySide6.QtCore import QTimer

        from app.ui.settings import SettingsDialog

        mode = os.environ.get("SS_MODE", "url")
        holder: dict = {}

        def _prepare() -> None:
            if mode == "local":
                window.seg.group.button(1).setChecked(True)
                window._switch_mode(1)
            elif mode == "settings":
                dlg = SettingsDialog(window.s, window)
                tab = os.environ.get("SS_TAB")
                if tab:
                    dlg.tabs.setCurrentIndex(int(tab))
                dlg.show()
                holder["dlg"] = dlg

        def _grab() -> None:
            target = holder.get("dlg") or window
            target.grab().save(shot)
            if os.environ.get("SS_HARD"):
                os._exit(0)      # 截图模式下不等后台线程收尾
            app.quit()

        QTimer.singleShot(1200, _prepare)
        QTimer.singleShot(int(os.environ.get("SS_SHOT_DELAY", "4200")), _grab)

        # 另一个开发辅助：SS_RUN=<URL> 自动发起一次任务，用来验证界面里的任务流
        auto = os.environ.get("SS_RUN")
        if auto:
            def _run() -> None:
                if os.environ.get("SS_NOVIDEO"):
                    window.chk_video.setChecked(False)
                window.url_edit.setText(auto)
                window._start_url()

            QTimer.singleShot(1500, _run)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
