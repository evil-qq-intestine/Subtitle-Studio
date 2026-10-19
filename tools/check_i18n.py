"""检查语言文件：缺键、废弃键、代码里用了但没定义的键。

用法：
    python tools/check_i18n.py           # 只报告
    python tools/check_i18n.py --strict  # 有问题时返回非 0（CI / 提交前用）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import i18n  # noqa: E402

TR_RE = re.compile(r'\b(?:tr|_lab|_btn|_hint)\(\s*["\']([A-Za-z0-9_.]+)["\']')
PH_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def placeholders(text: str) -> set[str]:
    """取 {name} 形式的占位符。漏一个运行时就显示成花括号原文。"""
    return set(PH_RE.findall(text or ""))


def _sources() -> list[tuple[Path, str]]:
    out = []
    for path in (ROOT / "app").rglob("*.py"):
        if path.name == "i18n.py":
            continue
        try:
            out.append((path, path.read_text(encoding="utf-8")))
        except OSError:
            continue
    return out


def used_keys() -> set[str]:
    """真正会被 tr() 解析到的键（含 _lab/_btn/_hint 这类间接引用）。"""
    keys: set[str] = set()
    for _path, text in _sources():
        keys.update(TR_RE.findall(text))
    return keys


def mentioned_keys() -> set[str]:
    """源码里以字符串字面量出现过的键，用来判断有没有废弃文案。"""
    mentioned: set[str] = set()
    for _path, text in _sources():
        for key in i18n.all_keys():
            if f'"{key}"' in text or f"'{key}'" in text:
                mentioned.add(key)
    return mentioned


def main() -> int:
    i18n.setup_console()
    strict = "--strict" in sys.argv
    if not i18n.LANGUAGES:
        print("找不到任何语言文件（app/locales/*.json）")
        return 1

    ref_keys = set(i18n.all_keys())
    used = used_keys()
    problems = 0

    print(f"参考语言: {i18n.REFERENCE}   键总数: {len(ref_keys)}   语言数: {len(i18n.LANGUAGES)}")
    for code, name in i18n.LANGUAGES:
        missing = i18n.missing_keys(code)
        extra = i18n.extra_keys(code)
        ph_bad = []
        for key in ref_keys:
            want = i18n.get_string(i18n.REFERENCE, key)
            got = i18n.get_string(code, key)
            if got is None:
                continue            # 缺键已经单独统计
            if placeholders(want) != placeholders(got):
                ph_bad.append((key, sorted(placeholders(want)), sorted(placeholders(got))))
        status = "OK"
        if missing or extra or ph_bad:
            status = f"缺 {len(missing)} / 多 {len(extra)} / 占位符 {len(ph_bad)}"
        print(f"  {code:<6} {name:<10} {i18n.coverage(code):>3}%  {status}")
        for k in missing[:12]:
            print(f"      缺: {k}")
        for k in extra[:12]:
            print(f"      多: {k}")
        for k, want, got in ph_bad[:12]:
            print(f"      占位符不符: {k}  期望 {want}  实际 {got}")
        if missing or extra or ph_bad:
            problems += 1

    undefined = sorted(used - ref_keys)
    unused = sorted(ref_keys - mentioned_keys())
    if undefined:
        print(f"\n代码里在用但语言文件里没有的键（{len(undefined)}）：")
        for k in undefined[:20]:
            print(f"  {k}")
        problems += 1
    if unused:
        print(f"\n定义了但代码没用的键（{len(unused)}，可能是废弃文案）：")
        for k in unused[:20]:
            print(f"  {k}")

    if problems:
        print(f"\n发现 {problems} 处问题")
        return 1 if strict else 0
    print("\n全部一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

