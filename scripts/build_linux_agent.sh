#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-python3}"
NAME="${NAME:-console-agent}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"

if [ ! -d ".venv" ]; then
  "$PYTHON" -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r ./console_agent/requirements-build.txt

pyinstaller \
  --onefile \
  --clean \
  --name "$NAME" \
  --add-data "console_agent/browser_client.js:console_agent" \
  ./run_console_agent.py

echo
echo "Built ./dist/$NAME"
echo "Client Linux PCs can run:"
echo "./dist/$NAME --host 127.0.0.1 --port 9001"
