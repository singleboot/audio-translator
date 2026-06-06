@echo off
title Audio Translator v1 — Setup
chcp 65001 >nul

echo ============================================
echo  Audio Translator v1 — One-Click Installer
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not on PATH.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [1/5] Creating virtual environment...
if exist ".venv" (
    echo        .venv already exists, skipping.
) else (
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [2/5] Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [3/5] Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1

echo [4/5] Installing core dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Some core dependencies failed to install.
    echo          The app may still work with limited functionality.
)

echo [5/5] Setup complete!
echo.
echo ============================================
echo  How to launch:
echo    run.bat
echo    OR manually: .venv\Scripts\python run.py
echo ============================================
echo.
echo  Optional: install Indic-Parler-TTS for Indian languages
echo    .venv\Scripts\pip install git+https://github.com/huggingface/parler-tts.git
echo.
pause
