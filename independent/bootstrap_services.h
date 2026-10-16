/* Experimental cooperative startup services. Include after generated CPU C.
 * New implementation from documented ABI observations, not a BIOS replacement.
 * Stack/heap policy is provisional until compared against a hardware trace.
 */
#ifndef AC4_BOOTSTRAP_SERVICES_H
#define AC4_BOOTSTRAP_SERVICES_H

enum { AC4_SERVICE_UNKNOWN=32, AC4_SERVICE_ARGUMENT=33,
       AC4_SERVICE_ORDER=34, AC4_SERVICE_DELAY=35, AC4_SERVICE_OVERRIDE=37,
       AC4_SERVICE_IDLE=38 };
typedef struct {
    uint32_t count, maximum, active;
} Ac4BootstrapSemaphore;
typedef struct { uint32_t resume; uint64_t ra; } Ac4BootstrapCall;
typedef struct {
    uint64_t gpr[32][2],hi[2],lo[2];
    uint32_t pc,depth,cp0_status;
    uint32_t fpr[32],fcr31;
    Ac4BootstrapCall frames[16];
} Ac4ThreadContext;
typedef struct {
    unsigned state,priority,wait_kind,wait_id,wakeups;
    uint32_t entry,stack,size,gp;
    uint64_t order;
    Ac4ThreadContext context;
} Ac4BootstrapThread;
typedef struct {
    uint32_t address,arg,flags,gp,next,cause;
    unsigned active;
} Ac4BootstrapInterrupt;
typedef struct {
    uint32_t gp, stack_low, stack_high, stack_pointer, args, root;
    uint32_t heap_start, heap_end, calls, last_number;
    unsigned thread_ready, heap_ready;
    Ac4BootstrapSemaphore semaphores[256];
    uint32_t syscall_overrides[256];
    uint32_t timer3_handler;
    unsigned enable_guest_overrides, call_depth;
    Ac4BootstrapCall guest_calls[16];
    Ac4BootstrapThread threads[256];
    unsigned current_thread,context_switches;
    uint64_t ready_order;
    Ac4BootstrapInterrupt interrupt_handlers[2][64];
    uint32_t interrupt_heads[2][16];
    uint32_t sif_system[3];
    void *event_state;
    int (*poll_events)(void *,Ac4Cpu *);
} Ac4Bootstrap;

static inline int ac4_interrupt_service(Ac4Cpu *c,Ac4Bootstrap *b,uint32_t number) {
    uint32_t cause=(uint32_t)c->gpr[4][0],argument=(uint32_t)c->gpr[5][0];
    unsigned dma=(number==18 || number==19 || number==22 || number==23);
    uint32_t valid=dma ? UINT32_C(0xe3ff) : UINT32_C(0x7fff);
    uint64_t result=UINT64_MAX;
    if (cause<16 && (valid&(UINT32_C(1)<<cause))) {
        if (number<20) {
            Ac4BootstrapInterrupt *handlers=b->interrupt_handlers[dma];
            uint32_t *link=&b->interrupt_heads[dma][cause];
            if (number==16 || number==18) {
                uint32_t next=(uint32_t)c->gpr[6][0];
                unsigned slot=0;
                for (unsigned i=0;i<64;i++) if (!handlers[i].active) { slot=i+1; break; }
                int valid_next=next==0 || next==UINT32_MAX ||
                    (next<=64 && handlers[next-1].active && handlers[next-1].cause==cause);
                if (slot && argument && !(argument&3) && valid_next) {
                    unsigned visited=0;
                    if (next) while (*link && *link!=next && visited++<64) link=&handlers[*link-1].next;
                    if (visited>=64) return AC4_SERVICE_ARGUMENT;
                    Ac4BootstrapInterrupt *handler=&handlers[slot-1];
                    handler->active=1; handler->cause=cause; handler->address=argument;
                    handler->arg=(uint32_t)c->gpr[7][0]; handler->flags=(uint32_t)c->gpr[8][0];
                    handler->gp=(uint32_t)c->gpr[28][0]; handler->next=*link; *link=slot; result=slot;
                }
            } else if (argument && argument<=64 && handlers[argument-1].active && handlers[argument-1].cause==cause) {
                unsigned visited=0;
                while (*link && *link!=argument && visited++<64) link=&handlers[*link-1].next;
                if (*link==argument) { *link=handlers[argument-1].next; handlers[argument-1].active=0; result=0; }
            }
        } else if (!(dma && cause==15)) {
            uint32_t address=dma ? UINT32_C(0x1000e010) : UINT32_C(0x1000f010);
            unsigned shift=cause+(dma ? 16 : 0);
            uint64_t low,high;
            if (!ac4_load(c,address,4,&low,&high)) return c->memory_error;
            unsigned old=(unsigned)((low>>shift)&1),enabled=number==20 || number==22;
            result=old!=enabled;
            if (old!=enabled && !ac4_store(c,address,4,UINT64_C(1)<<shift,0)) return c->memory_error;
        }
    }
    c->gpr[2][0]=result; c->pc+=4; b->calls++;
    return 0;
}

static inline void ac4_thread_save(Ac4Cpu *c,Ac4Bootstrap *b,Ac4BootstrapThread *t) {
    for (unsigned r=0;r<32;r++) for (unsigned h=0;h<2;h++) t->context.gpr[r][h]=c->gpr[r][h];
    for (unsigned h=0;h<2;h++) { t->context.hi[h]=c->hi[h]; t->context.lo[h]=c->lo[h]; }
    t->context.pc=c->pc; t->context.depth=b->call_depth;
    t->context.cp0_status=c->cp0_status;
    for (unsigned r=0;r<32;r++) t->context.fpr[r]=c->fpr[r];
    t->context.fcr31=c->fcr31;
    for (unsigned i=0;i<b->call_depth;i++) t->context.frames[i]=b->guest_calls[i];
}
static inline void ac4_thread_restore(Ac4Cpu *c,Ac4Bootstrap *b,Ac4BootstrapThread *t) {
    for (unsigned r=0;r<32;r++) for (unsigned h=0;h<2;h++) c->gpr[r][h]=t->context.gpr[r][h];
    for (unsigned h=0;h<2;h++) { c->hi[h]=t->context.hi[h]; c->lo[h]=t->context.lo[h]; }
    c->pc=t->context.pc; c->pending=0; c->fault_delay=0;
    c->cp0_status=t->context.cp0_status;
    for (unsigned r=0;r<32;r++) c->fpr[r]=t->context.fpr[r];
    c->fcr31=t->context.fcr31;
    b->call_depth=t->context.depth;
    for (unsigned i=0;i<b->call_depth;i++) b->guest_calls[i]=t->context.frames[i];
}
static inline int ac4_reschedule(Ac4Cpu *c,Ac4Bootstrap *b) {
    unsigned chosen=0;
    for (unsigned i=0;i<256;i++) {
        Ac4BootstrapThread *t=&b->threads[i];
        if (t->state!=1 && t->state!=2) continue;
        if (!chosen || t->priority<b->threads[chosen-1].priority ||
            (t->priority==b->threads[chosen-1].priority && t->order<b->threads[chosen-1].order)) chosen=i+1;
    }
    if (!chosen) return AC4_SERVICE_IDLE;
    if (chosen!=b->current_thread) {
        if (b->current_thread) {
            Ac4BootstrapThread *old=&b->threads[b->current_thread-1];
            ac4_thread_save(c,b,old);
            if (old->state==1) old->state=2;
        }
        ac4_thread_restore(c,b,&b->threads[chosen-1]);
        b->current_thread=chosen; b->context_switches++;
    }
    b->threads[chosen-1].state=1;
    return 0;
}

static inline int ac4_thread_service(Ac4Cpu *c,Ac4Bootstrap *b,uint32_t number) {
    if (!b->thread_ready || !b->current_thread) return AC4_SERVICE_ORDER;
    uint32_t a0=(uint32_t)c->gpr[4][0],a1=(uint32_t)c->gpr[5][0];
    Ac4BootstrapThread *current=&b->threads[b->current_thread-1];
    uint64_t result=0;
    unsigned schedule=0;
    if (number==32) {
        uint64_t fields[6],high;
        if (a0>UINT32_MAX-23) return AC4_SERVICE_ARGUMENT;
        for (unsigned i=1;i<6;i++) if (!ac4_load(c,a0+i*4,4,&fields[i],&high)) return c->memory_error;
        result=UINT64_MAX;
        uint64_t top=fields[2]+fields[3];
        if (fields[1] && !(fields[1]&3) && fields[3]>=16 && !((fields[2]|fields[3])&15) &&
            top<=c->memory_size && fields[5]<128) {
            for (unsigned i=0;i<256;i++) if (!b->threads[i].state) {
                Ac4BootstrapThread *t=&b->threads[i];
                t->state=16; t->entry=(uint32_t)fields[1]; t->stack=(uint32_t)fields[2];
                t->size=(uint32_t)fields[3]; t->gp=(uint32_t)fields[4]; t->priority=(unsigned)fields[5];
                t->wakeups=0; t->wait_kind=0; t->wait_id=0; result=i+1; break;
            }
        }
    } else if (number==33) {
        if (!a0 || a0>256 || a0==b->current_thread || b->threads[a0-1].state!=16) result=UINT64_MAX;
        else b->threads[a0-1].state=0;
    } else if (number==34) {
        if (!a0 || a0>256 || a0==b->current_thread || b->threads[a0-1].state!=16) result=UINT64_MAX;
        else {
            Ac4BootstrapThread *t=&b->threads[a0-1];
            for (unsigned r=0;r<32;r++) for (unsigned h=0;h<2;h++) t->context.gpr[r][h]=0;
            for (unsigned h=0;h<2;h++) { t->context.hi[h]=0; t->context.lo[h]=0; }
            t->context.gpr[4][0]=a1; t->context.gpr[28][0]=t->gp;
            t->context.gpr[29][0]=(uint64_t)t->stack+t->size;
            t->context.gpr[31][0]=b->root; t->context.pc=t->entry; t->context.depth=0;
            t->context.cp0_status=c->cp0_status;
            for (unsigned r=0;r<32;r++) t->context.fpr[r]=0;
            t->context.fcr31=0;
            t->wakeups=0; t->wait_kind=0; t->wait_id=0;
            t->state=2; t->order=++b->ready_order; schedule=1;
        }
    } else if (number==35 || number==36) {
        current->state=number==35 ? 16 : 0; schedule=1;
    } else if (number==41) {
        unsigned id=a0 ? a0 : b->current_thread;
        if (id>256 || !b->threads[id-1].state || b->threads[id-1].state==16 || a1>=128) result=UINT64_MAX;
        else { result=b->threads[id-1].priority; b->threads[id-1].priority=a1; schedule=1; }
    } else if (number==43) {
        unsigned priority=a0 ? a0 : current->priority;
        if (priority>=128) result=UINT64_MAX;
        else {
            unsigned first=0;
            for (unsigned i=0;i<256;i++) {
                Ac4BootstrapThread *t=&b->threads[i];
                if ((t->state==1 || t->state==2) && t->priority==priority &&
                    (!first || t->order<b->threads[first-1].order)) first=i+1;
            }
            if (first) b->threads[first-1].order=++b->ready_order;
            schedule=1;
        }
    } else if (number==47) {
        result=b->current_thread;
    } else if (number==50) {
        if (current->wakeups) current->wakeups--;
        else { current->state=4; current->wait_kind=1; current->wait_id=0; schedule=1; }
    } else if (number==51 || number==52) {
        if (!a0 || a0>256 || !b->threads[a0-1].state || b->threads[a0-1].state==16) result=UINT64_MAX;
        else {
            Ac4BootstrapThread *t=&b->threads[a0-1];
            if (t->state==4 && t->wait_kind==1) {
                t->state=2; t->wait_kind=0; t->order=++b->ready_order;
            } else if (t->wakeups<UINT32_MAX) t->wakeups++;
            if (number==51) schedule=1;
        }
    } else if (number>=65 && number<=70) {
        if (!a0 || a0>256 || !b->semaphores[a0-1].active) result=UINT64_MAX;
        else {
            Ac4BootstrapSemaphore *sema=&b->semaphores[a0-1];
            if (number==65) {
                sema->active=0;
                for (unsigned i=0;i<256;i++) {
                    Ac4BootstrapThread *t=&b->threads[i];
                    if (t->state==4 && t->wait_kind==2 && t->wait_id==a0) {
                        t->state=2; t->wait_kind=0; t->wait_id=0; t->context.gpr[2][0]=UINT64_MAX;
                        t->order=++b->ready_order;
                    }
                }
                schedule=1;
            } else if (number==66 || number==67) {
                unsigned waiter=0;
                for (unsigned i=0;i<256;i++) {
                    Ac4BootstrapThread *t=&b->threads[i];
                    if (t->state==4 && t->wait_kind==2 && t->wait_id==a0 &&
                        (!waiter || t->order<b->threads[waiter-1].order)) waiter=i+1;
                }
                if (waiter) {
                    Ac4BootstrapThread *t=&b->threads[waiter-1];
                    t->state=2; t->wait_kind=0; t->wait_id=0; t->order=++b->ready_order;
                } else if (sema->count<sema->maximum) sema->count++;
                else result=UINT64_MAX;
                schedule=number==66;
            } else if (sema->count) sema->count--;
            else if (number==68) {
                current->state=4; current->wait_kind=2; current->wait_id=a0;
                current->order=++b->ready_order; schedule=1;
            } else result=UINT64_MAX;
        }
    } else return AC4_SERVICE_UNKNOWN;
    c->gpr[2][0]=result; c->pc+=4; b->calls++;
    if (current->state==4) ac4_thread_save(c,b,current);
    return schedule ? ac4_reschedule(c,b) : 0;
}

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
    if ((number>=32 && number<=36) || number==41 || number==43 || number==47 ||
        (number>=50 && number<=52) || (number>=65 && number<=70))
        return ac4_thread_service(c,b,number);
    if (number>=16 && number<=23) return ac4_interrupt_service(c,b,number);
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
        b->current_thread=1; b->threads[0].state=1; b->threads[0].priority=0;
        b->threads[0].order=++b->ready_order;
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
    } else if (number==121 || number==122) {
        uint32_t old;
        if (a0>=UINT32_C(0x80000000) && a0<=UINT32_C(0x80000002)) {
            unsigned index=a0-UINT32_C(0x80000000);
            old=b->sif_system[index];
            if (number==121) b->sif_system[index]=a1;
        } else if (a0>=1 && a0<=4) {
            uint32_t address=UINT32_C(0x1000f200)+(a0-1)*16;
            uint64_t low,high;
            if (!ac4_load(c,address,4,&low,&high)) return c->memory_error;
            old=(uint32_t)low;
            if (number==121 && !ac4_store(c,address,4,a1,0)) return c->memory_error;
        } else return AC4_SERVICE_ARGUMENT;
        /* Set returns the prior value in this experimental ABI profile. */
        c->gpr[2][0]=ac4_sext(old,32);
    } else if (number==120) {
        /* Arm SIF0 destination-chain reception; the device stays busy until
         * incoming IOP data actually exists. No synthetic completion/IRQ. */
        if (!ac4_store(c,UINT32_C(0x1000c020),4,0,0) ||
            !ac4_store(c,UINT32_C(0x1000c000),4,UINT64_C(0x184),0)) return c->memory_error;
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
    if (b->thread_ready && b->current_thread && b->threads[b->current_thread-1].state!=1) {
        int scheduled=ac4_reschedule(c,b);
        if (scheduled) return scheduled;
    }
    uint64_t start=c->steps;
    while (c->steps-start<budget) {
        if (b->poll_events) {
            int event=b->poll_events(b->event_state,c);
            if (event) return event;
        }
        uint64_t remaining=budget-(c->steps-start);
        uint64_t quantum=b->poll_events && remaining>256 ? 256 : remaining;
        int status=ac4_run(c,quantum);
        if (b->call_depth && c->pc==UINT32_C(0xfff00000) && !c->pending &&
            (status==AC4_FETCH || status==AC4_BUDGET)) {
            if (status==AC4_FETCH) c->steps--; /* Private dispatch lookup, not a guest instruction. */
            Ac4BootstrapCall *frame=&b->guest_calls[--b->call_depth];
            c->pc=frame->resume; c->gpr[31][0]=frame->ra; b->calls++;
            if (status==AC4_FETCH) continue;
        }
        if (status==AC4_BUDGET && c->steps-start<budget) continue;
        if (status!=AC4_SYSCALL) return status;
        status=ac4_bootstrap_service(c,b);
        if (status) return status;
    }
    return AC4_BUDGET;
}
#endif
