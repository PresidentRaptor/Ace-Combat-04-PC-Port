# Windows installer and release packaging

This per-user, folder-based installer needs no administrator access or build
toolchain on the player's PC. It embeds a ZIP containing only the runtime,
launcher, shaders, DLLs, scripts, settings and license notices. The player selects
an uncompressed USA ISO (SLUS-20152), an empty destination and a desktop-shortcut
option. It validates SYSTEM.CNF and the SHA-256 of SLUS_201.52, builds the same
PT_LOAD memory image as `ps2recomp`, and copies the ISO as `game.iso`.

The original ISO is opened read-only. Installation uses a temporary sibling
directory and moves it into place only after extraction and copying finish.
Cancellation removes that staging directory. Existing nonempty game folders
are rejected to protect saves and personal settings. Upgrades use a fresh folder;
copy saves afterward. The installer does not register an Apps & Features entry.

## Build

From the source root after the normal UCRT64 Release build:

```powershell
python packaging/ac4/installer/build_release.py
```

Requires .NET Framework's `Framework64/v4.0.30319/csc.exe`, the normal
`build/gcc/ac4.exe` and compiled shaders, and UCRT64 DLLs/licenses from
`C:/msys64/ucrt64` (override with `AC4_UCRT_DIR`). No third-party installer
compiler is required. `build/release/2.2.2-beta/` receives the installer,
SHA256SUMS.txt, local payload ZIP and file manifest. Only the installer and
checksum file are GitHub release assets. The source archive is provided by GitHub.

The payload is assembled from an explicit file list. It excludes ISO images,
`generated/`, `ps2_image.bin`, textures, captures, saves and personal settings.
`release-settings.ini` supplies clean High/3x defaults, widescreen, FXAA and UI
smoothing. The game remains configurable through F4.

## Verify before publishing

After building the release, run:

```powershell
python packaging/ac4/installer/test_installer.py --iso "path/to/game.iso"
```

This compiles the C# integration harness and runs it in a fresh directory under
`build/release-tests/`. The test copies the full ISO and checks its hash, creates
and inspects a shortcut in the scratch folder, tests cancellation and rejects
invalid/modified discs and unsafe payload paths. It does not modify the real
desktop or the current game installation. It also renders the setup form and
boots the installed runtime for 180 fields using its own data and copied ISO.

Boot the installed runtime using only its installed data, ISO, DLLs and shaders.
Inspect the payload manifest and embedded ZIP before uploading. Commit the
packaging sources, rebuild so `release.json` records that commit, tag that
commit, and publish the installer with checksums as a prerelease until broader
campaign testing is complete. Do not upload local captures or game data.
