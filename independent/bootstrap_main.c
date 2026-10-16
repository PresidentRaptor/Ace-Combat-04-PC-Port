/* Diagnostic startup runner, not a playable game or complete PS2 kernel. */
#include "generated_program.inc"
#include "bootstrap_services.h"
#include "ee_devices.h"
#include "sif_transport.h"
#include "iop_command_peer.h"
#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>

#ifndef AC4_IOP_COMMAND_PROFILE
#define AC4_IOP_COMMAND_PROFILE 0
#endif
typedef struct {
    Ac4Devices *devices;
    Ac4SifTransport transport;
    Ac4IopCommandPeer peer;
    const char *stop_origin;
} Ac4SifEvents;
static int ac4_poll_sif(void *state,Ac4Cpu *cpu) {
    Ac4SifEvents *events=(Ac4SifEvents *)state;
    if (events->peer.count && (events->devices->dma[6].chcr&0x100)) {
        events->stop_origin="sif1-ownership-conflict"; return AC4_DEVICE;
    }
    int result=ac4_sif_poll(cpu,events->devices,&events->transport,16);
    if (result) {
        events->stop_origin=ac4_sif_irq_pending(events->devices) ? "pending-dma-irq" : "ee-sif-transport";
        return result;
    }
    result=ac4_iop_poll(&events->peer,cpu,16);
    if (result) events->stop_origin="iop-command-peer";
    return result;
}

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
    Ac4SifEvents events={0}; events.devices=&devices;
    boot.event_state=&events; boot.poll_events=ac4_poll_sif;
    cpu.memory=ram; cpu.memory_size=32*1024*1024; cpu.pc=AC4_PROGRAM_ENTRY;
    cpu.ee_memory_map=1;
    cpu.verify_instruction_bytes=1;
    cpu.coherent_cache_profile=1;
    /* Explicit application startup profile, not a captured BIOS Status value. */
    const uint32_t initial_status=UINT32_C(0x20000000);
    cpu.cp0_status=initial_status;
    cpu.device_state=&devices; cpu.device_read=ac4_device_read; cpu.device_write=ac4_device_write;
    unsigned char *iop_ram=NULL;
    if (AC4_IOP_COMMAND_PROFILE) {
        iop_ram=calloc(1,2*1024*1024);
        if (!iop_ram || ac4_iop_start(&events.peer,&devices,&events.transport,iop_ram,2*1024*1024,0x1000)) {
            free(iop_ram); free(ram); fprintf(stderr,"Cannot start IOP command profile.\n"); return 65;
        }
        /* Explicit host service startup, not a measured BIOS register state. */
        devices.d_ctrl=1;
        boot.sif_service_state=&events.peer; boot.sif_service=ac4_iop_service;
    }
    int status=ac4_bootstrap_run(&cpu,&boot,UINT64_C(5000000));
    printf("{\"scope\":\"experimental-bootstrap-diagnostic\",\"status\":%d,"
           "\"pc\":%u,\"fault_pc\":%u,\"fault_address\":%u,\"delay\":%u,"
           "\"steps\":%" PRIu64 ",\"services_completed\":%u,\"last_syscall\":%u,"
           "\"stack_pointer\":%u,\"heap_start\":%u,\"heap_end\":%u,"
           "\"override_target\":%u,\"current_thread\":%u,\"context_switches\":%u,"
           "\"sif0_waiting\":%u,\"last_device_read_address\":%u,\"last_device_read_value\":%" PRIu64 ","
           "\"initial_cp0_status\":%u,\"coherent_cache_profile\":%u,"
           "\"sif0_quadwords\":%" PRIu64 ",\"sif1_quadwords\":%" PRIu64 ","
           "\"sif0_fifo_words\":%u,\"sif1_fifo_words\":%u,"
           "\"iop_command_profile\":%u,\"iop_commands\":%" PRIu64 ",\"iop_received_transfers\":%" PRIu64 ","
           "\"iop_submitted_quadwords\":%" PRIu64 ",\"iop_last_command\":%u,\"iop_last_option\":%u,"
           "\"iop_ee_receive_buffer\":%u,\"iop_pending_jobs\":%u,"
           "\"iop_dma_source\":%u,\"iop_dma_destination\":%u,\"iop_dma_size\":%u,\"iop_dma_attribute\":%u,"
           "\"iop_reply_packets\":%" PRIu64 ",\"iop_rpc_init_ack_generated\":%u,\"dma_status\":%u,"
           "\"stop_origin\":\"%s\",\"cpu_fault_context_applies\":%u,\"dma_irq_pending\":%u,"
           "\"a0\":%" PRIu64 ",\"a1\":%" PRIu64 ",\"a2\":%" PRIu64 "}\n",
           status,cpu.pc,cpu.fault_pc,cpu.fault_address,cpu.fault_delay,cpu.steps,
           boot.calls,boot.last_number,boot.stack_pointer,boot.heap_start,boot.heap_end,
           boot.last_number<256 ? boot.syscall_overrides[boot.last_number] : 0,
           boot.current_thread,boot.context_switches,
           devices.sif0_waiting,devices.last_read_address,devices.last_read_value,
           initial_status,cpu.coherent_cache_profile,
           events.transport.quadwords[0],events.transport.quadwords[1],
           events.transport.to_ee.count,events.transport.to_iop.count,
           (unsigned)AC4_IOP_COMMAND_PROFILE,events.peer.accepted_commands,events.peer.received_transfers,
           events.peer.submitted_quadwords,events.peer.last_command,events.peer.last_option,
           events.peer.ee_receive_buffer,events.peer.count,
           events.peer.last_source,events.peer.last_destination,events.peer.last_size,events.peer.last_attribute,
           events.peer.reply_packets,events.peer.rpc_init_ack_generated,devices.d_stat,
           events.stop_origin ? events.stop_origin : "cpu-or-kernel",events.stop_origin==NULL,
           (unsigned)!!ac4_sif_irq_pending(&devices),
           cpu.gpr[4][0],cpu.gpr[5][0],cpu.gpr[6][0]);
    free(iop_ram); free(ram);
    /* Diagnostic stops are explicitly unsuccessful execution, not a game exit. */
    return status==AC4_BREAK ? 0 : 2;
}
