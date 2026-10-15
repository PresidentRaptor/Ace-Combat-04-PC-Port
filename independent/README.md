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
