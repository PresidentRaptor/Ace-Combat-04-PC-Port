# Independent AC4 implementation

This directory is the new implementation on branch `independent-ac4`.
The surrounding source tree remains the existing derived port for comparison.
Nothing here currently replaces the playable executable.

## Target

An AC4-only static recompiler and Windows runtime, native flight rendering,
correct fallback rendering, sound, movies, input, saves, and campaign coverage.
No AC5 implementation, symbol map, generated output, or binaries are build inputs.
Third-party libraries remain separately attributed.

## Development boundaries

- Write new implementation here without importing `../tools`, `../runtime`,
  `../generated`, or the old AC4 symbol/configuration maps.
- Use AC4 disc observations and independently documented hardware behavior.
- Record references and evidence in PROVENANCE.md as components are added.
- Recheck old AC4 discoveries against the disc before using them.
- Existing derived code and its notices remain intact until replaced. A new
  branch does not change that code's provenance.
- A new filename or a changed API name is not evidence of independence.

## First tool

Python 3.10+, standard library only:

```
python independent/ac4_image.py path/to/SLUS_201.52
python -B -m unittest discover -s independent/tests -v
```

The inspector validates the supported executable hash and ELF load layout.
It emits metadata only; it neither translates nor executes game code.
Use `--allow-other` only to inspect synthetic fixtures or another MIPS ELF.
See MILESTONES.md for completion gates and current progress.

Cloud development and local acceptance follow [CLOUD_HANDOFF.md](CLOUD_HANDOFF.md).
Repository-level AGENTS.md records the implementation boundaries for cloud tasks.

## Disc inspection

```
python -B independent/ac4_disc.py "path/to/Ace Combat 04.iso"
```

This reads only the volume descriptors, root directory and executable extent.
It verifies the executable in memory and emits metadata without extracting game
files. Plain ISO9660 images only; compressed/raw-sector images are unsupported.
The validated local result is recorded in reference-image.json, with no game code.

## M2a scalar decoding and partial control flow

`r5900.decode(word, pc)` returns scalar operands, signed immediates, a direct
32-bit target when available, delay-slot classification, likely status and
link register/address. See PROVENANCE.md for implemented groups and sources.
Addresses, PC+4 region selection, branch destinations and PC+8 links explicitly
wrap to 32 bits. A nonzero link register records the link written before the
slot, including on an untaken link branch. JALR with rd=0 discards the link.
Reserved, undefined and unsupported encodings raise `DecodeError`.

Run a synthetic graph from the repository root:

```
python -B independent/r5900_analysis.py --base 0x1000 --words 50850002 24020007 0000000d 03e00008 00000000
```

Callable interface (put `independent` on Python's module search path):

```python
from r5900_analysis import analyze
result = analyze({0x1000: 0x03e00008, 0x1004: 0}, [0x1000])
assert result.edges[0].target is None  # unresolved return-shaped JR $ra
```

Graph interpretation:

- Edges represent normal destinations **after** the specified slot effect.
  `executed` uses PC+4; `annulled` skips that word on an untaken likely branch.
  The branch condition and register target are sampled before the slot.
  Both conditional outcomes are retained; register values are not evaluated.
- A slot is decoded in context, without inventing an ordinary slot-to-next-word
  edge. It can also be reached as an ordinary instruction through another edge
  or an explicitly supplied entry. Loops terminate through address visitation.
- Calls have a distinct `continuation` at PC+8 with condition
  `if-callee-returns`. This is speculative reachability, not proof of a return.
  A register target stays `null`; even JR $ra is only return-shaped. Other
  pending paths are still explored after encountering a return.
- Missing/unsupported slots and forbidden control transfers/SYNC in slots
  produce diagnostics and retain destinations with `traversable=false`.
  Annulled paths still continue. An unconditional exception in a slot blocks
  normal successors and adds an unresolved exception edge on executed paths.
  Conditional traps retain both exception and normal completion possibilities.
  Normal edges implicitly require normal completion of the slot.
- Unsupported words stop their path with a diagnostic. Out-of-range direct
  destinations remain explicit edges with a diagnostic when fetched. These
  are analysis boundaries, not proof of invalid guest code. Diagnostics for a
  likely slot describe the possible taken path, not its annulled execution.
- This is a partial scalar normal-flow graph, not full function recovery.
  No jump-table recovery, register propagation, callee-return proof, exception
  vector resolution, memory faults, interrupt flow or executable/data separation
  is implemented. Arithmetic/load/store exceptions are outside this graph.

## Local M2 verification (PowerShell, repository root)

Substitute only the paths with the user's own supported USA disc/executable.
No cloud AC4 analysis results are available. Commands deliberately use
`--summary` to emit identity, counts and diagnostic addresses without raw words
or a disassembly. The ISO adapter reads the executable in memory through the
independent disc reader and then verifies its identity with the ELF inspector.
Allocated executable PROGBITS sections are inventoried when present. Each must
agree with an executable load mapping. Nonallocated vendor/debug sections and
allocated data are excluded. Stripped files use the explicitly reported
file-backed executable-load fallback. Zero-fill is always excluded. Section
flags still do not prove that every selected word is code.

```powershell
python -B -m unittest discover -s independent/tests -v
git diff --check
python -B independent/ac4_disc.py "D:\Games\Ace Combat 04.iso"
New-Item -ItemType Directory -Force work | Out-Null
python -B independent/r5900_analysis.py --iso "D:\Games\Ace Combat 04.iso" --summary | Out-File -Encoding utf8 work/ac4-m2a-iso-summary.json
if ($LASTEXITCODE -ne 0) { throw "AC4 ISO analysis failed" }
```

For an already locally extracted executable, the equivalent path is:

```powershell
python -B independent/ac4_image.py "D:\Games\AC4\SLUS_201.52"
python -B independent/r5900_analysis.py --elf "D:\Games\AC4\SLUS_201.52" --summary | Out-File -Encoding utf8 work/ac4-m2a-elf-summary.json
if ($LASTEXITCODE -ne 0) { throw "AC4 ELF analysis failed" }
```

Record Python version, commit, accepted identity, candidate-word counts,
rejections by reason, visited/decoded addresses, unresolved edges, blocked
edges and diagnostic boundaries in MILESTONES.md. Linear inventory includes
possible embedded data and must not be reported as instruction coverage.
Entry reachability may stop early on unsupported EE instructions; that is a
reported gap, not an invitation to treat them as NOP. Additional locally
verified entry addresses can be passed with repeated `--entry 0xADDRESS`
(the supplied list replaces the default ELF entry).

Local acceptance must independently check AC4-derived examples of direct and
backward branches, calls/returns, delay slots and branch-likely annulment against
hardware documentation/observed behavior. Record addresses and conclusions
without committing game bytes, extracted files or generated guest code.
For detailed local review, omitting `--summary` prints words and a graph; keep
that output local. M2 remains in progress until broader instruction coverage,
indirect-target validation and AC4-derived gates pass. Windows/Vulkan, disc
runtime behavior, controllers, audio and campaign testing remain on the PC.

## Repeat local static acceptance

```
python -B independent/validate_ac4.py --iso "path/to/Ace Combat 04.iso"
```

An extracted executable can be supplied with `--elf` instead. The command
requires the original supported identity, checks five reviewed branch/call/return
and delay-slot cases, and reports metadata/inventory/entry-analysis results only.
It does not execute game code or produce extracted files. See MILESTONES.md for
the measured local result and remaining M2 gates. M2b brought the suite to 48
tests with FPU and quadword/SA decoding; see M2c below for the current count.

## M2c packed, system and VU decoding

The decoder now recognizes packed MMI groups, secondary HI/LO forms, baseline
COP0 transfers, interrupt/TLB operations and ERET, PREF, COP2 transfers/memory
operations/branches, and common VU arithmetic/integer/microcall forms. See
PROVENANCE.md for sources and limits. Interlock bits, destination masks, integer
and vector register namespaces, scalar-register restrictions and signed VIADDI
immediates are preserved. These are decoding results, not implementations of
the numerical operations or VU synchronization/timing.

ERET produces an unresolved exception-return edge without CPU fallthrough or a
delay slot. VCALLMS/VCALLMSR start VU0 microcode and keep normal EE fallthrough;
their micro targets are not inserted into the EE control-flow graph. Extended
VU operations and specialized COP0 debug/performance encodings remain unsupported,
as do CACHE and unlisted/reserved encodings.

The local verification command also checks eight reviewed MMI/system/VU
instruction candidates. All 13 checks are static; they do not prove those
instructions execute during gameplay. Current suite: 65 passing test methods.

## M2d extended decoding and indirect-register analysis

Extended VU macros, the documented EE CACHE operations and specialized COP0
debug/performance transfers are now decoded. Encoding checks still reject
reserved/fixed-field violations. VU microcode in AC4's named `.vutext` section
is separately reported in image metadata and excluded from EE instruction
inventory. Stripped images without section names still use the documented
conservative whole-load fallback; they cannot identify `.vutext` this way.

For a bounded register-constant analysis, use:

```
python -B independent/r5900_analysis.py --iso "path/to/Ace Combat 04.iso" --summary --seed-direct-calls --resolve-indirects
```

`--seed-direct-calls` adds in-range direct-call targets found in the candidate
EE words to the entry set. These are possible entries, not verified functions.
Each seed begins with unknown GPRs except zero. `--resolve-indirects` runs a
normal-flow constant analysis on the supplied partial graph. It samples a
register target before link/slot writes, joins conflicting values to unknown,
and discards all ABI assumptions across speculative call returns. Unknown
effects lose facts rather than retain guessed targets. Only a small scalar
subset has constant semantics; this is not a CPU interpreter.

Resolved targets are reports, not new traversed edges. Loads are not evaluated,
tables are not recovered, and arbitrary runtime entry paths/interrupts are not
modelled. Do not use the reports as a complete dispatch table or boot evidence.
The local AC4 seeded run currently proves **zero** constant register destinations;
the measured unresolved cases require further function-pointer/table analysis.

Current validation: 86 synthetic tests and 19 local static disc checks pass.
See MILESTONES.md for exact inventory/graph counts and remaining acceptance work.


## M2e bounded table candidates

Add `--recover-switches` to the verified ELF/ISO analysis command for strict
bounded absolute-table candidates. The report includes guard/table/destination
metadata and its assumptions. It does not change reachability or prove immutable
tables/global guard dominance. Current local results are recorded in MILESTONES.md.

## M3a standalone scalar build and native checks

Python 3.10+ remains sufficient for parsing/decoding tests. Native execution tests
also need a GCC-compatible C11 compiler; set `AC4_TEST_CC` to its name/full path.
Set `AC4_REQUIRE_NATIVE_TESTS=1` to fail if no compiler exists, as CI does.

```
cmake -S independent -B ../dev/build-independent -DCMAKE_BUILD_TYPE=Release
cmake --build ../dev/build-independent
ctest --test-dir ../dev/build-independent --output-on-failure
```

Choose a generator/compiler installed on your system. On this Windows machine,
use `-G Ninja -DCMAKE_C_COMPILER=C:/msys64/ucrt64/bin/gcc.exe` and put that compiler's
bin directory on PATH. This target compiles a synthetic ADDIU/BREAK program; it
has no game assets, old build inputs, kernel/device runtime or renderer.

The experimental `r5900_codegen.py --words ... --base ... --output ...` emits C11
for supplied synthetic instructions. Unsupported instructions reject translation.
`--elf`/`--iso` instead selects the verified image's bounded entry graph and
requires an explicit output file; keep generated game source outside Git.
No indirect-target assumptions are added; uncovered fetches stop diagnostically.

For repeatable local AC4 entry execution without keeping generated game files:

```
python -B independent/validate_native_ac4.py --iso "path/to/Ace Combat 04.iso" --cc C:/msys64/ucrt64/bin/gcc.exe
```

This creates private temporary source/RAM/native binary, executes the initial
clear loop and stops at the first syscall. It compares metadata/register/memory
results calculated from the reviewed entry sequence. It is not an independent
hardware oracle or evidence of boot. C stop codes describe bounded-harness
faults; there is no guest CP0 exception-vector delivery, MMU, devices, kernel,
floating-point/vector execution or timing model. See MILESTONES.md for actual
local results and the remaining M3 gates.


## Local Windows bootstrap diagnostic (M3b/M4a)

The native startup runner now has bounded code selection, explicit unsupported
stops, guarded instruction bytes, EE RAM aliases/scratchpad and limited startup
services. It can run AC4's own early kernel patch from an explicitly observed
runtime copy. It still stops at CreateThread and is **not playable**.

Build into a fresh directory outside this Git repository:

```
python -B independent/build_bootstrap.py --iso "../Ace Combat 04 - Shattered Skies (USA).iso" --output ../dev/my-ac4-bootstrap --cc C:/msys64/ucrt64/bin/gcc.exe --limit 2048 --entry 0x264a88 --copied-code 0x3fabd8:0x80076000:1856
```

The explicit entry and copy metadata were verified against this supported AC4
image. They are not inputs from the old maps. The copy destination is not
preloaded: the guest copies it and runtime instruction-byte checks enforce the
translated contents. Unknown devices, active timers, missing guest instructions
and unimplemented services stop explicitly. This is not a runtime interpreter.

Output contains a native executable, ram.bin, manifest.json with hashes and
measured stop data, and README.txt. Run the executable with ram.bin as its sole
argument. Exit code 2 means incomplete execution. Private game-derived files
must stay outside Git; no package is uploaded by this builder. The native runner
requires Windows/UCRT, not Python or the compiler. Python and a GCC-compatible
C compiler are needed to produce a local package.

Startup stack/heap policy and the guest syscall bridge are experimental and
have not passed a hardware/emulator oracle comparison. The bridge supplies
ordinary-function returns rather than full CP0 exception delivery. MILESTONES.md
and reference-bootstrap.json record exactly how far the local build gets.


## Cooperative thread continuation (M4b)

The diagnostic now supports a bounded cooperative thread/semaphore model and
conditional EI/DI status changes. Local AC4 execution records two context
switches and gets past CreateThread into initialization. It still has no graphics
or gameplay. The latest exact build command, additional observed PC seeds,
selection-limit effects and remaining boundary are in MILESTONES.md; older
commands/results above describe earlier stages.

Current native CPU context covers implemented GPR/HI/LO/partial Status state and
guest syscall frames. Numerical FPU/vector execution, IRQ-driven scheduling, full CP0 and
suspend/terminate APIs are not implemented. No-ready-thread waits stop with
IDLE rather than inventing external events. Scheduler return/stack policies
still need an independent trace. Diagnostic packages now use O0 compilation;
the native synthetic suite continues to check optimized generated C.


## Guarded initialization replay and current IOP boundary

The builder now emits stable per-4-KiB C units and reuses unchanged native objects
within a build. Add `--discover-fetches 32 --discovery-limit 512 --jobs 4` to opt
into bounded rebuild/replay of observed missing fetch addresses. Previously
selected code is retained. Every replay starts from initial RAM, and every
instruction still checks its translated bytes. Unsupported instructions,
modified code and unverified addresses are not turned into NOPs or accepted
by the discovery pass. This does not prove every possible dispatch target.

`--limit` bounds the initial plan; each discovery round can add up to
`--discovery-limit` more addresses. The manifest records all additions and the
initial plan separately. Schema 3 records the paged backend, input hashes,
per-round compilation/reuse counts and timings. Source digests aggregate the
sorted generated-module digest map, rather than hashing a single C file.

Current local validation passes 199 tests, 19 static disc checks and both CTest
checks. AC4 reaches SIF initialization, arms incoming reception, then waits for
the IOP command-ready flag. The 5,000,000-instruction budget stops the polling
loop; it is not a successful boot or gameplay result. No artificial IOP ready
bit, DMA completion or server reply is generated. See the latest MILESTONES.md
section for the exact reproducible command, observed reads and remaining work.

The CPU runner's initial Status=0x20000000 is an explicit functional startup
profile with COP1 usable, not a measured BIOS state. Raw FPU transfers/branches
and context are supported; numerical FPU/VU operations and full exception/IRQ
semantics remain incomplete. Existing derived code and its notices are preserved.

## SIF transport foundation (M4d)

`sif_transport.h` now moves real synthetic DMA data through bounded SIF0/SIF1
queues. It supports a main-RAM chain subset, partial-input/output backpressure,
channel address/count progress, completion status and both sides' mailbox write
directions. The startup runner polls it between at most 256 guest instructions
and syscall boundaries, with at most 16 actions per channel per poll. These are
host scheduling limits, not hardware timing or FIFO capacity measurements.

An asserted DMA interrupt stops with DEVICE until interrupt delivery exists.
Unsupported chain modes, scratchpad DMA, stall/MFIFO operation and nonzero-QWC
restart remain explicit gaps. No IOP executable, command server or RPC service
is connected. The local AC4 result remains the same IOP command-ready wait;
both queues and transferred-quadword counts are zero. Synthetic peer loopback
tests demonstrate transport only. The next task is a live command endpoint and
SifSetDma submission, followed by guest interrupt handling and RPC replies.
