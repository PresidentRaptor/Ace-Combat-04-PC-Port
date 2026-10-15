"""Compile and execute AC4's bounded entry graph up to its first syscall.

This is a flat-memory scalar smoke check, not kernel/boot compatibility or an
independent hardware oracle. Game bytes/generated source exist only in a private
temporary directory, which is removed when the command finishes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from ac4_image import read_layout
from r5900_codegen import entry_program


DRIVER = r'''
#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
int main(void) {
    unsigned char *memory=malloc(32*1024*1024);
    FILE *file=fopen("ram.bin","rb");
    if (!memory || !file) return 10;
    if (fread(memory,1,32*1024*1024,file)!=32*1024*1024) return 11;
    fclose(file);
    /* Poison the reviewed startup clear range to make writes observable. */
    for (unsigned i=0x411780;i<0x4cc760;i++) memory[i]=0xa5;
    Ac4Cpu c={0}; c.memory=memory; c.memory_size=32*1024*1024; c.pc=0x100008;
    int status=ac4_run(&c,1000000);
    unsigned dirty=0;
    for (unsigned i=0x411780;i<0x4cc760;i++) if (memory[i]) dirty++;
    printf("{\"status\":%d,\"pc\":%u,\"steps\":%" PRIu64
           ",\"syscall_register\":%" PRIu64 ",\"v0\":%" PRIu64
           ",\"gp\":%" PRIu64 ",\"uncleared_bytes\":%u}",
           status,c.pc,c.steps,c.gpr[3][0],c.gpr[2][0],c.gpr[28][0],dirty);
    free(memory); return 0;
}
'''


def validate(data, cc):
    source, entry, count = entry_program(data)  # Identity is required here.
    _, segments = read_layout(data)
    memory = bytearray(32 * 1024 * 1024)
    for segment in segments:
        if segment.address + segment.memory_size > len(memory):
            raise ValueError('load mapping outside smoke harness RAM')
        memory[segment.address:segment.address + segment.file_size] = data[
            segment.offset:segment.offset + segment.file_size]
    environment = dict(os.environ)
    environment['PATH'] = str(Path(cc).resolve().parent) + os.pathsep + environment.get('PATH', '')
    with tempfile.TemporaryDirectory(prefix='ac4-native-entry-') as folder:
        root = Path(folder)
        (root / 'ram.bin').write_bytes(memory)
        (root / 'entry.c').write_text(source + DRIVER, encoding='utf-8')
        exe = root / ('entry.exe' if os.name == 'nt' else 'entry')
        build = subprocess.run([cc, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                                str(root / 'entry.c'), '-o', str(exe)],
                               capture_output=True, text=True, env=environment, timeout=60)
        if build.returncode:
            raise ValueError(f'C compiler rejected translation: {build.stderr}')
        run = subprocess.run([str(exe)], cwd=root, capture_output=True, text=True,
                             check=True, timeout=15, env=environment)
        observed = json.loads(run.stdout)
    # Values calculated separately from the reviewed startup field/loop behavior;
    # they are not a trace from physical hardware or a second CPU emulator.
    expected = dict(status=2, pc=0x100064, steps=335107, syscall_register=60,
                    v0=0x4cc760, gp=0x4159f0, uncleared_bytes=0)
    if observed != expected:
        raise ValueError(f'native entry mismatch: {observed}; expected {expected}')
    return dict(scope='bounded scalar entry smoke check; no syscall service or boot',
                entry=f'0x{entry:08x}', translated_addresses=count,
                generated_source_sha256=hashlib.sha256(source.encode('utf-8')).hexdigest(),
                observation=observed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--elf', type=Path)
    source.add_argument('--iso', type=Path)
    parser.add_argument('--cc', default=os.environ.get('AC4_TEST_CC', 'gcc'),
                        help='GCC-compatible C11 compiler name or full path')
    args = parser.parse_args()
    try:
        cc = shutil.which(args.cc)
        if cc is None:
            raise ValueError('C compiler unavailable; supply --cc')
        if args.iso:
            from ac4_disc import executable_from_iso
            with args.iso.open('rb') as stream:
                data, _ = executable_from_iso(stream)
        else:
            data = args.elf.read_bytes()
        result = validate(data, cc)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
