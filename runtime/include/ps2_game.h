#ifndef PS2_GAME_H
#define PS2_GAME_H

/* Which game this runtime is built for.  CMake's PS2_GAME option defines
   PS2_GAME_AC4; without it the build is the original AC5 one. */
#ifdef PS2_GAME_AC4
#define PS2_GAME_TITLE   "Ace Combat 04 - Shattered Skies"
#define PS2_GAME_SHORT   "Ace Combat 04"
#define PS2_GAME_SERIAL  "SLUS-20152"
#define PS2_GAME_PREFIX  "ac4_"
#else
#define PS2_GAME_TITLE   "Ace Combat 5 - The Unsung War"
#define PS2_GAME_SHORT   "Ace Combat 5"
#define PS2_GAME_SERIAL  "SLUS-20851"
#define PS2_GAME_PREFIX  "ac5_"
#endif

#endif
