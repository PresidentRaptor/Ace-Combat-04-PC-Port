"""Run the supported source-only checks; never reads a game ISO or generated data."""
from pathlib import Path
import subprocess
import sys

from test_support import compiler_environment

root = Path(__file__).resolve().parents[1]
_, env = compiler_environment()
(root / 'out').mkdir(exist_ok=True)
checks = [
    'test_ac4_audio.py', 'test_ac4_widescreen.py', 'test_ac4_texture_pool.py',
    'test_patch.py', 'check_gs_sampling.py', 'check_upload_streams.py',
    'check_indexed_blocks.py', 'check_cloud_graphics.py', 'check_readback_protocol.py',
    'check_playtest_input.py', 'check_gfxq_model.py', 'check_texture_index.py',
    'check_review_fixes.py',
]
for name in checks:
    print('\nRunning ' + name, flush=True)
    subprocess.run([sys.executable, str(root / 'tools' / name)], cwd=root, env=env, check=True)
print('\nAll %d source-only checks passed. Full Windows/game validation is separate.' % len(checks))
