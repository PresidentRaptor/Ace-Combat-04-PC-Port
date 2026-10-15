"""Exercise the actual widescreen HUD code with synthetic GS draws."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
src = (root/'runtime/src/ps2_gs.c').read_text()
start = src.index('static float ws_area;')
end = src.index('static void vk_triangle_draw(', start)
prelude = r'''
#include "ps2_vk.h"
#include "ps2_settings.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
ps2_settings ps2_cfg;
int ps2_gif_path = 2;
u32 ps2_gs_frame_count, gs_prim;
u64 gs_stat_ws_hud, gs_stat_ws_cue;
float ps2_vk_game_aspect(void) { return ps2_cfg.widescreen ? 16.0f/9.0f : 4.0f/3.0f; }
u64 ps2_kernel_vblank_count(void) { return ps2_gs_frame_count; }
void ps2_log(const char *fmt, ...) { (void)fmt; }
u64 tex0_reg(void) { return 0; }
static int sprite_clamp_axis(float a,float b,float c,float d,u32 *e) { return 0; }
'''
test = r'''
static void draw(float x, float y, float w, float h, float z, int red, int textured) {
    ps2_vk_state st = {0};
    st.fb_w=512; st.fb_h=448; st.tme=textured; st.fst=1;
    st.scissor[1]=511; st.scissor[3]=447;
    ps2_vk_vertex v[6] = {0};
    for(int k=0;k<6;k++) { v[k].x=x; v[k].y=y; v[k].z=z;
        v[k].r=255; v[k].g=red?0:255; }
    v[2].x=v[5].x=x+w; v[1].y=v[2].y=v[5].y=y+h;
    ws_hud(&st,v,6);
    if(z==0 && w<100) {
        float expected=256.5f+(x-256.5f)*0.75f;
        assert(fabsf(v[0].x-expected)<0.001f);
        assert(fabsf((v[2].x-v[0].x)-w*0.75f)<0.001f);
    }
}
int main(void) {
    ps2_cfg.widescreen=1; ps2_cfg.hud_layout=PS2_HUD_EDGES;
    ps2_gs_frame_count=100;
    /* Red selection rectangles and white cells must use the same transform. */
    for(int i=0;i<3;i++) { draw(120+i*100,170,16,16,0,1,0);
        draw(120+i*100,170,16,16,0,0,1); }
    draw(0,0,400,400,0,0,1); assert(ps2_gs_ws_pillar());
    /* A paused mission can draw enough Z-zero overlays to trigger the old
       menu heuristic, but its flight HUD keeps the world full width. */
    ps2_gs_frame_count=101; draw(20,20,40,12,1,0,1);
    draw(0,0,400,400,0,0,1); assert(!ps2_gs_ws_pillar());
    ps2_gs_frame_count=102; assert(!ps2_gs_ws_pillar());
    /* A real menu without flight glyphs can pillarbox again. */
    ps2_gs_frame_count=103; draw(0,0,400,400,0,0,1);
    assert(ps2_gs_ws_pillar());
    ps2_gs_frame_count=116; assert(!ps2_gs_ws_pillar());
    /* Recorded seeker cell from the user capture. The diamond must share
       the target box's projection even over captions, warnings and corners. */
    for(int row=0;row<3;row++) for(int side=0;side<3;side++) {
        ps2_vk_state cue={0}; cue.fb_w=512; cue.fb_h=448;
        cue.tme=cue.fst=1; cue.tex_w=cue.tex_h=256;
        cue.scissor[1]=511; cue.scissor[3]=447;
        ps2_vk_vertex diamond[6]={{0}};
        float x=20+side*200, y=32+row*160;
        for(int k=0;k<6;k++) {
            diamond[k].x=x; diamond[k].y=y; diamond[k].z=1;
            diamond[k].r=255; diamond[k].s=212; diamond[k].t=176;
        }
        diamond[2].x=x+16; diamond[2].s=228;
        diamond[2].y=y+18; diamond[2].t=192;
        assert(ws_seeker_sprite(&cue,diamond,6));
        ws_hud(&cue,diamond,6);
        assert(diamond[0].x==x && diamond[2].x==x+16);
        /* Same artwork in a Z-zero menu must still scale with that menu. */
        for(int k=0;k<6;k++) diamond[k].z=0;
        assert(!ws_seeker_sprite(&cue,diamond,6));
        ws_hud(&cue,diamond,6);
        assert(fabsf(diamond[0].x-(256.5f+(x-256.5f)*0.75f))<0.001f);
        /* A red caption from another page is not a seeker. */
        cue.tex_w=64; cue.tex_h=16;
        for(int k=0;k<6;k++) diamond[k].z=1;
        assert(!ws_seeker_sprite(&cue,diamond,6));
    }
    ps2_cfg.widescreen=0;
    ps2_vk_state st={0}; st.fb_w=512; st.fb_h=448;
    ps2_vk_vertex v[2]={{0}}; v[0].x=120; v[1].x=140;
    ws_hud(&st,v,2); assert(v[0].x==120 && v[1].x==140);
    puts("PASS: menu highlights and cells agree; flight/pause suppress menu crop; menu/fade expiry; seeker follows target across caption/warning/corner rows; captions stay distinct; widescreen-off unchanged");
}
'''
env=dict(os.environ, PATH='C:/msys64/ucrt64/bin;'+os.environ['PATH'])
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp); c=tmp/'test.c'; exe=tmp/'test.exe'
    c.write_text(prelude+src[start:end]+test)
    subprocess.run(['C:/msys64/ucrt64/bin/gcc.exe','-std=c23','-O2',
                    '-I'+str(root/'runtime/include'),str(c),'-lm','-o',str(exe)],check=True,env=env)
    subprocess.run([str(exe)],check=True,env=env)
