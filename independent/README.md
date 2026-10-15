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
