"""Experimental startup policy and explicit boundary checks, not BIOS accuracy."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_codegen import native

HEADER = (Path(__file__).resolve().parents[1] / 'bootstrap_services.h').read_text()
WRAPPER = r'''
int test_boot(Ac4Cpu *c, uint64_t budget) {
    c->memory_base=0;
    Ac4Bootstrap bootstrap={0};
    int status=ac4_bootstrap_run(c,&bootstrap,budget);
    c->gpr[16][0]=bootstrap.calls;
    c->gpr[17][0]=bootstrap.stack_pointer;
    c->gpr[18][0]=bootstrap.heap_end;
    c->gpr[19][0]=bootstrap.last_number;
    c->gpr[20][0]=bootstrap.semaphores[0].count;
    c->gpr[21][0]=bootstrap.semaphores[0].maximum;
    c->gpr[22][0]=bootstrap.call_depth;
    c->gpr[23][0]=bootstrap.timer3_handler;
    c->gpr[24][0]=bootstrap.current_thread;
    c->gpr[25][0]=bootstrap.context_switches;
    return status;
}
'''


def run(words, registers=None, *, guest_overrides=False, **kwargs):
    wrapper=WRAPPER.replace('Ac4Bootstrap bootstrap={0};',
                            f'Ac4Bootstrap bootstrap={{0}}; bootstrap.enable_guest_overrides={int(guest_overrides)};')
    return native(words, registers=registers, extra_source=HEADER+wrapper,
                  run_function='test_boot', **kwargs)


class BootstrapTests(unittest.TestCase):
    def test_guest_override_bridge_returns_to_syscall_continuation_and_restores_ra(self):
        words={0:12,4:0x2403005a,8:12,12:13,32:0x24020007,36:0x03e00008,40:0}
        result=run(words,{3:116,4:90,5:32,31:0x88},guest_overrides=True)
        self.assertEqual((result['status'],result['pc'],result['r'][2],result['r'][31]),(1,12,7,0x88))
        self.assertEqual((result['r'][16],result['r'][22],result['steps']),(2,0,7))
        result=run(words,{3:116,4:90,5:32,31:0x88},guest_overrides=True,limit=6)
        self.assertEqual((result['status'],result['pc'],result['r'][31],result['steps']),(8,12,0x88,6))

    def test_nested_guest_override_calls_preserve_return_frames(self):
        words={0:12,4:0x2404005b,8:0x24050060,12:12,16:0x2403005a,20:12,24:13,
               64:0x2403005b,68:12,72:0x03e00008,76:0,
               96:0x24020009,100:0x03e00008,104:0}
        result=run(words,{3:116,4:90,5:64,31:0x88},guest_overrides=True)
        self.assertEqual((result['status'],result['pc'],result['r'][2],result['r'][31]),(1,24,9,0x88))
        self.assertEqual((result['r'][16],result['r'][22]),(4,0))

    def test_untranslated_guest_handler_stops_with_frame_intact(self):
        result=run({0:12,4:0x2403005a,8:12,12:13},{3:116,4:90,5:0x1000},guest_overrides=True)
        self.assertEqual((result['status'],result['pc'],result['r'][16],result['r'][22]),(3,0x1000,1,1))

    def test_alarm_patch_timer_handler_registration_is_explicit(self):
        result=run({0:12,4:13},{3:116,4:0x12c,5:0x80076000})
        self.assertEqual((result['status'],result['r'][23]),(1,0x80076000))

    def test_create_semaphore_reads_initial_and_maximum_not_count_field(self):
        result=run({0:12,4:0x24040020,8:0x24030040,12:12,16:13},
                   {3:60,5:-1,6:64},memory={32:99,36:5,40:2})
        self.assertEqual((result['status'],result['r'][2],result['r'][16]),(1,1,2))
        self.assertEqual(result['r'][20:22],[2,5])

    def test_create_semaphore_rejects_bad_counts_without_allocating(self):
        result=run({0:12,4:0x24040020,8:0x24030040,12:12,16:13},
                   {3:60,5:-1,6:64},memory={36:1,40:2})
        self.assertEqual((result['r'][2],result['r'][20:22]),(0xffffffffffffffff,[0,0]))

    def test_syscall_override_never_falls_back_to_builtin_service(self):
        # Register a replacement for SetupThread, then call that service.
        result=run({0:12,4:0x2403003c,8:12,12:13},
                   {3:116,4:60,5:0x1000,6:64})
        self.assertEqual((result['status'],result['pc'],result['r'][16]),(37,8,1))

    def test_syscall_patch_registration_checks_index_and_alignment(self):
        for index,address in ((256,0x1000),(90,0x1001),(90,0)):
            result=run({0:12,4:13},{3:116,4:index,5:address})
            self.assertEqual((result['status'],result['r'][16]),(33,0))

    def test_automatic_stack_profile_resumes_and_preserves_upper_gpr(self):
        result = run({0: 12, 4: 0x0040e82d, 8: 13},
                     {3: 60, 4: 0x42, 5: -1, 6: 64}, upper={2: 99})
        self.assertEqual((result['status'], result['r'][29], result['r'][16:18]), (1, 192, [1,192]))
        self.assertEqual(result['upper'][2], 99)

    def test_explicit_stack_returns_top_of_supplied_region(self):
        result = run({0: 12, 4: 13}, {3: 60, 5: 64, 6: 64})
        self.assertEqual((result['r'][2],result['r'][17]), (128,128))

    def test_heap_sentinel_uses_reserved_stack_boundary(self):
        # SetupThread; a0=32; a1=-1; v1=61; SetupHeap; BREAK
        result = run({0: 12, 4: 0x24040020, 8: 0x2405ffff, 12: 0x2403003d,
                      16: 12, 20: 13}, {3: 60, 5: -1, 6: 64})
        self.assertEqual((result['status'], result['r'][16:19]), (1,[2,192,192]))

    def test_heap_before_thread_and_duplicate_setup_stop(self):
        result = run({0: 12, 4: 13}, {3: 61, 4: 32, 5: -1})
        self.assertEqual((result['status'],result['pc'],result['r'][16]), (34,0,0))
        result = run({0: 12, 4: 12, 8: 13}, {3: 60, 5: -1, 6: 64})
        self.assertEqual((result['status'],result['pc'],result['r'][16]), (34,4,1))

    def test_invalid_stack_bounds_alignment_and_unknown_service(self):
        for stack,size in ((-1,0), (-1,257), (200,64), (1,64), (-1,63)):
            with self.subTest(stack=stack,size=size):
                result = run({0: 12, 4: 13}, {3: 60, 5: stack, 6: size})
                self.assertEqual((result['status'],result['r'][16]), (33,0))
        result = run({0: 12, 4: 13}, {3: 999})
        self.assertEqual((result['status'],result['pc'],result['r'][16]), (32,0,0))

    def test_syscall_in_delay_slot_is_not_resumed_as_normal_call(self):
        result = run({0: 0x08000004, 4: 12, 16: 13}, {3: 60, 5: -1, 6: 64})
        self.assertEqual((result['status'],result['pc'],result['r'][16]), (35,4,0))

    def test_total_budget_spans_services(self):
        result = run({0: 12, 4: 0, 8: 13}, {3: 60, 5: -1, 6: 64}, limit=1)
        self.assertEqual((result['status'],result['steps'],result['pc']), (8,1,4))


if __name__ == '__main__':
    unittest.main()
