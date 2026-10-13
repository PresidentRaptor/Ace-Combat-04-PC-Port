@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
set "DISC=%~1"
if not defined DISC if exist "game.iso" set "DISC=%~dp0game.iso"
if not defined DISC if exist "game\SYSTEM.CNF" set "DISC=%~dp0game"
if not defined DISC for %%I in ("%~dp0*.iso") do if not defined DISC set "DISC=%%~fI"
if not defined DISC goto missing
if not exist "%DISC%" goto missing
for /f "delims==" %%V in ('set PS2_ 2^>nul') do set "%%V="
set "PS2_SHADER_DIR=%~dp0runtime\shaders"
set "PS2_SAVE_DIR=%~dp0saves"
echo Ace Combat 04: Shattered Skies - recompiled
echo Disc: %DISC%
echo Session output is saved to last-play.log.
"%~dp0runtime\ac4.exe" --data "%~dp0runtime" --disc "%DISC%" --vblanks 0 --watchdog 0 > "%~dp0last-play.log" 2>&1
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" exit /b 0
echo Game exited with code %RC%. Please send last-play.log with your report.
pause
exit /b %RC%
:missing
echo Drag your Ace Combat 04 USA ISO (SLUS-20152) onto PLAY.bat,
echo or put it in this folder, then double-click PLAY.bat.
pause
exit /b 1
