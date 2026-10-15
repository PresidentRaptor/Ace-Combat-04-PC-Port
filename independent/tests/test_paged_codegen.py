"""Native page boundaries and incremental compilation without game inputs."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_codegen import native,compiler
from r5900_codegen import emit_modules,TranslationError
from native_build import compile_pages


class PagedCodegenTests(unittest.TestCase):
    def test_delay_slot_crosses_compilation_page_and_retains_target(self):
        words={0xffc:0x00800008,0x1000:0x24040014,0x2000:13}
        result=native(words,entry=0xffc,registers={4:0x2000},paged=True)
        self.assertEqual((result['status'],result['pc'],result['r'][4],result['steps']),(1,0x2000,20,3))

    def test_memory_fault_in_another_page_keeps_branch_exception_context(self):
        result=native({0xffc:0x08000800,0x1000:0x8c020001,0x2000:13},entry=0xffc,paged=True)
        self.assertEqual((result['status'],result['fault_pc'],result['delay']),(4,0xffc,1))

    def test_likely_annulment_and_budget_match_monolithic_backend(self):
        program={0xffc:0x50800002,0x1000:0x8c020001,0x1004:13,0x1008:13}
        for backend in (False,True):
            result=native(program,entry=0xffc,registers={4:1},paged=backend)
            self.assertEqual((result['status'],result['steps'],result['pc']),(1,2,0x1004))
        result=native({0:0x08000000,4:0},limit=9,paged=True)
        self.assertEqual((result['status'],result['steps'],result['pc']),(8,9,4))

    def test_packed_aliases_and_128_bit_memory_use_shared_state(self):
        result=native({0:0x704313a9,4:0x7c820000,8:0x78850000,12:13},
                      registers={2:11,3:22,4:0x1000},upper={2:33,3:44},paged=True)
        self.assertEqual((result['r'][5],result['upper'][5]),(33,44))

    def test_generated_page_sources_are_stable_when_another_page_is_added(self):
        first=emit_modules({0:13},0)
        second=emit_modules({0:13,0x1000:13},0)
        for name in ('ac4_cpu.h','ac4_runtime.c','ac4_page_00000.c'):
            self.assertEqual(first[name],second[name])
        self.assertNotEqual(first['ac4_dispatch.c'],second['ac4_dispatch.c'])
        with self.assertRaises(TranslationError):
            emit_modules({0:0x40024800},0)
        self.assertIn('AC4_UNSUPPORTED',emit_modules({0:0x40024800},0,stop_unsupported=True)['ac4_page_00000.c'])

    def test_native_object_cache_rebuilds_changed_units_and_header_dependents(self):
        cc=compiler()
        if cc is None:
            if os.environ.get('AC4_REQUIRE_NATIVE_TESTS')=='1':
                self.fail('native compiler required')
            self.skipTest('native compiler required')
        environment=dict(os.environ)
        environment['PATH']=str(Path(cc).parent)+os.pathsep+environment.get('PATH','')
        with tempfile.TemporaryDirectory(prefix='ac4-page-cache-') as folder:
            root=Path(folder); cache={}
            (root/'main.c').write_text('#include "ac4_cpu.h"\nint main(void) { Ac4Cpu c={0}; return ac4_run(&c,10)==AC4_BREAK ? 0 : 1; }',encoding='utf-8')
            first=emit_modules({0:13},0)
            executable,report=compile_pages(first,root,cc,environment,cache,jobs=2)
            self.assertEqual((report['compiled'],report['reused']),(4,0))
            subprocess.run([str(executable)],env=environment,check=True,timeout=5)
            second=emit_modules({0:13,0x1000:13},0)
            _,report=compile_pages(second,root,cc,environment,cache,jobs=2)
            self.assertEqual((report['compiled'],report['reused']),(2,3))
            second['ac4_cpu.h']+='\n/* dependency changed */\n'
            _,report=compile_pages(second,root,cc,environment,cache,jobs=2)
            self.assertEqual((report['compiled'],report['reused']),(5,0))


if __name__=='__main__':
    unittest.main()
