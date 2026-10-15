"""EE address windows and test-only device callbacks, not hardware timing."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_codegen import native

WRAPPER = '''
int bus_run(Ac4Cpu *c, uint64_t budget) {
    c->ee_memory_map=1;
    return ac4_run(c,budget);
}
'''


class MemoryBusTests(unittest.TestCase):
    def test_cached_and_uncached_ram_aliases_share_storage(self):
        for address in (0x1000,0x20001000,0x80001000,0xa0001000):
            result=native({0:0xac820000,4:0x8ca30000,8:13},
                          registers={4:address,5:0x1000,2:0x12345678},
                          extra_source=WRAPPER,run_function='bus_run')
            self.assertEqual((result['status'],result['r'][3]),(1,0x12345678))
            self.assertEqual(result['memory'][:4],[0x78,0x56,0x34,0x12])

    def test_accelerated_alias_does_not_map_reserved_lower_megabyte(self):
        result=native({0:0x8c820000,4:13},registers={4:0x30001000},
                      extra_source=WRAPPER,run_function='bus_run')
        self.assertEqual(result['status'],5)

    def test_scratchpad_quadword_is_separate_and_preserves_both_halves(self):
        result=native({0:0x7c82000f,4:0x78830007,8:13},
                      registers={4:0x70000000,2:0x123456789abcdef0},upper={2:0xfedcba9876543210},
                      extra_source=WRAPPER,run_function='bus_run')
        self.assertEqual((result['r'][3],result['upper'][3]),
                         (0x123456789abcdef0,0xfedcba9876543210))
        self.assertEqual(result['memory'],[0]*256)

    def test_scratchpad_end_does_not_wrap_into_start(self):
        result=native({0:0xa0820000,4:0x90830001,8:13},
                      registers={4:0x70003fff,2:42},extra_source=WRAPPER,run_function='bus_run')
        self.assertEqual((result['status'],result['pc'],result['r'][3]),(5,4,0))

    def test_unknown_device_does_not_read_zero_or_report_success(self):
        result=native({0:0x8c820000,4:13},registers={4:0x10001810,2:99},
                      extra_source=WRAPPER,run_function='bus_run')
        self.assertEqual((result['status'],result['pc'],result['r'][2]),(11,0,99))

    def test_device_callback_receives_physical_address_and_alignment_is_checked(self):
        source='''
static int test_read(void *state,uint32_t address,unsigned bytes,uint64_t *low,uint64_t *high) {
    (*(unsigned *)state)++;
    if (address!=0x10001810 || bytes!=4) return AC4_DEVICE;
    *low=0x89abcdef; *high=0; return 0;
}
int bus_run(Ac4Cpu *c,uint64_t budget) {
    unsigned calls=0; c->ee_memory_map=1;
    c->device_state=&calls; c->device_read=test_read;
    int result=ac4_run(c,budget); c->gpr[20][0]=calls; return result;
}
'''
        result=native({0:0x8c820000,4:13},registers={4:0xb0001810},
                      extra_source=source,run_function='bus_run')
        self.assertEqual((result['status'],result['r'][2],result['r'][20]),
                         (1,0xffffffff89abcdef,1))
        result=native({0:0x8c820000,4:13},registers={4:0x10001811},
                      extra_source=source,run_function='bus_run')
        self.assertEqual((result['status'],result['r'][20]),(4,0))


if __name__=='__main__':
    unittest.main()
