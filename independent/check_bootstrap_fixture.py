"""CTest driver: synthetic startup runner and malformed RAM/CLI failures."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    executable=Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix='ac4-bootstrap-fixture-') as folder:
        ram=Path(folder)/'ram.bin'
        ram.write_bytes(bytes.fromhex('070002240d000000')+bytes(32*1024*1024-8))
        result=subprocess.run([str(executable),str(ram)],capture_output=True,text=True,timeout=10)
        if result.returncode or json.loads(result.stdout)['status']!=1:
            raise ValueError(f'synthetic bootstrap failed: {result.stderr} {result.stdout}')
        ram.write_bytes(bytes(17))
        result=subprocess.run([str(executable),str(ram)],capture_output=True,text=True,timeout=10)
        if result.returncode!=65:
            raise ValueError('malformed RAM did not fail explicitly')
        result=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
        if result.returncode!=64:
            raise ValueError('missing RAM argument did not fail explicitly')
    print('Synthetic bootstrap and invalid-input checks passed; no game inputs.')


if __name__=='__main__':
    main()
