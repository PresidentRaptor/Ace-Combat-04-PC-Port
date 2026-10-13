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
set "PS2_SPEED_LOG=1"
set "PS2_PROFILE_PHASES=1"
set "PS2_PROFILE_GUEST=1"
set "PS2_PAD_DIAG=1"
set "PS2_TRACE_MC=1"
echo Diagnostic mode adds profiling overhead. Close the game normally for final summaries.
echo Session output is saved to diagnostics.log.
> "%~dp0diagnostics.log" echo AC4 recompiled diagnostics
>> "%~dp0diagnostics.log" echo Started %DATE% %TIME%
powershell -NoProfile -Command "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | Format-List; Get-FileHash -Algorithm SHA256 -LiteralPath 'runtime/ac4.exe' | Format-List" >> "%~dp0diagnostics.log" 2>&1
"%~dp0runtime\ac4.exe" --data "%~dp0runtime" --disc "%DISC%" --vblanks 0 --watchdog 0 >> "%~dp0diagnostics.log" 2>&1
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" exit /b 0
echo Game exited with code %RC%. Please send diagnostics.log with your report.
pause
exit /b %RC%
:missing
echo Drag your Ace Combat 04 USA ISO (SLUS-20152) onto DIAGNOSTICS.bat,
echo or put it in this folder, then double-click DIAGNOSTICS.bat.
pause
exit /b 1
