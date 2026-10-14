@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
set "DISC=%~1"
if not defined DISC for %%I in ("%~dp0*.iso") do if not defined DISC set "DISC=%%~fI"
if not defined DISC goto missing
if not exist "%DISC%" goto missing
if not exist "%~dp0runtime\ac4-edge-test.exe" goto missing
for /f "delims==" %%V in ('set PS2_ 2^>nul') do set "%%V="
set "PS2_SHADER_DIR=%~dp0runtime\edge-test-shaders"
set "PS2_SETTINGS_FILE=%~dp0runtime\ac4-edge-test.ini"
set "PS2_SAVE_DIR=%~dp0saves"
set "PS2_TEXTURE_PACK=off"
echo Ace Combat 04 - native rendering and edge-smoothing test
echo Use F4 to compare FXAA and UI filtering. Output: edge-test.log
"%~dp0runtime\ac4-edge-test.exe" --data "%~dp0runtime" --disc "%DISC%" --vblanks 0 --watchdog 0 > "%~dp0edge-test.log" 2>&1
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" exit /b 0
echo Game exited with code %RC%. See edge-test.log.
pause
exit /b %RC%
:missing
echo This launcher needs runtime\ac4-edge-test.exe and your Ace Combat 04 USA ISO.
echo Drag the ISO onto this file, or put it beside the launcher.
pause
exit /b 1
