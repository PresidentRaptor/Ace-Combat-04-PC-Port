"""128-bit logical/copy semantics, source aliases and immutable zero."""
import unittest
from test_codegen import native


def mmi(rs,rt,rd,selector,group):
    return 0x70000000|(rs<<21)|(rt<<16)|(rd<<11)|(selector<<6)|group


def halves(lanes,bits):
    raw=b''.join(value.to_bytes(bits//8,'little') for value in lanes)
    return int.from_bytes(raw[:8],'little'),int.from_bytes(raw[8:],'little')


class PackedCodegenTests(unittest.TestCase):
    def test_wrapping_arithmetic_keeps_carries_inside_each_lane(self):
        for bits,add,sub in ((8,8,9),(16,4,5),(32,0,1)):
            mask=(1<<bits)-1; sign=1<<(bits-1); repeat=128//bits//4
            a=halves([mask,0,sign,sign-1]*repeat,bits)
            b=halves([1,1,sign,sign]*repeat,bits)
            result=native({0:mmi(2,3,8,add,8),4:mmi(2,3,2,sub,8),8:13},
                          registers={2:a[0],3:b[0]},upper={2:a[1],3:b[1]})
            self.assertEqual((result['r'][8],result['upper'][8]),halves([0,1,0,mask]*repeat,bits))
            self.assertEqual((result['r'][2],result['upper'][2]),halves([mask-1,mask,0,mask]*repeat,bits))

    def test_comparisons_produce_full_lane_masks_and_use_signed_order(self):
        for bits,equal,greater in ((8,10,10),(16,6,6),(32,2,2)):
            mask=(1<<bits)-1; sign=1<<(bits-1); repeat=128//bits//4
            a=halves([mask,0,sign,sign-1]*repeat,bits)
            b=halves([0,0,sign-1,sign]*repeat,bits)
            result=native({0:mmi(2,3,8,equal,40),4:mmi(2,3,9,greater,8),8:13},
                          registers={2:a[0],3:b[0]},upper={2:a[1],3:b[1]})
            self.assertEqual((result['r'][8],result['upper'][8]),halves([0,mask,0,0]*repeat,bits))
            self.assertEqual((result['r'][9],result['upper'][9]),halves([0,0,0,mask]*repeat,bits))

    def test_signed_minimum_maximum_include_negative_extremes(self):
        for bits,selector in ((16,7),(32,3)):
            mask=(1<<bits)-1; sign=1<<(bits-1); repeat=128//bits//4
            a=halves([mask,0,sign,sign-1]*repeat,bits)
            b=halves([0,0,sign-1,sign]*repeat,bits)
            result=native({0:mmi(2,3,8,selector,40),4:mmi(2,3,9,selector,8),8:13},
                          registers={2:a[0],3:b[0]},upper={2:a[1],3:b[1]})
            self.assertEqual((result['r'][8],result['upper'][8]),halves([mask,0,sign,sign]*repeat,bits))
            self.assertEqual((result['r'][9],result['upper'][9]),halves([0,0,sign-1,sign-1]*repeat,bits))

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
