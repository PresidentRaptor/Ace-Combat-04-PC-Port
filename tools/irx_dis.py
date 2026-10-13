"""Disassemble an IOP module (.IRX) with its symbols and relocations applied.

The module is laid out at address 0 (as the IOP loader would before
relocating).  Relocated %hi/%lo pairs and jumps are annotated with the symbol
or address they resolve to.

usage: python tools/irx_dis.py MODULE.IRX [FUNCTION ...]
       (no function names: list the symbols)
"""
import struct
import sys

from ps2recomp.r5900 import decode

REG = ("zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 "
       "s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra").split()


def load(path):
    d = open(path, "rb").read()
    shoff, = struct.unpack_from("<I", d, 32)
    shnum, shstr = struct.unpack_from("<HH", d, 48)
    secs = [struct.unpack_from("<10I", d, shoff + 40 * i) for i in range(shnum)]
    stro = secs[shstr][4]
    def nm(o, base):
        return d[base + o:d.index(b"\0", base + o)].decode()
    named = {nm(s[0], stro): (i, s) for i, s in enumerate(secs)}
    size = max(s[3] + s[5] for s in secs if s[2] & 2)  # SHF_ALLOC
    img = bytearray(size)
    for s in secs:
        if s[2] & 2 and s[1] == 1:
            img[s[3]:s[3] + s[5]] = d[s[4]:s[4] + s[5]]
    syms = {}
    if ".symtab" in named:
        _, st = named[".symtab"]
        strtab = secs[st[6]][4]
        for k in range(st[5] // 16):
            n, v, sz, info, oth, shn = struct.unpack_from("<IIIBBH", d, st[4] + 16 * k)
            if n and shn and shn < 0xFF00 and (info & 0xF) in (0, 1, 2):
                name = nm(n, strtab)
                if not name.startswith(("gcc2", "__gnu", "_f", "_e")):
                    syms.setdefault(v, name)
    # relocations: offsets within .text that are relocated
    rel = {}
    for name, (i, s) in named.items():
        if s[1] == 9:  # SHT_REL
            for k in range(s[5] // 8):
                off, info = struct.unpack_from("<II", d, s[4] + 8 * k)
                rel[secs[s[7]][3] + off] = info & 0xFF
    return bytes(img), syms, rel


def main():
    img, syms, rel = load(sys.argv[1])
    by_name = {v: k for k, v in syms.items()}
    if len(sys.argv) == 2:
        for a in sorted(syms):
            print("%06X %s" % (a, syms[a]))
        return
    starts = sorted(syms)
    for fn in sys.argv[2:]:
        a = by_name[fn] if fn in by_name else int(fn, 16)
        nxt = min([s for s in starts if s > a] + [len(img)])
        print("\n%s:" % syms.get(a, fn))
        hi = {}
        for x in range(a, nxt, 4):
            w = struct.unpack_from("<I", img, x)[0]
            i = decode(w, x)
            op, rs, rt = w >> 26, (w >> 21) & 31, (w >> 16) & 31
            imm = w & 0xFFFF
            simm = imm - 0x10000 if imm & 0x8000 else imm
            note = ""
            if i.name in ("JAL", "J"):
                t = (w & 0x3FFFFFF) << 2
                note = syms.get(t, "%06X" % t)
            elif op == 0x0F:
                hi[rt] = imm << 16
            elif op in (0x09, 0x0D, 0x23, 0x2B, 0x21, 0x25, 0x20, 0x24, 0x28, 0x29) \
                    and rs in hi and rel.get(x) == 6:
                v = hi[rs] + simm if op != 0x0D else hi[rs] | imm
                note = syms.get(v, "&%06X" % v)
            if i.btarget and i.name.startswith("B"):
                ops = "%s, %s, %06X" % (REG[rs], REG[rt], i.btarget)
            elif op == 0:
                ops = "%s, %s, %s sa=%d" % (REG[i.rd], REG[rs], REG[rt], i.sa)
            elif i.name in ("J", "JAL"):
                ops = ""
            else:
                ops = "%s, %s, %d" % (REG[rt], REG[rs], simm)
            lab = syms.get(x)
            print("%s  %06X %-8s %-28s %s" % ("*" if lab and x != a else " ", x,
                                              i.name if not i.is_nop else "nop",
                                              ops if not i.is_nop else "", note))


if __name__ == "__main__":
    main()
