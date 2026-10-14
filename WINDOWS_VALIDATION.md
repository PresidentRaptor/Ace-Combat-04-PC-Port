# Native Windows validation

The priority is faithful play with the existing game assets. HD art remains
optional. These checks establish a development baseline, not error-free coverage
of the entire campaign.

## Edge smoothing

High, Ultra and 4K now enable FXAA and smooth UI texture sampling, with sharpening
reduced from 0.20 to 0.10. Low and Medium retain their existing behavior. Existing
saved settings are respected: reselect a preset to adopt its new values.

The presentation shader applies FXAA and sharpening to the same resolved image
as its center sample. This prevents postprocessing from sampling raw high-
resolution texels and undoing the supersampling average. FXAA skips regions
with little contrast. These options can be compared in F4; they cannot restore
detail absent from the original art.

`gsreplay --preset N` exercises the presentation path with presets 0..4. Its PPM
screenshot captures the game render target before final presentation effects,
so it does not establish the visual quality of FXAA. Final display quality and
performance need live-play comparison.

## Verified in this pass

- Settings persistence/presets and 5,242,880 controller stick cases.
- AC4 streaming audio tests; runtime SPU2, GS, VIF and VU self-tests.
- AC4 HLE controller contract (original libpad): port state, slot rejection,
  active-low buttons, analog sticks, release and output-buffer boundaries.
- AC4 ISO boot files via the HLE test: SYSTEM.CNF serial and SLUS_201.52 ELF magic.
- Recompiler ordering/overrides, GS sampling, texture indexing, readback locking,
  upload streams, input handling, graphics-queue ownership and patch contracts.
- Vulkan replays of aircraft selection at High and Mission 1 islands at Ultra.
- Packaged Windows build boots from the supplied ISO and completes 180 fields
  without reported runtime errors. This is a short startup smoke test.

## Coverage gaps

`tools/test_runtime_regressions.py` contains AC5 guest function addresses and
cannot test the current AC4 generated code. `tools/test_vfs.py` likewise expects
AC5's extracted disc and DATA.TBL. Neither is counted as an AC4 pass. AC4-specific
collision/mission-cleanup and archive tests still need equivalent fixtures.

Later campaign missions, saving/loading across mission transitions, prolonged
audio/video playback, device reconnection, fullscreen changes, expanded mission
map readability and a verified AC4 widescreen camera patch need further live
testing. Texture work does not close those gaps.

The separate `PLAY_EDGE_TEST.bat` package uses its own graphics settings and
shader folder, the normal saves, and original textures. It permits comparison
with the existing PLAY.bat build while Windows has that executable open.
