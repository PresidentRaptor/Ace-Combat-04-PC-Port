"""Recognize one bounded absolute jump-table idiom from verified image inputs.

This produces candidates, not global dominance or runtime immutability proofs.
No AC5 maps, inferred function boundaries or unbounded table scanning are used.
"""
from dataclasses import asdict, dataclass

from ac4_image import readonly_bytes
from r5900 import DecodeError, decode
from r5900_analysis import executable_words


@dataclass(frozen=True)
class SwitchCandidate:
    jump: int
    guard: int
    index_register: int
    table: int
    count: int
    default_target: int
    targets: tuple[int, ...]
    assumption: str = 'guard is sole entry; initial read-only table remains unchanged'


def match_switch(words, jump_pc, read_table, known_entries=()):
    """Strict SLTIU/BEQ/LUI/SLL/ADDIU/ADDU/LW/JR plus normal delay slot."""
    try:
        ins = [decode(words[pc], pc) for pc in range(jump_pc - 28, jump_pc + 8, 4)]
    except (KeyError, DecodeError):
        return None
    guard, branch, high, shift, low, add, load, jump, slot = ins
    if [i.mnemonic for i in ins[:-1]] != [
            'sltiu', 'beq', 'lui', 'sll', 'addiu', 'addu', 'lw', 'jr']:
        return None
    if slot.flow != 'normal' or slot.has_delay_slot:
        return None
    g, b, h, sh, lo, a, ld, j = [i.operands for i in ins[:-1]]
    count, index, condition = g['immediate'], g['rs'], g['rt']
    if not 0 < count <= 4096 or not condition or condition == index:
        return None
    if {b['rs'], b['rt']} != {condition, 0}:
        return None
    base, scaled = h['rt'], sh['rd']
    if not base or base == index or not scaled or base == scaled:
        return None
    if sh['rt'] != index or sh['shift'] != 2:
        return None
    if lo['rt'] != base or lo['rs'] != base:
        return None
    if {a['rs'], a['rt']} != {base, scaled} or a['rd'] != ld['base']:
        return None
    if not ld['base'] or not ld['rt'] or ld['rt'] != j['rs']:
        return None
    internal = set(range(guard.pc + 4, jump_pc + 8, 4))
    if internal.intersection(known_entries) or branch.target in internal:
        return None
    table = ((h['immediate'] << 16) + lo['immediate'] + ld['offset']) & 0xffffffff
    if table & 3:
        return None
    raw = read_table(table, count * 4)
    if raw is None or len(raw) != count * 4:
        return None
    targets = tuple(int.from_bytes(raw[i:i + 4], 'little') for i in range(0, len(raw), 4))
    if any(t & 3 or t not in words or t in internal for t in targets):
        return None
    try:
        for target in set(targets):
            decode(words[target], target)
    except DecodeError:
        return None
    return SwitchCandidate(jump_pc, guard.pc, index, table, count, branch.target, targets)


def recover_switches(data):
    words, entry, _ = executable_words(data)
    entries, indirect_sites = {entry}, []
    for pc, word in words.items():
        try:
            ins = decode(word, pc)
        except DecodeError:
            continue
        if ins.target is not None:
            entries.add(ins.target)
        if ins.mnemonic == 'jr' and ins.operands['rs'] != 31:
            indirect_sites.append(pc)
    candidates = []
    for pc in indirect_sites:
        found = match_switch(words, pc, lambda address, size: readonly_bytes(data, address, size), entries)
        if found is not None:
            candidates.append(found)
    return candidates


def switch_summary(candidates):
    return {
        'scope': 'bounded initial-image candidates; guard dominance and immutability not proven',
        'tables': len(candidates),
        'entries': sum(c.count for c in candidates),
        'distinct_targets': len({t for c in candidates for t in c.targets}),
        'candidates': [asdict(c) for c in candidates],
    }
