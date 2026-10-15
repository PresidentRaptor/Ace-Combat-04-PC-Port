"""Read AC4's root executable from a plain 2048-byte-sector ISO9660 image."""
import argparse
import json
from pathlib import Path

from ac4_image import AC4_SIZE, ImageError, inspect

SECTOR = 2048


def both(data, offset, width):
    little = int.from_bytes(data[offset:offset + width], 'little')
    big = int.from_bytes(data[offset + width:offset + 2 * width], 'big')
    if little != big:
        raise ImageError('ISO duplicated numeric fields disagree')
    return little


def record(data):
    if len(data) < 34 or data[0] != len(data) or 33 + data[32] > len(data):
        raise ImageError('invalid ISO directory record')
    if data[1] or data[26] or data[27] or data[25] & 0x80:
        raise ImageError('extended, interleaved or multi-extent ISO records unsupported')
    if both(data, 28, 2) != 1:
        raise ImageError('multi-volume ISO unsupported')
    return (both(data, 2, 4), both(data, 10, 4), data[25],
            data[33:33 + data[32]])


def executable_from_iso(stream):
    stream.seek(0, 2)
    total = stream.tell()

    def read_at(offset, length):
        if offset < 0 or length < 0 or offset + length > total:
            raise ImageError('ISO extent outside image')
        stream.seek(offset)
        data = stream.read(length)
        if len(data) != length:
            raise ImageError('truncated ISO extent')
        return data

    primary = None
    for sector in range(16, 80):
        descriptor = read_at(sector * SECTOR, SECTOR)
        if descriptor[1:7] != b'CD001\x01':
            raise ImageError('invalid ISO volume descriptor')
        if descriptor[0] == 1:
            if primary is not None:
                raise ImageError('multiple primary ISO descriptors unsupported')
            primary = descriptor
        if descriptor[0] == 255:
            break
    else:
        raise ImageError('ISO volume descriptor terminator missing')
    if primary is None:
        raise ImageError('primary ISO descriptor missing')
    if both(primary, 128, 2) != SECTOR:
        raise ImageError('only 2048-byte logical blocks supported')
    volume_bytes = both(primary, 80, 4) * SECTOR
    if volume_bytes > total:
        raise ImageError('declared ISO volume exceeds image')

    def volume_read(block, size):
        if block * SECTOR + size > volume_bytes:
            raise ImageError('extent exceeds declared ISO volume')
        return read_at(block * SECTOR, size)

    root_length = primary[156]
    block, size, flags, _name = record(primary[156:156 + root_length])
    if not flags & 2 or size > 16 * 1024 * 1024:
        raise ImageError('invalid or unsupported ISO root directory')
    directory = volume_read(block, size)
    cursor = 0
    found = None
    while cursor < len(directory):
        length = directory[cursor]
        if not length:
            cursor = (cursor // SECTOR + 1) * SECTOR
            continue
        if cursor % SECTOR + length > SECTOR:
            raise ImageError('ISO directory record crosses sector boundary')
        file_block, file_size, file_flags, name = record(directory[cursor:cursor + length])
        if name in (b'SLUS_201.52;1', b'SLUS_201.52'):
            if found is not None or file_flags & 2 or file_size != AC4_SIZE:
                raise ImageError('ambiguous or invalid AC4 executable record')
            found = (file_block, file_size)
        cursor += length
    if found is None:
        raise ImageError('SLUS_201.52 not found in ISO root')
    data = volume_read(*found)
    return data, {'sector': found[0], 'size': found[1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('iso', type=Path)
    args = parser.parse_args()
    try:
        with args.iso.open('rb') as stream:
            data, location = executable_from_iso(stream)
        result = inspect(data)
    except (OSError, ImageError) as error:
        parser.exit(1, f'{error}\n')
    result['iso_executable'] = location
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
