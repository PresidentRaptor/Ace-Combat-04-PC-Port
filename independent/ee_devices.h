/* Bounded EE register models from PS2tek's hardware descriptions.
 * Active timers, DMA payload movement and IRQ delivery remain unsupported.
 * SIF0 can be armed to wait for incoming data; it never fabricates completion.
 */
#ifndef AC4_EE_DEVICES_H
#define AC4_EE_DEVICES_H
typedef struct { uint32_t count,mode,compare,hold; } Ac4TimerRegisters;
typedef struct { uint32_t chcr,madr,qwc,tadr,asr0,asr1,sadr; } Ac4DmaRegisters;
typedef struct {
    Ac4TimerRegisters timers[4];
    Ac4DmaRegisters dma[10];
    uint32_t d_ctrl,d_stat,d_pcr,d_sqwc,d_rbsr,d_rbor,d_stadr,d_enable;
    uint32_t intc_stat,intc_mask;
    unsigned sif0_waiting;
    uint32_t sif_mscom,sif_smcom,sif_msflag,sif_smflag;
    uint32_t last_read_address;
    uint64_t last_read_value,read_count;
} Ac4Devices;

static inline uint32_t *ac4_dma_register(Ac4Devices *d,uint32_t address,uint32_t *mask,int *control) {
    static const uint32_t bases[10]={0x10008000,0x10009000,0x1000a000,0x1000b000,0x1000b400,
                                     0x1000c000,0x1000c400,0x1000c800,0x1000d000,0x1000d400};
    *control=0;
    for (unsigned i=0;i<10;i++) {
        if (address<bases[i] || address-bases[i]>=0x100) continue;
        Ac4DmaRegisters *channel=&d->dma[i];
        switch (address-bases[i]) {
        case 0: *mask=0xffff01fd; *control=1; return &channel->chcr;
        case 0x10: *mask=0xfffffff0; return &channel->madr;
        case 0x20: *mask=0xffff; return &channel->qwc;
        case 0x30: *mask=0xfffffff0; return &channel->tadr;
        case 0x40: if (i<3) { *mask=0xfffffff0; return &channel->asr0; } break;
        case 0x50: if (i<3) { *mask=0xfffffff0; return &channel->asr1; } break;
        case 0x80: if (i>=8) { *mask=0x3ff0; return &channel->sadr; } break;
        default: break;
        }
        return NULL;
    }
    return NULL;
}
static inline uint32_t *ac4_dma_global(Ac4Devices *d,uint32_t address,uint32_t *mask) {
    switch (address) {
    case 0x1000e000: *mask=0x7ff; return &d->d_ctrl;
    case 0x1000e020: *mask=0x83ff03ff; return &d->d_pcr;
    case 0x1000e030: *mask=0x00ff00ff; return &d->d_sqwc;
    case 0x1000e040: *mask=0x7ffffff0; return &d->d_rbsr;
    case 0x1000e050: *mask=0x7ffffff0; return &d->d_rbor;
    case 0x1000e060: *mask=0x7ffffff0; return &d->d_stadr;
    default: return NULL;
    }
}

static inline int ac4_timer_decode(uint32_t address,unsigned bytes,unsigned *index,unsigned *reg) {
    if (bytes!=4 || address<UINT32_C(0x10000000) || address>=UINT32_C(0x10002000))
        return 0;
    uint32_t offset=address-UINT32_C(0x10000000);
    *index=offset/0x800; *reg=offset%0x800;
    return *reg==0 || *reg==0x10 || *reg==0x20 || (*index<2 && *reg==0x30);
}
static inline int ac4_device_read_impl(void *state,uint32_t address,unsigned bytes,uint64_t *low,uint64_t *high) {
    Ac4Devices *devices=(Ac4Devices *)state;
    if (bytes==4) {
        *high=0;
        if (address==0x1000e010) { *low=devices->d_stat; return 0; }
        if (address==0x1000f000) { *low=devices->intc_stat; return 0; }
        if (address==0x1000f010) { *low=devices->intc_mask; return 0; }
        if (address==0x1000f520) { *low=devices->d_enable; return 0; }
        if (address==0x1000f200) { *low=devices->sif_mscom; return 0; }
        if (address==0x1000f210) { *low=devices->sif_smcom; return 0; }
        if (address==0x1000f220) { *low=devices->sif_msflag; return 0; }
        if (address==0x1000f230) { *low=devices->sif_smflag; return 0; }
        uint32_t mask; int control;
        uint32_t *value=ac4_dma_global(devices,address,&mask);
        if (!value) value=ac4_dma_register(devices,address,&mask,&control);
        if (value) { *low=*value&mask; return 0; }
    }
    unsigned index,reg;
    if (!ac4_timer_decode(address,bytes,&index,&reg)) return AC4_DEVICE;
    Ac4TimerRegisters *timer=&((Ac4Devices *)state)->timers[index];
    if (timer->mode&0x80) return AC4_DEVICE;
    *high=0;
    *low=reg==0 ? timer->count : reg==0x10 ? timer->mode : reg==0x20 ? timer->compare : timer->hold;
    return 0;
}
static inline int ac4_device_read(void *state,uint32_t address,unsigned bytes,uint64_t *low,uint64_t *high) {
    int result=ac4_device_read_impl(state,address,bytes,low,high);
    if (!result) {
        Ac4Devices *devices=(Ac4Devices *)state;
        devices->last_read_address=address; devices->last_read_value=*low; devices->read_count++;
    }
    return result;
}
static inline int ac4_device_write(void *state,uint32_t address,unsigned bytes,uint64_t low,uint64_t high) {
    unsigned index,reg;
    (void)high;
    Ac4Devices *devices=(Ac4Devices *)state;
    if (bytes==4) {
        uint32_t word=(uint32_t)low;
        if (address==0x1000e010) {
            uint32_t next=(devices->d_stat&0xe3ff&~word)|((devices->d_stat^word)&0x63ff0000);
            if ((next&0x8000) || ((next>>16)&next&0x63ff)) return AC4_DEVICE;
            devices->d_stat=next; return 0;
        }
        if (address==0x1000f000) { devices->intc_stat&=~word&0x7fff; return 0; }
        if (address==0x1000f010) {
            uint32_t next=(devices->intc_mask^word)&0x7fff;
            if (next&devices->intc_stat) return AC4_DEVICE;
            devices->intc_mask=next; return 0;
        }
        if (address==0x1000f590) { devices->d_enable=word; return 0; }
        if (address==0x1000f200) { devices->sif_mscom=word; return 0; }
        if (address==0x1000f220) { devices->sif_msflag|=word; return 0; }
        if (address==0x1000f230) { devices->sif_smflag&=~word; return 0; }
        uint32_t mask; int control=0;
        uint32_t *value=ac4_dma_global(devices,address,&mask);
        if (!value) value=ac4_dma_register(devices,address,&mask,&control);
        if (value) {
            if (control && (word&0x100)) {
                if (address!=0x1000c000 || word!=0x184) return AC4_DEVICE;
                devices->sif0_waiting=1;
            } else if (control && address==0x1000c000) devices->sif0_waiting=0;
            *value=word&mask; return 0;
        }
    }
    if (!ac4_timer_decode(address,bytes,&index,&reg) || reg==0x30) return AC4_DEVICE;
    Ac4TimerRegisters *timer=&((Ac4Devices *)state)->timers[index];
    if ((timer->mode&0x80) || (reg==0x10 && (low&0x80))) return AC4_DEVICE;
    if (reg==0) timer->count=(uint32_t)low&0xffff;
    else if (reg==0x20) timer->compare=(uint32_t)low&0xffff;
    else timer->mode=(timer->mode&0xc00&~(uint32_t)low)|((uint32_t)low&0x3ff);
    return 0;
}
#endif
