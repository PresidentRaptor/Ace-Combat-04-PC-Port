#ifndef PS2_VK_H
#define PS2_VK_H

#include "ps2_runtime.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct ps2_vk_vertex {
    float x, y, z;
    float r, g, b, a;
    float s, t, q;
    float fog;
    u32 round_uv;
    /* With PS2_VK_RUV_CLAMP: the texel range a bilinear sprite samples at
       native resolution (first and last pixel centre), as signed 12.4 lo|hi<<16
       per axis.  Upscaled sub-pixels are kept inside it, so a sprite never
       picks up the texels beyond its edge that native rendering never reads. */
    u32 clamp_u, clamp_v;
} ps2_vk_vertex;

#define PS2_VK_RUV_SPRITE (1u << 29)
#define PS2_VK_RUV_CLAMP  (1u << 30)

typedef struct ps2_vk_state {
    u32 fb_w, fb_h;
    u32 fb_psm;
    u32 fb_mask;
    int shuffle_rg;
    u32 shuffle_alpha;
    s32 scissor[4];

    u32 ztst;
    int zwrite;

    int abe;
    u32 alpha_a, alpha_b, alpha_c, alpha_d, alpha_fix;

    int tme;
    u32 tex_index;
    float tex_w, tex_h;
    u32 tfx;
    int tcc;

    u32 rt;
    u32 tex_rt;
    int tex_depth;
    int tex_self;
    int fst;
    u32 tex_lod;
    int tex_point;

    u32 wms, wmt;
    u32 minu, maxu, minv, maxv;

    int ate;
    u32 atst, aref;
    u32 afail;
    int zte;

    int fge;
    u32 fogcol;
    int fba;
    int date, datm;
    u32 zrt;
    int zcopy;
    int colclip;
    u32 emitter;
    int native_region;
    /* CLUT in a GPU-drawn render target: slot + 1, its pixel position
       (x | y << 16), and whether the texture is 4-bit */
    u32 clut_rt;
    u32 clut_xy;
    int clut_four;
    /* An untextured draw into the VRAM another target uses as its Z buffer
       (AC4 clears its depth that way): that target's slot + 1, and the Z
       width the colour bits stand for (24 or 32).  The renderer repeats the
       draw as a depth write there. */
    u32 zclear_rt;
    u32 zclear_bits;
    /* PSMT8H texture whose indices are a render target's alpha (tex_rt):
       gs.frag looks each alpha up in the palette texture clut_tex - 1 */
    int index_rt;
    u32 clut_tex;
    /* Mip level chosen per pixel (TEX1.LCM=0): K (12 bits), L << 12, this
       draw's level << 14, MXL << 17, on (bit 20), blend with the next level
       (bit 21, it is texture clut_tex - 1), nearest level (bit 22).  gs.frag
       discards the pixels whose LOD belongs to another level's draw. */
    u32 mip;
} ps2_vk_state;

enum { PS2_VK_POINTS = 0, PS2_VK_LINES = 1, PS2_VK_TRIANGLES = 2 };

int  ps2_vk_enabled(void);
int  ps2_vk_closed(void);

void ps2_vk_draw(int topology, const ps2_vk_state *st,
                 const ps2_vk_vertex *v, int n);

enum { PS2_VK_NATIVE_NONE = 0, PS2_VK_NATIVE_SUN_FLARE = 1,
       PS2_VK_NATIVE_SUN_GHOST = 2,
       PS2_VK_NATIVE_2D = 3 };

void ps2_vk_draw_2d(int topology, const ps2_vk_state *st,
                    const ps2_vk_vertex *v, int n);
typedef struct ps2_vk_native {
    u32 pass;
    u32 rt;
    u32 zrt;
    u32 tex;
    float tex_w, tex_h;
    int tex_point;
    u32 wrap;
    float box[4];
    float sun_z;
    s32 scissor[4];
} ps2_vk_native;

void ps2_vk_native_draw(const ps2_vk_native *nd, const ps2_vk_vertex *v, int n);

typedef struct ps2_vk_mesh_block {
    float m[16];
    float c[16];
    float l[12];
    float r[16];
    float e[12];
    float fog0, fog1;
    float zscale, zmax;
    float xoff, yoff;
    float spec_alpha;
    float pad0;
    u32 mode;
    u32 pass;
    u32 clip;
    u32 pad1;
    u32 prog;
    u32 pad2, pad3, pad4;
    float p[16];
} ps2_vk_mesh_block;

enum { PS2_VK_NATIVE_MESH = 4 };

int  ps2_vk_mesh_available(void);
int  ps2_vk_mesh_material_ok(const ps2_vk_state *st);
int  ps2_vk_mesh_store(const u8 *records, u32 n_verts, const u32 *indices,
                       u32 n_indices, u32 *vbase, u32 *ifirst);
int  ps2_vk_mesh_room(u32 n_verts, u32 n_indices, u32 n_draws);
enum { PS2_VK_MESH_CULL = 1, PS2_VK_MESH_GSFRAG = 4 };
void ps2_vk_draw_mesh(const ps2_vk_state *st, const ps2_vk_mesh_block *b,
                      u32 vbase, u32 ifirst, u32 n_indices, int cull);
void ps2_vk_draw_mesh_topo(const ps2_vk_state *st, const ps2_vk_mesh_block *b,
                           u32 vbase, u32 ifirst, u32 n_indices, int cull,
                           int topology);
extern void (*ps2_vk_before_record)(void);

u32  ps2_vk_texture(u64 key, u32 hash, const u8 *rgba, u32 w, u32 h);
int  ps2_vk_texture_is(u32 idx, u64 key, u32 hash);
/* texture whose pixels the caller keeps alive and unchanged (texture packs) */
u32  ps2_vk_texture_ext(u64 key, u32 hash, const u8 *rgba, u32 w, u32 h);

u32  ps2_vk_texture_native(u32 src, u32 x, u32 y, u32 w, u32 h);
u32  ps2_vk_texture_native_find(u64 key, u32 hash, u32 w, u32 h);
u32  ps2_vk_texture_native_rgba(u64 key, u32 hash, const u8 *rgba, u32 w, u32 h);
const u8 *ps2_vk_texture_pixels(u32 idx);
void ps2_vk_texture_size(u32 idx, u32 *w, u32 *h);

void ps2_vk_invalidate(u32 base, u32 size);

#define PS2_VK_PRESENT_BLANK 0xFFFFFFFFu
int  ps2_vk_present(u32 disp_x, u32 disp_y, u32 disp_w, u32 disp_h, u32 rt);

extern int ps2_vk_lockstep;

int  ps2_vk_screenshot(const char *path);

extern float ps2_vk_display_aspect;
/* The picture shape the game's camera and HUD are laid out for: 4/3 unless
   widescreen is on. */
float ps2_vk_game_aspect(void);

void ps2_vk_stats(u64 *frames, u64 *draws, u64 *verts, u64 *textures);

#ifdef __cplusplus
}
#endif

#endif
