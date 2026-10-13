"""Recover GCC jump tables (`jr $reg` switches), standing in for IDA's.

Walks back from each non-$ra `jr` through a short window, tracking registers
that hold %hi/%lo constants, to find the `lw` that fetched the target and the
table it indexed.  The case count comes from the `sltiu` bound check when
there is one, otherwise the table is read until an entry leaves .text.

Writes an ida_db-shaped JSON (functions/names empty, switches filled) that
ps2recomp takes through --ida-db.

usage: python tools/find_switches.py ELF OUT_JSON
"""
import json
import sys

from ps2recomp.elf import ElfFile

WINDOW = 24


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def main():
    elf = ElfFile(sys.argv[1])
    ranges = elf.text_ranges()
    lo, hi = min(a for a, _ in ranges), max(b for _, b in ranges)

    def in_text(v):
        return lo <= v < hi and not v & 3

    def read(addr):
        try:
            return elf.word(addr)
        except Exception:
            return None

    switches = []
    unresolved = []
    for a in range(lo, hi, 4):
        w = elf.word(a)
        if w & 0xFC1FFFFF != 0x00000008 or (w >> 21) & 31 == 31:
            continue
        jreg = (w >> 21) & 31
        const = {}
        table = None
        bound = None
        start = max(lo, a - 4 * WINDOW)
        for b in range(start, a, 4):
            x = elf.word(b)
            op, rs, rt = x >> 26, (x >> 21) & 31, (x >> 16) & 31
            rd, fn, imm = (x >> 11) & 31, x & 63, x & 0xFFFF
            if op == 0x0F:                                  # lui
                const[rt] = imm << 16
            elif op == 0x09:                                # addiu
                if rs not in const and 16 <= rs <= 23:
                    # callee-saved base set up earlier in the function
                    for c in range(start - 4, max(lo, start - 4 * 400), -4):
                        y = elf.word(c)
                        if y >> 26 == 0x0F and (y >> 16) & 31 == rs:
                            const[rs] = (y & 0xFFFF) << 16
                            break
                        if y == 0x03E00008:     # jr $ra: previous function
                            break
                if rs in const:
                    const[rt] = (const[rs] + s16(imm)) & 0xFFFFFFFF
                else:
                    const.pop(rt, None)
            elif op == 0x0D and rs in const:                # ori
                const[rt] = const[rs] | imm
            elif op == 0x0B:                                # sltiu
                bound = imm
                const.pop(rt, None)
            elif op == 0 and fn in (0x21, 0x2D):            # addu / daddu
                if rs in const and rt not in const:
                    const[rd] = const[rs]
                elif rt in const and rs not in const:
                    const[rd] = const[rt]
                else:
                    const.pop(rd, None)
            elif op == 0x23 and rt == jreg:                 # lw jreg, off(base)
                table = (const[rs] + s16(imm)) & 0xFFFFFFFF if rs in const else None
            elif op != 0x2B and op != 0x04 and op != 0x05:
                # any other write: forget the destination
                if op == 0:
                    const.pop(rd, None)
                elif op not in (0x28, 0x29, 0x2B, 0x3F, 0x1F):
                    const.pop(rt, None)
        if table is None:
            unresolved.append(a)
            continue
        targets = []
        n = bound if bound else 1024
        for i in range(n):
            v = read(table + 4 * i)
            if v is None or not in_text(v) or abs(v - a) > 0x10000:
                break
            targets.append(v)
        if not targets:
            unresolved.append(a)
            continue
        switches.append(dict(ea=a, func=0, jumps=table, ncases=len(targets),
                             elbase=0, startea=a, targets=sorted(set(targets))))

    json.dump({"meta": {}, "segments": [], "functions": [], "names": {},
               "switches": switches}, open(sys.argv[2], "w"))
    print("%d switches recovered, %d indirect jumps unresolved%s"
          % (len(switches), len(unresolved),
             (": " + " ".join("%08X" % u for u in unresolved[:20]))
             if unresolved else ""))


if __name__ == "__main__":
    main()
