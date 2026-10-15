"""Repeatable local static checks against the verified USA AC4 executable.

Reports metadata only. These checks do not run the game or prove CPU semantics.
The expected addresses/operands were reviewed directly from the local disc;
no inherited symbol maps or executable bytes are stored here.
"""
import argparse
import json
from pathlib import Path

from ac4_disc import executable_from_iso
from ac4_image import ImageError
from r5900 import decode
from r5900_analysis import analyze, executable_words, inventory


CASES = (
    (0x10002c, 'bne', 0x100018, 'addiu'),
    (0x100084, 'jal', 0x26b2d0, 'sll'),
    (0x1000c8, 'jr', None, 'addiu'),
    (0x100354, 'beql', 0x10036c, 'andi'),
    (0x1027e0, 'bc1tl', 0x1027f4, 'lwc1'),
)


def check_case(words, pc, mnemonic, target, slot_name):
    def require(condition, description):
        if not condition:
            raise ValueError(f'{pc:#010x}: {description}')

    ins = decode(words[pc], pc)
    slot_pc = (pc + 4) & 0xffffffff
    slot = decode(words[slot_pc], slot_pc)
    require(ins.mnemonic == mnemonic and ins.target == target, 'instruction/target mismatch')
    require(slot.mnemonic == slot_name, 'delay-slot instruction mismatch')
    graph = analyze({pc: words[pc], slot_pc: words[slot_pc]}, [pc])
    edges = [e for e in graph.edges if e.source == pc]
    executed = [e for e in edges if e.target == target and e.slot_effect == 'executed']
    require(len(executed) == 1 and executed[0].traversable, 'executed-slot edge mismatch')
    if ins.flow == 'branch':
        untaken = [e for e in edges if e.condition == 'untaken']
        require(len(untaken) == 1 and untaken[0].target == (pc + 8) & 0xffffffff,
                'untaken destination mismatch')
        require(untaken[0].slot_effect == ('annulled' if ins.likely else 'executed'),
                'untaken slot effect mismatch')
    if mnemonic == 'jal':
        require(ins.link_register == 31 and ins.link_address == (pc + 8) & 0xffffffff,
                'call link mismatch')
    if mnemonic == 'jr':
        require(ins.operands['rs'] == 31 and executed[0].kind == 'return',
                'return must retain unresolved register target')
    return {'address': f'0x{pc:08x}', 'mnemonic': mnemonic,
            'target': f'0x{target:08x}' if target is not None else None,
            'slot': slot_name, 'passed': True}


def validate(data):
    words, entry, metadata = executable_words(data)
    checks = [check_case(words, *case) for case in CASES]
    counts = inventory(words)
    graph = analyze(words, [entry])
    return {
        'scope': 'local-static-inspection; not execution or gameplay validation',
        'image': metadata,
        'cases': checks,
        'inventory': {'candidate_words': counts['candidate_words'],
                      'accepted_words': sum(counts['decoded'].values()),
                      'rejected_words': sum(counts['rejected'].values()),
                      'rejected': counts['rejected']},
        'entry_analysis': {'visited_addresses': len(graph.visited),
                           'decoded_addresses_including_slots': len(graph.instructions),
                           'edges': len(graph.edges),
                           'diagnostics': graph.diagnostics,
                           'exception_sites': [f'0x{e.source:08x}' for e in graph.edges
                                               if e.kind == 'exception']},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--iso', type=Path)
    source.add_argument('--elf', type=Path)
    args = parser.parse_args()
    try:
        if args.iso:
            with args.iso.open('rb') as stream:
                data, _ = executable_from_iso(stream)
        else:
            data = args.elf.read_bytes()
        result = validate(data)
    except (OSError, ValueError, KeyError, ImageError) as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
