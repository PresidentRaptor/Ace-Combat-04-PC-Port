"""Run the real AC4 streaming implementation against synthetic ADPCM blocks."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'runtime/src/ps2_hle_ac4.c').read_text()
start = source.index('#define VAG_CHANNELS')
end = source.index('static int vag_rpc(', start)
prelude = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <pthread.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;
typedef int16_t s16; typedef int64_t s64;
#define PS2_IOP_RAM_SIZE (2u << 20)
#define PS2_IOP_RAM_BASE 0x1c000000u
static u8 ram[PS2_IOP_RAM_SIZE];
static s16 gains[48][2];
static u64 field;
static void ps2_log(const char *fmt, ...) { (void)fmt; }
static u64 ps2_kernel_vblank_count(void) { return field; }
static void ps2_get_mem(void *out, u32 addr, u32 size) {
    memcpy(out, ram + (addr & (PS2_IOP_RAM_SIZE-1)), size);
}
static void ps2_spu2_decode_block(const u8 *blk, s16 *out, int *s1, int *s2, u32 *hdr) {
    /* Decoder is separately tested: give each ADPCM block an identifiable constant. */
    for (int i=0; i<28; i++) out[i] = blk[2] * 128;
}
static void ps2_spu2_voice_volume(u32 i, s16 *l, s16 *r) {
    *l=gains[i][0]; *r=gains[i][1];
}
'''
test = r'''
int main(void) {
    vag_base = 0x40000;
    vag_spu_voice[0] = 24;
    gains[24][0] = gains[24][1] = 16384; /* half-volume mono */
    u32 addr = vag_base + 0x180;
    ram[addr+2] = 64;
    ps2_ac4_iop_fill(addr,16);
    vag_begin(0,16,1,4096);
    s16 out[60] = {0};
    vag_run(out,28);
    assert(vag[0].status == VAG_ST_PLAY);
    for (int i=1; i<28; i++) assert(out[2*i] == 4096 && out[2*i+1] == 4096);
    vag_run(out+56,1);
    assert(vag[0].status == VAG_ST_IDLE);
    /* A refill in a recycled low slot must follow an older same-field refill. */
    memset(vag_fills,0,sizeof vag_fills);
    ps2_ac4_iop_fill(addr,16);
    ps2_ac4_iop_fill(addr+16,16);
    vag_fills[0].used=1;
    ps2_ac4_iop_fill(addr+32,16);
    assert(vag_next_fill(&vag[0]) == 1);
    /* Stereo voices have independent pan/volume, including complete mute. */
    memset(vag_fills,0,sizeof vag_fills);
    ram[addr+2]=32; ram[addr+2048+2]=64;
    gains[24][0]=16384; gains[24][1]=0;
    gains[25][0]=0; gains[25][1]=8192;
    ps2_ac4_iop_fill(addr,4096);
    vag_begin(0,2048,2,4096);
    memset(out,0,sizeof out);
    vag_run(out,3);
    assert(out[2]==2048 && out[3]==2048);
    memset(gains,0,sizeof gains);
    memset(out,0,sizeof out);
    vag_run(out,3);
    for (int i=0;i<6;i++) assert(out[i]==0);
    puts("PASS: final 28-sample block, same-field refill ordering, stereo routing, volume, mute");
}
'''
env = os.environ.copy()
env['PATH'] = 'C:/msys64/ucrt64/bin;' + env['PATH']
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    (tmp/'test.c').write_text(prelude + source[start:end] + test)
    subprocess.run(['C:/msys64/ucrt64/bin/gcc.exe','-std=c23','-O2',str(tmp/'test.c'),
                    '-o',str(tmp/'test.exe'),'-lpthread'], check=True, env=env)
    subprocess.run([str(tmp/'test.exe')], check=True, env=env)
