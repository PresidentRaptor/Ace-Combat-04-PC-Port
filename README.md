# Ace Combat 04: Shattered Skies - PC Port

A work-in-progress native Windows port of **Ace Combat 04: Shattered Skies**
(PlayStation 2, USA, SLUS-20152), built through static recompilation.

The priority is faithful gameplay with the original assets: correct rendering,
audio, controls, saving and widescreen presentation. Higher rendering resolutions,
edge smoothing and replacement textures are available; HD texture packs are optional.
This is not a complete remaster or a fully validated campaign release.

The original executable's main CPU functions are translated to C ahead of time
and compiled into `ac4.exe`. A shared runtime implements the console services,
Vulkan GS graphics, vector units, audio, movie decoding, memory cards and input.
The port runs independently of an Ace Combat 5 installation.

The recompiler and shared runtime originate in
[sal063's Ace Combat 5 static recompilation](https://github.com/sal063/Ace-Combat-5-Static-recompilation).
This project adds the AC4 configuration, native AC4 sound services, and the
rendering, widescreen and Windows fixes described below. Original attribution
and licenses are retained.

You must supply the supported game executable and disc data. The recompiled
game source and extracted game assets are not distributed; `generated/` is
created locally from your copy of the game.

Repository: [PresidentRaptor/Ace-Combat-04-PC-Port](https://github.com/PresidentRaptor/Ace-Combat-04-PC-Port).

## Current status

- **Mission 01 completed in live play.** Boot, opening and story movies,
  briefings, aircraft/weapon selection, and flight have been checked at native
  and 6x internal resolution. Later campaign missions still need full playthroughs;
  title-screen demonstration flights provide only limited additional coverage.
- **Audio and saving:** music, radio, voices and effects work in the tested
  sections; pre-mission SAVE and title-screen LOAD/CONTINUE have been verified.
  The startup audio spike is fixed and confirmed in live play.
- **Widescreen:** an AC4 camera correction widens the 3D view while menus and
  movies retain their 4:3 layout. HUD placement is configurable. Target diamonds,
  hangar selector guides, downward-view effects and the objectives screen's scan
  overlay have received separate fixes. Original 4:3 presentation remains available.
- **Windows controls and display:** keyboard/controller rebinding, analog settings,
  vibration, fullscreen, an ISAF application icon and an F4 settings menu.
- **Image quality:** up to 8x internal resolution, UI smoothing, FXAA and sharpening.
  These smooth the original assets; they do not add missing texture detail.
  [Optional replacement texture packs](#hd-textures) can supply higher-resolution art.
- **Mods:** F4 lists installed mods and selects which load at startup. Lua mods
  use `ac4`; native mods use `ac4mod.h`. Legacy API names remain compatible.
  See the [mod guide](mods/README.md).

For implementation details and test coverage, see the
[technical notes](docs/technical-notes.md), [Windows validation](docs/windows-validation.md),
[widescreen fixes](docs/widescreen.md) and
[audio/render follow-up](docs/audio-and-rendering.md).

## Build and run

### Windows installer

The [2.2.3 Beta release](https://github.com/PresidentRaptor/Ace-Combat-04-PC-Port/releases/tag/v2.2.3-beta)
includes a Windows setup executable. Select your unmodified USA ISO (SLUS-20152),
choose an empty game folder, and leave the desktop-shortcut option enabled if
wanted. Setup verifies the game executable, copies the ISO and creates the local
memory image. The download contains no ISO or extracted memory image. About
4 GB free space and Windows' .NET Framework 4.8 are needed in addition to a
Vulkan 1.3-capable GPU/driver. No compiler or Python is required to install.

The installer uses a folder under your account by default. Install updates into
a new folder and copy your saves; existing game folders are not overwritten.
For packaging details, see the [installer guide](packaging/ac4/installer/README.md).

The following steps are for building from source. If you already have a locally
assembled game folder, launch `Ace Combat 04.exe` there.

### Requirements

- **The game.** The US release, SLUS-20152, as an ISO (or extracted disc files). Other regions won't work: the config files are tied to addresses in the US executable.
- **64-bit Windows** and a GPU with a Vulkan 1.3 driver.
- **[MSYS2](https://www.msys2.org)**. In the MSYS2 UCRT64 shell:

  ```
  pacman -S mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-sdl3 mingw-w64-ucrt-x86_64-pkgconf \
            mingw-w64-ucrt-x86_64-vulkan-headers mingw-w64-ucrt-x86_64-vulkan-loader \
            mingw-w64-ucrt-x86_64-shaderc
  ```

  GCC must be 15 or newer: the generated code relies on guaranteed tail calls (`[[gnu::musttail]]`).
- **CMake** 3.20+, **Ninja**, and **Python 3** (standard library only).

### Step 1: get the executable off the disc

The recompiler needs one file from the disc, `SLUS_201.52`, in the root of the ISO. Mount the ISO (double-click it in Explorer) or open it with 7-Zip and copy the file out. Check it:

```powershell
Get-FileHash .\SLUS_201.52 -Algorithm SHA256
```

```
38ECEBD6965C2F74EC8973F538781506BF3A2CFAD86F908DEB6C5D585D528301
```

It should be exactly 3,248,756 bytes. If the hash doesn't match, stop: a different region or a modified executable won't line up with the config files. Keep the ISO; the game reads its models, textures, sound and movies from it while you play.

### Step 2: recompile and build

From an MSYS2 UCRT64 shell (or Git Bash with `C:\msys64\ucrt64\bin` on the PATH), in the root of this repo:

```
bash tools/build_ac4.sh path/to/SLUS_201.52
```

That translates the game functions into `generated/` using the AC4 configuration,
configures CMake the first time, and builds. Expect several minutes for the
initial compilation. You get:

- `build/gcc/ac4.exe`: the game
- `build/gcc/shaders/`: the compiled shaders (must stay next to the exe, or set `PS2_SHADER_DIR`)
- `build/gcc/gsreplay.exe`: a developer tool that replays graphics captures

<details>
<summary>The same steps by hand (PowerShell)</summary>

```powershell
$env:PATH = "C:\msys64\ucrt64\bin;$env:PATH"
$env:PYTHONPATH = "tools"
python -m ps2recomp "C:\path\to\SLUS_201.52" -o generated `
    --ida-db config/ac4/ida_db.json --ida-seeds config/ac4/seeds.json `
    --symbols config/ac4/sdk_symbols.json --symbols config/ac4/manual_symbols.json `
    --overrides config/ac4/overrides.json --hooks config/ac4/hooks.json
cmake -S . -B build/gcc -G Ninja -DCMAKE_BUILD_TYPE=Release `
    -DCMAKE_C_COMPILER=C:/msys64/ucrt64/bin/gcc.exe `
    -DCMAKE_CXX_COMPILER=C:/msys64/ucrt64/bin/c++.exe `
    -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64
cmake --build build/gcc
```

Use every flag: the overrides replace SDK functions that talk to hardware the PC doesn't have (SIF RPC, the CD drive, the pads) with native handlers, and without them the game waits forever.
</details>

### Step 3: play

Quickest, from the repo root:

```powershell
.\build\gcc\ac4.exe --data generated --disc "C:\path\to\Ace Combat 04 - Shattered Skies (USA).iso" --watchdog 0
```

For a folder you can double-click, copy the scripts and player README from
`packaging/ac4/` and arrange the local build as follows:

```
Ace Combat 04/
  Ace Combat 04.exe        <- optional launcher, built as described below
  DIAGNOSTICS.bat, README.txt   <- from packaging/ac4/
  MAKE_HD_TEXTURES.bat     <- optional, from packaging/ac4/
  your ISO
  runtime/
    ac4.exe, shaders/, ps2_image.bin (from generated/),
    SDL3.dll, libwinpthread-1.dll, libiconv-2.dll (from C:\msys64\ucrt64\bin)
```

For the optional launcher, copy `packaging/ac4/launcher/` to `launcher/` inside
that game folder, then run its `build-launcher.bat`. It writes
`Ace Combat 04.exe` into the parent game folder and uses `icon.ico` if present.
`ac4.exe` is the runtime; `Ace Combat 04.exe` is the small launcher. Keep these
filenames when updating, because the scripts and launcher use them.

To use `MAKE_HD_TEXTURES.bat`, also keep the source checkout in the game
folder as `src/`; that script calls `src/tools/texture_pack.py`. Building and
playing with original textures do not require Real-ESRGAN or Pillow.

The launcher finds the ISO in the folder, keeps saves in `saves/`, and writes the session log to `last-play.log`. `DIAGNOSTICS.bat` runs with profiling and the developer hotkeys on and writes `diagnostics.log`.

- **Saves** go to `saves/` (or `PS2_SAVE_DIR`). They use this runtime's own card format, not PCSX2's.
- **Settings** are saved to `ac4_settings.ini` next to `ac4.exe`; compiled GPU pipelines are cached in `ac4_pipelines.*` (safe to delete).

### Controls and the settings menu

Controllers go through SDL; buttons map by position (bottom face = Cross, right = Circle, left = Square, top = Triangle; bumpers L1/R1, triggers L2/R2). Keyboard defaults:

| PS2 | Keyboard |
| --- | --- |
| D-pad | Arrow keys |
| Cross, Circle, Square, Triangle | X, S, Z, A |
| L1, R1 / L2, R2 | Q, E / 1, 3 |
| Left stick | Numpad 8, 4, 2, 6 (W also works for up) |
| Start, Select | Enter, Right Shift |

- **F4** opens the settings menu: graphics presets and internal resolution (up to 8x), display and presentation, texture filtering and post-processing, master volume, vibration, keyboard and controller bindings, and PCSX2-style analog dead zones.
- **F11** or **Alt+Enter** toggles fullscreen.
- **Esc** asks before quitting (or closes the menu).
- F6 to F10 are capture and trace tools for development; they only work with `PS2_DEV_KEYS=1` (DIAGNOSTICS.bat sets it).

### HD textures

The runtime can draw replacement textures, at up to 8x the PS2's resolution, in place of the originals. A replacement is matched by the original's pixels, so it follows a texture wherever the game loads it. No textures are included: a pack is made on your machine from your copy of the game.

1. In the game, open **F4 > Rendering** and tick **Save textures for upscaling**, then play the parts you want covered (menus, the hangar, missions; the title screen's demonstration flights cover several later missions). Textures go to `textures\dump`, each saved once; pictures that change every frame, like movies, are skipped.
2. Upscale them: `MAKE_HD_TEXTURES.bat` in the game folder, or `python tools/texture_pack.py upscale textures/dump --output textures/hd/upscaled --esrgan <realesrgan-ncnn-vulkan.exe>`. This needs Python with Pillow and the Windows [Real-ESRGAN ncnn Vulkan](https://github.com/xinntao/Real-ESRGAN/releases) build. Photographic textures (terrain, aircraft skins, the hangar) use Real-ESRGAN's general model, and text and menu art its anime model. Textures up to 512 px are scaled 4x and up to 1024 px 2x. Running it again only adds textures that aren't in a pack yet.
3. Restart the game. **F4 > Rendering > HD texture pack** switches the pack on and off, for comparison.

Replacements are read in the background the first time they're drawn, and use up to 4 GB of RAM (`PS2_TEXTURE_PACK_MB`). Far away they fade back to the original's level of detail instead of shimmering. To change one by hand, `python tools/texture_pack.py export textures/dump` writes PNGs and a contact sheet, and `import ORIGINAL.pam EDITED.png` packages your edit; files directly in `textures\hd` take priority over `textures\hd\upscaled`.

## What was fixed for AC4

Implementation details and diagnostic switches are in the [technical notes](docs/technical-notes.md). The main corrections include:

- **VU pair hazards**: when a lower instruction loads a register the upper one reads in the same cycle, the upper must see the old value (aircraft were invisible).
- **24-bit texture uploads** (font palettes: smudged text, over-bright menus), **64-pixel channel shuffles** (self-shadowed aircraft drew black).
- **Palettes drawn by the GPU**: the sun's halo palette is rendered every frame; it is now looked up from the render target (the sun was a square of rainbow rings).
- **Depth clears done with colour draws** into the Z buffer's memory (black shapes over the hangar).
- **Per-pixel mip levels** for `TEX1.LCM=0`, blended between levels as the game asks (trilinear): distant terrain lives only in the small levels of AC4's terrain texture cache (islands were big wrong squares at a distance, then showed seams between tiles).
- **Palette indices read from the frame** (PSMT8H from a render target): the haze and sea-detail layer is weighted by an alpha remap of the back buffer (the haze was uniform and the sea nearly black).
- **Presentation**: fields are never dropped, each field keeps its own display buffer, and present semaphores are per swapchain image (single frames of an older picture flashed on screen).
- **Widescreen layout**: camera/HUD alignment, menu selector guides, objectives scan clipping and framebuffer effects are handled separately so menu fixes do not crop gameplay.
- **Streaming audio**: stale IOP staging reads are invalidated before playback, preventing the startup spike.
- **Upscaled 2D**: sprites keep to the texels the PS2 samples at native resolution (thin lines around text boxes at higher resolutions).

## Troubleshooting

- **A crash at startup inside a `...Vulkan...` or `OSD` DLL.** Overlays inject themselves into every Vulkan program (GPU Tweak III OSD, ReShade, OBS, Steam, RTSS...). Try again with the overlay closed.
- **CMake can't find Vulkan, `sdl3` or `glslc`.** The MSYS2 packages above are missing, or `C:\msys64\ucrt64\bin` isn't on the PATH in that window.
- **CMake warns there's no musttail attribute.** GCC is older than 15.
- **`ac4.exe` complains about a missing DLL.** Copy `SDL3.dll`, `libwinpthread-1.dll` and `libiconv-2.dll` from `C:\msys64\ucrt64\bin` next to it.
- **`vk: cannot open shader`.** The `shaders` folder isn't next to `ac4.exe`; move it back or set `PS2_SHADER_DIR`.
- **The game quits by itself with a WATCHDOG message.** Add `--watchdog 0`.
- For a bug report, run `DIAGNOSTICS.bat` and attach `diagnostics.log`.

## What's in here

- `tools/ps2recomp/`: the recompiler (ELF in, C out); `tools/vurecomp/`: the VU1 microprogram recompiler
- `tools/`: AC4 config builders (`find_entries.py`, `find_switches.py`, `port_symbols.py`), analysis tools (`listing.py`, `irx_dis.py`) and tests
- `runtime/`: everything that stands in for the console, plus the settings menu; `runtime/src/ps2_hle_ac4.c` is AC4's sound system
- `runtime/shaders/`: the GLSL shaders, compiled at build time
- `config/ac4/`: AC4's function entries, jump tables, symbols, overrides and hooks
- `packaging/ac4/`: the launcher source, `DIAGNOSTICS.bat`, `MAKE_HD_TEXTURES.bat` and the player README
- `docs/`: technical notes, validation evidence and optional texture-work checkpoints
- `third_party/`: Dear ImGui (settings menu) and Lua 5.4 (mod scripts; see `mods/README.md`)
- `generated/`: the recompiler's output, created in step 2

## Development and validation

From the source root, with the UCRT64 compiler on `PATH`, these focused checks
run without the game disc:

```powershell
python tools/test_ac4_audio.py
python tools/test_ac4_widescreen.py
python tools/test_ac4_texture_pool.py
python tools/test_patch.py
python tools/test_settings.py
python tools/check_gs_sampling.py
```

Some other tests need additional fixtures or dependencies. In particular,
`tools/test_ac4_mod_api.py` needs the built Windows runtime, generated data and
the supported ISO in the source checkout's parent folder; it verifies native/Lua
API names and compatibility aliases. Texture-pack tests need Pillow.
`ac4.exe --vu-test --novideo` runs the VU self-test.

A passing test or capture replay does not establish full campaign compatibility.
For reports, include the mission, camera view, graphics settings, steps to reproduce,
and `diagnostics.log` from `DIAGNOSTICS.bat`. Keep game assets and captures containing
game data out of public source commits.

## Contributing and support

See the [contribution guide](CONTRIBUTING.md), [Code of Conduct](CODE_OF_CONDUCT.md),
[support guide](SUPPORT.md), [security policy](SECURITY.md) and
[compatibility checklist](docs/compatibility.md). Use the repository's issue forms
for reports and proposals. AC4 bugs belong here rather than in the upstream AC5
tracker. Never attach ISOs or extracted game data.

Run `python tools/run_checks.py` for the game-data-free checks used in GitHub
Actions. They do not establish full Windows or campaign compatibility. See the
[change history](CHANGELOG.md) and [maintainer checklist](docs/maintaining.md)
for release practices and current repository limitations.

## Credits

- **sal063**: original Ace Combat 5 static recompilation, including the shared recompiler, runtime, renderer, settings menu and tooling.
- **AC4 port contributors and testers**: AC4 configuration, sound services, renderer corrections, widescreen integration, Windows packaging and playtesting; see the repository commit history.
- PCSX2's game database was the reference for which GS behaviours AC04 depends on.
- Dear ImGui and Lua, under their own licenses.

## Legal

Ace Combat is a trademark of Bandai Namco Entertainment. This project isn't affiliated with or endorsed by them. No game files are included or will be shared.

The code is released under the Apache License 2.0 (see `LICENSE`), as is the project it is based on. Dear ImGui is MIT licensed (`third_party/imgui/LICENSE.txt`), and so is Lua (`third_party/lua/LICENSE.html`).
