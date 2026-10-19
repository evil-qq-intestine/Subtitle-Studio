#requires -Version 7
# 一键构建：打包 → 可选签名 → 生成 MSI（→ 再签名）。
#
#   .\build.ps1                 打包 + 出 MSI
#   .\build.ps1 -SkipMsi        只打包免安装目录
#   .\build.ps1 -SkipApp        只重新生成 MSI（用已有的 dist）
#   .\build.ps1 -Sign           构建完顺便签名（需配置证书环境变量，见 installer\sign.ps1）
param(
    [switch]$SkipApp,
    [switch]$SkipMsi,
    [switch]$Sign
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root

$exe = Join-Path $root 'dist\Subtitle Studio\Subtitle Studio.exe'
$msi = Join-Path $root 'installer\Subtitle Studio.msi'
$signScript = Join-Path $root 'installer\sign.ps1'

# ---------------------------------------------------------------- 资源
# 图标和安装图是生成物，仓库里有；缺失时补一下
if (-not (Test-Path 'assets\app.ico') -or -not (Test-Path 'assets\banner.bmp')) {
    Write-Host "== 0/2 生成图标资源 ==" -ForegroundColor Cyan
    & python tools\make_icon.py
    if ($LASTEXITCODE -ne 0) { throw 'make_icon 失败' }
    & python tools\make_installer_art.py
    if ($LASTEXITCODE -ne 0) { throw 'make_installer_art 失败' }
}

# ---------------------------------------------------------------- 打包
if (-not $SkipApp) {
    Write-Host "== 1/2 打包应用 ==" -ForegroundColor Cyan

    $excludes = @(
        'tkinter', 'unittest', 'pydoc', 'doctest',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets',
        'PySide6.QtNetwork', 'PySide6.QtPrintSupport', 'PySide6.QtSql',
        'PySide6.QtTest', 'PySide6.QtXml', 'PySide6.QtOpenGL',
        'PySide6.QtDBus', 'PySide6.QtSvg', 'PySide6.QtMultimedia'
    ) | ForEach-Object { @('--exclude-module', $_) }

    # 语言文件必须显式带上，否则打包后界面全是键名
    $pyArgs = @(
        '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
        '--name', 'Subtitle Studio',
        '--icon', 'assets\app.ico',
        '--add-data', 'app\locales;app\locales',
        '--add-data', 'assets;assets'
    ) + $excludes + @('main.py')

    & python @pyArgs
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 失败' }

    if ($Sign) {
        Write-Host "== 签名 exe ==" -ForegroundColor Cyan
        & pwsh -NoProfile -ExecutionPolicy Bypass -File $signScript -Files $exe
        if ($LASTEXITCODE -ne 0) { throw 'exe 签名失败' }
    }
}

# ---------------------------------------------------------------- MSI
if (-not $SkipMsi) {
    Write-Host "== 2/2 生成 MSI ==" -ForegroundColor Cyan
    & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'installer\build_msi.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'MSI 构建失败' }

    if ($Sign) {
        Write-Host "== 签名 MSI ==" -ForegroundColor Cyan
        & pwsh -NoProfile -ExecutionPolicy Bypass -File $signScript -Files $msi
        if ($LASTEXITCODE -ne 0) { throw 'MSI 签名失败' }
    }
}

Write-Host ""
Write-Host "完成：" -ForegroundColor Green
Write-Host "  免安装目录  dist\Subtitle Studio\"
Write-Host "  安装包      installer\Subtitle Studio.msi"
