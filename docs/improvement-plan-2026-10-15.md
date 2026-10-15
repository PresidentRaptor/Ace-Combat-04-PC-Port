# AC4 improvement research and implementation plan

Prepared October 15, 2026. Inspected source revision: `b4a6771`.

## Recommendation and scope

Make campaign compatibility measurable first, then improve pacing and reliability, then prototype enhancements behind options. The strongest unconventional investment is a reproducible mission-test system that makes every discovered bug cheaper to reproduce and prevent.

This is a source inspection and external research plan. No new live playthrough, benchmark, or runtime test was performed for this report. Effort figures below are engineering estimates for one developer familiar with the code; campaign play and access to additional GPUs add calendar time. Benefits are hypotheses until measured. “New” means a proposed extension to this checkout, not a claim that nobody previously considered it.

## What the checkout already provides

- Static EE recompilation, VU execution, Vulkan GS rendering, native AC4 audio services, ISO filesystem, memory cards, SDL input, widescreen, Lua/native mods, texture replacement, and a verified-ISO installer.
- `ps2_video.c` already has pipeline disk caching, remembered pipeline keys, budgeted warm-up, CPU timing, GPU timestamp queries, and presentation-mode selection. Extend these rather than adding duplicate systems.
- `ps2_memcard.c` already checks writes, flushes to storage, replaces the previous card through a temporary file, locks cards against concurrent writers, and rejects invalid cards. The next improvement is recovery history and fault testing.
- Gamepad added/removed events already exist. The gap is verified behavior across transitions, not basic hotplug implementation.
- `dev/tools` already offers pad scripts, GS captures/replays, image comparison and transient-glitch detection. Some of this infrastructure lives outside the source repository.
- Current documentation establishes completed Mission 01 play, not complete campaign compatibility. The older root handoff contains superseded widescreen priorities; the current source docs take precedence.

## First delivery: trustworthy validation

### 1. Make render regression failures actionable — P0, 1–2 days

Evidence: `dev/tools/pngdiff.py` prints changed-pixel counts and exits successfully even on a dimension mismatch. `dev/tools/regress.sh` does not turn visual differences or missing baselines into a failed result. A printed comparison is useful for review but is not yet an automated gate.

Implementation:

1. Move maintained test utilities into `src/tools/regression/`; leave captures and baselines in a configurable local fixture directory.
2. Add explicit thresholds, dimension/format validation, nonzero failure status, JSON summaries, and propagation of replay/comparator failures. Missing required fixtures must be a failure or an explicit skip, never a pass.
3. Version a manifest with build/shader identifiers, capture hash, resolution, aspect, preset, frame number and baseline provenance.
4. Require an explicit baseline-update command and reviewer inspection of changed output.

Acceptance: intentionally alter one pixel above the configured threshold, change image dimensions, remove a baseline and force replay failure; each must produce the expected failure. An unchanged fixture suite passes. Keep exact comparisons for stable synthetic cases and separately documented tolerances for cross-driver images.

### 2. Build a campaign compatibility matrix — P0, initial 2–4 days plus playthrough

Create entries for every mission and meaningful transition: briefing, aircraft/weapons, launch, flight, mission-specific events, success/failure, results, next mission, save and reload. Track camera, aspect, resolution, GPU/driver, mods and evidence separately. Include long sessions and later-game effects rather than assuming attract demos cover them.

Use disposable copies of locally acquired progression saves. Build a scenario manifest and runner around existing `flight_run.py`, `menu_run.py`, pad scripting and log checks. Add verified mission/scene markers so scenarios wait on game state rather than only hardcoded field counts. Initial automation covers entering and running a scene; it does not establish mission completion.

Acceptance: each completed mission has documented real play, successful save/reload, relevant captures, and an associated reproducer for discovered bugs. First milestone: cover several distinct later missions and return-to-menu paths; release milestone: complete campaign traversal.

### 3. Capture the image actually presented — P0, 3–6 days

The documented replay PPM is taken before final presentation effects. Add an optional capture after resolve, FXAA, sharpening, viewport placement and UI composition. Copy the final color attachment before presentation with correct usage flags, layout transitions and synchronization; use a supported intermediate target where direct swapchain capture is unavailable.

Store scene-only and final-composited images separately. Add short multi-frame tests for stale frames, flicker, pause/resume, fullscreen, resize and rapid settings changes. Preserve the current field/display-buffer association.

Acceptance: a change to FXAA or pillarboxing changes the final capture; presentation sequences contain no unexpected old frames. Validate live as well as in replay because replay does not reproduce all scheduling behavior.

### 4. Add a two-level continuous test system — P0, 3–5 days

No `.github` directory was present at initial inspection. Concurrent local work appeared before this report finished: `.github/workflows/source-checks.yml`, `tools/run_checks.py`, `tools/test_support.py`, and `docs/compatibility.md`, among other changes. The runner already aggregates source-only checks and the compatibility document establishes an initial coverage table. Treat those as work in progress to review and extend, not missing features to recreate; they were not tested in this research task. Register suitable native tests with CTest and extend the first tier with synthetic runtime/recompiler/parser checks as needed. Add a second tier using local/private fixtures for ISO smoke tests, replay and mission scenarios. Never include disc data or captured game assets in public test artifacts.

Change the CMake musttail capability warning to a configuration failure for supported release builds: it currently warns even though the source states correctness depends on guaranteed tail calls. Record toolchain/dependency versions and shader hashes in release manifests.

Acceptance: a clean supported environment runs the synthetic suite; missing private fixtures are explicit; an unsupported compiler is rejected; release runtime and shader provenance can be reconstructed.

## Reliability and performance

### 5. Audit GPU synchronization and transitions — P1, 3–7 days

Run Vulkan synchronization validation on the regression corpus and live transition scenarios. Focus on render-target palette reads, depth/color aliasing, GPU readbacks, texture replacement, async graphics ownership and swapchain recreation. Record resource lifetime and ownership invariants near the implementation. Khronos documents synchronization validation specifically for detecting resource-access hazards [1].

Acceptance: no actionable validation errors on these scenarios across available GPU vendors. Keep async graphics opt-in until long live runs establish safety. Validation success alone is not proof of correctness.

### 6. Optimize measured frame-time bottlenecks — P1, 3–5 days for measurement

Extend `PS2_SPEED_LOG`, GPU timestamps and host profiling with exportable per-frame data: guest speed, CPU work, GPU work, fence/acquire waits, pipeline creation, texture upload, I/O latency and audio starvation. Measure cold/warm caches separately and report median/p95/p99 times and hitch counts. Document hardware and settings. The budget follows the measured guest field cadence; do not assume every content path is a 60 Hz game frame.

Use identical scenarios to evaluate synchronous/async graphics and 1x/3x/6x rendering. Treat a 10% p95/p99 improvement without correctness loss as an initial optimization acceptance target, not a predicted result.

Then choose one intervention:

- **Pipeline stalls:** improve existing warm-up with scenario-specific key lists and visible loading progress. If needed, prototype a synchronized compilation worker or optional graphics pipeline libraries. Never drop draws while waiting for a pipeline. Khronos describes pipeline caching and libraries as distinct reuse mechanisms [2,3]. Budgeted warm-up still cannot preempt one expensive compile.
- **CPU hotspots:** add optional GCC profile-generate/profile-use builds, training on diverse missions, menus, movies and audio. Start with runtime files; evaluate generated code separately. Preserve aliasing, overflow and floating-point assumptions, musttail behavior, and patchable hook entries. GCC documents PGO options [4]. Avoid global fast-math and blanket optimization-level changes.
- **Disc stalls:** instrument `ps2_vfs.c` before changing it. If reads matter, add bounded read-ahead keyed by disc identity and mod-layer generation; invalidate on mod changes. Preserve guest completion ordering and use bounded memory. Verify against uncached reads byte-for-byte.

### 7. Make saves recoverable — P1, 3–5 days

Extend existing atomic saves with a bounded history of known-good card versions, build/time metadata and a user-visible restore workflow. Use independent validated backups; never silently replace a damaged card with an empty card. Preserve the existing format and compatibility.

Inject short writes, full disk, failed replacement, truncated cards, invalid entries and concurrent launches in isolated temporary folders. Terminate a writer at several commit stages and verify that either the old or new valid card remains. Test actual save/load across mission transitions.

Acceptance: previous valid progress survives every injected failure; restore creates an inspectable backup first; normal cards remain readable by existing builds.

### 8. Keep diagnostic disk writes off the audio callback — P1, 2–4 days

`ps2_audio.c` writes WAV/stem data directly from `audio_cb` when diagnostic capture is enabled. Replace diagnostic writes with a bounded producer queue and background writer. Log dropped diagnostic blocks rather than blocking playback. Audit mixing/shared state separately; moving all mixing to another thread is a larger timing change.

SDL states audio stream callbacks may run from any thread [5]. Add starvation and callback-duration counters, device/default-output changes, pause/resume and long movie tests.

Acceptance: slow diagnostic storage does not stall playback; bounded memory use; no new audio spikes or refill-order changes.

### 9. Finish PC lifecycle behavior — P1, 3–6 days

Exercise controller disconnect/reconnect, multiple controllers, default audio changes, focus loss, fullscreen/resize, sleep/resume and unavailable graphics devices. Define recoverable versus restart-required errors and preserve saves in either case. Existing hotplug code needs tests for stuck buttons and rumble stopping on disconnect. SDL recommends supporting gamepad hotplug [6].

Add a local support-bundle export containing versions, settings, recent logs and timing summaries. Let the player inspect it; exclude saves, disc data, full memory and personal paths by default.

### 10. Improve installation and upgrades — P1, 4–7 days

The installer already validates the executable and stages installation safely. Add an upgrade/migration workflow that copies validated saves and settings into a fresh version folder, verifies runtime/shader manifests and offers rollback. Reuse the player's local ISO where safe instead of requiring another full copy. Keep a portable path option. Test paths with spaces/non-ASCII text and restrictive permissions. Start with local packages; an online updater can follow later.

Acceptance: upgrade and rollback preserve progression; incompatible settings are migrated explicitly; interrupted updates leave a playable previous version.

## Experimental work with concrete feasibility gates

### 11. A mission recorder that turns play into tests — P1 prototype, 1–2 weeks

Record input by guest field plus seed, build, disc hash, configuration, starting card hash and hashes of selected guest state at agreed boundaries. First measure determinism by repeating identical cold boots. If wall clock, audio-driven state or host scheduling causes divergence, identify and record those inputs before promising deterministic replays.

Extend capture tooling with a bounded rolling event/command history and a manual “mark problem” key. Add automatic markers for unusually long frames, unhandled syscalls and underruns. The first useful deliverable is a short reproducer from boot or a game save, not full rewind.

Acceptance: a known bug reproduces repeatedly and the runner identifies the first divergent checkpoint. A GPU command history must include the initial state and referenced data needed for replay; retaining raw commands alone is insufficient.

### 12. Differential CPU/VU testing — P1 prototype, 1–2 weeks

Generate bounded synthetic instruction sequences and compare emitted-code execution against a small independent semantic reference. Prioritize delay slots, sign extension, overflow, memory boundaries, VU paired hazards and special floating-point values. Expand decoder/dispatch coverage checks into execution checks. Add bounded mutation tests for ISO/VFS, card and texture-pack parsers.

Property-based fuzzing combines invariants with generated inputs; Google's FuzzTest provides an example of the approach [7]. Choose tooling that fits the Windows build or run portable isolated components on another test host; do not assume FuzzTest is a drop-in Windows dependency.

Acceptance: seeded known mistakes are detected and each failure reduces to a small permanent fixture. Avoid treating the same implementation copied into a test as an independent oracle.

### 13. Archive-aware modding — P2, 1–3 weeks after format study

The mod guide says AC4's `BIN/DATA.CDP` currently needs whole-file replacement. Investigate a virtual subfile overlay: index archive entries, resolve replacements by stable member identity, and intercept logical reads while preserving offsets and streaming behavior. If the game performs arbitrary physical-sector reads, this may require game-level hooks or a virtual rebuilt archive rather than a simple VFS layer.

Acceptance: replace one locally supplied asset without redistributing the full archive, allow two nonconflicting mods, and make conflicts explicit. Fall back to whole-file replacement if member identity or relocation cannot be made reliable.

### 14. Higher-quality textures through selective processing — P2, 4–8 days prototype

Improve the existing replacement workflow with contact-sheet approval, semantic categories, original-vs-replacement comparisons, mip generation, upload timing and separate decoded-RAM/GPU budgets. Detect animated/generated targets, UI and font atlases before upscaling. Preserve transparent edges, palette meaning and atlas padding. Support pack version/priority metadata.

Acceptance: demonstrate improvement on aircraft, terrain and UI examples without seams, shimmer or unreadable text; measure memory and traversal hitches. Do not auto-approve an AI upscale because it is larger.

### 15. Presentation interpolation at 120/144 Hz — P3 research, 1–2 week feasibility spike

Keep guest simulation timing fixed. Start with camera/object transform identity and two known scenes; interpolate only verified matching geometry and keep HUD, movies, discontinuities and feedback effects at original cadence. RT64 demonstrates draw matching and interpolation in an N64 renderer [8]; that architecture is inspiration, not a PS2-compatible replacement.

AC4's GS-level stream, VU transforms, alpha effects, render-target feedback and draw identity make this expensive. A native render-command/transform hook may be necessary. Reject the prototype if it cannot preserve target alignment, shadows and effects. Do not unlock simulation frame rate globally or market duplicated/generated frames as faster game logic.

### 16. Accessibility and enthusiast controls — P2, 3–7 days per validated feature

Use existing input and hook APIs for optional gyro fine aim, toggle/hold alternatives, remapping profiles and reduced vibration. Investigate text-size and contrast changes through known UI elements, not a global scale that moves target markers. Add subtitle/audio controls only after identifying the relevant game data or buses. Preserve defaults and per-feature rollback.

### 17. Adaptive resolution and wider displays — P2, separate prototypes

Use GPU timing to choose between a small set of preallocated internal resolutions with hysteresis. Preserve GS-native coordinates and feedback dependencies. Start with per-scene changes before attempting mid-scene switching. Acceptance: improved tail latency without oscillation, resource spikes or render changes beyond sampling.

For ultrawide, first audit the existing aspect math and hardcoded HUD recognition. Test culling, sea glare, target markers, menus and all camera classes. The current 16:9 fix does not prove arbitrary-aspect correctness. Keep experimental aspect ratios opt-in.

### 18. Full checkpoints, rewind, native renderer and other platforms — P3

`ps2_state.c` currently writes diagnostic snapshots; that is not a proven restore system. Complete checkpoints require CPU contexts, scheduler/threads, DMA/VIF/GIF, GS/VRAM, VU, IOP/HLE, audio decoder/refill state, filesystem handles, mods and GPU reconstruction at a safe boundary. Build save-then-restore equivalence before rewind. Disk saves remain separate.

A new native renderer could expose transforms for interpolation and modern lighting, but would need to reproduce the game's VU microcode and GS effects. Treat it as a separate research branch with a tiny scene milestone, not a replacement roadmap commitment. Ray tracing, DLSS/FSR temporal integration and HDR similarly need missing motion/depth/exposure semantics; high resolution alone does not provide them.

Linux/Steam Deck or ARM64 should begin with a dependency/ABI audit: Windows sampling profiler, runtime patching, instruction-cache flushes, executable-memory management and toolchain tail calls. Static recompilation by itself does not make the surrounding runtime portable.

## Suggested sequence and decision points

| Window | Deliverable | Completion gate |
|---|---|---|
| Week 1 | Failing regression gate, fixture manifest, compiler guard, campaign matrix | Injected regression fails; unchanged baseline passes |
| Weeks 2–3 | Later-mission scenarios, final-output capture, lifecycle/sync checks | Reproducible bugs and reviewed live transitions |
| Weeks 3–4 | Timing report, save recovery, audio diagnostics queue | Fault tests preserve progress; measured timing baseline |
| Weeks 5–6 | One evidence-selected optimization, upgrade migration | Correctness suite passes and measured benefit is retained |
| Following work | Mission recorder/differential tests; one player enhancement | Separate feasibility and acceptance gates per feature |

This is a sequencing example, not a fixed delivery promise. Full campaign validation and cross-vendor testing may extend beyond it. Do not begin all experiments concurrently. The recommended first implementation is items 1, 2 and the musttail guard in item 4; these provide immediate protection for everything that follows.

## Primary research references

1. [Khronos: synchronization validation](https://www.khronos.org/blog/a-guide-to-vulkan-synchronization-validation)
2. [Khronos: pipeline cache guide](https://docs.vulkan.org/guide/latest/pipeline_cache.html)
3. [Khronos: graphics pipeline library sample](https://docs.vulkan.org/samples/latest/samples/extensions/graphics_pipeline_library/README.html)
4. [GCC 15 optimization options](https://gcc.gnu.org/onlinedocs/gcc-15.1.0/gcc/Optimize-Options.html)
5. [SDL3 audio stream callback contract](https://wiki.libsdl.org/SDL3/SDL_AudioStreamCallback)
6. [SDL3 gamepad guidance](https://wiki.libsdl.org/SDL3/CategoryGamepad)
7. [Google FuzzTest](https://github.com/google/fuzztest)
8. [RT64 renderer and interpolation design](https://github.com/rt64/rt64)
