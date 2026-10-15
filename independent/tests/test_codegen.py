"""Compile generated scalar C and check independently calculated guest outcomes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from r5900_codegen import emit_program, TranslationError


def compiler():
    configured = os.environ.get('AC4_TEST_CC')
    found = configured or shutil.which('cc') or shutil.which('gcc') or 'C:/msys64/ucrt64/bin/gcc.exe'
    return shutil.which(found) or (found if Path(found).is_file() else None)


def native(words, *, registers=None, upper=None, memory=None, limit=100, entry=0, resume=None, memory_size=256,
           extra_source='', run_function='ac4_run'):
    cc = compiler()
    if cc is None:
        if os.environ.get('AC4_REQUIRE_NATIVE_TESTS') == '1':
            raise AssertionError('native C compiler required; set AC4_TEST_CC')
        raise unittest.SkipTest('native C compiler required; set AC4_TEST_CC')
    initial = ''.join(f'c.gpr[{r}][0]=UINT64_C({value & ((1 << 64)-1)});' for r, value in (registers or {}).items())
    initial += ''.join(f'c.gpr[{r}][1]=UINT64_C({value & ((1 << 64)-1)});' for r, value in (upper or {}).items())
    initial += ''.join(f'memory[{i}]={value};' for i, value in (memory or {}).items())
    driver = r'''
#include <stdio.h>
#include <inttypes.h>
int main(void) {
    unsigned char memory[256]={0}; Ac4Cpu c={0};
    c.memory=memory; c.memory_base=0x1000; c.memory_size=MEMORY_SIZE;
    INITIAL
    c.pc=ENTRY;
    int result=RUN_FUNCTION(&c,LIMIT);
    RESUME
    printf("{\"status\":%d,\"pc\":%u,\"steps\":%" PRIu64 ",\"fault_pc\":%u,\"delay\":%u,\"r\":[",result,c.pc,c.steps,c.fault_pc,c.fault_delay);
    for (int i=0;i<32;i++) printf("%s%" PRIu64,i ? "," : "",c.gpr[i][0]);
    printf("],\"upper\":[");
    for (int i=0;i<32;i++) printf("%s%" PRIu64,i ? "," : "",c.gpr[i][1]);
    printf("],\"memory\":[");
    for (int i=0;i<256;i++) printf("%s%u",i ? "," : "",(unsigned)memory[i]);
    printf("]}"); return 0;
}
'''.replace('INITIAL', initial).replace('ENTRY', str(entry)).replace('LIMIT', str(limit)).replace('MEMORY_SIZE', str(memory_size)).replace('RUN_FUNCTION', run_function).replace(
        'RESUME', '' if resume is None else f'if (result!=AC4_BUDGET) {{ return 2; }} result=ac4_run(&c,{resume});')
    environment = dict(os.environ)
    environment['PATH'] = str(Path(cc).parent) + os.pathsep + environment.get('PATH', '')
    with tempfile.TemporaryDirectory(prefix='ac4-independent-') as folder:
        source, exe = Path(folder) / 'program.c', Path(folder) / ('program.exe' if os.name == 'nt' else 'program')
        source.write_text(emit_program(words, entry) + extra_source + driver, encoding='utf-8')
        build = subprocess.run([cc, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(exe)],
                               capture_output=True, text=True, env=environment)
        if build.returncode:
            raise AssertionError(build.stderr)
        result = subprocess.run([str(exe)], check=True, capture_output=True, text=True,
                                timeout=5, env=environment)
        return json.loads(result.stdout)


class CodegenTests(unittest.TestCase):
    def test_changed_instruction_bytes_stop_instead_of_running_stale_translation(self):
        words={0x1000:0xac820000,0x1004:13}
        raw=b''.join(word.to_bytes(4,'little') for word in words.values())
        wrapper='''
int checked_run(Ac4Cpu *c,uint64_t budget) {
    c->verify_instruction_bytes=1;
    return ac4_run(c,budget);
}
'''
        result=native(words,registers={4:0x1004,2:0},entry=0x1000,memory=dict(enumerate(raw)),
                      extra_source=wrapper,run_function='checked_run')
        self.assertEqual((result['status'],result['pc']),(12,0x1004))

    def test_unaligned_word_loads_each_lane_preserve_merge_bits(self):
        for op, expected in ((0x22, (0x11bbccdd, 0x2211ccdd, 0x332211dd, 0x44332211)),
                              (0x26, (0x44332211, 0xaa443322, 0xaabb4433, 0xaabbcc44))):
            words = {lane*4: (op<<26)|(4<<21)|((8+lane)<<16)|lane for lane in range(4)}
            words[16] = 13
            result = native(words, registers={4: 0x1000, **{r: 0xaabbccdd for r in range(8,12)}},
                            memory=dict(enumerate((0x11, 0x22, 0x33, 0x44))))
            self.assertEqual(result['r'][8:12], [v if v<0x80000000 else v|0xffffffff00000000 for v in expected])

    def test_unaligned_load_pairs_all_offsets_both_orders(self):
        for width, left, right in ((4, 0x22, 0x26), (8, 0x1a, 0x1b)):
            for reverse in (False, True):
                words = {}
                for lane in range(width):
                    pair = [(left, lane+width-1), (right, lane)]
                    if reverse:
                        pair.reverse()
                    for op, offset in pair:
                        words[len(words)*4] = (op<<26)|(4<<21)|((8+lane)<<16)|offset
                words[len(words)*4] = 13
                data = bytes(range(0x81, 0x91))
                result = native(words, registers={4: 0x1000}, upper={r: 99 for r in range(8,16)},
                                memory=dict(enumerate(data)))
                for lane in range(width):
                    expected = int.from_bytes(data[lane:lane+width], 'little', signed=width==4) & ((1<<64)-1)
                    self.assertEqual((result['r'][8+lane], result['upper'][8+lane]), (expected, 99))

    def test_unaligned_store_pairs_all_offsets_preserve_neighbors(self):
        value = 0x8877665544332211
        for width, left, right in ((4, 0x2a, 0x2e), (8, 0x2c, 0x2d)):
            words, expected = {}, bytearray([0xa5]*256)
            for lane in range(width):
                offset = 16+lane*16+lane
                for op, immediate in ((left, offset+width-1), (right, offset)):
                    words[len(words)*4] = (op<<26)|(4<<21)|(2<<16)|immediate
                expected[offset:offset+width] = value.to_bytes(8,'little')[:width]
            words[len(words)*4] = 13
            result = native(words, registers={4: 0x1000, 2: value}, memory={i: 0xa5 for i in range(256)})
            self.assertEqual(result['memory'], list(expected))

    def test_merge_access_checks_only_selected_bytes_and_zero_destination(self):
        # LWL at lane zero needs only byte zero, not an entire word.
        result = native({0: 0x88820000, 4: 13}, registers={4: 0x1000, 2: 0x12345678},
                        memory={0: 0xfe}, memory_size=1)
        self.assertEqual((result['status'], result['r'][2]), (1, 0xfffffffffe345678))
        result = native({0: 0x98800000, 4: 13}, registers={4: 0x1000}, memory_size=1)
        self.assertEqual((result['status'], result['r'][0]), (5, 0))

    def test_merge_store_fault_does_not_partially_write(self):
        result = native({0: 0xb4820000, 4: 13}, registers={4: 0x1000, 2: -1},
                        memory={i: 0xa5 for i in range(8)}, memory_size=3)
        self.assertEqual(result['status'], 5)
        self.assertEqual(result['memory'][:8], [0xa5]*8)

    def test_word_wrap_sign_extension_and_upper_preservation(self):
        result = native({0: 0x24420001, 4: 13}, registers={2: 0x7fffffff}, upper={2: 99})
        self.assertEqual(result['r'][2], 0xffffffff80000000)
        self.assertEqual(result['upper'][2], 99)
        self.assertEqual(result['status'], 1)

    def test_trapping_add_does_not_write_destination(self):
        result = native({0: 0x20420001, 4: 13}, registers={2: 0x7fffffff})
        self.assertEqual((result['status'], result['r'][2]), (7, 0x7fffffff))

    def test_branch_condition_sampled_before_delay_slot_write(self):
        # BEQ a0,zero targets 16; slot makes a0 nonzero, which cannot undo it.
        result = native({0: 0x10800003, 4: 0x24840001, 8: 0x24020063,
                         12: 13, 16: 0x24020007, 20: 13})
        self.assertEqual((result['r'][2], result['r'][4]), (7, 1))

    def test_untaken_likely_annuls_faulting_memory_access(self):
        result = native({0: 0x50800002, 4: 0x8c020001, 8: 13, 12: 13}, registers={4: 1})
        self.assertEqual((result['status'], result['steps']), (1, 2))

    def test_jalr_target_precedes_link_and_source_overwrite(self):
        result = native({0: 0x0320f809, 4: 0x24190014, 16: 13}, registers={25: 16})
        self.assertEqual((result['pc'], result['r'][31], result['r'][25]), (16, 8, 20))

    def test_fault_in_delay_slot_records_branch_site(self):
        result = native({0: 0x08000004, 4: 0x8c020001, 16: 13})
        self.assertEqual((result['status'], result['fault_pc'], result['delay']), (4, 0, 1))

    def test_little_endian_store_and_signed_byte_load(self):
        result = native({0: 0xac820000, 4: 0x80830003, 8: 13},
                        registers={4: 0x1000, 2: 0x89abcdef})
        self.assertEqual(result['memory'][:4], [0xef, 0xcd, 0xab, 0x89])
        self.assertEqual(result['r'][3], 0xffffffffffffff89)

    def test_quadword_masks_address_and_copies_both_halves(self):
        result = native({0: 0x7c82000f, 4: 0x78830007, 8: 13},
                        registers={4: 0x1000, 2: 0x0123456789abcdef},
                        upper={2: 0xfedcba9876543210})
        self.assertEqual((result['r'][3], result['upper'][3]),
                         (0x0123456789abcdef, 0xfedcba9876543210))

    def test_load_to_zero_still_checks_memory_and_zero_is_immutable(self):
        result = native({0: 0x8c000000, 4: 13}, registers={0: 123}, upper={0: 456})
        self.assertEqual((result['status'], result['r'][0], result['upper'][0]), (5, 0, 0))

    def test_unsigned_signed_comparison_and_arithmetic_shift(self):
        result = native({0: 0x0043202a, 4: 0x0043282b, 8: 0x0002303b, 12: 13},
                        registers={2: 0xffffffffffffffff, 3: 1})
        self.assertEqual((result['r'][4], result['r'][5], result['r'][6]), (1, 0, 0xffffffffffffffff))

    def test_infinite_loop_is_bounded(self):
        result = native({0: 0x08000000, 4: 0}, limit=9)
        self.assertEqual((result['status'], result['steps'], result['pc']), (8, 9, 4))

    def test_budget_resume_preserves_pending_delay_slot(self):
        result = native({0: 0x08000004, 4: 0x24020007, 16: 13}, limit=1, resume=10)
        self.assertEqual((result['status'], result['r'][2], result['pc'], result['steps']), (1, 7, 16, 3))

    def test_control_or_sync_in_executed_slot_stops(self):
        for slot in (0x08000004, 0x0000000f):
            with self.subTest(slot=slot):
                result = native({0: 0x08000004, 4: slot, 16: 13})
                self.assertEqual((result['status'], result['fault_pc'], result['delay']), (6, 0, 1))

    def test_discarded_arithmetic_still_compiles_and_checks_overflow(self):
        result = native({0: 0x24400001, 4: 0x20400001}, registers={2: 0x7fffffff})
        self.assertEqual((result['status'], result['r'][0]), (7, 0))

    def test_link_on_untaken_branch_is_visible_to_delay_slot(self):
        # BGEZAL a0,+2; ADDU v0,ra,zero; BREAK
        result = native({0: 0x04910002, 4: 0x03e01021, 8: 13, 12: 13},
                        registers={4: 0xffffffffffffffff})
        self.assertEqual((result['r'][31], result['r'][2], result['pc']), (8, 8, 8))

    def test_multiply_accumulate_wrap_and_independent_hilo_banks(self):
        # MULT v0,a0,a1; MULTU1 v1,a2,a3; MADD zero,a2,a3;
        # MFLO t0; MFHI t1; MFLO1 t2; MFHI1 t3
        result = native({0: 0x00851018, 4: 0x70c71819, 8: 0x70c70000,
                         12: 0x00004012, 16: 0x00004810,
                         20: 0x70005012, 24: 0x70005810, 28: 13},
                        registers={4: 0xfffffffffffffffe, 5: 3,
                                   6: 0xffffffffffffffff, 7: 0xffffffffffffffff})
        self.assertEqual(result['r'][2], 0xfffffffffffffffa)
        self.assertEqual(result['r'][3], 1)
        self.assertEqual(result['r'][8:12], [0xfffffffffffffffb, 0xffffffffffffffff,
                                          1, 0xfffffffffffffffe])

    def test_division_sign_remainder_overflow_and_unsigned_bank(self):
        for left, right, quotient, remainder in ((-7, 3, -2, -1), (7, -3, -2, 1),
                                                 (-7, -3, 2, -1), (-2147483648, -1, -2147483648, 0)):
            with self.subTest(left=left, right=right):
                result = native({0: 0x0085001a, 4: 0x00001012, 8: 0x00001810, 12: 13},
                                registers={4: left, 5: right})
                self.assertEqual(result['r'][2:4], [quotient & ((1 << 64)-1), remainder & ((1 << 64)-1)])
        result = native({0: 0x7085001b, 4: 0x70001012, 8: 0x70001810, 12: 13},
                        registers={4: -1, 5: 2})
        self.assertEqual(result['r'][2:4], [0x7fffffff, 1])

    def test_undefined_multiply_division_inputs_stop_without_guest_exception(self):
        for word, registers in ((0x0085001a, {4: 7, 5: 0}),
                                (0x00850018, {4: 0xffffffff, 5: 1})):
            with self.subTest(word=word):
                result = native({0: word, 4: 13}, registers=registers)
                self.assertEqual((result['status'], result['pc']), (9, 0))

    def test_unsupported_operations_fail_generation(self):
        with self.assertRaisesRegex(TranslationError, 'unsupported operation'):
            emit_program({0: 0x4be21928}, 0)

    def test_generated_output_is_deterministic(self):
        self.assertEqual(emit_program({4: 13, 0: 0}, 0), emit_program({0: 0, 4: 13}, 0))


if __name__ == '__main__':
    unittest.main()
