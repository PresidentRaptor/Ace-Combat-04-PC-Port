"""Conservative scalar reachability and candidate-word inventory, not function recovery.

Edges leave an instruction *after* the indicated delay-slot effect. The slot is
not enqueued as an ordinary instruction unless it is also reached independently.
A continuation is a speculative return site, never a proven callee return.
"""
import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path

from ac4_image import ImageError, inspect, read_layout
from r5900 import DecodeError, Instruction, MASK, decode


@dataclass(frozen=True)
class Edge:
    source: int
    target: int | None
    kind: str
    condition: str = 'always'
    delay_slot: int | None = None
    slot_effect: str = 'none'  # executed, annulled, none
    traversable: bool = True


@dataclass
class Analysis:
    instructions: dict[int, Instruction]
    edges: list[Edge]
    diagnostics: list[dict]
    visited: list[int]

    def to_dict(self):
        return {'instructions': [asdict(self.instructions[p]) for p in sorted(self.instructions)],
                'edges': [asdict(e) for e in self.edges],
                'diagnostics': self.diagnostics, 'visited': self.visited}


def analyze(words: dict[int, int], entries) -> Analysis:
    """Explore both outcomes without register assumptions, bounded by supplied words.

    A JR $ra is only a return-shaped unresolved edge. No function boundaries are
    inferred. Architectural exceptions from arithmetic/memory and asynchronous
    events are outside this normal-flow graph; explicit traps are represented.
    """
    for pc, word in words.items():
        if not isinstance(pc, int) or not isinstance(word, int):
            raise ValueError('addresses and words must be integers')
        if not 0 <= pc <= MASK or pc & 3 or not 0 <= word <= MASK:
            raise ValueError('unaligned/out-of-range address or word')
    pending = list(entries)
    if any(not isinstance(p, int) or not 0 <= p <= MASK or p & 3 for p in pending):
        raise ValueError('invalid entry address')
    result = Analysis({}, [], [], [])
    seen = set()
    failures = set()

    def diagnostic(pc, reason):
        if (pc, reason) not in failures:
            failures.add((pc, reason))
            result.diagnostics.append({'pc': pc, 'reason': reason})

    def fetch(pc):
        if pc in result.instructions:
            return result.instructions[pc]
        if pc not in words:
            diagnostic(pc, 'outside supplied file-backed words')
            return None
        try:
            instruction = decode(words[pc], pc)
        except DecodeError as error:
            diagnostic(pc, str(error))
            return None
        result.instructions[pc] = instruction
        return instruction

    def edge(source, target, kind, condition='always', slot=None, effect='none', valid=True):
        result.edges.append(Edge(source, target, kind, condition, slot, effect, valid))
        if valid and target is not None:
            pending.append(target)

    while pending:
        pc = pending.pop()
        if pc in seen:
            continue
        seen.add(pc)
        result.visited.append(pc)
        ins = fetch(pc)
        if ins is None:
            continue
        after = (pc + 4) & MASK
        if not ins.has_delay_slot:
            if ins.flow in ('trap', 'exception'):
                edge(pc, None, 'exception', 'trap' if ins.flow == 'trap' else 'always')
            if ins.flow != 'exception':
                edge(pc, after, 'fallthrough', 'no-trap' if ins.flow == 'trap' else 'always')
            continue

        slot = fetch(after)
        valid = slot is not None
        if slot is not None and (slot.has_delay_slot or slot.mnemonic == 'sync'):
            diagnostic(after, 'unsupported/undefined control transfer or SYNC in delay slot')
            valid = False
        elif slot is not None and slot.flow in ('trap', 'exception'):
            condition = 'taken' if ins.likely else 'always'
            if slot.flow == 'trap':
                condition = 'taken-and-slot-trap' if ins.likely else 'slot-trap'
            edge(pc, None, 'exception', condition, after, 'executed')
            if slot.flow == 'exception':
                valid = False
        resume = (pc + 8) & MASK
        if ins.flow == 'branch':
            edge(pc, ins.target, 'call' if ins.link_register is not None else 'branch',
                 'taken', after, 'executed', valid)
            edge(pc, resume, 'fallthrough', 'untaken', after,
                 'annulled' if ins.likely else 'executed', True if ins.likely else valid)
        else:
            edge(pc, ins.target, ins.flow, slot=after, effect='executed', valid=valid)
        if ins.link_register is not None:
            # Separate from the actual branch outcomes: the callee might never return.
            edge(pc, resume, 'continuation', 'if-callee-returns', valid=valid)
    result.visited.sort()
    return result


def stream_words(data: bytes, base: int) -> dict[int, int]:
    if base & 3 or not 0 <= base <= MASK or len(data) % 4 or base + len(data) > MASK + 1:
        raise ValueError('expected aligned, nonwrapping whole-word byte range')
    return {base + i: int.from_bytes(data[i:i + 4], 'little') for i in range(0, len(data), 4)}


def executable_words(data: bytes):
    """Accept only the verified supported AC4 image; never inspect zero-fill as code."""
    metadata = inspect(data)
    entry, segments = read_layout(data)
    words = {}
    for segment in segments:
        if segment.flags & 1:
            words.update(stream_words(data[segment.offset:segment.offset + segment.file_size], segment.address))
    return words, entry, metadata


def inventory(words):
    """Linear candidate inventory, including possible embedded data; not code coverage."""
    decoded, rejected = Counter(), Counter()
    for pc, word in words.items():
        try:
            decoded[decode(word, pc).mnemonic] += 1
        except DecodeError as error:
            rejected[str(error)] += 1
    return {'candidate_words': len(words), 'decoded': dict(sorted(decoded.items())),
            'rejected': dict(sorted(rejected.items()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--words', nargs='+', type=lambda s: int(s, 16), help='synthetic hex words')
    source.add_argument('--elf', type=Path)
    source.add_argument('--iso', type=Path)
    parser.add_argument('--base', type=lambda s: int(s, 0), default=0x1000)
    parser.add_argument('--entry', action='append', type=lambda s: int(s, 0), help='repeat for additional known entries')
    parser.add_argument('--summary', action='store_true', help='metadata/counts only; no instruction words or graph')
    args = parser.parse_args()
    try:
        metadata = None
        if args.words is not None:
            if any(not 0 <= w <= MASK for w in args.words):
                raise ValueError('word outside 32 bits')
            words = stream_words(b''.join(w.to_bytes(4, 'little') for w in args.words), args.base)
            entry = args.base
        else:
            if args.iso:
                from ac4_disc import executable_from_iso
                with args.iso.open('rb') as stream:
                    data, location = executable_from_iso(stream)
            else:
                data = args.elf.read_bytes()
            words, entry, metadata = executable_words(data)
            if args.iso:
                metadata['iso_executable'] = location
        result = analyze(words, args.entry if args.entry is not None else [entry])
        output = {'image': metadata, 'inventory': inventory(words),
                  'reachability': {'visited_addresses': len(result.visited),
                                   'decoded_addresses_including_slots': len(result.instructions),
                                   'edges': len(result.edges),
                                   'unresolved_edges': sum(e.target is None for e in result.edges),
                                   'unresolved_register_edges': sum(
                                       e.target is None and e.kind in ('call', 'indirect', 'return')
                                       for e in result.edges),
                                   'blocked_edges': sum(not e.traversable for e in result.edges),
                                   'diagnostics': result.diagnostics}}
        if not args.summary:
            output['analysis'] = result.to_dict()
    except (OSError, ImageError, ValueError) as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
