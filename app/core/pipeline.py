"""任务流水线：抓取 / 抽字幕 / 翻译 / 落盘。

刻意不依赖 Qt，方便命令行直接跑和单元测试；UI 只是套一层线程。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..config import Settings
from ..i18n import tr
from . import subs
from .backends import build_translator
from .env import ensure_ytdlp, find_ffmpeg

Status = Callable[[str], None]
Prog = Callable[[float], None]
Log = Callable[[str], None]


class Cancelled(Exception):
    pass


class PipelineError(Exception):
    pass


@dataclass
class JobSpec:
    source: str
    is_url: bool
    target_lang: str = "简体中文"
    download_video: bool = True
    video_format: str = "1080"


@dataclass
class JobResult:
    title: str = ""
    subtitle_files: list[Path] = field(default_factory=list)
    video_path: Optional[Path] = None
    cue_count: int = 0
    seconds: float = 0.0


FORMAT_MAP = {
    "best": "bv*+ba/b",
    "2160": "bv*[height<=2160]+ba/b[height<=2160]/b",
    "1080": "bv*[height<=1080]+ba/b[height<=1080]/b",
    "720": "bv*[height<=720]+ba/b[height<=720]/b",
    "480": "bv*[height<=480]+ba/b[height<=480]/b",
}

ILLEGAL = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def sanitize(name: str, limit: int = 120) -> str:
    name = ILLEGAL.sub("_", name).strip().strip(".")
    return (name or "video")[:limit]


def _no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


class Pipeline:
    def __init__(self, settings: Settings,
                 on_status: Status = lambda s: None,
                 on_progress: Prog = lambda p: None,
                 on_log: Log = lambda s: None):
        self.s = settings
        self.status = on_status
        self.progress = on_progress
        self.log = on_log
        self._cancel = threading.Event()
        self._proc: Optional[subprocess.Popen] = None

    # ------------------------------------------------------------- 控制
    def cancel(self) -> None:
        self._cancel.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass

    def _check(self) -> None:
        if self._cancel.is_set():
            raise Cancelled()

    # --------------------------------------------------------- 子进程
    def _base_env(self) -> dict:
        env = os.environ.copy()
        ff = find_ffmpeg(self.s)
        if ff:
            env["PATH"] = str(ff.parent) + os.pathsep + env.get("PATH", "")
        return env

    def _run(self, cmd: list[str], cwd: Optional[Path] = None,
             capture: bool = True, on_line: Optional[Callable[[str], None]] = None) -> str:
        self._check()
        self.log("$ " + " ".join(str(c) for c in cmd[:8]) + (" …" if len(cmd) > 8 else ""))

        if capture:
            self._proc = subprocess.Popen(
                cmd, cwd=str(cwd) if cwd else None, env=self._base_env(),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                bufsize=1, creationflags=_no_window(),
            )
            lines: list[str] = []
            assert self._proc.stdout is not None
            for line in self._proc.stdout:
                if self._cancel.is_set():
                    self._proc.kill()
                    raise Cancelled()
                line = line.rstrip()
                if not line:
                    continue
                lines.append(line)
                if on_line:
                    on_line(line)
            self._proc.wait()
            return "\n".join(lines)

        self._proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=self._base_env(),
                                    capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", creationflags=_no_window())
        return (self._proc.stdout or "") + (self._proc.stderr or "")

    # --------------------------------------------------------- 主流程
    def run(self, spec: JobSpec) -> JobResult:
        t0 = time.time()
        self._check()
        self.status(tr("st.tools"))
        try:
            ytdlp = ensure_ytdlp(self.s, self.log, lambda p, m: self.log(m))
        except Exception as exc:  # noqa: BLE001
            raise PipelineError(tr("err.ytdlp_missing", err=exc)) from exc
        if not find_ffmpeg(self.s):
            self.log(tr("st.no_ffmpeg"))

        result = JobResult()
        if spec.is_url:
            self._run_url(spec, ytdlp, result)
        else:
            self._run_local(spec, result)

        result.seconds = time.time() - t0
        return result

    # --------------------------------------------------------- 远程
    def _meta(self, ytdlp: Path, url: str) -> str:
        """取标题。失败就退化成链接里的 id。"""
        try:
            out = self._run(self._common(ytdlp) + ["--skip-download", "--print", "%(title)s", url])
        except (subprocess.SubprocessError, OSError) as exc:
            self.log(tr("st.meta_fail", err=exc))
            out = ""
        clean = [
            ln.strip() for ln in out.splitlines()
            if ln.strip() and not ln.startswith(("[", "ERROR", "WARNING", "  "))
        ]
        if clean:
            return clean[-1]
        m = re.search(r"[?&]v=([\w-]{6,})", url) or re.search(r"/([\w-]{8,})(?:$|[?&])", url)
        return m.group(1) if m else "video"

    def _common(self, ytdlp: Path) -> list[str]:
        cmd = [str(ytdlp), "--no-warnings", "--no-playlist", "--newline",
               "--retries", "5", "--socket-timeout", "25"]
        if self.s.proxy:
            cmd += ["--proxy", self.s.proxy]
        if self.s.cookies_browser:
            cmd += ["--cookies-from-browser", self.s.cookies_browser]
        elif self.s.cookies_file:
            cmd += ["--cookies", self.s.cookies_file]
        if self.s.impersonate:
            cmd += ["--impersonate", self.s.impersonate]
        if self.s.extra_args:
            import shlex
            try:
                cmd += shlex.split(self.s.extra_args)
            except ValueError as exc:
                self.log(f"额外参数解析失败：{exc}")
        return cmd

    def _run_url(self, spec: JobSpec, ytdlp: Path, result: JobResult) -> None:
        url = spec.source.strip()
        workdir = self.s.workdir_path()
        tmp = Path(tempfile.mkdtemp(prefix="ss-job-"))

        self.status(tr("st.meta"))
        title = sanitize(self._meta(ytdlp, url))
        base = workdir / title
        result.title = title
        self.log(tr("st.title", title=title))

        template = str(tmp / "%(id)s.%(ext)s")
        got_sub: Optional[Path] = None

        self.status(tr("st.subs"))
        self.progress(0.08)
        sub_cmd = self._common(ytdlp) + [
            "--skip-download", "--write-subs", "--write-auto-subs",
            "--sub-langs", f"{self.s.src_lang},{self.s.src_lang}-orig",
            "--sub-format", "vtt", "-o", template, url,
        ]
        if find_ffmpeg(self.s):
            sub_cmd += ["--convert-subs", "vtt"]
        sub_out = self._run(sub_cmd, on_line=lambda ln: self.log(ln)
                            if "subtitle" in ln.lower() else None)
        self._check_output(sub_out)

        found = sorted(tmp.glob("*.vtt"), key=lambda p: p.stat().st_size, reverse=True)
        if found:
            got_sub = found[0]
            self.log(tr("st.sub_file", name=got_sub.name,
                        kb=max(1, got_sub.stat().st_size // 1024)))

        self.progress(0.25)

        if spec.download_video:
            self.status(tr("st.video"))
            fmt = FORMAT_MAP.get(spec.video_format, FORMAT_MAP["1080"])
            if not find_ffmpeg(self.s):
                fmt = "b[ext=mp4]/b"
            vid_cmd = self._common(ytdlp) + [
                "-f", fmt, "--merge-output-format", "mp4", "-o", template, url,
            ]

            def on_dl(line: str) -> None:
                m = re.search(r"\[download\]\s+([\d.]+)%", line)
                if m:
                    self.progress(0.25 + 0.35 * float(m.group(1)) / 100.0)

            vid_out = self._run(vid_cmd, on_line=on_dl)
            self._check_output(vid_out)
            media = [
                p for p in tmp.iterdir()
                if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov", ".flv")
            ]
            if media:
                biggest = max(media, key=lambda p: p.stat().st_size)
                target = workdir / f"{title}{biggest.suffix}"
                shutil.move(str(biggest), str(target))
                result.video_path = target
                self.log(tr("st.video_file", name=target.name,
                            mb=max(1, target.stat().st_size // 1024 // 1024)))

        self.progress(0.62)

        if got_sub is None:
            if result.video_path:
                self.log(tr("st.no_subs_try_asr"))
                got_sub = self._asr(result.video_path, tmp / "asr.vtt")
            if got_sub is None:
                raise PipelineError(tr("err.no_subs"))

        files, count = self._translate_file(got_sub, base)
        result.subtitle_files = files
        result.cue_count = count
        self.progress(1.0)
        self.status(tr("st.done"))

    def _check_output(self, output: str) -> None:
        """把 yt-dlp 常见失败翻译成可执行的提示。"""
        text = (output or "").lower()
        if ("sign in to confirm" in text or "not a bot" in text
                or "登录以确认" in text or "confirm you" in text):
            raise PipelineError(tr("err.bot_check"))
        if "failed to decrypt with dpapi" in text or "could not copy chrome cookie" in text:
            raise PipelineError(tr("err.cookies_dpapi"))
        if "curl_cffi" in text or ("impersonate" in text and "not supported" in text):
            raise PipelineError(tr("err.impersonate_missing"))
        if "no video formats found" in text:
            raise PipelineError(tr("err.no_formats"))

    # --------------------------------------------------------- 本地
    def _run_local(self, spec: JobSpec, result: JobResult) -> None:
        video = Path(spec.source).expanduser()
        if not video.is_file():
            raise PipelineError(tr("err.no_file", path=video))

        result.title = sanitize(video.stem)
        base = video.with_suffix("")
        ffmpeg = find_ffmpeg(self.s)
        if not ffmpeg:
            raise PipelineError(tr("err.need_ffmpeg"))

        self.status(tr("st.probe"))
        self.progress(0.05)
        sub_path = self._extract_embedded(ffmpeg, video)
        if sub_path:
            self.log(f"字幕：{sub_path.name}")
        else:
            self.log(tr("st.no_track"))
            self.progress(0.15)
            sub_path = self._asr(video, None)
            if sub_path is None:
                raise PipelineError(tr("err.no_embedded"))

        self.progress(0.6)
        files, count = self._translate_file(sub_path, base, outdir=video.parent)
        result.subtitle_files = files
        result.cue_count = count
        result.video_path = video
        self.progress(1.0)
        self.status(tr("st.done"))

    def _probe_subs(self, ffmpeg: Path, video: Path) -> list[dict]:
        ffprobe = ffmpeg.with_name("ffprobe.exe" if sys.platform.startswith("win") else "ffprobe")
        if not ffprobe.is_file():
            found = shutil.which("ffprobe")
            if not found:
                return []
            ffprobe = Path(found)
        try:
            out = subprocess.run(
                [str(ffprobe), "-v", "quiet", "-print_format", "json",
                 "-show_streams", "-select_streams", "s", str(video)],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace", creationflags=_no_window())
            data = json.loads(out.stdout or "{}")
            return data.get("streams", []) or []
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return []

    def _extract_embedded(self, ffmpeg: Path, video: Path) -> Optional[Path]:
        streams = self._probe_subs(ffmpeg, video)
        text_codecs = {"subrip", "srt", "ass", "ssa", "mov_text", "webvtt", "text"}
        usable = [s for s in streams if (s.get("codec_name") or "") in text_codecs]
        if not usable:
            return []
        stream = usable[0]
        idx = stream.get("index", 0)
        tmp = Path(tempfile.mkdtemp(prefix="ss-sub-")) / f"{video.stem}.vtt"
        self.status(tr("st.extract"))
        try:
            self._run([str(ffmpeg), "-y", "-v", "error", "-i", str(video),
                       "-map", f"0:{idx}", "-c:s", "webvtt", str(tmp)])
        except (subprocess.SubprocessError, OSError) as exc:
            self.log(tr("st.extract_fail", err=exc))
            return []
        return tmp if tmp.is_file() and tmp.stat().st_size > 0 else []

    # --------------------------------------------------------- ASR
    def _asr(self, video: Path, out_path: Optional[Path]) -> Optional[Path]:
        if not self.s.asr_enabled:
            return None
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError:
            self.log(tr("st.asr_missing"))
            return None

        self.status(tr("st.asr"))
        self.log(tr("st.asr_model", model=self.s.asr_model))
        model = WhisperModel(self.s.asr_model, device="auto", compute_type="auto")
        segments, info = model.transcribe(str(video), vad_filter=True)
        self.log(tr("st.asr_lang", lang=info.language, prob=info.language_probability))

        cues: list[dict] = []
        for seg in segments:
            self._check()
            cues.append({
                "start": subs.sec_to_ts(seg.start),
                "end": subs.sec_to_ts(seg.end),
                "text": seg.text.strip(),
            })
        if not cues:
            return None

        target = out_path or (Path(tempfile.mkdtemp(prefix="ss-asr-")) / f"{video.stem}.vtt")
        subs.write_vtt(cues, target)
        self.log(tr("st.asr_done", n=len(cues)))
        return target

    # --------------------------------------------------------- 翻译
    def _translate_file(self, sub_path: Path, base: Path,
                        outdir: Optional[Path] = None) -> tuple[list[Path], int]:
        self.status(tr("st.reading"))
        cues = subs.parse_subtitle(sub_path)
        if not cues:
            raise PipelineError(tr("err.empty_subs"))

        if self.s.merge_sentences:
            blocks = subs.merge_sentences(cues)
        else:
            blocks = cues
        self.log(tr("st.merge_stats", cues=len(cues), blocks=len(blocks)))

        translator = build_translator(self.s)
        ok, detail = translator.test()
        if not ok:
            raise PipelineError(tr("err.engine_down", err=detail))
        max_chars = self.s.max_chars or subs.default_max_chars(self.s.target_lang)

        out_cues: list[dict] = []
        total = len(blocks)
        started = time.time()
        for i, b in enumerate(blocks, 1):
            self._check()
            try:
                zh = translator.translate(b["text"], self.s.target_lang)
            except Exception as exc:  # noqa: BLE001
                self.log(tr("st.translate_fail", i=i, err=exc))
                zh = b["text"]
            out_cues.extend(subs.lay_out(b, zh, max_chars))

            if i == 1 or i % 5 == 0 or i == total:
                elapsed = time.time() - started
                rate = i / elapsed if elapsed else 0
                eta = (total - i) / rate if rate else 0
                self.progress(0.62 + 0.38 * i / total)
                self.status(tr("st.translate", i=i, n=total, eta=f"{eta:.0f}"))

        outdir = outdir or base.parent
        outdir.mkdir(parents=True, exist_ok=True)
        stem = base.with_suffix("") if base.suffix else base
        full_vtt = Path(str(stem) + f".{self.s.target_lang}.vtt")
        full_srt = Path(str(stem) + f".{self.s.target_lang}.srt")
        subs.write_vtt(out_cues, full_vtt, note=f"translated by Subtitle Studio")
        subs.write_srt(out_cues, full_srt)

        self.log(tr("st.output", name=full_srt.name))
        return [full_vtt, full_srt], len(out_cues)




