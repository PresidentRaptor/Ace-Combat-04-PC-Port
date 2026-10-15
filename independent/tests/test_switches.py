"""A recovered table must have a matching guard, scale, mapping and destinations."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from r5900_switches import match_switch


def fixture():
    # Synthetic switch with three entries at 0x2000; case addresses 0x40/44/48.
    words = {}
    encoded = (0x2c820003, 0x1040001e, 0x3c030000, 0x00042080,
               0x24632000, 0x00832021, 0x8c850000, 0x00a00008, 0)
    words.update({index * 4: word for index, word in enumerate(encoded)})
    words.update({0x40: 13, 0x44: 13, 0x48: 13, 0x80: 13})
    raw = b''.join(target.to_bytes(4, 'little') for target in (0x40, 0x44, 0x48))
    return words, raw


class SwitchTests(unittest.TestCase):
    def test_bound_not_sentinel_controls_table_length(self):
        words, raw = fixture()
        requests = []

        def reader(address, size):
            requests.append((address, size))
            return raw

        candidate = match_switch(words, 28, reader)
        self.assertIsNotNone(candidate)
        self.assertEqual(requests, [(0x2000, 12)])
        self.assertEqual(candidate.targets, (0x40, 0x44, 0x48))
        self.assertEqual(candidate.default_target, 0x80)

    def test_wrong_guard_or_scale_does_not_guess_a_table(self):
        words, raw = fixture()
        for address, replacement in ((0, 0x2c820000), (0, 0x2c840003), (4, 0x1440001e),
                                       (12, 0x000420c0), (20, 0x00842021),
                                       (24, 0x8c860000), (32, 0x03e00008)):
            changed = dict(words)
            changed[address] = replacement
            with self.subTest(address=address):
                self.assertIsNone(match_switch(changed, 28, lambda *_: raw))

    def test_external_entry_inside_guarded_sequence_is_rejected(self):
        words, raw = fixture()
        self.assertIsNone(match_switch(words, 28, lambda *_: raw, {12}))
        self.assertIsNotNone(match_switch(words, 28, lambda *_: raw, {0, 0x80}))

    def test_mutable_truncated_and_invalid_targets_rejected(self):
        words, raw = fixture()
        for data in (None, raw[:-1], b'\xfc\0\0\0' * 3,
                     (0x41).to_bytes(4, 'little') * 3,
                     (0x100).to_bytes(4, 'little') * 3):
            with self.subTest(data=data):
                self.assertIsNone(match_switch(words, 28, lambda *_: data))

    def test_duplicate_cases_are_preserved(self):
        words, _ = fixture()
        candidate = match_switch(words, 28, lambda *_: (0x40).to_bytes(4, 'little') * 3)
        self.assertEqual(candidate.targets, (0x40, 0x40, 0x40))


if __name__ == '__main__':
    unittest.main()
