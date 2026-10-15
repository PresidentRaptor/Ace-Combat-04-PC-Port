"""Inspect a little-endian ELF32 MIPS executable without the legacy toolchain."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct

AC4_SHA256 = '38ecebd6965c2f74ec8973f538781506bf3a2cfad86f908deb6c5d585d528301'
AC4_SIZE = 3248756
HEADER = struct.Struct('<16sHHIIIIIHHHHHH')
PROGRAM = struct.Struct('<IIIIIIII')
ADDRESS_LIMIT = 1 << 32


class ImageError(ValueError):
    """An unsupported or malformed executable."""


@dataclass(frozen=True)
class Segment:
    offset: int
    address: int
    file_size: int
    memory_size: int
    flags: int
    alignment: int


def read_layout(data: bytes) -> tuple[int, list[Segment]]:
    if len(data) < HEADER.size:
        raise ImageError('truncated ELF header')
    (ident, kind, machine, version, entry, phoff, _shoff, _flags,
     ehsize, phsize, phcount, _shsize, _shcount, _shstr) = HEADER.unpack_from(data)
    if ident[:7] != b'\x7fELF\x01\x01\x01':
        raise ImageError('expected ELF32, little endian, identification version 1')
    if kind != 2 or machine != 8 or version != 1:
        raise ImageError('expected an executable for MIPS, ELF version 1')
    if ehsize != HEADER.size:
        raise ImageError('unexpected ELF header size')
    if phcount == 0 or phcount == 0xffff or phsize != PROGRAM.size:
        raise ImageError('missing or unsupported program header table')
    if phoff < ehsize or phoff + phsize * phcount > len(data):
        raise ImageError('program header table outside file')
    segments = []
    for index in range(phcount):
        (ptype, offset, address, _physical, filesz, memsz,
         flags, alignment) = PROGRAM.unpack_from(data, phoff + index * phsize)
        if ptype != 1:
            continue
        if filesz > memsz or offset + filesz > len(data):
            raise ImageError(f'load segment {index}: invalid file extent')
        if address + memsz > ADDRESS_LIMIT:
            raise ImageError(f'load segment {index}: address overflow')
        if alignment > 1 and (alignment & (alignment - 1) or
                              address % alignment != offset % alignment):
            raise ImageError(f'load segment {index}: invalid alignment')
        if memsz:
            segments.append(Segment(offset, address, filesz, memsz, flags, alignment))
    if not segments:
        raise ImageError('no nonempty load segments')
    ordered = sorted(segments, key=lambda segment: segment.address)
    for left, right in zip(ordered, ordered[1:]):
        if left.address + left.memory_size > right.address:
            raise ImageError('overlapping load segments are unsupported')
    if entry % 4 or not any(s.flags & 1 and s.address <= entry < s.address + s.file_size
                            for s in segments):
        raise ImageError('entry must be aligned and inside file-backed executable data')
    return entry, segments


def inspect(data: bytes, *, require_ac4: bool = True) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    supported = len(data) == AC4_SIZE and digest == AC4_SHA256
    if require_ac4 and not supported:
        raise ImageError('not the supported unmodified USA SLUS_201.52 executable')
    entry, segments = read_layout(data)
    return {
        'sha256': digest, 'file_size': len(data), 'supported_ac4': supported,
        'entry': f'0x{entry:08x}',
        'load_segments': [
            {'address': f'0x{s.address:08x}', 'offset': s.offset,
             'file_size': s.file_size, 'memory_size': s.memory_size,
             'zero_fill_size': s.memory_size - s.file_size,
             'flags': s.flags, 'alignment': s.alignment}
            for s in segments
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('--allow-other', action='store_true',
                        help='inspect another ELF without accepting it as supported AC4')
    args = parser.parse_args()
    try:
        result = inspect(args.executable.read_bytes(), require_ac4=not args.allow_other)
    except (OSError, ImageError) as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
