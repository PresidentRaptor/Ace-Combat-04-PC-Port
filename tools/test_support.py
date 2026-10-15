"""Compiler discovery for game-data-free tests on Windows and Linux."""
import os
from pathlib import Path
import shutil


def compiler_environment():
    env = os.environ.copy()
    ucrt = Path('C:/msys64/ucrt64/bin')
    if os.name == 'nt' and ucrt.is_dir():
        env['PATH'] = str(ucrt) + os.pathsep + env.get('PATH', '')
    compiler = shutil.which(env.get('CC', 'gcc'), path=env.get('PATH'))
    if not compiler:
        raise RuntimeError('GCC is required for these checks; put it on PATH or set CC.')
    return compiler, env
