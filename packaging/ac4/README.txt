Ace Combat 04: Shattered Skies - recompiled for PC
==================================================

Windows 10/11, 64-bit. Needs a GPU/driver with Vulkan 1.3. Connect a
controller before starting.

The game's own code (SLUS_201.52 from the US disc, SLUS-20152) is
recompiled to native code; the disc data is read from your ISO while you
play. Game data is not included.

Playing
-------
Double-click "Ace Combat 04.exe" (or PLAY.bat). Either one uses the ISO in
this folder; you can also drag an ISO onto them. Saves go to the saves
folder - keep it when updating the build.

Keyboard: Enter = Start, arrows = D-pad, X = Cross, S = Circle,
Z = Square, A = Triangle, numpad 8/2/4/6 = left stick, Q/E = L1/R1,
1/3 = L2/R2, right Shift = Select. Everything can be rebound in the
settings menu (F4). F11 or Alt+Enter toggles fullscreen; Esc quits.

For a bug, send last-play.log (replaced on each launch) with the mission,
what happened and how to reproduce it. DIAGNOSTICS.bat writes a more
detailed diagnostics.log.

What works
----------
Boot, memory card detection, the opening FMV and title, menus, the story
movies with their soundtrack, mission briefings, and in-flight play of
Mission 01 with HUD, radio, music, voice and sound effects were all
checked from start to finish, at native resolution and at internal
resolution 6.

Fixed in this build
-------------------
- Aircraft were invisible or showed as black boxes/silhouettes. Models now
  draw textured and lit in the hangar, the cockpit view and the external
  (chase) view, including the game's own self-shadowing on the aircraft.
- Menus were too bright and their text looked smudged/outlined. The font
  colours were being lost on upload; text is now crisp and the menu
  brightness matches the PS2.
- At higher internal resolutions, thin lines appeared along the edges of
  menu text boxes, subtitles and HUD labels. 2D elements now sample only
  what the PS2 shows at its own resolution.
- The ground (and haze) flashed for single frames during missions. When
  the PC fell a frame behind, a frame's drawing was skipped and the next
  one was built on stale effect buffers; frames are no longer skipped.
- Single-frame flicker in flight, the hangar and the pause menu: for one
  refresh the screen showed an older picture (anywhere from a tenth of a
  second to about half a second old - HUD, ground and FPS counter all from
  that moment). A finished frame could reach the screen before its drawing
  had completed, so the window showed what that buffer held before. The
  hand-off to the window now waits for each frame properly, and each frame
  is shown with the display buffer the game chose for it (AC4 flips
  between two in menus and the hangar).
- The sun showed as a large square of rainbow rings. Its glow colours are
  drawn by the game on the graphics chip each frame and are now read from
  there; the sun is a soft round glow again.
- The F4 settings/mod menu now uses Ace Combat 04's blue colours.
- Hangar (aircraft select): black shapes cut into the aircraft and the
  floor, the canopy was a black blob and parts of the hangar were missing.
  The game clears its depth buffer by drawing into it like a picture; that
  clear never reached the depth used for the hangar, so each frame was
  depth-tested against earlier frames. It now does, and the aircraft,
  canopy frame, windows and floor reflection all draw.
- Islands in the distance were big squares of the wrong texture (building
  fronts, light spots) that only turned into proper land up close. The
  game keeps distant terrain in the small mipmap levels of its terrain
  texture cache and lets the graphics chip pick the level by distance;
  that choice was missing, so the full-size level was read. The level is
  now chosen for each triangle from its distance, and distant islands
  show their real coastline and terrain.
- Controller vibration now works: the game's rumble commands drive the
  controller's motors. It can be switched off under Input in the F4 menu
  ("Vibration").
- Saving and loading were checked: SAVE from the pre-mission menu writes
  the save file (MISSION 01 / SITTING DUCK), and LOAD from the title menu
  reads it back.
- Quitting no longer leaves a 25 MB ps2_frame.ppm screenshot in this
  folder (an older one can be deleted).

Known limits
------------
- Graphics run through the emulated GS. The native renderer the AC5 port
  uses was written for AC5's VU1 programs and is off. Higher internal
  resolutions (F4) work; resolution 6 was checked through Mission 01.
- The 16:9 widescreen option is ignored: the patch behind it is for AC5's
  executable and would corrupt AC4.
- The graphics machine runs on the game thread (an AC4-specific race shows
  up when it runs on its own thread); a modern CPU holds full speed.
- Only Mission 01 has been played through so far; later missions have not
  been checked yet.

Rebuilding
----------
The source is in src. src\README_AC4.md explains how the AC4 build is
made from the AC5 recompilation project.
