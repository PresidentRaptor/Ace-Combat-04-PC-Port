"""Real synthetic SIF payloads; no IOP readiness or hardware-timing oracle."""
from pathlib import Path
import unittest
from test_codegen import native
from test_dma_registers import DEVICES
from test_bootstrap import HEADER

TRANSPORT=(Path(__file__).resolve().parents[1]/'sif_transport.h').read_text()


def exercise(body):
    wrapper='''
#include <assert.h>
static int arm(Ac4Devices *d,unsigned index,uint32_t control) {
    return ac4_device_write(d,0x1000c000+index*0x400,4,control,0);
}
static void tag(Ac4Cpu *c,unsigned offset,uint32_t low,uint32_t address) {
    ac4_sif_put32(c->memory+offset,low); ac4_sif_put32(c->memory+offset+4,address);
}
int transport_run(Ac4Cpu *c,uint64_t budget) {
    (void)budget; (void)arm; (void)tag;
    Ac4Devices d={0}; Ac4SifTransport s={0};
    c->memory_base=0; c->ee_memory_map=1; d.d_ctrl=1;
    (void)d; (void)s;
    BODY
    return AC4_BREAK;
}
'''.replace('BODY',body)
    return native({0:13},extra_source=DEVICES+TRANSPORT+wrapper,
                  run_function='transport_run',paged=True)


class SifTransportTests(unittest.TestCase):
    def test_fifo_wraparound_and_atomic_backpressure(self):
        exercise('''
    uint32_t input[64],output[64]; for (unsigned i=0;i<64;i++) input[i]=i;
    assert(ac4_sif_push(&s.to_ee,input,64));
    assert(!ac4_sif_push(&s.to_ee,input,1) && s.to_ee.count==64);
    assert(ac4_sif_pop(&s.to_ee,output,61));
    for (unsigned i=0;i<61;i++) assert(output[i]==i);
    assert(ac4_sif_push(&s.to_ee,input,61));
    assert(ac4_sif_pop(&s.to_ee,output,64));
    assert(output[0]==61 && output[2]==63 && output[3]==0 && output[63]==60);
    output[0]=123; assert(!ac4_sif_pop(&s.to_ee,output,1));
    assert(output[0]==123 && !s.to_ee.count);
''')

    def test_iop_mailbox_ownership_and_bidirectional_acknowledgement(self):
        exercise('''
    uint32_t v=0;
    assert(!ac4_device_write(&d,0x1000f200,4,0x1000,0));
    assert(!ac4_sif_iop_read(&d,0x1d000000,&v) && v==0x1000);
    assert(ac4_sif_iop_write(&d,0x1d000000,123)==AC4_DEVICE && d.sif_mscom==0x1000);
    assert(!ac4_sif_iop_write(&d,0x1d000010,0x2000) && d.sif_smcom==0x2000);
    assert(!ac4_device_write(&d,0x1000f220,4,0x70000,0));
    assert(!ac4_sif_iop_write(&d,0x1d000020,0x20000) && d.sif_msflag==0x50000);
    assert(!ac4_sif_iop_write(&d,0x1d000030,0x10000));
    assert(!ac4_sif_iop_write(&d,0x1d000030,0x20000) && d.sif_smflag==0x30000);
    assert(!ac4_device_write(&d,0x1000f230,4,0x10000,0) && d.sif_smflag==0x20000);
    assert(ac4_sif_iop_read(&d,0x1d000040,&v)==AC4_DEVICE);
''')

    def test_empty_partial_tag_and_partial_quadword_stay_busy(self):
        exercise('''
    assert(!arm(&d,0,0x184));
    assert(!ac4_sif_poll(c,&d,&s,100));
    assert(d.sif0_waiting && d.dma[5].chcr==0x184 && !d.d_stat);
    uint32_t words[]={0x70000001,128,0x44332211,0x88776655,0xccbbaa99,0xffeedd00};
    assert(ac4_sif_push(&s.to_ee,words,1));
    assert(!ac4_sif_poll(c,&d,&s,100) && s.to_ee.count==1 && !s.tags[0]);
    assert(ac4_sif_push(&s.to_ee,words+1,4));
    assert(!ac4_sif_poll(c,&d,&s,100));
    assert(s.to_ee.count==3 && d.dma[5].qwc==1 && !s.quadwords[0]);
    assert(c->memory[128]==0 && !d.d_stat);
    assert(ac4_sif_push(&s.to_ee,words+5,1));
    assert(!ac4_sif_poll(c,&d,&s,100));
    assert(!d.sif0_waiting && !(d.dma[5].chcr&0x100) && d.d_stat==0x20);
    assert(s.quadwords[0]==1 && s.completions[0]==1 && !s.to_ee.count);
    assert(ac4_sif_u32(c->memory+128)==0x44332211 && ac4_sif_u32(c->memory+140)==0xffeedd00);
''')

    def test_destination_continue_and_end_preserve_words_after_end(self):
        exercise('''
    uint32_t input[]={0,128,0x10000001,144,11,22,33,44,0x70000000,160,0xabcdef};
    assert(ac4_sif_push(&s.to_ee,input,11)); assert(!arm(&d,0,0x184));
    assert(!ac4_sif_poll(c,&d,&s,100));
    assert(s.tags[0]==3 && s.quadwords[0]==1 && s.completions[0]==1);
    assert(s.to_ee.count==1 && ac4_sif_peek(&s.to_ee,0)==0xabcdef);
    assert(ac4_sif_u32(c->memory+144)==11 && ac4_sif_u32(c->memory+156)==44);
''')

    def test_irq_tag_waits_for_payload_then_latches_real_pending_irq(self):
        exercise('''
    uint32_t input[]={0x80000001,128,1,2,3,4};
    assert(ac4_sif_push(&s.to_ee,input,6)); assert(!arm(&d,0,0x184));
    d.d_stat=0x200000;
    assert(!ac4_sif_poll(c,&d,&s,1) && !(d.d_stat&0x20));
    assert(ac4_sif_poll(c,&d,&s,10)==AC4_DEVICE);
    assert(s.quadwords[0]==1 && s.completions[0]==1 && d.d_stat==0x200020);
    assert(ac4_sif_irq_pending(&d) && !(d.dma[5].chcr&0x100));
    assert(!ac4_device_write(&d,0x1000e010,4,0x20,0));
    assert(!ac4_sif_poll(c,&d,&s,10) && !ac4_sif_irq_pending(&d));
''')

    def test_disabled_dma_and_pause_preserve_queued_bytes(self):
        exercise('''
    uint32_t input[]={0x70000001,128,1,2,3,4};
    assert(ac4_sif_push(&s.to_ee,input,6)); assert(!arm(&d,0,0x184));
    d.d_ctrl=0; assert(!ac4_sif_poll(c,&d,&s,100) && s.to_ee.count==6);
    d.d_ctrl=1; d.d_enable=0x10000;
    assert(!ac4_sif_poll(c,&d,&s,100) && s.to_ee.count==6);
    d.d_enable=0; assert(!ac4_sif_poll(c,&d,&s,1) && d.dma[5].qwc==1);
    d.d_enable=0x10000; assert(!ac4_sif_poll(c,&d,&s,100) && !s.quadwords[0]);
    d.d_enable=0; assert(!ac4_sif_poll(c,&d,&s,100) && s.completions[0]==1);
    assert(!d.sif_smflag && !d.sif_msflag);
''')

    def test_invalid_tag_features_and_destinations_never_write_host_memory(self):
        exercise('''
    uint32_t input[]={0x20000001,128,1,2,3,4};
    assert(ac4_sif_push(&s.to_ee,input,6)); assert(!arm(&d,0,0x184));
    assert(ac4_sif_poll(c,&d,&s,10)==AC4_DEVICE && s.to_ee.count==6);
    s.to_ee.words[0]=0x70000001; s.to_ee.words[1]=129;
    assert(ac4_sif_poll(c,&d,&s,10)==AC4_DEVICE && s.to_ee.count==6);
    s.to_ee.words[1]=0x80000080;
    assert(ac4_sif_poll(c,&d,&s,10)==AC4_DEVICE && s.to_ee.count==6);
    s.to_ee.words[1]=256;
    assert(ac4_sif_poll(c,&d,&s,10)==AC4_BOUNDS && s.to_ee.count==4);
    assert(d.dma[5].qwc==1 && !s.quadwords[0] && !d.d_stat);
    assert(c->fault_address==256 && c->memory[128]==0);
''')

    def test_source_refe_with_tte_emits_tag_before_payload(self):
        exercise('''
    tag(c,64,2,128); tag(c,72,0x70000002,192);
    for (unsigned i=0;i<8;i++) ac4_sif_put32(c->memory+128+4*i,0x12340000+i);
    d.dma[6].tadr=64; assert(!arm(&d,1,0x1c5));
    assert(!ac4_sif_poll(c,&d,&s,1) && s.to_iop.count==0 && s.tags[1]==1);
    assert(!ac4_sif_poll(c,&d,&s,1) && s.to_iop.count==2);
    assert(ac4_sif_peek(&s.to_iop,0)==0x70000002 && ac4_sif_peek(&s.to_iop,1)==192);
    assert(!ac4_sif_poll(c,&d,&s,10) && s.to_iop.count==10);
    for (unsigned i=0;i<8;i++) assert(ac4_sif_peek(&s.to_iop,2+i)==0x12340000+i);
    assert(d.dma[6].madr==160 && d.dma[6].tadr==80 && !d.dma[6].qwc);
    assert(d.d_stat==0x40 && s.completions[1]==1);
''')

    def test_source_fifo_full_blocks_without_consuming_payload(self):
        exercise('''
    tag(c,64,0x70000001,0); tag(c,80,0x11223344,0x55667788);
    uint32_t filler[64]={0}; assert(ac4_sif_push(&s.to_iop,filler,63));
    d.dma[6].tadr=64; assert(!arm(&d,1,0x105));
    assert(!ac4_sif_poll(c,&d,&s,100));
    assert(s.to_iop.count==63 && d.dma[6].qwc==1 && d.dma[6].madr==80 && !d.d_stat);
    assert(ac4_sif_pop(&s.to_iop,filler,63));
    assert(!ac4_sif_poll(c,&d,&s,100) && s.to_iop.count==4 && s.completions[1]==1);
    assert(ac4_sif_peek(&s.to_iop,0)==0x11223344);
''')

    def test_source_cnt_ref_next_and_end_chaining(self):
        exercise('''
    tag(c,32,0x10000001,0); tag(c,48,11,22);
    tag(c,64,0x30000001,160); tag(c,80,0x20000001,128); tag(c,96,33,44);
    tag(c,128,0x70000000,0); tag(c,160,55,66);
    d.dma[6].tadr=32; assert(!arm(&d,1,0x105));
    assert(!ac4_sif_poll(c,&d,&s,100));
    assert(s.tags[1]==4 && s.quadwords[1]==3 && s.completions[1]==1);
    assert(s.to_iop.count==12 && ac4_sif_peek(&s.to_iop,0)==11);
    assert(ac4_sif_peek(&s.to_iop,4)==55 && ac4_sif_peek(&s.to_iop,8)==33);
''')

    def test_source_loop_is_bounded_and_unsupported_features_stay_explicit(self):
        exercise('''
    tag(c,32,0x20000000,32); d.dma[6].tadr=32;
    assert(!arm(&d,1,0x105)); assert(!ac4_sif_poll(c,&d,&s,17));
    assert(s.tags[1]==17 && !s.completions[1] && (d.dma[6].chcr&0x100));
    tag(c,32,0x50000000,32);
    assert(ac4_sif_poll(c,&d,&s,17)==AC4_DEVICE && s.tags[1]==17);
    tag(c,32,0x24000000,32);
    assert(ac4_sif_poll(c,&d,&s,17)==AC4_DEVICE);
    tag(c,32,0x20000000,32); d.d_ctrl|=0x10;
    assert(ac4_sif_poll(c,&d,&s,17)==AC4_DEVICE);
''')

    def test_tag_irq_does_not_terminate_when_tie_is_disabled(self):
        exercise('''
    uint32_t input[]={0x80000001,128,1,2,3,4,0x70000000,160};
    assert(ac4_sif_push(&s.to_ee,input,8)); assert(!arm(&d,0,0x104));
    assert(!ac4_sif_poll(c,&d,&s,100));
    assert(s.tags[0]==2 && s.completions[0]==1 && s.quadwords[0]==1);
    assert(!s.to_ee.count && d.d_stat==0x20);
''')

    def test_dma_physical_bounds_never_use_cpu_alias_or_mmio(self):
        exercise('''
    tag(c,64,1,0x1000f200); d.dma[6].tadr=64; assert(!arm(&d,1,0x105));
    assert(ac4_sif_poll(c,&d,&s,100)==AC4_BOUNDS);
    assert(!s.to_iop.count && !s.quadwords[1] && !d.d_stat);
    assert(c->fault_address==0x1000f200 && !d.sif_mscom);
    assert(!arm(&d,1,0)); d.dma[6].qwc=0; d.dma[6].tadr=0x80000040;
    assert(!arm(&d,1,0x105));
    assert(ac4_sif_poll(c,&d,&s,100)==AC4_BOUNDS);
    assert(!s.to_iop.count && !s.quadwords[1]);
''')

    def test_last_ram_quadword_is_valid_and_next_one_preserves_fifo(self):
        exercise('''
    uint32_t input[]={0x70000002,240,1,2,3,4,5,6,7,8};
    assert(ac4_sif_push(&s.to_ee,input,10)); assert(!arm(&d,0,0x184));
    assert(ac4_sif_poll(c,&d,&s,100)==AC4_BOUNDS);
    assert(s.quadwords[0]==1 && s.to_ee.count==4 && d.dma[5].qwc==1);
    assert(d.dma[5].madr==256 && !d.d_stat && !s.completions[0]);
    assert(ac4_sif_u32(c->memory+240)==1 && ac4_sif_u32(c->memory+252)==4);
''')

    def test_stop_rearm_and_nonzero_qwc_resume_are_not_guessed(self):
        exercise('''
    uint32_t input[]={0x70000000,128};
    assert(ac4_sif_push(&s.to_ee,input,2)); assert(!arm(&d,0,0x184));
    assert(!arm(&d,0,0)); assert(!ac4_sif_poll(c,&d,&s,100) && s.to_ee.count==2);
    assert(!arm(&d,0,0x184)); assert(!ac4_sif_poll(c,&d,&s,100) && s.completions[0]==1);
    d.dma[5].qwc=1; assert(!arm(&d,0,0x184));
    assert(ac4_sif_poll(c,&d,&s,10)==AC4_DEVICE);
    assert(ac4_sif_poll(c,&d,&s,10)==AC4_DEVICE && d.dma[5].qwc==1);
''')

    def test_synthetic_peer_loopback_moves_actual_bytes_between_ram_buffers(self):
        exercise('''
    tag(c,64,2,128); tag(c,72,0x70000002,192);
    for (unsigned i=0;i<32;i++) c->memory[128+i]=(unsigned char)(i^0xa5);
    d.dma[6].tadr=64; assert(!arm(&d,1,0x145)); assert(!arm(&d,0,0x184));
    assert(!ac4_sif_poll(c,&d,&s,100) && s.to_iop.count==10);
    uint32_t wire[10]; assert(ac4_sif_pop(&s.to_iop,wire,10));
    assert(ac4_sif_push(&s.to_ee,wire,10));
    assert(!ac4_sif_poll(c,&d,&s,100));
    for (unsigned i=0;i<32;i++) assert(c->memory[192+i]==(unsigned char)(i^0xa5));
    assert(d.d_stat==0x60 && s.completions[0]==1 && s.completions[1]==1);
    assert(!d.sif_smflag && !d.sif_msflag);
''')

    def test_bootstrap_polls_during_guest_loop_without_losing_global_budget(self):
        wrapper='''
static int events(void *state,Ac4Cpu *c) {
    unsigned *calls=(unsigned *)state; (*calls)++; c->gpr[10][0]=*calls;
    return *calls==3 ? AC4_DEVICE : 0;
}
int event_run(Ac4Cpu *c,uint64_t budget) {
    Ac4Bootstrap b={0}; unsigned calls=0;
    b.event_state=&calls; b.poll_events=events;
    return ac4_bootstrap_run(c,&b,budget);
}
'''
        result=native({0:0x1000ffff,4:0},limit=1000,extra_source=HEADER+wrapper,
                      run_function='event_run',paged=True)
        self.assertEqual((result['status'],result['steps'],result['r'][10]),(11,512,3))
        result=native({0:0x1000ffff,4:0},limit=300,extra_source=HEADER+wrapper,
                      run_function='event_run',paged=True)
        self.assertEqual((result['status'],result['steps'],result['r'][10]),(8,300,2))


if __name__=='__main__':
    unittest.main()
