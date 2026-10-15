/* New synthetic harness. No game code, old runtime or AC5 interfaces. */
#include "synthetic.inc"
#include <stdio.h>

int main(void) {
    Ac4Cpu cpu = {0};
    int status = ac4_run(&cpu, 16);
    if (status != AC4_BREAK || cpu.gpr[2][0] != 7 || cpu.pc != 4 || cpu.steps != 2) {
        fprintf(stderr, "Synthetic scalar execution failed (status %d).\n", status);
        return 1;
    }
    puts("Independent scalar harness passed; this target does not run AC4.");
    return 0;
}
