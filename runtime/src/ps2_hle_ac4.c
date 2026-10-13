/* Ace Combat 04 IOP services: the game's own sound modules, SOUND.IRX and
   VAG.IRX, replaced by native code.  Both modules ship with their symbol
   tables, which is what these follow.

   SOUND.IRX (RPC 81000101, sifrpc_server) gets one batch a field: the EE
   queues commands into one of two 9216-byte send buffers and ships the full
   one with sceSifCallRpc(fno 1, NOWAIT).  A batch is {count, commands...};
   each command starts with its type, and the sizes are fixed by type:
      1-4  72 bytes  tone key on / set tone attribute / key off
        5  12        key off by bit mask
      6-9  16        reverb mode / depth / on / off
       10  20        {10, IOP src, SPU dst, size, seq} -- see below
    11-13  12        master / core input / data input volume
       14   8        a word echoed back in the voice status
   Command 10 hands a transfer to the module's TransBd thread:
     dst != 0   sceSdVoiceTrans: copy a bank from IOP RAM into SPU RAM
     src != 0   sceSdBlockTrans, looping: play 16-bit PCM from an IOP ring
                buffer through the core 0 data input (AutoDMA); movies do this
     neither    stop the AutoDMA stream
   The reply ends with {10, last finished seq, result} -- result is
   sceSdBlockTransStatus() >> 24, the half of the AutoDMA ring now playing,
   which movies use to refill the other half -- then {15, word, 48 voice
   state bytes}.  The EE keeps seq/result at +44/+48 of its sound state. */

#include "ps2_runtime.h"
#include "ps2_hle.h"
#include <math.h>
#include <pthread.h>

u64  ps2_kernel_vblank_count(void);
int  ps2_audio_running(void);
void ps2_spu2_write(u32 dst, u32 iop_src, u32 size);
void ps2_spu2_key_on(u32 i, u32 ssa, u32 lsax, u32 pitch,
                     u32 adsr1, u32 adsr2, s16 voll, s16 volr);
void ps2_spu2_key_off(u32 i);
void ps2_spu2_set_voice(u32 i, u32 ssa, u32 pitch, u32 adsr1, u32 adsr2,
                        u32 voll_reg, u32 volr_reg, int loop);
void ps2_spu2_stream_volume(u32 i, u32 l, u32 r);
void ps2_spu2_voice_pitch(u32 i, u32 p);
void ps2_spu2_voice_volume(u32 i, s16 *l, s16 *r);
u8   ps2_spu2_voice_status(u32 i);
void ps2_spu2_command_lock(void);
void ps2_spu2_command_unlock(void);
void ps2_spu2_decode_block(const u8 *blk, s16 *out, int *s1, int *s2,
                           u32 *hdr);

#define AC4_SOUND_SID   0x81000101u
#define AC4_VAG_SID     0x81000102u

#define SND_REPLY_TRANS   10u
#define SND_REPLY_VOICES  15u
#define SND_ADMA_BLOCK    512u      /* bytes of one channel in AutoDMA data */

static pthread_mutex_t snd_lock = PTHREAD_MUTEX_INITIALIZER;
static struct {
    u32 seq_req, seq_done, result;
    int streaming, first_half_done;
    u32 src, size;          /* AutoDMA ring: IOP physical, bytes */
    u32 sample, samples;    /* position and length in stereo samples */
    int vol_l, vol_r;       /* signed 16-bit data input gain (Q15) */
} snd;
static u32 snd_status_word;
static u8 snd_voice[48];        /* iop_ch_state: 1 keyed on, 4 keyed off */
static u64 snd_keyons;
static u64 snd_calls, snd_uploads, snd_upload_bytes, snd_streams, snd_stream_samples;

static void zero(u32 recv, int rsize) {
    if (recv && rsize > 0)
        for (int i = 0; i < rsize; i++) ps2_w8(recv + (u32)i, 0);
}

static int snd_cmd_size(u32 type) {
    if (type >= 1 && type <= 4) return 72;
    if (type == 5) return 12;
    if (type >= 6 && type <= 9) return 16;
    if (type == 10) return 20;
    if (type >= 11 && type <= 13) return 12;
    if (type == 14) return 8;
    return 0;
}

static s16 snd_clamp(int v) {
    return (s16)(v > 32767 ? 32767 : v < -32768 ? -32768 : v);
}

/* advance the AutoDMA stream by n samples, mixing into out if given */
static void snd_run(s16 *out, u32 n) {
    u32 half;
    if (!snd.streaming || !snd.samples) return;
    half = snd.samples / 2u;
    for (u32 k = 0; k < n; k++) {
        u32 s = snd.sample, pair = s / 256u, i = s % 256u;
        u32 a = snd.src + pair * (2u * SND_ADMA_BLOCK) + i * 2u;
        if (out) {
            s16 l = (s16)ps2_r16(PS2_IOP_RAM_BASE + (a & (PS2_IOP_RAM_SIZE - 1u)));
            s16 r = (s16)ps2_r16(PS2_IOP_RAM_BASE
                                 + ((a + SND_ADMA_BLOCK) & (PS2_IOP_RAM_SIZE - 1u)));
            out[2 * k]     = snd_clamp(out[2 * k] + l * snd.vol_l / 0x8000);
            out[2 * k + 1] = snd_clamp(out[2 * k + 1] + r * snd.vol_r / 0x8000);
        }
        if (++snd.sample >= snd.samples) snd.sample = 0;
        if (snd.sample == half || snd.sample == 0) {
            /* the DMA interrupt: report the half now playing */
            snd.result = snd.sample == half ? 1u : 0u;
            snd.seq_done = snd.seq_req;
            snd.first_half_done = 1;
        }
        snd_stream_samples++;
    }
}

void ps2_ac4_snd_mix(s16 *out, u32 n) {
    pthread_mutex_lock(&snd_lock);
    snd_run(out, n);
    pthread_mutex_unlock(&snd_lock);
}

static void snd_transfer(u32 src, u32 dst, u32 size, u32 seq) {
    src &= PS2_IOP_RAM_SIZE - 1u;
    snd.seq_req = seq;
    if (dst) {
        ps2_spu2_write(dst, PS2_IOP_RAM_BASE + src, size);
        snd.result = 0;
        snd.seq_done = seq;
        snd_uploads++;
        snd_upload_bytes += size;
    } else if (src) {
        snd.streaming = 1;
        snd.first_half_done = 0;
        snd.src = src;
        snd.size = size;
        snd.samples = size / (2u * SND_ADMA_BLOCK) * 256u;
        snd.sample = 0;
        snd.result = 0;
        snd_streams++;
        ps2_log("ac4-sound: AutoDMA stream from IOP %06X, %u-byte ring", src, size);
    } else {
        snd.streaming = 0;
        snd.seq_done = seq;
    }
}

/* The tone attributes a key-on (72 bytes) carries, as set_tone_attr_all
   reads them: ADSR at +36/+38, volume at +44/+46 (15-bit, clamped), the
   center note/fine and note/fine bytes at +48..+51, the sample's own rate
   at +58 and its SPU address at +64.  The voice (0..47) is the byte at +14.
   set_tone_attr (command 2) reuses the layout and picks what to change by
   the flags word at +16: 1 volume, 2 the raw pitch at +56, 4 note pitch. */
static u32 snd_note_pitch(u32 c) {
    u32 center = ps2_r8(c + 48), cfine = ps2_r8(c + 49);
    u32 note = ps2_r8(c + 50);
    s32 fine = (s8)ps2_r8(c + 51);
    u32 rate = ps2_r16(c + 58);
    double semis = ((double)note - center) + ((double)fine - cfine) / 128.0;
    double pitch = 4096.0 * pow(2.0, semis / 12.0);
    pitch = pitch * (rate ? rate : 48000u) / 48000.0;
    return pitch > 0x3FFF ? 0x3FFFu : (u32)pitch;
}

static u32 snd_vol(u32 c, u32 off) {
    s32 v = (s16)ps2_r16(c + off);
    if (v > 0x3FFF) v = 0x3FFF;
    if (v < -0x4000) v = -0x4000;
    return (u32)v & 0x7FFFu;
}

static void snd_key_on(u32 c) {
    u32 v = ps2_r8(c + 14);
    if (v >= 48) return;
    ps2_spu2_command_lock();
    ps2_spu2_key_on(v, ps2_r32(c + 64), ps2_r32(c + 64), snd_note_pitch(c),
                    ps2_r16(c + 36), ps2_r16(c + 38),
                    (s16)(u16)(snd_vol(c, 44) << 1), (s16)(u16)(snd_vol(c, 46) << 1));
    ps2_spu2_command_unlock();
    snd_voice[v] = 1;
    snd_keyons++;
}

static void snd_set_attr(u32 c) {
    u32 v = ps2_r8(c + 14), flags = ps2_r32(c + 16);
    if (v >= 48) return;
    ps2_spu2_command_lock();
    if (flags & 1u) ps2_spu2_stream_volume(v, snd_vol(c, 44), snd_vol(c, 46));
    if (flags & 2u) ps2_spu2_voice_pitch(v, ps2_r16(c + 56));
    if (flags & 4u) ps2_spu2_voice_pitch(v, snd_note_pitch(c));
    ps2_spu2_command_unlock();
}

static void snd_key_off(u32 v) {
    if (v >= 48) return;
    ps2_spu2_command_lock();
    ps2_spu2_key_off(v);
    ps2_spu2_command_unlock();
    if (snd_voice[v]) snd_voice[v] = 4;
}

/* get_ch_stat: 1 still keyed and sounding, 4 released but audible, 0 done */
static u8 snd_voice_state(u32 v) {
    u8 hw = ps2_spu2_voice_status(v);
    if (snd_voice[v] == 1 && (hw == 1 || hw == 3)) return 1;
    snd_voice[v] = hw ? 4 : 0;
    return snd_voice[v];
}

static int sound_rpc(ps2_ctx *ctx, u32 fno, u32 send, int ssize,
                     u32 recv, int rsize) {
    (void)ctx;
    snd_calls++;
    zero(recv, rsize);
    pthread_mutex_lock(&snd_lock);
    if (fno == 0) {
        memset(&snd, 0, sizeof snd);
        memset(snd_voice, 0, sizeof snd_voice);
        snd.seq_req = snd.seq_done = 1;     /* the EE starts its state at 1 */
        snd.vol_l = snd.vol_r = 0x7FFF;
    } else if (fno == 1 && send && ssize >= 4) {
        u32 n = ps2_r32(send), off = 4;
        for (u32 k = 0; k < n; k++) {
            u32 type = ps2_r32(send + off);
            int size = snd_cmd_size(type);
            if (!size || off + (u32)size > (u32)ssize) break;
            switch (type) {
            case 1: case 3:
                snd_key_on(send + off);
                break;
            case 2:
                snd_set_attr(send + off);
                break;
            case 4:
                snd_key_off(ps2_r8(send + off + 14));
                break;
            case 5: {
                u32 m0 = ps2_r32(send + off + 4), m1 = ps2_r32(send + off + 8);
                for (u32 b = 0; b < 24; b++) {
                    if (m0 & (1u << b)) snd_key_off(b);
                    if (m1 & (1u << b)) snd_key_off(24 + b);
                }
                break;
            }
            case 10:
                snd_transfer(ps2_r32(send + off + 4), ps2_r32(send + off + 8),
                             ps2_r32(send + off + 12), ps2_r32(send + off + 16));
                break;
            case 13:
                snd.vol_l = (s16)ps2_r16(send + off + 6);
                snd.vol_r = (s16)ps2_r16(send + off + 8);
                break;
            case 14:
                snd_status_word = ps2_r32(send + off + 4);
                break;
            }
            off += (u32)size;
        }
    }
    if (!ps2_audio_running()) snd_run(NULL, 48000u / 60u);
    if (recv && rsize >= 16 + 8 + 48) {
        ps2_w32(recv + 0, 2);
        ps2_w32(recv + 4, SND_REPLY_TRANS);
        ps2_w32(recv + 8, snd.seq_done);
        ps2_w32(recv + 12, snd.result);
        ps2_w32(recv + 16, SND_REPLY_VOICES);
        ps2_w32(recv + 20, snd_status_word);
        for (u32 v = 0; v < 48; v++) ps2_w8(recv + 24 + v, snd_voice_state(v));
    }
    pthread_mutex_unlock(&snd_lock);
    return 0;
}

/* VAG.IRX (RPC 81000102), "AC4 VAG module", streams music and voice.  The
   module ships with its symbols; this follows its vagctrl.c/vagstr.c.

   The EE drives the disc side: it reads each stream block straight into one
   of a channel's three IOP buffers (sceCdReadIOPm) and the module plays them
   through SPU2 voices, moving to the next buffer when one is used up.

   fno 0 (VagAllInit) replies R[0] = the module's buffer area (vag_buf); the
   EE carves the channel buffers out of it exactly as the module does:
     EE ch 0/1 (stereo): R[0] + 0x180 + ch*0x60000 + k*0x20000, k = 0..2
     EE ch 2..5 (mono):  R[0] + 0x180 + (ch-2)*0x30000 + k*0x10000
   Stereo data is interleaved in 2048-byte sectors, 64 KB per voice a buffer.

   fno 1 (VagCtrl) sends {count, play-enable mask, commands...}, five words a
   command {cmd, ee channel, length per voice, channels, pitch}:
     1 begin_PlayVag   2 begin_PlayVag1   3 end_PlayVag   4 complete_PlayVag
   and replies, per IOP channel i (EE channels 4/5 drive IOP channels 2/3):
     R[1+i] bytes played per voice   R[5+i] status (1 idle, 32/64 playing)
     R[9+i] next IOP buffer -- every change makes the EE read another block.

   Here the IOP side is native: reads into a channel's buffers are queued as
   they land, and the audio callback decodes the ADPCM from IOP RAM, resampled
   by the pitch, mixing it over the SPU2 output.  Using a buffer up advances
   R[9+i]; reaching the length makes the channel idle again. */

#define VAG_CHANNELS    6
#define VAG_IOP_CHANS   4
#define VAG_BUF_BYTES   0x000C01C0u
#define VAG_SECTOR      2048u
#define VAG_ST_IDLE     1u
#define VAG_ST_PLAY     32u
#define VAG_ST_DONE     64u     /* the EE has sent the last block */
#define VAG_FILLS       64
#define VAG_OUT_RATE    48000u

typedef struct {
    u32 addr, size;     /* IOP physical address, bytes */
    u64 field;
    u64 order;         /* refills in one field still have a strict order */
    int used;
} vag_fill;

typedef struct {
    s16 blk[28];
    int have, idx, s1, s2;
    s16 prev, cur;
} vag_voice;

typedef struct {
    u32 status;
    int finished;           /* the audio thread ended it; logged by the RPC */
    int ee_ch, nch;
    u32 region, region_size, buf_size;
    u32 length, played;     /* bytes per voice */
    u32 pitch, phase;       /* 4096 = 48 kHz; 16.16 phase */
    u32 next_buf;           /* R[9+i] */
    int fill;               /* index into vag_fills, -1 for none */
    u32 pos;                /* bytes per voice into the current fill */
    vag_voice v[2];
} vag_chan;

static pthread_mutex_t vag_lock = PTHREAD_MUTEX_INITIALIZER;
static vag_chan vag[VAG_IOP_CHANS];
static vag_fill vag_fills[VAG_FILLS];
static u32 vag_base;            /* IOP physical */
static u32 vag_enable_mask = 0x3Fu;
static u64 vag_calls, vag_starts, vag_samples, vag_underruns;
static u64 vag_fill_order;
/* VagAllInit receives the four starting voice numbers, on SPU2 core 1.
   SOUND.IRX's attribute commands control these same voices (volume/fades). */
static u32 vag_spu_voice[VAG_IOP_CHANS];

static int vag_iop(u32 ee_ch) {
    return ee_ch == 4 ? 2 : ee_ch == 5 ? 3 : (int)ee_ch;
}

static void vag_region(u32 ee, u32 *base, u32 *size, u32 *buf) {
    if (ee < 2) {
        *buf = 0x20000u;
        *base = vag_base + 0x180u + ee * 0x60000u;
    } else {
        *buf = 0x10000u;
        *base = vag_base + 0x180u + (ee - 2u) * 0x30000u;
    }
    *size = *buf * 3u;
}

static int vag_in(const vag_chan *c, u32 a) {
    return a >= c->region && a < c->region + c->region_size;
}

/* drop every queued block of this channel's buffers older than `before` */
static void vag_drop(vag_chan *c, u64 before) {
    for (int k = 0; k < VAG_FILLS; k++)
        if (!vag_fills[k].used && vag_fills[k].size && vag_in(c, vag_fills[k].addr)
            && vag_fills[k].field < before)
            vag_fills[k].used = 1;
    c->fill = -1;
    c->pos = 0;
}

static int vag_next_fill(const vag_chan *c) {
    int best = -1;
    for (int k = 0; k < VAG_FILLS; k++) {
        const vag_fill *f = &vag_fills[k];
        if (f->used || !f->size || !vag_in(c, f->addr)) continue;
        if (best < 0 || f->order < vag_fills[best].order)
            best = k;
    }
    return best;
}

/* sceCdReadIOPm landed `size` bytes at IOP address `addr` */
void ps2_ac4_iop_fill(u32 addr, u32 size) {
    int slot = -1;
    addr &= PS2_IOP_RAM_SIZE - 1u;
    if (!vag_base) return;
    pthread_mutex_lock(&vag_lock);
    for (int k = 0; k < VAG_FILLS; k++)
        if (vag_fills[k].used || !vag_fills[k].size) { slot = k; break; }
    if (slot < 0) slot = 0;
    vag_fills[slot].addr = addr;
    vag_fills[slot].size = size;
    vag_fills[slot].field = ps2_kernel_vblank_count();
    vag_fills[slot].order = ++vag_fill_order;
    vag_fills[slot].used = 0;
    pthread_mutex_unlock(&vag_lock);
}

static void vag_finish(vag_chan *c) {
    /* runs on the audio thread: no logging here, vag_rpc reports it */
    c->finished = 1;
    c->status = VAG_ST_IDLE;
    vag_drop(c, ~0ull);
}

static int vag_sample(vag_chan *c, int voice, s16 *out) {
    vag_voice *v = &c->v[voice];
    if (v->idx >= v->have) {
        const vag_fill *f;
        u32 sector, off, a;
        u8 blk[16];
        if (c->fill >= 0 && c->pos >= vag_fills[c->fill].size / (u32)c->nch) {
            vag_fills[c->fill].used = 1;
            c->fill = -1;
            c->pos = 0;
            c->next_buf = (c->next_buf + 1u) % 3u;
        }
        if (c->fill < 0) {
            c->fill = vag_next_fill(c);
            if (c->fill < 0) return 0;
        }
        f = &vag_fills[c->fill];
        sector = c->pos / VAG_SECTOR;
        off = c->pos % VAG_SECTOR;
        a = f->addr + sector * VAG_SECTOR * (u32)c->nch
            + (u32)voice * VAG_SECTOR + off;
        ps2_get_mem(blk, PS2_IOP_RAM_BASE + (a & (PS2_IOP_RAM_SIZE - 1u)), 16);
        ps2_spu2_decode_block(blk, v->blk, &v->s1, &v->s2, NULL);
        v->have = 28;
        v->idx = 0;
        if (voice == c->nch - 1) {
            c->pos += 16;
            c->played += 16;
        }
    }
    *out = v->blk[v->idx++];
    return 1;
}

static s16 vag_clamp(int v) {
    return (s16)(v > 32767 ? 32767 : v < -32768 ? -32768 : v);
}

/* advance every playing channel by n output frames, mixing into out if given */
static void vag_run(s16 *out, u32 n) {
    for (int i = 0; i < VAG_IOP_CHANS; i++) {
        vag_chan *c = &vag[i];
        if (c->status != VAG_ST_PLAY && c->status != VAG_ST_DONE) continue;
        if (!((vag_enable_mask >> c->ee_ch) & 1u)) continue;
        s16 vol[2][2] = {{0}};
        for (int vo = 0; vo < c->nch; vo++)
            ps2_spu2_voice_volume(vag_spu_voice[i] + (u32)vo, &vol[vo][0], &vol[vo][1]);
        for (u32 k = 0; k < n; k++) {
            c->phase += c->pitch << 4;          /* pitch/4096 in 16.16 */
            while (c->phase >= 0x10000u) {
                c->phase -= 0x10000u;
                /* played counts decoded ADPCM bytes, not consumed PCM. The
                   final block still contains up to 27 samples to drain. */
                if (c->played >= c->length && c->v[0].idx >= c->v[0].have) {
                    vag_finish(c);
                    goto next;
                }
                for (int vo = 0; vo < c->nch; vo++) {
                    s16 s;
                    if (!vag_sample(c, vo, &s)) { vag_underruns++; goto next; }
                    c->v[vo].prev = c->v[vo].cur;
                    c->v[vo].cur = s;
                }
            }
            if (out) {
                s64 f = c->phase;
                int l = c->v[0].prev + (int)(((c->v[0].cur - c->v[0].prev) * f) >> 16);
                int r = 0;
                if (c->nch > 1)
                    r = c->v[1].prev + (int)(((c->v[1].cur - c->v[1].prev) * f) >> 16);
                int ml = (int)(((s64)l * vol[0][0] + (s64)r * vol[1][0]) / 32768);
                int mr = (int)(((s64)l * vol[0][1] + (s64)r * vol[1][1]) / 32768);
                out[2 * k]     = vag_clamp(out[2 * k] + ml);
                out[2 * k + 1] = vag_clamp(out[2 * k + 1] + mr);
            }
            vag_samples++;
        }
next:   ;
    }
}

void ps2_ac4_vag_mix(s16 *out, u32 n) {
    pthread_mutex_lock(&vag_lock);
    vag_run(out, n);
    pthread_mutex_unlock(&vag_lock);
}

static void vag_begin(u32 ee, u32 length, u32 nch, u32 pitch) {
    vag_chan *c = &vag[vag_iop(ee)];
    u32 keep_next = c->next_buf;
    memset(c, 0, sizeof *c);
    c->ee_ch = (int)ee;
    c->nch = nch == 2 ? 2 : 1;
    vag_region(ee, &c->region, &c->region_size, &c->buf_size);
    c->length = length;
    c->pitch = pitch ? pitch : 4096u;
    c->fill = -1;
    /* the module moves to its next buffer when a stream begins */
    c->next_buf = (keep_next + 1u) % 3u;
    c->status = VAG_ST_PLAY;
    vag_starts++;
    ps2_log("ac4-vag: ch%u begin, %u bytes a voice, %d voice(s), pitch %u",
                ee, length, c->nch, c->pitch);
}

static int vag_rpc(ps2_ctx *ctx, u32 fno, u32 send, int ssize,
                   u32 recv, int rsize) {
    (void)ctx;
    vag_calls++;
    zero(recv, rsize);
    if (fno == 0) {
        if (!vag_base) {
            u32 a = ps2_iop_alloc(VAG_BUF_BYTES + 64u);
            vag_base = ((a & (PS2_IOP_RAM_SIZE - 1u)) + 63u) & ~63u;
            ps2_log("ac4-vag: stream buffers at IOP %06X", vag_base);
        }
        pthread_mutex_lock(&vag_lock);
        memset(vag, 0, sizeof vag);
        memset(vag_fills, 0, sizeof vag_fills);
        for (int i = 0; i < VAG_IOP_CHANS; i++) {
            vag[i].status = VAG_ST_IDLE;
            vag[i].next_buf = 1;
            vag_spu_voice[i] = send && ssize >= 16 ? 24u + ps2_r32(send + 4u * (u32)i) : 48u;
        }
        ps2_log("ac4-vag: SPU voices %u/%u, %u/%u, %u, %u",
                vag_spu_voice[0], vag_spu_voice[0] + 1, vag_spu_voice[1],
                vag_spu_voice[1] + 1, vag_spu_voice[2], vag_spu_voice[3]);
        pthread_mutex_unlock(&vag_lock);
        if (recv && rsize >= 52) {
            ps2_w32(recv, vag_base);
            for (int i = 0; i < VAG_IOP_CHANS; i++)
                ps2_w32(recv + 36 + 4u * (u32)i, 1);
        }
        return 0;
    }
    pthread_mutex_lock(&vag_lock);
    if (send && ssize >= 8) {
        u32 n = ps2_r32(send);
        vag_enable_mask = ps2_r32(send + 4);
        for (u32 k = 0; k < n && 8 + 20 * (k + 1) <= (u32)ssize; k++) {
            u32 c = send + 8 + 20 * k;
            u32 cmd = ps2_r32(c), ee = ps2_r32(c + 4);
            vag_chan *v;
            if (ee >= VAG_CHANNELS) continue;
            v = &vag[vag_iop(ee)];
            switch (cmd) {
            case 1: case 2:
                vag_begin(ee, ps2_r32(c + 8), ps2_r32(c + 12), ps2_r32(c + 16));
                break;
            case 3:
                ps2_log("ac4-vag: ch%u end (status %u, %u of %u bytes played)",
                        ee, v->status, v->played, v->length);
                if (v->status != VAG_ST_IDLE) {
                    v->status = VAG_ST_IDLE;
                    vag_drop(v, ps2_kernel_vblank_count());
                }
                break;
            case 4:
                ps2_log("ac4-vag: ch%u all data sent", ee);
                if (v->status == VAG_ST_PLAY) v->status = VAG_ST_DONE;
                break;
            }
        }
    }
    if (!ps2_audio_running())
        vag_run(NULL, VAG_OUT_RATE / 60u);
    for (int i = 0; i < VAG_IOP_CHANS; i++)
        if (vag[i].finished) {
            vag[i].finished = 0;
            ps2_log("ac4-vag: ch%d finished after %u bytes a voice",
                    vag[i].ee_ch, vag[i].played);
        }
    if (recv && rsize >= 52)
        for (int i = 0; i < VAG_IOP_CHANS; i++) {
            ps2_w32(recv + 4 + 4u * (u32)i, vag[i].played);
            ps2_w32(recv + 20 + 4u * (u32)i, vag[i].status);
            ps2_w32(recv + 36 + 4u * (u32)i, vag[i].next_buf);
        }
    pthread_mutex_unlock(&vag_lock);
    return 0;
}

void ps2_ac4_services_register(void) {
    ps2_rpc_register(AC4_SOUND_SID, sound_rpc, "ac4-sound");
    ps2_rpc_register(AC4_VAG_SID, vag_rpc, "ac4-vag");
}

void ps2_ac4_report(void) {
    if (snd_calls)
        ps2_log("ac4: sound driver %llu calls, %llu bank uploads (%llu KB), "
                "%llu AutoDMA streams (%.1f s), %llu sound effects",
                (unsigned long long)snd_calls,
                (unsigned long long)snd_uploads,
                (unsigned long long)(snd_upload_bytes >> 10),
                (unsigned long long)snd_streams, snd_stream_samples / 48000.0,
                (unsigned long long)snd_keyons);
    if (vag_calls)
        ps2_log("ac4: vag %llu calls (%llu streams, %.1f s streamed, %llu underruns)",
                (unsigned long long)vag_calls, (unsigned long long)vag_starts,
                (double)vag_samples / VAG_OUT_RATE,
                (unsigned long long)vag_underruns);
}
