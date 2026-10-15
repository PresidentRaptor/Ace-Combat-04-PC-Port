"""Independent EE instruction decoder; addresses are 32-bit guest virtual addresses.

No execution semantics or inherited implementation inputs. See PROVENANCE.md.
Unsupported, reserved and architecturally undefined encodings raise DecodeError.
"""
from dataclasses import dataclass

MASK = 0xffffffff

# EE instruction-set manual appendix 7.2: function selects the MMI group;
# bits 10..6 select the operation inside that group. These are encodings, not
# implementations of the packed arithmetic. Unlisted slots remain unsupported.
PACKED_GROUPS = {
    8: {0: 'paddw', 1: 'psubw', 2: 'pcgtw', 3: 'pmaxw',
        4: 'paddh', 5: 'psubh', 6: 'pcgth', 7: 'pmaxh',
        8: 'paddb', 9: 'psubb', 10: 'pcgtb',
        16: 'paddsw', 17: 'psubsw', 18: 'pextlw', 19: 'ppacw',
        20: 'paddsh', 21: 'psubsh', 22: 'pextlh', 23: 'ppach',
        24: 'paddsb', 25: 'psubsb', 26: 'pextlb', 27: 'ppacb',
        30: 'pext5', 31: 'ppac5'},
    40: {1: 'pabsw', 2: 'pceqw', 3: 'pminw', 4: 'padsbh',
         5: 'pabsh', 6: 'pceqh', 7: 'pminh', 10: 'pceqb',
         16: 'padduw', 17: 'psubuw', 18: 'pextuw',
         20: 'padduh', 21: 'psubuh', 22: 'pextuh',
         24: 'paddub', 25: 'psubub', 26: 'pextub', 27: 'qfsrv'},
    9: {0: 'pmaddw', 2: 'psllvw', 3: 'psrlvw', 4: 'pmsubw',
        8: 'pmfhi', 9: 'pmflo', 10: 'pinth', 12: 'pmultw',
        13: 'pdivw', 14: 'pcpyld', 16: 'pmaddh', 17: 'phmadh',
        18: 'pand', 19: 'pxor', 20: 'pmsubh', 21: 'phmsbh',
        26: 'pexeh', 27: 'prevh', 28: 'pmulth', 29: 'pdivbw',
        30: 'pexew', 31: 'prot3w'},
    41: {0: 'pmadduw', 3: 'psravw', 8: 'pmthi', 9: 'pmtlo',
         10: 'pinteh', 12: 'pmultuw', 13: 'pdivuw', 14: 'pcpyud',
         18: 'por', 19: 'pnor', 26: 'pexch', 27: 'pcpyh', 30: 'pexcw'},
}


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
    memory = {26: 'ldl', 27: 'ldr', 30: 'lq', 31: 'sq',
              32: 'lb', 33: 'lh', 34: 'lwl', 35: 'lw',
              36: 'lbu', 37: 'lhu', 38: 'lwr', 39: 'lwu', 40: 'sb', 41: 'sh',
              42: 'swl', 43: 'sw', 44: 'sdl', 45: 'sdr', 46: 'swr', 55: 'ld', 63: 'sd'}
    if op in memory:
        return emit(memory[op], {'rt': rt, 'base': rs, 'offset': signed})
    if op in (49, 57):
        return emit('lwc1' if op == 49 else 'swc1',
                    {'ft': rt, 'base': rs, 'offset': signed})
    if op in (54, 62):
        return emit('lqc2' if op == 54 else 'sqc2',
                    {'vft': rt, 'base': rs, 'offset': signed})
    if op == 1 and rt in (24, 25):
        return emit('mtsab' if rt == 24 else 'mtsah', {'rs': rs, 'immediate': imm})
    if op == 51:
        # Reserved PREF hints have the same effect as hint zero on the EE.
        return emit('pref', {'base': rs, 'hint': rt, 'offset': signed})
    if op == 18:
        if rs == 8 and rt <= 3:
            return emit(('bc2f', 'bc2t', 'bc2fl', 'bc2tl')[rt],
                        {'immediate': signed}, 'branch',
                        (pc + 4 + signed * 4) & MASK, bool(rt & 2))
        if rs in (1, 2, 5, 6):
            zero(word & 0x7fe)
            name = {1: 'qmfc2', 2: 'cfc2', 5: 'qmtc2', 6: 'ctc2'}[rs]
            return emit(name, {'rt': rt, 'vfd' if rs in (1, 5) else 'vi': rd,
                               'interlock': word & 1})
        if rs >= 16:
            mask = rs & 15  # x/y/z/w correspond to mask bits 3/2/1/0.
            if fn < 28:
                name = ('vadd', 'vsub', 'vmadd', 'vmsub', 'vmax', 'vmini', 'vmul')[fn // 4]
                return emit(name + 'xyzw'[fn & 3],
                            {'vfd': sa, 'vfs': rd, 'vft': rt, 'dest_mask': mask})
            scalar = {28: 'vmulq', 29: 'vmaxi', 30: 'vmuli', 31: 'vminii',
                      32: 'vaddq', 33: 'vmaddq', 34: 'vaddi', 35: 'vmaddi',
                      36: 'vsubq', 37: 'vmsubq', 38: 'vsubi', 39: 'vmsubi'}
            if fn in scalar:
                zero(rt)
                return emit(scalar[fn], {'vfd': sa, 'vfs': rd, 'dest_mask': mask})
            vectors = {40: 'vadd', 41: 'vmadd', 42: 'vmul', 43: 'vmax',
                       44: 'vsub', 45: 'vmsub', 46: 'vopmsub', 47: 'vmini'}
            if fn in vectors:
                if fn == 46 and mask != 14:
                    raise DecodeError('outer product requires xyz destination mask')
                return emit(vectors[fn], {'vfd': sa, 'vfs': rd, 'vft': rt, 'dest_mask': mask})
            if fn in (48, 49, 50, 52, 53):
                zero(mask)
                if rd >= 16 or rt >= 16 or fn != 50 and sa >= 16:
                    raise DecodeError('unsupported VU integer register')
                if fn == 50:
                    return emit('viaddi', {'vit': rt, 'vis': rd,
                                          'immediate': sa - 32 if sa & 16 else sa})
                return emit({48: 'viadd', 49: 'visub', 52: 'viand', 53: 'vior'}[fn],
                            {'vid': sa, 'vis': rd, 'vit': rt})
            if fn == 56:
                zero(mask)
                immediate = (word >> 6) & 0x7fff
                # Starts VU0 microcode; does not branch the EE instruction PC.
                return emit('vcallms', {'immediate': immediate, 'micro_address': immediate * 8})
            if fn == 57:
                zero(mask, rt, rd, sa)
                return emit('vcallmsr', {})
    if op == 16:
        if rs == 8 and rt <= 3:
            return emit(('bc0f', 'bc0t', 'bc0fl', 'bc0tl')[rt],
                        {'immediate': signed}, 'branch',
                        (pc + 4 + signed * 4) & MASK, bool(rt & 2))
        if rs in (0, 4):
            # Specialized debug/performance selector encodings are not yet
            # accepted. Baseline transfers require all eleven low bits zero.
            zero(word & 0x7ff)
            return emit('mfc0' if rs == 0 else 'mtc0', {'rt': rt, 'cop0': rd})
        system = {1: 'tlbr', 2: 'tlbwi', 6: 'tlbwr', 8: 'tlbp',
                  24: 'eret', 56: 'ei', 57: 'di'}
        if rs == 16 and fn in system:
            zero(rt, rd, sa)
            return emit(system[fn], {}, 'exception-return' if fn == 24 else 'normal')
    if op == 28:
        if fn in PACKED_GROUPS and sa in PACKED_GROUPS[fn]:
            name = PACKED_GROUPS[fn][sa]
            if name in ('pmfhi', 'pmflo'):
                zero(rs, rt)
                return emit(name, {'rd': rd})
            if name in ('pmthi', 'pmtlo'):
                zero(rt, rd)
                return emit(name, {'rs': rs})
            if name in ('pdivw', 'pdivuw', 'pdivbw'):
                zero(rd)
                return emit(name, {'rs': rs, 'rt': rt})
            if name in ('pext5', 'ppac5', 'pabsw', 'pabsh', 'pexeh', 'prevh',
                        'pexew', 'prot3w', 'pexch', 'pcpyh', 'pexcw'):
                zero(rs)
                return emit(name, {'rd': rd, 'rt': rt})
            return emit(name, {'rd': rd, 'rs': rs, 'rt': rt})
        multiply = {0: 'madd', 1: 'maddu', 24: 'mult1', 25: 'multu1',
                    32: 'madd1', 33: 'maddu1'}
        if fn in multiply:
            zero(sa)
            return emit(multiply[fn], {'rd': rd, 'rs': rs, 'rt': rt})
        if fn == 4:
            zero(rt, sa)
            return emit('plzcw', {'rd': rd, 'rs': rs})
        if fn in (16, 18):
            zero(rs, rt, sa)
            return emit('mfhi1' if fn == 16 else 'mflo1', {'rd': rd})
        if fn in (17, 19):
            zero(rt, rd, sa)
            return emit('mthi1' if fn == 17 else 'mtlo1', {'rs': rs})
        if fn in (26, 27):
            zero(rd, sa)
            return emit('div1' if fn == 26 else 'divu1', {'rs': rs, 'rt': rt})
        if fn == 48 and sa <= 4:
            zero(rs, rt)
            return emit('pmfhl.' + ('lw', 'uw', 'slw', 'lh', 'sh')[sa], {'rd': rd})
        if fn == 49:
            zero(rt, rd, sa)
            return emit('pmthl.lw', {'rs': rs})
        shifts = {52: 'psllh', 54: 'psrlh', 55: 'psrah',
                  60: 'psllw', 62: 'psrlw', 63: 'psraw'}
        if fn in shifts:
            zero(rs)
            return emit(shifts[fn], {'rd': rd, 'rt': rt,
                                    'shift': sa & (15 if fn < 60 else 31)})
    if op == 17:
        if rs == 8 and rt <= 3:
            target = (pc + 4 + signed * 4) & MASK
            return emit(('bc1f', 'bc1t', 'bc1fl', 'bc1tl')[rt],
                        {'immediate': signed}, 'branch', target, bool(rt & 2))
        if rs in (0, 2, 4, 6):
            zero(word & 0x7ff)
            control = rs in (2, 6)
            if rs == 2 and rd not in (0, 31) or rs == 6 and rd != 31:
                raise DecodeError('unsupported FPU control register')
            return emit({0: 'mfc1', 2: 'cfc1', 4: 'mtc1', 6: 'ctc1'}[rs],
                        {'rt': rt, 'fcr' if control else 'fs': rd})
        if rs == 16:
            binary = {0: 'add.s', 1: 'sub.s', 2: 'mul.s', 3: 'div.s',
                      22: 'rsqrt.s', 28: 'madd.s', 29: 'msub.s',
                      40: 'max.s', 41: 'min.s'}
            if fn in binary:
                return emit(binary[fn], {'fd': sa, 'fs': rd, 'ft': rt})
            if fn == 4:
                # EE SQRT uses ft, unlike the other unary operations.
                zero(rd)
                return emit('sqrt.s', {'fd': sa, 'ft': rt})
            if fn in (5, 6, 7, 36):
                zero(rt)
                return emit({5: 'abs.s', 6: 'mov.s', 7: 'neg.s', 36: 'cvt.w.s'}[fn],
                            {'fd': sa, 'fs': rd})
            accumulator = {24: 'adda.s', 25: 'suba.s', 26: 'mula.s',
                           30: 'madda.s', 31: 'msuba.s'}
            comparisons = {48: 'c.f.s', 50: 'c.eq.s', 52: 'c.lt.s', 54: 'c.le.s'}
            if fn in accumulator or fn in comparisons:
                zero(sa)
                return emit((accumulator | comparisons)[fn], {'fs': rd, 'ft': rt})
        if rs == 20 and fn == 32:
            zero(rt)
            return emit('cvt.s.w', {'fd': sa, 'fs': rd})
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
        if fn == 40:
            zero(rs, rt, sa)
            return emit('mfsa', {'rd': rd})
        if fn == 41:
            zero(rt, rd, sa)
            return emit('mtsa', {'rs': rs})
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
