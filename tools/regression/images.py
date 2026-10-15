"""Strict, dependency-free RGB/RGBA PNG and P6 PPM comparison."""
import argparse
import json
from pathlib import Path
import struct
import zlib


def read_image(path):
    data = Path(path).read_bytes()
    if data.startswith(b'P6'):
        import re
        match = re.match(rb'P6\s+(\d+)\s+(\d+)\s+255(?:\r\n|\s)', data)
        if not match:
            raise ValueError('unsupported PPM header (expected P6/255)')
        w, h = map(int, match.groups())
        pixels = data[match.end():]
        if not w or not h or len(pixels) != w * h * 3:
            raise ValueError('invalid PPM dimensions/payload')
        return w, h, 3, pixels
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('expected PNG or P6 PPM')
    pos, chunks, payload = 8, [], bytearray()
    w = h = channels = 0
    while pos < len(data):
        if pos + 12 > len(data):
            raise ValueError('truncated PNG chunk')
        size, = struct.unpack_from('>I', data, pos)
        tag = data[pos+4:pos+8]
        end = pos + 12 + size
        if end > len(data):
            raise ValueError('truncated PNG data')
        body = data[pos+8:end-4]
        crc, = struct.unpack_from('>I', data, end-4)
        if zlib.crc32(tag + body) != crc:
            raise ValueError('PNG CRC mismatch')
        if not chunks and tag != b'IHDR':
            raise ValueError('PNG must start with IHDR')
        if tag == b'IHDR':
            if chunks or size != 13:
                raise ValueError('invalid IHDR')
            w, h, depth, color, comp, filt, interlace = struct.unpack('>IIBBBBB', body)
            if not w or not h or depth != 8 or color not in (2, 6) or comp or filt or interlace:
                raise ValueError('expected non-interlaced 8-bit RGB/RGBA PNG')
            channels = 3 if color == 2 else 4
        elif tag == b'IDAT':
            payload.extend(body)
        elif tag == b'IEND':
            if size or end != len(data):
                raise ValueError('invalid IEND/trailing PNG bytes')
            chunks.append(tag)
            break
        elif not tag[0] & 32:
            raise ValueError('unsupported critical PNG chunk')
        chunks.append(tag)
        pos = end
    if not chunks or chunks[-1] != b'IEND' or not payload:
        raise ValueError('incomplete PNG')
    stride = w * channels
    expected = h * (stride + 1)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(payload, expected + 1)
    if len(raw) != expected or not decoder.eof or decoder.unused_data:
        raise ValueError('invalid PNG scanline payload')
    pixels, previous, pos = bytearray(), bytearray(stride), 0
    for _ in range(h):
        kind = raw[pos]
        row = bytearray(raw[pos+1:pos+1+stride])
        pos += stride + 1
        if kind > 4:
            raise ValueError('invalid PNG filter')
        for x in range(stride):
            a = row[x-channels] if x >= channels else 0
            b = previous[x]
            c = previous[x-channels] if x >= channels else 0
            if kind == 1:
                predictor = a
            elif kind == 2:
                predictor = b
            elif kind == 3:
                predictor = (a + b) // 2
            elif kind == 4:
                p = a + b - c
                distances = (abs(p-a), abs(p-b), abs(p-c))
                predictor = (a, b, c)[distances.index(min(distances))]
            else:
                predictor = 0
            row[x] = (row[x] + predictor) & 255
        pixels.extend(row)
        previous = row
    return w, h, channels, pixels


def compare(reference, actual, threshold=16, allowed_pixels=0):
    if not 0 <= threshold <= 255 or allowed_pixels < 0:
        raise ValueError('threshold must be 0..255; allowed_pixels must be nonnegative')
    w, h, channels, a = read_image(reference)
    w2, h2, channels2, b = read_image(actual)
    if (w, h, channels) != (w2, h2, channels2):
        return dict(passed=False, reason='dimensions or channel format differ',
                    reference=[w, h, channels], actual=[w2, h2, channels2])
    count = peak = 0
    for i in range(0, len(a), channels):
        delta = max(abs(a[i+k] - b[i+k]) for k in range(channels))
        peak = max(peak, delta)
        count += delta > threshold
    return dict(passed=count <= allowed_pixels, changed_pixels=count, max_delta=peak,
                threshold=threshold, allowed_pixels=allowed_pixels, width=w, height=h)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference')
    parser.add_argument('actual')
    parser.add_argument('--threshold', type=int, default=16)
    parser.add_argument('--allowed-pixels', type=int, default=0)
    args = parser.parse_args()
    try:
        result = compare(args.reference, args.actual, args.threshold, args.allowed_pixels)
    except (OSError, ValueError, zlib.error) as exc:
        result = dict(passed=False, error=str(exc))
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
