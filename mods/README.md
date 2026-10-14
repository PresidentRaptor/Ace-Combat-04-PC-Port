# Mods

Drop a mod in here as a directory. It is picked up the next time the game
starts — nothing to rebuild, nothing to repack.

```
mods/
  my_mod/
    mod.toml                          optional
    files/
      VAG/BRIEF01.VPK                 a whole file on the disc
      my_mod/table.bin                a new file, for scripts to read
    script.lua                        Lua, run at startup
    lib/helpers.lua                   a module, for require("lib.helpers")
    patch.pnach                       PCSX2 patches (data patches work)
    symbols.txt                       names for functions
    module.dll                        native code, only with native = true
```

## What a mod can change

| Layer | How | Example |
| --- | --- | --- |
| Files | `files/` | music, briefings, movies |
| Memory | `.pnach`, `ac5.patch` | a PCSX2 data patch |
| Functions | `ac5.hook_before/after/replace`, `ac5.redirect` | new weapon behaviour |
| Over time | `ac5.every`, `ac5.after`, field callbacks | a HUD counter |
| The controller | `ac5.on_input`, `ac5.pad` | remapping, macros |
| Between runs | `ac5.store`, `ac5.stored` | unlocks, statistics |

The mod interface was written for the Ace Combat 5 runtime this port grew from,
which is why its names start with `ac5`. Three of its calls hooked parts of
AC5 that Ace Combat 04 does not have, and are refused here: `on_frame`,
`on_scene` and `param`.

## The filesystem the game reads from

The game does not read the disc directly. Every read — the CD library, the
sound and music streams and the movies — goes through one filesystem, and mods
are layers in it. This works the same on a `.iso` and on an extracted disc
directory.

A file under `files/` is named by its path on the disc, without regard to
case: `VAG/BRIEF01.VPK` replaces that file, and its size may change. Anything
that is not on the disc is a new file, which scripts can read; the log says
so, because it is usually a typo. Ace Combat 04 keeps most of its data in
`BIN/DATA.CDP`, so for now a mod replaces that file whole or not at all.

## Memory patches: .pnach

PCSX2 `.pnach` files work as they do in PCSX2 for patches that change data:
`patch=place,EE,address,type,value`, where place 0 means once at start, 1 means
every field and 2 means both. Two kinds are refused, each with a message:
- **Patches into the game's code.** The code was recompiled, so they would
  change nothing; use a hook instead.
- **Conditional extended codes.** The rest of that section is skipped, because
  the lines after a conditional depend on it.

Two mods patching the same bytes: the higher priority keeps them.

From a script, `ac5.patch(addr, value, width, original, when)` does the same.
With `original`, the patch is only written over that value, which protects
against patching memory that holds something else.

## Scripts

Every `.lua` file in a mod's directory runs at startup, in name order. Put
modules for `require` in a subdirectory. A script sees one table, `ac5`, which
is `runtime/include/ac5mod.h` call for call:

```lua
-- functions: by address, or by name (the recompiler's names, symbols.txt)
ac5.hook_before(0x00263718, function(ctx) count = count + 1 end)
ac5.hook_after("sceVu0ViewScreenMatrix", function(ctx)
    ac5.log("camera set up")
end)
local h = ac5.hook_replace(0x00123456, function(ctx)
    if not wanted then return false end    -- the game's own function runs
    ac5.set_return(ctx, 1)
end)
ac5.unhook(h)

local t = ac5.every(600, function() ac5.log("ten seconds") end)
ac5.after(60, function() ac5.cancel(t) end)

-- the controller, before the game sees it
ac5.on_input(function(pads)
    if pads[1].buttons & ac5.BTN.l3 ~= 0 then
        pads[1].buttons = pads[1].buttons | ac5.BTN.cross
    end
end)

ac5.store("best_score", 12345)          -- saves/mods/<id>.txt
local helpers = require("lib.helpers")
```

Hooks and callbacks return a handle. `unhook` detaches hooks; `cancel` stops
callbacks and timers.

Each mod has its own globals. `io`, `os`, `dofile`, `loadfile` and
`collectgarbage` are not there, and `load` takes source text only. A callback
that raises an error is reported for its first three failures and switched off
after ten; a switched-off replacement lets the game's own function run. The
`ctx` a callback is given is valid only while that callback runs.

A function with an after-hook is called rather than jumped to. If a guest loop
runs through it by tail jumps more than 256 calls deep, the deeper calls skip
their after-hooks rather than growing the stack; the run summary counts it.

## Native modules

A DLL exporting `int ac5_mod_main(const ac5_api *api)` loads only when the
mod's manifest says `native = true`. It is ordinary code in the game's process,
so only enable it for mods you trust. Check `api->abi_version >=
AC5_ABI_VERSION`: fields are only ever added.

## mod.toml

Every field is optional.

```toml
name     = "Custom Music"
version  = "1.0"
author   = "someone"
priority = 10            # higher wins every conflict; default 0
enabled  = false         # switch it off without deleting it
native   = true          # allow the DLLs in this directory to load
requires = "base_pack >= 1.2, helpers"
abi      = 3             # the mod ABI it needs, at least
game     = "SLUS-20152"

[config]
volume   = "0.8"         # read back with ac5.config("volume")
```

A mod whose requirements are not met is switched off, and the log and the run
summary say why. That covers a missing or switched-off mod, a version outside
the range, a newer ABI, a different game, or a requirement cycle. Mods load
after the mods they require.

## When two mods want the same thing

Priority decides everywhere: the same file, hooked function, indirect-call
target or memory bytes. At equal priority the mod whose directory name sorts
later wins. Every conflict is in the log with both sides named.

## When something goes wrong

- `PS2_NO_MODS=1` turns the whole layer off. Always the first thing to try.
- `PS2_MOD_DIR=path` loads from somewhere else.
- The run summary lists every mod, what it supplied, why any were switched
  off, every conflict, hook and patch, and every script error.
