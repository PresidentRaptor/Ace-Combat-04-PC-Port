/* Experimental single-thread startup services. Include after generated CPU C.
 * New implementation from documented ABI observations, not a BIOS replacement.
 * Stack/heap policy is provisional until compared against a hardware trace.
 */
#ifndef AC4_BOOTSTRAP_SERVICES_H
#define AC4_BOOTSTRAP_SERVICES_H

enum { AC4_SERVICE_UNKNOWN=32, AC4_SERVICE_ARGUMENT=33,
       AC4_SERVICE_ORDER=34, AC4_SERVICE_DELAY=35, AC4_SERVICE_OVERRIDE=37 };
typedef struct {
    uint32_t count, maximum, active;
} Ac4BootstrapSemaphore;
typedef struct { uint32_t resume; uint64_t ra; } Ac4BootstrapCall;
typedef struct {
    uint32_t gp, stack_low, stack_high, stack_pointer, args, root;
    uint32_t heap_start, heap_end, calls, last_number;
    unsigned thread_ready, heap_ready;
    Ac4BootstrapSemaphore semaphores[256];
    uint32_t syscall_overrides[256];
    uint32_t timer3_handler;
    unsigned enable_guest_overrides, call_depth;
    Ac4BootstrapCall guest_calls[16];
} Ac4Bootstrap;

static inline int ac4_bootstrap_service(Ac4Cpu *c, Ac4Bootstrap *b) {
    uint32_t number=(uint32_t)c->gpr[3][0];
    uint32_t a0=(uint32_t)c->gpr[4][0], a1=(uint32_t)c->gpr[5][0];
    uint32_t a2=(uint32_t)c->gpr[6][0];
    b->last_number=number;
    if (c->fault_delay) return AC4_SERVICE_DELAY;
    /* Optional ordinary-function bridge for documented guest kernel patches.
     * It supplies a private return sentinel and restores the caller's ra.
     * It does not model CP0 privilege transitions or arbitrary BIOS vectors. */
    if (number<256 && b->syscall_overrides[number]) {
        if (!b->enable_guest_overrides) return AC4_SERVICE_OVERRIDE;
        if (b->call_depth>=16) return AC4_SERVICE_ARGUMENT;
        Ac4BootstrapCall *frame=&b->guest_calls[b->call_depth++];
        frame->resume=c->pc+4; frame->ra=c->gpr[31][0];
        c->gpr[31][0]=UINT32_C(0xfff00000); c->pc=b->syscall_overrides[number];
        return 0;
    }
    if (number==60) {
        if (b->thread_ready) return AC4_SERVICE_ORDER;
        if (c->memory_base || !c->memory || !a2 || a2>c->memory_size || (a2&15))
            return AC4_SERVICE_ARGUMENT;
        uint64_t low=a1==UINT32_MAX ? (uint64_t)c->memory_size-a2 : a1;
        uint64_t high=low+a2;
        if ((low&15) || high>c->memory_size) return AC4_SERVICE_ARGUMENT;
        b->gp=a0; b->stack_low=(uint32_t)low; b->stack_high=(uint32_t)high;
        /* PS2tek documents RDRAM-size minus size for automatic-stack return.
         * This policy is explicitly experimental, not hardware-verified. */
        b->stack_pointer=a1==UINT32_MAX ? (uint32_t)low : (uint32_t)high;
        b->args=(uint32_t)c->gpr[7][0]; b->root=(uint32_t)c->gpr[8][0];
        b->thread_ready=1; c->gpr[2][0]=b->stack_pointer;
    } else if (number==61) {
        if (!b->thread_ready || b->heap_ready) return AC4_SERVICE_ORDER;
        uint64_t end=a1==UINT32_MAX ? b->stack_low : (uint64_t)a0+a1;
        if (a0>=end || end>b->stack_low) return AC4_SERVICE_ARGUMENT;
        b->heap_start=a0; b->heap_end=(uint32_t)end; b->heap_ready=1;
        c->gpr[2][0]=b->heap_end;
    } else if (number==64) {
        if (!b->thread_ready) return AC4_SERVICE_ORDER;
        uint64_t maximum, initial, high;
        if (a0>UINT32_MAX-11) return AC4_SERVICE_ARGUMENT;
        if (!ac4_load(c,a0+4,4,&maximum,&high) || !ac4_load(c,a0+8,4,&initial,&high))
            return c->memory_error;
        uint64_t result=UINT64_MAX;
        if (maximum && maximum<=INT32_MAX && initial<=maximum) {
            for (unsigned i=0;i<256;i++) {
                if (!b->semaphores[i].active) {
                    b->semaphores[i].active=1;
                    b->semaphores[i].maximum=(uint32_t)maximum;
                    b->semaphores[i].count=(uint32_t)initial;
                    result=i+1;
                    break;
                }
            }
        }
        c->gpr[2][0]=result;
    } else if (number==100) {
        /* This functional harness has coherent data and no hardware caches.
         * Changed compiled instruction bytes are checked at each fetch and stop.
         * FlushCache therefore has no further cache state to update. */
    } else if (number==116) {
        if ((a0>=256 && a0!=0x12c) || !a1 || (a1&3)) return AC4_SERVICE_ARGUMENT;
        /* The documented alarm patch uses out-of-table index 0x12c to install
         * timer-3's handler. Record it explicitly, not by corrupting host RAM.
         * Timer enable still stops until clock/interrupt delivery exists. */
        if (a0==0x12c) b->timer3_handler=a1;
        else b->syscall_overrides[a0]=a1;
    } else {
        return AC4_SERVICE_UNKNOWN;
    }
    b->calls++;
    c->pc+=4;
    return 0;
}

static inline int ac4_bootstrap_run(Ac4Cpu *c, Ac4Bootstrap *b, uint64_t budget) {
    uint64_t start=c->steps;
    while (c->steps-start<budget) {
        int status=ac4_run(c,budget-(c->steps-start));
        if (b->call_depth && c->pc==UINT32_C(0xfff00000) && !c->pending &&
            (status==AC4_FETCH || status==AC4_BUDGET)) {
            if (status==AC4_FETCH) c->steps--; /* Private dispatch lookup, not a guest instruction. */
            Ac4BootstrapCall *frame=&b->guest_calls[--b->call_depth];
            c->pc=frame->resume; c->gpr[31][0]=frame->ra; b->calls++;
            if (status==AC4_FETCH) continue;
        }
        if (status!=AC4_SYSCALL) return status;
        status=ac4_bootstrap_service(c,b);
        if (status) return status;
    }
    return AC4_BUDGET;
}
#endif
