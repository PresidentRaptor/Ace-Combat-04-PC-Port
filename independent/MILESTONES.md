# Completion milestones

Status: M0 and M1 complete; M2, M3 and M4 in progress. No independent playable build yet.
Progress is measured by passed gates, not lines written or guessed percentages.

| ID | Status | Deliverable | Completion gate |
| --- | --- | --- | --- |
| M0 | Complete | Isolated development area, provenance rules, audit and plan | New branch from main; existing port preserved; replacement scope recorded |
| M1 | Complete | Independent AC4 executable and disc inspection | ELF reader tested; supported disc executable validated locally; ISO reader extracts/verifies executable; reference manifest recorded |
| M2 | In progress | R5900 decoding and static analysis | Instruction classes, branch/delay-slot behavior and indirect targets verified with synthetic and AC4-derived cases |
| M3 | In progress | CPU translation and minimal execution harness | Deterministic C generation; arithmetic, memory, exceptions and call dispatch verified against an independent oracle; repeatable AC4 translation |
| M4 | In progress | Boot services | Memory, kernel, interrupts, disc services, SIF and input reach stable interactive menus with a basic graphics path |
| M5 | Pending | Graphics fallback and vector units | VIF/VU/GS behavior renders menus, hangar and flight correctly; captures match documented reference scenes |
| M6 | Pending | Sound, movies and persistent saves | AC4 sound protocols, streaming and movie sync work; saves reload across process restarts and mission transitions |
| M7 | Pending | First complete playable mission | Mission 01 starts and completes with correct input, visuals, sound and save/load; repeatable regression checks |
| M8 | Pending | Native AC4 flight renderer | Aircraft, terrain, objects, sky, lighting, shadows and flight HUD have verified native paths; effects/fallback compose correctly |
| M9 | Pending | Windows product and performance | Reproducible fresh-disc installation, settings, widescreen and controllers; measured frame pacing; no AC5 inputs or imports |
| M10 | Pending | Campaign and provenance acceptance | Full campaign and unlock/save flows tested; remaining defects recorded; all shipped components have reviewed origins and notices |

Stages overlap: M4 needs early M5 rendering; sound and saving can develop before
M5 is complete. Native rendering starts after a reliable reference path exists.
M10 is the completion gate for the requested outcome.

## Current evidence

- Branch: independent-ac4, created from main.
- Independent ELF and ISO inspectors implemented; 10 synthetic test methods pass, including malformed inputs and rejection of unsupported game data.
- Direct ISO validation passed on 2026-10-15. Executable size: 3,248,756 bytes; SHA-256 matches the supported USA image. Metadata is recorded in reference-image.json.
- A standalone scalar CMake harness exists. Kernel/device runtime and renderer are pending.

## Progress updates

For each milestone record: what changed, commands run, observed results, remaining
failures and acceptance evidence. Do not mark a stage complete from source review
alone. No schedule is committed before translation and boot risks are measured.

## M1 validation (2026-10-15)

Commands run from the repository root:

```
python -B -m unittest discover -s independent/tests -v
python -B independent/ac4_disc.py "../Ace Combat 04 - Shattered Skies (USA).iso"
```

Results: 10 tests passed. Disc executable identity accepted. Entry 0x00100008;
one load segment at 0x00100000, 3,217,196 file-backed bytes and 765,984
zero-fill bytes. No executable payload was written or added to Git.
ISO support is deliberately limited to plain 2048-byte-sector ISO9660,
single-volume contiguous files and root executable lookup. It is not yet the
runtime disc filesystem, a full integrity scan, or support for compressed images.

## Next: M2

1. Record primary R5900 instruction references and validation sources.
2. Implement an independent decoder, explicitly rejecting unsupported encodings.
3. Test scalar control flow and delay slots before adding MMI, FPU and COP2.
4. Inventory instruction encodings directly from verified AC4 executable ranges.
5. Recover branches and indirect control flow without the old symbol maps.

## M2a cloud validation (2026-10-15)

Base: `independent-ac4` at `617943e`; changes confined to `independent/`.
Implemented the bounded scalar decoder, contextual delay-slot/likely edges,
explicit link metadata, unresolved indirect/return edges, speculative call
continuations, partial reachability, candidate-word inventory and CLI adapters
to the existing verified ELF/ISO readers. Primary Sony hardware references,
exact supported groups and unsupported encodings are in PROVENANCE.md.

Commands run from the repository root:

```
python -B -m unittest discover -s independent/tests -v
python -B independent/r5900_analysis.py --base 0x1000 --words 50850002 24020007 0000000d 03e00008 00000000 --summary
git diff --check
```

Observed: 34 test methods pass (10 existing and 24 new); synthetic CLI succeeds;
whitespace check passes. New scenarios cover signed/backward branches, PC+4
jump-region boundaries, 32-bit PC/link wrap, fixed-zero fields and undefined
aliases, explicit exceptions, direct/indirect calls, unresolved returns and
other paths after returns, contextual slots, taken/untaken likely effects,
missing/unsupported/forbidden slots, loops and independent slot entries.
A synthetic-identity ELF adapter test checks file-backed executable selection
and exclusion of non-executable data/zero-fill without changing production
identity requirements. No inherited implementation or AC5 code was used.

Gaps and remaining M2 acceptance evidence:

- No cloud game files exist; **no AC4-derived decoding or analysis validation
  was performed**. M1's earlier local identity result does not validate M2a.
- MMI, FPU, COP2/VU, COP0 and remaining EE-specific encodings are unsupported.
  Unknown/reserved words stop traversal with diagnostics rather than NOPs.
- No register propagation, jump-table recovery, complete function boundaries,
  exception-vector resolution or full exception/control-flow model exists.
  Indirect targets remain unresolved; continuations do not prove returns.
- Candidate inventory is not executable/data classification or coverage.
  Synthetic graph behavior is not independent CPU execution-oracle evidence.
- Run the exact PowerShell ISO/ELF commands in README.md on the PC, review
  diagnostic boundaries and AC4-derived cases, then record metadata/counts and
  findings here. No fabricated local results, Windows/Vulkan or campaign claims.

M2 stays **In progress**. M2a's bounded cloud implementation and synthetic tests
are ready for review; remaining instruction groups and local AC4 acceptance
must pass before M2 can be completed. No PR was opened; any future PR must target
`independent-ac4`, never `main`.

## M2a local review and M2b continuation (2026-10-15)

Fetched and reviewed cloud commit `79d72cb`; fast-forwarded the clean local
independent-ac4 branch. All 34 cloud tests passed on local Python 3.11.0.
The verified local ISO adapter passed. Baseline entry analysis visited five
addresses and stopped at 0x00100018 because SQ was unsupported.

Implemented M2b locally:

- Quadword LQ/SQ and SA register forms MFSA/MTSA/MTSAB/MTSAH.
- COP1 transfers, supported FCR restrictions, BC1 branches/likely forms,
  LWC1/SWC1, single-precision arithmetic/accumulator/compare/conversion decoding.
  SQRT uses ft; other unary operations use fs. CTC1 permits only FCR31.
- ELF section selection excludes allocated data even within the single RWX
  load segment, and ignores nonallocated vendor/debug sections. Stripped
  executables retain an explicitly reported load-segment fallback. Invalid
  executable section extents, alignments, overlaps and mappings are rejected.
- Repeatable metadata-only local verification in validate_ac4.py. Five AC4
  cases cover backward branch, direct call, unresolved return, integer likely
  annulment and FP likely annulment. Branch opcode fields and target arithmetic
  were separately checked from disc bytes against the hardware descriptions.

Validation commands from repository root:

```
python -B -m unittest discover -s independent/tests -v
python -B independent/validate_ac4.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso"
git diff --check
```

Observed: **48 tests pass**, all five static disc checks pass, identity matches
the unchanged supported SHA-256. Two executable sections at 0x00100000 and
0x00297c00 contain 422,413 candidate words (previous whole-segment inventory:
804,299). Current decoder accepts 412,068 and rejects 10,345 candidates.
These are encoding inventory counts, not verified code or execution coverage.

Entry analysis now visits 23 addresses, decodes 24 including contextual slots,
and records 24 edges with no unsupported-instruction diagnostic. It ends at
the explicit SYSCALL at 0x00100064. This is a correct analysis boundary for
the current exception model, **not evidence of booting or executing AC4**.

Reviewed local cases (metadata only; no words/guest source committed):

| Address | Instruction | Target | Slot |
| --- | --- | --- | --- |
| 0x0010002c | BNE | 0x00100018 | ADDIU |
| 0x00100084 | JAL | 0x0026b2d0 | SLL |
| 0x001000c8 | JR ra | Unresolved | ADDIU |
| 0x00100354 | BEQL | 0x0010036c | ANDI |
| 0x001027e0 | BC1TL | 0x001027f4 | LWC1 |

Remaining: packed MMI, COP0/COP2/VU decoding, CACHE/PREF, unsupported encodings,
register propagation and jump tables, full indirect-target acceptance, and an
independent execution oracle. Local static checks do not validate floating-point
arithmetic, memory access, timing, syscall execution, graphics or gameplay.
M2 remains **In progress**; M3 and later stages remain pending.

## M2c continuation (2026-10-15)

Implemented packed MMI groups and secondary HI/LO forms, basic COP0
transfers/branches, interrupt/TLB/exception-return decoding and PREF. Added
COP2 transfers, interlock fields, LQC2/SQC2, CPU branches, common vector
arithmetic/broadcast/scalar forms, VI arithmetic and VU0 microprogram calls.

ERET terminates the EE normal-flow graph with an unresolved exception-return
edge and no delay slot. ERET in a branch delay slot blocks the executed path;
an untaken likely branch can still annul it. VCALLMS starts separate VU0
microcode without inventing an EE branch or delay slot.

Validation: independent suite **65 tests pass** on local Python 3.11.0;
the supported ISO passes the original five flow cases plus eight new
MMI/system/VU candidate checks. Sources and implementation limits are recorded
in PROVENANCE.md. No game words or generated guest source are committed.

Commands from repository root:

```
python -B -m unittest discover -s independent/tests -v
python -B independent/validate_ac4.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso"
git diff --check
```

Local section inventory: 422,413 candidate words; 418,587 accepted encodings,
3,826 rejections (previous 10,345). Remaining rejection categories:
817 fixed-field violations, 206 unsupported/reserved SPECIAL, 14 COP0,
2,756 COP2 and 33 CACHE. Counts include possible embedded data and are not
execution coverage. Entry analysis still stops at SYSCALL 0x00100064;
23 visited addresses/24 decoded including slots/24 edges, no diagnostics.

**Next:** extended VU macro forms and CACHE/system selectors, then conservative
register/indirect-target recovery. Full execution semantics/oracle evidence and
boot services are still absent. M2 remains In progress; later milestones pending.

## M2d extended decoding and first target analysis (2026-10-15)

Added extended VU macro decoding from individual primary encoding pictures:
accumulator forms, conversions/moves, component-selected Q operations, VU
loads/stores, random forms, VNOP/VWAITQ and integer/vector transfers. Added
the documented CACHE operations and COP0 debug/performance selectors.
Unknown encodings still fail; numerical/privilege/timing execution is absent.

The local section-name inspection identified the second executable section as
`.vutext`: 19,712 bytes of separate VU microcode. It is now classified and
reported separately, rather than inventoried as EE instructions. EE `.text`
contains **417,485** candidate words: **417,481** accepted encodings and **four**
fixed-field rejections at 0x00273d80/84/88/8c. These repeated candidates remain
rejected. They are not silently treated as instructions or used to claim
complete executable/data separation. Earlier whole-executable inventory counts
are historical and included VU words. No execution coverage percentage is inferred.

Added conservative GPR constant propagation on the partial graph. Tests cover
word sign extension, zero-register writes, source changes in delay slots, JALR,
branch joins, likely annulment, loop convergence, load/transfer invalidation,
call clobbering and independently seeded entries. Target values are sampled
before links/slots; unresolved values remain unresolved. Reports do not extend
the graph and make no assumptions about ABI preservation or loaded pointers.

Validation: **86 tests pass** on local Python 3.11.0, **19 static local checks
pass** against the verified USA ISO, and whitespace checks pass. Commands:

```
python -B -m unittest discover -s independent/tests -v
python -B independent/validate_ac4.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso"
python -B independent/r5900_analysis.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso" --summary --seed-direct-calls --resolve-indirects
git diff --check
```

The additional seeded analysis uses **2,955 candidate entries** and visits
287,299 addresses (325,367 decoded including slots), producing 322,367 edges,
662 blocked edges and one distinct diagnostic at 0x00273d80. Its 3,193 register
transfer sites yield **zero proved constant destinations**. The 662 blocked
edges are retained boundaries, not successful paths. Calls/returns and syscall
semantics are not established merely by graph traversal. Default startup-only
analysis remains bounded by the explicit SYSCALL at 0x00100064.

**Next:** recover bounded jump tables/function-pointer targets from independently
verified AC4 patterns, account for analysis boundaries, and add an independent
execution oracle before progressing to translation/runtime acceptance. M2
remains **In progress**; no independent playable build exists.


## M2e jump-table candidates and M3a native scalar harness (2026-10-15)

Added strict guarded absolute-table recognition using initial non-writable ELF
sections. Guards, scaling, register aliases, known external entries, exact bounds,
file mappings and destination alignment are checked. The verified local image
contains **77 candidates, 1,562 entries and 702 distinct destinations** under this
one pattern. Global guard dominance and runtime immutability are not proven;
these candidates do not add assumed edges to normal analysis. Stripped images
cannot establish the section property. Other table/function-pointer forms remain.

Added a new deterministic C11 scalar translator, flat-memory CPU state, bounded
execution and standalone CMake target. Each supplied instruction becomes C for
its guest address; unsupported operations reject generation. Implements scalar
integer arithmetic/shifts/comparisons, branches/likely/link/indirect dispatch,
loads/stores including both LQ/SQ halves, HI/LO transfers, multiply/accumulate
and divide in both banks. Word results sign-extend the lower 64 GPR bits while
preserving the upper 64. Native synthetic tests check independently calculated
outcomes, overflow, address faults, slot timing/annulment, links, HI/LO separation,
endianness, zero register and budget/resume. Undefined arithmetic inputs stop
with a host diagnostic. These stops are not guest CP0 exception delivery.

Commands from repository root (GCC-compatible compiler required for native checks):

```
python -B -m unittest discover -s independent/tests -v
python -B independent/validate_ac4.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso"
python -B independent/r5900_analysis.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso" --summary --recover-switches
python -B independent/validate_native_ac4.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso" --cc C:/msys64/ucrt64/bin/gcc.exe
cmake -S independent -B ../dev/build-independent -G Ninja -DCMAKE_C_COMPILER=C:/msys64/ucrt64/bin/gcc.exe -DCMAKE_BUILD_TYPE=Release
cmake --build ../dev/build-independent
ctest --test-dir ../dev/build-independent --output-on-failure
git diff --check
```

Observed locally: **114 tests pass**, including 18 native compilation/execution
methods (20 codegen methods total); **19 static disc checks pass**; standalone
CMake configure/build and **1/1 CTest pass** using GNU C 16.2.0. Native tests compile
with C11, optimization and warnings treated as errors. CI now requires a compiler
rather than silently skipping native tests, and also builds/runs the CMake target.
Remote CI execution is separate from these local observations.

Verified-image entry translation selects **24 addresses**. Native execution runs
**335,107 attempted instructions**, clears poisoned startup RAM 0x00411780 through
0x004cc75f, and stops at **SYSCALL 0x00100064**, with syscall register v1=60,
v0=0x004cc760 and gp=0x004159f0. The original ELF load mapping initializes private
32 MiB RAM. Expected startup results were calculated from reviewed fields and
loop behavior, not physical-hardware traces or a separate CPU emulator. The
validator generates source/RAM/executable in a temporary directory and removes
it afterward. No game payload or generated guest source is added to Git.

M2 and M3 remain **In progress**. This is a bounded scalar execution check, not
successful syscall execution, boot, menus or gameplay. Missing M3 gates include
an independent CPU oracle, full exceptions/privilege/device memory semantics,
remaining instruction execution (FPU/MMI/VU/system), complete dispatch recovery
and larger repeatable translation. M4-M10 remain pending. Existing derived code
and its notices are preserved until the replacement passes its acceptance gates.


## M3b / M4a local bootstrap diagnostic (2026-10-15)

A native Windows startup diagnostic can now be built directly from the supported
user's disc. It remains **NOT PLAYABLE**. Neither a passing compiler nor a
successful diagnostic package is the M4/menu or M10/campaign acceptance gate.

New independent work:

- All eight scalar unaligned load/store merge operations, checking only touched
  bytes and preserving untouched register/memory bytes. Paired loads/stores,
  every offset, both load orders, bounds and zero destinations are tested.
- Opt-in EE data-memory mapping for RAM cached/uncached/accelerated aliases and
  16 KiB scratchpad, plus explicit device read/write callbacks. No MMU,
  privilege checks or cache timing is inferred from these address mappings.
- Disabled EE timer register behavior, including 16-bit counters and mode flag
  write-one-to-clear. Active timer enable and unsupported device accesses stop;
  no fake advancing clock, IRQ or DMA completion is supplied.
- Provisional single-thread SetupThread/SetupHeap, CreateSema, cache-coherent
  FlushCache and guest syscall-patch registration. The documented timer-3 patch
  index 0x12c is stored explicitly, without out-of-bounds host table writes.
- Optional bounded ordinary-function bridge for registered guest handlers,
  including nested shadow return frames, caller ra restoration and budget
  boundaries. This does not model a BIOS exception frame/CP0 privilege switch.
- Bounded static selection with explicit unsupported-operation stops. Selected
  syscall continuations are not claims that services succeed. Compiled game
  instructions are checked against current RAM before execution; changed code
  stops instead of running stale generated C.
- Explicit observed code-copy mappings. Only specified file-backed source
  ranges are translated at the supplied runtime destination. The destination
  starts unloaded and the guest must actually copy matching bytes before its
  instruction guards pass. This is not arbitrary data/code classification.

Sources and important uncertainty are recorded in PROVENANCE.md. In particular,
PS2tek's stack/heap descriptions and the observed sentinel arguments do not
provide a complete authoritative ABI; the automatic stack and heap policy
remains experimental pending an independent hardware/emulator trace. These
service-policy tests validate the declared model, not BIOS equivalence.

Validation commands (repository root; fresh output directory required):

```
python -B -m unittest discover -s independent/tests -v
python -B independent/validate_ac4.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso"
python -B independent/validate_native_ac4.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso" --cc C:/msys64/ucrt64/bin/gcc.exe
cmake --build ../dev/build-independent
ctest --test-dir ../dev/build-independent --output-on-failure
python -B independent/build_bootstrap.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso" --output ../dev/ac4-bootstrap-verified-a --cc C:/msys64/ucrt64/bin/gcc.exe --limit 2048 --entry 0x264a88 --copied-code 0x3fabd8:0x80076000:1856
git diff --check
```

Observed: **152 independent tests pass**, with native compiler required;
**19 static disc checks pass**; original first-syscall native acceptance still
passes; **2/2 CTest pass**. GNU C 16.2.0 builds both standalone targets with
warnings as errors. CI's existing default build now covers both synthetic
runners, including invalid-input rejection by the native RAM loader.

The AC4 package selects 2,048 addresses with 12 pending selection addresses and
four explicit unsupported instruction boundaries. The additional entry
0x00264a88 and copy 0x003fabd8 -> 0x80076000 (1,856 bytes) were derived from
fresh observed syscall arguments and decoded against the user's verified image.
No legacy symbol maps were used. The guest's copy handler and copied alarm
patch execute with instruction-byte checks enabled.

The measured run reaches **339,303 attempted instructions and 23 completed
modeled service calls**, stopping with status 32 (unknown service) at
**0x00263ea4: CreateThread (32 decimal)**. It has no thread scheduler, menus,
graphics, input, audio or mission execution. Enlarging the selection limit
would not fix this missing service. No later behavior is claimed.

Two fresh local builds have identical native executable SHA-256
`690b550675d44c6e5e4944bc9afd9de5e99940934001d8b5882a2d9b2db1e1a3`,
RAM SHA-256 and observations. GNU PE timestamps are disabled in this builder.
This measures reproducibility on the same local toolchain, not across hosts or
compiler versions. Metadata only is committed in reference-bootstrap.json;
private executable/RAM outputs stay outside Git. Import inspection shows only
Windows system/UCRT DLLs, and the artifact runs without the compiler on PATH.
Native exit 2 is an incomplete execution boundary, never a successful game exit.

**Next:** thread creation/context/scheduling and semaphore waits, fuller kernel
exception/interrupt semantics, active timers and COP0/remaining CPU execution,
then SIF/disc/device services. Validate the provisional bootstrap policy against
an independent oracle before closing M3/M4. M2/M3/M4 stay In progress; M5-M10
remain pending. No independent playable build is ready.


## M4b cooperative scheduling and local continuation (2026-10-15)

Implemented a bounded 256-slot cooperative thread model from published kernel
ABI documentation: dormant thread creation/deletion, start/exit/delete-exit,
priority changes, equal-priority ready-queue rotation, current-thread identity,
sleep/wake and pending wake counts. Added semaphore delete/signal/wait/poll with
explicit blocking. No runnable thread returns diagnostic IDLE (38), not success
or a fabricated wake-up. Unsupported suspend/terminate/status APIs remain stops.

Context switches preserve the implemented CPU state: both 64-bit halves of all
GPRs, both HI/LO banks, PC, partial Status state and nested guest syscall-return
frames. Memory, scratchpad, devices and the global instruction budget remain
shared. No floating-point/vector context is claimed while those execution
families remain unsupported. New threads inherit heap/process settings and
use the documented parameter structure; stack alignment/initial layout, return
values and FIFO semaphore wait ordering remain provisional model policies until
an independent scheduler trace is available.

EI/DI now implement the EE manual's conditional EIE-bit changes for kernel,
EDI, EXL and ERL states. They do not deliver interrupts or establish a complete
COP0 privilege/exception implementation. Added 128-bit PAND/POR/PXOR/PNOR and
PCPYLD/PCPYUD/PCPYH execution with source sampling before alias writes. These
unblocked the title's early memory initialization routines.

Validation: **167 independent tests pass** with the native compiler required;
**2/2 CTest pass**; **19 static disc checks pass** and the original native
first-syscall check still passes. New scheduler tests verify priority-driven
switch/return, full GPR halves and HI/LO preservation, argument/GP delivery,
sleep/wake preemption, semaphore handoff, FIFO rotation, no-ready-thread stops,
invalid inputs, bounded global budgets and nested syscall frames across switches.
EI/DI mode cases and packed logical/copy aliases are checked independently.
These are implementation-model checks, not hardware-oracle acceptance.

The local AC4 run now gets past CreateThread/StartThread and EI, recording
**two context switches**, **29 completed modeled service calls**, and
**339,768 attempted instructions**. Its next boundary is a missing selected
instruction at **0x0027c844**, reported as FETCH (3). This is a translation-map
boundary, not evidence of an invalid guest address. The current map selects
16,384 addresses; unsupported system/FPU/vector/packed operations remain
explicit. No menus, rendering or gameplay have been reached.

Command for this exact diagnostic (choose a fresh output directory):

```
python -B independent/build_bootstrap.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso" --output ../dev/ac4-bootstrap-local-scheduler --cc C:/msys64/ucrt64/bin/gcc.exe --limit 16384 --entry 0x264a88 --entry 0x1001a4 --entry 0x27c680 --copied-code 0x3fabd8:0x80076000:1856
```

Additional entry seeds were observed as missing PCs during guarded local runs
and verified in the supported CPU image. They are code-selection seeds, not
proved function boundaries or complete indirect-target recovery. A smaller
bounded selection can stop earlier, including at a missing slot; adding seeds
can change what fits within the limit. Current metadata is in
reference-bootstrap.json. Larger diagnostic maps now compile at **O0** to bound
compiler latency; synthetic execution tests retain optimized native compilation.
No performance or new cross-build reproducibility result is inferred.

**Next:** expand verified dispatch selection for observed initialization paths,
COP0/FPU/vector execution and remaining kernel/device services; independently
validate scheduler and startup ABI policies. M2/M3/M4 remain In progress. The
local diagnostic is still not a playable build, and later milestones stay open.


## M2f / M3c / M4c guarded replay and SIF initialization (2026-10-15)

Implemented bounded observation-driven static rebuild/replay. A FETCH stop can
add code only from the verified CPU image or explicitly declared code-copy
ranges. Existing translated addresses are retained, modified instruction bytes
are not accepted, and unsupported operations remain diagnostic stops. Each
replay restarts from the original RAM/process state; it does not continue a
half-executed service or interpret unknown opcodes. These observed destinations
are model-dependent evidence, not a complete indirect dispatch proof.

Added a deterministic per-4-KiB C translation-unit backend with the same CPU
instruction emission as the single-file backend. Stable pages retain native
objects across discovery rounds; changes to shared headers invalidate them.
Compilation uses bounded parallel jobs and a linker response file for Windows
command-length limits. Runtime inputs are snapshotted before compilation.
Tests cover cross-page targets/slots/fault context, likely annulment, budgets,
128-bit state, stable generation and changed-page/header cache invalidation.
This is a static translator, not a runtime opcode interpreter.

CPU extensions from primary hardware descriptions:

- Packed byte/halfword/word wrapping add/subtract, equality and signed-greater
  comparisons, plus signed halfword/word min/max. Tests cover carry isolation,
  negative extrema, complete lane masks, both GPR halves and source aliases.
- MFC0/MTC0 for Status only, including sign extension and access gating.
  Other COP0 registers and full privilege/exception delivery remain unsupported.
- Raw COP1 register/control/memory transfers, MOV.S and BC1 branches/likely
  forms. CU1-disabled accesses stop diagnostically, even for a zero GPR
  destination. FPR/FCR31 state is preserved across thread switches. FCR0 and
  numerical floating-point operations still stop; host IEEE arithmetic is not
  substituted for the EE numerical model.

The application runner now explicitly starts with Status **0x20000000** (CU1
usable, kernel-mode functional profile). This is an experimental configured
state, **not a captured BIOS handoff value**. The observed profile is included
in the manifest and still requires independent validation.

Added inactive DMA/INTC configuration with documented masks, interrupt status
acknowledgement and mask toggles; bounded interrupt handler registration/removal
and enable/disable services; SifSetDChain and SIF register services. SIF0 can be
armed in destination-chain mode and remains busy waiting for incoming data.
No payload, completion or interrupt is fabricated. Outgoing DMA, active timers
and pending IRQ delivery still stop. EE writes set its own mailbox flags and
clear IOP-owned flags; they cannot create IOP readiness. Software SIF slots are
separate from physical registers. Some kernel return policies, including the
SetReg prior-value return, remain provisional rather than BIOS-oracle results.

Validation: **199 tests pass** with a required native compiler; **19 static disc
checks pass**, the original native first-syscall check passes, and **2/2 CTest
pass**. Both C backends are exercised on synthetic inputs; generated code is
compiled with warnings treated as errors. No remote CI result is inferred.

Exact local build (fresh destination required):

```
python -B independent/build_bootstrap.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso" --output ../dev/ac4-bootstrap-io-wait-verified --cc C:/msys64/ucrt64/bin/gcc.exe --limit 16384 --entry 0x264a88 --entry 0x1001a4 --entry 0x27c680 --copied-code 0x3fabd8:0x80076000:1856 --discover-fetches 32 --discovery-limit 512 --jobs 4
```

The run performs **10 discovery extensions**, retaining **18,520 translated
addresses** in the final map. The initial 60-unit compilation took 3.345 seconds;
the final replay compiled two units, reused 82, and took 0.431 seconds plus
0.166 seconds linking on this local toolchain. These are build measurements,
not game performance or cross-host reproducibility evidence.

AC4 now reaches its SIF command-initialization wait. At 0x0026baa8..0x0026bab8,
the guest calls GetReg(4), tests **0x20000** in SMFLAG and loops while clear.
The last observed physical read is **0x1000f230 = 0**; SIF0 remains armed.
The bounded run stops with **BUDGET (8)** at **0x002644bc** after **5,000,000
attempted instructions** and two context switches. Its 517,726 completed modeled
service calls are largely repeated readiness polling, **not additional boot or
execution coverage**. No IOP command server, packet reply or ready bit exists
in the current implementation. No menu, renderer or mission has been reached.

Manifest schema 3 records page backend/build timings, runtime-input hashes and
all discovery reports. The generated-source digest is SHA-256 of canonical
sorted JSON mapping generated module names to their SHA-256 digests. Initial
selection limits/boundaries are labelled separately from discovery plans;
--limit applies to the initial plan, not the final monotonically enlarged map.
All generated source, object files and game payloads remain outside Git.

**Next:** implement independently sourced IOP/SIF command startup, packet/DMA
transfer and RPC services, with truthful event/interrupt delivery; then add the
remaining CPU/VU/graphics/disc paths. Do not force SMFLAG or fake a completed
transfer to call boot successful. Independent execution-oracle and scheduler/
startup-profile acceptance remain open. M2/M3/M4 stay In progress, M5-M10 pending.

### M4d: bounded SIF transport foundation (2026-10-15)

Completed the transport portion of the next IOP/SIF task. New independent code
moves real bytes between physical EE RAM and bounded directional queues, with
source REFE/CNT/NEXT/REF/END and destination CNT/CNTS/END tags, optional source
tag-data pairs, TIE termination, address/count updates and completion status.
Empty or partial input and full output retain pending work; zero-size/cyclic
chains remain bounded. EE and IOP mailbox writes obey opposite flag directions.

The runner polls up to 16 actions per channel between 256-instruction quanta
and syscall boundaries. The global instruction budget and delayed branches are
preserved. Queue capacity (64 words), action bound and quantum are functional
host policies, not a cycle-accurate model. Every source/header input is included
in the existing private-build snapshot/hash mechanism.

Pending DMA IRQs latch real completion state and stop with DEVICE; no guest
handler is called yet. Physical addresses cannot use CPU aliases or invoke
MMIO as RAM. Scratchpad DMA, priority-control tags, CALL/RET/REFS, MFIFO/stalls,
interleaving and nonzero-QWC restart remain explicit unsupported boundaries.
IOP DMA/DICR and SifSetDma kernel submission are separate unfinished work.

Validation: **216 tests**, including **17 new transport/event methods**, pass
with the native compiler required; **2/2 CTest**, **19 static local checks** and
the original **335,107-instruction first-syscall check** pass. Tests use actual
synthetic bytes, partial delivery, backpressure/wraparound, invalid tags and
addresses, IRQ completion/acknowledgement, cancellation, bounded cyclic chains,
and manual peer loopback between separate RAM buffers. This is model evidence,
not an independent hardware/emulator oracle.

Exact local build (fresh destination required):

```
python -B independent/build_bootstrap.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso" --output ../dev/ac4-bootstrap-sif-transport-final --cc C:/msys64/ucrt64/bin/gcc.exe --limit 16384 --entry 0x264a88 --entry 0x1001a4 --entry 0x27c680 --copied-code 0x3fabd8:0x80076000:1856 --discover-fetches 32 --discovery-limit 512 --jobs 4
```

The result retains 18,520 addresses after ten discovery extensions and matches
the previous native observation: BUDGET at **0x002644bc**, **5,000,000** attempted
instructions, **517,726** mostly polling service calls, two context switches,
SIF0 armed, last SMFLAG read **0x1000f230 = 0**. Both FIFO counts and both
transferred-quadword counts are **zero**. This run validates integration without
claiming additional boot coverage: there is still no IOP producer/server.
reference-bootstrap.json records the current metadata; game data stays local.

Remaining M4d/IOP work: live command endpoint and mailbox initialization based
on its lifecycle, SifSetDma submission, actual packet/reply generation, guest
IRQ delivery and RPC services. Do not force readiness or claim the overall IOP
boundary is resolved. M4 remains In progress; no menu or gameplay exists.

### M4e: optional live command endpoint and initialization exchange (2026-10-15)

Added an explicit, opt-in functional host IOP command profile. A live bounded
receiver with separate 2-MiB memory and receive address 0x1000 exists before
its mailbox publishes SIF/CMD readiness. No IOP CPU/BIOS/IRX is executed and
BOOTEND is not asserted. This is a new service implementation, not an empty
ready-flag bypass. The default runner retains the profile-disabled baseline.

Implemented bounded SifSetDma/SifDmaStat host submission, atomic descriptor-batch
validation, asynchronous FIFO transfer into IOP memory, initialization/SADDR/SREG
command subsets and the observed RPC-init acknowledgement. The supported
header-only opt=1 request generates SET_SREG(0,1) as an actual SIF0 packet.
The guest's software table is not directly modified; its handler still needs to
run. Unknown RPC servers, unsupported DMA attributes, invalid spans, queue/chain
ownership conflicts and malformed commands stop or backpressure explicitly.
Queue, attribute, startup and kernel return policies remain provisional; see
PROVENANCE.md. Raw EE channel-6 registers and IOP DMA/DICR are not replaced by
this high-level kernel adapter. Actual queue transfer metrics are separate.

Added opt-in coherent-memory DHWBIN/DHWOIN execution after observing AC4's
cache-flush routine at 0x0026bf08. The application runner enables that profile;
arbitrary tag operations, uncached/SPR maintenance and stale compiled code are
still rejected. This is not a hardware cache or TLB implementation.

Validation: **237 tests pass**, including **16 command-peer methods** and
**5 cache-profile methods**; compiler required. **2/2 CTest**, **19 static local
checks** and the original **335,107-instruction first-syscall check** pass.
Tests cover actual padded source bytes, incomplete input, atomic validation,
source/descriptor aliases, queue capacity/status, disabled DMA, command order,
unknown commands, reply backpressure, pending IRQ status and instruction guards.
No hardware oracle or remote CI result is claimed.

Exact optional-profile build (fresh destination required):

```
python -B independent/build_bootstrap.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso" --output ../dev/ac4-bootstrap-iop-command-verified --cc C:/msys64/ucrt64/bin/gcc.exe --limit 16384 --entry 0x264a88 --entry 0x1001a4 --entry 0x27c680 --copied-code 0x3fabd8:0x80076000:1856 --discover-fetches 48 --discovery-limit 512 --jobs 4 --iop-command-profile
```

AC4 now completes **two accepted initialization commands**, with **two incoming
IOP transfers**, **three submitted quadwords**, and **one reply packet**. SIF0
moves **two quadwords** into the EE receive buffer **0x004c9400** and completes
with D_STAT **0x00200020** (channel-5 status and mask). There are no pending
kernel jobs and both FIFOs are empty. The run stops with **DEVICE (11)** and
`stop_origin=pending-dma-irq` at next PC **0x0026b868**, after **341,391** attempted
instructions, **41** modeled service calls and two context switches. Thirteen
discovery extensions retain **18,659** addresses. The acknowledgement is
generated and delivered to packet RAM, **not consumed by the guest handler**.

`cpu_fault_context_applies=0`: legacy fault_pc/fault_address/delay values are the
last EE instruction's context, not a delivered interrupt/EPC. No interrupt
handler, completed RPC initialization, menu or mission has been reached.

Comparison build omitting --iop-command-profile, output
`../dev/ac4-bootstrap-iop-disabled-verified`, reproduces the previous **5,000,000**
instruction polling stop at **0x002644bc** with zero commands/transport data;
ten discovery extensions now retain **18,522** addresses because the two cache
operations are translatable. reference-bootstrap.json records the optional run;
reference-bootstrap-no-iop.json contains compact comparison metadata. All
native executables, RAM and generated guest code remain local outside Git.

**Next:** implement independently justified EE DMA interrupt acceptance/delivery,
context preservation and the registered guest handler path, then verify the
guest consumes SET_SREG and continues. RPC servers, reboot/module loading and
remaining CPU/VU/graphics/disc systems remain open. M4 stays In progress.
