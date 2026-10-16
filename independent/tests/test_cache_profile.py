"""Explicit coherent-memory maintenance subset, not a hardware cache model."""
import unittest
from test_codegen import native,TranslationError


class CacheProfileTests(unittest.TestCase):
    def test_supported_maintenance_preserves_memory_and_registers(self):
        wrapper='''
int cache_run(Ac4Cpu *c,uint64_t budget) {
    c->coherent_cache_profile=1; c->memory_base=0; c->ee_memory_map=1;
    return ac4_run(c,budget);
}
'''
        for op in (24,28):
            word=(47<<26)|(4<<21)|(op<<16)|63
            result=native({0:word,4:13},registers={4:64,5:0x123456789},memory={64:0xaa,127:0xbb},
                          extra_source=wrapper,run_function='cache_run',paged=True)
            self.assertEqual((result['status'],result['r'][5]),(1,0x123456789))
            self.assertEqual((result['memory'][64],result['memory'][127]),(0xaa,0xbb))

    def test_disabled_profile_is_explicit_and_uncached_addresses_are_undefined(self):
        word=(47<<26)|(4<<21)|(24<<16)
        result=native({0:word,4:13},registers={4:64},paged=True)
        self.assertEqual(result['status'],10)
        wrapper='''
int cache_run(Ac4Cpu *c,uint64_t budget) {
    c->coherent_cache_profile=1; c->memory_base=0; c->ee_memory_map=1;
    return ac4_run(c,budget);
}
'''
        for address in (0x20000040,0xa0000040,0x70000040,0x1000f200):
            result=native({0:word,4:13},registers={4:address},extra_source=wrapper,
                          run_function='cache_run',paged=True)
            self.assertEqual((result['status'],result['pc']),(9,0))

    def test_privilege_and_line_bounds_stop_without_rewriting_memory(self):
        wrapper='''
int cache_run(Ac4Cpu *c,uint64_t budget) {
    c->coherent_cache_profile=1; c->memory_base=0; c->ee_memory_map=1;
    c->cp0_status=(uint32_t)c->gpr[5][0];
    return ac4_run(c,budget);
}
'''
        word=(47<<26)|(4<<21)|(24<<16)
        result=native({0:word,4:13},registers={4:64,5:0x10},extra_source=wrapper,
                      run_function='cache_run',paged=True)
        self.assertEqual(result['status'],13)
        result=native({0:word,4:13},registers={4:0x80000100},extra_source=wrapper,
                      run_function='cache_run',paged=True)
        self.assertEqual(result['status'],5)

    def test_index_tag_operations_stay_unsupported(self):
        with self.assertRaises(TranslationError):
            native({0:(47<<26)|(4<<21)|(16<<16),4:13},paged=True)

    def test_cache_maintenance_cannot_disable_modified_instruction_guard(self):
        words={0:0xac820000,4:(47<<26)|(24<<16),8:13}
        raw=b''.join(word.to_bytes(4,'little') for word in words.values())
        wrapper='''
int cache_run(Ac4Cpu *c,uint64_t budget) {
    c->coherent_cache_profile=1; c->memory_base=0; c->ee_memory_map=1;
    c->verify_instruction_bytes=1;
    return ac4_run(c,budget);
}
'''
        result=native(words,registers={4:8},memory=dict(enumerate(raw)),extra_source=wrapper,
                      run_function='cache_run',paged=True)
        self.assertEqual((result['status'],result['pc']),(12,8))


if __name__=='__main__':
    unittest.main()
