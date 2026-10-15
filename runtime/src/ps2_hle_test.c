#include "ps2_runtime.h"
#include "ps2_hle.h"
#include "ps2_vfs.h"
#include <string.h>

void hle_sceSifAllocIopHeap(ps2_ctx *);
void hle_sceSifFreeIopHeap(ps2_ctx *);
void hle_sceSifAllocSysMemory(ps2_ctx *);
void hle_sceSifQueryMaxFreeMemSize(ps2_ctx *);
void hle_sceSifQueryTotalFreeMemSize(ps2_ctx *);
void hle_scePad2Init(ps2_ctx *);
void hle_scePad2End(ps2_ctx *);
void hle_scePad2CreateSocket(ps2_ctx *);
void hle_scePad2DeleteSocket(ps2_ctx *);
void hle_sceVibGetProfile(ps2_ctx *);
void hle_scePadInit(ps2_ctx *);
void hle_scePadPortOpen(ps2_ctx *);
void hle_scePadPortClose(ps2_ctx *);
void hle_scePadGetState(ps2_ctx *);
void hle_scePadRead(ps2_ctx *);
void ps2_iop_services_register(void);
void ps2_build_dispatch(void);

static u32 invoke(void (*fn)(ps2_ctx *), u32 a, u32 b, u32 c) {
    ps2_ctx ctx = {0};
    ctx.r[4].ud[0] = a;
    ctx.r[5].ud[0] = b;
    ctx.r[6].ud[0] = c;
    fn(&ctx);
    return ctx.r[2].uw[0];
}

int ps2_hle_selftest(const char *disc) {
    int fail = 0;
    const u32 send = 0x10000, recv = 0x11000;
    ps2_build_dispatch();
    ps2_sif_hle_init();
    ps2_cdvd_init();
    ps2_cdvd_rpc_register();
    ps2_iop_services_register();
    ps2_pad_init();
    u32 capacity = invoke(hle_sceSifQueryTotalFreeMemSize, 0, 0, 0);
    u32 first = invoke(hle_sceSifAllocIopHeap, 513, 0, 0);
    fail += !first;
    fail += invoke(hle_sceSifFreeIopHeap, first + 256, 0, 0) != (u32)-1;
    fail += invoke(hle_sceSifFreeIopHeap, first, 0, 0) != 0;
    fail += invoke(hle_sceSifFreeIopHeap, first, 0, 0) != (u32)-1;
    for (int i = 0; i < 64; i++) {
        u32 p = invoke(hle_sceSifAllocIopHeap, capacity, 0, 0);
        fail += p != first;
        fail += invoke(hle_sceSifAllocIopHeap, 1, 0, 0) != 0;
        fail += invoke(hle_sceSifFreeIopHeap, p, 0, 0) != 0;
    }
    fail += invoke(hle_sceSifAllocIopHeap, 0xffffffffu, 0, 0) != 0;
    u32 fixed = first + 512;
    fail += invoke(hle_sceSifAllocSysMemory, 2, 256, fixed) != fixed;
    fail += invoke(hle_sceSifAllocSysMemory, 2, 256, fixed) != 0;
    fail += invoke(hle_sceSifAllocSysMemory, 2, 256, fixed + 1) != 0;
    fail += invoke(hle_sceSifQueryMaxFreeMemSize, 0, 0, 0) != capacity - 768;
    fail += invoke(hle_sceSifQueryTotalFreeMemSize, 0, 0, 0) != capacity - 256;
    fail += invoke(hle_sceSifAllocSysMemory, 1, 256, 0) != first + capacity - 256;
    ps2_sif_hle_init();
    ps2_cdvd_rpc_register();
    ps2_iop_services_register();
    fail += invoke(hle_scePad2Init, 0, 0, 0) != 1;
    for (int i = 0; i < 16; i++)
        fail += invoke(hle_scePad2CreateSocket, 0, 0, 0) != (u32)i;
    fail += invoke(hle_scePad2CreateSocket, 0, 0, 0) != (u32)-1;
    fail += invoke(hle_scePad2End, 0, 0, 0) != 1;
    fail += invoke(hle_scePad2Init, 0, 0, 0) != 1;
    fail += invoke(hle_scePad2CreateSocket, 0, 0, 0) != 0;
    ps2_w8(recv, 0xff);
    fail += invoke(hle_sceVibGetProfile, 0, recv, 0) != 1;
    fail += ps2_r8(recv) != 3;
    {
        /* AC4 uses the original libpad interface. */
        fail += invoke(hle_scePadInit, 0, 0, 0) != 1;
        fail += invoke(hle_scePadRead, 0, 0, recv) != 0;
        fail += invoke(hle_scePadPortOpen, 0, 1, send) != 0;
        fail += invoke(hle_scePadPortOpen, 0, 0, send) != 1;
        ps2_pad_host[0].connected = 1;
        ps2_pad_host[0].buttons = (1u << 14) | (1u << 7); /* Cross + Left */
        ps2_pad_host[0].lx = 17; ps2_pad_host[0].ly = 239;
        ps2_pad_host[0].rx = 128; ps2_pad_host[0].ry = 128;
        ps2_w8(recv + 32, 0xa5);
        fail += invoke(hle_scePadGetState, 0, 0, 0) != 6;
        fail += invoke(hle_scePadRead, 0, 0, recv) != 32;
        fail += ps2_r8(recv) != 0 || ps2_r8(recv + 1) != 0x73;
        fail += ps2_r16(recv + 2) != (u16)~ps2_pad_host[0].buttons;
        fail += ps2_r8(recv + 6) != 17 || ps2_r8(recv + 7) != 239;
        fail += ps2_r8(recv + 32) != 0xa5;
        ps2_pad_host[0].buttons = 0;
        fail += invoke(hle_scePadRead, 0, 0, recv) != 32;
        fail += ps2_r16(recv + 2) != 0xffff;
        fail += invoke(hle_scePadPortClose, 0, 0, 0) != 1;
        fail += invoke(hle_scePadRead, 0, 0, recv) != 0;
        ps2_log("AC4 libpad contract checked: closed port, slot rejection, active-low buttons, sticks, release, buffer bounds");
    }
    fail += invoke(hle_scePad2DeleteSocket, 0, 0, 0) != 1;
    fail += invoke(hle_scePad2DeleteSocket, 0, 0, 0) != (u32)-1;
    ps2_w8(recv + 5, 0xa5);
    fail += ps2_rpc_call(0x80000001u, 0, 0, 0, recv, 5) != 0;
    fail += ps2_r8(recv + 5) != 0xa5;
    fail += ps2_rpc_call(0x80000593u, 3, 0, 0, recv, 5) != 0;
    fail += ps2_r32(recv) != 0 || ps2_r8(recv + 5) != 0xa5;
    if (disc) {
        fail += ps2_vfs_open(disc) != 0;
        /* AC4's boot files */
        const ps2_disc_file *boot = ps2_vfs_find("\\SYSTEM.CNF;1");
        const ps2_disc_file *elf = ps2_vfs_find("\\SLUS_201.52;1");
        char cnf[512] = {0};
        unsigned char magic[4] = {0};
        int bytes = boot ? ps2_vfs_read(boot, 0, sizeof(cnf)-1, cnf) : -1;
        fail += bytes <= 0 || strstr(cnf, "SLUS_201.52") == NULL;
        fail += !elf || ps2_vfs_read(elf, 0, 4, magic) != 4 || memcmp(magic, "\177ELF", 4);
        ps2_log("AC4 disc boot files checked (SYSTEM.CNF and SLUS_201.52)");
    }
    ps2_log("HLE contract regressions: %s (%d failures)", fail ? "FAILED" : "passed", fail);
    return fail != 0;
}
