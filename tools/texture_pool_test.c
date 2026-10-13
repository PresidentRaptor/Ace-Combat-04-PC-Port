/* Exercise the real CPU texture pool without opening a Vulkan device. */
#include "texture_pool_under_test.h"
#include <assert.h>
#include <stdarg.h>

void ps2_log(const char *fmt, ...) { (void)fmt; }

int main(void) {
    u8 rgba[64 * 64 * 4] = {0};
    u32 recent[3] = {~0u, ~0u, ~0u};
    vk_ready = 1;
    for (u32 field = 0; field < 20000; field++) {
        u64 key = (u64)field * 0x100000001ull;
        rgba[0] = (u8)field;
        u32 idx = ps2_vk_texture(key, field, rgba, 64, 64);
        assert(idx != ~0u);
        for (u32 j = 0; j < 2 && j < field; j++)
            assert(ps2_vk_texture_is(recent[(field - j - 1) % 3],
                (u64)(field - j - 1) * 0x100000001ull, field - j - 1));
        assert(ps2_vk_texture(key, field, rgba, 64, 64) == idx);
        assert(ps2_vk_texture_pixels(idx)[0] == (u8)field);
        recent[field % 3] = idx;
        tex_rec_seq++;
    }
    assert(ntextures <= 4);
    assert(tex_bytes <= 4 * sizeof(rgba) * 2);
    /* A re-key must remove the old hash-chain link (including collisions). */
    u32 entries = 0;
    for (u32 b = 0; b < TEX_HASH; b++) {
        u32 count = 0;
        for (s32 i = tex_head[b]; i >= 0; i = tex_next[i]) {
            assert(++count <= ntextures);
            assert(tex_bucket(textures[i].key) == b);
            entries++;
        }
    }
    assert(entries == ntextures);
    u32 native = ps2_vk_texture(1ull << 63, 42, rgba, 64, 64);
    textures[native].levels = 7;
    tex_rec_seq += 10;
    u32 plain = ps2_vk_texture(123, 43, rgba, 64, 64);
    assert(plain != native);
    assert(textures[plain].levels <= 1);
    puts("PASS: 20,000 scene keys, protected pending frames, bounded memory, hash-chain reuse, mip isolation");
    return 0;
}
