#ifndef PS2_MODAPI_H
#define PS2_MODAPI_H

#include "ps2_runtime.h"
#include "ps2_hle.h"
#include "ac4mod.h"

#ifdef __cplusplus
extern "C" {
#endif

const ac4_api *ps2_modapi_for(const char *mod_id, int priority,
                              const char *(*config_get)(const char *mod_id,
                                                        const char *key));

void ps2_modapi_field_tick(void);

void ps2_modapi_input(ps2_pad_state *pads, int ports);

void ps2_modapi_shutdown(void);

const ac4_api *ps2_modapi_enter(const ac4_api *api);
void ps2_modapi_leave(const ac4_api *previous);

void ps2_modapi_report(void);

void ps2_lua_start(void);
void ps2_lua_report(void);

#ifdef __cplusplus
}
#endif

#endif
