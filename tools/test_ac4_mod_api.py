"""Exercise the AC4 mod API and legacy aliases in the built Windows runtime."""
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / 'out' / 'ac4_mod_api'
out.mkdir(parents=True, exist_ok=True)
mods = out / 'mods'
for name, legacy in [('canonical', False), ('legacy', True)]:
    directory = mods / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'mod.toml').write_text('native = true\ngame = "SLUS-20152"\nabi = 3\n')
    prefix = 'ac5' if legacy else 'ac4'
    source = directory / 'module.c'
    source.write_text(f'''#include "{prefix}mod.h"
#include <string.h>
__declspec(dllexport) int {prefix}_mod_main(const {prefix}_api *api) {{
    if (api->abi_version < {prefix.upper()}_ABI_VERSION ||
        strcmp(api->game_id, "SLUS-20152")) return 1;
    api->log("{name} native API passed");
    return 0;
}}
''')
    subprocess.run(['gcc', '-shared', '-Wall', '-Werror',
                    '-I' + str(root / 'runtime/include'), str(source),
                    '-o', str(directory / 'module.dll')], check=True)

(mods / 'canonical' / 'script.lua').write_text('''
assert(ac4 == ac5)
assert(ac4.game_id == "SLUS-20152")
assert(ac4.abi_version >= 3)
assert(ac4.BTN.l1 == 1024 and ac5.BTN.r3 == 4)
ac4.after(1, function() ac4.log("canonical Lua callback passed") end)
ac5.after(2, function() ac5.log("legacy Lua callback passed") end)
''')
env = os.environ.copy()
env["PATH"] = str(root.parent / "runtime") + os.pathsep + env.get("PATH", "")
for key in list(env):
    if key.startswith('PS2_'):
        del env[key]
env.update(PS2_MOD_DIR=str(mods), PS2_SAVE_DIR=str(out / 'saves'),
           PS2_SETTINGS_FILE=str(out / 'settings.ini'),
           PS2_SHADER_DIR=str(root.parent / 'runtime/shaders'),
           PS2_TEXTURE_PACK='off', SDL_AUDIODRIVER='dummy')
run = subprocess.run([str(root / 'build/gcc/ac4.exe'), '--hidden',
                      '--data', str(root / 'generated'), '--disc',
                      str(root.parent / 'Ace Combat 04 - Shattered Skies (USA).iso'),
                      '--vblanks', '180', '--seconds', '20', '--watchdog', '20'],
                     cwd=root, env=env, capture_output=True, timeout=60)
log = (run.stdout + run.stderr).decode(errors='replace')
(out / 'runtime.log').write_text(log)
assert run.returncode == 0, f'Runtime failed: {run.returncode}; see {out}'
for marker in ['canonical native API passed', 'legacy native API passed',
               'canonical Lua callback passed', 'legacy Lua callback passed']:
    assert marker in log, f'Missing {marker}; see {out}'
assert 'failed to load:' not in log, f'Lua load failure; see {out}'
print('AC4 native/Lua API and legacy compatibility passed')
