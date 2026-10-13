"""Annotated disassembly of a .text range, for identifying functions by hand.

Shows partitioned function boundaries, known names, resolved %hi/%lo
constants with the string they point at, and call targets by name.

usage: python tools/listing.py ELF [--ida-db J] [--ida-seeds J] [--symbols J]...
                                START END   (hex)
       python tools/listing.py ELF ... --xref HEXADDR   (who builds this address)
"""
import argparse
import json
import re

from ps2recomp.elf import ElfFile
from ps2recomp.analysis import Program
from ps2recomp.r5900 import decode


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


REG = ("zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 "
       "s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra").split()


def ops(ins):
    if ins.is_nop:
        return ""
    if ins.btarget and ins.name.startswith("B"):
        return "%s, %s, %08X" % (REG[ins.rs], REG[ins.rt], ins.btarget)
    if ins.name in ("J", "JAL"):
        return "%08X" % ins.target
    if ins.name in ("JR", "JALR"):
        return REG[ins.rs]
    if ins.op == 0:
        return "%s, %s, %s sa=%d" % (REG[ins.rd], REG[ins.rs], REG[ins.rt], ins.sa)
    if ins.op == 0x0F:
        return "%s, 0x%04X" % (REG[ins.rt], ins.imm)
    return "%s, %s, %d" % (REG[ins.rt], REG[ins.rs], ins.simm)


def cstr(elf, a):
    out = b""
    try:
        while len(out) < 60:
            b = elf.word(a & ~3) >> (8 * (a & 3)) & 0xFF
            if b == 0:
                break
            if b < 0x20 or b > 0x7E:
                return None
            out += bytes([b])
            a += 1
    except Exception:
        return None
    return out.decode() if len(out) >= 3 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("elf")
    ap.add_argument("--ida-db")
    ap.add_argument("--ida-seeds")
    ap.add_argument("--symbols", action="append", default=[])
    ap.add_argument("--xref")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("range", nargs="*")
    a = ap.parse_intermixed_args()

    elf = ElfFile(a.elf)
    prog = Program(elf, a.ida_db, log=lambda *x: None)
    prog.seed()
    if a.ida_seeds:
        for k in ("xref", "ptr"):
            for v in json.load(open(a.ida_seeds)).get(k, ()):
                if prog.in_text(v):
                    prog.entries.add(v)
    prog.partition()
    names = {}
    for p in a.symbols:
        for k, v in json.load(open(p)).items():
            if not k.startswith("//"):
                names[int(k, 0)] = v["name"] if isinstance(v, dict) else v

    def nm(x):
        return names.get(x, "sub_%08X" % x)

    lo, hi = prog.lo, prog.hi
    # constant-propagate lui/addiu|ori within each function, per address
    consts = {}
    for f in prog.functions.values():
        regs = {}
        for x in sorted(set(f.addrs) | set(f.delay_slots)):
            w = prog.words[x]
            op, rs, rt = w >> 26, (w >> 21) & 31, (w >> 16) & 31
            if op == 0x0F:
                regs[rt] = (w & 0xFFFF) << 16
            elif op in (0x09, 0x0D) and rs in regs:
                v = (regs[rs] + s16(w & 0xFFFF)) & 0xFFFFFFFF if op == 0x09 \
                    else regs[rs] | (w & 0xFFFF)
                consts[x] = v
                regs[rt] = v
            elif op in (0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2B, 0x37,
                        0x3F, 0x1E, 0x1F, 0x31, 0x39) and rs in regs:
                consts[x] = (regs[rs] + s16(w & 0xFFFF)) & 0xFFFFFFFF

    if a.xref:
        t = int(a.xref, 16)
        for x, v in sorted(consts.items()):
            if v == t:
                print("%08X in %s" % (x, nm(prog.owner.get(x, 0))))
        for x, ins in prog.insns.items():
            if ins.name in ("JAL", "J") and ins.target == t:
                print("%08X %s in %s" % (x, ins.name, nm(prog.owner.get(x, 0))))
        return

    start, end = int(a.range[0], 16), int(a.range[1], 16)
    if a.summary:
        for fa in sorted(f for f in prog.functions if start <= f < end):
            f = prog.functions[fa]
            body = sorted(set(f.addrs) | set(f.delay_slots))
            callees, strs, consts_seen, sysc = [], [], [], []
            for x in body:
                ins = prog.insns[x]
                if ins.name == "JAL":
                    callees.append(nm(ins.target))
                if ins.name == "SYSCALL" and x - 4 in prog.insns:
                    sysc.append(prog.insns[x - 4].simm)
                if x in consts:
                    s = cstr(elf, consts[x])
                    if s:
                        strs.append(s)
                    elif consts[x] >> 24 == 0x80:
                        consts_seen.append("%08X" % consts[x])
            print("%08X %4d %-28s calls=[%s]%s%s%s" % (
                fa, len(body), nm(fa), ",".join(callees),
                " str=%r" % strs if strs else "",
                " k=%s" % consts_seen if consts_seen else "",
                " sys=%s" % sysc if sysc else ""))
        return
    for x in range(start, end, 4):
        if x in prog.functions:
            print("\n%s:  (%d insns)" % (nm(x), len(prog.functions[x].addrs)))
        ins = decode(prog.words[x], x)
        line = "  %08X %08X %-8s %s" % (x, prog.words[x], ins.name, ops(ins))
        if ins.name in ("JAL", "J"):
            line += "  -> " + nm(ins.target)
        if x in consts:
            s = cstr(elf, consts[x])
            line += "  ; =%08X" % consts[x] + (' "%s"' % s if s else "")
        if x in names and x not in prog.functions:
            line += "  <" + names[x] + ">"
        print(line)


if __name__ == "__main__":
    main()
