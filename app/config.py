"""应用配置：读写与默认值。"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_NAME = "Subtitle Studio"
APP_ID = "SubtitleStudio"


def app_data_dir() -> Path:
    """跨平台的应用数据目录。"""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home())
        p = Path(base) / APP_ID
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / APP_ID
    else:
        p = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / APP_ID
    p.mkdir(parents=True, exist_ok=True)
    return p


def default_workdir() -> str:
    home = Path.home()
    for name in ("Videos", "Movies"):
        cand = home / name
        if cand.is_dir():
            return str(cand / APP_ID)
    return str(home / APP_ID)


CONFIG_PATH = app_data_dir() / "config.json"

# 目标语言固定选项（界面用下拉框，不允许手输）。
# 想加语言改这里一处即可，设置页和主界面都读取这个列表。
TARGET_LANGS = [
    "简体中文",
    "繁体中文",
    "英文",
    "日语",
    "韩语",
    "法语",
    "德语",
    "西班牙语",
    "俄语",
    "葡萄牙语",
    "意大利语",
    "阿拉伯语",
]


@dataclass
class Settings:
    # —— 常规 ——
    workdir: str = ""
    proxy: str = ""
    ui_lang: str = ""                # "" = 跟随系统；zh / en
    target_lang: str = "简体中文"
    src_lang: str = "en"
    merge_sentences: bool = True
    max_chars: int = 0
    download_video: bool = True
    video_format: str = "1080"

    # —— 下载（yt-dlp 传参）——
    cookies_browser: str = ""        # chrome / edge / firefox / …；空 = 不用
    cookies_file: str = ""
    impersonate: str = ""            # chrome / safari / edge / firefox；空 = 不用
    extra_args: str = ""             # 原样追加给 yt-dlp

    # —— 引擎 ——
    backend: str = "ollama"          # ollama | api
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    api_base: str = ""
    api_key: str = ""
    api_model: str = ""
    api_style: str = "openai"        # openai | raw

    # —— 工具 ——
    ytdlp_path: str = ""
    ffmpeg_path: str = ""

    # —— 语音识别（本地无字幕轨时可选）——
    asr_enabled: bool = False
    asr_model: str = "small"

    def __post_init__(self) -> None:
        if not self.workdir:
            self.workdir = default_workdir()

    # ------------------------------------------------------------------ IO
    @classmethod
    def load(cls) -> "Settings":
        if CONFIG_PATH.exists():
            try:
                raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                known = {f.name for f in fields(cls)}
                return cls(**{k: v for k, v in raw.items() if k in known})
            except (OSError, ValueError, TypeError):
                pass
        return cls()

    def save(self) -> None:
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(
                json.dumps(asdict(self), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    # -------------------------------------------------------------- helpers
    def workdir_path(self) -> Path:
        p = Path(self.workdir).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def backend_label(self) -> str:
        from .i18n import tr
        if self.backend == "ollama":
            return f"{tr('engine.ollama')} · {self.ollama_model or tr('engine.no_model')}"
        return f"{tr('engine.api')} · {self.api_model or tr('engine.no_model')}"
