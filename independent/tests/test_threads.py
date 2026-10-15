"""Cooperative scheduling outcomes; no hardware scheduler equivalence claimed."""
import unittest
from test_bootstrap import run,HEADER
from test_codegen import native


def imm(rt,value,rs=0,op=9):
    return (op<<26)|(rs<<21)|(rt<<16)|(value&0xffff)


def words(sequence,base=0):
    return {base+i*4:word for i,word in enumerate(sequence)}


def descriptor(entry=128,priority=1):
    data={}
    for offset,value in ((36,entry),(40,96),(44,64),(48,0x42),(52,priority)):
        data.update({offset+i:byte for i,byte in enumerate(value.to_bytes(4,'little'))})
    return data


SETUP=[12,imm(4,32),imm(3,32),12,0x0040202d,imm(5,77),imm(3,34),12]
CHILD=words([0xac040040,0xac1c0044,imm(8,7),0x01000011,imm(3,35),12],128)


def scheduled(program, *, extra='', registers=None, **kwargs):
    wrapper='''
int scheduled_run(Ac4Cpu *c,uint64_t budget) {
    c->memory_base=0; Ac4Bootstrap b={0}; b.thread_ready=1; b.current_thread=1;
    b.threads[0].state=1; b.threads[0].priority=0; b.threads[0].order=1;
    b.threads[1].state=2; b.threads[1].priority=1; b.threads[1].order=2;
    b.threads[1].context.pc=128; b.ready_order=2;
    EXTRA
    int status=ac4_bootstrap_run(c,&b,budget);
    c->gpr[24][0]=b.current_thread; c->gpr[25][0]=b.context_switches;
    c->gpr[26][0]=b.threads[0].state; c->gpr[27][0]=b.threads[1].state;
    return status;
}
'''.replace('EXTRA',extra)
    return native(program,registers=registers,extra_source=HEADER+wrapper,
                  run_function='scheduled_run',**kwargs)


class ThreadTests(unittest.TestCase):
    def test_priority_switch_round_trip_preserves_128_bit_gpr_and_hilo(self):
        program=words(SETUP+[imm(4,0),imm(5,2),imm(3,41),12,0x00006010,13])
        program.update(CHILD)
        result=run(program,{3:60,5:-1,6:64,8:0x5555},memory=descriptor(),upper={8:99})
        self.assertEqual(result['status'],1)
        self.assertEqual(result['memory'][64:72],[77,0,0,0,0x42,0,0,0])
        self.assertEqual((result['r'][8],result['upper'][8],result['r'][12]),(0x5555,99,0))
        self.assertEqual(result['r'][24:26],[1,2])

    def test_thread_start_passes_argument_and_sleep_wake_preempts(self):
        program=words(SETUP+[imm(3,50),12,imm(2,7),13])
        program.update(words([0xac040040,imm(4,1),imm(3,51),12,0xac000040,13],128))
        result=run(program,{3:60,5:-1,6:64},memory=descriptor())
        self.assertEqual((result['status'],result['r'][2],result['memory'][64]),(1,7,77))
        self.assertEqual(result['r'][24:26],[1,2])

    def test_wait_semaphore_blocks_then_signal_wakes_higher_priority_thread(self):
        program=words([12,imm(2,7),13])
        program.update(words([imm(4,1),imm(3,66),12,13],128))
        result=scheduled(program,registers={3:68,4:1},
                         extra='b.semaphores[0].active=1; b.semaphores[0].maximum=1;')
        self.assertEqual((result['status'],result['r'][2]),(1,7))
        self.assertEqual(result['r'][24:28],[1,2,1,2])

    def test_equal_priority_rotate_uses_fifo_ready_order(self):
        program=words([12,13])
        program.update(words([imm(2,42),0xac020040,imm(3,35),12],128))
        result=scheduled(program,registers={3:43,4:0},extra='b.threads[1].priority=0;')
        self.assertEqual((result['status'],result['memory'][64]),(1,42))
        self.assertEqual(result['r'][24:26],[1,2])

    def test_no_ready_thread_reports_idle_without_executing_wait_continuation(self):
        result=scheduled(words([12,imm(2,99),13]),registers={3:50},extra='b.threads[1].state=16;')
        self.assertEqual((result['status'],result['pc'],result['steps']),(38,4,1))
        self.assertEqual(result['r'][26],4)

    def test_invalid_thread_descriptor_and_restarting_running_thread_fail(self):
        result=run(words(SETUP[:4]+[13]),{3:60,5:-1,6:64},memory=descriptor(entry=129))
        self.assertEqual(result['r'][2],0xffffffffffffffff)
        result=scheduled(words([12,13]),registers={3:34,4:1})
        self.assertEqual((result['status'],result['r'][2]),(1,0xffffffffffffffff))

    def test_poll_semaphore_does_not_block_and_signal_saturates(self):
        result=scheduled(words([12,13]),registers={3:69,4:1},
                         extra='b.semaphores[0].active=1; b.semaphores[0].maximum=1;')
        self.assertEqual((result['status'],result['r'][2]),(1,0xffffffffffffffff))
        result=scheduled(words([12,13]),registers={3:66,4:1},
                         extra='b.semaphores[0].active=1; b.semaphores[0].maximum=1; b.semaphores[0].count=1;')
        self.assertEqual((result['status'],result['r'][2]),(1,0xffffffffffffffff))

    def test_budget_counts_all_threads_without_resetting_on_switch(self):
        program=words([12,13]); program.update(words([imm(2,5),13],128))
        result=scheduled(program,registers={3:50},limit=2)
        self.assertEqual((result['status'],result['steps'],result['pc']),(8,2,132))
        self.assertEqual(result['r'][24:26],[2,1])

    def test_guest_syscall_return_frames_survive_thread_switches(self):
        program=words([12,13]); program.update(words([imm(3,50),12,0x03e00008,0],64))
        program.update(words([imm(4,1),imm(3,51),12,13],128))
        result=scheduled(program,registers={3:90,31:0x88},
                         extra='b.enable_guest_overrides=1; b.syscall_overrides[90]=64;')
        self.assertEqual((result['status'],result['pc'],result['r'][31]),(1,4,0x88))
        self.assertEqual(result['r'][24:26],[1,2])


if __name__=='__main__':
    unittest.main()
