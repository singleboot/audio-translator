@echo off
title Audio Translator v1
chcp 65001 >nul

:: Find Python from venv or system
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

echo Starting Audio Translator v1...
echo Open http://127.0.0.1:8000 in your browser
echo Press Ctrl+C to stop.
echo.

%PYTHON% run.py
pause
