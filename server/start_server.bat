@echo off
rem Runs the server in this window (for watching the log). For everyday use run install_autostart.bat once.
title NovaTV AI Subtitle Server
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
"%~dp0..\.venv11\Scripts\python.exe" "%~dp0nova_subs.py" serve --port 8765
