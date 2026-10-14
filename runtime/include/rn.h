#ifndef RN_H
#define RN_H

#include "ps2_runtime.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Graphics-stream dump of one field (PS2_RN_DUMP=<file>, PS2_RN_DUMP_FIELD=<n>):
   VIF1 unpacks and microprogram uploads, XGKICKs and GS register writes. */
extern int rn_dump_on;
void rn_dump_init(void);
void rn_dump_frame(void);
void rn_dump_vif(u32 code, u32 tops, u32 cl, u32 wl, u32 tpc, const u8 *mem,
                 const u8 *micro);
void rn_dump_xgkick(u32 addr, const u8 *mem, u32 mem_size);
void rn_dump_gsreg(u32 reg, u64 val);

#ifdef __cplusplus
}
#endif

#endif
