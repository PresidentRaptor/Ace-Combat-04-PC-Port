/* Legacy source compatibility for AC4 mods using the original API names.
 * New mods should include ac4mod.h. The ABI layout remains version 3. */
#ifndef AC5MOD_H
#define AC5MOD_H
#include "ac4mod.h"

#define AC5_ABI_VERSION AC4_ABI_VERSION
#define AC5_BTN_CIRCLE AC4_BTN_CIRCLE
#define AC5_BTN_CROSS AC4_BTN_CROSS
#define AC5_BTN_DOWN AC4_BTN_DOWN
#define AC5_BTN_LEFT AC4_BTN_LEFT
#define AC5_BTN_RIGHT AC4_BTN_RIGHT
#define AC5_BTN_SELECT AC4_BTN_SELECT
#define AC5_BTN_SQUARE AC4_BTN_SQUARE
#define AC5_BTN_START AC4_BTN_START
#define AC5_BTN_TRIANGLE AC4_BTN_TRIANGLE
#define AC5_BTN_UP AC4_BTN_UP
#define AC5_PAD_PORTS AC4_PAD_PORTS
#define AC5_PATCH_ALWAYS AC4_PATCH_ALWAYS
#define AC5_PATCH_BOTH AC4_PATCH_BOTH
#define AC5_PATCH_ONCE AC4_PATCH_ONCE
#define ac5_api ac4_api
#define ac5_ctx ac4_ctx
#define ac5_field_fn ac4_field_fn
#define ac5_frame_fn ac4_frame_fn
#define ac5_hook_fn ac4_hook_fn
#define ac5_input_fn ac4_input_fn
#define ac5_mod_main_fn ac4_mod_main_fn
#define ac5_pad ac4_pad
#define ac5_scene_fn ac4_scene_fn

#define AC5_BTN_L1 AC4_BTN_L1
#define AC5_BTN_L2 AC4_BTN_L2
#define AC5_BTN_L3 AC4_BTN_L3
#define AC5_BTN_R1 AC4_BTN_R1
#define AC5_BTN_R2 AC4_BTN_R2
#define AC5_BTN_R3 AC4_BTN_R3

#endif
