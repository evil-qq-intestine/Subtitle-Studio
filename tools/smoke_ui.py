"""界面冒烟测试：不需要显示器，把主窗口和设置页都建一遍。

CI 里跑这个能挡住「导入错名字 / 布局里引用了不存在的控件 / 语言表缺键崩掉」这类问题，
比只做 compileall 有用得多。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.config import Settings  # noqa: E402
from app.i18n import LANGUAGES, get_language, set_language, setup_console  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.settings import SettingsDialog  # noqa: E402


def main() -> int:
    setup_console()
    app = QApplication(sys.argv)  # noqa: F841

    original = get_language()
    window = MainWindow(Settings())
    dialog = SettingsDialog(Settings())

    for code, _name in LANGUAGES:
        set_language(code)
        window.retranslate()
        dialog.retranslate()

        # 关键控件都该有文字，空字符串说明键没对上
        checks = {
            "go_btn": window.go_btn.text(),
            "task_title": window.task_title.text(),
            "merge": window.chk_merge.text(),
            "gear": window.gear_btn.text(),
            "tabs": dialog.tabs.tabText(0),
            "save": dialog.save_btn.text(),
        }
        empty = [k for k, v in checks.items() if not v.strip()]
        if empty:
            print(f"[{code}] 这些控件没有文字: {empty}", file=sys.stderr)
            return 1
        print(f"[{code}] {checks['go_btn']} / {checks['task_title']} / {checks['save']}")

    set_language(original)

    # 语言下拉框数量要和已加载的语言一致
    if dialog.ui_lang.count() != len(LANGUAGES) + 1:
        print("语言下拉框项数不对", file=sys.stderr)
        return 1

    print("UI smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


