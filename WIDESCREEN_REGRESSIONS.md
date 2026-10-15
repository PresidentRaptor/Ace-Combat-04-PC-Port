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

## Target diamond: further evidence required

The existing code assumes small red flight cues already use the widened
projection. The user's screenshot shows that the seeker diamond can disagree
with its target box. The automated flight recorded friendly boxes and a pause
menu but did not reproduce a selected enemy's diamond. No speculative marker
projection correction has been applied.

A diagnostic F6 capture taken while the offset is visible is requested. Replay
it with `gsreplay CAPTURE --widescreen --hidden --shot FILE.ppm`. The capture must
already contain a widened camera: the replay option applies HUD layout only.
`PS2_TRACE_WS_CUES=1` reports small marker/cue bounds, depth state and colors
every 30 fields, including draws exempted from HUD scaling. Compare the raw
diamond and target-box coordinates before choosing a projection correction.
