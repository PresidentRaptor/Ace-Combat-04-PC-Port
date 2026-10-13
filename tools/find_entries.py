"""Heuristic function entry finder, standing in for an IDA export.

Seeds an ida_seeds-style JSON ({"xref": [...]}) with:
  - the first instruction after each `jr $ra` + delay slot (skipping nop
    padding), when no branch in the preceding code jumps past it;
  - every `addiu $sp, $sp, -N` that opens a frame right after padding or a
    return;
  - text addresses that appear as 32-bit words in data sections (pointer
    tables, vtables, callbacks), when they land on an instruction boundary
    right after a return or padding.

usage: python tools/find_entries.py ELF OUT_JSON
"""
import json
import sys

from ps2recomp.elf import ElfFile
from ps2recomp.r5900 import decode, CAT_BRANCH, CAT_BRANCH_LIKELY

JR_RA = 0x03E00008


def main():
    elf = ElfFile(sys.argv[1])
    lo, hi = min(a for a, _ in elf.text_ranges()), max(b for _, b in elf.text_ranges())
    words = {a: elf.word(a) for a in range(lo, hi, 4)}

    # furthest forward branch target reaching each address, to avoid splitting
    # a function at a mid-body return: an address some earlier branch jumps
    # to (or past) is still inside that function
    reach = {}
    far = 0
    for a in range(lo, hi, 4):
        ins = decode(words[a], a)
        if ins.cat in (CAT_BRANCH, CAT_BRANCH_LIKELY) and ins.btarget > a:
            far = max(far, ins.btarget)
        reach[a] = far

    def after_boundary(a):
        """a follows a return/padding: previous non-nop is the delay slot of
        `jr $ra` (or of an unconditional `j`), or a is at .text start."""
        p = a - 4
        while p >= lo and words[p] == 0:
            p -= 4
        if p < lo:
            return True
        # `jr $ra; nop`: the delay slot was skipped over as padding
        if (words[p] == JR_RA or words[p] >> 26 == 2) and p + 4 < a:
            return reach.get(p, 0) < a
        if p - 4 >= lo and (words[p - 4] == JR_RA or words[p - 4] >> 26 == 2):
            # a frame being opened is a function start, never a delay slot
            if words[p] & 0xFFFF8000 == 0x27BD8000:
                return False
            return reach.get(p - 4, 0) < a
        return False

    entries = set()
    for a in range(lo, hi, 4):
        w = words[a]
        if w == 0:
            continue
        if after_boundary(a):
            entries.add(a)

    ptr = set()
    for sec in elf.sections:
        data = getattr(sec, "data", None)
        if not data or not getattr(sec, "addr", 0) or sec.name.startswith(".text"):
            continue
        for i in range(0, len(data) - 3, 4):
            v = int.from_bytes(data[i:i + 4], "little")
            if lo <= v < hi and not v & 3 and words[v] and after_boundary(v):
                ptr.add(v)

    json.dump({"xref": sorted(entries), "ptr": sorted(ptr)},
              open(sys.argv[2], "w"))
    print("%d boundary entries, %d data pointers" % (len(entries), len(ptr)))


if __name__ == "__main__":
    main()
