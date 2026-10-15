"""Bounded selection never implies successful services or unsupported execution."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from r5900_codegen import bounded_plan,emit_program,TranslationError
from build_bootstrap import output_path,copied_code_words,extend_fetch_plan
from test_ac4_image import fixture


class PlanTests(unittest.TestCase):
    def test_fetch_discovery_preserves_previous_selection_and_bounds_growth(self):
        initial={0:13}
        available={0:13,16:0,20:0,24:13}
        extended,report=extend_fetch_plan(available,initial,dict(status=3,pc=16,steps=7),limit=2)
        self.assertEqual(initial,{0:13})
        self.assertEqual(extended,{0:13,16:0,20:0})
        self.assertEqual(report['fetch_pc'],'0x00000010')
        self.assertEqual(report['added_addresses'],2)
        self.assertIsNone(extend_fetch_plan(available,extended,dict(status=3,pc=16)))

    def test_fetch_discovery_rejects_unknown_modified_and_nonfetch_boundaries(self):
        for observation in (dict(status=3,pc=32),dict(status=12,pc=16),dict(status=10,pc=16),
                            dict(status=3,pc='16'),dict(status=3,pc=True)):
            with self.subTest(observation=observation):
                self.assertIsNone(extend_fetch_plan({0:13,16:0},{0:13},observation))
        self.assertIsNone(extend_fetch_plan({0:13,16:1},{0:13},dict(status=3,pc=16)))

    def test_discovered_unsupported_opcode_remains_explicit_stop(self):
        extended,report=extend_fetch_plan({0:13,16:0x40024800},{0:13},dict(status=3,pc=16))
        self.assertEqual(extended[16],0x40024800)
        self.assertIn('return AC4_UNSUPPORTED;',emit_program(extended,0,stop_unsupported=True))
        self.assertTrue(report['plan']['boundaries'])

    def test_copied_code_uses_file_backing_at_relocated_pc(self):
        words,metadata=copied_code_words(bytes(fixture()),[(0x1000,0x80076000,4)])
        self.assertEqual(words,{0x80076000:0x04030201})
        self.assertEqual(metadata[0]['destination'],'0x80076000')

    def test_copied_code_rejects_bss_overlaps_and_invalid_ranges(self):
        for regions in ([(0x1004,0x80076000,4)],[(0x1000,0x80076001,4)],
                        [(0x1000,0xfffffffc,8)],[(0x1000,0x80076000,0)],
                        [(0x1000,0x80076000,4),(0x1000,0x80076000,4)]):
            with self.subTest(regions=regions):
                with self.assertRaises(ValueError):
                    copied_code_words(bytes(fixture()),regions)
    def test_syscall_resume_is_opt_in_selection_only(self):
        words={0:12,4:0,8:13}
        self.assertEqual(set(bounded_plan(words,[0])[0]),{0})
        selected,report=bounded_plan(words,[0],resume_syscalls=True)
        self.assertEqual(set(selected),{0,4,8})
        self.assertTrue(report['syscall_continuations_selected'])

    def test_limit_and_unmapped_entries_remain_boundaries(self):
        selected,report=bounded_plan({0:0,4:0,8:13},[0,16],limit=1)
        self.assertEqual(set(selected),{0})
        self.assertGreater(report['pending_addresses'],0)
        _,report=bounded_plan({0:13},[16])
        self.assertEqual(report['boundaries'][0]['address'],'0x00000010')
        with self.assertRaises(TranslationError):
            bounded_plan({},[0],limit=0)

    def test_indirect_target_is_not_guessed(self):
        selected,_=bounded_plan({0:0x00800008,4:0,8:13,16:13},[0])
        self.assertNotIn(16,selected)

    def test_explicit_unsupported_mode_stops_instead_of_nop(self):
        words={0:0x40024800}
        with self.assertRaises(TranslationError):
            emit_program(words,0)
        self.assertIn('return AC4_UNSUPPORTED;',emit_program(words,0,stop_unsupported=True))
        selected,report=bounded_plan(words,[0])
        self.assertEqual(set(selected),{0})
        self.assertIn('mfc0',report['boundaries'][0]['reason'])

    def test_game_derived_output_rejects_repository_and_existing_directory(self):
        with self.assertRaisesRegex(ValueError,'outside'):
            output_path(Path(__file__).resolve().parents[1]/'generated-game-build')
        with self.assertRaises(ValueError):
            output_path(Path(__file__).resolve().parents[2].parent)


if __name__=='__main__':
    unittest.main()
