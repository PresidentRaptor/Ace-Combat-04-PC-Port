# Cloud development and local acceptance

Repository: PresidentRaptor/Ace-Combat-04-PC-Port
Integration branch: independent-ac4
Baseline foundation commit: d126ad4

## Environment setup

Select this repository and `independent-ac4` in Codex Cloud. Use Python 3.10+
(3.12 is used in CI), Git and a shell. No packages, secrets or game data are
required for the initial task. A C compiler and CMake will be needed for M3.
Use the following environment smoke test from the repository root:

```
python --version
python -B -m unittest discover -s independent/tests -v
git status --short
```

Expected starting result: 10 test methods pass. Do not install the legacy port's
graphics stack to run these tests. Public primary documentation access is useful
for hardware research; record the actual references consulted in PROVENANCE.md.

## First task: M2a, scalar decoder and control-flow foundation

Implement a new, independent R5900 scalar instruction decoder and conservative
control-flow analysis under independent/. Read AGENTS.md and independent's
README, PROVENANCE and MILESTONES first. Do not inspect/copy the legacy decoder,
runtime or symbol maps. Use primary ISA documentation and synthetic inputs.

Deliverables:

1. Record hardware references and explicitly identify which instruction groups
   are implemented. Decode scalar operands, signed immediates and direct targets.
   Reject reserved/unsupported encodings rather than silently treating them as NOP.
2. Model direct jumps/calls, conditional branches, register jumps, return sites,
   branch delay slots and likely-branch annulment. Use PC+4 for branch offsets and
   jump-region calculation; handle address wrap and link addresses explicitly.
3. Preserve unresolved register targets as unresolved edges. Never infer that
   every function ends at the first return or claim complete indirect recovery.
4. Test known encodings, negative/backward branches, region boundaries,
   reserved fields, indirect calls/returns, and taken/untaken likely branches.
   Tests must validate architectural behavior, not merely restate decoder tables.
5. Provide a CLI or callable analysis interface for synthetic instruction streams
   and a documented way to use the verified AC4 ELF/ISO readers locally.
6. Run all independent tests, report results, and update MILESTONES.md. Keep M2
   in progress if MMI/FPU/COP2 coverage or AC4-derived validation remains absent.

Do not implement the renderer or rewrite the rest of the repository in this task.
Do not weaken tests or acceptance gates to call the task complete. Return changes
for review against independent-ac4 with a concise report and local test commands.
If creating a PR, its base must be independent-ac4, not main.

## Local return procedure

1. Review the cloud diff and provenance notes before integrating.
2. Run the independent test suite on Windows.
3. Run the new analysis against the user's local ISO without committing any
   extracted bytes or generated game code. Record metadata/coverage and gaps.
4. Only then decide whether the applicable milestone gate has passed.
5. Assign the next bounded task from MILESTONES.md; do not assume the cloud task
   continues forever or that a passing task completes an entire milestone.

Keep the existing playable build for behavior comparisons. Windows graphics,
sound, controllers and campaign validation remain local acceptance requirements.

## Return status and next bounded work

M2a was pushed as 79d72cb and reviewed locally. M2b adds section-aware inventory,
quadword/SA/FPU decoding, 48 passing tests and five passing local static checks.
Read the latest milestone evidence before starting another task; do not repeat
M2a or use its historical unsupported-group list as the current implementation.

M2c now adds MMI, baseline COP0 and common COP2/VU forms, with 65 tests and
13 static local checks. Next bounded scope: extended VU macro forms, CACHE and
specialized COP0 selectors from primary hardware references. Preserve explicit unsupported
boundaries and do not treat system calls as successful fallthrough. Register
propagation, jump-table recovery and execution-oracle evidence remain separate
acceptance work. M2 must remain in progress until its full gate is met.

M2d now adds extended VU/CACHE/system decoding, separates `.vutext`, and adds a
conservative indirect-register constant report. Current suite: 86 tests; 19
local static checks pass. Read the latest tracker evidence: the seeded AC4 run
proves zero constant register destinations. Next bounded task is independently
verified jump-table/function-pointer analysis; do not claim the constant pass
resolved the remaining targets, and do not repeat completed decoder work.


M2e/M3a now add guarded absolute-table candidates and a new scalar C generator,
native execution checks and standalone CMake smoke target. Read the latest
MILESTONES.md evidence: 114 tests, 19 static disc checks and 1/1 CTest pass locally;
bounded native AC4 startup stops at syscall 60, not boot. CI requires a C compiler.
Next work: independent execution-oracle comparisons, full exception/system
semantics and broader translated execution; retain unsupported-operation failures.
Do not silently turn candidate table targets into proven dispatch edges or treat
hand-calculated entry results as a hardware trace. Game files stay local.


M3b/M4a add the local bootstrap package, scalar merge operations, EE memory bus,
limited disabled-timer/startup/semaphore-creation services and an experimental
guest syscall bridge. 152 tests and 2/2 CTest pass locally. With the explicitly
observed entry/copy metadata in README, AC4 reaches CreateThread after 339,303
instructions and 23 modeled service calls. This is not a playable build.
Next bounded task is thread creation/context/scheduling and wait behavior;
review sources and provisional stack/heap/bridge policy before extending it.
Do not declare scheduling/interrupt correctness without independent evidence.
Keep missing services/timers/system instructions explicit and preserve byte
checks for copied or modified code. See reference-bootstrap.json for exact data.
