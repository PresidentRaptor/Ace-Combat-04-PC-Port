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
  Chapter 2, pp. 24–134: scalar encoding pictures, operands and restrictions;
  especially BEQ/BEQL pp. 30–31, link branches pp. 33–34 and 41–42,
  J/JAL/JALR/JR pp. 65–68, SYNC p. 121 and explicit exceptions pp. 122–134.
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
