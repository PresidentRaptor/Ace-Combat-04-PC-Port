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
