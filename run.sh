#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

echo "Starting Audio Translator v1..."
echo "Open http://127.0.0.1:8000 in your browser"
echo "Press Ctrl+C to stop."
echo ""

exec "$PYTHON" run.py
