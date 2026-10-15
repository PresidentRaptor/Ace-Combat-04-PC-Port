"""128-bit logical/copy semantics, source aliases and immutable zero."""
import unittest
from test_codegen import native


def mmi(rs,rt,rd,selector,group):
    return 0x70000000|(rs<<21)|(rt<<16)|(rd<<11)|(selector<<6)|group


class PackedCodegenTests(unittest.TestCase):
    def test_logical_operations_write_both_halves(self):
        operations=((18,9),(18,41),(19,9),(19,41))
        program={i*4:mmi(2,3,8+i,selector,group) for i,(selector,group) in enumerate(operations)}
        program[16]=13
        result=native(program,registers={2:0xff00,3:0x0ff0},upper={2:0x1234,3:0x00ff})
        self.assertEqual(result['r'][8:12],[0x0f00,0xfff0,0xf0f0,0xffffffffffff000f])
        self.assertEqual(result['upper'][8:12],[0x34,0x12ff,0x12cb,0xffffffffffffed00])

    def test_copy_halves_sample_sources_before_alias_write(self):
        result=native({0:mmi(2,3,2,14,9),4:mmi(2,3,3,14,41),8:13},
                      registers={2:11,3:22},upper={2:33,3:44})
        self.assertEqual((result['r'][2],result['upper'][2]),(22,11))
        self.assertEqual((result['r'][3],result['upper'][3]),(11,44))
        result=native({0:mmi(0,2,2,27,41),4:13},registers={2:0x12345678},upper={2:0xabcdef01})
        self.assertEqual((result['r'][2],result['upper'][2]),(0x5678567856785678,0xef01ef01ef01ef01))

    def test_packed_destination_zero_discards_both_halves(self):
        result=native({0:mmi(2,3,0,18,41),4:13},registers={2:-1,3:-1},upper={2:-1,3:-1})
        self.assertEqual((result['status'],result['r'][0],result['upper'][0]),(1,0,0))


if __name__=='__main__':
    unittest.main()
