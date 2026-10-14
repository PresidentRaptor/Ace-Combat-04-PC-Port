#ifndef PS2_TEXPACK_H
#define PS2_TEXPACK_H
#include <stdint.h>

/* Replacement ("HD") texture packs.  A texture is identified by its decoded
   RGBA pixels and size (never by VRAM address, which the game reuses), so a
   replacement follows the picture wherever it is uploaded.  Packs are
   directories of <id>_<w>x<h>.pam files (8-bit RGBA PAM) whose size is an
   integer multiple (1..8) of the original; tools/texture_pack.py makes them. */

#ifdef __cplusplus
extern "C" {
#endif

/* How the texture was sampled when it was seen, kept next to dumps so an
   upscaler can pad the borders the right way (GS CLAMP modes). */
typedef struct {
    unsigned wms, wmt;      /* 0 repeat, 1 clamp, 2 region clamp, 3 region repeat */
    unsigned region;        /* 1: a window of a larger texture (terrain atlas tile) */
    unsigned frame;         /* GS field counter, for the stable-texture dump rule */
} ps2_texpack_use;

uint64_t ps2_texpack_id(const unsigned char *rgba, unsigned w, unsigned h);

/* A pack is indexed (or dumping is on) and replacements are enabled. */
int ps2_texpack_active(void);
unsigned ps2_texpack_count(void);
const char *ps2_texpack_dir(void);
/* Bytes of replacement pixels resident, and the limit (PS2_TEXTURE_PACK_MB). */
void ps2_texpack_memory(uint64_t *used, uint64_t *limit);

/* Dumping: a picture is saved once, the first time it is drawn at least four
   fields after it first appeared, so movie frames and other pictures that
   keep changing are not.  want_dump is cheap (call it per draw while
   dumping); when it returns 1, pass the pixels to ps2_texpack_dump. */
int  ps2_texpack_want_dump(uint64_t id, unsigned frame);
void ps2_texpack_dump(const unsigned char *rgba, unsigned w, unsigned h, uint64_t id,
                      const ps2_texpack_use *use);

/* The replacement for an id, or NULL.  *pending is set while a replacement
   that exists is still being read from disk on the loader thread -- ask
   again on a later draw.  The pixels stay valid for the whole session. */
const unsigned char *ps2_texpack_get(uint64_t id, unsigned w, unsigned h,
                                     unsigned *rw, unsigned *rh, int *pending);

/* Synchronous convenience (tests): see + get, waiting for the load. */
const unsigned char *ps2_texpack_lookup(const unsigned char *rgba, unsigned w,
    unsigned h, unsigned *rw, unsigned *rh, uint64_t *id);

/* Menu switches: use replacements, and save textures for upscaling into
   textures/dump (or PS2_TEXTURE_DUMP). */
void ps2_texpack_set_enabled(int on);
int  ps2_texpack_enabled(void);
void ps2_texpack_set_dump(int on);
int  ps2_texpack_dumping(void);
unsigned ps2_texpack_dumped(void);

#ifdef __cplusplus
}
#endif
#endif
