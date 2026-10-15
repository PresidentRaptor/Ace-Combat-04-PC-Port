# Change history

## Unreleased

- Organized developer documentation under `docs/` and removed retired experiments.
- Added contribution, conduct, security and support guidance, issue/PR templates,
  a compatibility checklist and game-data-free source checks for CI.

## 2.2.0 Beta

[Release and installer](https://github.com/PresidentRaptor/Ace-Combat-04-PC-Port/releases/tag/v2.2.0-beta)
— tagged commit `acb3843`.

- Windows folder-based installer verifies the USA executable inside the user's
  ISO, imports the disc, generates its memory image locally and offers a desktop shortcut.
- Included runtime DLLs/shaders, clean High/3x defaults, widescreen, FXAA and UI smoothing.
- Includes target-diamond, hangar-guide, objectives-scan, downward-view and startup-audio fixes.
- Uses AC4 mod API names with legacy compatibility aliases.
- Installer and SHA-256 checksums published without ISO or extracted game data.
- Mission 01 completed in live play; full campaign coverage remains incomplete.

The earlier AC5 version tags belong to the upstream project's history, not AC4
releases. Detailed implementation evidence is retained in the [development notes](docs/README.md).
