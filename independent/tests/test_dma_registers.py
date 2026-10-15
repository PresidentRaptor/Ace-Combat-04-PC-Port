"""Inactive DMA configuration and explicit non-completing SIF0 reception."""
from pathlib import Path
import unittest
from test_codegen import native

DEVICES=(Path(__file__).resolve().parents[1]/'ee_devices.h').read_text()


def device(program,registers,initial=''):
    wrapper='''
int device_run(Ac4Cpu *c,uint64_t budget) {
    Ac4Devices d={0}; INITIAL
    c->ee_memory_map=1; c->device_state=&d;
    c->device_read=ac4_device_read; c->device_write=ac4_device_write;
    int result=ac4_run(c,budget);
    c->gpr[24][0]=d.sif0_waiting; c->gpr[25][0]=d.intc_mask; c->gpr[26][0]=d.d_stat;
    return result;
}
'''.replace('INITIAL',initial)
    return native(program,registers=registers,extra_source=DEVICES+wrapper,run_function='device_run',paged=True)


class DmaRegisterTests(unittest.TestCase):
    def test_sif_mailbox_ownership_and_flag_write_directions(self):
        result=device({0:0xac820000,4:0x8c830000,8:0xac850000,12:0x8c860000,16:13},
                      {4:0x1000f220,2:0x10000,5:0x20000})
        self.assertEqual((result['r'][3],result['r'][6]),(0x10000,0x30000))
        result=device({0:0xac820000,4:0x8c830000,8:13},
                      {4:0x1000f230,2:0x10000},'d.sif_smflag=0x70000;')
        self.assertEqual(result['r'][3],0x60000)
        result=device({0:0xac820000,4:13},{4:0x1000f210,2:123})
        self.assertEqual(result['status'],11)

    def test_status_clear_and_mask_toggle_are_independent(self):
        result=device({0:0xac820000,4:0x8c830000,8:0xac850000,12:0x8c860000,16:13},
                      {4:0x1000e010,2:0x10001,5:0x10000},'d.d_stat=1;')
        self.assertEqual((result['status'],result['r'][3],result['r'][6]),(1,0x10000,0))

    def test_intc_status_ack_and_mask_toggle(self):
        result=device({0:0xac820000,4:0x8c830000,8:13},{4:0x1000f000,2:1},'d.intc_stat=5;')
        self.assertEqual((result['status'],result['r'][3]),(1,4))
        result=device({0:0xac820000,4:0x8c830000,8:0xac820000,12:0x8c850000,16:13},
                      {4:0x1000f010,2:4})
        self.assertEqual((result['r'][3],result['r'][5]),(4,0))

    def test_channel_address_and_count_masks(self):
        for offset,expected in ((0x10,0xfffffff0),(0x20,0xffff),(0x30,0xfffffff0)):
            result=device({0:0xac820000,4:0x8c830000,8:13},{4:0x1000c000+offset,2:-1})
            extended=expected if expected<0x80000000 else expected|0xffffffff00000000
            self.assertEqual(result['r'][3],extended)

    def test_sif0_arm_waits_without_ram_writes_completion_or_interrupt(self):
        result=device({0:0xac820000,4:0x8c830000,8:0x8c850000,12:13},{4:0x1000c000,2:0x184})
        self.assertEqual((result['status'],result['r'][3],result['r'][5]),(1,0x184,0x184))
        self.assertEqual((result['r'][24],result['r'][26]),(1,0))
        self.assertEqual(result['memory'],[0]*256)

    def test_outgoing_dma_and_pending_irq_remain_explicit_boundaries(self):
        result=device({0:0xac820000,4:13},{4:0x1000c400,2:0x185})
        self.assertEqual((result['status'],result['pc']),(11,0))
        result=device({0:0xac820000,4:13},{4:0x1000f010,2:4},'d.intc_stat=4;')
        self.assertEqual((result['status'],result['r'][25]),(11,0))


if __name__=='__main__':
    unittest.main()
