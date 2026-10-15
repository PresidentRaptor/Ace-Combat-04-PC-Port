"""ISO container tests use sparse synthetic bytes, not an AC4 executable."""
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ac4_disc as disc


def put_both(data, offset, value, width):
    data[offset:offset + width] = value.to_bytes(width, 'little')
    data[offset + width:offset + 2 * width] = value.to_bytes(width, 'big')


def directory_record(name, block, size, flags=0):
    length = 33 + len(name) + (len(name) % 2 == 0)
    data = bytearray(length)
    data[0] = length
    put_both(data, 2, block, 4)
    put_both(data, 10, size, 4)
    data[25] = flags
    put_both(data, 28, 1, 2)
    data[32] = len(name)
    data[33:33 + len(name)] = name
    return data


def fixture():
    count = 22 + (disc.AC4_SIZE + 2047) // 2048
    data = bytearray(count * 2048)
    primary = bytearray(2048)
    primary[:7] = b'\x01CD001\x01'
    put_both(primary, 80, count, 4)
    put_both(primary, 128, 2048, 2)
    root = directory_record(b'\x00', 20, 2048, 2)
    primary[156:156 + len(root)] = root
    data[16 * 2048:17 * 2048] = primary
    data[17 * 2048:17 * 2048 + 7] = b'\xffCD001\x01'
    entry = directory_record(b'SLUS_201.52;1', 22, disc.AC4_SIZE)
    data[20 * 2048:20 * 2048 + len(entry)] = entry
    return data


class DiscTests(unittest.TestCase):
    def test_locates_exact_executable_extent(self):
        data, location = disc.executable_from_iso(io.BytesIO(fixture()))
        self.assertEqual(len(data), disc.AC4_SIZE)
        self.assertEqual(location['sector'], 22)

    def test_malformed_images(self):
        for offset, value in [(16 * 2048 + 1, 0),
                              (16 * 2048 + 128, 1),
                              (20 * 2048 + 2, 255),
                              (20 * 2048 + 25, 128),
                              (20 * 2048 + 33, 88)]:
            data = fixture()
            data[offset] = value
            with self.subTest(offset=offset):
                with self.assertRaises(disc.ImageError):
                    disc.executable_from_iso(io.BytesIO(data))

    def test_truncated_image(self):
        with self.assertRaises(disc.ImageError):
            disc.executable_from_iso(io.BytesIO(fixture()[:-2048]))

    def test_synthetic_payload_fails_game_identity(self):
        data, _ = disc.executable_from_iso(io.BytesIO(fixture()))
        with self.assertRaises(disc.ImageError):
            disc.inspect(data)


if __name__ == '__main__':
    unittest.main()
