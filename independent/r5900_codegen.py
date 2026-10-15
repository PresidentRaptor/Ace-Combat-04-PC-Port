"""Experimental static scalar EE-to-C translator for bounded test programs.

Each supplied instruction becomes C for that fixed guest address. Unsupported
operations reject translation; no runtime opcode decoder or inherited runtime
is used. Host stop codes are diagnostics, not PS2 exception-vector delivery.
"""
import argparse
from pathlib import Path

from r5900 import decode, DecodeError


class TranslationError(ValueError):
    pass


RUNTIME = r'''
#include <stdint.h>
#include <stddef.h>
enum { AC4_BREAK=1, AC4_SYSCALL=2, AC4_FETCH=3, AC4_ALIGNMENT=4,
       AC4_BOUNDS=5, AC4_UNDEFINED_SLOT=6, AC4_OVERFLOW=7, AC4_BUDGET=8,
       AC4_UNDEFINED_INPUT=9 };
typedef struct {
    uint64_t gpr[32][2], hi[2], lo[2], steps;
    uint32_t pc, pending_target, branch_pc, fault_pc, fault_address, code;
    unsigned pending, fault_delay;
    unsigned char *memory;
    uint32_t memory_base, memory_size;
    int memory_error;
} Ac4Cpu;
static inline uint64_t ac4_sext(uint64_t value, unsigned bits) {
    uint64_t mask=(UINT64_C(1)<<bits)-1;
    value &= mask;
    return value | ((value & (UINT64_C(1)<<(bits-1))) ? ~mask : 0);
}
static inline uint64_t ac4_asr(uint64_t value, unsigned shift) {
    if (!shift) return value;
    return (value>>shift) | ((UINT64_C(0)-(value>>63))<<(64-shift));
}
static inline int ac4_less(uint64_t left, uint64_t right) {
    return (left ^ UINT64_C(0x8000000000000000)) <
           (right ^ UINT64_C(0x8000000000000000));
}
static inline int64_t ac4_signed_word(uint64_t value) {
    return (int64_t)(value & UINT64_C(0xffffffff)) -
           ((value & UINT64_C(0x80000000)) ? INT64_C(0x100000000) : 0);
}
static inline int ac4_memory(Ac4Cpu *c, uint32_t address, unsigned bytes, size_t *offset) {
    c->fault_address=address;
    if (address & (bytes-1)) { c->memory_error=AC4_ALIGNMENT; return 0; }
    if (!c->memory || address<c->memory_base || bytes>c->memory_size ||
        (uint64_t)address-c->memory_base>(uint64_t)c->memory_size-bytes ||
        (uint64_t)address+bytes>UINT64_C(0x100000000)) {
        c->memory_error=AC4_BOUNDS; return 0;
    }
    *offset=(size_t)((uint64_t)address-c->memory_base);
    return 1;
}
static inline int ac4_load(Ac4Cpu *c, uint32_t address, unsigned bytes,
                           uint64_t *low, uint64_t *high) {
    size_t offset;
    if (!ac4_memory(c,address,bytes,&offset)) return 0;
    *low=0; *high=0;
    for (unsigned i=0;i<bytes;i++) {
        if (i<8) *low|=(uint64_t)c->memory[offset+i]<<(8*i);
        else *high|=(uint64_t)c->memory[offset+i]<<(8*(i-8));
    }
    return 1;
}
static inline int ac4_store(Ac4Cpu *c, uint32_t address, unsigned bytes,
                            uint64_t low, uint64_t high) {
    size_t offset;
    if (!ac4_memory(c,address,bytes,&offset)) return 0;
    for (unsigned i=0;i<bytes;i++)
        c->memory[offset+i]=(unsigned char)((i<8 ? low>>(8*i) : high>>(8*(i-8)))&255);
    return 1;
}
int ac4_run(Ac4Cpu *c, uint64_t budget) {
    c->gpr[0][0]=0; c->gpr[0][1]=0;
    for (uint64_t tick=0;tick<budget;tick++) {
        uint32_t pc=c->pc, resume=c->pending_target;
        (void)resume; /* Some bounded programs contain only control/stop cases. */
        unsigned delay=c->pending;
        c->pending=0;
        c->fault_pc=delay ? c->branch_pc : pc;
        c->fault_delay=delay;
        if (pc&3) { c->fault_address=pc; return AC4_ALIGNMENT; }
        c->steps++;
        switch (pc) {
'''


def u64(value):
    return f'UINT64_C(0x{value & ((1 << 64) - 1):016x})'


def register(number):
    return f'c->gpr[{number}][0]'


def write(number, expression):
    return f'{register(number)}={expression};' if number else ''


def translate(ins):
    o, name, pc = ins.operands, ins.mnemonic, ins.pc
    rs, rt = register(o.get('rs', 0)), register(o.get('rt', 0))
    immediate = u64(o.get('immediate', 0))
    lines = []
    if ins.has_delay_slot:
        lines.append('if (delay) return AC4_UNDEFINED_SLOT;')
        if name in ('j', 'jal'):
            lines.append(f'uint32_t destination=UINT32_C(0x{ins.target:08x});')
        elif name in ('jr', 'jalr'):
            lines.append(f'uint32_t destination=(uint32_t){rs};')
        else:
            condition = None
            if name in ('beq', 'beql', 'bne', 'bnel'):
                condition = f'{rs}=={rt}' if name.startswith('beq') else f'{rs}!={rt}'
            elif name.startswith('bltz'):
                condition = f'({rs}>>63)!=0'
            elif name.startswith('bgez'):
                condition = f'({rs}>>63)==0'
            elif name in ('blez', 'blezl'):
                condition = f'({rs}==0 || ({rs}>>63)!=0)'
            elif name in ('bgtz', 'bgtzl'):
                condition = f'({rs}!=0 && ({rs}>>63)==0)'
            if condition is None:
                raise TranslationError(f'{pc:#x}: unsupported branch {name}')
            lines.append(f'int taken=({condition});')
            lines.append(f'uint32_t destination=taken ? UINT32_C(0x{ins.target:08x}) : '
                         f'UINT32_C(0x{(pc + 8) & 0xffffffff:08x});')
        if ins.link_register is not None:
            lines.append(write(ins.link_register, u64(ins.link_address)))
        if ins.likely:
            lines.append(f'if (!taken) {{ c->pc=UINT32_C(0x{(pc + 8) & 0xffffffff:08x}); break; }}')
        lines.extend(['c->pending=1; c->pending_target=destination; c->branch_pc=pc;',
                      f'c->pc=UINT32_C(0x{(pc + 4) & 0xffffffff:08x}); break;'])
        return '\n'.join(lines)
    if name in ('break', 'syscall'):
        return f'c->code={o["code"]}; return AC4_{name.upper()};'
    if name == 'lui':
        lines.append(write(o['rt'], f'ac4_sext({u64(o["immediate"] << 16)},32)'))
    elif name in ('ori', 'andi', 'xori', 'slti', 'sltiu'):
        if name == 'slti':
            expression = f'(uint64_t)ac4_less({rs},{immediate})'
        elif name == 'sltiu':
            expression = f'(uint64_t)({rs}<{immediate})'
        else:
            operator = {'ori': '|', 'andi': '&', 'xori': '^'}[name]
            expression = f'({rs}{operator}{immediate})'
        lines.append(write(o['rt'], expression))
    elif name in ('add', 'addi', 'addu', 'addiu', 'sub', 'subu',
                   'dadd', 'daddi', 'daddu', 'daddiu', 'dsub', 'dsubu'):
        wide, subtract = name.startswith('d'), 'sub' in name
        right = immediate if name in ('addi', 'addiu', 'daddi', 'daddiu') else rt
        ctype = 'uint64_t' if wide else 'uint32_t'
        lines.extend([f'{ctype} a=({ctype}){rs}, b=({ctype}){right};',
                      f'{ctype} value=({ctype})(a {"-" if subtract else "+"} b);'])
        if not name.endswith('u'):
            bits = 64 if wide else 32
            check = '(a^b)' if subtract else '~(a^b)'
            lines.append(f'if (({check}&(a^value)&{u64(1 << (bits - 1))})!=0) return AC4_OVERFLOW;')
        lines.append(write(o.get('rd', o.get('rt')), 'value' if wide else 'ac4_sext(value,32)'))
        lines.append('(void)value;')  # Discarded destinations still check overflow.
    elif name in ('mfhi', 'mfhi1', 'mflo', 'mflo1', 'mthi', 'mthi1', 'mtlo', 'mtlo1'):
        bank = int(name.endswith('1'))
        special = 'hi' if 'hi' in name else 'lo'
        if name.startswith('mf'):
            lines.append(write(o['rd'], f'c->{special}[{bank}]'))
        else:
            lines.append(f'c->{special}[{bank}]={rs};')
    elif name in ('mult', 'multu', 'mult1', 'multu1', 'madd', 'maddu', 'madd1', 'maddu1',
                   'div', 'divu', 'div1', 'divu1'):
        bank = int(name.endswith('1'))
        unsigned = name.rstrip('1').endswith('u')
        # The manual leaves non-word inputs and zero divisors undefined. Stop
        # with a host diagnostic; do not invent a guest exception or result.
        lines.append(f'if ({rs}!=ac4_sext({rs},32) || {rt}!=ac4_sext({rt},32)) return AC4_UNDEFINED_INPUT;')
        if name.startswith('div'):
            lines.append(f'if (!(uint32_t){rt}) return AC4_UNDEFINED_INPUT;')
            left = f'(uint64_t)(uint32_t){rs}' if unsigned else f'ac4_signed_word({rs})'
            right = f'(uint64_t)(uint32_t){rt}' if unsigned else f'ac4_signed_word({rt})'
            lines.extend([f'uint64_t quotient=(uint64_t)({left}/{right});',
                          f'uint64_t remainder=(uint64_t)({left}%{right});',
                          f'c->lo[{bank}]=ac4_sext(quotient,32); c->hi[{bank}]=ac4_sext(remainder,32);'])
        else:
            product = (f'(uint64_t)(uint32_t){rs}*(uint64_t)(uint32_t){rt}' if unsigned else
                       f'(uint64_t)(ac4_signed_word({rs})*ac4_signed_word({rt}))')
            lines.append(f'uint64_t product={product};')
            if name.startswith('madd'):
                lines.append(f'product+=((uint64_t)(uint32_t)c->hi[{bank}]<<32)|(uint32_t)c->lo[{bank}];')
            lines.extend([f'c->lo[{bank}]=ac4_sext(product,32);',
                          f'c->hi[{bank}]=ac4_sext(product>>32,32);',
                          write(o['rd'], f'c->lo[{bank}]')])
    elif name in ('and', 'or', 'xor', 'nor', 'slt', 'sltu', 'movz', 'movn'):
        if name in ('movz', 'movn'):
            condition = f'{rt}==0' if name == 'movz' else f'{rt}!=0'
            lines.append(f'if ({condition}) {{ {write(o["rd"], rs)} }}')
        else:
            expression = {'and': f'({rs}&{rt})', 'or': f'({rs}|{rt})',
                          'xor': f'({rs}^{rt})', 'nor': f'~({rs}|{rt})',
                          'slt': f'(uint64_t)ac4_less({rs},{rt})',
                          'sltu': f'(uint64_t)({rs}<{rt})'}[name]
            lines.append(write(o['rd'], expression))
    elif name in ('sll', 'srl', 'sra', 'sllv', 'srlv', 'srav',
                   'dsll', 'dsll32', 'dsrl', 'dsrl32', 'dsra', 'dsra32',
                   'dsllv', 'dsrlv', 'dsrav'):
        wide = name.startswith('d')
        shift = str(o['shift']) if 'shift' in o else f'({rs}&{63 if wide else 31})'
        value = rt if wide else f'ac4_sext({rt},32)'
        if 'sra' in name:
            expression = f'ac4_asr({value},(unsigned){shift})'
        elif 'srl' in name:
            expression = f'({rt}>>{shift})' if wide else f'((uint32_t){rt}>>{shift})'
        else:
            expression = f'({rt}<<{shift})'
        lines.append(write(o['rd'], expression if wide else f'ac4_sext({expression},32)'))
    elif name in ('lb', 'lbu', 'lh', 'lhu', 'lw', 'lwu', 'ld', 'lq',
                   'sb', 'sh', 'sw', 'sd', 'sq'):
        width = {'b': 1, 'h': 2, 'w': 4, 'd': 8, 'q': 16}[name[1]]
        lines.append(f'uint32_t address=(uint32_t)({register(o["base"])}+{u64(o["offset"])});')
        if width == 16:
            lines.append('address &= ~UINT32_C(15);')
        if name.startswith('l'):
            lines.append(f'uint64_t low,high; if (!ac4_load(c,address,{width},&low,&high)) return c->memory_error;')
            expression = f'ac4_sext(low,{width * 8})' if name in ('lb', 'lh', 'lw') else 'low'
            lines.append(write(o['rt'], expression))
            if width == 16 and o['rt']:
                lines.append(f'c->gpr[{o["rt"]}][1]=high;')
        else:
            lines.append(f'if (!ac4_store(c,address,{width},{rt},c->gpr[{o["rt"]}][1])) return c->memory_error;')
    elif name == 'sync':
        lines.append('if (delay) return AC4_UNDEFINED_SLOT;')
        # Otherwise single-threaded; no timing/inter-thread model.
    else:
        raise TranslationError(f'{pc:#x}: unsupported operation {name}')
    lines.extend(['c->gpr[0][0]=0; c->gpr[0][1]=0;',
                  f'c->pc=delay ? resume : UINT32_C(0x{(pc + 4) & 0xffffffff:08x}); break;'])
    return '\n'.join(lines)


def emit_program(words, entry):
    if entry not in words:
        raise TranslationError('entry outside supplied instruction map')
    parts = [RUNTIME]
    try:
        for pc in sorted(words):
            ins = decode(words[pc], pc)
            parts.append(f'case UINT32_C(0x{pc:08x}): {{\n{translate(ins)}\n}}\n')
    except DecodeError as error:
        raise TranslationError(str(error)) from None
    parts.append('default: c->fault_address=pc; return AC4_FETCH;\n}\n}\nreturn AC4_BUDGET;\n}\n')
    return ''.join(parts)


def entry_program(data):
    """Translate the verified image's bounded entry graph, stopping at services.

    No indirect-target assumptions are added. Fetches outside the selected graph
    stop at AC4_FETCH, and unsupported reachable operations reject generation.
    """
    from r5900_analysis import executable_words, analyze
    words, entry, _ = executable_words(data)
    graph = analyze(words, [entry])
    if graph.diagnostics:
        raise TranslationError(f'entry analysis has diagnostics: {graph.diagnostics}')
    selected = {pc: words[pc] for pc in graph.instructions}
    return emit_program(selected, entry), entry, len(selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--words', nargs='+', type=lambda value: int(value, 16))
    source.add_argument('--elf', type=Path)
    source.add_argument('--iso', type=Path)
    parser.add_argument('--base', type=lambda value: int(value, 0), default=0x1000)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.words is not None:
            source = emit_program({args.base + 4 * i: word for i, word in enumerate(args.words)}, args.base)
        else:
            if args.iso:
                from ac4_disc import executable_from_iso
                with args.iso.open('rb') as stream:
                    data, _ = executable_from_iso(stream)
            else:
                data = args.elf.read_bytes()
            if args.output is None:
                raise ValueError('game translation requires --output to an untracked local path')
            source, _, _ = entry_program(data)
        if args.output:
            args.output.write_text(source, encoding='utf-8')
        else:
            print(source, end='')
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
