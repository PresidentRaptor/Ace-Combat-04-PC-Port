/* Independent functional IOP command endpoint and queued SifSetDma adapter.
 * Include after bootstrap_services.h, ee_devices.h and sif_transport.h.
 * This is an explicit host service profile, not IOP CPU/BIOS/IRX execution.
 * Actual submitted bytes traverse the SIF1 FIFO into separate IOP memory.
 * Only the RPC initialization acknowledgement exists; no RPC servers, BIOS
 * boot-complete flag or IRQ vector are supplied.
 */
#ifndef AC4_IOP_COMMAND_PEER_H
#define AC4_IOP_COMMAND_PEER_H
enum { AC4_IOP_ORDER=48,AC4_IOP_PACKET=49,AC4_IOP_COMMAND=50,AC4_IOP_ATTRIBUTE=51,
       AC4_IOP_JOBS=8,AC4_IOP_DESCRIPTORS=16 };
typedef struct { uint32_t source,destination,bytes,attribute; } Ac4IopTransfer;
typedef struct {
    Ac4IopTransfer descriptors[AC4_IOP_DESCRIPTORS];
    uint32_t id,count,index,offset;
    unsigned header_sent,waiting;
    uint64_t expected_receive;
} Ac4IopJob;
typedef struct {
    Ac4Devices *devices;
    Ac4SifTransport *transport;
    unsigned char *ram;
    uint32_t ram_size,receive_buffer,ee_receive_buffer,software[32];
    unsigned active,initialized;
    int error;
    Ac4IopJob jobs[AC4_IOP_JOBS];
    unsigned head,count;
    uint32_t next_id,completed_id;
    uint32_t rx_address,rx_remaining,rx_start,rx_size,rx_tag;
    unsigned rx_active;
    uint64_t received_transfers,received_words,submitted_quadwords,accepted_commands;
    uint32_t last_command,last_option,last_packet_size;
    uint32_t last_source,last_destination,last_size,last_attribute;
    unsigned reply_pending,rpc_init_ack_generated;
    uint32_t reply[10];
    uint64_t reply_packets;
} Ac4IopCommandPeer;

static inline int ac4_iop_start(Ac4IopCommandPeer *p,Ac4Devices *d,Ac4SifTransport *s,
                                unsigned char *ram,uint32_t size,uint32_t receive) {
    if (p->active || !ram || size>0x200000 || size<256 || (receive&15) ||
        receive>size-256 || !receive || d->sif_smcom || d->sif_smflag)
        return AC4_IOP_ORDER;
    p->devices=d; p->transport=s; p->ram=ram; p->ram_size=size;
    p->receive_buffer=receive; p->active=1;
    /* A live bounded receiver/command dispatcher now owns this address.
     * Advertise its lifecycle through the IOP-owned mailboxes, never BOOTEND. */
    (void)ac4_sif_iop_write(d,0x1d000010,receive);
    (void)ac4_sif_iop_write(d,0x1d000030,0x30000);
    return 0;
}

static inline int ac4_iop_command(Ac4IopCommandPeer *p,const unsigned char *packet,uint32_t bytes) {
    if (!p->active) return AC4_IOP_ORDER;
    if (bytes<16) return AC4_IOP_PACKET;
    uint32_t sizes=ac4_sif_u32(packet),size=sizes&255;
    p->last_command=ac4_sif_u32(packet+8); p->last_option=ac4_sif_u32(packet+12);
    p->last_packet_size=size;
    if (size<16 || size>bytes || size>256) return AC4_IOP_PACKET;
    if (sizes>>8) return AC4_IOP_COMMAND; /* Separate payload commands not implemented. */
    if (p->last_command==UINT32_C(0x80000000) ||
        (p->last_command==UINT32_C(0x80000002) && p->last_option==0)) {
        if (size!=20) return AC4_IOP_PACKET;
        uint32_t receive=ac4_sif_u32(packet+16);
        if (!receive || (receive&15) || receive>0x02000000-256) return AC4_IOP_PACKET;
        p->ee_receive_buffer=receive;
        if (p->last_command==UINT32_C(0x80000002)) {
            p->initialized=1;
            (void)ac4_sif_iop_write(p->devices,0x1d000030,0x20000);
        }
    } else if (p->last_command==UINT32_C(0x80000002) && p->last_option==1) {
        /* Local AC4 sends a header-only opt=1 request and polls SREG[0] for
         * nonzero at 0x265b98..0x265ba0. Reply through its actual SIF handler:
         * SET_SREG(0,1), not a direct write into the guest's software table.
         * This initializes the command protocol only, not any RPC server. */
        if (!p->initialized || !p->ee_receive_buffer || p->reply_pending) return AC4_IOP_ORDER;
        if (size!=16) return AC4_IOP_PACKET;
        uint32_t reply[10]={0xf0000002,p->ee_receive_buffer,24,0,0x80000001,0,0,1,0,0};
        for (unsigned i=0;i<10;i++) p->reply[i]=reply[i];
        p->reply_pending=1; p->rpc_init_ack_generated=1;
    } else if (p->last_command==UINT32_C(0x80000001)) {
        if (size!=24) return AC4_IOP_PACKET;
        uint32_t index=ac4_sif_u32(packet+16);
        if (index>=32) return AC4_IOP_PACKET;
        p->software[index]=ac4_sif_u32(packet+20);
    } else return AC4_IOP_COMMAND;
    p->accepted_commands++; return 0;
}

/* The kernel ABI accepts CPU aliases for the source/descriptor pointers. After
 * translation only bounded physical EE main RAM is used; no MMIO/SPR access.
 * Qword rounding reads actual source padding, not invented zero bytes.
 */
static inline int ac4_iop_source(Ac4Cpu *c,uint32_t address,uint32_t bytes,uint32_t *physical) {
    uint32_t a=ac4_physical(address);
    c->fault_address=address;
    if ((a&15) || !bytes || (bytes&15)) return AC4_ALIGNMENT;
    if (a>=0x02000000 || bytes>0x02000000-a || c->memory_base || !c->memory ||
        bytes>c->memory_size || a>c->memory_size-bytes) return AC4_BOUNDS;
    *physical=a; return 0;
}
static inline int ac4_iop_submit(Ac4IopCommandPeer *p,Ac4Cpu *c,uint32_t address,uint32_t count) {
    if (!p->active) return AC4_IOP_ORDER;
    if (p->error) return p->error;
    if (!count || count>AC4_IOP_DESCRIPTORS || (address&3) ||
        (uint64_t)address+(uint64_t)count*16>UINT64_C(0x100000000)) return AC4_SERVICE_ARGUMENT;
    if (p->count==AC4_IOP_JOBS) { c->gpr[2][0]=0; return 0; }
    if (p->next_id==INT32_MAX) return AC4_IOP_ORDER;
    if ((p->devices->dma[6].chcr&0x100) || (!p->count && p->transport->to_iop.count))
        return AC4_DEVICE;
    Ac4IopJob candidate={0}; candidate.count=count;
    for (unsigned i=0;i<count;i++) {
        uint32_t fields[4];
        for (unsigned field=0;field<4;field++) {
            uint32_t a=address+i*16+field*4,physical=ac4_physical(a);
            if (physical>=0x02000000 || ac4_device_address(physical)) return AC4_BOUNDS;
            uint64_t low,high;
            if (!ac4_load(c,a,4,&low,&high)) return c->memory_error;
            fields[field]=(uint32_t)low;
        }
        p->last_source=fields[0]; p->last_destination=fields[1];
        p->last_size=fields[2]; p->last_attribute=fields[3];
        if (!fields[2] || fields[2]>INT32_MAX-15) return AC4_SERVICE_ARGUMENT;
        uint32_t bytes=(fields[2]+15)&~UINT32_C(15),physical;
        int result=ac4_iop_source(c,fields[0],bytes,&physical);
        if (result) return result;
        if ((fields[1]&3) || bytes>p->ram_size || fields[1]>p->ram_size-bytes)
            return AC4_BOUNDS;
        /* Published ABI names INT_O=4, ERT=0x40. Their mapping to IOP
         * notification/end tag bits is provisional until independently traced.
         * The local AC4 initialization descriptor uses 0x44. */
        if (fields[3]&~UINT32_C(0x44)) return AC4_IOP_ATTRIBUTE;
        candidate.descriptors[i]=(Ac4IopTransfer){physical,fields[1],bytes,fields[3]};
    }
    candidate.id=++p->next_id;
    p->jobs[(p->head+p->count)%AC4_IOP_JOBS]=candidate; p->count++;
    c->gpr[2][0]=candidate.id; return 0;
}
static inline int ac4_iop_service(void *state,Ac4Cpu *c,uint32_t number) {
    Ac4IopCommandPeer *p=(Ac4IopCommandPeer *)state;
    if (number==119 || number==UINT32_C(0xffffff89))
        return ac4_iop_submit(p,c,(uint32_t)c->gpr[4][0],(uint32_t)c->gpr[5][0]);
    if (number!=118 && number!=UINT32_C(0xffffff8a)) return AC4_SERVICE_UNKNOWN;
    if (!p->active) return AC4_IOP_ORDER;
    uint32_t id=(uint32_t)c->gpr[4][0];
    c->gpr[2][0]=UINT64_MAX; /* Completed/unknown IDs: provisional negative ABI result. */
    for (unsigned i=0;i<p->count;i++) {
        Ac4IopJob *job=&p->jobs[(p->head+i)%AC4_IOP_JOBS];
        if (job->id==id) { c->gpr[2][0]=i ? 1 : 0; break; }
    }
    return 0;
}

static inline int ac4_iop_send_step(Ac4IopCommandPeer *p,Ac4Cpu *c) {
    if (!p->count) return 0;
    Ac4IopJob *job=&p->jobs[p->head];
    if (job->waiting) {
        if (p->received_transfers<job->expected_receive) return 0;
        job->index++; job->offset=0; job->waiting=0; job->header_sent=0;
        if (job->index==job->count) {
            p->completed_id=job->id; p->head=(p->head+1)%AC4_IOP_JOBS; p->count--;
            return 0;
        }
    }
    Ac4IopTransfer *transfer=&job->descriptors[job->index];
    if (!job->header_sent) {
        uint32_t tag[2]={transfer->destination|(transfer->attribute&0x40 ? UINT32_C(0x80000000) : 0)|
                        (transfer->attribute&4 ? UINT32_C(0x40000000) : 0),transfer->bytes/4};
        if (ac4_sif_push(&p->transport->to_iop,tag,2)) {
            job->header_sent=1; job->expected_receive=p->received_transfers+1;
        }
        return 0;
    }
    if (p->transport->to_iop.count>AC4_SIF_WORDS-4) return 0;
    unsigned char *source;
    int result=ac4_sif_ram(c,transfer->source+job->offset,&source);
    if (result) return result;
    uint32_t data[4];
    for (unsigned i=0;i<4;i++) data[i]=ac4_sif_u32(source+4*i);
    if (!ac4_sif_push(&p->transport->to_iop,data,4)) return 0;
    p->submitted_quadwords++; job->offset+=16;
    if (job->offset==transfer->bytes) job->waiting=1;
    return 0;
}
static inline int ac4_iop_receive_step(Ac4IopCommandPeer *p) {
    Ac4SifFifo *fifo=&p->transport->to_iop;
    if (!p->rx_active) {
        if (fifo->count<2) return 0;
        uint32_t tag=ac4_sif_peek(fifo,0),words=ac4_sif_peek(fifo,1),address=tag&0xffffff;
        if ((tag&0x3f000003) || !words || (words&~UINT32_C(0xfffffc)) ||
            words>p->ram_size/4 || address>p->ram_size-words*4) return AC4_IOP_PACKET;
        p->rx_tag=tag; p->rx_start=address; p->rx_address=address;
        p->rx_remaining=words; p->rx_size=words*4; p->rx_active=1;
        ac4_sif_drop(fifo,2); return 0;
    }
    uint32_t data[4];
    if (!ac4_sif_pop(fifo,data,4)) return 0;
    for (unsigned i=0;i<4;i++) ac4_sif_put32(p->ram+p->rx_address+4*i,data[i]);
    p->rx_address+=16; p->rx_remaining-=4; p->received_words+=4;
    if (!p->rx_remaining) {
        p->rx_active=0; p->received_transfers++;
        if (p->rx_start==p->receive_buffer && (p->rx_tag&0x40000000))
            return ac4_iop_command(p,p->ram+p->rx_start,p->rx_size);
    }
    return 0;
}
static inline int ac4_iop_poll(Ac4IopCommandPeer *p,Ac4Cpu *c,unsigned actions) {
    if (!p->active) return 0;
    if (p->error) return p->error;
    if (!(p->devices->d_ctrl&1) || (p->devices->d_enable&0x10000)) return 0;
    for (unsigned i=0;i<actions;i++) {
        if (p->reply_pending && ac4_sif_push(&p->transport->to_ee,p->reply,10)) {
            p->reply_pending=0; p->reply_packets++;
        }
        int result=ac4_iop_send_step(p,c);
        if (!result) result=ac4_iop_receive_step(p);
        if (result) { p->error=result; return result; }
    }
    return 0;
}
#endif
