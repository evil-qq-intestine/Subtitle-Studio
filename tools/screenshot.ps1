#requires -Version 7
# 启动应用并截图（捕获 stderr 便于排错）。
param(
    [string]$Out = 'D:\subtitle translation\tools\shot.png',
    [int]$Wait = 10
)

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$root = 'D:\subtitle translation'
$log = Join-Path $root 'tools\app.log'
if (Test-Path $log) { Remove-Item $log -Force }

$proc = Start-Process -FilePath 'python' `
    -ArgumentList @('main.py') `
    -WorkingDirectory $root `
    -RedirectStandardError $log `
    -RedirectStandardOutput (Join-Path $root 'tools\app.out') `
    -PassThru -WindowStyle Normal

Start-Sleep -Seconds $Wait

try {
    $wshell = New-Object -ComObject WScript.Shell
    $null = $wshell.AppActivate($proc.Id)
} catch { }
Start-Sleep -Milliseconds 900

$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()

Write-Host "screenshot -> $Out"
Write-Host "pid=$($proc.Id) running=$(-not $proc.HasExited)"
if ((Test-Path $log) -and (Get-Item $log).Length -gt 0) {
    Write-Host "--- stderr ---"
    Get-Content $log | Select-Object -First 30
}
