#!/usr/bin/env bash
set -euo pipefail

echo "============================================"
echo " Audio Translator v1 — One-Click Installer"
echo "============================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "[ERROR] Python is not installed or not on PATH."
    echo "Please install Python 3.10+ from https://python.org"
    exit 1
fi
PYTHON=$(command -v python3 || command -v python)

echo "[1/5] Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "       .venv already exists, skipping."
else
    $PYTHON -m venv .venv
fi

echo "[2/5] Activating virtual environment..."
source .venv/bin/activate

echo "[3/5] Upgrading pip..."
pip install --upgrade pip --quiet

echo "[4/5] Installing core dependencies..."
pip install -r requirements.txt || {
    echo "[WARNING] Some core dependencies failed to install."
    echo "          The app may still work with limited functionality."
}

echo "[5/5] Setup complete!"
echo ""
echo "============================================"
echo " How to launch:"
echo "   bash run.sh"
echo "   OR manually: .venv/bin/python run.py"
echo "============================================"
echo ""
echo " Optional: install Indic-Parler-TTS for Indian languages"
echo "   pip install git+https://github.com/huggingface/parler-tts.git"
echo ""
