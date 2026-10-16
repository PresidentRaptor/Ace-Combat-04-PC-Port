"""Package a built Windows runtime, never the user's ISO or generated image.

Run from the source checkout: python packaging/ac4/installer/build_release.py
Requires the normal UCRT64 build, .NET Framework csc, and dependency DLLs.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
VERSION = '2.2.1-beta'
BUILD = ROOT / 'build/gcc'
OUT = ROOT / 'build/release' / VERSION
STAGE = OUT / 'payload'
CSC = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
UCRT = Path(os.environ.get('AC4_UCRT_DIR', 'C:/msys64/ucrt64'))


def copy(source, relative):
    dest = STAGE / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def compile_cs(output, sources, *options):
    subprocess.run([str(CSC), '/nologo', '/optimize+', '/platform:x64',
                    '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll',
                    '/r:System.IO.Compression.dll', '/r:System.IO.Compression.FileSystem.dll',
                    '/out:' + str(output), *options, *map(str, sources)], check=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # The only recursively removed directory is the known generated payload.
    assert STAGE.resolve() == (ROOT / 'build/release' / VERSION / 'payload').resolve()
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir()
    copy(BUILD / 'ac4.exe', 'runtime/ac4.exe')
    for name in ['SDL3.dll', 'libwinpthread-1.dll', 'libiconv-2.dll']:
        copy(UCRT / 'bin' / name, 'runtime/' + name)
    for name in ['gs.vert', 'gs.frag', 'present.vert', 'present.frag',
                 'gs_zcopy.frag', 'colclip.frag']:
        copy(BUILD / 'shaders' / (name + '.spv'), 'runtime/shaders/' + name + '.spv')
    for name in ['DIAGNOSTICS.bat']:
        copy(HERE.parent / name, name)
    copy(HERE / 'INSTALL.txt', 'README.txt')
    copy(HERE / 'INSTALL.txt', 'INSTALL.txt')
    copy(HERE / 'release-settings.ini', 'runtime/ac4_settings.ini')
    copy(ROOT / 'LICENSE', 'licenses/PROJECT-Apache-2.0.txt')
    copy(ROOT / 'third_party/imgui/LICENSE.txt', 'licenses/Dear-ImGui-MIT.txt')
    copy(ROOT / 'third_party/lua/LICENSE.html', 'licenses/Lua-MIT.html')
    for package in ['SDL3', 'libwinpthread', 'libiconv']:
        directory = UCRT / 'share/licenses' / package
        for file in directory.rglob('*'):
            if file.is_file():
                copy(file, Path('licenses') / package / file.relative_to(directory))
    (STAGE / 'licenses/ATTRIBUTION.txt').write_text(
        'Ace Combat 04 PC Port\n'
        'Shared recompiler/runtime derived from sal063\'s Ace Combat 5 static recompilation.\n'
        'https://github.com/sal063/Ace-Combat-5-Static-recompilation\n'
        'AC4 changes: https://github.com/PresidentRaptor/Ace-Combat-04-PC-Port\n'
        'See the accompanying project and third-party license files.\n', encoding='utf-8')
    compile_cs(STAGE / 'Ace Combat 04.exe', [HERE.parent / 'launcher/Launcher.cs'],
               '/target:winexe', '/win32icon:' + str(ROOT / 'runtime/ac4.ico'))
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    (STAGE / 'release.json').write_text(json.dumps({'version': VERSION, 'commit': commit,
        'game': 'SLUS-20152', 'memory_image_included': False}, indent=2) + '\n', encoding='utf-8')
    files = sorted(p for p in STAGE.rglob('*') if p.is_file())
    for file in files:
        assert file.suffix.lower() not in ['.iso', '.bin', '.gscap', '.pam', '.png']
        assert not any(part in ['saves', 'generated', 'textures'] for part in file.relative_to(STAGE).parts)
    (OUT / 'payload-manifest.json').write_text(json.dumps([
        {'path': p.relative_to(STAGE).as_posix(), 'size': p.stat().st_size,
         'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files], indent=2) + '\n', encoding='utf-8')
    payload = OUT / 'payload.zip'
    with zipfile.ZipFile(payload, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in files:
            archive.write(file, file.relative_to(STAGE).as_posix())
    setup = OUT / ('Ace-Combat-04-PC-Port-' + VERSION + '-Setup.exe')
    compile_cs(setup, [HERE / 'InstallerCore.cs', HERE / 'Setup.cs'], '/target:winexe',
               '/win32icon:' + str(ROOT / 'runtime/ac4.ico'),
               '/win32manifest:' + str(HERE / 'setup.manifest'),
               '/resource:' + str(payload) + ',payload.zip')
    (OUT / 'SHA256SUMS.txt').write_text(hashlib.sha256(setup.read_bytes()).hexdigest() +
                                     '  ' + setup.name + '\n', encoding='ascii')
    print('Built', setup)
    print('Payload:', len(files), 'files; no ISO or memory image')


if __name__ == '__main__':
    main()
