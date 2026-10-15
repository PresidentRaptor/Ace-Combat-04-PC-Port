"""Handler registration/masks, not asynchronous interrupt delivery."""
import unittest
from test_bootstrap import HEADER
from test_dma_registers import DEVICES
from test_codegen import native


def service(program,registers):
    wrapper='''
int interrupt_run(Ac4Cpu *c,uint64_t budget) {
    Ac4Devices d={0}; Ac4Bootstrap b={0};
    c->ee_memory_map=1; c->memory_base=0; c->device_state=&d;
    c->device_read=ac4_device_read; c->device_write=ac4_device_write;
    int result=ac4_bootstrap_run(c,&b,budget);
    c->gpr[24][0]=b.interrupt_heads[0][2]; c->gpr[25][0]=b.interrupt_handlers[0][1].next;
    c->gpr[26][0]=b.interrupt_handlers[0][2].next; c->gpr[27][0]=d.intc_mask;
    c->gpr[28][0]=d.sif0_waiting; c->gpr[29][0]=d.dma[5].chcr;
    return result;
}
'''
    return native(program,registers=registers,extra_source=HEADER+DEVICES+wrapper,
                  run_function='interrupt_run',paged=True)


class InterruptServiceTests(unittest.TestCase):
    def test_sif_software_register_storage_is_separate_from_hardware(self):
        result=service({0:12,4:0x0040402d,8:0x2403007a,12:12,16:13},
                       {3:121,4:0x80000000,5:0x81234560})
        self.assertEqual((result['status'],result['r'][8],result['r'][2]),(1,0,0xffffffff81234560))
        result=service({0:12,4:13},{3:122,4:4})
        self.assertEqual((result['status'],result['r'][2]),(1,0))

    def test_unknown_sif_software_slot_is_not_a_fake_zero_register(self):
        result=service({0:12,4:13},{3:122,4:0x80000003})
        self.assertEqual((result['status'],result['pc']),(33,0))

    def test_handler_insertion_before_existing_and_at_front(self):
        result=service({0:12,4:0x24050084,8:12,12:0x24060001,16:0x24050088,20:12,24:13},
                       {3:16,4:2,5:128,6:0})
        self.assertEqual((result['status'],result['r'][2]),(1,3))
        self.assertEqual(result['r'][24:27],[2,3,1])

    def test_handler_removal_and_bad_address(self):
        result=service({0:12,4:0x24050001,8:0x24030011,12:12,16:13},{3:16,4:2,5:128})
        self.assertEqual((result['status'],result['r'][2],result['r'][24]),(1,0,0))
        result=service({0:12,4:13},{3:16,4:2,5:129})
        self.assertEqual((result['r'][2],result['r'][24]),(0xffffffffffffffff,0))

    def test_enable_reports_transition_without_toggling_an_enabled_mask_again(self):
        result=service({0:12,4:0x0040402d,8:12,12:0x0040482d,
                        16:0x24030015,20:12,24:13},{3:20,4:2})
        self.assertEqual((result['r'][8],result['r'][9],result['r'][2],result['r'][27]),(1,0,1,0))

    def test_set_dchain_arms_real_device_state_but_does_not_complete_it(self):
        result=service({0:12,4:13},{3:120})
        self.assertEqual((result['status'],result['r'][28],result['r'][29]),(1,1,0x184))


if __name__=='__main__':
    unittest.main()
