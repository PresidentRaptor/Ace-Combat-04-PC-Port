"""Conservative target proofs must survive joins, calls, aliases and slot writes."""
from pathlib import Path
import json
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from r5900 import decode
from r5900_constants import UNKNOWN, resolve_indirects, transfer


class ConstantTests(unittest.TestCase):
    def test_cli_reports_constants_without_emitting_game_words(self):
        script = Path(__file__).resolve().parents[1] / 'r5900_analysis.py'
        command = [sys.executable, '-B', str(script), '--base', '0', '--words',
                   '24190010', '03200008', '00000000', '--summary', '--resolve-indirects']
        output = json.loads(subprocess.run(command, check=True, capture_output=True, text=True).stdout)
        self.assertEqual(output['indirect_resolution']['constant_targets'], 1)
        self.assertEqual(output['indirect_resolution']['targets'][0]['target'], 16)
        self.assertNotIn('analysis', output)

    def test_lui_addiu_sign_extension_and_zero_register(self):
        state = transfer(decode(0x3c198000, 0), UNKNOWN)
        self.assertEqual(state[25], 0xffffffff80000000)
        state = transfer(decode(0x2739fff0, 4), state)
        self.assertEqual(state[25], 0x7ffffff0)
        self.assertEqual(transfer(decode(0x24000001, 8), state)[0], 0)

    def test_indirect_target_sampled_before_delay_slot_overwrites_source(self):
        words = {0: 0x24190010, 4: 0x03200008, 8: 0x24190014, 16: 13}
        target, = resolve_indirects(words, [0])
        self.assertEqual((target.source, target.target), (4, 16))

    def test_jalr_link_and_slot_cannot_change_sampled_destination(self):
        words = {0: 0x24190020, 4: 0x0320f809, 8: 0x24190024, 12: 13, 32: 13}
        target, = resolve_indirects(words, [0])
        self.assertEqual(target.target, 32)

    def test_join_keeps_only_agreeing_values(self):
        words = {0: 0x10800005, 4: 0, 8: 0x24190040, 12: 0x08000008,
                 16: 0, 24: 0x24190044, 28: 0, 32: 0x03200008, 36: 0}
        target, = resolve_indirects(words, [0])
        self.assertIsNone(target.target)
        words[24] = words[8]
        target, = resolve_indirects(words, [0])
        self.assertEqual(target.target, 64)

    def test_calls_discard_abi_assumptions_on_continuation(self):
        words = {0: 0x24190040, 4: 0x0c000008, 8: 0, 12: 0x03200008,
                 16: 0, 32: 0x03e00008, 36: 0}
        targets = {t.source: t for t in resolve_indirects(words, [0])}
        self.assertIsNone(targets[12].target)
        self.assertEqual(targets[32].target, 12)
        # An independent callee entry removes the caller-only RA assumption.
        targets = {t.source: t for t in resolve_indirects(words, [0, 32])}
        self.assertIsNone(targets[32].target)

    def test_loads_and_coprocessor_transfers_kill_destination_facts(self):
        for word in (0x8c190000, 0x44190000, 0x48390000):
            words = {0: 0x24190040, 4: word, 8: 0x03200008, 12: 0}
            with self.subTest(word=word):
                self.assertIsNone(resolve_indirects(words, [0])[0].target)

    def test_likely_annulment_does_not_apply_taken_slot_to_untaken_path(self):
        words = {0: 0x24190040, 4: 0x50800004, 8: 0x24190044,
                 12: 0x03200008, 16: 0, 24: 0x03200008, 28: 0}
        targets = {t.source: t.target for t in resolve_indirects(words, [0])}
        self.assertEqual(targets, {12: 64, 24: 68})

    def test_unknown_instruction_effects_do_not_preserve_stale_targets(self):
        # DIV has no modelled destination; clearing facts is deliberately safe.
        words = {0: 0x24190040, 4: 0x0085001a, 8: 0x03200008, 12: 0}
        self.assertIsNone(resolve_indirects(words, [0])[0].target)

    def test_unaligned_target_remains_unresolved(self):
        target, = resolve_indirects({0: 0x24190041, 4: 0x03200008, 8: 0}, [0])
        self.assertEqual(target.status, 'unaligned-address')
        self.assertIsNone(target.target)

    def test_loops_lose_changing_constants_and_terminate(self):
        words = {0: 0x24190040, 4: 0x27390004, 8: 0x1480fffe, 12: 0,
                 16: 0x03200008, 20: 0}
        target, = resolve_indirects(words, [0])
        self.assertIsNone(target.target)


if __name__ == '__main__':
    unittest.main()
