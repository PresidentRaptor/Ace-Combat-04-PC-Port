"""Compile deterministic C translation units, retaining unchanged local objects."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
import subprocess
import time


def compile_pages(files,root,cc,environment,cache,*,jobs=4):
    if not 1<=jobs<=8:
        raise ValueError('native build jobs must be between 1 and 8')
    for name,source in files.items():
        path=root/name
        raw=source.encode('utf-8')
        if not path.exists() or path.read_bytes()!=raw:
            path.write_bytes(raw)
    headers=sorted(root.glob('*.h'))+sorted(root.glob('*.inc'))
    dependency=hashlib.sha256(b''.join(path.name.encode()+b'\0'+path.read_bytes() for path in headers)).digest()
    sources=sorted(root.glob('*.c'))
    objects=[]; changed=[]
    for source in sources:
        object_file=source.with_suffix('.o')
        objects.append(object_file)
        digest=hashlib.sha256(dependency+source.read_bytes()).digest()
        if cache.get(source.name)!=(digest,object_file) or not object_file.exists():
            changed.append((source,object_file,digest))
    started=time.perf_counter()
    def compile_one(item):
        source,object_file,digest=item
        result=subprocess.run([cc,'-std=c11','-O0','-Wall','-Wextra','-Werror','-I',str(root),
                               '-c',str(source),'-o',str(object_file)],
                              capture_output=True,text=True,env=environment,timeout=120)
        if result.returncode:
            raise ValueError(f'native compilation failed for {source.name}: {result.stderr}')
        return source.name,(digest,object_file)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for name,value in pool.map(compile_one,changed):
            cache[name]=value
    compile_seconds=time.perf_counter()-started
    # A response file avoids Windows command-length limits for large maps.
    response=root/'link.rsp'
    response.write_text('\n'.join('"'+path.as_posix()+'"' for path in objects)+'\n',encoding='utf-8')
    executable=root/('ac4-independent-bootstrap.exe' if os.name=='nt' else 'ac4-independent-bootstrap')
    command=[cc,'@'+str(response),'-o',str(executable)]
    if os.name=='nt':
        command.append('-Wl,--no-insert-timestamp')
    started=time.perf_counter()
    result=subprocess.run(command,capture_output=True,text=True,env=environment,timeout=120)
    if result.returncode:
        raise ValueError(f'native link failed: {result.stderr}')
    return executable,dict(translation_units=len(sources),compiled=len(changed),
                           reused=len(sources)-len(changed),
                           compile_seconds=round(compile_seconds,3),
                           link_seconds=round(time.perf_counter()-started,3))
