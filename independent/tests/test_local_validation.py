"""The local-check mechanism must detect wrong architectural expectations."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_ac4 import check_case, check_operation


class LocalCheckTests(unittest.TestCase):
    def test_operation_check_rejects_wrong_register_and_flow(self):
        words = {0: 0x40026000, 4: 0}
        self.assertTrue(check_operation(words, 0, 'mfc0', {'rt': 2, 'cop0': 12})['passed'])
        with self.assertRaises(ValueError):
            check_operation(words, 0, 'mfc0', {'rt': 3, 'cop0': 12})
        with self.assertRaises(ValueError):
            check_operation({0: 0x42000018}, 0, 'eret', {})

    def test_backward_branch_and_slot_checked(self):
        words = {0x2000: 0x1480ffff, 0x2004: 0x24420001}
        result = check_case(words, 0x2000, 'bne', 0x2000, 'addiu')
        self.assertTrue(result['passed'])
        for name, target, slot in (('beq', 0x2000, 'addiu'),
                                    ('bne', 0x2004, 'addiu'),
                                    ('bne', 0x2000, 'ori')):
            with self.subTest(name=name, target=target, slot=slot):
                with self.assertRaises(ValueError):
                    check_case(words, 0x2000, name, target, slot)

    def test_likely_branch_and_unresolved_return(self):
        self.assertTrue(check_case({0: 0x50800003, 4: 0}, 0, 'beql', 16, 'sll')['passed'])
        result = check_case({0: 0x03e00008, 4: 0}, 0, 'jr', None, 'sll')
        self.assertIsNone(result['target'])
        with self.assertRaises(ValueError):
            check_case({0: 0x00800008, 4: 0}, 0, 'jr', None, 'sll')


if __name__ == '__main__':
    unittest.main()
