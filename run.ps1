#requires -Version 7
# Windows 启动脚本
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) {
    Write-Host "没找到 python，请先安装 Python 3.10+ 并加入 PATH" -ForegroundColor Red
    exit 1
}

try {
    python -c "import PySide6" 2>$null
    if ($LASTEXITCODE -ne 0) { throw }
} catch {
    Write-Host "缺少 PySide6，正在安装…" -ForegroundColor Yellow
    python -m pip install -r requirements.txt
}

python main.py @args
