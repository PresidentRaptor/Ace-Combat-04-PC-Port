"""Make replacement ("HD") texture packs for the AC4 runtime.

  export DIR             PNGs and a labelled contact sheet of saved textures
  import ORIGINAL EDITED package one hand-edited PNG
  upscale DUMP           upscale every saved texture with Real-ESRGAN into a pack

Textures are saved by the game with "Save textures for upscaling" in the F4
menu (into textures/dump).  A pack is a folder of <id>_<w>x<h>.pam files; the
game reads textures/hd and its subfolders, files directly in textures/hd
first, so a hand-made replacement wins over a generated one.

Requires Pillow; `upscale` also needs realesrgan-ncnn-vulkan
(https://github.com/xinntao/Real-ESRGAN/releases, the ncnn Vulkan build).
No game assets are downloaded or bundled: everything is made from your own
copy of the game, and packs stay on your machine.
"""
import argparse
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


def identity(rgba, w, h):
    value = 14695981039346656037
    for byte in struct.pack('<II', w, h) + rgba:
        value = ((value ^ byte) * 1099511628211) & 0xffffffffffffffff
    return f'{value:016x}_{w}x{h}'


def read_pam(path):
    with Path(path).open('rb') as f:
        if f.readline().strip() != b'P7':
            raise ValueError('Expected a P7 PAM texture capture')
        header = {}
        for _ in range(16):
            line = f.readline().strip()
            if line == b'ENDHDR':
                break
            key, value = line.split(maxsplit=1)
            header[key] = value
        else:
            raise ValueError('Unterminated PAM header')
        w, h = int(header[b'WIDTH']), int(header[b'HEIGHT'])
        if not (0 < w <= 4096 and 0 < h <= 4096):
            raise ValueError('Invalid texture dimensions')
        if header.get(b'DEPTH') != b'4' or header.get(b'MAXVAL') != b'255' or header.get(b'TUPLTYPE') != b'RGB_ALPHA':
            raise ValueError('Expected 8-bit RGBA')
        rgba = f.read(w*h*4 + 1)
        if len(rgba) != w*h*4:
            raise ValueError('Texture payload size mismatch')
        return rgba, w, h


def write_pam(path, rgba, w, h):
    if len(rgba) != w*h*4:
        raise ValueError('RGBA size mismatch')
    Path(path).write_bytes(f'P7\nWIDTH {w}\nHEIGHT {h}\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n'.encode() + rgba)


def read_info(dump):
    """dump_info.tsv: name, wms, wmt, region (GS CLAMP modes the texture was drawn with)."""
    info = {}
    path = Path(dump) / 'dump_info.tsv'
    if path.exists():
        for line in path.read_text().splitlines():
            parts = line.split('\t')
            if len(parts) >= 4:
                info[parts[0]] = (int(parts[1]), int(parts[2]), int(parts[3]))
    return info


def classify(im):
    """Pick how to upscale a texture.  Returns (kind, alpha_mode) or None to skip.

    kind 'photo' (terrain, skins, the hangar) or 'art' (text, HUD and menu art:
    few colours); alpha 'cutout' (mostly fully opaque or fully clear: glyphs,
    decals -- upscaled for crisp edges), 'material' (anything else: smooth
    resize, as the game uses it as a blend weight) or 'opaque'."""
    from PIL import ImageFilter, ImageStat
    rgb = im.convert('RGB')
    alpha = im.getchannel('A')
    hist = alpha.histogram()
    n = im.width * im.height
    clear, solid = hist[0], hist[255]
    if clear >= n * 0.995:
        return None                                # nothing visible
    if solid == n:
        amode = 'opaque'
    elif clear + solid >= n * 0.9:
        amode = 'cutout'
    else:
        amode = 'material'
    colours = rgb.getcolors(64)
    if amode != 'opaque':
        # judge detail by what is visible
        bg = rgb.copy()
        bg.paste((0, 0, 0), mask=alpha.point(lambda a: 255 if a < 8 else 0))
        rgb = bg
    detail = ImageStat.Stat(rgb.convert('L').filter(ImageFilter.FIND_EDGES)).mean[0]
    if detail < 1.5 and amode != 'cutout':
        return None                                # smooth gradients, glows: no gain
    kind = 'art' if colours is not None and len(colours) <= 32 else 'photo'
    return kind, amode


def pad(im, wrap_u, wrap_v, border):
    """Extend the borders the way the GS samples past them -- the opposite edge
    for REPEAT/REGION_REPEAT (0, 3), the edge itself for CLAMP/REGION_CLAMP --
    so the upscaler sees the right neighbours and tiles meet without seams."""
    from PIL import Image

    def extend(img, horizontal, repeat):
        w, h = img.size
        if not horizontal:
            img = img.transpose(Image.Transpose.TRANSPOSE)
            w, h = h, w
        if repeat:
            left = img.crop((w - border, 0, w, h)) if w >= border else img.resize((border, h))
            right = img.crop((0, 0, border, h)) if w >= border else img.resize((border, h))
        else:
            left = img.crop((0, 0, 1, h)).resize((border, h), Image.Resampling.NEAREST)
            right = img.crop((w - 1, 0, w, h)).resize((border, h), Image.Resampling.NEAREST)
        out = Image.new(img.mode, (w + 2 * border, h))
        out.paste(left, (0, 0))
        out.paste(img, (border, 0))
        out.paste(right, (border + w, 0))
        return out if horizontal else out.transpose(Image.Transpose.TRANSPOSE)

    return extend(extend(im, True, wrap_u in (0, 3)), False, wrap_v in (0, 3))


def run_esrgan(exe, model, src, dst):
    cmd = [str(exe), '-i', str(src), '-o', str(dst), '-n', model, '-s', '4', '-f', 'png']
    r = subprocess.run(cmd, cwd=str(Path(exe).parent), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'{Path(exe).name} failed ({r.returncode}):\n{r.stderr[-2000:]}')


def upscale(args):
    from PIL import Image
    dump = Path(args.dump)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    exe = Path(args.esrgan)
    if not exe.exists():
        raise SystemExit(f'Real-ESRGAN not found at {exe} (use --esrgan)')
    info = read_info(dump)
    have = {p.stem for p in Path(args.output).parent.rglob('*.pam')} | {p.stem for p in out.rglob('*.pam')}
    jobs = []
    skipped = {'small': 0, 'large': 0, 'flat': 0, 'done': 0, 'strip': 0}
    for path in sorted(dump.glob('*.pam')):
        name = path.stem
        if name in have:
            skipped['done'] += 1
            continue
        rgba, w, h = read_pam(path)
        if min(w, h) < args.min_size:
            skipped['small'] += 1
            continue
        if max(w, h) > args.max_aspect * min(w, h):
            # a narrow decode running past its picture into unrelated memory
            # (AC4's 64x1024 strips): changes with that memory, never reused
            skipped['strip'] += 1
            continue
        scale = 4
        while scale > 1 and max(w, h) * scale > args.max_size:
            scale //= 2
        if scale < 2:
            skipped['large'] += 1
            continue
        im = Image.frombytes('RGBA', (w, h), rgba)
        cls = classify(im)
        if cls is None:
            skipped['flat'] += 1
            continue
        wms, wmt, region = info.get(name, (1, 1, 0))
        jobs.append((name, im, scale, cls, wms, wmt))
    print(f'{len(jobs)} textures to upscale; skipped: {skipped["done"]} already in a pack, '
          f'{skipped["small"]} smaller than {args.min_size}px, {skipped["large"]} too large, '
          f'{skipped["flat"]} without detail to gain, {skipped["strip"]} narrow strips')
    if not jobs:
        return
    border = 8
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        dirs = {}
        for name, im, scale, (kind, amode), wms, wmt in jobs:
            model = 'realesrgan-x4plus-anime' if kind == 'art' else 'realesrgan-x4plus'
            d = tmp / f'in_{model}'
            d.mkdir(exist_ok=True)
            dirs[model] = d
            padded = pad(im, wms, wmt, border)
            padded.convert('RGB').save(d / f'{name}.png')
            if amode == 'cutout':
                a = tmp / 'in_realesrgan-x4plus-anime'
                a.mkdir(exist_ok=True)
                dirs['realesrgan-x4plus-anime'] = a
                padded.getchannel('A').convert('RGB').save(a / f'{name}__alpha.png')
        for model, d in dirs.items():
            o = tmp / f'out_{model}'
            o.mkdir()
            print(f'Real-ESRGAN {model}: {len(list(d.glob("*.png")))} images ...', flush=True)
            run_esrgan(exe, model, d, o)
        done = 0
        for name, im, scale, (kind, amode), wms, wmt in jobs:
            model = 'realesrgan-x4plus-anime' if kind == 'art' else 'realesrgan-x4plus'
            w, h = im.size
            up = Image.open(tmp / f'out_{model}' / f'{name}.png').convert('RGB')
            up = up.crop((border*4, border*4, border*4 + w*4, border*4 + h*4))
            if amode == 'cutout':
                a = Image.open(tmp / 'out_realesrgan-x4plus-anime' / f'{name}__alpha.png').convert('L')
                a = a.crop((border*4, border*4, border*4 + w*4, border*4 + h*4))
            elif amode == 'material':
                a = im.getchannel('A').resize((w*4, h*4), Image.Resampling.BICUBIC)
            else:
                a = None
            if scale != 4:
                up = up.resize((w*scale, h*scale), Image.Resampling.LANCZOS)
                if a is not None:
                    a = a.resize((w*scale, h*scale), Image.Resampling.LANCZOS)
            if a is None:
                a = Image.new('L', up.size, 255)
            up.putalpha(a)
            write_pam(out / f'{name}.pam', up.tobytes(), up.width, up.height)
            done += 1
    print(f'Wrote {done} replacement textures to {out}. Restart the game to load them.')


def main():
    from PIL import Image, ImageDraw
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export', help='Convert captures to PNGs and a labeled contact sheet')
    export.add_argument('directory', type=Path)
    imp = sub.add_parser('import', help='Package an edited PNG using its original capture identity')
    imp.add_argument('original', type=Path)
    imp.add_argument('edited', type=Path)
    imp.add_argument('--output', type=Path, default=Path('textures/hd'))
    imp.add_argument('--scale', type=int, choices=range(1,9), help='Resize for an exact integer texture scale')
    imp.add_argument('--alpha', choices=['original', 'edited'], default='original',
                     help='Preserve original material/opacity values by default')
    up = sub.add_parser('upscale', help='Upscale every saved texture with Real-ESRGAN into a pack')
    up.add_argument('dump', type=Path, help='folder of saved textures (textures/dump)')
    up.add_argument('--output', type=Path, default=Path('textures/hd/upscaled'))
    up.add_argument('--esrgan', type=Path, default=Path('tools/realesrgan/realesrgan-ncnn-vulkan.exe'))
    up.add_argument('--max-size', type=int, default=2048,
                    help='largest replacement side; big textures get 2x instead of 4x (default 2048)')
    up.add_argument('--min-size', type=int, default=16, help='skip textures smaller than this')
    up.add_argument('--max-aspect', type=int, default=8, help='skip textures longer than this times their width')
    args = parser.parse_args()
    if args.command == 'upscale':
        upscale(args)
    elif args.command == 'export':
        files = sorted(args.directory.glob('*.pam'))
        sheet = Image.new('RGB', (1000, 285*max(1,(len(files)+3)//4)), (25,25,25))
        for i,path in enumerate(files):
            rgba,w,h = read_pam(path)
            im = Image.frombytes('RGBA', (w,h), rgba)
            im.save(path.with_suffix('.png'))
            tile = Image.new('RGB', (250,285), (65,65,65))
            im.thumbnail((246,244))
            tile.paste(im, (2,2), im)
            ImageDraw.Draw(tile).text((4,250), f'{i}: {path.stem}\n{w}x{h}', fill='white')
            sheet.paste(tile, ((i%4)*250,(i//4)*285))
        sheet.save(args.directory/'catalog.png')
        print(f'Exported {len(files)} textures to {args.directory}')
    else:
        rgba,w,h = read_pam(args.original)
        name = identity(rgba,w,h)
        if name != args.original.stem:
            raise ValueError('Original capture name does not match its pixel contents')
        with Image.open(args.edited) as source:
            im = source.convert('RGBA')
        if args.scale:
            im = im.resize((w*args.scale,h*args.scale), Image.Resampling.LANCZOS)
        x,y = im.size
        if x > 4096 or y > 4096 or x < w or y < h or x%w or y%h or x//w != y//h or x//w > 8:
            raise ValueError('Use matching integer scales 1..8, at most 4096x4096')
        if args.alpha == 'original':
            alpha = Image.frombytes('RGBA', (w,h), rgba).getchannel('A')
            im.putalpha(alpha.resize((x,y), Image.Resampling.BILINEAR))
        args.output.mkdir(parents=True, exist_ok=True)
        dest = args.output/(name+'.pam')
        write_pam(dest, im.tobytes(), x, y)
        print(f'{dest}: {w}x{h} -> {x}x{y}. Restart the game to load it.')


if __name__ == '__main__':
    main()
