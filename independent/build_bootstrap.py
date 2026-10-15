"""Build a local native AC4 startup diagnostic; no playable-build claim.

Requires the supported user's image. Output contains private game-derived data,
so destinations inside this Git repository are rejected. No legacy build inputs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from ac4_image import read_layout, inspect
from r5900_analysis import executable_words,stream_words
from r5900_codegen import bounded_plan, emit_program

HERE = Path(__file__).resolve().parent


def output_path(path):
    path = path.resolve()
    if path.is_relative_to(HERE.parent):
        raise ValueError('game-derived build output must be outside this Git repository')
    if path.exists():
        raise ValueError('output directory already exists; select a fresh destination')
    return path


def copied_code_words(data, regions):
    """Map explicitly observed file-backed copies without preloading destinations.

    Runtime instruction guards still require the guest to perform the copy.
    This classifies only the user-specified range, not all embedded data as code.
    """
    _,segments=read_layout(data)
    words,metadata={},[]
    for source,destination,size in regions:
        if min(source,destination)<0 or size<=0 or (source|destination|size)&3 or \
                source+size>1<<32 or destination+size>1<<32:
            raise ValueError('copied-code range must be aligned, positive and nonwrapping')
        mappings=[s for s in segments if s.address<=source and source+size<=s.address+s.file_size]
        if len(mappings)!=1:
            raise ValueError('copied-code source is not one file-backed load range')
        segment=mappings[0]
        offset=segment.offset+source-segment.address
        selected=stream_words(data[offset:offset+size],destination)
        if words.keys() & selected.keys():
            raise ValueError('overlapping copied-code destinations')
        words.update(selected)
        metadata.append(dict(source=f'0x{source:08x}',destination=f'0x{destination:08x}',size=size))
    return words,metadata


def build(data, output, cc, *, limit=1024, extra_entries=(), copied_regions=()):
    output = output_path(output)
    image = inspect(data)  # Supported identity is mandatory before any output.
    words, entry, _ = executable_words(data)
    copied,copies=copied_code_words(data,copied_regions)
    if words.keys() & copied.keys():
        raise ValueError('copied-code destination overlaps original selected CPU words')
    words.update(copied)
    seeds=[entry,*extra_entries,*[destination for _,destination,_ in copied_regions]]
    if any(pc not in words for pc in seeds):
        raise ValueError('entry seed outside verified CPU image ranges')
    selected, selection = bounded_plan(words,seeds,limit=limit,resume_syscalls=True)
    selection['entry_seeds']=[f'0x{pc:08x}' for pc in seeds]
    selection['observed_code_copies']=copies
    program = emit_program(selected,entry,stop_unsupported=True)
    program += f'\n#define AC4_PROGRAM_ENTRY UINT32_C(0x{entry:08x})\n'
    _, segments = read_layout(data)
    ram = bytearray(32*1024*1024)
    for s in segments:
        if s.address+s.memory_size > len(ram):
            raise ValueError('load range outside diagnostic RAM')
        ram[s.address:s.address+s.file_size] = data[s.offset:s.offset+s.file_size]
    environment = dict(os.environ)
    environment['PATH'] = str(Path(cc).resolve().parent)+os.pathsep+environment.get('PATH','')
    with tempfile.TemporaryDirectory(prefix='ac4-bootstrap-build-') as folder:
        root = Path(folder)
        generated = root/'generated_program.inc'
        generated.write_text(program,encoding='utf-8')
        ram_file = root/'ram.bin'
        ram_file.write_bytes(ram)
        executable = root/('ac4-independent-bootstrap.exe' if os.name=='nt' else 'ac4-independent-bootstrap')
        # Large diagnostic dispatch maps prioritize bounded compilation latency;
        # optimized code generation is still exercised by the native unit suite.
        command=[cc,'-std=c11','-O0','-Wall','-Wextra','-Werror','-I',str(root),'-I',str(HERE),
                 str(HERE/'bootstrap_main.c'),'-o',str(executable)]
        if os.name=='nt':
            command.append('-Wl,--no-insert-timestamp')
        compile_result = subprocess.run(command,
            capture_output=True,text=True,env=environment,timeout=120)
        if compile_result.returncode:
            raise ValueError(f'native build failed: {compile_result.stderr}')
        execution = subprocess.run([str(executable),str(ram_file)],capture_output=True,
                                   text=True,env=environment,timeout=30)
        if execution.returncode not in (0,2):
            raise ValueError(f'diagnostic process failed: {execution.stderr}')
        observation = json.loads(execution.stdout)
        if observation.get('scope')!='experimental-bootstrap-diagnostic':
            raise ValueError('invalid diagnostic response')
        version = subprocess.run([cc,'--version'],capture_output=True,text=True,
                                 env=environment,check=True,timeout=10).stdout.splitlines()[0]
        manifest = dict(schema=1,scope='experimental bootstrap diagnostic; NOT PLAYABLE',optimization='O0',
                        image_sha256=image['sha256'],compiler=version,
                        generated_source_sha256=hashlib.sha256(program.encode()).hexdigest(),
                        ram_sha256=hashlib.sha256(ram).hexdigest(),
                        executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
                        selection=selection,observation=observation,
                        limitations=['provisional startup stack/heap policy and cooperative scheduler ABI',
                                     'ordinary-function guest syscall bridge; no CP0 privilege transition',
                                     'no hardware execution oracle or complete exception delivery',
                                     'unknown services/instructions and missing dispatch targets stop',
                                     'no graphics, input, audio, disc runtime or gameplay'])
        output.mkdir(parents=True)
        shutil.copy2(executable,output/executable.name)
        shutil.copy2(ram_file,output/'ram.bin')
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        (output/'README.txt').write_text(
            'EXPERIMENTAL AC4 STARTUP DIAGNOSTIC - NOT A PLAYABLE GAME\n\n'
            f'Run from this directory: ./{executable.name} ram.bin\n'
            'Requires the original matching RAM image produced by this build.\n'
            'RAM and executable contain your private game-derived data; keep them outside Git.\n'
            'Exit status 2 is a reported incomplete execution boundary, not game success.\n'
            'See manifest.json for measured results and limitations.\n',encoding='utf-8')
    return dict(output=str(output),**manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--iso',type=Path)
    source.add_argument('--elf',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cc',default=os.environ.get('AC4_TEST_CC','gcc'))
    parser.add_argument('--limit',type=int,default=1024)
    parser.add_argument('--entry',type=lambda value:int(value,0),action='append',default=[],
                        help='additional independently verified CPU entry (repeatable)')
    parser.add_argument('--copied-code',action='append',default=[],metavar='SOURCE:DESTINATION:SIZE',
                        help='explicitly observed runtime code copy; repeat for additional regions')
    args = parser.parse_args()
    try:
        output_path(args.output)
        cc = shutil.which(args.cc)
        if cc is None:
            raise ValueError('C compiler unavailable; supply --cc')
        if args.iso:
            from ac4_disc import executable_from_iso
            with args.iso.open('rb') as stream:
                data,_ = executable_from_iso(stream)
        else:
            data=args.elf.read_bytes()
        regions=[]
        for item in args.copied_code:
            fields=item.split(':')
            if len(fields)!=3:
                raise ValueError('copied-code requires SOURCE:DESTINATION:SIZE')
            regions.append(tuple(int(field,0) for field in fields))
        result=build(data,args.output,cc,limit=args.limit,extra_entries=args.entry,copied_regions=regions)
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        parser.exit(1,f'{error}\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
