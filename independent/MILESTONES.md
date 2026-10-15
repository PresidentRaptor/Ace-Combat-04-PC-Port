# Completion milestones

Status: M0 and M1 complete; M2 in progress. No independent playable build yet.
Progress is measured by passed gates, not lines written or guessed percentages.

| ID | Status | Deliverable | Completion gate |
| --- | --- | --- | --- |
| M0 | Complete | Isolated development area, provenance rules, audit and plan | New branch from main; existing port preserved; replacement scope recorded |
| M1 | Complete | Independent AC4 executable and disc inspection | ELF reader tested; supported disc executable validated locally; ISO reader extracts/verifies executable; reference manifest recorded |
| M2 | In progress | R5900 decoding and static analysis | Instruction classes, branch/delay-slot behavior and indirect targets verified with synthetic and AC4-derived cases |
| M3 | Pending | CPU translation and minimal execution harness | Deterministic C generation; arithmetic, memory, exceptions and call dispatch verified against an independent oracle; repeatable AC4 translation |
| M4 | Pending | Boot services | Memory, kernel, interrupts, disc services, SIF and input reach stable interactive menus with a basic graphics path |
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
- Independent CMake/runtime/renderer do not exist yet.

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
