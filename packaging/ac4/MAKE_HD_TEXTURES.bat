@echo off
setlocal
cd /d "%~dp0"
rem Upscales the textures saved with "Save textures for upscaling" (F4 menu,
rem Rendering) from textures\dump into textures\hd\upscaled with Real-ESRGAN.
rem Needs Python 3 with Pillow (py -m pip install Pillow) and the Windows
rem realesrgan-ncnn-vulkan build unpacked in tools\realesrgan
rem (https://github.com/xinntao/Real-ESRGAN/releases).
set "TOOL=%~dp0src\tools\texture_pack.py"
set "ESRGAN=%~dp0tools\realesrgan\realesrgan-ncnn-vulkan.exe"
if not exist "%TOOL%" (
  echo Cannot find src\tools\texture_pack.py next to this file.
  goto end
)
if not exist "%ESRGAN%" (
  echo Real-ESRGAN is not in tools\realesrgan.
  echo Download realesrgan-ncnn-vulkan-...-windows.zip from
  echo https://github.com/xinntao/Real-ESRGAN/releases and unpack it there.
  goto end
)
if not exist "textures\dump\*.pam" (
  echo No saved textures in textures\dump yet. In the game, open F4,
  echo Rendering, tick "Save textures for upscaling" and play for a while.
  goto end
)
python "%TOOL%" upscale "textures\dump" --output "textures\hd\upscaled" --esrgan "%ESRGAN%"
if errorlevel 1 echo Upscaling failed; see the messages above.
:end
pause
