"""Isolated replay benchmark: first pass and warmed passes, with raw timing evidence."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

from run import ROOT, digest, environment


def statistics(values, budget=16.683333):
    if not values:
        return None
    ordered = sorted(values)
    def percentile(p):
        return ordered[max(0, math.ceil(len(ordered)*p)-1)]
    return dict(samples=len(values), median_ms=percentile(.5), p95_ms=percentile(.95),
                p99_ms=percentile(.99), max_ms=max(values),
                over_budget=sum(v > budget for v in values), budget_ms=budget)


def summarize(path, skip_frames, budget):
    with path.open() as file:
        rows = list(csv.DictReader(file))
    host = [r for r in rows if r['kind'] == 'host' and int(r['frame']) > skip_frames]
    gpu = [r for r in rows if r['kind'] == 'gpu' and int(r['frame']) > skip_frames]
    if not host or any(r['submitted'] != '1' for r in host):
        raise ValueError('missing host rows or failed submissions')
    host_ids = {r['frame'] for r in host}
    gpu_ids = {r['frame'] for r in gpu}
    if len(host_ids) != len(host) or len(gpu_ids) != len(gpu) or not gpu_ids <= host_ids:
        raise ValueError('duplicate frame IDs or GPU rows without matching host submissions')
    def column(records, key):
        return statistics([float(r[key]) for r in records], budget)
    return dict(host={k: column(host, k) for k in ('interval_ms', 'host_ms', 'fence_ms',
                'acquire_ms', 'record_ms', 'submit_ms', 'present_ms', 'compile_ms')},
                gpu={k: column(gpu, k) for k in ('gpu_ms', 'scene_ms', 'upscale_ms')},
                new_pipelines=sum(int(r['new_pipelines']) for r in host),
                gpu_samples_missing=len(host_ids-gpu_ids))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--exe', type=Path, default=ROOT/'build/gcc/gsreplay.exe')
    parser.add_argument('--shaders', type=Path, default=ROOT/'build/gcc/shaders')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--loops', type=int, default=60)
    parser.add_argument('--resolution', type=int, choices=range(1, 9), default=1)
    parser.add_argument('--preset', type=int, choices=range(4), default=0)
    parser.add_argument('--present', choices=['immediate', 'fifo', 'mailbox'], default='immediate')
    parser.add_argument('--cache', choices=['off', 'cold', 'warm'], default='off')
    parser.add_argument('--budget-ms', type=float, default=16.683333)
    parser.add_argument('--timeout', type=float, default=240)
    args = parser.parse_args()
    if args.loops < 2 or args.budget_ms <= 0:
        parser.error('need at least two loops and a positive field budget')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for filename in ('frames.csv', 'summary.json', 'last.ppm'):
        (output/filename).unlink(missing_ok=True)
    env = environment(args.shaders.resolve())
    env.update(PS2_SPEED_LOG='1', PS2_UPSCALE=str(args.resolution),
               PS2_FRAME_TIMINGS=str(output/'frames.csv'), PS2_PRESENT_MODE=args.present)
    command = [str(args.exe.resolve()), str(args.capture.resolve()), '--hidden', '--loop',
               str(args.loops), '--preset', str(args.preset), '--shot', str(output/'last.ppm')]
    # A new temporary cwd prevents accidental settings/mod/texture reuse. A warm
    # cache is primed by this command under the same private cache prefix.
    with tempfile.TemporaryDirectory(prefix='ac4-bench-', dir=output) as cwd:
        env['PS2_PIPELINE_CACHE'] = '0' if args.cache == 'off' else str(Path(cwd)/'pipelines')
        if args.cache == 'warm':
            with (output/'prime.log').open('w') as log:
                subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                               check=True, timeout=args.timeout)
        with (output/'run.log').open('w') as log:
            subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=args.timeout)
    text = (output/'run.log').read_text()
    passes = re.findall(r'\[REPLAY\] pass (\d+): (\d+) fields in .*?\(([\d.]+) ms/field\)', text)
    if len(passes) != args.loops or any(int(p[1]) <= 0 for p in passes):
        raise ValueError('incomplete benchmark passes')
    if '[REPLAY] FIDELITY:' in text:
        raise ValueError('benchmark differs from recorded commands; reject its performance result')
    if args.cache == 'warm' and 'vk: pipeline cache loaded (' not in text:
        raise ValueError('warm benchmark did not load its primed application cache')
    if not (output/'last.ppm').is_file():
        raise ValueError('benchmark did not produce its final screenshot')
    fields = int(passes[0][1])
    summary = dict(executable_sha256=digest(args.exe), capture_sha256=digest(args.capture),
                   shaders={p.name: digest(p) for p in sorted(args.shaders.glob('*.spv'))},
                   resolution=args.resolution, preset=args.preset, present=args.present,
                   cache=args.cache, loops=args.loops, fields_per_pass=fields,
                   first_pass_ms_per_field=float(passes[0][2]),
                   warmed_pass_ms_per_field=statistics([float(p[2]) for p in passes[1:]], args.budget_ms),
                   hardware=[line for line in text.splitlines() if line.startswith('vk: ') and '(API ' in line],
                   fidelity_warnings=text.count('[REPLAY] FIDELITY:'),
                   cpu=os.environ.get('PROCESSOR_IDENTIFIER', 'unavailable'),
                   notes='Renderer interval includes producer/CPU/wait work; host_ms is renderer only. '
                         'Hidden replay does not measure physical display latency or gameplay guest CPU. '
                         'Cold means application pipeline cache only; driver/OS caches are uncontrolled.')
    timing = output/'frames.csv'
    if timing.exists():
        summary['steady_frames'] = summarize(timing, fields, args.budget_ms)
    else:
        summary['steady_frames'] = None  # Supports comparison to pre-instrumentation binaries.
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
