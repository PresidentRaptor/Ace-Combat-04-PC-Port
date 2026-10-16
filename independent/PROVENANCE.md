# Provenance record

## Audit baseline

Audit date: 2026-10-15. Existing source baseline: upstream AC5 commit
078662b4018b5e79d5aa5ee9b9c60aceec9e7649.

Comparing current runtime/ and tools/ to that baseline, excluding Python caches:
35 files identical, 51 modified, 28 added. Added does not imply independent.
Core ps2recomp ELF, analysis, decoder, emitter and signature matcher are identical.
Four vurecomp files are identical; its emitter is modified. Console services and
rendering contain inherited implementations. All 154 config/ac4/sdk_symbols.json
entries identify their origin as 'ported from AC5'. ac4mod.h retains upstream API
structure/documentation. AC5 native rendering was removed from the current port.
The 77 third_party files compared were identical; source these libraries directly
with their own notices if used in the independent implementation.

AC4 sound protocol notes, camera observations, manual function discoveries,
launcher/installer and regression scenarios are reuse candidates requiring review.
No independent-origin claim is made for them by this audit.

This is a component-level audit, not a line-by-line authorship certification.
Existing derived source, Git history and packaged executables are not made
independent by adding this directory. Existing notices must stay with those files.

## New implementation inputs

| Component | Inputs/reference | Scope and limits |
| --- | --- | --- |
| ac4_image.py | System V ELF32 header/program-header layout; MIPS machine ID 8; Python struct/hashlib | New parser; no imports or copied implementation from existing port. ELF format reference: https://refspecs.linuxfoundation.org/elf/elf.pdf |
| tests/test_ac4_image.py | Synthetic ELF byte fixtures | No game bytes or inherited test implementation |
| Supported image identity | SLUS_201.52 size/hash documented in this project's README | Identity metadata only; must verify against user's disc |

The developer has previously inspected inherited source. This record describes
implementation inputs; it does not claim a formally isolated clean-room process.
New hardware components need specific primary references before implementation.

| Component | Inputs/reference | Scope and limits |
| --- | --- | --- |
| ac4_disc.py | ECMA-119 second edition, volume descriptors and directory records: https://ecma-international.org/wp-content/uploads/ECMA-119_2nd_edition_december_1987.pdf | New limited ISO reader; no inherited filesystem or installer imports |
| tests/test_ac4_disc.py | Synthetic volume/directory records and zero-filled payload | No game bytes; tests extents, identity rejection and malformed metadata |
| reference-image.json | Read-only inspection of user's AC4 ISO on 2026-10-15 | Metadata only; no extracted code or assets |

## M2a scalar foundation (2026-10-15)

New `r5900.py`, `r5900_analysis.py` and `tests/test_r5900.py` were written
from hardware descriptions and synthetic words. No inherited decoder, runtime,
tools, generated code, symbol maps or AC5 implementation was inspected or used
for this task. This statement describes this task's inputs, not a formally
isolated clean-room process or a claim about earlier work.

Primary hardware documents actually consulted (public document mirrors; no PDF
or manual text is redistributed in this change):

- Sony Computer Entertainment, **EE Core Instruction Set Manual**, version 6.0,
  April 2002. [Document mirror](https://github.com/ninjadynamics/PS2Docs/blob/3a6e97416b0e23c4e94288515adef521cf077682/EE_Core_Instruction_Set_Manual.pdf).
  Chapter 2, pp. 24ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ134: scalar encoding pictures, operands and restrictions;
  especially BEQ/BEQL pp. 30ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ31, link branches pp. 33ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ34 and 41ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ42,
  J/JAL/JALR/JR pp. 65ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ68, SYNC p. 121 and explicit exceptions pp. 122ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ134.
  Chapter 3, MULT/MULTU pp. 154/156: EE's optional destination GPR extension.
  Consulted encoding pictures for sign extension, shift widths, fixed-zero
  fields and trap code fields as well as the descriptive text. Where the
  BLTZALL prose describes fallthrough including the slot, its operation block
  explicitly nullifies it; the implementation follows that block and section
  2.5.1 of the Core User's Manual.
  Retrieved PDF SHA-256:
  `104205afc6f5a5071168d8bf693a6c8b4db9a02e1aa66eb51a828e8951f5c069`.
- Sony Computer Entertainment, **EE Core User's Manual**, version 6.0,
  April 2002. [Document mirror](https://github.com/ninjadynamics/PS2Docs/blob/3a6e97416b0e23c4e94288515adef521cf077682/EE_Core_Users_Manual.pdf).
  Section 2.5.1, branch delay slots and likely nullification; section 1.3.6,
  instruction issue restrictions, including branches/ERET in delay slots.
  The decoder follows the instruction-set manual's stricter SYNC restriction
  and does not traverse a slot containing any SYNC variant.
  Retrieved PDF SHA-256:
  `0ad766eb827157fad19aa579fd9df54f2ca312211e7f0dbdb4b723992b566ce3`.

Implemented groups (decoding only; no arithmetic, memory or exception execution):

- Integer register ALU: ADD/ADDU/SUB/SUBU, DADD/DADDU/DSUB/DSUBU,
  AND/OR/XOR/NOR, SLT/SLTU, MOVZ/MOVN.
- Immediate ALU: ADDI/ADDIU/DADDI/DADDIU, SLTI/SLTIU, ANDI/ORI/XORI, LUI.
- Shifts: SLL/SRL/SRA, SLLV/SRLV/SRAV, DSLL/DSRL/DSRA,
  DSLL32/DSRL32/DSRA32, DSLLV/DSRLV/DSRAV.
- HI/LO: MULT/MULTU (including EE destination GPR), DIV/DIVU,
  MFHI/MFLO/MTHI/MTLO.
- Scalar memory: LB/LBU/LH/LHU/LW/LWU/LD, LWL/LWR/LDL/LDR,
  SB/SH/SW/SD, SWL/SWR/SDL/SDR. Offsets are signed; effective addresses
  are not evaluated.
- Control: J/JAL/JR/JALR; BEQ/BNE/BLEZ/BGTZ and likely forms;
  BLTZ/BGEZ, likely forms, link forms and likely-link forms.
- Explicit exceptions: SYSCALL/BREAK; TEQ/TNE/TGE/TGEU/TLT/TLTU
  and immediate equivalents. SYNC stype is decoded.

All other groups remain unsupported, including COP0, FPU/COP1, COP2/VU,
MMI and remaining EE-specific operations (including LQ/SQ and SA operations),
CACHE/PREF and any unlisted encoding. Unsupported words and invalid fixed
fields raise `DecodeError`; zero is decoded as SLL $zero,$zero,0, never used
as an error fallback. Undefined JALR source/link alias and link branches with
rs=31 are rejected. Register contents and value-dependent restrictions are not
validated by this static decoder.

Tests use literal hand-encoded scalar scenarios, synthetic ELF headers and
synthetic ISO fixtures only. The ELF adapter test temporarily substitutes the
identity of its synthetic ELF within the test; production identity constants
and the default verified-image requirement are unchanged. No game bytes,
external emulator implementation or inherited test oracle are inputs.

## M2b local continuation (2026-10-15)

New extensions were written from format/ISA descriptions and fresh inspection
of the user's verified AC4 disc. No legacy decoder, symbol map, runtime or AC5
implementation was used. The M2a implemented-group list above is historical;
the following groups are now added (decoding only):

- LQ/SQ; MFSA/MTSA/MTSAB/MTSAH.
- LWC1/SWC1; MFC1/MTC1/CFC1/CTC1; BC1F/T/FL/TL.
- ADD/SUB/MUL/DIV/RSQRT/MAX/MIN/MADD/MSUB single-precision forms;
  SQRT/ABS/MOV/NEG; ADDA/SUBA/MULA/MADDA/MSUBA; four EE comparisons;
  CVT.W.S and CVT.S.W. No FPU arithmetic or register execution is implemented.

References consulted:

- Sony **EE Core Instruction Set Manual**, version 6.0 (April 2002),
  chapters 3 and 5, and appendix 7.4. Public text mirror:
  https://studylib.net/doc/28989088/ee-insns . In particular, SQRT p. 376
  uses ft; CFC1/CTC1 pp. 353-354 have different FCR restrictions; the EE
  comparison/accumulator forms have no destination FPR. No manual text or PDF
  is distributed. Encoding recognition does not imply arithmetic correctness.
- TIS **ELF Specification**, version 1.2, Book I section-header format and
  SHF_ALLOC/SHF_EXECINSTR/PROGBITS definitions:
  https://refspecs.linuxfoundation.org/elf/elf.pdf . The new section reader
  selects only executable allocated sections that agree with the load mapping.
- User's USA AC4 ISO, verified through independent readers. The expected case
  addresses in validate_ac4.py were reviewed from these bytes. A separate raw
  field inspection checked primary opcodes/registers and signed offsets without
  calling the decoder, then checked the target arithmetic against the manual.
  Only addresses, names, target conclusions and aggregate counts are recorded;
  no game bytes, extracted assets or generated guest source are committed.

The local checks establish static encoding/graph consistency for selected cases.
They are not an independent CPU execution oracle or a campaign validation claim.
Synthetic tests add malformed section mapping cases and nonallocated vendor
section handling, quadword prologue/return-slot behavior, distinct FPU/GPR
namespaces, restricted FCR writes, unary/accumulator field restrictions and FP
likely annulment across an unsupported slot.

## M2c packed/system/VU decoding (2026-10-15)

Sources actually consulted for new independent decoding and tests:

- Sony **EE Core Instruction Set Manual**, v6.0, chapter 3 encoding pictures
  and appendix 7.2 (MMI groups 0-3); chapter 4 and appendix 7.3 (COP0), and
  PREF p. 96. Same public text mirror recorded above. PMFHL formats and
  PMTHL fixed fields were checked in their individual encoding descriptions.
  Packed halfword shifts use only the low four shift bits. Specialized COP0
  debug/performance selectors remain unsupported. A baseline MFC0/MTC0 decode
  does not certify that every possible COP0 register number is implemented.
- Sony **VU User's Manual**, v6.0, April 2002, chapter 6: transfers/branches
  pp. 230-239, common vector arithmetic, VI integer operations and microcalls
  pp. 241-317. Primary authored document at public PDF mirror:
  https://manuals.plus/m/a858ef55cd2638accdfca612d5359eb6e48a48c7fd6792b18080d866e610fde5.pdf
  Encoding fields distinguish GPR, VF and VI registers, interlocks, component
  masks and I/Q scalar broadcasts. VOPMSUB requires the xyz mask; VCALLMS
  addresses are in eight-byte microinstruction units and are not EE branches.
  Macro integer register numbers above 15 are conservatively rejected.
- Fresh metadata-only inspection of the supported AC4 disc supplied eight
  operation candidates in validate_ac4.py. Raw fields were inspected directly
  and checked against the documented selectors. No inherited implementation,
  symbol tables, generated guest code or AC5 data was used.

New coverage includes MMI0/1/2/3, secondary scalar multiply/divide/HI/LO,
PMFHL/PMTHL, packed shifts, basic COP0/TLB/interrupt/ERET, PREF, COP2 data/control
transfers, LQC2/SQC2, BC2 branches, vector arithmetic/broadcast/scalar forms,
VIADD/VISUB/VIAND/VIOR/VIADDI and VCALLMS/VCALLMSR. This is a partial decoder:
extended VU macro forms, VU micro decoding/execution, CACHE, specialized COP0
selectors and unlisted instructions remain unsupported. None of the new
arithmetic, memory, privilege, interlock or pipeline behavior is executed.

## M2d extended VU/system and register constants (2026-10-15)

The earlier VU web mirror became unavailable. Archived authored hardware PDFs
were read locally using the bundled pypdf package. References stay in dev/
outside the source repository; no PDF or extracted manual text is committed.

- Sony **VU User's Manual**, v6.0, chapter 6, pp. 240-323: individual extended
  MacroOP encoding pictures. Archived source:
  https://github.com/ninjadynamics/PS2Docs/blob/main/VU_Users_Manual.pdf
  SHA-256 `a858ef55cd2638accdfca612d5359eb6e48a48c7fd6792b18080d866e610fde5`.
  The new vu_macro.py covers accumulator broadcasts, conversions, vector moves,
  clipping/outer products, VU loads/stores, division-component selectors,
  transfers, random-register forms, VNOP and VWAITQ. Integer register numbers
  above 15 and non-single-component VILWR masks remain conservative rejections.
- Sony **EE Core Instruction Set Manual**, v6.0, chapter 4, pp. 294-342:
  documented cache operations and debug/performance selectors. Archived source:
  https://github.com/ninjadynamics/PS2Docs/blob/main/EE_Core_Instruction_Set_Manual.pdf
  SHA-256 matches the previously recorded `104205af...f5c069` full hash.
  Undefined cache operations and unlisted selector encodings remain rejected.
- TIS ELF section-name string tables (previous reference) and fresh local AC4
  section headers identify `.text` and `.vutext` as different instruction sets.
  The latter is not decoded as EE code. A section name is classification
  metadata, not evidence that every word in `.text` is executed code.
- New r5900_constants.py uses the small scalar-operation descriptions in
  chapter 2 of the EE instruction manual and an independently implemented
  meet-over-supplied-paths constant analysis. It does not copy an emulator,
  upstream recompiler or inherited runtime implementation. Synthetic branch,
  call, loop, alias and delay-slot fixtures test the conservative assumptions.

Six further local instruction candidates were checked from raw fields and
added as metadata to validate_ac4.py. Constants are tracked only in the lower
64 GPR bits; inferred control targets are reported in the decoder's 32-bit
guest-PC model. No memory-load constants, runtime exception semantics, dynamic
entry coverage or CPU execution oracle is claimed. Call-return continuations
discard all GPR facts. Reporting a constant never expands the partial graph.


## M2e and M3a implementation inputs (2026-10-15)

- `r5900_switches.py`: newly written strict pattern matcher from fresh local AC4
  instruction-field observations and the already documented ELF/EE references.
  No inherited symbol maps, signature databases or recompiler implementation.
  Initial section read-only flags are not runtime immutability evidence.
- `r5900_codegen.py`: newly written C11 scalar generator and bounded flat-memory
  harness from Sony EE Core Instruction Set Manual v6.0, chapters 2 and 3.
  Consulted scalar descriptions, branch/link/delay rules, LQ/SQ address masking,
  HI/LO transfer/multiply/accumulate and divide descriptions (pp. 51-53,
  138-145 and 146-157 for division/extended HI/LO). The archived primary manual
  and SHA-256 were recorded above. No emulator or inherited implementation was
  imported, adapted or used as an execution oracle. No timing/interlock model.
- `tests/test_codegen.py` and `scalar_smoke.c`: synthetic instructions and
  independently calculated expected outcomes; native C compilation/execution.
  `validate_native_ac4.py`: verified user's disc, ELF layout and reviewed startup
  fields; expected entry-loop results calculated separately from generated C.
  This is not a second CPU emulator or hardware-trace comparison. Undefined
  non-word multiply/divide inputs and division by zero stop with a host diagnostic,
  not a fabricated guest exception or guessed implementation-defined result.
- `CMakeLists.txt`: new standalone synthetic harness build with Python-generated
  C and the host standard C library; no old runtime/tools/build dependencies.

All game-derived payloads and generated guest source remain local and untracked.
No attribution is removed from the existing derived implementation. These
components are partial replacements, not completion of the port/provenance gate.


## M3b / M4a inputs and experimental policy (2026-10-15)

- Scalar merge loads/stores: Sony EE Core Instruction Set Manual v6.0,
  pp. 72-83, 99-102 and 117-120. Newly written byte-range merge logic and
  synthetic native tests; no inherited/emulator implementation was adapted.
- Memory windows, scratchpad, disabled timer registers, kernel API/parameter
  layouts and alarm patch behavior: original author's PS2tek reverse-engineering
  documentation, Memory Map / EE Timers / BIOS EE Syscalls / BIOS EE Patches:
  https://psi-rockin.github.io/ps2tek/index.html . Consulted directly on
  2026-10-15. This is an independent author's documentation, not an official Sony
  ABI guarantee or hardware trace. No PS2tek emulator implementation was used.
- SetupThread/SetupHeap API names and argument order were cross-checked against
  the PS2SDK project's published declarations:
  https://ps2dev.github.io/ps2sdk/kernel_8h.html . No PS2SDK source/header/library
  is imported or shipped. The new code is not adapted from its kernel wrappers.
- Stack/heap special-value behavior in the documentation is incomplete/ambiguous.
  The chosen automatic-stack profile returns RAM-size minus stack-size; a
  heap-size sentinel uses the reserved stack boundary as its end. These are
  explicitly provisional policies informed by observed AC4 arguments. Passing
  synthetic tests does not establish accuracy or permit M3/M4 completion.
- bootstrap_services.h, ee_devices.h, bootstrap_main.c and build_bootstrap.py
  are new limited models/runner/build orchestration. Semaphore handles and
  bounded shadow guest-call return frames are new implementation choices.
  They do not claim the BIOS's internal layout, full scheduler, privilege model
  or timing. Timer enable remains an explicit failure until clock/IRQ support.
- Fresh local syscall observations identify the CPU copy handler 0x00264a88 and
  copied alarm patch from 0x003fabd8 to 0x80076000, size 1,856 bytes. These are
  metadata from the user's verified disc and observed guest call arguments,
  not inherited maps or AC5 behavior. New copied-code selection validates
  file backing, alignment, bounds and overlaps; actual guest writes and
  instruction-byte checks are required before relocated code can execute.

The diagnostic executable and initial RAM contain private game-derived material
and stay outside Git. reference-bootstrap.json contains hashes/addresses/counts
only. Its observations are results from this experimental implementation, not a
separate execution oracle. Existing derived source/notices remain untouched.


## M4b thread model and CPU extensions (2026-10-15)

The new cooperative scheduler was written from PS2tek's BIOS EE Threading and
EE Syscalls descriptions, cross-checking the thread parameter field offsets
against PS2SDK's published kernel.h declarations:
https://ps2dev.github.io/ps2sdk/kernel_8h_source.html . No scheduler implementation,
TCB source, inherited runtime or AC5 map was copied/adapted. Internal context
storage, queue ordering and shadow syscall frames are new implementation choices.
Model choices such as semaphore FIFO wake ordering, some return values and new
stack layout are provisional, not claims of exact BIOS behavior. The primary
references do not replace independent execution-oracle validation.

Conditional EI/DI effects were checked against Sony EE Core Instruction Set
Manual v6.0 pp. 314-315; Status bit positions were cross-checked against PS2tek.
No interrupt delivery, privilege transition or complete COP0 model is inferred.
Packed logical and copy operations use the same Sony manual's individual PAND,
POR/PXOR/PNOR and PCPYH/PCPYLD/PCPYUD descriptions (copy pp. 189-191), with fresh
synthetic alias/upper-half expectations and no emulator implementation inputs.

Additional local selection seeds 0x001001a4 and 0x0027c680 came from explicit
FETCH boundaries in guarded runs of the user's verified image. They do not
establish complete function boundaries or global dispatch coverage. Runtime
observations still reflect the provisional startup/scheduler model, not a
physical-console trace. No game words, generated source or artifacts enter Git.


## M2f / M3c / M4c inputs (2026-10-15)

- Newly written page-based C emission, object-cache orchestration and bounded
  rebuild/replay use only the independent decoder/translator and verified local
  image observations. No inherited code generator, emulator, AC5 maps or build
  runtime was used. Runtime instruction guards remain mandatory for game builds.
- Sony EE Core Instruction Set Manual v6.0: packed arithmetic/comparison/min/max
  individual descriptions (including PADDB p.160, PADDW p.174, PCEQB p.177,
  PCGTB p.183, PMAXW p.224, PMINH p.235, PSUBB p.270, PSUBW p.284);
  MFC0 p.318 and MTC0 p.328; COP1 control transfers pp.353-354, LWC1 p.358,
  MFC1 p.364, MOV.S p.366, MTC1 p.371 and SWC1 p.379. Document/hash recorded
  earlier. New code implements only the stated subsets; numerical FPU/VU,
  other COP0 registers and full exception delivery remain explicit gaps.
- PS2tek, EE COP0/DMAC/INTC/SIF/BIOS syscall descriptions, consulted directly:
  https://psi-rockin.github.io/ps2tek/index.html . Newly written register masks,
  W1C/XOR semantics, handler ledger and passive incoming SIF0 state. No actual
  DMA data or interrupts are delivered. Configuration and unsupported-event
  tests do not establish device timing or hardware-oracle compatibility.
- PS2SDK's published SIF register identifiers/API declarations, not its kernel
  implementation: https://ps2dev.github.io/ps2sdk/sifdma_8h_source.html and
  https://ps2dev.github.io/ps2sdk/kernel_8h.html . These distinguish software
  slots 0x80000000..2 from physical register IDs 1..4. No source/header/library
  is imported. SetReg returning the prior value is a provisional model policy
  requiring independent ABI validation; it is not proven by those declarations.

The application profile explicitly sets COP1 usability in initial Status
(0x20000000). This is a configured functional starting state, not a BIOS dump
or console trace. Current IOP readiness flags remain zero because no IOP side
exists. The observed AC4 polling loop tests SMFLAG bit 0x20000; this was checked
from the user's supported image fields and native read metadata, independently
of old maps. Diagnostic budget exhaustion is not a boot claim.

reference-bootstrap.json contains hashes/counts/addresses/build metadata only.
Its current page-source hash aggregates module digests; runtime-input hashes
record snapshotted own source used for the build. No generated game source,
object, executable, RAM, ISO or assets are committed or uploaded.

## M4d transport inputs (2026-10-15)

New `sif_transport.h` and tests were written from PS2tek's original hardware
documentation: https://psi-rockin.github.io/ps2tek/index.html , sections DMAC
I/O, Chain Mode, Interrupts, and SIF Registers/DMA. These describe the incoming
64-bit destination tag, outgoing optional upper-tag pair, payload quadwords,
channel status, and opposite EE/IOP mailbox ownership. No emulator or legacy
port implementation was read or adapted for this work.

Implemented source tags are REFE/CNT/NEXT/REF/END; destination tags are
CNT/CNTS/END with stall controls disabled. Only physical main RAM is supported.
Priority-control tags, CALL/RET/REFS, scratchpad selection, MFIFO/stalls and
nonzero-QWC restart stop rather than approximating unverified behavior.
Completion latches the real channel status after data moves; pending IRQs stop
instead of pretending to invoke a handler. IOP DMA registers, DICR, command/RPC
servers and cycle timing are not implemented.

The 64-word queue size, 16-action poll bound and 256-instruction host quantum
are explicit functional-model policies. Synthetic tests independently construct
tags and byte patterns, including a manual peer loopback; they do not establish
hardware compatibility. No IOP readiness flags or reply packets are generated
by the runner. The supported local image reproduces the previous polling stop
with zero transferred quadwords, not new game execution coverage.

Cross-checked Sony EE User's Manual v6.0, sections 5.2.3-5.2.4, 5.6-5.9,
pp.45-48, 58-62 and 73-79, in the published manual transcription:
https://studylib.net/doc/25813272/emotion-engine-user-s-manual . It confirms
source tag IDs, chain addresses, register fields and restart restrictions.
Its destination-tag table names ID 0 CNTS and ID 1 CNT, opposite to PS2tek's
labels. The present subset accepts both only with stall controls disabled, so
their supported behavior is identical; use the Sony encoding when implementing
stall-address updates. The transport computes the next TADR on tag acceptance;
intermediate register timing still requires hardware-oracle validation. No
manual, source code or game bytes are redistributed.
