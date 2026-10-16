/* New bounded SIF byte transport from PS2tek DMAC/SIF register descriptions.
 * Include after generated CPU and ee_devices.h. No IOP code/boot/RPC emulation.
 * FIFO capacity and polling quantum are host policies, not hardware timings.
 * Unsupported DMA features and interrupt delivery stop explicitly.
 */
#ifndef AC4_SIF_TRANSPORT_H
#define AC4_SIF_TRANSPORT_H

enum { AC4_SIF_WORDS=64 };
typedef struct { uint32_t words[AC4_SIF_WORDS]; unsigned head,count; } Ac4SifFifo;
typedef struct {
    Ac4SifFifo to_ee,to_iop;
    uint64_t generation[2],tags[2],quadwords[2],completions[2];
    unsigned loaded[2],end[2],extra;
    uint64_t extra_data;
} Ac4SifTransport;

/* A full queue applies backpressure; failed pushes/pops do not change it. */
static inline int ac4_sif_push(Ac4SifFifo *f,const uint32_t *words,unsigned count) {
    if (count>AC4_SIF_WORDS-f->count) return 0;
    for (unsigned i=0;i<count;i++) f->words[(f->head+f->count+i)%AC4_SIF_WORDS]=words[i];
    f->count+=count; return 1;
}
static inline uint32_t ac4_sif_peek(const Ac4SifFifo *f,unsigned index) {
    return f->words[(f->head+index)%AC4_SIF_WORDS];
}
static inline int ac4_sif_pop(Ac4SifFifo *f,uint32_t *words,unsigned count) {
    if (count>f->count) return 0;
    for (unsigned i=0;i<count;i++) words[i]=ac4_sif_peek(f,i);
    f->head=(f->head+count)%AC4_SIF_WORDS; f->count-=count; return 1;
}
static inline void ac4_sif_drop(Ac4SifFifo *f,unsigned count) {
    f->head=(f->head+count)%AC4_SIF_WORDS; f->count-=count;
}

/* IOP-side mailbox ownership is the reverse of the EE-side register API.
 * Nothing calls these to manufacture readiness: a future live peer must do so.
 */
static inline int ac4_sif_iop_read(Ac4Devices *d,uint32_t address,uint32_t *value) {
    switch (address) {
    case 0x1d000000: *value=d->sif_mscom; return 0;
    case 0x1d000010: *value=d->sif_smcom; return 0;
    case 0x1d000020: *value=d->sif_msflag; return 0;
    case 0x1d000030: *value=d->sif_smflag; return 0;
    default: return AC4_DEVICE;
    }
}
static inline int ac4_sif_iop_write(Ac4Devices *d,uint32_t address,uint32_t value) {
    switch (address) {
    case 0x1d000010: d->sif_smcom=value; return 0;
    case 0x1d000020: d->sif_msflag&=~value; return 0;
    case 0x1d000030: d->sif_smflag|=value; return 0;
    default: return AC4_DEVICE;
    }
}
static inline int ac4_sif_irq_pending(const Ac4Devices *d) {
    return (d->d_stat&0x8000) || ((d->d_stat>>16)&d->d_stat&0x63ff);
}

/* DMA accesses physical main RAM only in this subset. Never alias an invalid
 * physical DMA address into RAM or redirect it to a memory-mapped device.
 */
static inline int ac4_sif_ram(Ac4Cpu *c,uint32_t address,unsigned char **storage) {
    c->fault_address=address;
    if (address&15) return AC4_ALIGNMENT;
    if (address>=UINT32_C(0x02000000) || c->memory_base || !c->memory ||
        c->memory_size<16 || address>c->memory_size-16) return AC4_BOUNDS;
    *storage=c->memory+address; return 0;
}
static inline uint32_t ac4_sif_u32(const unsigned char *p) {
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static inline void ac4_sif_put32(unsigned char *p,uint32_t word) {
    for (unsigned i=0;i<4;i++) p[i]=(unsigned char)(word>>(8*i));
}
static inline int ac4_sif_finish(Ac4SifTransport *s,Ac4Devices *d,unsigned index) {
    d->dma[5+index].chcr&=~UINT32_C(0x100);
    d->d_stat|=UINT32_C(1)<<(5+index);
    s->loaded[index]=0; s->completions[index]++;
    if (!index) d->sif0_waiting=0;
    return ac4_sif_irq_pending(d) ? AC4_DEVICE : 0;
}

/* One action is a tag, tag-data pair, or payload quadword. Work is bounded even
 * for cyclic/zero-length chains. Empty input/full output preserves busy state.
 */
static inline int ac4_sif_channel(Ac4Cpu *c,Ac4Devices *d,Ac4SifTransport *s,
                                  unsigned index,unsigned actions) {
    Ac4DmaRegisters *ch=&d->dma[5+index];
    if (s->generation[index]!=d->sif_generation[index]) {
        s->generation[index]=d->sif_generation[index];
        s->loaded[index]=0; s->end[index]=0;
        if (index) s->extra=0;
        /* Resuming nonzero QWC from a register-written TAG is not established
         * for this SIF subset. Preserve it and stop instead of guessing. */
        if ((ch->chcr&0x100) && ch->qwc) return AC4_DEVICE;
    }
    if (!(ch->chcr&0x100)) return 0;
    if ((ch->chcr&0x3c)!=4) return AC4_DEVICE;
    if (!(d->d_ctrl&1) || (d->d_enable&0x10000)) return 0;
    if ((d->d_ctrl&0xfc) || (d->d_pcr&0x80000000)) return AC4_DEVICE;
    for (unsigned action=0;action<actions;action++) {
        if (index && s->extra) {
            uint32_t pair[2]={(uint32_t)s->extra_data,(uint32_t)(s->extra_data>>32)};
            if (!ac4_sif_push(&s->to_iop,pair,2)) return 0;
            s->extra=0; continue;
        }
        if (!ch->qwc && s->loaded[index]) {
            if (s->end[index]) return ac4_sif_finish(s,d,index);
            s->loaded[index]=0;
        }
        if (!s->loaded[index]) {
            if (ch->qwc) return AC4_DEVICE;
            uint32_t tag,address; uint64_t extra=0; unsigned char *storage=NULL;
            if (index) {
                int result=ac4_sif_ram(c,ch->tadr,&storage);
                if (result) return result;
                tag=ac4_sif_u32(storage); address=ac4_sif_u32(storage+4);
                extra=(uint64_t)ac4_sif_u32(storage+8)|((uint64_t)ac4_sif_u32(storage+12)<<32);
            } else {
                if (s->to_ee.count<2) return 0;
                tag=ac4_sif_peek(&s->to_ee,0); address=ac4_sif_peek(&s->to_ee,1);
            }
            unsigned id=(tag>>28)&7,qwc=tag&0xffff;
            if ((tag&0x0c000000) ||
                ((!index || id==0 || id==2 || id==3) && (address&0x8000000f))) return AC4_DEVICE;
            if (index ? !(id==0 || id==1 || id==2 || id==3 || id==7) : !(id==0 || id==1 || id==7))
                return AC4_DEVICE;
            s->end[index]=(id==7 || (index && id==0) || ((tag&0x80000000) && (ch->chcr&0x80)));
            if (index) {
                uint32_t adjacent=ch->tadr+16;
                ch->madr=(id==0 || id==3) ? address : adjacent;
                ch->tadr=(id==2) ? address : (id==0 || id==3) ? adjacent : adjacent+qwc*16;
                s->extra=(ch->chcr&0x40)!=0; s->extra_data=extra;
            } else {
                ch->madr=address; ac4_sif_drop(&s->to_ee,2);
            }
            ch->chcr=(ch->chcr&0xffff)|(tag&0xffff0000);
            ch->qwc=qwc; s->loaded[index]=1; s->tags[index]++;
            continue;
        }
        unsigned char *storage;
        if (index ? s->to_iop.count>AC4_SIF_WORDS-4 : s->to_ee.count<4) return 0;
        int result=ac4_sif_ram(c,ch->madr,&storage);
        if (result) return result;
        uint32_t words[4];
        if (index) {
            for (unsigned i=0;i<4;i++) words[i]=ac4_sif_u32(storage+4*i);
            if (!ac4_sif_push(&s->to_iop,words,4)) return 0;
        } else {
            if (!ac4_sif_pop(&s->to_ee,words,4)) return 0;
            for (unsigned i=0;i<4;i++) ac4_sif_put32(storage+4*i,words[i]);
        }
        ch->madr+=16; ch->qwc--; s->quadwords[index]++;
    }
    return 0;
}
static inline int ac4_sif_poll(Ac4Cpu *c,Ac4Devices *d,Ac4SifTransport *s,unsigned actions) {
    if (ac4_sif_irq_pending(d)) return AC4_DEVICE;
    int result=ac4_sif_channel(c,d,s,0,actions);
    return result ? result : ac4_sif_channel(c,d,s,1,actions);
}
#endif
