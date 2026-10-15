# Contributing

The goal is faithful native Windows play of Ace Combat 04: Shattered Skies
(USA, SLUS-20152). Correctness, stability, saving, audio and controls take
priority over new artwork or changes to the original gameplay.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). The project is a beta;
maintainers cannot promise response dates or full campaign compatibility.

## Reports and proposals

Search existing issues first, then use the repository's bug, feature or support
form. Include the release or commit, mission, camera, Windows/GPU/driver,
reproduction steps and relevant settings. Test original textures without mods
when practical and say whether an issue also occurs in 4:3.

Review logs before attaching them: remove personal paths, account details and
other private information. Never upload an ISO, original ELF, generated game
source, memory image, extracted textures/audio, full graphics captures or saves
containing game data. Describe how maintainers can reproduce the issue with
their own copy instead. [Security reports](SECURITY.md) follow a separate process.

## Build and test

Follow the [README](README.md#build-and-run) for the supported executable hash,
MSYS2 UCRT64 dependencies and build commands. You need your own game copy for
the full runtime build. No game files are required for the focused source checks:

```powershell
python tools/run_checks.py
```

These checks need Python 3.12+ and GCC on PATH. On Windows the runner also
recognizes the usual `C:/msys64/ucrt64/bin` installation. GitHub Actions runs
these checks on Linux; it does not build the Windows port or play the game.
For the current coverage, see [compatibility](docs/compatibility.md).

Changes to the native runtime still need a Windows build. For rendering, use a
local capture or scripted run and compare affected scenes, 4:3 and widescreen.
Test audio changes with the synthetic audio checks and normal playback. Check
that save, settings and mod API compatibility remain intact where affected.
Installer changes need the [installer integration tests](packaging/ac4/installer/README.md).
Record what you actually tested and what you could not test.

## Pull requests

- Branch from current `main`; keep each PR focused on one problem.
- Explain the trigger, before/after behavior and validation. Link the relevant
  issue if one exists. Use draft PRs for unfinished work.
- Follow nearby C/C++/Python style. Avoid broad formatting changes, generated
  output, build products or unrelated personal settings.
- Preserve ABI/file-format compatibility or explain and test a migration.
- Credit borrowed work and retain its license notices. Contributions are
  accepted under the project's Apache-2.0 license unless explicitly marked
  third-party code under its existing license. Do not relicense vendored code.
- You are responsible for understanding and validating submitted code,
  including code produced with AI assistance. Explain material tool assistance
  when it helps reviewers understand a change; a tool's output is not test evidence.
- Address review comments and keep the description aligned with the final patch.

Maintainers may ask for a smaller change, additional evidence or a separate
proposal for large features. Direct maintenance on `main` is currently possible;
contributors should use PRs. Merged feature branches are cleaned up automatically.

## Releases and credit

Use new version tags for new release builds. Never silently replace a published
installer with different code under the same version. Build from the tagged
commit, include checksums and licenses, and describe validation and known limits.
See [maintainer guidance](docs/maintaining.md) and [change history](CHANGELOG.md).

AC4 reports belong in this repository, not sal063's AC5 issue tracker. The
upstream recompiler/runtime attribution remains in the README and release licenses.
