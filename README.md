# ps2recomp: Ace Combat 04: Shattered Skies

A static recompilation of **Ace Combat 04: Shattered Skies** (PS2, NTSC-U, SLUS-20152) for Windows.

This project is built on [sal063's Ace Combat 5 static recompilation](https://github.com/sal063/Ace-Combat-5-Static-recompilation): the recompiler, the runtime and most of what is described here are their work. This fork adds an Ace Combat 04 configuration, the AC4-specific system code, and a set of emulation and renderer fixes that AC4 needed. The AC5 build, its config and its native renderer have been removed; sal063's repository has them.

The game's main CPU code isn't emulated. A Python tool reads the original executable and translates every function into C ahead of time, and GCC compiles that together with a runtime that stands in for the rest of the console: the GS (drawn through Vulkan), the VU vector units, SPU2 audio, the IPU for the movies, the IOP modules, memory cards and controllers. The result is a normal `ac4.exe`.

There's no game code or assets in this repo. You bring your own copy of the game; the recompiler builds the C code from it on your machine, which is why `generated/` is in `.gitignore`.

## Status

- Boot, memory card, the opening movie, title and menus, story movies with sound, briefings, the hangar, and **Mission 01 in flight** (HUD, radio, music, voices, effects) are checked start to finish at native resolution and at 6x internal resolution.
- **Saving and loading** work (pre-mission SAVE, title-screen LOAD and CONTINUE).
- **Controller vibration**, rebindable keyboard and controller, PCSX2-style analog settings.
- The picture defaults to an undistorted 4:3 image in wide windows. AC4 does not yet have a verified game-specific 16:9 camera patch; AC5's patch is not applied.
- **HD texture packs**: the game's textures can be saved, upscaled with Real-ESRGAN and drawn in place of the PS2 originals (aircraft, hangar, terrain, menus). See [HD textures](#hd-textures).
- The F4 system menu has a **Mods** page for viewing installed mods and changing which ones load at the next launch.
- The Windows executable uses the Ace Combat 04 ISAF insignia as its application icon.
- Later missions haven't been played yet. The title screen's demonstration flights, recorded in several of them (snowy mountains, a bridge, a low pass through a city, the cockpit view), render correctly.

How AC4 differs from AC5 under the hood:

- AC4 is drawn entirely through the emulated GS. AC5's native renderer was written for AC5's own VU1 programs and has been removed.
- AC4's sound modules (`SOUND.IRX`, `VAG.IRX`) are replaced by native code written from their own symbol tables.
- The config files in `config/ac4/` were rebuilt from the executable alone, without IDA or the PS2 SDK. `README_AC4.md` explains how.

## What you need

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

## Step 1: get the executable off the disc

The recompiler needs one file from the disc, `SLUS_201.52`, in the root of the ISO. Mount the ISO (double-click it in Explorer) or open it with 7-Zip and copy the file out. Check it:

```powershell
Get-FileHash .\SLUS_201.52 -Algorithm SHA256
```

```
38ECEBD6965C2F74EC8973F538781506BF3A2CFAD86F908DEB6C5D585D528301
```

It should be exactly 3,248,756 bytes. If the hash doesn't match, stop: a different region or a modified executable won't line up with the config files. Keep the ISO; the game reads its models, textures, sound and movies from it while you play.

## Step 2: recompile and build

From an MSYS2 UCRT64 shell (or Git Bash with `C:\msys64\ucrt64\bin` on the PATH), in the root of this repo:

```
bash tools/build_ac4.sh path/to/SLUS_201.52
```

That runs the recompiler with the AC4 config (about 5,950 functions into `generated/`), configures CMake the first time, and builds. Expect several minutes: every generated file is essentially one huge function. You get:

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
    -DCMAKE_CXX_COMPILER=C:/msys64/ucrt64/bin/c++.exe
cmake --build build/gcc
```

Use every flag: the overrides replace SDK functions that talk to hardware the PC doesn't have (SIF RPC, the CD drive, the pads) with native handlers, and without them the game waits forever.
</details>

## Step 3: play

Quickest, from the repo root:

```powershell
.\build\gcc\ac4.exe --data generated --disc "C:\path\to\Ace Combat 04 - Shattered Skies (USA).iso" --watchdog 0
```

For a folder you can double-click, lay it out like this (the files in `packaging/ac4/` do the rest):

```
Ace Combat 04/
  Ace Combat 04.exe        <- build with packaging/ac4/launcher/build-launcher.bat (no console window)
  PLAY.bat, DIAGNOSTICS.bat, README.txt   <- from packaging/ac4/
  your ISO
  runtime/
    ac4.exe, shaders/, ps2_image.bin (from generated/),
    SDL3.dll, libwinpthread-1.dll, libiconv-2.dll (from C:\msys64\ucrt64\bin)
```

The launcher and `PLAY.bat` find the ISO in the folder, keep saves in `saves/`, and write the session log to `last-play.log`. `DIAGNOSTICS.bat` runs with profiling and the developer hotkeys on and writes `diagnostics.log`.

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

The details, with the debug switches used to find each one, are in `README_AC4.md`. In short:

- **VU pair hazards**: when a lower instruction loads a register the upper one reads in the same cycle, the upper must see the old value (aircraft were invisible).
- **24-bit texture uploads** (font palettes: smudged text, over-bright menus), **64-pixel channel shuffles** (self-shadowed aircraft drew black).
- **Palettes drawn by the GPU**: the sun's halo palette is rendered every frame; it is now looked up from the render target (the sun was a square of rainbow rings).
- **Depth clears done with colour draws** into the Z buffer's memory (black shapes over the hangar).
- **Per-pixel mip levels** for `TEX1.LCM=0`, blended between levels as the game asks (trilinear): distant terrain lives only in the small levels of AC4's terrain texture cache (islands were big wrong squares at a distance, then showed seams between tiles).
- **Palette indices read from the frame** (PSMT8H from a render target): the haze and sea-detail layer is weighted by an alpha remap of the back buffer (the haze was uniform and the sea nearly black).
- **Presentation**: fields are never dropped, each field keeps its own display buffer, and present semaphores are per swapchain image (single frames of an older picture flashed on screen).
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
- `packaging/ac4/`: the launcher source, `PLAY.bat`, `DIAGNOSTICS.bat`, `MAKE_HD_TEXTURES.bat` and the player README
- `third_party/`: Dear ImGui (settings menu) and Lua 5.4 (mod scripts; see `mods/README.md`)
- `generated/`: the recompiler's output, created in step 2

Tests: the scripts in `tools/` named `test_*.py` and `check_*.py` run without the game; `ac4.exe --vu-test --novideo` runs the VU self-test.

## Credits

- **sal063**: the Ace Combat 5 static recompilation this is built on: recompiler, runtime, renderer, settings menu and tooling.
- PCSX2's game database was the reference for which GS behaviours AC04 depends on.
- Dear ImGui and Lua, under their own licenses.

## Legal

Ace Combat is a trademark of Bandai Namco Entertainment. This project isn't affiliated with or endorsed by them. No game files are included or will be shared.

The code is released under the Apache License 2.0 (see `LICENSE`), as is the project it is based on. Dear ImGui is MIT licensed (`third_party/imgui/LICENSE.txt`), and so is Lua (`third_party/lua/LICENSE.html`).
