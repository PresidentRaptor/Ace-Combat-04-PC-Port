# Visual regression and performance workflow

The source-only suite (`python tools/run_checks.py`) tests the comparison gate
and timing analyzer using synthetic data. It needs no game disc, graphics driver
or image library. Actual graphics tests additionally need the locally built
Windows runtime, shaders, and private captures/baselines.

## Visual gate

From the source root:

```powershell
python tools/regression/run.py --fixtures ../dev
```

`tools/regression/cases.json` identifies the 12 existing captures by SHA-256 and
pins each case's resolution, preset, widescreen setting and field limit (0 means
the complete capture). Fixtures stay outside the repository. Required captures,
baselines or shaders missing, capture hash changes, replay failure/timeout,
missing output, incomplete replay, fidelity warnings, malformed images, dimension
or channel-format changes, and image differences exceeding thresholds all fail.
There is no successful empty suite or automatic baseline creation.

The default permits channel differences of at most 16 with **zero pixels** over
that limit. Set `threshold` to 0 for exact comparisons; `allowed_pixels` explicitly
sets the number permitted over that threshold per case. RGBA comparisons include
alpha. RGB and RGBA are deliberately different formats. Supported files are
non-interlaced 8-bit RGB/RGBA PNG and binary P6/255 PPM. Unsupported formats fail.

The runner discards inherited `PS2_*` overrides and isolates working directories
to avoid personal settings, mods and textures affecting results. It disables
texture packs and the application pipeline cache. Custom scenarios belong in an
explicit manifest, not inherited environment variables. Use `--exe`, `--shaders`,
`--output`, `--manifest` and `--timeout` to select build paths and artifacts.

`out/regression/summary.json` records per-case results and executable/shader
hashes. Individual replay logs and fresh PPMs remain there for inspection.
`python tools/regression/images.py reference.png actual.ppm` is a standalone
comparator with the same exit contract and optional `--threshold` and
`--allowed-pixels` arguments.

Baseline replacement is explicit:

```powershell
python tools/regression/run.py --fixtures ../dev --update-baselines
```

Review every changed image before accepting those files. This writes PNG/PPM
baselines and JSON sidecars with capture/build/shader hashes, settings, UTC time
and rendered field count. Subsequent runs validate sidecar settings and baseline
hashes. Historical baselines without sidecars remain usable; the new run summary
records their hashes but does not invent historical build provenance. A failing
update can leave earlier successful cases updated, so review the summary and
retain fixture backups. Baseline updates are not an all-or-nothing transaction.

The legacy `../dev/tools/regress.sh` and `pngdiff.py` forward to these maintained
tools. `regress.sh baseline` maps to explicit update mode. Old arbitrary
`ENV=value` arguments are rejected; use a scenario manifest instead. `rep.sh`
now removes stale outputs and stops on replay failure.

These screenshots still cover the scene target, not all final presentation
effects. Live tests remain necessary for presentation flicker and display changes.

## Per-frame timing

Set `PS2_FRAME_TIMINGS` to a writable CSV filename for either executable. It
enables the existing renderer/GPU timing paths without needing `PS2_SPEED_LOG`.
CSV output is buffered and closed at renderer shutdown. It is optional and off
by default. `PS2_SPEED_LOG=1` also supplies existing periodic game/renderer logs.

Host rows contain a monotonically increasing frame ID, start-to-start interval,
fence/acquire/record/submit/present durations, renderer total, submit success,
whether presentation was requested, and pipeline compilation cost/count. GPU
rows use the **original submitted frame ID**, even when collected several frames
later, and split scene and presentation execution. Final completed queries are
collected after the existing shutdown idle wait. No extra per-frame GPU wait is
introduced. Missing GPU timestamp support means host-only results.

The renderer interval includes time between renderer attempts: guest preparation,
queue waits, frame pacing, warm-up and scheduling can all contribute. It is not
an isolated guest CPU time measurement. Renderer `host_ms` excludes most of that
producer work. GPU execution excludes queue backlog before its first timestamp.
`shown=1` requests presentation; it does not establish the time pixels reached a
physical display. Compilation is already part of record time, so do not add it
again. CSV writes/profiling themselves have overhead.

## Reproducible replay measurements

```powershell
python tools/regression/benchmark.py ../dev/captures/ext.gscap --output out/bench/ext-1x --resolution 1
python tools/regression/benchmark.py ../dev/captures/ext.gscap --output out/bench/ext-3x --resolution 3
python tools/regression/benchmark.py ../dev/captures/ext.gscap --output out/bench/ext-6x --resolution 6
```

Defaults are 60 passes, preset Low with explicit resolution, immediate present,
no application pipeline cache, and no mods/textures/settings from the game
folder. Change `--present` to fifo/mailbox for separately labeled paced runs.
`--cache cold` starts a fresh application cache; `--cache warm` primes that same
private cache before measurement. Driver and OS caches are not cleared. Logs,
raw CSV, final screenshot, shader/build/capture hashes, GPU/API identification,
CPU identification when available, and JSON statistics are retained.

The first pass is reported separately. Steady statistics exclude its field count
and include nearest-rank median/p95/p99, maximum, and counts over `--budget-ms`
(default 16.683333 ms, a **field budget**, not a universal game frame rate).
Pass-level times from old binaries are rounded by their existing log format;
new per-frame CSV retains microsecond-scale decimal precision. Use repeated,
sequential before/after trials without other games/benchmarks running. Do not
combine instrumented phase profiling and final performance measurements.

Replay measures captured graphics processing and cannot establish EE gameplay
performance, sync/async game-thread behavior, input latency or physical display
pacing. Use separate scripted live runs, temporary saves, `PS2_SPEED_LOG` and
the same timing CSV for those. Confirm actual mission entry in the log/capture;
pad scripts alone do not prove a particular scene was reached.

## Optional runtime profile-guided optimization

CPU sampling identified texture decode/upload and VU execution as significant
replay costs. Runtime-only GCC PGO offers a measured optimization experiment
without changing PS2 numeric semantics, generated guest code or hook sleds.
It is **off by default**. Use the same build directory for training and use:

```powershell
cmake -S . -B build/gcc -DPS2_PGO_MODE=generate
cmake --build build/gcc
# Run representative captures with gsreplay, and normal game scenarios with ac4.
# Exit each process normally so GCC writes its own profiles.
cmake -S . -B build/gcc -DPS2_PGO_MODE=use
cmake --build build/gcc
```

`PS2_PGO_DIR` overrides the profile directory. Both executables compile shared
runtime sources separately and need their own training. Include menus, movies,
flight and different missions; a replay profile does not train `ac4.exe`.
Generate mode uses atomic counters because runtime code executes across threads;
its performance is not a baseline. Use mode rejects missing/stale profiles at
compile time. After runtime source/toolchain changes, retrain from a fresh
profile directory. Do not publish private profiles: they reflect local game use.
Re-run correctness and visual checks, compare identical benchmark workloads,
then validate actual gameplay before considering release adoption.

Return to the ordinary build with `-DPS2_PGO_MODE=off` and rebuild. None of these
commands deploys the build to the player runtime or changes the release defaults.
