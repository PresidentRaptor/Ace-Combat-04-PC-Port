"""Independent EE scalar decoder; addresses are 32-bit guest virtual addresses.

No execution semantics or inherited implementation inputs. See PROVENANCE.md.
Unsupported, reserved and architecturally undefined encodings raise DecodeError.
"""
from dataclasses import dataclass

MASK = 0xffffffff


class DecodeError(ValueError):
    pass


@dataclass(frozen=True)
class Instruction:
    pc: int
    word: int
    mnemonic: str
    operands: dict[str, int]
    flow: str = 'normal'
    target: int | None = None
    likely: bool = False
    link_register: int | None = None
    link_address: int | None = None

    @property
    def has_delay_slot(self):
        return self.flow in ('branch', 'jump', 'call', 'indirect', 'return')


def decode(word: int, pc: int) -> Instruction:
    if not 0 <= word <= MASK or not 0 <= pc <= MASK or pc & 3:
        raise DecodeError('word/PC outside 32 bits or unaligned PC')
    op, rs, rt = word >> 26, (word >> 21) & 31, (word >> 16) & 31
    rd, sa, fn = (word >> 11) & 31, (word >> 6) & 31, word & 63
    imm = word & 0xffff
    signed = imm - 0x10000 if imm & 0x8000 else imm

    def emit(name, operands, flow='normal', target=None, likely=False, link=None):
        return Instruction(pc, word, name, operands, flow, target, likely, link,
                           (pc + 8) & MASK if link is not None else None)

    def zero(*fields):
        if any(fields):
            raise DecodeError('reserved nonzero field')

    if op in (2, 3):
        target = (((pc + 4) & MASK) & 0xf0000000) | ((word & 0x3ffffff) << 2)
        return emit('j' if op == 2 else 'jal', {'target': target},
                    'jump' if op == 2 else 'call', target, link=31 if op == 3 else None)
    branches = {4: 'beq', 5: 'bne', 6: 'blez', 7: 'bgtz',
                20: 'beql', 21: 'bnel', 22: 'blezl', 23: 'bgtzl'}
    reg_branches = {0: 'bltz', 1: 'bgez', 2: 'bltzl', 3: 'bgezl',
                    16: 'bltzal', 17: 'bgezal', 18: 'bltzall', 19: 'bgezall'}
    if op in branches or op == 1 and rt in reg_branches:
        link = 31 if op == 1 and rt >= 16 else None
        if link is not None and rs == 31:
            raise DecodeError('undefined link branch with rs=31')
        operands = {'rs': rs, 'immediate': signed}
        if op in (4, 5, 20, 21):
            operands['rt'] = rt
        elif op != 1:
            zero(rt)
        target = (pc + 4 + signed * 4) & MASK
        return emit(reg_branches[rt] if op == 1 else branches[op], operands,
                    'branch', target, (op >= 20 if op != 1 else bool(rt & 2)), link)
    immediate = {8: 'addi', 9: 'addiu', 10: 'slti', 11: 'sltiu',
                 12: 'andi', 13: 'ori', 14: 'xori', 24: 'daddi', 25: 'daddiu'}
    if op in immediate:
        return emit(immediate[op], {'rt': rt, 'rs': rs,
                                    'immediate': imm if op in (12, 13, 14) else signed})
    if op == 15:
        zero(rs)
        return emit('lui', {'rt': rt, 'immediate': imm})
    memory = {26: 'ldl', 27: 'ldr', 32: 'lb', 33: 'lh', 34: 'lwl', 35: 'lw',
              36: 'lbu', 37: 'lhu', 38: 'lwr', 39: 'lwu', 40: 'sb', 41: 'sh',
              42: 'swl', 43: 'sw', 44: 'sdl', 45: 'sdr', 46: 'swr', 55: 'ld', 63: 'sd'}
    if op in memory:
        return emit(memory[op], {'rt': rt, 'base': rs, 'offset': signed})
    immediate_traps = {8: 'tgei', 9: 'tgeiu', 10: 'tlti', 11: 'tltiu',
                       12: 'teqi', 14: 'tnei'}
    if op == 1 and rt in immediate_traps:
        return emit(immediate_traps[rt], {'rs': rs, 'immediate': signed}, 'trap')
    if op == 0:
        shifts = {0: 'sll', 2: 'srl', 3: 'sra', 56: 'dsll', 58: 'dsrl',
                  59: 'dsra', 60: 'dsll32', 62: 'dsrl32', 63: 'dsra32'}
        if fn in shifts:
            zero(rs)
            return emit(shifts[fn], {'rd': rd, 'rt': rt, 'shift': sa + (32 if fn >= 60 else 0)})
        alu = {4: 'sllv', 6: 'srlv', 7: 'srav', 10: 'movz', 11: 'movn',
               20: 'dsllv', 22: 'dsrlv', 23: 'dsrav', 24: 'mult', 25: 'multu',
               32: 'add', 33: 'addu', 34: 'sub', 35: 'subu', 36: 'and', 37: 'or',
               38: 'xor', 39: 'nor', 42: 'slt', 43: 'sltu', 44: 'dadd',
               45: 'daddu', 46: 'dsub', 47: 'dsubu'}
        if fn in alu:
            zero(sa)
            return emit(alu[fn], {'rd': rd, 'rs': rs, 'rt': rt})
        if fn in (26, 27):
            zero(rd, sa)
            return emit('div' if fn == 26 else 'divu', {'rs': rs, 'rt': rt})
        if fn in (16, 18):
            zero(rs, rt, sa)
            return emit('mfhi' if fn == 16 else 'mflo', {'rd': rd})
        if fn in (17, 19):
            zero(rt, rd, sa)
            return emit('mthi' if fn == 17 else 'mtlo', {'rs': rs})
        if fn in (8, 9):
            zero(rt, sa, rd if fn == 8 else 0)
            if fn == 9 and rs == rd:
                raise DecodeError('undefined jalr with rs=rd')
            link = rd if fn == 9 and rd else None  # $zero discards the link
            return emit('jr' if fn == 8 else 'jalr',
                        {'rs': rs, **({'rd': rd} if fn == 9 else {})},
                        'call' if link is not None else 'return' if fn == 8 and rs == 31 else 'indirect',
                        link=link)
        if fn in (12, 13):
            return emit('syscall' if fn == 12 else 'break', {'code': (word >> 6) & 0xfffff}, 'exception')
        if fn == 15:
            zero(rs, rt, rd)
            return emit('sync', {'stype': sa})
        traps = {48: 'tge', 49: 'tgeu', 50: 'tlt', 51: 'tltu', 52: 'teq', 54: 'tne'}
        if fn in traps:
            return emit(traps[fn], {'rs': rs, 'rt': rt, 'code': (word >> 6) & 0x3ff}, 'trap')
    raise DecodeError(f'unsupported or reserved encoding (opcode={op:#x})')
