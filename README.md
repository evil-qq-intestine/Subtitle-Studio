# Subtitle Studio

桌面端视频字幕翻译工具。给一个链接（或拖一个本地视频），自动抓取原字幕、用本地模型或你自己的 API 翻译成中文，输出可直接加载的 `.srt` / `.vtt`。

**纯 Qt 原生界面**（PySide6 / Qt Widgets），不用 Electron、不用 WebView、不用浏览器内核套壳。Windows / macOS / Linux 同一套代码。

> **安装包未签名。** 双击 MSI 时 SmartScreen 会提示「Windows 已保护你的电脑」，
> 点 **更多信息 → 仍要运行** 即可，文件本身是完整的。原因和解决办法见「安装包（MSI）」一节。

![主界面](docs/main.png)

## 为什么需要它

YouTube 的「自动翻译」字幕走 `api/timedtext?...&tlang=` 接口。在没有 PO token 的会话上，这个接口会返回 429 或空响应——实测**与出口 IP 无关**（换 Cloudflare WARP 出口同样 429，而那边 YouTube 反而直接要求登录验人）。

但**原始语言字幕轨是正常的**。所以不去求 YouTube 给译文，抓原文自己翻。

## 功能

- **链接下载**：任意 yt-dlp 支持的站点（YouTube / Bilibili / …），可只取字幕，也可连视频一起下
- **本地视频**：自动探测内嵌文本字幕轨并提取；没有字幕轨时可选用 Whisper 语音识别
- **翻译引擎**：本地 Ollama，或任意 OpenAI 兼容 API（DeepSeek / SiliconFlow / LM Studio / vLLM / llama.cpp）
- **工具自举**：启动时检查 yt-dlp，缺失会自动下载（Windows 下解压即用）
- **下载参数**：支持浏览器 Cookie、TLS 指纹伪装、任意额外 yt-dlp 参数（见下）
- **完整 i18n**：简体中文 / English 可切换，也可跟随系统；切换即时生效，不用重启
- **可配置工作目录**，输出与视频同名，播放器可直接加载
- **目标语言是固定下拉列表**（简体中文 / 繁体中文 / 英文 / 日语 / …），不允许手输，避免写出模型不认识的语种名；想增删语言改 `app/config.py` 里的 `TARGET_LANGS` 一处即可
- 任务队列、实时进度、随时取消、一键打开输出目录

## 下载参数（设置 → 下载）

遇到站点要登录、或有反爬限制时用这里：

| 项 | 说明 |
|---|---|
| 从浏览器读取 Cookie | `--cookies-from-browser`。**Chrome / Edge 的 Cookie 被 DPAPI 加密，yt-dlp 解不开**，实测会报 `Failed to decrypt with DPAPI`；**Firefox 可以正常读取** |
| cookies.txt | 自己导出的 Cookie 文件，走 `--cookies`。Chrome 用户建议走这条 |
| 伪装 TLS 指纹 | `--impersonate`。**不要对 YouTube 开**，YouTube 排斥该指纹，会直接 `No video formats found`；这是给别的站点用的 |
| 额外参数 | 原样追加给 yt-dlp，shell 规则解析（支持引号），例如 `--extractor-args "youtube:player_client=web"` |

两个预设按钮：「应对确认不是机器人」会切到 Firefox Cookie 并清空伪装；「快速：只取字幕」只关掉视频下载。

app 会把 yt-dlp 的常见失败翻译成可执行的提示（需要登录 / Cookie 解不开 / 伪装导致解析失败 / 引擎连不上），而不是抛原始报错。

## 界面语言

设置 → 常规 → 界面语言，可选 **跟随系统 / 简体中文 / English**，切换后界面立刻刷新（含已存在任务卡上的按钮和状态）。

文案存在 `app/locales/*.json`，新增语言不用改代码，详见下面「翻译贡献」。

语言下拉框里会显示各语言的完成度（如「日本語 62%」），半成品一眼可见。

## 环境要求

| 项 | 说明 |
|---|---|
| Python | 3.10+（开发用 3.11） |
| PySide6 | 必需，界面框架 |
| yt-dlp | 缺失时应用会自动下载到 `%APPDATA%\SubtitleStudio\bin` |
| ffmpeg | 可选。下载合并高画质视频、提取内嵌字幕时需要 |
| 翻译模型 | Ollama 里的任意模型，或一个 OpenAI 兼容 API |

## 安装

```bash
pip install -r requirements.txt
```

启动：

```bash
python main.py
```

Windows 也可以双击 `run.ps1`，Linux/macOS 用 `./run.sh`。

> **pip 装不上？** 这台机器上出现过 `SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC`（中间链路干扰 OpenSSL）。
> 绕法是用 curl 拉 wheel 再本地安装，脚本见 `wheels/fetch_wheels.ps1`。

## 首次使用

1. 启动后右上角会显示检测到的引擎，例如 `● Ollama · hy-mt2`。
2. 如果显示「未配置引擎」，点它打开 **设置 → 翻译引擎**：
   - 选 **Ollama**：填服务地址，点「刷新模型」，选一个翻译模型
   - 或选 **OpenAI 兼容 API**：填 Base URL（要带 `/v1`）、Key、模型名
   - 点「测试翻译」确认能出字
3. 在 **设置 → 常规** 里填代理（例如 `http://127.0.0.1:7897`），否则国内拉不到 YouTube。
4. 粘贴链接 → 开始翻译。

翻译模型推荐用专门的翻译模型（如腾讯混元 Hy-MT2、Qwen），通用对话模型也能用但断句质量差一些。

## 界面

| | |
|---|---|
| ![本地文件](docs/local.png) | ![设置](docs/settings.png) |

## 命令行模式

不需要界面时（批处理、排错）可以直接跑：

```bash
python main.py --cli "https://www.youtube.com/watch?v=xxxx" --model hy-mt2
python main.py --cli "D:\movie.mkv" --target 简体中文
python main.py --cli "URL" --api-base https://api.deepseek.com/v1 --api-key sk-... --api-model deepseek-chat
```

常用参数：`--no-video`（只取字幕）、`--quality 720`、`--proxy`、`--workdir`、`--src en`。

## 两个关键工程细节

**1. 必须先合并成完整句子再翻。**
YouTube 的 ASR 字幕按 2~5 秒切碎，碎片单独送翻译会严重幻觉：

| 输入 | 输出 |
|---|---|
| `really really long trunks` | 长得超长的树干 ❌ |
| `they have really... really really long trunks` | 他们的阴茎实在……长得超级长 ❌ |
| `...in front of the elephants. ...they have really really long trunks` | 这些大象…拥有极长的鼻子 ✅ |

所以按句末标点合并（`...` / `…` 视为停顿，不当句末），并设最小块长度。

**2. 抓字幕走显式代理，不走 TUN。**
实测 TUN（fake-ip）对 Google 系流量会间歇性 `RST` / 超时，而 HTTP 代理端口稳定，因此 yt-dlp 默认加 `--proxy`。

## 目录结构

```
main.py                  入口（GUI / CLI）
build.ps1                一键构建（打包 → 可选签名 → MSI）
app/
  config.py              配置读写（JSON，位于用户配置目录）
  i18n.py                文案加载与 tr()
  locales/               界面文案（zh.json / en.json）
  core/
    env.py               yt-dlp / ffmpeg 探测与自举
    subs.py              字幕解析、句子合并、时间轴重排、输出
    backends.py          翻译引擎（Ollama / OpenAI 兼容）+ 自动探测
    pipeline.py          任务流水线（不依赖 Qt，可单独测试）
  ui/
    icon.py              应用图标绘制（exe / 窗口 / 安装包共用）
    theme.py             深色主题与 QSS
    widgets.py           任务卡、拖拽区等组件
    settings.py          设置对话框
    main_window.py       主窗口
installer/
  Product.wxs            MSI 定义
  build_msi.ps1          WiX 编译（首次运行自动拉工具链）
  sign.ps1               Authenticode 签名（无证书时跳过）
assets/                  图标与安装图（生成物，见 tools/make_*.py）
tools/                   自检、界面冒烟、i18n 检查、图标生成
.github/workflows/       CI / 构建发布 / 语言检查
```

核心逻辑（`app/core`）不依赖 Qt，`python tools/selfcheck.py` 可以脱离界面自检；`python tools/smoke_ui.py` 则离屏把界面建一遍，CI 里跑。

## 翻译贡献（怎么加一门语言）

文案不写在代码里，全在 `app/locales/*.json`：

```json
{
  "_language": { "code": "ja", "name": "日本語" },
  "strings": {
    "main.start": "翻訳",
    "main.tasks": "タスク"
  }
}
```

加语言只要三步，**不用改任何代码**：

1. 复制 `app/locales/en.json` 为 `app/locales/ja.json`
2. 改掉 `_language` 里的 `code` / `name`
3. 翻译 `strings` 里的值

程序启动时会扫描 `app/locales/` 并自动把新语言加进「界面语言」下拉框。没翻到的键会回退到中文，所以可以先提交半成品。

提交前跑一下检查：

```bash
python tools/check_i18n.py --strict
```

它会报告：

- 各语言缺哪些键（附完成度百分比）
- 有哪些多余键（通常是废弃文案）
- **占位符不一致**：比如中文 `翻译 {i}/{n}`、英文漏了 `{n}`，运行时就会把花括号原样显示出来
- 代码里 `tr("...")` 用了但语言文件里没有的键

GitHub Actions 也接了这一步（`.github/workflows/i18n.yml`），改 `app/locales/` 的 PR 会自动跑 `--strict`，缺键直接卡住。

语言文件在打包时必须一起带上（`build.ps1` 里已处理 `--add-data app\locales;app\locales`），否则打包后的界面会全是键名。

## 安装包（MSI）

构建好的安装包在 `installer\Subtitle Studio.msi`（43 MB）。

> **未签名，SmartScreen 提示点「更多信息 → 仍要运行」**
>
> 这个安装包没有做代码签名，双击时 Windows 会弹「Windows 已保护你的电脑」。
> 点左侧的 **更多信息**，再点 **仍要运行** 即可。文件本身是完整的，只是没有证书声明发布者。
>
> 想彻底消除提示需要购买代码签名证书（OV 证书约 $150–300/年），或者把项目开源后
> 申请 [SignPath Foundation](https://signpath.io) 的免费开源签名。详见下面「代码签名」。

- **英文**安装向导（ProductLanguage 1033），自绘品牌横幅
- 装到 `C:\Program Files\Subtitle Studio`
- 创建开始菜单和桌面快捷方式
- 带卸载项，支持覆盖升级（MajorUpgrade）
- 内置 107 MB 运行时，目标机器**不需要装 Python**

重新构建：

```powershell
.\build.ps1              # 打包 + MSI 一条龙
.\build.ps1 -SkipMsi     # 只打包免安装目录
.\build.ps1 -SkipApp     # 只重出 MSI
.\build.ps1 -Sign        # 构建完顺便签名（需配置证书）
```

构建脚本会自动用 `heat` 收集文件、`candle` + `light` 编译。**首次运行会自动从 NuGet 下载 WiX 3.14 工具链**（约 40MB，存到 `build\wix\`），不需要手动装。

## 代码签名

`installer\sign.ps1` 支持两种证书来源，通过环境变量配置：

| 变量 | 说明 |
|---|---|
| `SIGN_PFX_PATH` + `SIGN_PFX_PASSWORD` | pfx 文件 |
| `SIGN_CERT_THUMBPRINT` | 本机证书存储里的指纹（配合 `/sm`） |
| `SIGN_TIMESTAMP_URL` | 可选，默认 `http://timestamp.digicert.com` |

没配证书时脚本直接跳过（退出码 0），所以本地构建不受影响。

```powershell
$env:SIGN_PFX_PATH = "C:\keys\mycert.pfx"
$env:SIGN_PFX_PASSWORD = "..."
.\build.ps1 -Sign
```

签名顺序有讲究：**先签 exe → 再打 MSI → 再签 MSI**，因为 MSI 会重新打包 exe，签名不会自动继承。`build.ps1 -Sign` 已经按这个顺序处理。

## 持续集成

| 工作流 | 触发 | 做什么 |
|---|---|---|
| `ci.yml` | push / PR | 语法检查、语言文件一致性、界面冒烟测试（离屏建窗口） |
| `build.yml` | 打 `v*` tag 或手动 | Windows 上完整打包，上传 MSI 与免安装目录，打 tag 时自动发 Release |
| `i18n.yml` | 改 `app/locales/**` | 只跑语言一致性检查（不装 PySide6，几秒钟） |

`build.yml` 里如果配了 `SIGN_PFX_BASE64` / `SIGN_PFX_PASSWORD` 两个 secret 会自动签名，没配就出未签名包。

## 打包成免安装目录

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "Subtitle Studio" main.py
```

产物在 `dist/Subtitle Studio/`，整个目录拷走就能用。PySide6 打包出来仍是原生 Qt 程序，不含浏览器内核。

> 注意：直接用上面这条命令会漏掉 `app/locales`，界面会显示成键名。用 `.\build.ps1 -SkipMsi` 才是完整的。

## 已知限制

- 纯音乐 / 无字幕的视频抓不到原文；除非开启语音识别
- 合并句子后输出粒度比原字幕粗（一句一条），换行由标点决定
- 没有 JS runtime（deno）时 yt-dlp 可能拿不到全部字幕语言，但不影响取原语言字幕
- 语音识别需要额外装 `faster-whisper`，首次使用会下载模型（small 约 500MB）

