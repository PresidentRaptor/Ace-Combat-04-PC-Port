# Startup audio and downward-view follow-up

## Startup audio

A scripted 40-second startup (Start at fields 1500 and 1800) reproduced stale
VAG queue entries when menu music begins. These included nine sound-bank staging
transfers, 67584..196608 bytes, roughly 1500..1780 fields old. Their addresses
had subsequently been overwritten in IOP RAM. The records held addresses,
not owned copies, so playback could decode unrelated bank data or repeat newer
data.

Every new IOP read now invalidates queued descriptions whose byte ranges
overlap it, including active references. A stream ignores transfers larger
than one ring buffer. Disjoint refills keep their original order. The corrected
startup queues only the current 131072-byte music buffer, age one field, and
reports zero stream underruns. Tests cover this sequence, partial overlaps,
oversized transfers, active-reference invalidation, final-block draining,
stereo routing and volume.

Waveforms were captured through SDL's dummy audio driver, avoiding playback
through the speakers. On 2026-10-14 the user confirmed normal startup audio
through the normal playback device.

Normal shutdown stops the audio callback before video teardown and final
`_exit`, also finalizing diagnostic WAV headers. Optional `PS2_AUDIO_WAV=PATH`
plus `PS2_AUDIO_STEMS=1` writes cumulative stereo 48-kHz signed-16 raw taps:
`.spu2.s16` after SPU2, `.vag.s16` after adding VAG, `.adma.s16` after adding
AutoDMA. Local game audio is excluded from Git. `PS2_AC4_AUDIO_TRACE=1` reports
queued metadata at stream begin; `PS2_SPU2_TRACE=1` also reports keyed voices.

## Downward-view 4:3 remnants

The dive capture exposed a Z-zero PSMT8H haze/alpha-feedback sprite treated as
UI. Its first strip covers x0..44, y181.25..448.5 in a 512x448 framebuffer.
Its target lookup falls back to VRAM, so it lacks the direct render-target
binding that normally excludes feedback from layout changes. The widescreen
UI transform squeezed its coverage toward the center.

High-plane indexed framebuffer formats (PSMT8H, PSMT4HL and PSMT4HH), shuffle,
index-target and depth-copy passes now retain screen coverage. A test exercises
the recorded strip without a direct target binding. The corrected dive replay
changes the affected left-hand haze region and no longer transforms that pass
as UI. This is separate from the viewport black-bar guard and working seeker
diamond source-cell rule.

On 2026-10-14 the user also confirmed that looking down in chase view is
correct in normal play.
