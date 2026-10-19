"""自检：模块导入 + 工具探测 + 引擎探测。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.core import backends, env, pipeline, subs
from app.i18n import setup_console
from app.ui import main_window, settings as ui_settings, theme, widgets  # noqa: F401


def main() -> int:
    setup_console()
    s = Settings.load()
    print("配置路径:", Path.home())
    print("工作目录:", s.workdir)
    print("引擎:", s.backend_label)
    print("目标语言:", s.target_lang, "| 原语言:", s.src_lang)
    print("合并句子:", s.merge_sentences, "| 下载视频:", s.download_video)

    info = env.probe_tools(s)
    for key, val in info.items():
        status = "OK " if val["ok"] else "缺失"
        print(f"工具 {key:7s} {status} {(val['version'] or val['path'])[:60]}")

    models = backends.probe_ollama(s.ollama_url)
    print("Ollama:", "连不上" if models is None else f"{len(models)} 个模型 {models[:5]}")

    if models:
        s.ollama_model = backends.pick_model(models)
        tr = backends.build_translator(s)
        ok, msg = tr.test()
        print("翻译测试:", "通过" if ok else "失败", "|", msg)

    # 字幕解析/合并冒烟
    cues = [
        {"start": "00:00:01.000", "end": "00:00:02.000", "text": "here we are in front of the elephants"},
        {"start": "00:00:02.000", "end": "00:00:03.000", "text": "they have really"},
        {"start": "00:00:03.000", "end": "00:00:04.000", "text": "really long trunks"},
    ]
    blocks = subs.merge_sentences(cues)
    print("合并测试:", len(blocks), "块 ->", [b["text"] for b in blocks])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


