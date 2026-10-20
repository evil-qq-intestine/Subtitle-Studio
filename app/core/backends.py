"""翻译引擎：本地 Ollama / 任意 OpenAI 兼容 API。

设计原则：只要能出译文的就行。Ollama 只是其中一种，LM Studio、vLLM、llama.cpp server、
DeepSeek、SiliconFlow、OpenAI 全部走同一套 OpenAI 兼容协议。
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from ..config import Settings
from ..i18n import tr
from .env import find_ollama

Log = Callable[[str], None]

CLEAN_PREFIX = re.compile(r"^(译文|翻译|Translation|Output)\s*[:：]\s*", re.I)


def build_prompt(text: str, target: str) -> str:
    return f"把下面的文本翻译成{target}，不要额外解释。\n\n{text}"


def _clean(out: str) -> str:
    out = re.sub(r"\s*\n\s*", " ", out or "").strip()
    out = CLEAN_PREFIX.sub("", out)
    if len(out) >= 2 and out[0] == out[-1] and out[0] in "\"'“”":
        out = out[1:-1].strip()
    return out


def _is_local(host: str) -> bool:
    host = host.lower()
    return any(h in host for h in ("127.0.0.1", "localhost", "0.0.0.0", "::1"))


def _opener(url: str, proxy: str = "") -> urllib.request.OpenerDirector:
    handlers: list = []
    if proxy and not _is_local(urllib.parse.urlparse(url).hostname or ""):
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def _post_json(url: str, payload: dict, headers: dict, proxy: str = "",
               timeout: int = 180, tries: int = 3) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    hdrs = {"Content-Type": "application/json", **headers}
    last: Exception | None = None
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs)
            with _opener(url, proxy).open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last = exc
            if attempt < tries:
                time.sleep(1.2 * attempt)
    raise RuntimeError(tr("err.request", err=last))


def _get_json(url: str, headers: dict, proxy: str = "", timeout: int = 8) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with _opener(url, proxy).open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --------------------------------------------------------------------- 引擎

class Translator:
    label = "engine"

    def translate(self, text: str, target: str) -> str:
        raise NotImplementedError

    def test(self) -> tuple[bool, str]:
        t0 = time.time()
        try:
            out = self.translate("Hello, world. This is a translation test.", "简体中文")
            ms = int((time.time() - t0) * 1000)
            if not out.strip():
                return False, "返回空结果"
            return True, f"{ms} ms · {out[:40]}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:200]


class OllamaTranslator(Translator):
    def __init__(self, url: str, model: str, proxy: str = ""):
        self.url = url.rstrip("/")
        self.model = model
        self.proxy = proxy

    @property
    def label(self) -> str:
        return f"{tr('engine.ollama')} · {self.model}"

    def translate(self, text: str, target: str) -> str:
        payload = {
            "model": self.model,
            "prompt": build_prompt(text, target),
            "stream": False,
            "options": {"temperature": 0.7, "top_p": 0.6, "top_k": 20,
                        "repeat_penalty": 1.05, "num_predict": 1024},
        }
        data = _post_json(f"{self.url}/api/generate", payload, {}, self.proxy)
        return _clean(data.get("response", ""))


class OpenAICompatTranslator(Translator):
    def __init__(self, base: str, key: str, model: str, proxy: str = ""):
        self.base = base.rstrip("/")
        self.key = key
        self.model = model
        self.proxy = proxy

    @property
    def label(self) -> str:
        return f"{tr('engine.api')} · {self.model}"

    def _headers(self) -> dict:
        h = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        return h

    def translate(self, text: str, target: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system",
                 "content": f"你是字幕翻译引擎。把用户给的文本翻译成{target}，只输出译文，"
                            f"不要解释、不要加引号。"},
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
            "stream": False,
        }
        data = _post_json(f"{self.base}/chat/completions", payload,
                          self._headers(), self.proxy)
        try:
            return _clean(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"返回格式不识别: {str(data)[:200]}")


# --------------------------------------------------------------------- 探测

def probe_ollama(url: str, timeout: float = 2.5) -> list[str] | None:
    try:
        data = _get_json(f"{url.rstrip('/')}/api/tags", {}, timeout=timeout)
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:  # noqa: BLE001
        return None


def probe_openai(base: str, key: str = "", proxy: str = "",
                 timeout: float = 5) -> list[str] | None:
    try:
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        data = _get_json(f"{base.rstrip('/')}/models", headers, proxy, timeout)
        items = data.get("data") or data.get("models") or []
        out = []
        for it in items:
            name = it.get("id") or it.get("name") if isinstance(it, dict) else str(it)
            if name:
                out.append(name)
        return out
    except Exception:  # noqa: BLE001
        return None


LOCAL_ENDPOINTS = [
    ("Ollama", "http://127.0.0.1:11434", "ollama"),
    ("LM Studio", "http://127.0.0.1:1234/v1", "openai"),
    ("llama.cpp", "http://127.0.0.1:8080/v1", "openai"),
    ("vLLM", "http://127.0.0.1:8000/v1", "openai"),
]


def start_ollama(settings: Settings, log: Log | None = None,
                 timeout: float = 30.0) -> bool:
    """Ollama 没在跑就尝试拉起来。

    只对本机地址生效（远端 Ollama 我们没法启动它）。启动失败就返回 False，
    由调用方决定是报错还是继续等。
    """
    import os
    import subprocess
    import sys
    import time

    if not _is_local(urllib.parse.urlparse(settings.ollama_url).hostname or ""):
        return False

    if probe_ollama(settings.ollama_url, timeout=1.5) is not None:
        return True

    exe = find_ollama()
    if exe is None:
        if log:
            log(tr("st.ollama_not_found"))
        return False

    if log:
        log(tr("st.ollama_starting", path=str(exe)))

    kwargs: dict = {}
    if sys.platform.startswith("win"):
        # DETACHED_PROCESS：应用退出后 Ollama 继续跑，下次不用再拉
        kwargs["creationflags"] = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                                   | getattr(subprocess, "DETACHED_PROCESS", 0))
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(
            [str(exe), "serve"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=os.environ.copy(),
            **kwargs,
        )
    except OSError as exc:
        if log:
            log(tr("st.ollama_start_failed", err=exc))
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        if probe_ollama(settings.ollama_url, timeout=1.5) is not None:
            if log:
                log(tr("st.ollama_ready"))
            return True
        time.sleep(0.8)

    if log:
        log(tr("st.ollama_timeout"))
    return False

MODEL_HINTS = ("mt", "translate", "翻译", "hy-mt", "hunyuan", "qwen", "gemma", "saiga")


def pick_model(models: list[str]) -> str:
    """从模型列表里挑一个更像翻译模型的。"""
    if not models:
        return ""
    for keyword in MODEL_HINTS:
        for m in models:
            if keyword in m.lower():
                return m
    return models[0]


@dataclass
class Detected:
    name: str
    kind: str          # ollama | openai
    base: str
    models: list[str]

    @property
    def best_model(self) -> str:
        return pick_model(self.models)


def autodetect(settings: Settings) -> list[Detected]:
    """扫描本机常见推理服务。"""
    found: list[Detected] = []

    models = probe_ollama(settings.ollama_url)
    if models is not None:
        found.append(Detected("Ollama", "ollama", settings.ollama_url, models))

    for name, base, kind in LOCAL_ENDPOINTS[1:]:
        if found and found[0].base == base:
            continue
        models = probe_openai(base)
        if models:
            found.append(Detected(name, "openai", base, models))

    if settings.api_base:
        models = probe_openai(settings.api_base, settings.api_key, settings.proxy)
        if models:
            found.append(Detected("自定义 API", "openai", settings.api_base, models))

    return found


def build_translator(settings: Settings) -> Translator:
    if settings.backend == "ollama":
        if not settings.ollama_model:
            raise RuntimeError(tr("err.no_model"))
        return OllamaTranslator(settings.ollama_url, settings.ollama_model, settings.proxy)
    if not settings.api_base or not settings.api_model:
        raise RuntimeError(tr("err.no_api"))
    return OpenAICompatTranslator(settings.api_base, settings.api_key,
                                  settings.api_model, settings.proxy)


