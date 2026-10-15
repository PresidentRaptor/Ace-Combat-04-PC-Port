"""Conservative GPR constant propagation over the existing partial flow graph.

Results apply only to the graph and entry assumptions supplied. No jump tables,
memory contents, ABI preservation or complete function boundaries are inferred.
Resolved register targets are reported; they do not extend graph traversal yet.
"""
from collections import deque
from dataclasses import asdict, dataclass

from r5900_analysis import analyze

U64 = (1 << 64) - 1
UNKNOWN = (0,) + (None,) * 31


def signed(value, width):
    value &= (1 << width) - 1
    return value - (1 << width) if value >> (width - 1) else value


def transfer(ins, state):
    """Track a small defined scalar subset; all other writes lose information."""
    out = list(state)
    o, name = ins.operands, ins.mnemonic

    def put(register, value):
        if register:
            out[register] = None if value is None else value & U64

    def binary(operation, left, right):
        return None if left is None or right is None else operation(left, right)

    if ins.has_delay_slot:
        if ins.link_register is not None:
            put(ins.link_register, ins.link_address)
    elif name == 'lui':
        put(o['rt'], signed(o['immediate'] << 16, 32))
    elif name in ('ori', 'andi', 'xori', 'addiu', 'daddiu'):
        left, right = state[o['rs']], o['immediate']
        operation = {'ori': lambda a, b: a | b, 'andi': lambda a, b: a & b,
                     'xori': lambda a, b: a ^ b, 'addiu': lambda a, b: signed(a + b, 32),
                     'daddiu': lambda a, b: a + b}[name]
        put(o['rt'], binary(operation, left, right))
    elif name in ('addu', 'subu', 'daddu', 'dsubu', 'and', 'or', 'xor', 'nor', 'slt', 'sltu'):
        operation = {'addu': lambda a, b: signed(a + b, 32),
                     'subu': lambda a, b: signed(a - b, 32),
                     'daddu': lambda a, b: a + b, 'dsubu': lambda a, b: a - b,
                     'and': lambda a, b: a & b, 'or': lambda a, b: a | b,
                     'xor': lambda a, b: a ^ b, 'nor': lambda a, b: ~(a | b),
                     'slt': lambda a, b: int(signed(a, 64) < signed(b, 64)),
                     'sltu': lambda a, b: int(a < b)}[name]
        put(o['rd'], binary(operation, state[o['rs']], state[o['rt']]))
    elif name in ('movz', 'movn'):
        condition = state[o['rt']]
        source, previous = state[o['rs']], state[o['rd']]
        if condition is None:
            value = source if source == previous else None
        else:
            move = (condition == 0) if name == 'movz' else (condition != 0)
            value = source if move else previous
        put(o['rd'], value)
    elif name in ('sll', 'srl', 'sra', 'dsll', 'dsll32', 'dsrl', 'dsrl32', 'dsra', 'dsra32'):
        value, shift = state[o['rt']], o['shift']
        if value is not None:
            if name == 'sll':
                value = signed(value << shift, 32)
            elif name == 'srl':
                value = signed((value & 0xffffffff) >> shift, 32)
            elif name == 'sra':
                value = signed(value, 32) >> shift
            elif name.startswith('dsll'):
                value <<= shift
            elif name.startswith('dsrl'):
                value >>= shift
            else:
                value = signed(value, 64) >> shift
        put(o['rd'], value)
    elif name in ('lb', 'lbu', 'lh', 'lhu', 'lw', 'lwu', 'ld', 'lq',
                   'lwl', 'lwr', 'ldl', 'ldr', 'mfc0', 'mfc1', 'qmfc2',
                   'cfc1', 'cfc2', 'mfps', 'mfpc', 'mfbpc', 'mfiab', 'mfiabm',
                   'mfdab', 'mfdabm', 'mfdvb', 'mfdvbm'):
        put(o['rt'], None)
    elif (name in ('sb', 'sh', 'sw', 'sd', 'sq', 'swl', 'swr', 'sdl', 'sdr',
                   'lwc1', 'swc1', 'lqc2', 'sqc2', 'sync', 'pref', 'ei', 'di',
                   'mtc0', 'mtc1', 'ctc1', 'ctc2', 'qmtc2', 'mthi', 'mtlo',
                   'mthi1', 'mtlo1', 'mtsa', 'mtsab', 'mtsah', 'pmthi', 'pmtlo',
                   'pmthl.lw', 'mtps', 'mtpc', 'mtbpc', 'mtiab', 'mtiabm',
                   'mtdab', 'mtdabm', 'mtdvb', 'mtdvbm', 'tlbr', 'tlbwi', 'tlbwr', 'tlbp')
          or name.startswith(('v', 'cache.'))):
        pass  # No EE GPR destination; other machine state is outside this model.
    elif 'rd' in o:
        put(o['rd'], None)
    else:
        # Unknown effects must never preserve a stale guessed target. In
        # particular we make no assumptions about HI/LO or runtime callbacks.
        return UNKNOWN
    out[0] = 0
    return tuple(out)


@dataclass(frozen=True)
class RegisterTarget:
    source: int
    register: int
    target: int | None
    status: str


def resolve_indirects(words, entries, graph=None):
    """Meet constants from all supplied graph paths; unknown wins at merges.

    Every entry starts without register assumptions. Call-return continuations
    discard all GPR facts, even registers normally callee-saved by an ABI.
    Register jump targets are sampled before the link/slot writes. This is a
    normal-flow model; runtime exceptions/interrupts are not simulated.
    """
    entries = list(entries)
    graph = graph if graph is not None else analyze(words, entries)
    edges = {}
    for edge in graph.edges:
        edges.setdefault(edge.source, []).append(edge)
    states = {}
    pending, queued = deque(), set()

    def merge(pc, incoming):
        previous = states.get(pc)
        joined = incoming if previous is None else tuple(
            a if a == b else None for a, b in zip(previous, incoming))
        if joined != previous:
            states[pc] = joined
            if pc not in queued:
                pending.append(pc)
                queued.add(pc)

    for entry in entries:
        merge(entry, UNKNOWN)
    while pending:
        pc = pending.popleft()
        queued.remove(pc)
        ins = graph.instructions.get(pc)
        if ins is None:
            continue
        after = transfer(ins, states[pc])
        for edge in edges.get(pc, ()):
            if not edge.traversable or edge.target is None:
                continue
            outgoing = after
            if edge.kind == 'continuation':
                outgoing = UNKNOWN
            elif edge.slot_effect == 'executed':
                slot = graph.instructions.get(edge.delay_slot)
                if slot is None:
                    continue
                outgoing = transfer(slot, outgoing)
            merge(edge.target, outgoing)
    targets = []
    for pc in sorted(states):
        ins = graph.instructions.get(pc)
        if ins is None or ins.mnemonic not in ('jr', 'jalr'):
            continue
        register = ins.operands['rs']
        value = states[pc][register]
        status, target = 'unknown-register', None
        if value is not None:
            if value >> 32 not in (0, 0xffffffff):
                status = 'noncanonical-address'
            elif value & 3:
                status = 'unaligned-address'
            else:
                target = value & 0xffffffff
                status = 'constant-on-supplied-paths'
        targets.append(RegisterTarget(pc, register, target, status))
    return targets


def target_summary(targets):
    return {'scope': 'supplied-partial-graph; targets do not extend traversal',
            'register_sites': len(targets),
            'constant_targets': sum(t.target is not None for t in targets),
            'targets': [asdict(t) for t in targets]}
