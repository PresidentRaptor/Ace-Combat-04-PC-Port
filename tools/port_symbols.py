"""Port SDK symbol names from a reference game (AC5) onto a target game (AC4).

Neither game ships a symbol table and there is no PS2 SDK on hand, so the
reference's already-identified SDK functions serve as the signature library:
each one's instructions are masked where a relink would change them (jump
targets, %hi/%lo halves, gp-relative offsets) and searched for in the target's
partitioned functions.  A unique, whole-function match names the target
function.  Functions that changed between SDK releases simply do not match.

usage: python tools/port_symbols.py REF_ELF REF_SYMBOLS REF_IDA_DB TARGET_ELF OUT
                                  [TARGET_IDA_DB TARGET_SEEDS [TARGET_MANUAL]]

Names pinned by hand in TARGET_MANUAL are never assigned by matching.
"""
import json
import sys
from collections import defaultdict
from difflib import SequenceMatcher

from ps2recomp.elf import ElfFile
from ps2recomp.analysis import Program

LUI, ADDIU, ORI, J, JAL = 0x0F, 0x09, 0x0D, 0x02, 0x03
MEMOPS = {0x20, 0x21, 0x23, 0x24, 0x25, 0x27, 0x28, 0x29, 0x2B, 0x37, 0x3F,
          0x1E, 0x1F, 0x31, 0x39, 0x35, 0x3D, 0x0B}


def mask_words(words):
    """Mask relocatable fields.  Registers loaded by LUI stay 'tainted' so the
    low half that completes the address is masked too."""
    out = []
    hi_regs = set()
    for w in words:
        op = w >> 26
        rs = (w >> 21) & 31
        rt = (w >> 16) & 31
        if op in (J, JAL):
            out.append(w & 0xFC000000)
            continue
        if op == LUI:
            hi_regs.add(rt)
            out.append(w & 0xFFFF0000)
            continue
        if (op in (ADDIU, ORI) or op in MEMOPS) and (rs in hi_regs or rs == 28):
            out.append(w & 0xFFFF0000)
            continue
        out.append(w)
    return tuple(out)


def func_words(prog, fn):
    return [prog.words[a] for a in sorted(set(fn.addrs) | set(fn.delay_slots))]


def partitioned(elf_path, ida_db=None, seeds=None):
    elf = ElfFile(elf_path)
    prog = Program(elf, ida_db, log=lambda *a: None)
    prog.seed()
    if seeds:
        for key in ("xref", "ptr"):
            for a in json.load(open(seeds)).get(key, ()):
                if prog.in_text(a):
                    prog.entries.add(a)
    prog.partition()
    return prog


def main():
    ref_elf, ref_syms, ref_db, tgt_elf, out = sys.argv[1:6]
    ref = partitioned(ref_elf, ref_db)
    syms = {int(k, 16): v["name"] for k, v in json.load(open(ref_syms)).items()
            if not k.startswith("//")}
    if len(sys.argv) > 8:
        pinned = {v["name"] for k, v in json.load(open(sys.argv[8])).items()
                  if not k.startswith("//")}
        syms = {a: n for a, n in syms.items() if n not in pinned}

    sigs = defaultdict(set)
    for a, name in syms.items():
        fn = ref.functions.get(a)
        if not fn or len(fn.addrs) < 4:
            continue
        sigs[mask_words(func_words(ref, fn))].add(name)

    tgt = partitioned(tgt_elf, *sys.argv[6:8])
    hits = defaultdict(list)
    for a, fn in tgt.functions.items():
        s = mask_words(func_words(tgt, fn))
        if s in sigs and len(sigs[s]) == 1:
            hits[next(iter(sigs[s]))].append(a)

    found = {}
    for name, addrs in hits.items():
        if len(addrs) == 1:
            found[addrs[0]] = name
    exact = len(found)

    # Fuzzy pass: the same SDK function from an older release usually differs
    # by a few instructions.  Score whole masked bodies and keep only clear
    # winners.
    ref_by_name = {}
    for a, name in syms.items():
        fn = ref.functions.get(a)
        if fn and len(fn.addrs) >= 12:
            ref_by_name.setdefault(name, a)
    tsigs = {a: mask_words(func_words(tgt, fn))
             for a, fn in tgt.functions.items()}
    taken = set(found)
    named = set(found.values())
    fuzzy = 0
    for name, ra in sorted(ref_by_name.items()):
        if name in named:
            continue
        rs = mask_words(func_words(ref, ref.functions[ra]))
        n = len(rs)
        scored = []
        for ta, ts in tsigs.items():
            if ta in taken or not (0.75 * n <= len(ts) <= 1.33 * n):
                continue
            sm = SequenceMatcher(None, rs, ts, autojunk=False)
            if sm.real_quick_ratio() < 0.8 or sm.quick_ratio() < 0.8:
                continue
            scored.append((sm.ratio(), ta))
        scored.sort(reverse=True)
        if scored and scored[0][0] >= 0.85 and (
                len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.05):
            found[scored[0][1]] = name
            taken.add(scored[0][1])
            named.add(name)
            fuzzy += 1

    # Call-graph pass: a matched pair's ordered call lists line up, so callees
    # of known functions inherit names until nothing new turns up.
    rev = {v: k for k, v in syms.items()}
    def calls(prog, fn):
        out = []
        for a in sorted(set(fn.addrs) | set(fn.delay_slots)):
            w = prog.words[a]
            if w >> 26 == JAL:
                out.append((a & 0xF0000000) | ((w & 0x03FFFFFF) << 2))
        return out
    graph = 0
    changed = True
    while changed:
        changed = False
        for ta, name in list(found.items()):
            ra = rev.get(name)
            if ra is None or ra not in ref.functions or ta not in tgt.functions:
                continue
            rc = calls(ref, ref.functions[ra])
            tc = calls(tgt, tgt.functions[ta])
            if len(rc) != len(tc):
                continue
            for r, t in zip(rc, tc):
                cn = syms.get(r)
                if not cn or cn in named or t in taken or t not in tgt.functions:
                    continue
                rf, tf = ref.functions.get(r), tgt.functions[t]
                if len(tf.addrs) < 8:
                    continue
                if rf and not (0.6 * len(rf.addrs) <= len(tf.addrs)
                               <= 1.66 * len(rf.addrs)):
                    continue
                found[t] = cn
                taken.add(t)
                named.add(cn)
                graph += 1
                changed = True
    print("exact %d, fuzzy %d, call-graph %d" % (exact, fuzzy, graph))
    json.dump({"0x%08X" % a: {"name": n, "lib": "ported from AC5", "words": 0}
               for a, n in sorted(found.items())}, open(out, "w"), indent=1)
    ambiguous = sum(1 for v in hits.values() if len(v) > 1)
    print("ref: %d named, %d unique signatures; target: %d functions"
          % (len(syms), len(sigs), len(tgt.functions)))
    print("matched %d symbols (%d ambiguous dropped) -> %s"
          % (len(found), ambiguous, out))


if __name__ == "__main__":
    main()
