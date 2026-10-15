"""Synthetic executable sections constrain inventory even in an RWX segment."""
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ac4_image as image
from r5900_analysis import executable_words


def fixture():
    data = bytearray(0x300)
    image.HEADER.pack_into(data, 0, b'\x7fELF\x01\x01\x01' + bytes(9),
                           2, 8, 1, 0x1000, 52, 0x200, 0, 52, 32, 1, 40, 3, 0)
    image.PROGRAM.pack_into(data, 52, 1, 0x100, 0x1000, 0x1000, 0x80, 0xa0, 7, 0x100)
    image.SECTION.pack_into(data, 0x228, 0, 1, 6, 0x1000, 0x100, 8, 0, 0, 4, 0)
    image.SECTION.pack_into(data, 0x250, 0, 1, 3, 0x1040, 0x140, 16, 0, 0, 4, 0)
    data[0x100:0x108] = bytes.fromhex('0800e00300000000')
    data[0x140:0x150] = b'not instructions'
    return data


class SectionTests(unittest.TestCase):
    def test_readonly_table_bytes_require_allocated_nonwritable_file_mapping(self):
        data = fixture()
        self.assertIsNone(image.readonly_bytes(data, 0x1040, 16))
        image.SECTION.pack_into(data, 0x250, 0, 1, 2, 0x1040, 0x140, 16, 0, 0, 4, 0)
        self.assertEqual(image.readonly_bytes(data, 0x1044, 4), b'inst')
        for address, size in ((0x103f, 4), (0x104f, 2), (0x1080, 4), (-1, 4),
                              (0x1040, 0), (0xffffffff, 4)):
            with self.subTest(address=address, size=size):
                self.assertIsNone(image.readonly_bytes(data, address, size))

    def test_readonly_table_rejects_truncated_and_inconsistent_sections(self):
        for offset, size in ((0x141, 16), (0x140, 0x200), (0x140, 0x50)):
            data = fixture()
            image.SECTION.pack_into(data, 0x250, 0, 1, 2, 0x1040, offset, size, 0, 0, 4, 0)
            with self.subTest(offset=offset, size=size):
                with self.assertRaises(image.ImageError):
                    image.readonly_bytes(data, 0x1040, 4)

    def test_stripped_image_cannot_establish_readonly_section(self):
        data = fixture()
        h = list(image.HEADER.unpack_from(data))
        h[6], h[11], h[12], h[13] = 0, 0, 0, 0
        image.HEADER.pack_into(data, 0, *h)
        self.assertIsNone(image.readonly_bytes(data, 0x1000, 4))

    def test_rwx_data_and_zero_fill_excluded(self):
        data = fixture()
        with patch.object(image, 'AC4_SIZE', len(data)), patch.object(
                image, 'AC4_SHA256', hashlib.sha256(data).hexdigest()):
            words, entry, metadata = executable_words(data)
        self.assertEqual(words, {0x1000: 0x03e00008, 0x1004: 0})
        self.assertEqual(entry, 0x1000)
        self.assertEqual(metadata['code_selection'], 'allocated-executable-sections')

    def test_rejects_inconsistent_section_mappings_and_formats(self):
        for address, offset, size, flags, kind, alignment in (
            (0x1000, 0x104, 8, 6, 1, 4),
            (0x1000, 0x100, 0x84, 6, 1, 4),
            (0x1000, 0x100, 8, 6, 8, 4),
            (0x1001, 0x101, 8, 6, 1, 1),
            (0x1000, 0x100, 7, 6, 1, 4),
            (0x1000, 0x100, 8, 6, 1, 3),
        ):
            data = fixture()
            image.SECTION.pack_into(data, 0x228, 0, kind, flags, address,
                                    offset, size, 0, 0, alignment, 0)
            _, segments = image.read_layout(data)
            with self.subTest(address=address, offset=offset, size=size, flags=flags):
                with self.assertRaises(image.ImageError):
                    image.code_ranges(data, segments)

    def test_overlapping_sections_rejected(self):
        data = fixture()
        image.SECTION.pack_into(data, 0x250, 0, 1, 6, 0x1004, 0x104, 8, 0, 0, 4, 0)
        _, segments = image.read_layout(data)
        with self.assertRaisesRegex(image.ImageError, 'overlapping'):
            image.code_ranges(data, segments)

    def test_truncated_section_table_rejected(self):
        data = fixture()[:0x260]
        _, segments = image.read_layout(data)
        with self.assertRaisesRegex(image.ImageError, 'section table outside'):
            image.code_ranges(data, segments)

    def test_nonallocated_vendor_sections_with_execute_bit_are_not_code(self):
        data = fixture()
        image.SECTION.pack_into(data, 0x250, 0, 0x7ffff421, 5, 0, 0x140, 16, 0, 0, 1, 0)
        _, segments = image.read_layout(data)
        _, ranges = image.code_ranges(data, segments)
        self.assertEqual(ranges, [{'address': 0x1000, 'offset': 0x100, 'size': 8}])

    def test_vu_microcode_is_separate_from_ee_even_with_same_flags(self):
        data = fixture()
        # Extend the header table with a synthetic section-name string table.
        data.extend(bytes(0x100))
        header = list(image.HEADER.unpack_from(data))
        header[12], header[13] = 4, 3
        image.HEADER.pack_into(data, 0, *header)
        names = b'\0.text\0.vutext\0.shstrtab\0'
        data[0x300:0x300 + len(names)] = names
        image.SECTION.pack_into(data, 0x228, 1, 1, 6, 0x1000, 0x100, 8, 0, 0, 4, 0)
        image.SECTION.pack_into(data, 0x250, 7, 1, 6, 0x1040, 0x140, 16, 0, 0, 8, 0)
        image.SECTION.pack_into(data, 0x278, 15, 3, 0, 0, 0x300, len(names), 0, 0, 1, 0)
        _, segments = image.read_layout(data)
        self.assertEqual(image.code_ranges(data, segments)[1],
                         [{'address': 0x1000, 'offset': 0x100, 'size': 8}])
        self.assertEqual(image.code_ranges(data, segments, architecture='vu')[1],
                         [{'address': 0x1040, 'offset': 0x140, 'size': 16}])
        data[0x228:0x22c] = (999).to_bytes(4, 'little')
        with self.assertRaisesRegex(image.ImageError, 'section name'):
            image.code_ranges(data, segments)


if __name__ == '__main__':
    unittest.main()
