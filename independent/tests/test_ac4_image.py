"""Synthetic executable fixtures; no game data required."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / 'ac4_image.py'
SPEC = importlib.util.spec_from_file_location('independent_ac4_image', MODULE_PATH)
image = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = image
SPEC.loader.exec_module(image)


def fixture(*, entry=0x1000, segments=None):
    if segments is None:
        segments = [(1, 0x100, 0x1000, 0x1000, 4, 16, 5, 0x100)]
    data = bytearray(0x200)
    ident = b'\x7fELF\x01\x01\x01' + bytes(9)
    image.HEADER.pack_into(data, 0, ident, 2, 8, 1, entry, 52, 0, 0,
                           52, 32, len(segments), 0, 0, 0)
    for index, segment in enumerate(segments):
        image.PROGRAM.pack_into(data, 52 + index * 32, *segment)
    data[0x100:0x104] = b'\x01\x02\x03\x04'
    return data


class LayoutTests(unittest.TestCase):
    def test_valid_layout_and_zero_fill(self):
        result = image.inspect(bytes(fixture()), require_ac4=False)
        self.assertFalse(result['supported_ac4'])
        self.assertEqual(result['entry'], '0x00001000')
        self.assertEqual(result['load_segments'][0]['zero_fill_size'], 12)

    def test_game_identity_is_required_by_default(self):
        with self.assertRaisesRegex(image.ImageError, 'supported unmodified'):
            image.inspect(bytes(fixture()))

    def test_header_and_table_rejections(self):
        cases = [b'', bytes(52)]
        for offset, fmt, value in [(4, '<B', 2), (5, '<B', 2), (18, '<H', 3),
                                    (28, '<I', 500), (40, '<H', 51),
                                    (42, '<H', 31), (44, '<H', 0)]:
            data = fixture()
            struct.pack_into(fmt, data, offset, value)
            cases.append(bytes(data))
        for data in cases:
            with self.subTest(data=data[:52]):
                with self.assertRaises(image.ImageError):
                    image.read_layout(data)

    def test_segment_rejections(self):
        cases = [
            (1, 0x100, 0x1000, 0, 17, 16, 5, 1),
            (1, 0x1ff, 0x1000, 0, 4, 16, 5, 1),
            (1, 0x100, 0xfffffff0, 0, 4, 32, 5, 1),
            (1, 0x100, 0x1000, 0, 4, 16, 5, 3),
            (1, 0x101, 0x1000, 0, 4, 16, 5, 0x100),
            (2, 0x100, 0x1000, 0, 4, 16, 5, 1),
        ]
        for segment in cases:
            with self.subTest(segment=segment):
                with self.assertRaises(image.ImageError):
                    image.read_layout(bytes(fixture(segments=[segment])))

    def test_entry_must_be_aligned_executable_file_data(self):
        for entry in (0x1001, 0x1004, 0x2000):
            with self.subTest(entry=entry):
                with self.assertRaises(image.ImageError):
                    image.read_layout(bytes(fixture(entry=entry)))
        with self.assertRaises(image.ImageError):
            image.read_layout(bytes(fixture(segments=[(1, 256, 4096, 0, 4, 16, 4, 1)])))

    def test_overlapping_loads_rejected(self):
        with self.assertRaisesRegex(image.ImageError, 'overlapping'):
            image.read_layout(bytes(fixture(segments=[
                (1, 256, 4096, 0, 4, 16, 5, 1),
                (1, 260, 4100, 0, 4, 16, 5, 1),
            ])))


if __name__ == '__main__':
    unittest.main()
