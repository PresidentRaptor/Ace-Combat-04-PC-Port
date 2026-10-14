from pathlib import Path
import os
import subprocess
import shutil
import sys

root = Path(__file__).resolve().parents[1]
out = root / 'out' / 'settings_test'
out.mkdir(parents=True, exist_ok=True)
exe = out / 'settings_test.exe'
ini = out / 'settings_test.ini'

subprocess.run(['gcc', '-std=gnu2x', '-O1', '-fno-strict-aliasing', '-fwrapv',
                '-Wall', '-Wextra', '-Wno-unused-parameter',
                '-I' + str(root / 'runtime/include'),
                str(root / 'tools/settings_test.c'),
                str(root / 'runtime/src/ps2_settings.c'),
                '-lSDL3', '-lm', '-o', str(exe)], check=True)
if ini.exists():
    ini.unlink()
if os.name == 'nt':
    # The packaged runtime already carries SDL and its dependencies. Keep the
    # console test runnable without an interactive missing-DLL error dialog.
    for dll in (root.parent / 'runtime').glob('*.dll'):
        shutil.copy2(dll, out / dll.name)
subprocess.run([str(exe)], check=True, env=dict(os.environ, PS2_SETTINGS_FILE=str(ini)))
