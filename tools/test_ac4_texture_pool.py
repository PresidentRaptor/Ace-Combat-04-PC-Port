"""Compile the actual pool functions in isolation (no Vulkan/window required)."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'runtime/src/ps2_video.c').read_text()
def between(start, end):
    return source[source.index(start):source.index(end, source.index(start))]

header = '''#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
typedef uint8_t u8; typedef uint32_t u32; typedef int32_t s32; typedef uint64_t u64;
typedef uintptr_t VkImage, VkDeviceMemory, VkImageView, VkDescriptorSet;
#define VK_MAX_TEXTURES 8192
#define VK_TEX_BYTES (512u << 20)
static int vk_ready;
static u32 tex_rec_seq = 2;
void ps2_log(const char *, ...);
'''
header += between('typedef struct {\n    u64 id, key;', 'static ps2_vk_vertex *rec_verts;')
header += between('static vk_texture textures[', 'static pthread_mutex_t list_lock')
header += between('int ps2_vk_texture_is(', 'void ps2_vk_invalidate(')
env = os.environ.copy()
env['PATH'] = 'C:/msys64/ucrt64/bin;' + env['PATH']
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    (tmp / 'texture_pool_under_test.h').write_text(header)
    subprocess.run(['C:/msys64/ucrt64/bin/gcc.exe', '-std=c23', '-O2', '-I'+str(tmp),
                    str(root/'tools/texture_pool_test.c'), '-o', str(tmp/'test.exe')], check=True, env=env)
    subprocess.run([str(tmp/'test.exe')], check=True, env=env)
