#!/usr/bin/env bash
# Linux / macOS 启动脚本
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "没找到 python3，请先安装 Python 3.10+"
  exit 1
fi

if ! python3 -c "import PySide6" >/dev/null 2>&1; then
  echo "缺少 PySide6，正在安装…"
  python3 -m pip install -r requirements.txt
fi

exec python3 main.py "$@"