# Visual regression and runtime PGO results — October 15, 2026

Implemented the visual failure gate, optional per-frame timing CSV, isolated
benchmark runner, and opt-in runtime-only GCC profile-guided optimization.
The ordinary build remains the default. Benchmarking did not deploy a player
runtime or change release defaults.

## Test machine and method

- AMD Ryzen 9 9950X3D, NVIDIA GeForce RTX 5090.
- Windows display driver registry version `32.0.16.1714`; Vulkan API `1.4.351`.
- MSYS2 UCRT64 GCC 16.2.0, existing Release optimization settings.
- Control and candidate contain the same timing implementation and shaders.
  PGO changes only compilation of the shared runtime; generated guest code,
  third-party libraries, arithmetic settings and patchable entries are unchanged.
- Three private captures: `ext` (6 fields), `snow` (16), `aircraft` (30).
  Forty passes per case/build, Low preset with explicit 1x/3x/6x resolution,
  hidden Vulkan window, immediate presentation, application pipeline cache off,
  replacement textures/mods disabled, isolated working directories.
- First pass excluded from steady statistics. Each build/case contributes
  234, 624 or 1,170 steady renderer intervals respectively. Percentiles use
  nearest rank. Runs were sequential, with no concurrent game/benchmark training.
- The same scenes were included in PGO training: these are improvements on
  trained workloads, not evidence of generalization to unseen missions.

CPU sampling of 60 `ext` passes found substantial time in texture decode,
texture uploads and interpreted VU execution. Of all 4,036 samples, 9.39% were
attributed to `current_texture_inner`, 8.33% to `trx_data_px`, and 27.65% combined
to `vu_run`, `vu_lower`, `vu_upper` and `vu_set_flags`. Another 31.74% was outside
the executable, including drivers/waiting. Sampling and phase profiling were
separate from final measurements. This favored a CPU compilation experiment
over a speculative renderer rewrite or higher GPU throughput work.

## Main paired results

Numbers below are **renderer start-to-start intervals**, in milliseconds.
They include producer/CPU work and can include replay snapshot restoration and
scheduling between attempts. They are not physical display latency or isolated
guest CPU measurements.

| Scene | Resolution | Median control → PGO | Median reduction | p95 control → PGO | p99 control → PGO |
|---|---|---|---|---|---|
| Flight | 1x | 10.847 → 9.899 | 8.7% | 13.376 → 12.286 | 13.917 → 12.543 |
| Flight | 3x | 11.348 → 10.091 | 11.1% | 14.017 → 12.578 | 15.516 → 13.485 |
| Flight | 6x | 10.849 → 9.991 | 7.9% | 13.519 → 12.280 | 14.052 → 12.621 |
| Snow | 1x | 11.869 → 10.796 | 9.0% | 14.146 → 13.191 | 14.692 → 13.806 |
| Snow | 3x | 11.863 → 10.728 | 9.6% | 14.212 → 13.079 | 15.529 → 13.347 |
| Snow | 6x | 11.860 → 10.973 | 7.5% | 14.119 → 13.176 | 14.918 → 13.483 |
| Aircraft select | 1x | 18.242 → 16.782 | 8.0% | 20.167 → 18.508 | 21.832 → 20.041 |
| Aircraft select | 3x | 18.259 → 16.700 | 8.5% | 20.346 → 18.713 | 22.029 → 20.039 |
| Aircraft select | 6x | 18.247 → 16.712 | 8.4% | 20.291 → 18.664 | 21.710 → 20.436 |

GPU medians were essentially unchanged: for example, flight at 6x was
2.468 → 2.473 ms, and aircraft select at 6x was 1.726 → 1.724 ms. This supports
the CPU-side explanation. No graphics work is removed and no draws are skipped
by the optimization.

The aircraft-select replay still exceeds the 16.683333 ms field budget at its
median and tail. Its 1x intervals above that budget fell from 1,170/1,170 to
725/1,170, but that is not a claim of full-speed gameplay. Small flight/snow
hitch counts were mixed (for example, snow 6x: 2 → 4), so reduced median/p95
does not establish elimination of transient stalls.

## Reversed-order repeats and cache checks

Twenty-pass 1x repeats ran PGO first, then control, reversing the main matrix's
ordering. Median control → PGO: flight 10.739 → 10.303 ms (4.1% reduction),
snow 11.852 → 10.648 ms (10.2%), aircraft select 18.212 → 16.593 ms (8.9%).
All three still favored PGO, but the smaller flight gain demonstrates run-to-run
variation. These short trials do not justify a universal speedup claim.

Separate twenty-pass flight/6x cache trials:

| Application cache | First-pass ms/field control → PGO | Steady median interval control → PGO | Steady p95 control → PGO |
|---|---|---|---|
| Fresh | 27.53 → 25.27 | 10.613 → 9.722 | 13.005 → 12.118 |
| Primed | 23.67 → 22.83 | 10.709 → 9.735 | 13.107 → 12.037 |

Warm runs explicitly verified loading the primed cache and its 35 remembered
pipeline states. No new pipelines were created in these steady samples and all
submitted host samples had matching GPU samples. Driver/OS caches were not
cleared; this is **not** a driver-cold compilation benchmark. First-pass costs
must not be treated as a general shader-stutter improvement from PGO.

## Correctness and failure-gate verification

- All 15 source-only checks pass, including six image-gate tests and two timing
  analysis tests. The image tests cover all five PNG scanline filters, CRC/
  truncation rejection, alpha, thresholds, size mismatch, empty suite, missing
  baseline, replay failure/timeout, stale output, missing screenshot, explicit
  baseline update, provenance mismatch and output/fixture collision protection.
- All 12 existing private capture/baseline comparisons pass with PGO: maximum
  channel difference is **0**, even though the configured tolerance is 16.
  The original baselines were not replaced.
- Final PPMs from ordinary and PGO builds are byte-identical for every one of
  the nine scene/resolution pairs in the main matrix.
- Recorded GS-command fidelity warnings: zero in measured runs.
- Optimized `ac4.exe --vu-test --novideo`: all cases pass.
- Optimized ISO startup smoke: exits successfully after 180 delivered vblanks.
  Its diagnostic report records two dropped startup fields; this short smoke
  does not validate presentation pacing or establish a change in that count.
- Profile collection also completed a disposable scripted 14,100-vblank game
  session. Instrumented training speed is not a performance result, and a pad
  script does not certify mission completion.
- Ordinary Windows build succeeds with `PS2_PGO_MODE=off`; generated/use modes
  were also compiled and exercised. A Windows lock on the training replay
  executable required retaining it under a separate local filename before
  replacing the build output. The final default build is an ordinary build.
- The legacy Python comparator/crop import path was exercised successfully.
  Git Bash could not start in this sandbox (MSYS `NtCreateDirectoryObject`
  access denied), so the forwarding shell wrapper was inspected but not run.
  The maintained Python regression entry point was run directly throughout.

## Reproduction and artifacts

See [the workflow](regression-and-performance.md) for commands, format contracts,
PGO training instructions and limitations. Reuse the same private fixture hashes
in `tools/regression/cases.json`; keep game data out of public artifacts.

Local evidence under the source root:

- `out/performance/matrix/`: 18 main runs, each with raw CSV, replay log, final
  image and JSON statistics containing executable/capture/shader hashes.
- `out/performance/followup/`: reversed-order and application-cache trials.
- `out/performance/profile/`: host samples and initial diagnostic log.
- `out/performance/control/` and `out/performance/pgo/`: retained comparison
  binaries; optimized runtime self-test and startup logs are under `pgo/`.
- `out/performance/image-equivalence.json`: nine exact file-equivalence checks.
- `out/regression-pgo-final/summary.json`: final 12-case image gate.
- `out/performance/train-flight/`: disposable instrumented training session.

Recommendation: retain PGO as an opt-in build option while collecting more
missions and hardware. The measured CPU improvement is useful, but it does not
yet establish campaign-wide gains, physical display latency, sync/async game
thread performance or full correctness on other GPU vendors. The regression
gate and timing tools can be used immediately with ordinary builds.
