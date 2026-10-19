"""字幕解析 / 句子合并 / 时间轴重排 / 输出。

这里的规则是从实测里定下来的，别随手改：

* YouTube 的 ASR 字幕按 2~5 秒切碎，碎片单独翻译会严重幻觉
  （"really really long trunks" -> "树干"、"他们的阴茎"），所以先合并成完整句子。
* 口语里的 "..." / "…" 是停顿，不是句末。用省略号断句会切出半截句子，必须排除。
"""
from __future__ import annotations

import html
import re
from pathlib import Path

TAG_RE = re.compile(r"<[^>]+>")
# 冒号前是小时的部分可省略：WebVTT 允许 "MM:SS.mmm"，ffmpeg 抽出来的就是这种
VTT_TS_RE = re.compile(
    r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{3})\s*-->\s*"
    r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{3})"
)
SRT_TS_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})"
)
SENT_END = re.compile(r"(?<![.])[.!?][\"')\]]?$")
MIN_BLOCK_CHARS = 20
CN_PUNCT = "，。！？；、："

CJK_TARGETS = ("中文", "日语", "韩语", "繁體", "繁体")


def is_cjk_target(target: str) -> bool:
    return any(k in target for k in CJK_TARGETS)


def default_max_chars(target: str) -> int:
    return 24 if is_cjk_target(target) else 45


# ------------------------------------------------------------------ 工具函数

def clean_text(raw: str) -> str:
    raw = TAG_RE.sub("", raw)
    raw = raw.replace("&nbsp;", " ").replace("\u200b", "")
    raw = html.unescape(raw)
    return re.sub(r"\s+", " ", raw).strip()


def ts_to_sec(ts: str) -> float:
    parts = ts.replace(",", ".").split(":")
    if len(parts) >= 3:
        h, m, s = parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    else:
        h, m, s = 0, 0, parts[0]
    return int(h) * 3600 + int(m) * 60 + float(s)


def sec_to_ts(sec: float) -> str:
    sec = max(sec, 0.0)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


# ------------------------------------------------------------------ 解析

def _parse_blocks(body: str, ts_re: re.Pattern) -> list[dict]:
    cues: list[dict] = []
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    for block in re.split(r"\n\s*\n", body):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        hit = next((i for i, ln in enumerate(lines) if ts_re.search(ln)), None)
        if hit is None:
            continue
        m = ts_re.search(lines[hit])
        g = m.groups()
        if len(g) == 8:
            sh, sm, ss, sms, eh, em, es, ems = g
        else:  # SRT：始终带小时
            sh, sm, ss, sms = 0, g[0], g[1], g[2]
            eh, em, es, ems = 0, g[4], g[5], g[6]
        start = f"{int(sh or 0):02d}:{int(sm):02d}:{int(ss):02d}.{sms}"
        end = f"{int(eh or 0):02d}:{int(em):02d}:{int(es):02d}.{ems}"
        text = clean_text(" ".join(lines[hit + 1:]))
        if text:
            cues.append({"start": start, "end": end, "text": text})
    return cues


def _dedupe_rollup(cues: list[dict]) -> list[dict]:
    """自动字幕会滚动重复上一句，去掉叠加部分。"""
    out: list[dict] = []
    for c in cues:
        t = c["text"]
        if out:
            prev = out[-1]["text"]
            if t == prev:
                continue
            if t.startswith(prev) and len(t) > len(prev):
                rem = t[len(prev):].strip(" ,.-–—")
                if not rem:
                    continue
                c = dict(c, text=rem)
            elif prev.startswith(t):
                continue
        out.append(c)
    return out


def parse_subtitle(path: str | Path) -> list[dict]:
    path = Path(path)
    body = path.read_text(encoding="utf-8-sig", errors="replace")
    cues = _parse_blocks(body, VTT_TS_RE) or _parse_blocks(body, SRT_TS_RE)
    return _dedupe_rollup(cues)


# ------------------------------------------------------------------ 合并句子

def merge_sentences(cues: list[dict], max_len: int = 280,
                    max_gap: float = 2.5) -> list[dict]:
    blocks: list[dict] = []
    cur: dict | None = None
    prev_end: float | None = None

    for c in cues:
        start_sec = ts_to_sec(c["start"])
        if cur is not None and prev_end is not None and start_sec - prev_end > max_gap:
            blocks.append(cur)
            cur = None
        if cur is None:
            cur = {"start": c["start"], "end": c["end"], "text": c["text"]}
        else:
            joiner = "" if cur["text"].endswith(("-", "—")) else " "
            cur["text"] = cur["text"].rstrip("-—") + joiner + c["text"]
            cur["end"] = c["end"]
        prev_end = ts_to_sec(c["end"])

        if ((SENT_END.search(c["text"].strip()) and len(cur["text"]) >= MIN_BLOCK_CHARS)
                or len(cur["text"]) >= max_len):
            blocks.append(cur)
            cur = None

    if cur is not None:
        blocks.append(cur)
    return blocks


# ------------------------------------------------------------------ 排版

def split_for_display(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars * 1.4:
        return [text]
    pieces = re.findall(rf"[^{CN_PUNCT}]*[{CN_PUNCT}]?", text)
    pieces = [p.strip() for p in pieces if p and p.strip()]

    chunks: list[str] = []
    buf = ""
    for p in pieces:
        if buf and len(buf) + len(p) > max_chars:
            chunks.append(buf)
            buf = p
        else:
            buf += p
    if buf:
        chunks.append(buf)

    final: list[str] = []
    for c in chunks:
        while len(c) > max_chars * 2:
            cut = c.rfind(" ", 0, max_chars * 2)
            cut = cut if cut > 0 else max_chars * 2
            final.append(c[:cut].strip())
            c = c[cut:].strip()
        if c:
            final.append(c)
    return final or [text]


def lay_out(block: dict, translation: str, max_chars: int) -> list[dict]:
    """按字符比例把译文摊回该块的时间区间。"""
    chunks = split_for_display(translation, max_chars)
    if len(chunks) == 1:
        return [{"start": block["start"], "end": block["end"], "text": chunks[0]}]

    t0, t1 = ts_to_sec(block["start"]), ts_to_sec(block["end"])
    span = max(t1 - t0, 0.5)
    total = sum(len(c) for c in chunks) or 1
    out: list[dict] = []
    cursor = t0
    for ch in chunks:
        dur = span * len(ch) / total
        out.append({"start": sec_to_ts(cursor),
                    "end": sec_to_ts(min(cursor + dur, t1)),
                    "text": ch})
        cursor += dur
    return out


# ------------------------------------------------------------------ 输出

def write_vtt(cues: list[dict], path: str | Path, note: str = "") -> Path:
    path = Path(path)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("WEBVTT\n")
        if note:
            fh.write(f"NOTE {note}\n")
        fh.write("\n")
        for c in cues:
            fh.write(f"{c['start']} --> {c['end']}\n{c['text']}\n\n")
    return path


def write_srt(cues: list[dict], path: str | Path) -> Path:
    path = Path(path)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for i, c in enumerate(cues, 1):
            fh.write(f"{i}\n{c['start'].replace('.', ',')} --> "
                     f"{c['end'].replace('.', ',')}\n{c['text']}\n\n")
    return path


def write_both(cues: list[dict], base: Path, note: str = "") -> tuple[Path, Path]:
    return write_vtt(cues, base.with_suffix(".vtt"), note), write_srt(cues, base.with_suffix(".srt"))
