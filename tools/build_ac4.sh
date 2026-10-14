#!/bin/bash
# Regenerate AC4's C code from SLUS_201.52 and rebuild ac4.exe.
# usage: tools/build_ac4.sh PATH/TO/SLUS_201.52
set -e
cd "$(dirname "$0")/.."
ELF=${1:?path to SLUS_201.52}
export PATH="/c/msys64/ucrt64/bin:$PATH"
rm -rf generated
PYTHONPATH=tools python -m ps2recomp "$ELF" -o generated \
    --ida-db config/ac4/ida_db.json \
    --ida-seeds config/ac4/seeds.json \
    --symbols config/ac4/sdk_symbols.json \
    --symbols config/ac4/manual_symbols.json \
    --overrides config/ac4/overrides.json \
    --hooks config/ac4/hooks.json \
    --report config/ac4/report.json | grep -v '^seed: handler'
if [ ! -f build/gcc/build.ninja ]; then
    cmake -S . -B build/gcc -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_COMPILER=C:/msys64/ucrt64/bin/gcc.exe \
        -DCMAKE_CXX_COMPILER=C:/msys64/ucrt64/bin/c++.exe \
        -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64
fi
cmake --build build/gcc > build/build.log 2>&1 || { grep -E 'error' -A3 build/build.log | head -40; exit 1; }
grep -E ' error|Linking' build/build.log || true
