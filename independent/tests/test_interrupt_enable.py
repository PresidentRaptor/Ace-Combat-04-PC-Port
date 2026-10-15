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
