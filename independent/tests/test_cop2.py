"""VU transfer and CPU-branch encodings from Sony VU macro-mode formats."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from r5900 import DecodeError, decode
from r5900_analysis import analyze


class Cop2Tests(unittest.TestCase):
    def test_quadword_memory_is_vf_not_cpu_register(self):
        ins = decode(0xd885fff0, 0)
        self.assertEqual((ins.mnemonic, ins.operands),
                         ('lqc2', {'vft': 5, 'base': 4, 'offset': -16}))
        self.assertEqual(decode(0xf885fff0, 0).mnemonic, 'sqc2')

    def test_interlock_bit_is_not_a_reserved_bit(self):
        for word, name, register in ((0x48221800, 'qmfc2', 'vfd'),
                                      (0x48a21800, 'qmtc2', 'vfd'),
                                      (0x48421800, 'cfc2', 'vi'),
                                      (0x48c21800, 'ctc2', 'vi')):
            with self.subTest(name=name):
                first, second = decode(word, 0), decode(word | 1, 0)
                self.assertEqual(first.mnemonic, name)
                self.assertEqual(first.operands, {'rt': 2, register: 3, 'interlock': 0})
                self.assertEqual(second.operands['interlock'], 1)
                with self.assertRaises(DecodeError):
                    decode(word | 2, 0)

    def test_all_vu_cpu_branches_preserve_target_and_likely_effect(self):
        for kind, name in enumerate(('bc2f', 'bc2t', 'bc2fl', 'bc2tl')):
            word = 0x4900ffff | (kind << 16)
            ins = decode(word, 0x1000)
            self.assertEqual((ins.mnemonic, ins.target, ins.likely),
                             (name, 0x1000, kind >= 2))
            graph = analyze({0x1000: word, 0x1004: 0, 0x1008: 13}, [0x1000])
            untaken = next(e for e in graph.edges if e.source == 0x1000 and e.condition == 'untaken')
            self.assertEqual(untaken.slot_effect, 'annulled' if kind >= 2 else 'executed')
        for word in (0x49040000, 0x48000000, 0x4a000033):
            with self.assertRaises(DecodeError):
                decode(word, 0)

    def test_vector_masks_broadcasts_and_scalar_register_restriction(self):
        vector = decode(0x4be21928, 0)
        self.assertEqual((vector.mnemonic, vector.operands),
                         ('vadd', {'vfd': 4, 'vfs': 3, 'vft': 2, 'dest_mask': 15}))
        broadcast = decode(0x4b02191b, 0)
        self.assertEqual((broadcast.mnemonic, broadcast.operands['dest_mask']), ('vmulw', 8))
        self.assertEqual(decode(0x4b001922, 0).mnemonic, 'vaddi')
        with self.assertRaises(DecodeError):
            decode(0x4b021922, 0)
        self.assertEqual(decode(0x4bc2192e, 0).mnemonic, 'vopmsub')
        with self.assertRaises(DecodeError):
            decode(0x4be2192e, 0)

    def test_integer_immediate_is_signed_and_register_namespace_is_vi(self):
        ins = decode(0x4a021ff2, 0)
        self.assertEqual((ins.mnemonic, ins.operands),
                         ('viaddi', {'vit': 2, 'vis': 3, 'immediate': -1}))
        with self.assertRaises(DecodeError):
            decode(0x4a221830, 0)
        with self.assertRaises(DecodeError):
            decode(0x4b021830, 0)

    def test_micro_call_does_not_redirect_cpu_or_create_a_delay_slot(self):
        ins = decode(0x4a000178, 0x1000)
        self.assertEqual((ins.mnemonic, ins.operands),
                         ('vcallms', {'immediate': 5, 'micro_address': 40}))
        self.assertEqual(ins.flow, 'normal')
        self.assertIsNone(ins.target)
        graph = analyze({0: 0x4a000039, 4: 13}, [0])
        self.assertEqual(graph.edges[0].target, 4)
        self.assertIsNone(graph.edges[0].delay_slot)
        with self.assertRaises(DecodeError):
            decode(0x4a000079, 0)


if __name__ == '__main__':
    unittest.main()
