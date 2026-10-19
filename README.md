# Subtitle Studio

Turn any video into subtitles you can actually read. Paste a link (or drop a local file), and it fetches the original captions, merges them into complete sentences, translates them with a local model or your own API, and writes `.srt` / `.vtt` files next to the video.

Native **Qt** interface (PySide6 / Qt Widgets) — no Electron, no WebView, no embedded browser. One codebase for Windows, macOS and Linux.

**English** | [简体中文](README.zh-CN.md)

> **The installer is unsigned.** Windows SmartScreen will show "Windows protected your PC"
> when you run the MSI. Click **More info → Run anyway**; the file itself is fine, it just has
> no certificate naming a publisher. See [Installing](#windows-installer-recommended) for details.

![Main window](docs/main.png)

## Why this exists

YouTube's built-in "auto-translate" for captions goes through `api/timedtext?...&tlang=`. On a session without a PO token that endpoint answers 429 or an empty body — and testing showed this is **not about your IP** (a completely different egress, Cloudflare WARP, got the same 429, while YouTube there went further and demanded a sign-in).

The original-language caption track, however, works fine. So instead of asking YouTube for a translation, fetch the source and translate it yourself.

## Features

- **Links**: any site yt-dlp supports (YouTube, Bilibili, …). Subtitles only, or subtitles + video.
- **Local files**: finds embedded text subtitle tracks and extracts them; optional Whisper speech recognition when there are none.
- **Engines**: local Ollama, or any OpenAI-compatible API (DeepSeek, SiliconFlow, LM Studio, vLLM, llama.cpp).
- **Self-bootstrapping**: checks for yt-dlp on startup and downloads it if missing.
- **Download options**: browser cookies, TLS fingerprint impersonation, arbitrary extra yt-dlp arguments.
- **Full i18n**: Simplified Chinese / English, or follow the system; switches instantly, no restart.
- **Configurable output folder**; files are named after the video so players load them automatically.
- **Sentence-level merging** before translation (see [why](docs/DEVELOPMENT.md#two-implementation-notes)) — translating 2-second caption fragments produces garbage.
- Task queue with live progress, cancel anytime, one-click "open folder".

## Requirements

| | |
|---|---|
| Windows 10/11 | Nothing else — the installer bundles the runtime |
| From source | Python 3.10+ (developed on 3.11), `pip install -r requirements.txt` |
| yt-dlp | Downloaded automatically on first run if missing |
| ffmpeg | Optional — needed for merging high-quality video and extracting embedded subtitles |
| Translation | A model in Ollama, or any OpenAI-compatible endpoint |

## Install

### Windows installer (recommended)

Download `Subtitle Studio.msi` from [Releases](../../releases) and run it.

> **Unsigned build.** SmartScreen shows "Windows protected your PC" — click **More info**, then
> **Run anyway**. The MSI installs to `C:\Program Files\Subtitle Studio` and creates Start Menu
> and desktop shortcuts. Removing the warning entirely requires a code signing certificate
> (an OV certificate is roughly $150–300/year) or free signing for open-source projects via
> [SignPath Foundation](https://signpath.io). Both are covered in the
> [development guide](docs/DEVELOPMENT.md#code-signing).

### Run from source

```bash
git clone <this repo>
cd subtitle-studio
pip install -r requirements.txt
python main.py
```

On Windows you can also double-click `run.ps1`; on Linux/macOS use `./run.sh`.

## First run

1. The top-right corner shows the detected engine, e.g. `● Ollama · hy-mt2`.
2. If it says "engine not configured", click it and open **Settings → Engine**:
   - **Ollama**: set the service URL, click *Refresh models*, pick a translation model; or
   - **OpenAI-compatible API**: fill in Base URL (including `/v1`), key and model name.
   - Click *Test translation* to confirm it produces output.
3. In **Settings → General**, set your proxy (e.g. `http://127.0.0.1:7897`) if the sites you need are blocked.
4. Paste a link and hit translate.

Dedicated translation models (Tencent Hunyuan-MT, Qwen, …) give noticeably better results than general chat models.

## Usage

### From a link

Paste a URL, pick the target language and quality, and hit **Translate**. With *Download video* off you only get subtitles.

### Local files

Switch to **Local file** and drop a video in. If it has an embedded text subtitle track it is extracted and translated; otherwise enable speech recognition in **Settings → Tools**.

### Download options

**Settings → Download**, for sites that need a login or fight scrapers:

| Field | Notes |
|---|---|
| Read cookies from browser | `--cookies-from-browser`. **Chrome/Edge cookies are DPAPI-encrypted and yt-dlp cannot decrypt them** (`Failed to decrypt with DPAPI`); **Firefox works** |
| or cookies.txt | An exported cookie file, passed as `--cookies`. Recommended if you use Chrome |
| Impersonate TLS fingerprint | `--impersonate`. **Do not enable for YouTube** — it rejects that fingerprint and extraction fails with `No video formats found`. It is for other sites |
| Extra arguments | Appended to yt-dlp verbatim, shell-parsed (quotes supported), e.g. `--extractor-args "youtube:player_client=web"` |

Two preset buttons cover the common cases: *Handle bot check* switches to Firefox cookies and clears impersonation; *Fast: subtitles only* turns off video download.

Common yt-dlp failures (sign-in required, undecryptable cookies, impersonation breaking extraction, engine unreachable) are turned into actionable messages instead of raw errors.

### Interface language

**Settings → General → Interface language**: follow system, 简体中文, or English. Applies immediately, including buttons on tasks already in the queue.

The language dropdown shows translation completeness (e.g. `日本語 66%`), so partial translations are obvious at a glance.

## Screenshots

| Local file | Settings |
|---|---|
| ![Local file](docs/local.png) | ![Settings](docs/settings.png) |

## Command line

Handy for batch jobs and debugging:

```bash
python main.py --cli "https://www.youtube.com/watch?v=xxxx" --model hy-mt2
python main.py --cli "D:\movie.mkv" --target 简体中文
python main.py --cli "URL" --api-base https://api.deepseek.com/v1 --api-key sk-... --api-model deepseek-chat
```

Useful flags: `--no-video` (subtitles only), `--quality 720`, `--proxy`, `--workdir`, `--src en`.

## Known limitations

- Silent or music-only videos have no source captions unless speech recognition is enabled.
- Output is sentence-level rather than per-fragment, so line breaks follow punctuation.
- Without a JS runtime (deno) yt-dlp may list fewer subtitle languages; the source language still works.
- Speech recognition needs `pip install faster-whisper` and downloads a model on first use (≈500 MB for `small`).

## Contributing

- [Development guide](docs/DEVELOPMENT.md) — project layout, building the MSI, code signing, CI.
- **Translations**: one JSON file per language in `app/locales/`, no code changes. Run
  `python tools/check_i18n.py --strict` before opening a PR.

