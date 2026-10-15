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
