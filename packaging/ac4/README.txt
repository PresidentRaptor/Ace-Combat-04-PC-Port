Ace Combat 04: Shattered Skies - PC Port
======================================

Windows 10/11, 64-bit. Needs a GPU/driver with Vulkan 1.3. Connect a
controller before starting.

The game's own code (SLUS_201.52 from the US disc, SLUS-20152) is
recompiled to native code; the disc data is read from your ISO while you
play. Game data is not included. This is a work-in-progress Windows port,
focused on faithful play with the original assets. It runs independently
of an Ace Combat 5 installation. HD textures are optional.

Playing
-------
Double-click "Ace Combat 04.exe" (or PLAY.bat). Either one uses the ISO in
this folder; you can also drag an ISO onto them. Saves go to the saves
folder - keep it when updating the build.

Keyboard: Enter = Start, arrows = D-pad, X = Cross, S = Circle,
Z = Square, A = Triangle, numpad 8/2/4/6 = left stick, Q/E = L1/R1,
1/3 = L2/R2, right Shift = Select. Everything can be rebound in the
settings menu (F4), which also has the master volume and vibration.
F11 or Alt+Enter toggles fullscreen; Esc asks before quitting.

For a bug, send last-play.log (replaced on each launch) with the mission,
what happened and how to reproduce it. DIAGNOSTICS.bat writes a more
detailed diagnostics.log.

HD textures
-----------
The game's textures can be replaced with sharper, upscaled versions (the
aircraft, the hangar, terrain, menus). Packs are made on your PC from your
own copy of the game; none are included.

1. In the game press F4, open Rendering and tick "Save textures for
   upscaling", then play the parts you want covered. Textures are saved
   once each into textures\dump.
2. Run MAKE_HD_TEXTURES.bat. It needs Python 3 with Pillow
   (py -m pip install Pillow) and Real-ESRGAN (the Windows
   realesrgan-ncnn-vulkan zip from
   https://github.com/xinntao/Real-ESRGAN/releases, unpacked into
   tools\realesrgan). The pack goes to textures\hd\upscaled; running it
   again only adds new textures.
3. Restart the game. F4 > Rendering > "HD texture pack" switches it on and
   off for comparison.

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
- The F4 settings/mod menu uses Ace Combat 04's blue colours.
- Startup audio no longer decodes stale staging buffers as music. The
  corrected audio and downward chase-view effects were confirmed in play.
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
  now chosen for every pixel from its distance and blended between levels
  the way the game asks, so distant islands show their real coastline and
  terrain without seams between neighbouring patches of ground.
- Haze in flight: the game turns each pixel's alpha into a haze strength
  through a lookup table before drawing its haze and sea-detail layer. That
  step read stale data, so the haze was the same everywhere and the sea
  looked almost black from above. It now reads the real frame: haze grows
  with distance and the sea shows its wave texture.
- Controller vibration now works: the game's rumble commands drive the
  controller's motors. It can be switched off under Input in the F4 menu
  ("Vibration"), and "Vibration strength" there sets how hard it shakes
  (65% by default; full strength felt too strong).
- Saving and loading were checked: SAVE from the pre-mission menu writes
  the save file (MISSION 01 / SITTING DUCK), and LOAD from the title menu
  reads it back.
- Quitting no longer leaves a 25 MB ps2_frame.ppm screenshot in this
  folder (an older one can be deleted).
- Esc no longer ends the game on the spot: it asks first, with just a
  small "Quit?" box (the settings menu no longer opens behind it). The settings
  menu (F4) gained a master volume, "mute in the background" and a Quit
  button. The F6-F10 debugging keys only work in DIAGNOSTICS.bat now, so a stray key
  press can't fill the folder with capture files.
- 16:9 widescreen: F4 > Display > "Widescreen (16:9)" (off by default).
  The game's own camera is widened, so flight, the carrier deck, the
  hangar and the opening show more at the sides instead of being
  stretched. The HUD keeps its 4:3 shapes: by default its corner blocks
  (score, radar, time, weapons) sit at the screen's edges while the tapes,
  pitch ladder and captions stay in the middle ("HUD layout" in F4 also
  offers everything 4:3 in the centre). Menus, briefings and story movies
  stay 4:3 in the middle; target boxes, FRND/TGT labels and the lock-on
  arrow and diamond stay on their aircraft. Keep "Aspect ratio" on Auto
  (or 16:9).

- The enlarged radar map (Square) showed a dotted pattern instead of the
  map: a leftover value from the 3D drawing made the map picture repeat
  thousands of times across the panel. It now shows the islands.

Presentation and remaining coverage
-----------------------------------
- Graphics use the Vulkan GS renderer. Higher internal resolutions (F4)
  work; resolution 6 was checked through Mission 01.
- Widescreen widens the 3D camera while keeping menus and movies in a
  centered 4:3 layout. The HUD has configurable placement. Target diamonds,
  hangar selection guides and the mission-objectives scan have layout fixes;
  the scan stays inside the menu rather than crossing the black side bars.
- Higher internal resolution, UI smoothing and FXAA reduce jagged edges.
  They do not recreate detail absent from the original textures.
- The graphics machine runs on the game thread by default; a modern CPU
  holds full speed. On a slower CPU, PS2_ASYNC_GFX=1 runs it on its own
  thread (re-tested in Mission 01 without the stray triangles it used to
  show).
- Only Mission 01 has been played through so far. The demonstration
  flights the title screen plays (recorded in later missions: snowy
  mountains, a bridge, a city) all look right, but the later missions
  themselves have not been played yet.

Rebuilding
----------
The local source checkout is in src. Start with src\README.md for build
and setup instructions; src\docs\technical-notes.md contains technical notes.

Source: https://github.com/PresidentRaptor/Ace-Combat-04-PC-Port
The shared recompiler/runtime originated in sal063's Ace Combat 5 project.
Original attribution and licenses are retained in the source repository.
