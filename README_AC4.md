# Ace Combat 04 on the ps2recomp runtime

This tree is the AC5 static recompilation (github.com/sal063/Ace-Combat-5-Static-recompilation,
commit 078662b) extended to build **Ace Combat 04: Shattered Skies (USA, SLUS-20152)**.
`-DPS2_GAME=AC4` (the default here) builds `ac4.exe`; `-DPS2_GAME=AC5` still builds the
original `ac5.exe`.

## Building

Needs MSYS2 UCRT64 with `gcc` (15+), `sdl3`, `pkgconf`, `vulkan-headers`, `vulkan-loader`
and `shaderc`, plus CMake, Ninja and Python 3. Copy `SLUS_201.52` off the disc
(SHA-256 `38ECEBD6965C2F74EC8973F538781506BF3A2CFAD86F908DEB6C5D585D528301`), then:

```
bash tools/build_ac4.sh path/to/SLUS_201.52
```

That regenerates `generated/` and builds `build/gcc/ac4.exe`. To run from the tree:

```
build/gcc/ac4.exe --data generated --disc "path/to/Ace Combat 04 (USA).iso" --watchdog 0
```

## How the AC4 config was made (no IDA, no SDK)

AC5's `config/` comes from IDA and the PS2 SDK. AC4's was rebuilt from the executable alone:

| file | made by | what |
| --- | --- | --- |
| `config/ac4/seeds.json` | `tools/find_entries.py` | function entries: code after returns/tail calls, frame openers, code pointers in data |
| `config/ac4/ida_db.json` | `tools/find_switches.py` | `jr $reg` jump tables (131 of 134; the rest are `longjmp` and hand-written asm) |
| `config/ac4/sdk_symbols.json` | `tools/port_symbols.py` | SDK names carried over from AC5 by masked-signature, fuzzy and call-graph matching |
| `config/ac4/manual_symbols.json` | by hand | libpad, the rest of libcdvd, functions the matcher can't place |
| `config/ac4/overrides.json` | | the SIF/CD overrides that exist in AC4, plus the old (SDK 2.x) libpad |

Coverage is 99.46% of `.text`. `tools/listing.py` (annotated disassembly, `--xref`,
`--summary`) and `tools/irx_dis.py` (IOP modules with their symbols) were the working tools.

## Runtime changes

AC4-specific (`#ifdef PS2_GAME_AC4` or AC4-only files):

- `ps2_hle_ac4.c` — native replacements for AC4's IOP sound modules, written from their own
  symbol tables:
  - **SOUND.IRX** (RPC 81000101): batched command protocol; sound-effect key-on/attributes/key-off
    on the SPU2 voices, bank uploads into SPU RAM, AutoDMA PCM streaming (movie soundtracks)
    and the transfer-status/voice-status replies the EE polls.
  - **VAG.IRX** (RPC 81000102): music and voice streaming. The EE reads blocks into IOP buffers;
    the native module decodes the ADPCM from IOP RAM and mixes it, advancing the buffer index
    that drives the EE's refills.
- `ps2_hle_pad.c` — the original libpad (state machine, modes, actuators, pressure mode).
- `ps2_game.h` — window title, settings/pipeline file names, serial for mods.
- the native VU1 renderer (`rn/`) is off: it implements AC5's microcode.
- the 16:9 camera patch previously used by the AC5 build is not valid for AC4 and is never applied (`ps2_settings.c`). AC4's output defaults to an undistorted 4:3 image on wide displays; a validated game-specific camera patch is still needed for expanded 16:9 gameplay.
- the 4K preset uses display-aware internal resolution (Auto, up to 8x), 16x anisotropic filtering, sharp scaling, and bilinear sampling for enlarged screen-space UI art. This smooths map and HUD icons; original PS2 texture data remains native resolution until a compatible replacement-texture pack exists.
- `sceSifSetDma` writes to IOP RAM; the first `sceMcGetInfo` reports a newly inserted card;
  the graphics machine stays on the EE thread (`PS2_ASYNC_GFX=1` brings the async thread
  back, with intermittent stray-triangle frames in flight).

General fixes that AC4 exposed:

- `sceCdReadIOPm` lands in IOP RAM, not EE RAM.
- toIPU chain DMA honours CHCR.TAG when resumed (libmpeg's per-picture suspend/resume used
  to run into stale tags, starving the decoder at chunk boundaries).
- scratchpad DMA interleave mode (D_SQWC) is implemented.
- the bad-DMA-tag check no longer writes a 50 MB state dump unless `PS2_DUMP_BADTAG` is set.
- **VU upper/lower pairs** (`ps2_vu.c`, and `tools/vurecomp/emit.py` to match): both halves
  of a pair read their sources in the same cycle, so when the lower instruction loads a VF
  register the upper one reads, the upper must still see the old value (AC4's model
  microcode does `MULAx ACC,VF22,VF09x | LQ VF22`). When both halves write the same register the whole lower
  instruction is dropped, LQI/LQD address update included (`--vu-test` covers both cases). Running the lower first made aircraft
  invisible and scattered black triangles over model views.
- **PSMCT24/PSMZ24 uploads** are unpacked at 3 bytes a pixel (16 pixels in 3 quadwords).
  AC4 uploads its font CLUTs as CT24 to keep their alpha bytes; read as 4 bytes a pixel
  the last 4 CLUT entries -- the stroke centres -- stayed black, giving hollow, smudged
  text, and the menu glow textures came out far too bright.
- **upscaled sprites**: a bilinear sprite carries the texel range it samples at native
  resolution (`PS2_VK_RUV_CLAMP`, `clamp_u`/`clamp_v`, vertex attribute 5) and gs.frag keeps
  upscaled sub-pixels inside it, so text boxes, subtitles and HUD labels no longer pick up
  neighbouring texels as thin lines along their edges (PCSX2 needs "round sprite" for this game).
  Native-resolution output is unchanged.
- **no dropped fields** (`ps2_video.c`): a field the renderer had not started used to be
  replaced by the next one, so its draws never ran. AC4 carries render targets from field to
  field (the frame copy, haze and glow buffers), and the field after a drop flashed. The EE
  now waits (at most 100 ms) for the renderer instead; `PS2_DROP_FIELDS=1` restores dropping.
- **CLUTs drawn by the GPU** (`ps2_gs.c`, gs.frag set 3 `clutrt`): when a texture's CLUT lies
  in a render target newer than VRAM (AC4 renders its sun-halo palette every field), the
  texture is decoded to CLUT indices and gs.frag reads the colours from that render target
  (frag flag bit 30, bit 31 for 4-bit; position in the `clut_xy` push constant).
  `PS2_NO_CLUT_RT=1` turns it off. PCSX2 needs its "CPU sprite render" hack for the same draw.
- **presentation** (`ps2_video.c`): the submit signalled a "rendered" semaphore per frame in
  flight (3) for a 4-image MAILBOX swapchain, so under load the semaphore could be signalled
  again before the presentation engine had waited on it, and an image went to the screen
  before it was drawn -- one refresh of whatever that image held before (a picture 4-40
  presents old, its FPS overlay included; the reviewer's capture shows it every second or two
  in flight). The semaphore is now per swapchain image (`swap_rendered[]`), the swapchain
  image's layout change waits at colour-attachment output (the acquire wait stage) instead of
  top-of-pipe, and a SUBOPTIMAL acquire keeps its image and rebuilds the swapchain next time
  instead of acquiring again with a signalled semaphore. The renderer also takes the display
  buffer, offset and size with the field (`pub_present_*`) instead of reading the EE's live
  values, which could already belong to the next field -- AC4 flips between two display
  buffers in menus and the hangar.
- **depth clears through colour draws** (`ps2_gs.c` `zclear_rt`, `ps2_video.c` `zclear_draw`):
  AC4 clears the hangar's Z buffer (ZBP 0x6E000) with an untextured PSMCT32 sprite drawn
  into that address with alpha masked. Each render-target slot here has its own depth
  image, so the sprite only coloured a separate slot and the hangar kept the depth of
  earlier frames (black wedges on the floor, chunks of the aircraft and canopy missing).
  An untextured CT32/CT24/Z32/Z24 draw into memory that another slot's draws use as their
  Z buffer (and write) is now repeated as a depth-only draw on that slot, Z taken from the
  colour bits (R low byte, then G, B, and A for 32-bit). `PS2_NO_ZCLEAR=1` turns it off.
  Menus, flight, landing and the attract demo replay pixel-identical with it on.
- **mipmap level from Q** (`ps2_gs.c` `gs_prim_lod`, `gs_dyn_lod`): with TEX1.LCM=0 the GS
  picks the level per pixel, LOD = (log2(1/|Q|) << L) + K. The runtime only handled LCM=1
  and read level 0 otherwise. AC4's terrain (TEX0 0x2900, 512x512 PSMT8, MXL 3, MTBA,
  K -13.5) is a texture cache: near tiles own slots 0-63 by position, distant tiles get
  slots 64+ that alias the same squares and are uploaded only to levels 1-3 (0x2D00,
  0x2E00, 0x2E40), so level 0 showed a near tile's texture on the distant island. The level
  is now taken per primitive from the mean vertex LOD (rounded, clamped to MXL) and fed to
  the existing fixed-level decode; it is part of the draw-state memo key.
  `PS2_NO_DYN_MIP=1` turns it off. Real time at 6x stays at 60 fields/s.
- **PSMT8H indices from a render target** (`ps2_gs.c` `index_rt`/`clut_palette_texture`,
  gs.frag `flags.y` bit 1): in flight AC4 remaps the back buffer's alpha through a CLUT
  (TEX0 tbp 0, PSMT8H, FBMSK 00FFFFFF; entries `0x80 - i` below 128) and then blends its
  haze/sea-detail layer by destination alpha. The indices are read from the target (a
  self-read snapshot) and looked up in a 256x1 palette texture bound in set 3. Targets
  track when their alpha was last written (`gs_rt_aepoch`): AC4 also packs the aircraft's
  PSMT8H texture into the display buffer's alpha bytes, which draws there mask, so VRAM
  stays the source for it. `PS2_NO_INDEX_RT=1` turns it off; `PS2_TRACE_INDEX_RT=1` logs
  each use; `PS2_LOG_CLUT=<cbp>` dumps a CLUT.
- **vibration** (`ps2_hle_pad.c` SetActAlign/SetActDirect, `ps2_video.c` `apply_rumble`):
  the EE side records the motor levels (small on/off, large 0..255, mapped by the align
  bytes; AC4 aligns 00 01 FF..), and the renderer thread, which owns the SDL gamepad,
  drives `SDL_RumbleGamepad`, renewing a running effect each second. `vibration = 0` in
  `[input]` (F4 > Vibration) turns it off; `PS2_TRACE_RUMBLE=1` logs the setup and changes.
- **review fixes**: the exit screenshot (`ps2_frame.ppm`) is only written for bounded runs
  (`--vblanks N`) or with `PS2_EXIT_SHOT=1`; the 2D overlay's empty-box sentinel survives a
  signed/unsigned compare; the CLUT-in-render-target lookup requires a PSMCT32/24 target;
  the VAG module no longer logs from the audio thread. Saving and loading were exercised
  (pre-mission SAVE, title LOAD -> CONTINUE).
- **settings/mod menu** uses AC4's navy and light-blue colours (`ps2_ui.cpp`, `PS2_GAME_AC4`).
- **channel shuffles**: the CT16-over-CT32 shuffle sprite is also recognised when its
  64-pixel strips end exactly on the boundary (AC5 ends them half a pixel short). AC4's
  aircraft self-shadow (shadow volumes counted into a half-size buffer, shuffled into
  alpha, then `Cd*(1-Ad)`) missed the match, so the whole aircraft was darkened to black.

Debug switches added: `PS2_SNAP_AT=<field>` (state snapshot at a field), `PS2_TRACE_DMA4`,
`PS2_TRACE_MC`, `PS2_IPU_STATS`, `PS2_TRACE_AT_FIELD=<field,...>` (draw trace of the frame
presented at those fields, now with fog and STQ), `PS2_SKIP_DRAWS=<i,...>` and
`PS2_SKIP_KEY=<blend hex>[:<frag flags hex>]` (drop draws from the replayed list),
`PS2_DUMP_TEX_IDX=<n>` (write each texture decoded into Vulkan slot n, with its TEX0/CLUT),
`PS2_PAD_STICK=from-to:LY=0,...` (hold an analog axis on port 0 for a field range),
`PS2_SHOT_FROM=<present>` (first screenshot for `PS2_SHOT_EVERY`),
`PS2_TRACE_TRX_RANGE=lo:hi` (log host->local transfers by destination address),
`PS2_VU_WATCH_VF=16,20,...` (extra VF registers for `PS2_VU_WATCH`, which needs `PS2_CENSUS=1`),
`PS2_SKIP_KEY=blend:flags:texrt`,
`PS2_TRACE_STALE=1` (thumbnail every presented picture on the GPU and log one that repeats a
picture shown 2-96 presents earlier), `PS2_TRACE_REPEAT=1` (log a field whose vertex stream
equals an earlier field's), `PS2_TRACE_RT_MISS=1` (log draws that address a render target
but fall back to VRAM), `PS2_TRACE_VERTS=<draw>` (every vertex of that draw in a
`PS2_TRACE_FRAME` trace), `PS2_TRACE_TRXREGS=1` (BITBLTBUF/TRXPOS/TRXREG/TRXDIR writes),
`PS2_TRACE_TEXCACHE=<n>` (hook on AC4's terrain texture cache sub_0013B2F8: slot
counter and entries before/after n calls), TEX1 and MIPTBP1 in `PS2_TRACE_GSREGS`,
and `PS2_TRACE_GSREGS=<n>` with `PS2_GS_STATE_MEMO=0` (every distinct GS draw state of the
n-th field). `gsreplay` now writes the `PS2_VU_CENSUS` program dump on exit, so
`tools/vurecomp` can be fed from a capture (`--capture-at FIELD --capture-level dma`).

## Status

Verified start to finish: boot, memory card detection, opening FMV, title, menus, story movie
with sound, Mission 01 briefing, and Mission 01 in flight with HUD, radio, music, voices and
sound effects at full speed -- cockpit, HUD-only and external views, with the player's and
the wingmen's aircraft textured and self-shadowed -- at native resolution and at internal
resolution 6. Saving (pre-mission menu) and loading (title menu) are verified. Not yet exercised: later
missions. `PS2_ASYNC_GFX=1` has not been re-tested since the VU pair fix; the stray
triangles seen with it may have been that bug.
