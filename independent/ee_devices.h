/* New, bounded EE timer register model from PS2tek's timer descriptions.
 * Active timers deliberately stop: bus-clock scheduling/IRQs do not exist yet.
 */
#ifndef AC4_EE_DEVICES_H
#define AC4_EE_DEVICES_H
typedef struct { uint32_t count,mode,compare,hold; } Ac4TimerRegisters;
typedef struct { Ac4TimerRegisters timers[4]; } Ac4Devices;

static inline int ac4_timer_decode(uint32_t address,unsigned bytes,unsigned *index,unsigned *reg) {
    if (bytes!=4 || address<UINT32_C(0x10000000) || address>=UINT32_C(0x10002000))
        return 0;
    uint32_t offset=address-UINT32_C(0x10000000);
    *index=offset/0x800; *reg=offset%0x800;
    return *reg==0 || *reg==0x10 || *reg==0x20 || (*index<2 && *reg==0x30);
}
static inline int ac4_device_read(void *state,uint32_t address,unsigned bytes,uint64_t *low,uint64_t *high) {
    unsigned index,reg;
    if (!ac4_timer_decode(address,bytes,&index,&reg)) return AC4_DEVICE;
    Ac4TimerRegisters *timer=&((Ac4Devices *)state)->timers[index];
    if (timer->mode&0x80) return AC4_DEVICE;
    *high=0;
    *low=reg==0 ? timer->count : reg==0x10 ? timer->mode : reg==0x20 ? timer->compare : timer->hold;
    return 0;
}
static inline int ac4_device_write(void *state,uint32_t address,unsigned bytes,uint64_t low,uint64_t high) {
    unsigned index,reg;
    (void)high;
    if (!ac4_timer_decode(address,bytes,&index,&reg) || reg==0x30) return AC4_DEVICE;
    Ac4TimerRegisters *timer=&((Ac4Devices *)state)->timers[index];
    if ((timer->mode&0x80) || (reg==0x10 && (low&0x80))) return AC4_DEVICE;
    if (reg==0) timer->count=(uint32_t)low&0xffff;
    else if (reg==0x20) timer->compare=(uint32_t)low&0xffff;
    else timer->mode=(timer->mode&0xc00&~(uint32_t)low)|((uint32_t)low&0x3ff);
    return 0;
}
#endif
