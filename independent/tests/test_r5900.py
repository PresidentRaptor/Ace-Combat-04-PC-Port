"""Hand-encoded scalar cases and small architectural control-flow scenarios.

All bytes are synthetic; expected destinations/effects are calculated separately
from decoder tables. These are not AC4 compatibility or execution-oracle tests.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ac4_image
from ac4_image import ImageError
from r5900 import DecodeError, decode
from r5900_analysis import analyze, executable_words, inventory, stream_words


class DecoderTests(unittest.TestCase):
    def test_known_scalar_operands(self):
        # Common synthetic prologue: addiu sp,sp,-32; sw ra,28(sp); addu v0,a0,a1
        for word, name, operands in [
            (0x27bdffe0, 'addiu', {'rt': 29, 'rs': 29, 'immediate': -32}),
            (0xafbf001c, 'sw', {'rt': 31, 'base': 29, 'offset': 28}),
            (0x00851021, 'addu', {'rd': 2, 'rs': 4, 'rt': 5}),
            (0x8fa2fff8, 'lw', {'rt': 2, 'base': 29, 'offset': -8}),
            (0x3c028000, 'lui', {'rt': 2, 'immediate': 32768}),
            (0x3442ffff, 'ori', {'rt': 2, 'rs': 2, 'immediate': 65535}),
            (0x2c82ffff, 'sltiu', {'rt': 2, 'rs': 4, 'immediate': -1}),
            (0x000217fc, 'dsll32', {'rd': 2, 'rt': 2, 'shift': 63}),
            (0x00851018, 'mult', {'rd': 2, 'rs': 4, 'rt': 5}),
            (0x0085001b, 'divu', {'rs': 4, 'rt': 5}),
        ]:
            with self.subTest(word=hex(word)):
                ins = decode(word, 0x1000)
                self.assertEqual((ins.mnemonic, ins.operands), (name, operands))
                self.assertFalse(ins.has_delay_slot)

    def test_signed_immediate_extremes_and_zero_extension(self):
        self.assertEqual(decode(0x24828000, 0).operands['immediate'], -32768)
        self.assertEqual(decode(0x24827fff, 0).operands['immediate'], 32767)
        self.assertEqual(decode(0x30828000, 0).operands['immediate'], 32768)
        self.assertEqual(decode(0xdc82ffff, 0).operands['offset'], -1)

    def test_backward_branch_and_branch_limits(self):
        # At 0x1008, bne a0,zero,-3 returns to 0x1000, not 0xffc.
        self.assertEqual(decode(0x1480fffd, 0x1008).target, 0x1000)
        self.assertEqual(decode(0x10858000, 0x20000).target, 4)
        self.assertEqual(decode(0x10857fff, 0x20000).target, 0x40000)
        self.assertEqual(decode(0x1085fffe, 0).target, 0xfffffffc)
        self.assertEqual(decode(0x10850000, 0xfffffffc).target, 0)

    def test_jump_region_and_link_wrap(self):
        self.assertEqual(decode(0x08000003, 0x0ffffffc).target, 0x1000000c)
        self.assertEqual(decode(0x08000003, 0x0ffffff8).target, 12)
        ins = decode(0x0c000003, 0xfffffffc)
        self.assertEqual((ins.target, ins.link_address, ins.link_register), (12, 4, 31))
        self.assertEqual(decode(0x0c000003, 0xfffffff8).link_address, 0)

    def test_register_calls_and_return_shapes(self):
        ins = decode(0x0320f809, 0x1000)  # jalr ra,t9
        self.assertEqual((ins.flow, ins.target, ins.link_register, ins.link_address),
                         ('call', None, 31, 0x1008))
        custom = decode(0x03208009, 0x1000)
        self.assertEqual(custom.link_register, 16)
        discard = decode(0x03200009, 0x1000)
        self.assertEqual(discard.flow, 'indirect')
        self.assertIsNone(discard.link_register)
        self.assertEqual(decode(0x03e00008, 0).flow, 'return')
        self.assertEqual(decode(0x03200008, 0).flow, 'indirect')

    def test_link_branch_likely_metadata_is_unconditional_link(self):
        # bgezall a0,-1. Link is written even if the condition is false.
        ins = decode(0x0493ffff, 0xfffffffc)
        self.assertEqual((ins.mnemonic, ins.target, ins.link_address), ('bgezall', 0xfffffffc, 4))
        self.assertTrue(ins.likely)
        self.assertEqual(ins.link_register, 31)

    def test_reserved_fields_and_undefined_aliases(self):
        for word in [0x00200000, 0x00851061, 0x03e10008, 0x03e00808,
                     0x0320f849, 0x0085081a, 0x00201010, 0x00810011,
                     0x18210000, 0x3c220000, 0x0020000f,
                     0x03e0f809, 0x07f00000]:
            with self.subTest(word=hex(word)), self.assertRaises(DecodeError):
                decode(word, 0)

    def test_unsupported_groups_never_become_nops(self):
        # COP0 (including ERET), FPU branch, COP2, MMI, LQ, CACHE, reserved op.
        for word in [0x42000018, 0x45010001, 0x48000000, 0x70000000,
                     0x78000000, 0xbc000000, 0xc0000001]:
            with self.subTest(word=hex(word)), self.assertRaises(DecodeError):
                decode(word, 0)
        self.assertEqual(decode(0, 0).mnemonic, 'sll')

    def test_code_fields_are_not_reserved(self):
        self.assertEqual(decode(0x0001234c, 0).operands['code'], 0x48d)
        self.assertEqual(decode(0x0085fff4, 0).operands['code'], 1023)
        self.assertEqual(decode(0x000007cf, 0).operands['stype'], 31)
        self.assertEqual(decode(0x0489ffff, 0).operands['immediate'], -1)

    def test_input_validation(self):
        for word, pc in [(-1, 0), (1 << 32, 0), (0, -4), (0, 2), (0, 1 << 32)]:
            with self.subTest(word=word, pc=pc), self.assertRaises(DecodeError):
                decode(word, pc)


class AnalysisTests(unittest.TestCase):
    def test_taken_untaken_likely_annulment_has_observable_effect(self):
        # beq[l] a0,a1,+2; addiu v0,zero,7; break; break.
        # Project graph paths into a tiny trace oracle: writing v0 in the slot
        # must occur on both ordinary outcomes, only on the likely taken path.
        for branch, expected in [(0x10850002, (7, 7)), (0x50850002, (7, 0))]:
            graph = analyze({0: branch, 4: 0x24020007, 8: 13, 12: 13}, [0])
            for taken, want in zip((True, False), expected):
                path = next(e for e in graph.edges if e.source == 0 and
                            e.condition == ('taken' if taken else 'untaken'))
                register = 0
                trace = [0]
                if path.slot_effect == 'executed':
                    trace.append(path.delay_slot)
                    # Independent effect of the hand-encoded addiu in this scenario.
                    register = 7
                trace.append(path.target)
                self.assertEqual(register, want)
                self.assertEqual(trace[-1], 12 if taken else 8)
                self.assertEqual(4 in trace, taken or branch == 0x10850002)
            self.assertNotIn(4, graph.visited)  # slot is contextual, not ordinary flow

    def test_indirect_call_continuation_and_return_remain_unresolved(self):
        graph = analyze({0: 0x0320f809, 4: 0, 8: 0x03e00008, 12: 0}, [0])
        self.assertTrue(any(e.kind == 'call' and e.target is None and e.delay_slot == 4 for e in graph.edges))
        self.assertTrue(any(e.kind == 'continuation' and e.target == 8 and
                            e.condition == 'if-callee-returns' for e in graph.edges))
        self.assertTrue(any(e.kind == 'return' and e.target is None and e.delay_slot == 12 for e in graph.edges))
        self.assertFalse(any(e.source == 8 and e.target == 16 for e in graph.edges))

    def test_other_branch_path_survives_first_return(self):
        graph = analyze({0: 0x10850003, 4: 0, 8: 0x03e00008, 12: 0,
                         16: 0x03e00008, 20: 0}, [0])
        self.assertEqual({e.source for e in graph.edges if e.kind == 'return'}, {8, 16})

    def test_direct_call_visits_callee_and_possible_return_site(self):
        graph = analyze({0: 0x0c000004, 4: 0, 8: 13, 16: 0x03e00008, 20: 0}, [0])
        self.assertIn(16, graph.visited)
        self.assertIn(8, graph.visited)
        self.assertEqual(next(e.target for e in graph.edges if e.kind == 'call'), 16)
        # Direct unconditional jump has no fabricated continuation.
        graph = analyze({0: 0x08000004, 4: 0, 8: 13, 16: 13}, [0])
        self.assertNotIn(8, graph.visited)
        self.assertFalse(any(e.kind == 'continuation' for e in graph.edges))

    def test_missing_or_unsupported_slot_blocks_only_executed_paths(self):
        for slot in [None, 0x48000000, 0x08000000, 0x0000000f]:
            for branch in [0x10850002, 0x50850002]:
                words = {0: branch, 8: 13, 12: 13}
                if slot is not None:
                    words[4] = slot
                graph = analyze(words, [0])
                taken = next(e for e in graph.edges if e.source == 0 and e.condition == 'taken')
                untaken = next(e for e in graph.edges if e.source == 0 and e.condition == 'untaken')
                self.assertFalse(taken.traversable)
                self.assertEqual(taken.target, 12)  # retained even when path is blocked
                self.assertEqual(untaken.traversable, branch == 0x50850002)
                self.assertTrue(graph.diagnostics)

    def test_slot_address_can_also_be_independent_entry(self):
        graph = analyze({0: 0x08000002, 4: 0x24020007, 8: 13}, [0, 4])
        self.assertIn(4, graph.visited)
        self.assertTrue(any(e.source == 4 and e.target == 8 for e in graph.edges))

    def test_loop_terminates_and_address_wrap_preserves_slot(self):
        graph = analyze({0xfffffffc: 0x1000ffff, 0: 0}, [0xfffffffc])
        branch = next(e for e in graph.edges if e.condition == 'taken')
        self.assertEqual((branch.target, branch.delay_slot), (0xfffffffc, 0))
        self.assertLessEqual(len(graph.visited), 3)

    def test_explicit_exception_and_conditional_trap(self):
        graph = analyze({0: 0x00850034, 4: 12, 8: 0}, [0])
        self.assertTrue(any(e.source == 0 and e.kind == 'exception' and e.target is None for e in graph.edges))
        self.assertIn(4, graph.visited)
        self.assertNotIn(8, graph.visited)
        graph = analyze({0: 0x50850002, 4: 12, 8: 13, 12: 13}, [0])
        self.assertIn(8, graph.visited)  # annulled syscall doesn't trap
        self.assertNotIn(12, graph.visited)
        self.assertTrue(any(e.kind == 'exception' and e.delay_slot == 4 for e in graph.edges))

    def test_out_of_range_and_unsupported_targets_are_diagnostic(self):
        graph = analyze({0: 0x08000004, 4: 0}, [0, 8])
        self.assertTrue(any(e.target == 16 for e in graph.edges))
        self.assertEqual({d['pc'] for d in graph.diagnostics}, {8, 16})
        graph = analyze({0: 0x48000000, 4: 13}, [0])
        self.assertEqual(graph.visited, [0])
        self.assertFalse(graph.edges)
        self.assertTrue(graph.diagnostics)

    def test_stream_and_analysis_validation(self):
        self.assertEqual(stream_words(b'\x08\x00\xe0\x03', 0x1000), {0x1000: 0x03e00008})
        for data, base in [(b'\x00', 0), (bytes(4), 2), (bytes(8), 0xfffffffc)]:
            with self.assertRaises(ValueError):
                stream_words(data, base)
        for words, entries in [({2: 0}, [0]), ({0: -1}, [0]), ({0: 0}, [2])]:
            with self.assertRaises(ValueError):
                analyze(words, entries)
        with self.assertRaises(ImageError):
            executable_words(b'synthetic, not an AC4 executable')

    def test_verified_elf_adapter_excludes_nonexecute_and_zero_fill(self):
        # Test-only identity constants for an independently constructed ELF.
        # Production acceptance still requires the unchanged AC4 hash and size.
        data = bytearray(0x208)
        ident = b'\x7fELF\x01\x01\x01' + bytes(9)
        ac4_image.HEADER.pack_into(data, 0, ident, 2, 8, 1, 0x1000,
                                  52, 0, 0, 52, 32, 2, 0, 0, 0)
        ac4_image.PROGRAM.pack_into(data, 52, 1, 0x100, 0x1000, 0x1000, 8, 16, 5, 0x100)
        ac4_image.PROGRAM.pack_into(data, 84, 1, 0x200, 0x2000, 0x2000, 8, 8, 6, 0x100)
        data[0x100:0x108] = bytes.fromhex('0800e00300000000')
        with self.assertRaises(ImageError):
            executable_words(data)
        with patch.object(ac4_image, 'AC4_SIZE', len(data)), patch.object(
                ac4_image, 'AC4_SHA256', hashlib.sha256(data).hexdigest()):
            words, entry, metadata = executable_words(data)
        self.assertEqual(words, {0x1000: 0x03e00008, 0x1004: 0})
        self.assertEqual(entry, 0x1000)
        self.assertTrue(metadata['supported_ac4'])  # synthetic identity, not AC4 evidence
        self.assertEqual(analyze(words, [entry]).edges[0].kind, 'return')

    def test_link_branch_outcomes_and_indirect_discarded_link(self):
        graph = analyze({0: 0x04930003, 4: 0, 8: 13, 16: 13}, [0])
        outcomes = [e for e in graph.edges if e.source == 0]
        self.assertTrue(any(e.kind == 'call' and e.target == 16 and e.slot_effect == 'executed'
                            for e in outcomes))
        self.assertTrue(any(e.condition == 'untaken' and e.target == 8 and e.slot_effect == 'annulled'
                            for e in outcomes))
        self.assertEqual(graph.instructions[0].link_address, 8)
        graph = analyze({0: 0x03200009, 4: 0, 8: 13}, [0])
        self.assertEqual(len(graph.edges), 1)
        self.assertEqual((graph.edges[0].kind, graph.edges[0].target), ('indirect', None))
        self.assertNotIn(8, graph.visited)

    def test_inventory_reports_rejections_without_claiming_code_coverage(self):
        counts = inventory({0: 0, 4: 0x03e00008, 8: 0x48000000})
        self.assertEqual(counts['candidate_words'], 3)
        self.assertEqual(sum(counts['decoded'].values()), 2)
        self.assertEqual(sum(counts['rejected'].values()), 1)

    def test_cli_synthetic_and_summary(self):
        script = Path(__file__).resolve().parents[1] / 'r5900_analysis.py'
        command = [sys.executable, '-B', str(script), '--words', '03e00008', '00000000']
        full = subprocess.run(command, check=True, capture_output=True, text=True)
        result = json.loads(full.stdout)
        self.assertEqual(result['analysis']['edges'][0]['kind'], 'return')
        self.assertEqual(result['reachability']['unresolved_register_edges'], 1)
        summary = subprocess.run(command + ['--summary'], check=True, capture_output=True, text=True)
        self.assertNotIn('analysis', json.loads(summary.stdout))
        invalid = subprocess.run(command[:-2] + ['100000000'], capture_output=True, text=True)
        self.assertNotEqual(invalid.returncode, 0)


if __name__ == '__main__':
    unittest.main()
