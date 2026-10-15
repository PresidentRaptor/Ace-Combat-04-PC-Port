# Ace Combat 04 PC Port 2.2.0 Beta

This release adds a Windows installer for the current AC4 port. Download
**Ace-Combat-04-PC-Port-2.2.0-beta-Setup.exe** and select your unmodified USA ISO
(SLUS-20152). Setup verifies the executable inside the disc, creates the game
folder, imports the ISO and local memory image, and offers a desktop shortcut.
No ISO or extracted game assets are included in the download.

## Requirements and installation

- Windows 10/11 x64, .NET Framework 4.8 and a Vulkan 1.3 GPU/driver.
- Your own uncompressed USA ISO and about 4 GB of free disk space.
- An empty destination folder. The default is under your user's Local AppData
  folder; administrator access and build tools are not required.
- Leave **Create a desktop shortcut** selected to add the game to your desktop.
  Start it through that shortcut or `Ace Combat 04.exe` in the game folder.
- For an update, install into a new folder and copy your existing `saves/` folder.

The installer is unsigned. SHA256SUMS.txt identifies the exact uploaded build;
it does not provide a publisher signature.

## Included fixes and defaults

- AC4 widescreen camera and configurable HUD placement, with target diamonds
  aligned to their target boxes.
- Corrected hangar selection guides, objectives-screen scan clipping and
  downward chase-view framebuffer effects.
- Startup audio staging-buffer fix, confirmed in normal play.
- High/3x rendering, UI smoothing and FXAA enabled; original game textures.
- ISAF application icon, bundled shaders/DLLs, and project/third-party licenses.
- AC4 mod API naming with legacy compatibility aliases.

## Validation and coverage

Tests reject incorrect/modified disc executables, compare the generated memory
image with the recompiler's output, verify an exact ISO copy and shortcut target,
and exercise cancellation cleanup and protection of existing folders. The
installed runtime passes a 180-field ISO startup smoke test without using the
development data directory. Widescreen, audio and patch regression checks pass.

Mission 01 has been completed in live play. The full campaign is not yet
validated, so this release is marked as a beta/prerelease. F4 opens settings.
For a report, run DIAGNOSTICS.bat and provide the log, mission, camera and settings.
