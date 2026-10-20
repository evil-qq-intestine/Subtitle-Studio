"""外部工具探测与自举（yt-dlp / ffmpeg）。"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from ..config import Settings, app_data_dir

Log = Callable[[str], None]
Progress = Callable[[float, str], None]


def is_windows() -> bool:
    return sys.platform.startswith("win")


def bin_dir() -> Path:
    p = app_data_dir() / "bin"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _exe(name: str) -> str:
    return f"{name}.exe" if is_windows() else name


YTDLP_URLS = {
    "win32": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
    "darwin": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos",
    "linux": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp",
}

FFMPEG_HINTS = [
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    "/usr/local/bin/ffmpeg",
    "/opt/homebrew/bin/ffmpeg",
    "/usr/bin/ffmpeg",
]


def _run_version(path: Path, flag: str = "--version") -> Optional[str]:
    try:
        out = subprocess.run(
            [str(path), flag], capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if out.returncode == 0:
            first = (out.stdout or out.stderr or "").strip().splitlines()
            return first[0][:120] if first else ""
    except (OSError, subprocess.SubprocessError):
        pass
    return None


# --------------------------------------------------------------------- yt-dlp

def find_ytdlp(settings: Settings) -> Optional[Path]:
    candidates: list[Path] = []
    if settings.ytdlp_path:
        candidates.append(Path(settings.ytdlp_path))
    found = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if found:
        candidates.append(Path(found))
    candidates.append(bin_dir() / _exe("yt-dlp"))
    for name in ("yt-dlp.exe", "yt-dlp"):
        candidates.append(Path(os.getcwd()) / name)
        candidates.append(Path(__file__).resolve().parents[2] / name)

    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


def download_ytdlp(proxy: str = "", progress: Optional[Progress] = None,
                   log: Optional[Log] = None) -> Path:
    url = YTDLP_URLS.get(sys.platform, YTDLP_URLS["linux"])
    dest = bin_dir() / _exe("yt-dlp")
    tmp = dest.with_suffix(dest.suffix + ".part")

    if log:
        log(f"下载 yt-dlp: {url}")

    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)

    req = urllib.request.Request(url, headers={"User-Agent": "SubtitleStudio/1.0"})
    with opener.open(req, timeout=60) as resp, open(tmp, "wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(256 * 1024)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(min(done / total, 1.0),
                         f"下载 yt-dlp {done // 1024 // 1024} / {total // 1024 // 1024} MB")

    tmp.replace(dest)
    if not is_windows():
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if log:
        log(f"yt-dlp 已安装到 {dest}")
    return dest


def ensure_ytdlp(settings: Settings, log: Optional[Log] = None,
                 progress: Optional[Progress] = None) -> Path:
    """有就用，没有就下。"""
    path = find_ytdlp(settings)
    if path:
        return path
    if log:
        log("未检测到 yt-dlp，开始自动下载…")
    return download_ytdlp(settings.proxy, progress, log)


# --------------------------------------------------------------------- ffmpeg

def find_ffmpeg(settings: Settings) -> Optional[Path]:
    if settings.ffmpeg_path and Path(settings.ffmpeg_path).is_file():
        return Path(settings.ffmpeg_path)
    found = shutil.which("ffmpeg")
    if found:
        return Path(found)
    for hint in FFMPEG_HINTS:
        if Path(hint).is_file():
            return Path(hint)
    return None


def probe_tools(settings: Settings) -> dict:
    """返回工具状态，供设置页 / 启动检查使用。"""
    yt = find_ytdlp(settings)
    ff = find_ffmpeg(settings)
    result = {
        "ytdlp": {"path": str(yt) if yt else "", "version": None, "ok": False},
        "ffmpeg": {"path": str(ff) if ff else "", "version": None, "ok": False},
    }
    if yt:
        ver = _run_version(yt, "--version")
        result["ytdlp"].update(version=ver, ok=bool(ver))
    if ff:
        ver = _run_version(ff, "-version")
        result["ffmpeg"].update(version=ver, ok=bool(ver))
    return result


def ffmpeg_dir(ffmpeg: Optional[Path]) -> Optional[str]:
    """yt-dlp 通过 PATH 找 ffmpeg，这里把它的目录塞进环境变量。"""
    return str(ffmpeg.parent) if ffmpeg else None


def find_ollama() -> Optional[Path]:
    """找 Ollama 可执行文件。找不到就返回 None。"""
    found = shutil.which("ollama") or shutil.which("ollama.exe")
    if found:
        return Path(found)

    cands: list[Path] = []
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        cands.append(Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe")
    cands += [
        Path(r"C:\Program Files\Ollama\ollama.exe"),
        Path("/usr/local/bin/ollama"),
        Path("/usr/bin/ollama"),
        Path("/opt/homebrew/bin/ollama"),
        Path("/Applications/Ollama.app/Contents/Resources/ollama"),
    ]
    for c in cands:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


def detect_local_proxy() -> str:
    """扫一下本机常见的代理端口，省得用户第一次手动填。"""
    import socket

    for port in (7897, 7890, 10809, 10808, 1080, 2080):
        sock = socket.socket()
        sock.settimeout(0.15)
        try:
            sock.connect(("127.0.0.1", port))
            return f"http://127.0.0.1:{port}"
        except OSError:
            continue
        finally:
            sock.close()
    return ""
