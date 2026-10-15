"""Synthetic EE-specific and FPU encoding/flow regressions, not execution tests."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from r5900 import DecodeError, decode
from r5900_analysis import analyze


class ExtensionTests(unittest.TestCase):
    def test_quadword_prologue_and_epilogue(self):
        store = decode(0x7fbffff0, 0x1000)
        load = decode(0x7bbffff0, 0x1010)
        self.assertEqual(store.mnemonic, 'sq')
        self.assertEqual(load.mnemonic, 'lq')
        self.assertEqual(store.operands, {'rt': 31, 'base': 29, 'offset': -16})
        graph = analyze({0x1000: 0x7fbffff0, 0x1004: 0x03e00008,
                         0x1008: 0x7bbffff0}, [0x1000])
        self.assertFalse(graph.diagnostics)
        self.assertEqual(graph.edges[-1].kind, 'return')
        self.assertEqual(graph.edges[-1].slot_effect, 'executed')

    def test_shift_amount_register_forms(self):
        self.assertEqual(decode(0x00001028, 0).operands, {'rd': 2})
        self.assertEqual(decode(0x00800029, 0).operands, {'rs': 4})
        self.assertEqual(decode(0x0498ffff, 0).mnemonic, 'mtsab')
        self.assertEqual(decode(0x04990007, 0).operands, {'rs': 4, 'immediate': 7})
        for word in (0x00201028, 0x00810029):
            with self.assertRaises(DecodeError):
                decode(word, 0)

    def test_fpu_memory_has_separate_register_namespace(self):
        self.assertEqual(decode(0xc484fff8, 0).operands,
                         {'ft': 4, 'base': 4, 'offset': -8})
        self.assertEqual(decode(0xe484fff8, 0).mnemonic, 'swc1')

    def test_fpu_transfers_and_control_registers(self):
        for word, name, registers in (
            (0x44021800, 'mfc1', {'rt': 2, 'fs': 3}),
            (0x44821800, 'mtc1', {'rt': 2, 'fs': 3}),
            (0x4442f800, 'cfc1', {'rt': 2, 'fcr': 31}),
            (0x44c2f800, 'ctc1', {'rt': 2, 'fcr': 31}),
        ):
            with self.subTest(name=name):
                ins = decode(word, 0)
                self.assertEqual((ins.mnemonic, ins.operands), (name, registers))
        self.assertEqual(decode(0x44420000, 0).operands['fcr'], 0)
        for word in (0x44021801, 0x44420800, 0x44c20000):
            with self.assertRaises(DecodeError):
                decode(word, 0)

    def test_fpu_unary_source_and_accumulator_distinction(self):
        # ADD.S f4,f3,f2; SQRT.S f4,f2; NEG.S f4,f3; MULA.S f3,f2.
        self.assertEqual(decode(0x46021900, 0).operands, {'fd': 4, 'fs': 3, 'ft': 2})
        sqrt = decode(0x46020104, 0)
        self.assertEqual((sqrt.mnemonic, sqrt.operands), ('sqrt.s', {'fd': 4, 'ft': 2}))
        self.assertEqual(decode(0x46001907, 0).operands, {'fd': 4, 'fs': 3})
        self.assertEqual(decode(0x4602181a, 0).operands, {'fs': 3, 'ft': 2})
        for word in (0x46021904, 0x46021907, 0x4602191a, 0x46021932):
            with self.assertRaises(DecodeError):
                decode(word, 0)

    def test_only_ee_formats_and_comparisons_accepted(self):
        self.assertEqual(decode(0x46021832, 0).mnemonic, 'c.eq.s')
        self.assertEqual(decode(0x46001924, 0).mnemonic, 'cvt.w.s')
        self.assertEqual(decode(0x46801920, 0).mnemonic, 'cvt.s.w')
        for word in (0x46221900, 0x46001920, 0x46021831, 0x46821920):
            with self.assertRaises(DecodeError):
                decode(word, 0)

    def test_fp_likely_branch_annuls_unsupported_slot_on_untaken_path(self):
        # BC1TL with offset -1 returns to itself on the taken path.
        ins = decode(0x4503ffff, 0x1000)
        self.assertEqual((ins.mnemonic, ins.target, ins.likely), ('bc1tl', 0x1000, True))
        graph = analyze({0x1000: 0x4503ffff, 0x1004: 0x48000000,
                         0x1008: 0x0000000d}, [0x1000])
        taken, untaken = graph.edges[:2]
        self.assertFalse(taken.traversable)
        self.assertTrue(untaken.traversable)
        self.assertEqual(untaken.slot_effect, 'annulled')
        self.assertIn(0x1008, graph.visited)
        for word in (0x45040000, 0x45080000):
            with self.assertRaises(DecodeError):
                decode(word, 0)


if __name__ == '__main__':
    unittest.main()
