"""Integration test: requires the supported local ISO and generated image.

Makes a full ISO copy in a fresh build/release-tests/run-* scratch directory.
Does not create a real desktop shortcut or touch an existing game installation.
"""
from pathlib import Path
import argparse
import os
import runpy
import subprocess
import uuid

here = Path(__file__).resolve().parent
build = runpy.run_path(str(here / 'build_release.py'))
root = build['ROOT']
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--iso', type=Path,
                    default=root.parent / 'Ace Combat 04 - Shattered Skies (USA).iso')
args = parser.parse_args()
out = root / 'build/release-tests'
out.mkdir(parents=True, exist_ok=True)
exe = out / 'InstallerTests.exe'
build['compile_cs'](exe, [here / 'InstallerCore.cs', here / 'Setup.cs', here / 'InstallerTests.cs'],
                    '/target:exe', '/main:InstallerTests',
                    '/win32icon:' + str(root / 'runtime/ac4.ico'),
                    '/win32manifest:' + str(here / 'setup.manifest'))
scratch = out / ('run-' + uuid.uuid4().hex[:12])
subprocess.run([str(exe), str(args.iso.resolve()), str(root / 'generated/ps2_image.bin'),
                str(build['OUT'] / 'payload.zip'), str(scratch)], check=True)
installed = scratch / 'Installed Game'
env = {k: v for k, v in os.environ.items() if not k.startswith('PS2_')}
env.update(SDL_AUDIODRIVER='dummy', PS2_SHADER_DIR=str(installed / 'runtime/shaders'),
           PS2_SAVE_DIR=str(installed / 'saves'))
with (scratch / 'installed-smoke.log').open('w') as log:
    subprocess.run([str(installed / 'runtime/ac4.exe'), '--hidden', '--data',
                    str(installed / 'runtime'), '--disc', str(installed / 'game.iso'),
                    '--vblanks', '180', '--seconds', '20', '--watchdog', '20'],
                   cwd=installed, env=env, stdout=log, stderr=subprocess.STDOUT,
                   timeout=45, check=True)
print('Installed runtime startup passed; review files:', scratch)
