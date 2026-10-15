# Compatibility and test coverage

Updated 2026-10-15. Baseline: 2.2.0 Beta and current `main`, Windows x64,
USA SLUS-20152 executable. Only this executable hash is supported. A passing
unit test, replay or title-screen demo is not a full mission playthrough.

| Area | Evidence | Remaining coverage |
| --- | --- | --- |
| Boot, title, opening/story movies | Checked in development and live play | Extended playback and more hardware |
| Mission 01 | Completed in live play; native and 6x rendering exercised | More difficulty, aircraft and hardware combinations |
| Later campaign missions | Some title-screen demo scenes render correctly | Full mission playthroughs, progression and completion are unverified |
| Save/load | Pre-mission SAVE and title LOAD/CONTINUE verified | Cross-mission progression and long-term save compatibility |
| Music, speech and effects | Mission 01 checked; startup spike fix confirmed by user; synthetic stream tests | Long sessions, device changes and later-mission banks |
| Widescreen/HUD | Live play plus target, hangar and flight replay comparisons | Later menus/cameras and other display aspects |
| Objectives scan | Corrected in a recorded Mission 01 replay | Further live-play regression reports welcome |
| Keyboard/controller/rumble | Implemented, input checks and tested controller play | More devices, reconnects and custom layouts |
| Fullscreen/presentation | Implemented and exercised during development | Repeated mode changes, multi-monitor and diverse drivers |
| HD texture replacement | Loader/pool checks and local sample replays | Complete art coverage and terrain improvement are unverified |
| Installer | ISO/hash checks, exact copy/image comparison, cancellation, shortcut and installed startup tests | More PCs and installation paths |
| Source-only CI | Isolated runtime and Python checks without game files | Does not validate the complete Windows executable or campaign |

To improve this record, file a bug or support report with the version, mission,
difficulty, aircraft/camera, settings, GPU/driver and result. Record failed tests
as well as successful ones. Do not mark a mission verified from a demonstration
or brief startup. Maintainers can promote a row only when evidence supports it.

See [Windows validation](windows-validation.md), [widescreen evidence](widescreen.md)
and [audio/render follow-up](audio-and-rendering.md) for the existing test details.
