@echo off
title NovaTV AI Subtitle Server
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
"%~dp0..\.venv11\Scripts\python.exe" nova_subs.py serve --port 8765
