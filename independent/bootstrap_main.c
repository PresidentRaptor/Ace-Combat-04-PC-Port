/* Diagnostic startup runner, not a playable game or complete PS2 kernel. */
#include "generated_program.inc"
#include "bootstrap_services.h"
#include "ee_devices.h"
#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>

int main(int argc, char **argv) {
    if (argc!=2) {
        fprintf(stderr,"Usage: ac4-independent-bootstrap <verified-build-ram.bin>\n");
        return 64;
    }
    FILE *file=fopen(argv[1],"rb");
    unsigned char *ram=malloc(32*1024*1024);
    if (!file || !ram) {
        if (file) fclose(file);
        free(ram); fprintf(stderr,"Cannot open RAM image or allocate memory.\n"); return 65;
    }
    size_t got=fread(ram,1,32*1024*1024,file);
    int extra=fgetc(file), failed=ferror(file);
    fclose(file);
    if (got!=32*1024*1024 || extra!=EOF || failed) {
        free(ram); fprintf(stderr,"RAM image must be exactly 32 MiB.\n"); return 65;
    }
    Ac4Cpu cpu={0}; Ac4Bootstrap boot={0};
    boot.enable_guest_overrides=1;
    Ac4Devices devices={0};
    cpu.memory=ram; cpu.memory_size=32*1024*1024; cpu.pc=AC4_PROGRAM_ENTRY;
    cpu.ee_memory_map=1;
    cpu.verify_instruction_bytes=1;
    /* Explicit application startup profile, not a captured BIOS Status value. */
    const uint32_t initial_status=UINT32_C(0x20000000);
    cpu.cp0_status=initial_status;
    cpu.device_state=&devices; cpu.device_read=ac4_device_read; cpu.device_write=ac4_device_write;
    int status=ac4_bootstrap_run(&cpu,&boot,UINT64_C(5000000));
    printf("{\"scope\":\"experimental-bootstrap-diagnostic\",\"status\":%d,"
           "\"pc\":%u,\"fault_pc\":%u,\"fault_address\":%u,\"delay\":%u,"
           "\"steps\":%" PRIu64 ",\"services_completed\":%u,\"last_syscall\":%u,"
           "\"stack_pointer\":%u,\"heap_start\":%u,\"heap_end\":%u,"
           "\"override_target\":%u,\"current_thread\":%u,\"context_switches\":%u,"
           "\"sif0_waiting\":%u,\"last_device_read_address\":%u,\"last_device_read_value\":%" PRIu64 ","
           "\"initial_cp0_status\":%u,"
           "\"a0\":%" PRIu64 ",\"a1\":%" PRIu64 ",\"a2\":%" PRIu64 "}\n",
           status,cpu.pc,cpu.fault_pc,cpu.fault_address,cpu.fault_delay,cpu.steps,
           boot.calls,boot.last_number,boot.stack_pointer,boot.heap_start,boot.heap_end,
           boot.last_number<256 ? boot.syscall_overrides[boot.last_number] : 0,
           boot.current_thread,boot.context_switches,
           devices.sif0_waiting,devices.last_read_address,devices.last_read_value,
           initial_status,
           cpu.gpr[4][0],cpu.gpr[5][0],cpu.gpr[6][0]);
    free(ram);
    /* Diagnostic stops are explicitly unsuccessful execution, not a game exit. */
    return status==AC4_BREAK ? 0 : 2;
}
