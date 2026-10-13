@echo off
setlocal
cd /d "%~dp0"
set "PATH=%~dp0..\runtime;%PATH%"
set "PS2_UI_OPEN=7"
"%~dp0build\gcc\ac4.exe" --data generated --disc "%~dp0..\Ace Combat 04 - Shattered Skies (USA).iso" --watchdog 0
