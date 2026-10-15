"""Raw COP1 transfers/branches and context preservation; no FPU arithmetic."""
import unittest
from test_codegen import native
from test_threads import scheduled
from r5900_codegen import emit_program,TranslationError


def execute(program,*,enabled=True,condition=0,**kwargs):
    wrapper=f'''
int fp_run(Ac4Cpu *c,uint64_t budget) {{
    c->cp0_status={0x20000000 if enabled else 0}; c->fcr31={condition};
    int result=ac4_run(c,budget); c->gpr[22][0]=c->fpr[0]; c->gpr[23][0]=c->fcr31;
    return result;
}}
'''
    return native(program,extra_source=wrapper,run_function='fp_run',**kwargs)


class FpuTransferTests(unittest.TestCase):
    def test_gpr_move_preserves_all_bits_including_non_arithmetic_patterns(self):
        for value in (0x80000000,0x7fc01234,0x00000001):
            result=execute({0:0x44820000,4:0x46000046,8:0x44030800,12:13},
                           registers={2:value},upper={3:99},paged=True)
            expected=value if value<0x80000000 else value|0xffffffff00000000
            self.assertEqual((result['r'][3],result['upper'][3]),(expected,99))

    def test_fpu_memory_transfer_is_little_endian_bit_copy(self):
        result=execute({0:0xc4800000,4:0xe4800004,8:0x44020000,12:13},
                       registers={4:0x1000},memory={3:0x80})
        self.assertEqual(result['r'][2],0xffffffff80000000)
        self.assertEqual(result['memory'][:8],[0,0,0,0x80,0,0,0,0x80])

    def test_control_transfer_and_likely_annulment(self):
        result=execute({0:0x44c2f800,4:0x4443f800,8:13},registers={2:0xffffffff80800000})
        self.assertEqual(result['r'][3],0xffffffff80800000)
        result=execute({0:0x45030002,4:0x8c020001,8:13,12:13})
        self.assertEqual((result['status'],result['pc'],result['steps']),(1,8,2))

    def test_branch_condition_precedes_delay_slot_control_write(self):
        result=execute({0:0x45010003,4:0x44c2f800,8:0x24020063,12:13,
                        16:0x24020007,20:13},condition=0x800000)
        self.assertEqual((result['r'][2],result['r'][23]),(7,0))

    def test_disabled_coprocessor_stops_before_memory_access_or_zero_write(self):
        for word in (0xc4800001,0x44000000):
            result=execute({0:word,4:13},enabled=False,registers={4:0})
            self.assertEqual((result['status'],result['pc']),(13,0))
        with self.assertRaises(TranslationError):
            emit_program({0:0x44420000},0)  # Unknown FCR0 revision remains unsupported.

    def test_thread_switch_preserves_fpr_and_control_state(self):
        program={0:12,4:0x44020000,8:0x4443f800,12:13,
                 128:0x44800000,132:0x44c0f800,136:0x24040001,140:0x24030033,144:12,148:13}
        result=scheduled(program,registers={3:50},extra='''
c->cp0_status=0x20000000; c->fpr[0]=0x3f800000; c->fcr31=0x800000;
b.threads[1].context.cp0_status=0x20000000;
''')
        self.assertEqual((result['status'],result['r'][2],result['r'][3]),(1,0x3f800000,0x800000))
        self.assertEqual(result['r'][25],2)


if __name__=='__main__':
    unittest.main()
