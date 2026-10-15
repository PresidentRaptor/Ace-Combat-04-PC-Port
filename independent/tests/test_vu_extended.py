"""Architectural operand roles and fixed-field checks for extended macros."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from r5900 import decode, DecodeError
from r5900_analysis import analyze


def macro(group, variant, mask=15, fs=3, ft=2):
    return 0x4a00003c | (mask << 21) | (ft << 16) | (fs << 11) | (group << 6) | variant


class ExtendedVuTests(unittest.TestCase):
    def test_accumulator_has_no_destination_vf(self):
        ins = decode(macro(2, 2), 0)
        self.assertEqual((ins.mnemonic, ins.operands),
                         ('vmaddaz', {'vfs': 3, 'vft': 2, 'dest_mask': 15}))
        self.assertEqual(decode(macro(10, 2), 0).mnemonic, 'vmula')
        self.assertEqual(decode(macro(7, 0, ft=0), 0).mnemonic, 'vmulaq')
        with self.assertRaises(DecodeError):
            decode(macro(7, 0, ft=1), 0)

    def test_conversion_and_move_write_ft_not_selector_field(self):
        for group, variant, name in ((4, 3, 'vitof15'), (5, 2, 'vftoi12'),
                                      (7, 1, 'vabs'), (12, 0, 'vmove'), (12, 1, 'vmr32')):
            with self.subTest(name=name):
                ins = decode(macro(group, variant, mask=8), 0)
                self.assertEqual((ins.mnemonic, ins.operands),
                                 (name, {'vft': 2, 'vfs': 3, 'dest_mask': 8}))

    def test_division_components_are_not_a_destination_mask(self):
        ins = decode(macro(14, 0, mask=9), 0)
        self.assertEqual(ins.operands, {'vfs': 3, 'vft': 2,
                                      'fs_component': 1, 'ft_component': 2})
        sqrt = decode(macro(14, 1, mask=12, fs=0), 0)
        self.assertEqual(sqrt.operands, {'vft': 2, 'ft_component': 3})
        with self.assertRaises(DecodeError):
            decode(macro(14, 1, mask=13, fs=0), 0)
        with self.assertRaises(DecodeError):
            decode(macro(14, 1, mask=12, fs=1), 0)

    def test_load_store_integer_and_vector_roles_are_distinct(self):
        load = decode(macro(13, 0, fs=4, ft=31), 0)
        store = decode(macro(13, 3, fs=31, ft=4), 0)
        self.assertEqual(load.operands, {'vft': 31, 'vis': 4, 'dest_mask': 15})
        self.assertEqual(store.operands, {'vfs': 31, 'vit': 4, 'dest_mask': 15})
        with self.assertRaises(DecodeError):
            decode(macro(13, 0, fs=16), 0)
        self.assertEqual(decode(macro(15, 0, mask=3), 0).operands,
                         {'vit': 2, 'vfs': 3, 'fs_component': 3})

    def test_wait_and_nop_require_their_exact_fixed_fields(self):
        nop, wait = macro(11, 3, mask=0, fs=0, ft=0), macro(14, 3, mask=0, fs=0, ft=0)
        self.assertEqual(decode(nop, 0).mnemonic, 'vnop')
        self.assertEqual(decode(wait, 0).mnemonic, 'vwaitq')
        graph = analyze({0: wait, 4: nop, 8: 13}, [0])
        self.assertEqual(graph.visited, [0, 4, 8])
        for word in (nop | (1 << 11), wait | (1 << 21), macro(10, 3), macro(17, 0)):
            with self.subTest(word=word), self.assertRaises(DecodeError):
                decode(word, 0)

    def test_random_source_component_and_fixed_register(self):
        self.assertEqual(decode(macro(16, 2, mask=2, ft=0), 0).operands,
                         {'vfs': 3, 'fs_component': 2})
        self.assertEqual(decode(macro(16, 0, fs=0), 0).operands,
                         {'vft': 2, 'dest_mask': 15})
        for word in (macro(16, 2, mask=4, ft=0), macro(16, 0, fs=1),
                     macro(7, 3, mask=15), macro(11, 2, mask=15)):
            with self.subTest(word=word), self.assertRaises(DecodeError):
                decode(word, 0)


class CacheAndSelectorTests(unittest.TestCase):
    def test_ee_cache_operations_and_signed_address_offset(self):
        self.assertEqual(decode(0xbc98fff0, 0).mnemonic, 'cache.dhwbin')
        self.assertEqual(decode(0xbc8bfff0, 0).operands, {'base': 4, 'offset': -16})
        for operation in (3, 8, 9, 13, 15, 31):
            with self.subTest(operation=operation), self.assertRaises(DecodeError):
                decode(0xbc800000 | (operation << 16), 0)

    def test_debug_selectors_do_not_alias_generic_transfers(self):
        self.assertEqual(decode(0x4002c004, 0).mnemonic, 'mfdab')
        self.assertEqual(decode(0x4082c007, 0).mnemonic, 'mtdvbm')
        for selector in (1, 8, 0x400):
            with self.subTest(selector=selector), self.assertRaises(DecodeError):
                decode(0x4002c000 | selector, 0)

    def test_performance_counter_and_control_are_separate(self):
        self.assertEqual(decode(0x4002c800, 0).mnemonic, 'mfps')
        self.assertEqual(decode(0x4002c803, 0).operands, {'rt': 2, 'counter': 1})
        self.assertEqual(decode(0x4082c801, 0).mnemonic, 'mtpc')
        for selector in (2, 5, 0x40):
            with self.subTest(selector=selector), self.assertRaises(DecodeError):
                decode(0x4002c800 | selector, 0)


if __name__ == '__main__':
    unittest.main()
