"""Test the real C texture pack loader using synthetic, redistributable pixels."""
from pathlib import Path
import os
import subprocess
import tempfile
from texture_pack import identity, write_pam, pad

root = Path(__file__).resolve().parents[1]
env = dict(os.environ, PATH='C:/msys64/ucrt64/bin;'+os.environ['PATH'])
harness = r'''
#include "ps2_texpack.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void ps2_log(const char *fmt, ...) { (void)fmt; }
int main(int argc, char **argv) {
    unsigned char pixels[8*8*4];
    const char *mode = argc > 1 ? argv[1] : "";
    for (unsigned i=0;i<sizeof pixels;i++) pixels[i]=(unsigned char)i;
    if (!strcmp(mode, "alpha")) pixels[3]^=1; /* same RGB, different material alpha */
    unsigned w=0,h=0; uint64_t id=0;
    if (!strcmp(mode, "async")) {
        /* the loader thread: pending first, then the replacement */
        int pending = 0, polls = 0;
        const unsigned char *p;
        id = ps2_texpack_id(pixels, 8, 8);
        while (!(p = ps2_texpack_get(id, 8, 8, &w, &h, &pending)) && pending && polls < 100000000)
            polls++;
        printf("%016llx %u %u %d\n", (unsigned long long)id, w, h, p ? p[0] : -1);
        return 0;
    }
    if (!strcmp(mode, "stable")) {
        /* saved once: not until 4 fields after it first appears, then never again */
        id = ps2_texpack_id(pixels, 8, 8);
        printf("%d", ps2_texpack_want_dump(id, 5));
        printf("%d", ps2_texpack_want_dump(id, 6));
        printf("%d", ps2_texpack_want_dump(id, 9));
        printf("%d\n", ps2_texpack_want_dump(id, 30));
        return 0;
    }
    printf("%016llx ",(unsigned long long)ps2_texpack_id(pixels,8,8));
    const unsigned char *p=ps2_texpack_lookup(pixels,8,8,&w,&h,&id);
    printf("%u %u %d\n",w,h,p?p[0]:-1);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp); (tmp/'test.c').write_text(harness)
    subprocess.run(['C:/msys64/ucrt64/bin/gcc.exe','-std=c23','-O2','-Wall','-Wextra','-I'+str(root/'runtime/include'),
        str(tmp/'test.c'),str(root/'runtime/src/ps2_texpack.c'),'-o',str(tmp/'test.exe'),'-lpthread'],env=env,check=True)
    rgba=bytes(range(256)); name=identity(rgba,8,8)
    pack=tmp/'pack'; pack.mkdir(); dump=tmp/'dump'; dump.mkdir()
    def run(mode='', off=False, dumping=True):
        e=dict(env,PS2_TEXTURE_PACK='off' if off else str(pack))
        if dumping: e['PS2_TEXTURE_DUMP']=str(dump)
        return subprocess.check_output([str(tmp/'test.exe')]+([mode] if mode else []),env=e,text=True).strip()
    assert run()==name.split('_')[0]+' 0 0 -1'
    assert (dump/(name+'.pam')).exists()
    assert run('stable') == '0010', run('stable')   # fields 5, 6, 9 (4 later), 30
    path=pack/(name+'.pam'); write_pam(path,bytes([77,99,123,231])*16*16,16,16)
    assert run()==name.split('_')[0]+' 16 16 77'
    assert run('async', dumping=False)==name.split('_')[0]+' 16 16 77'
    assert run(off=True).endswith('0 0 -1')
    assert run('alpha').endswith('0 0 -1')
    # a hand-made file directly in the pack folder wins over a generated one
    sub=pack/'upscaled'; sub.mkdir()
    write_pam(sub/(name+'.pam'),bytes([11,0,0,255])*32*32,32,32)
    assert run()==name.split('_')[0]+' 16 16 77'
    path.unlink()
    assert run()==name.split('_')[0]+' 32 32 11'
    (sub/(name+'.pam')).unlink()
    # Wrong dimensions, noninteger scales, oversized or truncated files fall back.
    for w,h in [(16,24),(9,9),(72,72),(4,4)]:
        write_pam(path,bytes(w*h*4),w,h)
        assert run().endswith('0 0 -1'),(w,h)
    path.write_bytes(b'P7\nWIDTH 999999\nHEIGHT 999999\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n')
    assert run().endswith('0 0 -1')
    write_pam(path,bytes(16*16*4),16,16); path.write_bytes(path.read_bytes()[:-1])
    assert run().endswith('0 0 -1')

# The upscaler's border padding follows the GS wrap modes.
from PIL import Image
im = Image.new('RGBA', (16, 16))
im.putpixel((0, 0), (255, 0, 0, 255)); im.putpixel((15, 0), (0, 0, 255, 255))
p = pad(im, 0, 1, 8)            # repeat across, clamp down
assert p.size == (32, 32)
assert p.getpixel((7, 8)) == (0, 0, 255, 255)    # left border wraps to the right edge
assert p.getpixel((24, 8)) == (255, 0, 0, 255)   # right border wraps to the left edge
assert p.getpixel((8, 0)) == (255, 0, 0, 255)    # top border repeats the top row
p = pad(im, 1, 1, 8)
assert p.getpixel((7, 8)) == (255, 0, 0, 255)    # clamped: the edge itself
print('PASS: C/Python identity agreement, RGBA identity, 2x load, loader thread, '
      'stable-texture dumps, pack priority, disabled/missing packs, malformed '
      'replacements, upscaler border padding')
