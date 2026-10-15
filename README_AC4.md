# Ace Combat 04 PC Port - Technical Notes

This project builds **Ace Combat 04: Shattered Skies (USA, SLUS-20152)** as
`ac4.exe` for Windows. It runs independently of an Ace Combat 5 installation.

The recompiler and shared runtime originated in
[sal063's Ace Combat 5 static recompilation](https://github.com/sal063/Ace-Combat-5-Static-recompilation)
(commit 078662b). Original attribution and the Apache 2.0 license are retained.

For player-facing setup and the current support summary, see [README.md](README.md).

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

AC5's config came from IDA and the PS2 SDK. AC4's was rebuilt from the executable alone:

| file | made by | what |
| --- | --- | --- |
| `config/ac4/seeds.json` | `tools/find_entries.py` | function entries: code after returns/tail calls, frame openers, code pointers in data |
| `config/ac4/ida_db.json` | `tools/find_switches.py` | `jr $reg` jump tables (131 of 134; the rest are `longjmp` and hand-written asm) |
| `config/ac4/sdk_symbols.json` | `tools/port_symbols.py` | SDK names carried over from AC5 (its ELF and sal063's `config/`) by masked-signature, fuzzy and call-graph matching |
| `config/ac4/manual_symbols.json` | by hand | libpad, the rest of libcdvd, functions the matcher can't place |
| `config/ac4/overrides.json` | | the SIF/CD overrides that exist in AC4, plus the old (SDK 2.x) libpad |

Coverage is 99.46% of `.text`. `tools/listing.py` (annotated disassembly, `--xref`,
`--summary`) and `tools/irx_dis.py` (IOP modules with their symbols) were the working tools.

## Runtime changes

AC4-specific (formerly `#ifdef PS2_GAME_AC4`, or AC4-only files):

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
- AC5's native VU1 renderer (it implemented AC5's microcode) has been removed; everything is
  drawn through the emulated GS. `rn/rn_dump.c` remains: `PS2_RN_DUMP=<file>` with
  `PS2_RN_DUMP_FIELD=<n>` writes one field's VIF1 unpacks, XGKICKs and GS register writes.
- **16:9 widescreen** (F4 > Display, `[display] widescreen`; `ps2_hook.c` `vsm_before`,
  `ps2_gs.c` `ws_hud`, `ps2_vk_game_aspect` in `ps2_video.c`). AC5's camera patch targets
  SLUS-20851 and is never applied here; PCSX2's AC4 entry (one word at 0040DACC, 769.15 ->
  627.87) only shortens one camera's focal length. Every AC4 camera goes through
  `sceVu0ViewScreenMatrix` (00263718). The camera object keeps the size of its virtual
  screen at +352/+356 (640 x 480), focal length at +360, viewport at +392..+398 (512 x 448 in
  flight) and ax/ay = viewport / virtual size at +384/+388; the view cone that culls the world
  and clips the sea-glare fan is worked out from +352/+356 (sub_00102798). A hook before
  00263718 widens +352 for the on-screen cameras (called from 00102AC0, 00142200, 00246CE8;
  the matrix is camera + 96) to 640 x aspect / (4/3), 853.33 at 16:9, and scales this call's
  ax to match. Cameras copy these fields between each other, so a value the hook wrote is
  recognised and never widened twice; turning widescreen off writes 640 back. Widening only
  the ax argument left a jagged unlit band at the bottom corners (the sea-glare fan stayed
  clipped to the 4:3 cone). The self-shadow projection (called from 001146BC) is left alone.
  The HUD: 2D draws (not PATH1) into a display-sized target (at least 480 x 400) whose
  vertices all sit at Z max (flight HUD) or Z 0 (menus, captions, movies) with the depth test
  off (or ZTE 0) are pulled towards the centre by (4/3) / aspect, scissor included. Left
  alone: depth-tested draws (target boxes, their dotted trails and FRND/TGT labels are drawn
  with ZTST GREATER, even the parts at Z max, and were already placed by the widened camera),
  draws with real depth (sun flare, lens ghosts), full-width copies and non-UI draws, untextured full-height
  ones (fades and clears, drawn in 64-pixel strips), render-target copies and off-screen
  targets (the 512 x 128 cloud target). Movies and menus come out pillarboxed 4:3. With
  widescreen off nothing changes: the 12 captures replay pixel-identical. The lock-on arrow
  and seeker diamond are small untextured shapes placed at the target but drawn without the
  depth test; they are left in place when they touch a target box of this or the previous
  frame (the boxes come later in the frame), axis-aligned tape ticks excepted. HUD layout 2
  (`hud_layout = 2`, AC4's default, "corners at the screen edges") anchors the flight HUD's
  corner blocks to the sides instead of the centre: PTS/TGT and the radar (and the enlarged
  map, everything clipped to the radar's scissor at the left) left, TIME and the
  weapon/damage block right, recognised by position on the 512 x 448 layout (`ws_hud`);
  the speed/altitude tape numbers scroll into the radar's and weapon list's rows, so there
  only pieces the tapes never have count. The pitch ladder turns within ~150 px of the
  centre and never reaches a block. Captions, tapes, ladder and menus stay centred. `PS2_TRACE_VSM=1`
  logs the distinct calls of 00263718 and the on-screen cameras' fields; `PS2_VSM_SKIP=ra,...`
  leaves more callers (return addresses, hex) alone; `PS2_TRACE_WS=N[:M]` logs each primitive
  kept 4:3 in fields N..M. When the frame's squeezed Z-0 textured draws cover more than 35%
  of the target (a menu, briefing, hangar overlay or movie), the presentation scissors the
  picture to the 4:3 middle for that and the next 12 fields (`ps2_ws_pillar_frame`), so the
  sides show black instead of stretched leftovers and half-covered 3D.
  Z-zero menu highlights always use the menu transform, including red
  rectangles beside weapon cells; flight lock-cue exemptions do not apply to
  them. Far-plane flight HUD glyphs override the menu-coverage heuristic for
  the current and following field, so pausing and resuming does not crop the
  gameplay/HUD to the menu's middle. `tools/test_ac4_widescreen.py` exercises
  these cases against the actual C layout code. `gsreplay --widescreen` applies
  the layout to a capture taken with a widened camera; it does not widen an
  already recorded camera. `PS2_TRACE_WS_CUES=1` logs small target/cue draw
  coordinates every 30 fields for diagnosing marker projection.
  The textured seeker diamond is recognised by its HUD source cell, so it
  stays with its target when crossing captions, warnings or corner blocks;
  a screen-position exclusion must not squeeze that sprite like text.
  Pillarboxing is restricted to a displayed width of at least 640 columns:
  flight's 512-column viewport cannot trigger menu bars, even if HUD sprites
  disappear during camera changes or the 640-column backing target retains
  earlier menu coverage. The hangar's full-width/full-height line guides are
  transformed with its selector; copies, fades and clearing strips retain
  full coverage. Full-width indexed Z-zero UI sprites, including the objectives
  scan, use the centered transform and scissor even on a 512-column display.
  See [the regression notes](WIDESCREEN_REGRESSIONS.md) for recorded evidence.
- High and Ultra use bilinear sampling for enlarged screen-space UI art, which smooths map and HUD icons; original PS2 texture data remains native resolution unless a replacement-texture pack is enabled. For internal resolution that follows the window, pick Ultra and set Internal resolution to Auto (the smallest factor that covers the window, up to 8x).
- `sceSifSetDma` writes to IOP RAM; the first `sceMcGetInfo` reports a newly inserted card;
  the graphics machine stays on the EE thread by default (`PS2_ASYNC_GFX=1` brings the
  async thread back; see below).

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
- **upscaled sprites**: a sprite (bilinear, or point-sampled under smoothed UI) carries the texel range it samples at native
  resolution (`PS2_VK_RUV_CLAMP`, `clamp_u`/`clamp_v`, vertex attribute 5) and gs.frag keeps
  upscaled sub-pixels inside it, so text boxes, subtitles and HUD labels no longer pick up
  neighbouring texels as thin lines along their edges (PCSX2 needs "round sprite" for this game).
  Native-resolution output is unchanged.
- **GIF Q reset per tag** (`ps2_hw.c` `gif_feed`): the GIF's internal Q (what a packed RGBA
  writes into RGBAQ.Q) is reset to 1.0 at every GIFtag. AC4's enlarged radar map (Square) is
  an STQ sprite with S,T in 0..1 sent without a Q of its own; the Q left over from the last
  3D packet (~2e-5) tiled its 128 x 128 map texture tens of thousands of times, so the map
  showed a dot pattern instead of the islands. The 12 captures replay pixel-identical.
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
  0x2E00, 0x2E40), so level 0 showed a near tile's texture on the distant island.
  Triangles get the level per pixel (`gs_tri_mip_range`, `gs_dyn_mip`, ps2_vk_state.mip):
  Q is affine in screen space, so a triangle's LOD lies between its vertices' values. It is
  drawn once for each level that range touches (with 1/64 slack), with that level decoded as
  usual; gs.frag works LOD out per pixel from the interpolated Q, discards the pixels that
  belong to another level's draw (the two ends open), and for MMIN 3/5 blends towards the
  next level, decoded too and bound in set 3. AC4's terrain asks for MMIN 5 (trilinear).
  Every pixel is still written once with the triangle's own depth; batching is unchanged
  because the state depends only on the level. A per-triangle choice showed seams where
  neighbouring tiles landed on different levels. Sprites, lines and points keep the
  per-primitive mean (`gs_prim_lod`). `PS2_NO_MIP_BLEND=1` uses the nearest level per pixel,
  `PS2_NO_PIXEL_MIP=1` goes back to one level per triangle, `PS2_NO_DYN_MIP=1` turns
  both off. The native-resolution captures change by at most 4/255 (distant terrain only);
  real time at 6x stays at 60 fields/s.
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
  `[input]` (F4 > Vibration) turns it off; `vibration_strength` (0..1, default 0.65, F4 >
  Vibration strength) scales both motors; `PS2_TRACE_RUMBLE=1` logs the setup and changes.
- **review fixes**: the exit screenshot (`ps2_frame.ppm`) is only written for bounded runs
  (`--vblanks N`) or with `PS2_EXIT_SHOT=1`; the 2D overlay's empty-box sentinel survives a
  signed/unsigned compare; the CLUT-in-render-target lookup requires a PSMCT32/24 target;
  the VAG module no longer logs from the audio thread. Saving and loading were exercised
  (pre-mission SAVE, title LOAD -> CONTINUE).
- **settings/mod menu** uses AC4's navy and light-blue colours (`ps2_ui.cpp`).
- **channel shuffles**: the CT16-over-CT32 shuffle sprite is also recognised when its
  64-pixel strips end exactly on the boundary (AC5 ends them half a pixel short). AC4's
  aircraft self-shadow (shadow volumes counted into a half-size buffer, shuffled into
  alpha, then `Cd*(1-Ad)`) missed the match, so the whole aircraft was darkened to black.
- **replacement ("HD") textures** (`ps2_texpack.c`, `ps2_video.c` `texture_hd`/`hd_resolve`/
  `ps2_vk_texture_ext`, gs.frag `sample_hd`; started by reviewer Astra): a texture is
  identified by an FNV-1a hash of its decoded RGBA and size, never its VRAM address, and a
  pack is a folder of `<id>_<w>x<h>.pam` files at an integer scale (1-8x). AC4's terrain is
  matched per atlas window (the REGION_CLAMP/REPEAT rectangle of each 64x64 tile and its mip
  levels, which must be a power of two aligned to its size), everything else as the whole
  decode. Only recorded draws bind replacements; the GS keeps its own decode. The pack is
  indexed at start-up (`textures/hd`, subfolders after the files directly in it, so a
  hand-made file wins over `textures/hd/upscaled`); a replacement is read on a loader thread
  the first time it is drawn (the original stands in until then), kept for the session and
  bound without a copy (`ps2_vk_texture_ext`: full mip chain, recycled only among such
  textures, outside the 512 MB decode budget), up to `PS2_TEXTURE_PACK_MB` (4096). New
  uploads are limited to 48 MB a field. gs.frag samples a replacement in GS texel units for
  each bilinear tap (CLAMP, REGION_CLAMP and REGION_REPEAT as on the GS) and steps down its
  mip chain with the screen footprint, as far as the original's resolution, so the detail
  fades with distance instead of shimmering. The per-pixel mip blend binds the next level's
  replacement too. F4 > Rendering: "HD texture pack" (`[graphics] hd_textures`) and "Save
  textures for upscaling" (`textures/dump`, or `PS2_TEXTURE_DUMP=<dir>`): a picture is saved
  the first time it is drawn in a field after the one it appeared in (movie frames are not),
  with its wrap modes in `dump_info.tsv`. `tools/texture_pack.py upscale` runs Real-ESRGAN
  (ncnn Vulkan) over a dump: the general model for photographic textures, the anime model
  for few-colour art and for cut-out alpha (text, decals), borders padded the way the GS
  wraps or clamps, 4x up to 512 px and 2x up to 1024, skipping textures without detail to
  gain and the narrow strips AC4 decodes past their picture (64x1024). `MAKE_HD_TEXTURES.bat`
  wraps it. With no pack and dumping off, every capture replays pixel-identical.

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
resolution 6. Saving (pre-mission menu) and loading (title menu) are verified. Left at the title,
the game cycles its DEMONSTRATION flights, recorded in later missions (snowy mountains with a radar
dome, an F-14 in cloud, a bridge, a low pass between a city's towers, the cockpit view, a bomb
camera over a base); ten minutes of them rendered correctly. Not yet played: later missions.

`PS2_ASYNC_GFX=1` (graphics machine on its own thread) was re-tested after the VU pair fix:
Mission 01 flight at full speed, 1,470 consecutive fields and 1,000 fields sampled every 6th
over 6,000, checked for single-frame outliers against their neighbours, showed none of the
stray triangles seen before, which were most likely that bug. `PS2_TRAP_VU1_EE=1` (leaves
VU1's memory unmapped for the EE and logs every access) found no EE access to VU1 memory from
boot through flight, and the interrupt status the graphics thread raises VIF interrupts into is
now updated atomically. AC4 still defaults to synchronous: the EE thread holds full speed at
6x on a current CPU, and async is the thing to try on a slower one.
