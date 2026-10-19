"""界面文案（i18n）。

文案放在 `app/locales/<code>.json` 里，不再写死在代码中：

    {
      "_language": { "code": "zh", "name": "简体中文" },
      "strings": { "key": "文案", ... }
    }

新增语言 = 复制一份 en.json 改名、翻译、把 `_language` 改掉，代码不用动。
JSON 里的键按字母序排列，方便 diff 和 PR 评审。
"""
from __future__ import annotations

import json
import locale
import sys
from pathlib import Path
from typing import Dict, List, Tuple

Lang = str

REFERENCE = "zh"          # 缺失键时的兜底语言


def setup_console() -> None:
    """让中文能安全地打到控制台。

    Windows 上标准输出默认用本地代码页：中文系统是 cp936，英文 CI（GitHub Actions）
    是 cp1252 —— 后者遇到中文直接抛 UnicodeEncodeError。

    策略：
      * 输出被重定向（管道 / CI）时，强制 UTF-8，让日志按 UTF-8 正确解码；
      * 交互式终端保持原编码，只把错误策略改成 replace，避免少数生僻字把程序打挂。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is None:            # pythonw 下 stdout 可能是 None
                continue
            if stream.isatty():
                stream.reconfigure(errors="replace")
            else:
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def _locales_dirs() -> List[Path]:
    """兼容源码运行和 PyInstaller 打包（onedir 下资源在 _internal 里）。"""
    here = Path(__file__).resolve().parent
    cands: List[Path] = [here / "locales"]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        cands.append(Path(bundle) / "app" / "locales")
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        cands.append(exe_dir / "app" / "locales")
        cands.append(exe_dir / "_internal" / "app" / "locales")
    seen, out = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


class Language:
    __slots__ = ("code", "name", "strings", "path")

    def __init__(self, code: str, name: str, strings: Dict[str, str], path: Path):
        self.code = code
        self.name = name
        self.strings = strings
        self.path = path

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Language {self.code} {len(self.strings)} strings>"


def _load_file(path: Path) -> Language | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[i18n] 跳过 {path.name}: {exc}", file=sys.stderr)
        return None
    meta = raw.get("_language") or {}
    code = str(meta.get("code") or path.stem)
    name = str(meta.get("name") or code)
    strings = raw.get("strings") or {}
    if not isinstance(strings, dict):
        print(f"[i18n] {path.name} 的 strings 不是对象，已跳过", file=sys.stderr)
        return None
    return Language(code, name, {str(k): str(v) for k, v in strings.items()}, path)


def _load_all() -> Dict[str, Language]:
    langs: Dict[str, Language] = {}
    for directory in _locales_dirs():
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            lang = _load_file(path)
            if lang and lang.code not in langs:
                langs[lang.code] = lang
        if langs:
            break
    return langs


_loaded: Dict[str, Language] = _load_all()

# [(code, name)]：参考语言排最前，其余按代码排序
LANGUAGES: List[Tuple[str, str]] = []
if _loaded:
    ordered = [REFERENCE] if REFERENCE in _loaded else []
    ordered += [c for c in sorted(_loaded) if c not in ordered]
    LANGUAGES = [(c, _loaded[c].name) for c in ordered]
else:
    print("[i18n] 没找到任何语言文件，界面将显示键名", file=sys.stderr)


def _detect() -> Lang:
    """按系统区域猜语言。Windows 上 getlocale() 可能是
    'chinese (simplified)_china' 这种长名字，不能只看前两位。"""
    try:
        code = (locale.getlocale()[0] or "").lower()
    except (ValueError, TypeError):
        code = ""
    if not code:
        code = (sys.getlocale() or "").lower()
    code = code.replace("-", "_")

    def pick(candidate: str) -> str | None:
        return candidate if candidate in _loaded else None

    if code.startswith("zh") or "chinese" in code:
        return pick("zh") or pick("en") or (LANGUAGES[0][0] if LANGUAGES else "zh")
    if code.startswith("en") or "english" in code:
        return pick("en") or pick("zh") or (LANGUAGES[0][0] if LANGUAGES else "en")
    for known, _name in LANGUAGES:
        if code.startswith(known):
            return known
    return REFERENCE if REFERENCE in _loaded else (LANGUAGES[0][0] if LANGUAGES else "zh")


_lang: Lang = _detect()


def detect_language() -> Lang:
    return _detect()


def set_language(code: str) -> Lang:
    global _lang
    code = str(code or "").strip().lower()
    if code in _loaded:
        _lang = code
    elif code.startswith("en") and "en" in _loaded:
        _lang = "en"
    elif code:
        _lang = REFERENCE if REFERENCE in _loaded else code
    else:
        _lang = _detect()
    return _lang


def get_language() -> Lang:
    return _lang


def tr(key: str, **fmt) -> str:
    lang = _loaded.get(_lang)
    text = lang.strings.get(key) if lang is not None else None
    if text is None:
        ref = _loaded.get(REFERENCE)
        if ref is not None:
            text = ref.strings.get(key)
    if text is None:
        return key
    if fmt:
        try:
            return text.format(**fmt)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def language_label(code: str) -> str:
    for c, name in LANGUAGES:
        if c == code:
            return name
    return code


def available_codes() -> List[str]:
    return [c for c, _ in LANGUAGES]


def all_keys() -> List[str]:
    ref = _loaded.get(REFERENCE) or next(iter(_loaded.values()), None)
    return sorted(ref.strings) if ref else []


def missing_keys(code: str) -> List[str]:
    """给检查脚本用：该语言缺了哪些键。"""
    lang = _loaded.get(code)
    if lang is None:
        return all_keys()
    return [k for k in all_keys() if k not in lang.strings]


def extra_keys(code: str) -> List[str]:
    """该语言多出来的键（通常是废弃文案）。"""
    lang = _loaded.get(code)
    ref = _loaded.get(REFERENCE)
    if lang is None or ref is None:
        return []
    return sorted(set(lang.strings) - set(ref.strings))


def coverage(code: str) -> int:
    """该语言的完成度百分比（按参考语言的键数算）。"""
    total = len(all_keys())
    if not total:
        return 100
    return round((total - len(missing_keys(code))) / total * 100)


def get_string(code: str, key: str) -> str | None:
    """按语言码直取原文，不做回退（给检查脚本用）。"""
    lang = _loaded.get(code)
    return lang.strings.get(key) if lang is not None else None
