# Independent AC4 development

On branch `independent-ac4`, the active implementation is `independent/`.
Read `independent/README.md`, `independent/PROVENANCE.md`, and
`independent/MILESTONES.md` before changing that implementation.

The rest of this repository contains the existing AC5-derived AC4 port. Preserve
it and its notices. Do not copy, translate, rename, import or adapt implementation
from `runtime/`, `tools/`, `generated/`, `config/`, or upstream AC5 repositories
into `independent/`. New implementation must use documented hardware/file-format
behavior and AC4 observations with recorded sources. Do not claim a formally
isolated clean-room process: earlier work has inspected inherited source.

## Cloud and local responsibilities

- Cloud: independent tools/runtime code, synthetic tests, portable builds, and
  documentation. Work from `independent-ac4`; do not target `main` for integration.
- Local Windows: AC4 disc validation, Vulkan/driver checks, controllers, audio,
  installer checks, and campaign playthroughs.
- Game files are absent from Git intentionally. Do not request, download, commit
  or fabricate game executables, ISOs, generated guest code, textures or assets.
  Missing local fixtures must be recorded as pending local validation.
- Do not mark a milestone complete until every acceptance gate has evidence.
  Synthetic test success alone does not establish AC4 compatibility.
- Record exact commands, test results, limitations and local handoff steps in
  the milestone tracker. Keep changes within the assigned milestone scope.

## Validation

Run from the repository root:

```
python -B -m unittest discover -s independent/tests -v
git diff --check
```

Python 3.10+ and its standard library suffice for parser/decoder tests. Native
execution tests require a GCC-compatible C11 compiler; set AC4_TEST_CC as needed.
CI sets AC4_REQUIRE_NATIVE_TESTS=1 so native checks cannot silently skip. Do not run
the legacy build scripts for independent work. See `independent/CLOUD_HANDOFF.md`
for the next bounded task and return procedure.
