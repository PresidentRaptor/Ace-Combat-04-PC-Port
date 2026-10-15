"""Disabled timer register semantics; active timers must stop explicitly."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_codegen import native

HEADER=(Path(__file__).resolve().parents[1]/'ee_devices.h').read_text()
WRAPPER='''
int timer_run(Ac4Cpu *c,uint64_t budget) {
    Ac4Devices devices={0}; devices.timers[3].mode=0xc00;
    c->ee_memory_map=1; c->device_state=&devices;
    c->device_read=ac4_device_read; c->device_write=ac4_device_write;
    return ac4_run(c,budget);
}
'''


class TimerTests(unittest.TestCase):
    def test_disabled_mode_flags_write_one_to_clear(self):
        result=native({0:0xac820000,4:0x8c830000,8:13},
                      registers={4:0x10001810,2:0x405},
                      extra_source=HEADER+WRAPPER,run_function='timer_run')
        self.assertEqual((result['status'],result['r'][3]),(1,0x805))

    def test_counter_write_truncates_to_sixteen_bits(self):
        result=native({0:0xac820000,4:0x8c830000,8:13},
                      registers={4:0x10001800,2:0x12345678},
                      extra_source=HEADER+WRAPPER,run_function='timer_run')
        self.assertEqual((result['status'],result['r'][3]),(1,0x5678))

    def test_enabling_timer_stops_until_clock_and_interrupt_model_exists(self):
        result=native({0:0xac820000,4:13},registers={4:0x10001810,2:0x80},
                      extra_source=HEADER+WRAPPER,run_function='timer_run')
        self.assertEqual((result['status'],result['pc']),(11,0))

    def test_missing_hold_register_and_wrong_access_width_stop(self):
        for address,word in ((0x10001830,0x8c820000),(0x10001810,0x94820000)):
            with self.subTest(address=address,word=word):
                result=native({0:word,4:13},registers={4:address},
                              extra_source=HEADER+WRAPPER,run_function='timer_run')
                self.assertEqual(result['status'],11)


if __name__=='__main__':
    unittest.main()
