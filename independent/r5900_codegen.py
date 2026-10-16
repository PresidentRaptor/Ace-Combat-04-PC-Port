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
       AC4_UNDEFINED_INPUT=9, AC4_UNSUPPORTED=10, AC4_DEVICE=11, AC4_MODIFIED=12,
       AC4_PRIVILEGE=13 };
typedef struct {
    uint64_t gpr[32][2], hi[2], lo[2], steps;
    uint32_t pc, pending_target, branch_pc, fault_pc, fault_address, code;
    unsigned pending, fault_delay;
    unsigned char *memory;
    uint32_t memory_base, memory_size;
    int memory_error;
    unsigned ee_memory_map;
    unsigned verify_instruction_bytes;
    unsigned coherent_cache_profile;
    uint32_t cp0_status;
    uint32_t fpr[32],fcr31;
    unsigned char scratchpad[16384];
    void *device_state;
    int (*device_read)(void *,uint32_t,unsigned,uint64_t *,uint64_t *);
    int (*device_write)(void *,uint32_t,unsigned,uint64_t,uint64_t);
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
static inline uint64_t ac4_packed(uint64_t left,uint64_t right,unsigned bits,unsigned operation) {
    uint64_t mask=(UINT64_C(1)<<bits)-1,sign=UINT64_C(1)<<(bits-1),result=0;
    for (unsigned shift=0;shift<64;shift+=bits) {
        uint64_t a=(left>>shift)&mask,b=(right>>shift)&mask,value;
        int greater=(a^sign)>(b^sign);
        if (operation==0) value=(a+b)&mask;
        else if (operation==1) value=(a-b)&mask;
        else if (operation==2) value=a==b ? mask : 0;
        else if (operation==3) value=greater ? mask : 0;
        else if (operation==4) value=greater ? b : a;
        else value=greater ? a : b;
        result|=value<<shift;
    }
    return result;
}
static inline uint32_t ac4_physical(uint32_t address) {
    if (address>=UINT32_C(0x80000000) && address<UINT32_C(0xc0000000))
        return address&UINT32_C(0x1fffffff);
    if (address>=UINT32_C(0x20000000) && address<UINT32_C(0x22000000))
        return address-UINT32_C(0x20000000);
    if (address>=UINT32_C(0x30100000) && address<UINT32_C(0x32000000))
        return address-UINT32_C(0x30000000);
    return address;
}
static inline int ac4_device_address(uint32_t address) {
    return (address>=UINT32_C(0x10000000) && address<UINT32_C(0x10010000)) ||
           (address>=UINT32_C(0x12000000) && address<UINT32_C(0x12002000));
}
static inline int ac4_span(Ac4Cpu *c, uint32_t address, unsigned bytes, unsigned char **storage) {
    c->fault_address=address;
    if (c->ee_memory_map) {
        if (address>=UINT32_C(0x70000000) && address<UINT32_C(0x70004000)) {
            unsigned offset=address-UINT32_C(0x70000000);
            if (bytes>16384-offset) { c->memory_error=AC4_BOUNDS; return 0; }
            *storage=c->scratchpad+offset; return 1;
        }
        address=ac4_physical(address);
        if (ac4_device_address(address)) { c->memory_error=AC4_DEVICE; return 0; }
    }
    if (!c->memory || address<c->memory_base || bytes>c->memory_size ||
        (uint64_t)address-c->memory_base>(uint64_t)c->memory_size-bytes ||
        (uint64_t)address+bytes>UINT64_C(0x100000000)) {
        c->memory_error=AC4_BOUNDS; return 0;
    }
    *storage=c->memory+(size_t)((uint64_t)address-c->memory_base);
    return 1;
}
static inline int ac4_load(Ac4Cpu *c, uint32_t address, unsigned bytes,
                           uint64_t *low, uint64_t *high) {
    c->fault_address=address;
    if (address&(bytes-1)) { c->memory_error=AC4_ALIGNMENT; return 0; }
    if (c->ee_memory_map && ac4_device_address(ac4_physical(address))) {
        *low=0; *high=0;
        c->memory_error=c->device_read ? c->device_read(c->device_state,ac4_physical(address),bytes,low,high) : AC4_DEVICE;
        return c->memory_error==0;
    }
    unsigned char *storage;
    if (!ac4_span(c,address,bytes,&storage)) return 0;
    *low=0; *high=0;
    for (unsigned i=0;i<bytes;i++) {
        if (i<8) *low|=(uint64_t)storage[i]<<(8*i);
        else *high|=(uint64_t)storage[i]<<(8*(i-8));
    }
    return 1;
}
static inline int ac4_store(Ac4Cpu *c, uint32_t address, unsigned bytes,
                            uint64_t low, uint64_t high) {
    c->fault_address=address;
    if (address&(bytes-1)) { c->memory_error=AC4_ALIGNMENT; return 0; }
    if (c->ee_memory_map && ac4_device_address(ac4_physical(address))) {
        c->memory_error=c->device_write ? c->device_write(c->device_state,ac4_physical(address),bytes,low,high) : AC4_DEVICE;
        return c->memory_error==0;
    }
    unsigned char *storage;
    if (!ac4_span(c,address,bytes,&storage)) return 0;
    for (unsigned i=0;i<bytes;i++)
        storage[i]=(unsigned char)((i<8 ? low>>(8*i) : high>>(8*(i-8)))&255);
    return 1;
}
static inline int ac4_merge(Ac4Cpu *c, uint32_t address, unsigned width,
                            int left, int store, uint64_t *value) {
    unsigned lane=address&(width-1), count=left ? lane+1 : width-lane;
    uint32_t start=left ? address-lane : address;
    unsigned first=left ? width-count : 0;
    /* Only the selected bytes are accessed; precheck before any store. */
    unsigned char *storage;
    if (!ac4_span(c,start,count,&storage)) { c->fault_address=address; return 0; }
    for (unsigned i=0;i<count;i++) {
        unsigned shift=(first+i)*8;
        if (store) storage[i]=(unsigned char)(*value>>shift);
        else *value=(*value&~(UINT64_C(255)<<shift)) |
                    ((uint64_t)storage[i]<<shift);
    }
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
        c->fault_address=0;
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
            elif name in ('bc1f','bc1fl','bc1t','bc1tl'):
                lines.append('if (!(c->cp0_status&UINT32_C(0x20000000))) return AC4_PRIVILEGE;')
                condition='(c->fcr31&UINT32_C(0x800000))'+('!=0' if name.startswith('bc1t') else '==0')
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
    elif name in ('mfc1','mtc1','mov.s','lwc1','swc1','ctc1') or (name=='cfc1' and o['fcr']==31):
        lines.append('if (!(c->cp0_status&UINT32_C(0x20000000))) return AC4_PRIVILEGE;')
        if name=='mfc1':
            lines.append(write(o['rt'],f'ac4_sext(c->fpr[{o["fs"]}],32)'))
        elif name=='mtc1':
            lines.append(f'c->fpr[{o["fs"]}]=(uint32_t){rt};')
        elif name=='mov.s':
            lines.append(f'c->fpr[{o["fd"]}]=c->fpr[{o["fs"]}];')
        elif name=='ctc1':
            lines.append(f'c->fcr31=(uint32_t){rt};')
        elif name=='cfc1':
            lines.append(write(o['rt'],'ac4_sext(c->fcr31,32)'))
        else:
            lines.append(f'uint32_t address=(uint32_t)({register(o["base"])}+{u64(o["offset"])});')
            if name=='lwc1':
                lines.extend(['uint64_t low,high; if (!ac4_load(c,address,4,&low,&high)) return c->memory_error;',
                              f'c->fpr[{o["ft"]}]=(uint32_t)low;'])
            else:
                lines.append(f'if (!ac4_store(c,address,4,c->fpr[{o["ft"]}],0)) return c->memory_error;')
    elif name in ('lwl', 'lwr', 'ldl', 'ldr', 'swl', 'swr', 'sdl', 'sdr'):
        width = 4 if name[1] == 'w' else 8
        store = name.startswith('s')
        lines.extend([f'uint32_t address=(uint32_t)({register(o["base"])}+{u64(o["offset"])});',
                      f'uint64_t value={rt};',
                      f'if (!ac4_merge(c,address,{width},{int(name.endswith("l"))},{int(store)},&value)) return c->memory_error;'])
        if not store:
            lines.append(write(o['rt'], 'ac4_sext(value,32)' if width == 4 else 'value'))
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
    elif name in ('paddb','paddh','paddw','psubb','psubh','psubw',
                   'pceqb','pceqh','pceqw','pcgtb','pcgth','pcgtw',
                   'pminh','pminw','pmaxh','pmaxw'):
        if o['rd']:
            bits={'b':8,'h':16,'w':32}[name[-1]]
            operation={'padd':0,'psub':1,'pceq':2,'pcgt':3,'pmin':4,'pmax':5}[name[:-1]]
            lines.extend([f'uint64_t low=ac4_packed({rs},{rt},{bits},{operation});',
                          f'uint64_t high=ac4_packed(c->gpr[{o["rs"]}][1],c->gpr[{o["rt"]}][1],{bits},{operation});',
                          write(o['rd'],'low'),f'c->gpr[{o["rd"]}][1]=high;'])
    elif name in ('pand','por','pxor','pnor','pcpyld','pcpyud','pcpyh'):
        if o['rd']:
            rs_high=f'c->gpr[{o.get("rs",0)}][1]'
            rt_high=f'c->gpr[{o["rt"]}][1]'
            if name=='pcpyld':
                low,high=rt,rs
            elif name=='pcpyud':
                low,high=rs_high,rt_high
            elif name=='pcpyh':
                low=f'({rt}&UINT64_C(0xffff))*UINT64_C(0x0001000100010001)'
                high=f'({rt_high}&UINT64_C(0xffff))*UINT64_C(0x0001000100010001)'
            else:
                operator={'pand':'&','por':'|','pxor':'^','pnor':'|'}[name]
                invert='~' if name=='pnor' else ''
                low=f'{invert}({rs}{operator}{rt})'
                high=f'{invert}({rs_high}{operator}{rt_high})'
            lines.extend([f'uint64_t low={low},high={high};',
                          write(o['rd'],'low'),f'c->gpr[{o["rd"]}][1]=high;'])
    elif name in ('cache.dhwbin','cache.dhwoin'):
        lines.append('if (!c->coherent_cache_profile) return AC4_UNSUPPORTED;')
        lines.append('if (!(c->cp0_status&UINT32_C(0x10000006)) && (c->cp0_status&UINT32_C(0x18))) return AC4_PRIVILEGE;')
        lines.append(f'uint32_t address=(uint32_t)(c->gpr[{o["base"]}][0]+UINT64_C({o["offset"] & ((1<<64)-1)}));')
        lines.append('if (!(address<UINT32_C(0x02000000) || (address>=UINT32_C(0x80000000) && address<UINT32_C(0x82000000)))) return AC4_UNDEFINED_INPUT;')
        lines.append('unsigned char *line; if (!ac4_span(c,ac4_physical(address)&~UINT32_C(63),64,&line)) return c->memory_error;')
        lines.append('(void)line; c->fault_address=address;')
        # In this opt-in profile stores already reach coherent main RAM. There
        # is no dirty data cache to write back. Fetch-byte guards remain active.
    elif name in ('mfc0','mtc0') and o['cop0']==12:
        lines.append('if (!(c->cp0_status&UINT32_C(0x10000006)) && (c->cp0_status&UINT32_C(0x18))) return AC4_PRIVILEGE;')
        if name=='mfc0':
            lines.append(write(o['rt'],'ac4_sext(c->cp0_status,32)'))
        else:
            lines.append(f'c->cp0_status=(uint32_t){rt};')
    elif name in ('ei','di'):
        lines.append('if ((c->cp0_status&UINT32_C(0x20006)) || !(c->cp0_status&UINT32_C(0x18))) {')
        lines.append('c->cp0_status '+('|=UINT32_C(0x10000);' if name=='ei' else '&=~UINT32_C(0x10000);'))
        lines.append('}')
    elif name == 'sync':
        lines.append('if (delay) return AC4_UNDEFINED_SLOT;')
        # Otherwise single-threaded; no timing/inter-thread model.
    else:
        raise TranslationError(f'{pc:#x}: unsupported operation {name}')
    lines.extend(['c->gpr[0][0]=0; c->gpr[0][1]=0;',
                  f'c->pc=delay ? resume : UINT32_C(0x{(pc + 4) & 0xffffffff:08x}); break;'])
    return '\n'.join(lines)


def emit_case(word,pc,*,stop_unsupported=False):
    try:
        ins=decode(word,pc)
    except DecodeError as error:
        raise TranslationError(str(error)) from None
    try:
        body=translate(ins)
    except TranslationError:
        if not stop_unsupported:
            raise
        body='return AC4_UNSUPPORTED;'
    body=(f'if (c->verify_instruction_bytes) {{ uint64_t low,high; '
          f'if (!ac4_load(c,pc,4,&low,&high)) return c->memory_error; '
          f'if (low!=UINT32_C(0x{word:08x})) return AC4_MODIFIED; }}\n')+body
    return f'case UINT32_C(0x{pc:08x}): {{\n{body}\n}}\n'


def emit_program(words, entry, *, stop_unsupported=False):
    if entry not in words:
        raise TranslationError('entry outside supplied instruction map')
    parts=[RUNTIME]
    for pc in sorted(words):
        parts.append(emit_case(words[pc],pc,stop_unsupported=stop_unsupported))
    parts.append('default: c->fault_address=pc; return AC4_FETCH;\n}\n}\nreturn AC4_BUDGET;\n}\n')
    return ''.join(parts)


def emit_modules(words,entry,*,stop_unsupported=False):
    """Same CPU semantics in stable per-4-KiB translation units for native builds.

    Page dispatch is over generated guest addresses, not guest opcodes. The
    single-file backend remains available for small fixtures and differential QA.
    """
    if entry not in words:
        raise TranslationError('entry outside supplied instruction map')
    header,loop=RUNTIME.split('int ac4_run(Ac4Cpu *c, uint64_t budget) {',1)
    files={'ac4_cpu.h':'#ifndef AC4_GENERATED_CPU_H\n#define AC4_GENERATED_CPU_H\n'+header+
           '\nint ac4_run(Ac4Cpu *,uint64_t);\nint ac4_dispatch(Ac4Cpu *,uint32_t,unsigned,uint32_t);\n#endif\n'}
    loop=loop.removesuffix('        switch (pc) {\n')
    files['ac4_runtime.c']='#include "ac4_cpu.h"\nint ac4_run(Ac4Cpu *c,uint64_t budget) {'+loop+\
        '        int status=ac4_dispatch(c,pc,delay,resume);\n        if (status) return status;\n}\nreturn AC4_BUDGET;\n}\n'
    pages={}
    for pc in sorted(words):
        pages.setdefault(pc>>12,[]).append(emit_case(words[pc],pc,stop_unsupported=stop_unsupported))
    dispatch=['#include "ac4_cpu.h"\n']
    for page,cases in sorted(pages.items()):
        name=f'ac4_page_{page:05x}'
        signature=f'int {name}(Ac4Cpu *c,uint32_t pc,unsigned delay,uint32_t resume)'
        dispatch.append(signature+';\n')
        files[name+'.c']='#include "ac4_cpu.h"\n'+signature+\
            ' {\n(void)delay; (void)resume;\nswitch (pc) {\n'+''.join(cases)+\
            'default: c->fault_address=pc; return AC4_FETCH;\n}\nreturn 0;\n}\n'
    dispatch.append('int ac4_dispatch(Ac4Cpu *c,uint32_t pc,unsigned delay,uint32_t resume) {\nswitch (pc>>12) {\n')
    for page in sorted(pages):
        dispatch.append(f'case UINT32_C(0x{page:05x}): return ac4_page_{page:05x}(c,pc,delay,resume);\n')
    dispatch.append('default: c->fault_address=pc; return AC4_FETCH;\n}\n}\n')
    files['ac4_dispatch.c']=''.join(dispatch)
    return files


def bounded_plan(words, entries, *, limit=1024, resume_syscalls=False):
    """Select a bounded static map; every missing/unsupported execution still stops.

    Optional syscall continuations are only code selection, never service success.
    Indirect destinations are not guessed. A queue limit bounds generation work.
    """
    from collections import deque
    if not isinstance(limit, int) or limit < 1:
        raise TranslationError('positive instruction selection limit required')
    queue, selected, rejected = deque(entries), {}, {}
    seen = set()
    while queue and len(selected) < limit:
        pc = queue.popleft()
        if pc in seen:
            continue
        seen.add(pc)
        if pc not in words:
            rejected[pc] = 'outside selected image words'
            continue
        try:
            ins = decode(words[pc], pc)
        except DecodeError as error:
            rejected[pc] = str(error)
            continue
        selected[pc] = words[pc]
        try:
            translate(ins)
        except TranslationError as error:
            rejected[pc] = str(error)
            continue
        if ins.has_delay_slot:
            # The slot is selected independently as well as in branch context.
            queue.append((pc+4)&0xffffffff)
            if ins.target is not None:
                queue.append(ins.target)
            if ins.flow == 'branch' or ins.link_register is not None:
                queue.append((pc+8)&0xffffffff)
        elif ins.flow == 'normal' or (resume_syscalls and ins.mnemonic == 'syscall'):
            queue.append((pc+4)&0xffffffff)
    return selected, dict(selected_addresses=len(selected), selection_limit=limit,
                          pending_addresses=len(set(queue)-seen),
                          boundaries=[dict(address=f'0x{pc:08x}', reason=reason)
                                      for pc, reason in sorted(rejected.items())],
                          syscall_continuations_selected=resume_syscalls)


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
