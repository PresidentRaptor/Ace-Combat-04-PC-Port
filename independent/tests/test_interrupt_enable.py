"""EI/DI status changes from the EE instruction manual; no IRQ delivery model."""
import unittest
from test_codegen import native


def execute(status,operation):
    wrapper=f'''
int status_run(Ac4Cpu *c,uint64_t budget) {{
    c->cp0_status=UINT32_C({status});
    int result=ac4_run(c,budget); c->gpr[22][0]=c->cp0_status; return result;
}}
'''
    return native({0:operation,4:13},extra_source=wrapper,run_function='status_run')['r'][22]


class InterruptEnableTests(unittest.TestCase):
    def test_status_transfer_sign_extends_without_changing_upper_gpr_half(self):
        result=native({0:0x40826000,4:0x40036000,8:13},
                      registers={2:0x1234567890010401},upper={3:99},paged=True)
        self.assertEqual((result['status'],result['r'][3],result['upper'][3]),(1,0xffffffff90010401,99))

    def test_status_read_denied_in_user_mode_without_cu0_even_for_zero_destination(self):
        wrapper='''
int checked_status(Ac4Cpu *c,uint64_t budget) {
    c->cp0_status=0x10; return ac4_run(c,budget);
}
'''
        result=native({0:0x40006000,4:13},extra_source=wrapper,run_function='checked_status')
        self.assertEqual((result['status'],result['pc']),(13,0))

    def test_kernel_mode_ei_and_di_only_change_eie(self):
        self.assertEqual(execute(0x401,0x42000038),0x10401)
        self.assertEqual(execute(0x10401,0x42000039),0x401)

    def test_user_mode_without_edi_or_exception_level_has_no_effect(self):
        self.assertEqual(execute(0x10,0x42000038),0x10)
        self.assertEqual(execute(0x10010,0x42000039),0x10010)

    def test_edi_exl_and_erl_allow_user_mode_ei(self):
        for status in (0x20010,0x12,0x14):
            with self.subTest(status=status):
                self.assertEqual(execute(status,0x42000038),status|0x10000)


if __name__=='__main__':
    unittest.main()
