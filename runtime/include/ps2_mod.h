#ifndef PS2_MOD_H
#define PS2_MOD_H

#include "ps2_runtime.h"
#include "ac4mod.h"

#ifdef __cplusplus
extern "C" {
#endif

void ps2_mod_init(void);

void ps2_mod_start(void);

void ps2_mod_report(void);

unsigned ps2_mod_count(void);
const char *ps2_mod_id_at(unsigned i);
const char *ps2_mod_dir_at(unsigned i);
int ps2_mod_enabled_at(unsigned i);
int ps2_mod_enabled_setting_at(unsigned i);
int ps2_mod_set_enabled_at(unsigned i, int enabled);
const ac4_api *ps2_mod_api_at(unsigned i);

#ifdef __cplusplus
}
#endif

#endif
