#requires -Version 7
# 构建 MSI 安装包。路径全部相对脚本位置，换台机器/CI 也能跑。
# WiX 3 的工具链不在系统里，首次运行会自动从 NuGet 拉一份（约 40MB）。
$ErrorActionPreference = 'Stop'

$inst = $PSScriptRoot
$root = Split-Path $inst -Parent
$wixRoot = Join-Path $root 'build\wix'
$wix = Join-Path $wixRoot 'tools'
$obj = Join-Path $inst 'obj'
$wxl = Join-Path $inst 'en-us.wxl'
$msi = Join-Path $inst 'Subtitle Studio.msi'
$dist = Join-Path $root 'dist\Subtitle Studio'

if (-not (Test-Path $dist)) {
    throw "没找到 $dist，请先运行 ..\build.ps1（或 -SkipMsi 只打包）"
}

New-Item -ItemType Directory -Force -Path $obj | Out-Null

# ---------------------------------------------------------------- WiX 工具链
function Ensure-Wix {
    if (Test-Path (Join-Path $wix 'candle.exe')) { return }
    Write-Host "首次运行：下载 WiX 3.14 工具链…" -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $wixRoot | Out-Null
    $nupkg = Join-Path $wixRoot 'wix.3.14.1.nupkg'
    if (-not (Test-Path $nupkg)) {
        # 微软的 NuGet CDN，比 GitHub Releases 稳定（后者在国内经常卡住）
        $url = 'https://api.nuget.org/v3-flatcontainer/wix/3.14.1/wix.3.14.1.nupkg'
        Invoke-WebRequest -Uri $url -OutFile $nupkg -UseBasicParsing
    }
    $tmp = Join-Path $wixRoot 'extract'
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive -Path $nupkg -DestinationPath $tmp -Force
    Copy-Item (Join-Path $tmp 'tools') $wix -Recurse -Force
    Remove-Item $tmp -Recurse -Force
    if (-not (Test-Path (Join-Path $wix 'candle.exe'))) { throw 'WiX 解压后找不到 candle.exe' }
    Write-Host "WiX 就绪: $wix" -ForegroundColor Green
}
Ensure-Wix

# ---------------------------------------------------------------- 本地化
# en-us 是 WiX 的源语言，字符串内嵌在扩展 DLL 里，正常不需要补。
# 万一真缺了，下面的循环会把它补进 en-us.wxl；再缺就直接报错，
# 免得界面上出现 WixUIBack 这种键名。
$en = @{}

if (-not (Test-Path $wxl)) {
    @"
<?xml version="1.0" encoding="utf-8"?>
<WixLocalization Culture="en-us" xmlns="http://schemas.microsoft.com/wix/2006/localization">
</WixLocalization>
"@ | Set-Content -Path $wxl -Encoding utf8
}

# ---------------------------------------------------------------- 收集文件
Write-Host "收集文件…" -ForegroundColor Cyan
Push-Location $inst
& (Join-Path $wix 'heat.exe') dir "$dist" -cg AppFiles -gg -g1 -sfrag -srd `
    -dr INSTALLDIR -var var.SourceDir -out "$obj\Files.wxs" 2>&1 | Out-Null
$heatOk = $LASTEXITCODE -eq 0
Pop-Location
if (-not $heatOk -or -not (Test-Path "$obj\Files.wxs")) { throw 'heat 失败' }

# ---------------------------------------------------------------- 编译链接
$added = @{}
for ($round = 1; $round -le 20; $round++) {
    Push-Location $inst
    $candleOut = & (Join-Path $wix 'candle.exe') -arch x64 -dSourceDir="$dist" `
        Product.wxs "$obj\Files.wxs" -out "$obj\" 2>&1
    $candleOk = $LASTEXITCODE -eq 0
    Pop-Location
    if (-not $candleOk) {
        Write-Host ($candleOut -join "`n")
        throw 'candle 失败'
    }

    Push-Location $inst
    $out = & (Join-Path $wix 'light.exe') -ext WixUIExtension -cultures:en-us -loc $wxl `
        -spdb -sice:ICE61 "$obj\Product.wixobj" "$obj\Files.wixobj" -out $msi 2>&1
    $lightOk = $LASTEXITCODE -eq 0
    Pop-Location
    if ($lightOk) { Write-Host "light 成功（第 $round 轮）"; break }

    $text = $out -join "`n"
    $missing = [regex]::Matches($text, 'localization variable !\(loc\.([A-Za-z0-9_.]+)\)') |
               ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique

    if (-not $missing) {
        Write-Host $text
        throw '有错误但没找到缺失的本地化变量'
    }

    $new = @()
    foreach ($id in $missing) {
        if ($added.ContainsKey($id)) { continue }
        $added[$id] = $true
        $value = $en[$id]
        if (-not $value) {
            throw "缺少本地化字符串 $id，请补到 en-us.wxl"
        }
        $new += "  <String Id=`"$id`">$([System.Security.SecurityElement]::Escape($value))</String>"
    }
    Write-Host "第 $round 轮：补 $($new.Count) 条（累计 $($added.Count)）"

    $content = Get-Content $wxl -Raw
    $content = $content -replace '</WixLocalization>', ($new -join "`n") + "`n</WixLocalization>"
    Set-Content -Path $wxl -Value $content -Encoding utf8
}

if (Test-Path $msi) {
    $mb = [math]::Round((Get-Item $msi).Length / 1MB, 1)
    Write-Host "MSI: $msi  ($mb MB)"
} else {
    throw '没有生成 MSI'
}

