@echo off
rem Starts the NovaTV AI subtitle server now and at every Windows sign-in (hidden, restarts itself if it stops).
rem Safe to run from anywhere: the shortcut always points to this folder's supervisor.py.
cd /d "%~dp0"
"%~dp0..\.venv11\Scripts\python.exe" "%~dp0supervisor.py" install
pause
