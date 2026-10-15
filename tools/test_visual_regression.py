"""Exercise failure propagation using generated images and a fake replay process."""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).parent / 'regression'))
from images import compare, read_image
from run import run_case, digest

SCRATCH = Path(__file__).resolve().parents[1] / 'out'
SCRATCH.mkdir(exist_ok=True)


def png(path, pixels, channels=3, width=1, height=1):
    def chunk(tag, body):
        return struct.pack('>I', len(body)) + tag + body + struct.pack('>I', zlib.crc32(tag+body))
    stride = width * channels
    raw = b''.join(b'\0' + pixels[i:i+stride] for i in range(0, len(pixels), stride))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2 if channels == 3 else 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


class Images(unittest.TestCase):
    def test_all_png_filters(self):
        def chunk(tag, data):
            return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag+data))
        first = bytes((10, 20, 30, 40, 50, 60))
        second = bytes((15, 25, 35, 45, 55, 65))
        encoded = [second, bytes((15,25,35,30,30,30)), bytes((5,)*6),
                   bytes((10,15,20,18,18,18)), bytes((5,)*6)]
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            path = Path(tmp)/'filters.png'
            for kind, row in enumerate(encoded):
                path.write_bytes(b'\x89PNG\r\n\x1a\n'
                    + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0))
                    + chunk(b'IDAT', zlib.compress(b'\0'+first+bytes((kind,))+row))
                    + chunk(b'IEND', b''))
                self.assertEqual(read_image(path)[3], first+second)

    def test_threshold_dimensions_alpha_and_corruption(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            a, b = Path(tmp)/'a.png', Path(tmp)/'b.png'
            png(a, b'\0\0\0')
            png(b, b'\x10\0\0')
            self.assertTrue(compare(a, b)['passed'])
            self.assertFalse(compare(a, b, 0)['passed'])
            png(b, b'\x11\0\0')
            self.assertFalse(compare(a, b)['passed'])
            self.assertTrue(compare(a, b, allowed_pixels=1)['passed'])
            png(b, b'\0'*6, width=2)
            self.assertFalse(compare(a, b)['passed'])
            png(a, b'\0\0\0\0', channels=4)
            png(b, b'\0\0\0\xff', channels=4)
            self.assertFalse(compare(a, b)['passed'])
            b.write_bytes(b.read_bytes()[:-5])
            with self.assertRaises(ValueError):
                read_image(b)

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            a, b = Path(tmp)/'a.ppm', Path(tmp)/'b.ppm'
            a.write_bytes(b'P6\n1 1\n255\n\0\0\0')
            b.write_bytes(b'P6\n1 1\n255\n\xff\0\0')
            cmd = [sys.executable, str(Path(__file__).parent/'regression/images.py'), str(a), str(b)]
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 1)
            self.assertEqual(subprocess.run(cmd+['--allowed-pixels', '1'], capture_output=True).returncode, 0)

    def test_replay_failure_missing_baseline_and_stale_output(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            fixtures = Path(tmp)
            capture = fixtures/'capture.gscap'
            capture.write_bytes(b'synthetic capture')
            baseline = fixtures/'baseline.ppm'
            baseline.write_bytes(b'P6\n1 1\n255\n\0\0\0')
            case = dict(name='case', capture=capture.name, baseline=baseline.name,
                        sha256=digest(capture), preset=0, resolution=1)
            # Python itself exits nonzero on the fake capture; no Vulkan/game data needed.
            args = (case, fixtures, Path(sys.executable), fixtures, fixtures, False, {}, 5)
            (fixtures/'case.ppm').write_bytes(b'stale')
            with self.assertRaises(subprocess.CalledProcessError):
                run_case(*args)
            self.assertFalse((fixtures/'case.ppm').exists())
            with patch('run.subprocess.run', side_effect=subprocess.TimeoutExpired('fake', 5)):
                with self.assertRaises(subprocess.TimeoutExpired):
                    run_case(*args)
            baseline.unlink()
            with self.assertRaisesRegex(ValueError, 'baseline missing'):
                run_case(*args)
            case['baseline'] = 'case.ppm'
            (fixtures/'case.ppm').write_bytes(b'fixture must survive')
            with self.assertRaisesRegex(ValueError, 'overwrite a fixture'):
                run_case(*args)
            self.assertEqual((fixtures/'case.ppm').read_bytes(), b'fixture must survive')
            case['sha256'] = 'wrong'
            with self.assertRaisesRegex(ValueError, 'capture hash'):
                run_case(*args)

    def test_success_without_image_and_explicit_baseline_update(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            fixtures = Path(tmp)
            capture = fixtures/'capture.gscap'
            capture.write_bytes(b'fixture')
            png(fixtures/'baseline.png', b'\0'*3)
            case = dict(name='case', capture=capture.name, baseline='baseline.png',
                        sha256=digest(capture), preset=0, resolution=1)
            args = (case, fixtures, Path(sys.executable), fixtures, fixtures)
            with patch('run.subprocess.run'):
                with self.assertRaisesRegex(ValueError, 'without producing'):
                    run_case(*args, False, {}, 5)
            def fake_replay(command, **kwargs):
                Path(command[command.index('--shot')+1]).write_bytes(b'P6\n1 1\n255\n\xff\0\0')
                kwargs['stdout'].write('[REPLAY] pass 1: 1 fields\n[REPLAY] done;\n')
            with patch('run.subprocess.run', side_effect=fake_replay):
                self.assertFalse(run_case(*args, False, {}, 5)['passed'])
                self.assertTrue(run_case(*args, True, {}, 5)['updated'])
                self.assertTrue(run_case(*args, False, {}, 5)['passed'])
                case['resolution'] = 2
                with self.assertRaisesRegex(ValueError, 'provenance'):
                    run_case(*args, False, {}, 5)

    def test_empty_manifest_fails_with_summary(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            path = Path(tmp)
            manifest = path/'manifest.json'
            manifest.write_text('{"version":1,"cases":[]}')
            result = subprocess.run([sys.executable, str(Path(__file__).parent/'regression/run.py'),
                                     '--fixtures', tmp, '--manifest', str(manifest), '--output', tmp],
                                    capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads((path/'summary.json').read_text())['passed'])


if __name__ == '__main__':
    unittest.main()
