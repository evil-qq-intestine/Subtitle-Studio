"""失败任务重试的集成测试（离屏，不需要显示器）。

做的事情：
  1. 建窗口，塞一个必定失败的任务（本地文件不存在）
  2. 等它失败，确认卡片变成「失败」且重试按钮出现
  3. 点重试，确认任务重新启动、状态回到「进行中」
  4. 再等它失败一次，确认可以反复重试
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core.pipeline import JobSpec  # noqa: E402
from app.i18n import setup_console  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def pump(app: QApplication, seconds: float) -> None:
    """跑事件循环，让工作线程的信号能送到主线程。"""
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)


def wait_state(app: QApplication, card, state: str, timeout: float = 15.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if card._state == state:
            return True
        time.sleep(0.02)
    return False


def main() -> int:
    setup_console()
    app = QApplication(sys.argv)
    window = MainWindow(Settings())

    spec = JobSpec(source=r"Z:\definitely\missing\file.mkv", is_url=False,
                   target_lang="简体中文", download_video=False)
    window._spawn(spec, title="missing.mkv", subtitle="queued")
    pump(app, 0.3)

    tid = next(iter(window.specs))
    card = window.cards[tid]

    if not wait_state(app, card, "err"):
        print("失败：任务没有进入错误状态", file=sys.stderr)
        return 1
    print(f"1) 任务失败 -> 状态={card._state}  重试按钮可见={card.retry_btn.isVisibleTo(card)}")
    if not card.retry_btn.isVisibleTo(card):
        print("失败：重试按钮没出现", file=sys.stderr)
        return 1

    first_msg = card.status_label.text()
    print(f"   错误信息: {first_msg.splitlines()[0][:40]}")

    # 点重试：任务会在毫秒级再次失败，所以这里断言「线程被重新注册」而不是状态
    window._retry_task(tid)
    relaunched = tid in window.tasks
    print(f"2) 点重试 -> 重新启动={relaunched}  进度已归零={card.bar.value() == 0}")
    if not relaunched:
        print("失败：重试没有启动新线程", file=sys.stderr)
        return 1

    if not wait_state(app, card, "err"):
        print("失败：重试后没有再次失败", file=sys.stderr)
        return 1
    print(f"3) 再次失败 -> 重试按钮可见={card.retry_btn.isVisibleTo(card)}")

    # 再试一次，确认可反复
    window._retry_task(tid)
    again = tid in window.tasks
    print(f"4) 二次重试 -> 重新启动={again}")
    if not again:
        print("失败：二次重试无效", file=sys.stderr)
        return 1

    wait_state(app, card, "err", timeout=10)
    print("OK：重试流程正常")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


