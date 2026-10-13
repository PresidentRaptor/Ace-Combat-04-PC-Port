@echo off
rem Builds "Ace Combat 04.exe" in the game folder using the C# compiler built into Windows.
cd /d "%~dp0"
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
set "ICON="
if exist "icon.ico" set "ICON=/win32icon:icon.ico"
"%CSC%" /nologo /target:winexe /optimize+ %ICON% /r:System.Windows.Forms.dll /out:"..\Ace Combat 04.exe" Launcher.cs
if errorlevel 1 pause
