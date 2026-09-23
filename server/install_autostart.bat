@echo off
rem Starts the NovaTV subtitle server minimised every time you log in to Windows.
set LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\NovaTV Subtitle Server.lnk
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LNK%');$s.TargetPath='%~dp0start_server.bat';$s.WorkingDirectory='%~dp0';$s.WindowStyle=7;$s.Save()"
echo Autostart installed: %LNK%
pause
