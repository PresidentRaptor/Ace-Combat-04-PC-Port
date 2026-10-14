#include "ps2_runtime.h"
#include "ps2_hle.h"
#include "ps2_vfs.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void zero_reply(u32 recv, int rsize) {
    if (recv && rsize > 0)
        for (int i = 0; i < rsize; i++) ps2_w8(recv + (u32)i, 0);
}

#define LGDEV_SID       0x046D046Du
#define LGDEV_FNO_ENUM  1
#define LGDEV_FNO_INIT  12
#define LGDEV_FNO_CONF  18
#define LGDEV_VERSION   0x108u
#define LGDEV_ERR_NO_MORE_DEVICES 0x80000002u

static int lgdev_rpc(ps2_ctx *ctx, u32 fno, u32 send, int ssize,
                     u32 recv, int rsize) {
    (void)ctx; (void)send; (void)ssize;
    zero_reply(recv, rsize);
    if (fno == LGDEV_FNO_ENUM && rsize >= 4) {
        static int said;
        ps2_w32(recv, LGDEV_ERR_NO_MORE_DEVICES);
        if (!said) {
            said = 1;
            ps2_log("lgdev: enumerate -> no devices attached");
        }
    }
    if (fno == LGDEV_FNO_INIT && rsize >= 8) {
        ps2_w32(recv + 4, LGDEV_VERSION);
        ps2_log("lgdev: reported version %u.%02u", LGDEV_VERSION >> 8,
                LGDEV_VERSION & 0xFF);
    }
    return 0;
}

#define DBC_SID_MAIN    0x80001300u
#define DBC_FNO_VERSION 0x80001363u
#define DBC_VERSION     0x0300u

static int dbc_rpc(ps2_ctx *ctx, u32 fno, u32 send, int ssize,
                   u32 recv, int rsize) {
    (void)ctx; (void)send; (void)ssize;
    zero_reply(recv, rsize);
    if (fno == DBC_FNO_VERSION && rsize >= 4)
        ps2_w32(recv, DBC_VERSION);
    return 0;
}

#define DEV_SID          0x80000210u
#define DEV_FNO_REPORT   2u

static int dev_rpc(ps2_ctx *ctx, u32 fno, u32 send, int ssize,
                   u32 recv, int rsize) {
    (void)ctx; (void)ssize;
    zero_reply(recv, rsize);
    if (fno == DEV_FNO_REPORT) ps2_dbc_report(send, recv, rsize);
    return 0;
}

static int ok_rpc(ps2_ctx *ctx, u32 fno, u32 send, int ssize,
                  u32 recv, int rsize) {
    (void)ctx; (void)fno; (void)send; (void)ssize;
    zero_reply(recv, rsize);
    return 0;
}

#define MCSERV_SID       0x80000400u
#define MCSERV_FNO_INIT  254u
#define MCSERV_VERSION   522u
#define MCMAN_VERSION    526u

static int mcserv_rpc(ps2_ctx *ctx, u32 fno, u32 send, int ssize,
                      u32 recv, int rsize) {
    extern int ps2_memcard_rpc(ps2_ctx *,u32,u32,int,u32,int);
    return ps2_memcard_rpc(ctx,fno,send,ssize,recv,rsize);
}

void ps2_iop_services_register(void) {
    ps2_rpc_register(LGDEV_SID,   lgdev_rpc, "lgdev");
    ps2_rpc_register(DBC_SID_MAIN, dbc_rpc,  "dbcman");
    ps2_rpc_register(0x8000131Bu, dbc_rpc,   "dbcman-b");
    ps2_rpc_register(0x8000131Cu, dbc_rpc,   "dbcman-c");
    ps2_rpc_register(0x80000001u, ok_rpc,    "fileio");
    ps2_rpc_register(0x80000003u, ok_rpc,    "sysmem");
    ps2_rpc_register(0x80000006u, ok_rpc,    "loadfile");
    ps2_rpc_register(MCSERV_SID,  mcserv_rpc, "mcserv");
    ps2_rpc_register(DEV_SID,     dev_rpc,   "devices");
}

void hle_write(ps2_ctx *ctx) {
    static char line[1024];
    static size_t fill;
    int fd = (int)ps2_arg(ctx, 0);
    u32 buf = ps2_arg(ctx, 1);
    int len = (int)ps2_arg(ctx, 2);
    if (fd != 1 && fd != 2) { HRET(-1); return; }
    for (int i = 0; i < len; i++) {
        char c = (char)ps2_r8(buf + (u32)i);
        if (c == '\n' || fill == sizeof(line) - 1) {
            line[fill] = 0;
            if (fill) ps2_log("guest: %s", line);
            fill = 0;
            if (c != '\n') line[fill++] = c;
        } else if (c != '\r') {
            line[fill++] = c;
        }
    }
    HRET(len);
}

