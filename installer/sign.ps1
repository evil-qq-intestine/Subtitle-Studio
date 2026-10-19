#requires -Version 7
<#
  给 exe / MSI 做 Authenticode 签名。

  没有配置证书时直接跳过（退出码 0），所以放在构建流程里对开发机无影响。
  加 -Required 则在缺少证书时报错，适合发布流水线。

  证书来源（按优先级）：
    1. 环境变量 SIGN_PFX_PATH + SIGN_PFX_PASSWORD   —— pfx 文件
    2. 环境变量 SIGN_CERT_THUMBPRINT                —— 本机证书存储里的指纹
    3. 都没有                                        —— 跳过

  可选：SIGN_TIMESTAMP_URL，默认 DigiCert 时间戳（不加时间戳，证书过期后签名会失效）。
#>
param(
    [Parameter(Mandatory = $true)][string[]]$Files,
    [switch]$Required
)

$ErrorActionPreference = 'Stop'

$pfxPath = $env:SIGN_PFX_PATH
$pfxPwd = $env:SIGN_PFX_PASSWORD
$thumb = $env:SIGN_CERT_THUMBPRINT
$timestamp = if ($env:SIGN_TIMESTAMP_URL) { $env:SIGN_TIMESTAMP_URL } else { 'http://timestamp.digicert.com' }

function Find-SignTool {
    $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $kits = 'C:\Program Files (x86)\Windows Kits\10\bin'
    if (Test-Path $kits) {
        # 优先 x64，别拿到 arm64 那个
        $cand = Get-ChildItem $kits -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -match '\\x64\\' } |
                Sort-Object FullName -Descending | Select-Object -First 1
        if ($cand) { return $cand.FullName }
        $any = Get-ChildItem $kits -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
               Select-Object -First 1
        if ($any) { return $any.FullName }
    }
    return $null
}

if (-not $pfxPath -and -not $thumb) {
    if ($Required) {
        throw '要求签名，但没配置 SIGN_PFX_PATH / SIGN_CERT_THUMBPRINT'
    }
    Write-Host "未配置代码签名证书，跳过签名（SIGN_PFX_PATH / SIGN_CERT_THUMBPRINT 都为空）" -ForegroundColor Yellow
    exit 0
}

$signtool = Find-SignTool
if (-not $signtool) {
    $msg = '找不到 signtool.exe，需要安装 Windows SDK'
    if ($Required) { throw $msg }
    Write-Host "$msg，跳过签名" -ForegroundColor Yellow
    exit 0
}

$signArgs = @('sign', '/fd', 'sha256', '/tr', $timestamp, '/td', 'sha256')
if ($pfxPath) {
    $signArgs += @('/f', $pfxPath)
    if ($pfxPwd) { $signArgs += @('/p', $pfxPwd) }
} else {
    $signArgs += @('/sha1', $thumb, '/sm')
}

$failed = @()
foreach ($file in $Files) {
    if (-not (Test-Path $file)) {
        Write-Host "跳过（不存在）: $file" -ForegroundColor Yellow
        continue
    }
    Write-Host "签名 $(Split-Path $file -Leaf)" -ForegroundColor Cyan
    & $signtool @signArgs $file
    if ($LASTEXITCODE -ne 0) { $failed += $file }
}

if ($failed.Count) {
    throw "签名失败: $($failed -join ', ')"
}

foreach ($file in $Files) {
    if (-not (Test-Path $file)) { continue }
    $sig = Get-AuthenticodeSignature $file
    Write-Host ("  {0,-28} {1}" -f (Split-Path $file -Leaf), $sig.Status)
    if ($sig.Status -ne 'Valid' -and $Required) { throw "$file 签名校验未通过: $($sig.Status)" }
}
