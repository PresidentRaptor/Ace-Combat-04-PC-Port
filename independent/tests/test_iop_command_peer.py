"""Functional command-peer lifecycle and real queued packet delivery, not BIOS execution."""
from pathlib import Path
import unittest
from test_codegen import native
from test_bootstrap import HEADER
from test_dma_registers import DEVICES
from test_sif_transport import TRANSPORT

PEER=(Path(__file__).resolve().parents[1]/'iop_command_peer.h').read_text()


def peer(body):
    wrapper='''
#include <assert.h>
static void descriptor(Ac4Cpu *c,unsigned at,uint32_t src,uint32_t dst,uint32_t size,uint32_t attr) {
    ac4_sif_put32(c->memory+at,src); ac4_sif_put32(c->memory+at+4,dst);
    ac4_sif_put32(c->memory+at+8,size); ac4_sif_put32(c->memory+at+12,attr);
}
static void packet(unsigned char *at,uint32_t size,uint32_t command,uint32_t option,uint32_t value) {
    ac4_sif_put32(at,size); ac4_sif_put32(at+4,0); ac4_sif_put32(at+8,command);
    ac4_sif_put32(at+12,option); ac4_sif_put32(at+16,value);
}
int peer_run(Ac4Cpu *c,uint64_t budget) {
    (void)budget; (void)descriptor; (void)packet;
    Ac4Devices d={0}; Ac4SifTransport s={0}; Ac4IopCommandPeer p={0};
    unsigned char iop[1024]={0};
    c->memory_base=0; c->ee_memory_map=1; c->device_state=&d;
    c->device_read=ac4_device_read; c->device_write=ac4_device_write; d.d_ctrl=1;
    BODY
    return AC4_BREAK;
}
'''.replace('BODY',body)
    return native({0:13},extra_source=HEADER+DEVICES+TRANSPORT+PEER+wrapper,
                  run_function='peer_run',paged=True)


class IopCommandPeerTests(unittest.TestCase):
    def test_readiness_requires_real_endpoint_start_and_never_bootend(self):
        peer('''
    assert(!p.active && !d.sif_smcom && !d.sif_smflag);
    assert(ac4_iop_start(&p,&d,&s,iop,1024,800)==AC4_IOP_ORDER);
    assert(!p.active && !d.sif_smflag);
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    assert(p.active && p.receive_buffer==512 && d.sif_smcom==512 && d.sif_smflag==0x30000);
    assert(!p.initialized && !p.accepted_commands && !(d.sif_smflag&0x40000));
    assert(ac4_iop_start(&p,&d,&s,iop,1024,512)==AC4_IOP_ORDER);
''')

    def test_command_init_delivers_actual_padded_source_bytes(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    assert(!ac4_device_write(&d,0x1000f230,4,0x20000,0));
    packet(c->memory+64,20,0x80000002,0,128);
    for (unsigned i=20;i<32;i++) c->memory[64+i]=0xab;
    descriptor(c,32,64,512,20,0x44);
    assert(!ac4_iop_submit(&p,c,32,1) && c->gpr[2][0]==1);
    assert(!p.initialized && !p.received_transfers && !s.to_iop.count && iop[512]==0);
    assert(!ac4_iop_poll(&p,c,2) && p.received_words==4 && !p.initialized);
    assert(!ac4_iop_poll(&p,c,10));
    assert(p.initialized && p.ee_receive_buffer==128 && p.accepted_commands==1);
    assert(p.received_transfers==1 && p.submitted_quadwords==2 && !p.count);
    assert(d.sif_smflag==0x30000 && !s.to_iop.count);
    for (unsigned i=0;i<32;i++) assert(iop[512+i]==c->memory[64+i]);
''')

    def test_status_distinguishes_queued_active_and_completed_jobs(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    descriptor(c,32,64,128,16,0); c->memory[64]=0x72;
    assert(!ac4_iop_submit(&p,c,32,1)); assert(!ac4_iop_submit(&p,c,32,1));
    c->gpr[4][0]=1; assert(!ac4_iop_service(&p,c,118) && c->gpr[2][0]==0);
    c->gpr[4][0]=2; assert(!ac4_iop_service(&p,c,118) && c->gpr[2][0]==1);
    assert(!ac4_iop_poll(&p,c,3) && p.completed_id==1 && p.count==1);
    c->gpr[4][0]=1; assert(!ac4_iop_service(&p,c,118) && c->gpr[2][0]==UINT64_MAX);
    assert(!ac4_iop_poll(&p,c,10) && p.completed_id==2 && !p.count && iop[128]==0x72);
    c->gpr[4][0]=2; assert(!ac4_iop_service(&p,c,118) && c->gpr[2][0]==UINT64_MAX);
''')

    def test_bad_later_descriptor_does_not_enqueue_part_of_batch(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    descriptor(c,32,64,128,16,0); descriptor(c,48,80,1008,32,0);
    assert(ac4_iop_submit(&p,c,32,2)==AC4_BOUNDS);
    assert(!p.count && !p.next_id && !s.to_iop.count && !p.received_transfers);
    assert(!ac4_iop_poll(&p,c,100) && iop[128]==0);
''')

    def test_source_alias_and_descriptor_alias_are_validated_before_use(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    descriptor(c,32,0x80000040,128,16,0); c->memory[64]=0x9a;
    assert(!ac4_iop_submit(&p,c,0x80000020,1));
    assert(!ac4_iop_poll(&p,c,10) && iop[128]==0x9a);
    descriptor(c,32,0x1000f200,128,16,0);
    assert(ac4_iop_submit(&p,c,32,1)==AC4_BOUNDS && !p.count);
    assert(ac4_iop_submit(&p,c,0x1000f200,1)==AC4_BOUNDS && !p.count);
    descriptor(c,32,240,128,17,0);
    assert(ac4_iop_submit(&p,c,32,1)==AC4_BOUNDS && !p.count);
''')

    def test_queue_capacity_returns_zero_without_losing_existing_jobs(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    descriptor(c,32,64,128,16,0);
    for (unsigned i=0;i<8;i++) assert(!ac4_iop_submit(&p,c,32,1) && c->gpr[2][0]==i+1);
    assert(!ac4_iop_submit(&p,c,32,1) && c->gpr[2][0]==0 && p.count==8 && p.next_id==8);
    assert(!ac4_iop_poll(&p,c,100) && p.completed_id==8 && !p.count);
''')

    def test_disabled_dma_defers_queued_work_and_command_flags(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    descriptor(c,32,64,128,16,0); c->memory[64]=0x66;
    assert(!ac4_iop_submit(&p,c,32,1)); d.d_ctrl=0;
    assert(!ac4_iop_poll(&p,c,100) && p.count==1 && !p.received_transfers);
    d.d_ctrl=1; d.d_enable=0x10000;
    assert(!ac4_iop_poll(&p,c,100) && !p.submitted_quadwords);
    d.d_enable=0; assert(!ac4_iop_poll(&p,c,100) && iop[128]==0x66 && !p.count);
''')

    def test_unsupported_attributes_and_unaligned_sources_stay_explicit(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    descriptor(c,32,64,128,16,2);
    assert(ac4_iop_submit(&p,c,32,1)==AC4_IOP_ATTRIBUTE);
    descriptor(c,32,64,128,16,0x80);
    assert(ac4_iop_submit(&p,c,32,1)==AC4_IOP_ATTRIBUTE);
    descriptor(c,32,65,128,16,0);
    assert(ac4_iop_submit(&p,c,32,1)==AC4_ALIGNMENT);
    assert(!p.count && !p.next_id);
''')

    def test_incomplete_wire_data_does_not_run_command_handler(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    uint32_t input[]={0xc0000200,8,20,0,0x80000002,0,128,0,0,0};
    assert(ac4_sif_push(&s.to_iop,input,9));
    assert(!ac4_iop_poll(&p,c,100) && p.rx_active && !p.accepted_commands);
    assert(p.received_words==4 && p.rx_remaining==4);
    assert(ac4_sif_push(&s.to_iop,input+9,1));
    assert(!ac4_iop_poll(&p,c,100) && !p.rx_active && p.accepted_commands==1);
''')

    def test_command_buffer_copy_without_iop_notification_does_not_dispatch(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    packet(c->memory+64,20,0x80000002,0,128); descriptor(c,32,64,512,20,0);
    assert(!ac4_iop_submit(&p,c,32,1)); assert(!ac4_iop_poll(&p,c,100));
    assert(p.received_transfers==1 && !p.accepted_commands && !p.initialized);
    assert(ac4_sif_u32(iop+520)==0x80000002);
''')

    def test_unknown_rpc_bind_does_not_produce_fake_reply(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    packet(c->memory+64,20,0x80000009,0,128); descriptor(c,32,64,512,20,4);
    assert(!ac4_iop_submit(&p,c,32,1));
    assert(ac4_iop_poll(&p,c,100)==AC4_IOP_COMMAND);
    assert(p.last_command==0x80000009 && !p.accepted_commands);
    assert(ac4_iop_poll(&p,c,100)==AC4_IOP_COMMAND && p.error==AC4_IOP_COMMAND);
    unsigned count=p.count;
    assert(ac4_iop_submit(&p,c,32,1)==AC4_IOP_COMMAND && p.count==count);
    assert(!s.to_ee.count && !d.d_stat && !(d.sif_smflag&0x40000));
''')

    def test_rpc_init_ack_is_a_real_packet_and_stops_at_pending_dma_irq(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    unsigned char cmd[32]={0}; packet(cmd,20,0x80000002,0,128);
    assert(!ac4_iop_command(&p,cmd,32));
    packet(cmd,16,0x80000002,1,0);
    assert(!ac4_iop_command(&p,cmd,16) && p.reply_pending && !s.to_ee.count);
    assert(!ac4_iop_poll(&p,c,1) && s.to_ee.count==10 && p.reply_packets==1);
    assert(c->memory[128]==0 && !d.d_stat);
    d.d_stat=0x200000;
    assert(!ac4_device_write(&d,0x1000c000,4,0x184,0));
    assert(ac4_sif_poll(c,&d,&s,16)==AC4_DEVICE);
    assert(ac4_sif_u32(c->memory+128)==24 && ac4_sif_u32(c->memory+136)==0x80000001);
    assert(ac4_sif_u32(c->memory+144)==0 && ac4_sif_u32(c->memory+148)==1);
    assert(s.quadwords[0]==2 && d.d_stat==0x200020 && s.completions[0]==1);
    assert(p.rpc_init_ack_generated && p.accepted_commands==2 && !(d.sif_smflag&0x40000));
''')

    def test_rpc_init_order_and_reply_backpressure_preserve_ack(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    unsigned char cmd[32]={0}; packet(cmd,16,0x80000002,1,0);
    assert(ac4_iop_command(&p,cmd,16)==AC4_IOP_ORDER && !p.reply_pending);
    packet(cmd,20,0x80000002,0,128); assert(!ac4_iop_command(&p,cmd,32));
    uint32_t filler[64]={0}; assert(ac4_sif_push(&s.to_ee,filler,60));
    packet(cmd,16,0x80000002,1,0); assert(!ac4_iop_command(&p,cmd,16));
    assert(!ac4_iop_poll(&p,c,100) && p.reply_pending && s.to_ee.count==60 && !p.reply_packets);
    assert(ac4_iop_command(&p,cmd,16)==AC4_IOP_ORDER);
    assert(ac4_sif_pop(&s.to_ee,filler,60));
    assert(!ac4_iop_poll(&p,c,1) && !p.reply_pending && s.to_ee.count==10 && p.reply_packets==1);
''')

    def test_command_header_bounds_and_sreg_index_validation(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    unsigned char cmd[32]={0};
    assert(ac4_iop_command(&p,cmd,12)==AC4_IOP_PACKET);
    packet(cmd,20,0x80000002,0,128);
    assert(ac4_iop_command(&p,cmd,16)==AC4_IOP_PACKET);
    packet(cmd,20,0x80000002,0,129);
    assert(ac4_iop_command(&p,cmd,32)==AC4_IOP_PACKET);
    packet(cmd,24,0x80000001,0,32);
    assert(ac4_iop_command(&p,cmd,32)==AC4_IOP_PACKET);
    packet(cmd,24,0x80000001,0,3); ac4_sif_put32(cmd+20,0xaabbccdd);
    assert(!ac4_iop_command(&p,cmd,32) && p.software[3]==0xaabbccdd);
    packet(cmd,20,0x80000000,0,128);
    assert(!ac4_iop_command(&p,cmd,32) && p.ee_receive_buffer==128);
    assert(p.accepted_commands==2 && !p.initialized);
''')

    def test_bad_wire_tag_keeps_fifo_and_iop_ram_unchanged(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    uint32_t input[]={0xc00003fc,8,1,2,3,4,5,6,7,8};
    assert(ac4_sif_push(&s.to_iop,input,10));
    assert(ac4_iop_poll(&p,c,10)==AC4_IOP_PACKET && s.to_iop.count==10);
    assert(!p.rx_active && !p.received_words && iop[1020]==0);
''')

    def test_bootstrap_dma_hook_advances_pc_only_after_accepted_submission(self):
        peer('''
    assert(!ac4_iop_start(&p,&d,&s,iop,1024,512));
    descriptor(c,32,64,128,16,0); Ac4Bootstrap b={0};
    b.sif_service_state=&p; b.sif_service=ac4_iop_service;
    c->gpr[3][0]=119; c->gpr[4][0]=32; c->gpr[5][0]=1;
    assert(!ac4_bootstrap_service(c,&b) && c->pc==4 && b.calls==1 && p.count==1);
    c->gpr[3][0]=0xffffff8a; c->gpr[4][0]=1;
    assert(!ac4_bootstrap_service(c,&b) && c->pc==8 && c->gpr[2][0]==0);
    c->gpr[3][0]=119; c->gpr[4][0]=33;
    assert(ac4_bootstrap_service(c,&b)==AC4_SERVICE_ARGUMENT && c->pc==8 && b.calls==2);
''')


if __name__=='__main__':
    unittest.main()
