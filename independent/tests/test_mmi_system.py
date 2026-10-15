"""Hand-encoded packed/system forms and control-flow restrictions."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from r5900 import DecodeError, decode
from r5900_analysis import analyze


class PackedTests(unittest.TestCase):
    def test_group_selector_changes_operation_not_register_operands(self):
        for word, name in ((0x70851008, 'paddw'), (0x70851088, 'pcgtw'),
                           (0x708510a8, 'pceqw'), (0x70851489, 'pand'),
                           (0x708514a9, 'por'), (0x708516e8, 'qfsrv')):
            with self.subTest(name=name):
                ins = decode(word, 0)
                self.assertEqual((ins.mnemonic, ins.operands),
                                 (name, {'rd': 2, 'rs': 4, 'rt': 5}))
                self.assertFalse(ins.has_delay_slot)

    def test_unary_shuffle_does_not_read_rs(self):
        self.assertEqual(decode(0x700517c8, 0).mnemonic, 'ppac5')
        self.assertEqual(decode(0x700516c9, 0).operands, {'rd': 2, 'rt': 5})
        with self.assertRaises(DecodeError):
            decode(0x708517c8, 0)

    def test_scalar_secondary_accumulator_forms(self):
        self.assertEqual(decode(0x70851018, 0).mnemonic, 'mult1')
        self.assertEqual(decode(0x7085001b, 0).operands, {'rs': 4, 'rt': 5})
        self.assertEqual(decode(0x70001012, 0).operands, {'rd': 2})
        self.assertEqual(decode(0x70800013, 0).operands, {'rs': 4})
        self.assertEqual(decode(0x70801004, 0).mnemonic, 'plzcw')
        for word in (0x7085101b, 0x70051012, 0x70801013, 0x70851004):
            with self.subTest(word=word), self.assertRaises(DecodeError):
                decode(word, 0)

    def test_packed_hilo_and_format_restrictions(self):
        self.assertEqual(decode(0x70001030, 0).mnemonic, 'pmfhl.lw')
        self.assertEqual(decode(0x700010b0, 0).mnemonic, 'pmfhl.slw')
        self.assertEqual(decode(0x70800031, 0).mnemonic, 'pmthl.lw')
        self.assertEqual(decode(0x70001209, 0).mnemonic, 'pmfhi')
        self.assertEqual(decode(0x70800229, 0).mnemonic, 'pmthi')
        for word in (0x70001170, 0x70801031, 0x70801209, 0x70801229):
            with self.subTest(word=word), self.assertRaises(DecodeError):
                decode(word, 0)

    def test_halfword_shifts_mask_high_shift_bit(self):
        ins = decode(0x700517f4, 0)
        self.assertEqual((ins.mnemonic, ins.operands),
                         ('psllh', {'rd': 2, 'rt': 5, 'shift': 15}))
        self.assertEqual(decode(0x700517fc, 0).operands['shift'], 31)

    def test_reserved_group_slots_and_fixed_fields_rejected(self):
        for word in (0x70000308, 0x700002c8, 0x70000328, 0x70000049,
                     0x70000069, 0x700000a9, 0x70851040):
            with self.subTest(word=word), self.assertRaises(DecodeError):
                decode(word, 0)


class SystemTests(unittest.TestCase):
    def test_basic_cop0_transfer_and_interrupt_controls(self):
        self.assertEqual(decode(0x40026000, 0).operands, {'rt': 2, 'cop0': 12})
        self.assertEqual(decode(0x40826000, 0).mnemonic, 'mtc0')
        self.assertEqual(decode(0x42000038, 0).mnemonic, 'ei')
        self.assertEqual(decode(0x42000039, 0).mnemonic, 'di')
        for word in (0x40026001, 0x42010038, 0x42000818):
            with self.subTest(word=word), self.assertRaises(DecodeError):
                decode(word, 0)

    def test_eret_is_unresolved_without_delay_slot_or_fallthrough(self):
        ins = decode(0x42000018, 0)
        self.assertFalse(ins.has_delay_slot)
        graph = analyze({0: 0x42000018, 4: 0}, [0])
        self.assertEqual(graph.visited, [0])
        self.assertEqual([(e.kind, e.target, e.delay_slot) for e in graph.edges],
                         [('exception-return', None, None)])

    def test_eret_forbidden_in_delay_slot_preserves_likely_annulment(self):
        graph = analyze({0: 0x50800002, 4: 0x42000018, 8: 13, 12: 13}, [0])
        taken, untaken = graph.edges[:2]
        self.assertFalse(taken.traversable)
        self.assertTrue(untaken.traversable)
        self.assertEqual(untaken.slot_effect, 'annulled')

    def test_cop0_likely_branch_target_and_prefetch_hint(self):
        ins = decode(0x4102ffff, 0xfffffffc)
        self.assertEqual((ins.mnemonic, ins.target, ins.likely),
                         ('bc0fl', 0xfffffffc, True))
        pref = decode(0xcc9ffff0, 0)
        self.assertEqual(pref.operands, {'base': 4, 'hint': 31, 'offset': -16})


if __name__ == '__main__':
    unittest.main()
