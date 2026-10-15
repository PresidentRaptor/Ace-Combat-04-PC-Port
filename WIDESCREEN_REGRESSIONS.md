# Widescreen regression follow-up

Reviewed the main branch through `0bb242f`, including the widescreen camera,
HUD layout, menu pillarboxing, and the removal of AC5-only runtime components.
The local checkout matched GitHub main before edits.

## Corrected and installed

- Red menu highlights no longer take the flight lock-cue exemption. Z-zero
  selection rectangles use the same centered transform as their menu cells.
  The proximity exemption also excludes Z-zero menu shapes, so a previous
  frame's target boxes cannot catch menu highlights.
- Far-plane flight HUD sprites suppress the menu pillarboxing heuristic in
  that field and the following one. A pause menu or overlapping Z-zero effects
  cannot crop the world and clip the HUD's outer blocks while those sprites
  remain visible. Menus without a flight HUD retain their black sides.

The HUD-based guard alone proved insufficient in live play. Pillarboxing now
also requires the **displayed viewport** to be at least 640 columns. AC4's flight
viewport is 512 columns, even when its backing render target is 640 wide. This
hard gate prevents menu bars independently of missing/stale HUD draws. Ext,
dive and fly8 replays all present the full viewport width. Regression tests
explicitly check 512-column flight with no recent HUD draw and active menu
coverage.

The hangar guides were separately caught by the full-screen fade/copy
exemptions. A capture confirms a vertical line at x185.5, y0.5..448.5 and a
horizontal line across x0.5..640.5. These Z-zero untextured line primitives now
transform with the menu. Full-height rectangular clear strips remain exempt.
The corrected hangar replay visually aligns the vertical guide with its cell.
The user's target-diamond replay remains pixel-identical after these changes.

`tools/test_ac4_widescreen.py` compiles the actual C layout function and checks
highlight/cell alignment, flight/pause priority, real-menu eligibility, fade
expiry and the disabled-widescreen path. Sampling and texture-pool checks pass.
Aircraft and flight replays with widescreen disabled are pixel-identical to
the existing `dev/out/d1_aircraft.png` and `d1_ext.png` baselines.

The main Windows executable was rebuilt and installed in `runtime/ac4.exe`.
Its 180-field startup smoke test exits with code 0. The previous executable
is retained locally in `review/widescreen-regressions/installed-backup`.
Scripted wide-camera flight and pause captures are local review artifacts;
they contain game data and are excluded from the repository.

## Target diamond: corrected from the user's capture

The supplied F6 recording contains 14 completed fields plus a final partial
draw batch. The seeker and selected target box have identical raw centers in
all 15 batches. The diamond is a red textured sprite from the 256x256 HUD
symbol page, with source V 176..192. The caption-row exclusion was treating it
as text and pulling it toward the center; the box retained its world projection.
The warning-row exclusion could do the same elsewhere on screen.

`ws_seeker_sprite` identifies that source cell and preserves its projected
position independently of caption/warning rows and corner blocks. Z-zero menu
highlights retain the centered menu transform. The synthetic regression tests
cover nine screen positions, Z-zero artwork, and a different caption page.
The full user recording replays successfully. Its final image changes only in
the diamond region (x340..406, y29..64 at 1024x896); the diamond now overlays
the selected target box. The correction is installed in the main executable.

Replay with `gsreplay CAPTURE --widescreen --hidden --shot FILE.ppm`. The capture
must already contain a widened camera: the option applies HUD layout only.
`PS2_TRACE_WS_CUES=1` reports small marker/cue bounds, depth, color and UV source
every 30 fields. Use `PS2_TRACE_WS_CUES=all` for every field of a short recording.
