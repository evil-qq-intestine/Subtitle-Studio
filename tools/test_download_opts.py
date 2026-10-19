"""端到端验证：浏览器 Cookie + TLS 伪装 + 额外参数一起走一遍。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.core.pipeline import JobSpec, Pipeline, PipelineError


def main() -> int:
    s = Settings()
    s.workdir = r"D:\subtitle translation\tools\fixtures\out3"
    s.proxy = "http://127.0.0.1:17890"
    s.cookies_browser = "firefox"
    s.impersonate = ""
    s.extra_args = ""
    s.download_video = False
    s.ollama_model = "hy-mt2"

    pipe = Pipeline(s,
                    on_status=lambda m: print(f"[状态] {m}", flush=True),
                    on_log=lambda m: print(f"       {m}", flush=True))
    try:
        result = pipe.run(JobSpec(source="https://www.youtube.com/watch?v=jNQXAC9IVRw",
                                  is_url=True, target_lang="简体中文",
                                  download_video=False))
    except PipelineError as exc:
        print(f"失败: {exc}")
        return 1
    print(f"\n完成: {result.title} / {result.cue_count} 条 / {result.seconds:.0f}s")
    for f in result.subtitle_files:
        print("  ", f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

