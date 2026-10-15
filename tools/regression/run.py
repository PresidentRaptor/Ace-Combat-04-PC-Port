"""Replay local fixtures with isolated settings and fail closed on missing evidence."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import struct
import zlib
from datetime import datetime, timezone

from images import compare

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def environment(shaders):
    # Inherited PS2_* diagnostics/overrides can invalidate a comparison.
    env = {k: v for k, v in os.environ.items() if not k.startswith('PS2_')}
    if os.name == 'nt':
        env['PATH'] = 'C:/msys64/ucrt64/bin;' + env.get('PATH', '')
    env.update(PS2_SHADER_DIR=str(shaders), PS2_TEXTURE_PACK='0',
               PS2_PIPELINE_CACHE='0', PS2_PRESENT_MODE='immediate')
    return env


def run_case(case, fixtures, exe, shaders, output, update, provenance, timeout):
    name = case['name']
    if not name or Path(name).name != name or '/' in name or '\\' in name or name in ('.', '..'):
        raise ValueError('case name must be a filename stem')
    capture = (fixtures / case['capture']).resolve()
    baseline = (fixtures / case['baseline']).resolve()
    for path in (capture, baseline):
        if not path.is_relative_to(fixtures):
            raise ValueError('fixture path escapes fixture directory')
    if digest(capture) != case['sha256']:
        raise ValueError('capture hash mismatch')
    threshold = case.get('threshold', 16)
    allowed = case.get('allowed_pixels', 0)
    if not 0 <= threshold <= 255 or allowed < 0:
        raise ValueError('invalid comparison thresholds')
    if not update and not baseline.is_file():
        raise ValueError('required baseline missing')
    metadata_path = baseline.with_suffix('.json')
    if not update and metadata_path.exists():
        saved = json.loads(metadata_path.read_text())
        expected = dict(capture_sha256=case['sha256'], preset=case['preset'],
                        resolution=case['resolution'], widescreen=case.get('widescreen', False),
                        fields=case.get('fields', 0), baseline_sha256=digest(baseline))
        if any(saved.get(key) != value for key, value in expected.items()):
            raise ValueError('baseline provenance/settings mismatch')
    # Never accept an output left by a failed or previous replay.
    shot = output / (name + '.ppm')
    if shot.resolve() in (baseline, capture):
        raise ValueError('output image would overwrite a fixture')
    shot.unlink(missing_ok=True)
    command = [str(exe), str(capture), '--hidden', '--preset', str(case['preset']),
               '--shot', str(shot)]
    if case.get('fields'):
        command += ['--fields', str(case['fields'])]
    if case.get('widescreen', False):
        command += ['--widescreen']
    env = environment(shaders)
    env['PS2_UPSCALE'] = str(case['resolution'])
    with tempfile.TemporaryDirectory(prefix='ac4-replay-') as cwd:
        with (output / (name + '.log')).open('w') as log:
            subprocess.run(command, cwd=cwd, env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=timeout)
    if not shot.is_file():
        raise ValueError('replay succeeded without producing an image')
    replay_log = (output / (name + '.log')).read_text(errors='replace')
    match = re.search(r'\[REPLAY\] pass 1: (\d+) fields', replay_log)
    declared = re.search(r': level \w+, (\d+) fields,', replay_log)
    if (not match or int(match[1]) == 0 or '[REPLAY] done;' not in replay_log
            or '[REPLAY] FIDELITY:' in replay_log or '[REPLAY] bad record' in replay_log):
        raise ValueError('incomplete replay or recorded-command fidelity failure; see log')
    if declared:
        expected = min(int(declared[1]), case.get('fields') or int(declared[1]))
        if int(match[1]) != expected:
            raise ValueError('replayed field count differs from capture/limit')
    from images import read_image
    width, height, channels, pixels = read_image(shot)
    metadata = dict(provenance, capture_sha256=case['sha256'], preset=case['preset'],
                    resolution=case['resolution'], widescreen=case.get('widescreen', False),
                    fields=case.get('fields', 0), rendered_fields=int(match[1]),
                    baseline_sha256=digest(shot))
    if update:
        contents = shot.read_bytes()
        if baseline.suffix.lower() == '.png':
            def chunk(tag, data):
                return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag+data))
            stride = width * channels
            raw = b''.join(b'\0' + pixels[i:i+stride] for i in range(0, len(pixels), stride))
            contents = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',
                        width, height, 8, 2 if channels == 3 else 6, 0, 0, 0))
                        + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
        elif baseline.suffix.lower() != '.ppm':
            raise ValueError('baseline path must use .png or .ppm')
        baseline.parent.mkdir(parents=True, exist_ok=True)
        temp = baseline.with_suffix(baseline.suffix + '.tmp')
        temp.write_bytes(contents)
        temp.replace(baseline)
        metadata['baseline_sha256'] = digest(baseline)
        baseline.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n')
        return dict(passed=True, updated=True)
    return dict(compare(baseline, shot, threshold, allowed),
                baseline_sha256=digest(baseline), actual_sha256=digest(shot),
                capture_sha256=case['sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'tools/regression/cases.json')
    parser.add_argument('--exe', type=Path, default=ROOT / 'build/gcc/gsreplay.exe')
    parser.add_argument('--shaders', type=Path, default=ROOT / 'build/gcc/shaders')
    parser.add_argument('--output', type=Path, default=ROOT / 'out/regression')
    parser.add_argument('--update-baselines', action='store_true')
    parser.add_argument('--timeout', type=float, default=180)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        manifest = json.loads(args.manifest.read_text())
        if manifest.get('version') != 1:
            raise ValueError('unsupported manifest version')
        cases = manifest['cases']
        if not cases or len({c['name'] for c in cases}) != len(cases):
            raise ValueError('manifest must contain unique, nonempty cases')
        provenance = dict(created_utc=datetime.now(timezone.utc).isoformat(),
                          executable_sha256=digest(args.exe),
                          shaders={p.name: digest(p) for p in sorted(args.shaders.glob('*.spv'))})
        if not provenance['shaders']:
            raise ValueError('shader directory is empty')
        for case in cases:
            try:
                result = run_case(case, args.fixtures.resolve(), args.exe.resolve(),
                                  args.shaders.resolve(), output, args.update_baselines,
                                  provenance, args.timeout)
            except (OSError, ValueError, KeyError, zlib.error, struct.error, subprocess.SubprocessError) as exc:
                result = dict(passed=False, error=str(exc))
            results.append(dict(name=case['name'], **result))
            print(case['name'], json.dumps(result), flush=True)
    except (OSError, ValueError, KeyError) as exc:
        results.append(dict(name='setup', passed=False, error=str(exc)))
    summary = dict(passed=bool(results) and all(r['passed'] for r in results), cases=results,
                   provenance=locals().get('provenance', {}))
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
