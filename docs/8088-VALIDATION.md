# 8088 validation scope

The browser is compiled with the native ELKS IA16 GCC flags `-march=i8086 -mtune=i8086`, and the retained ELF is checked for instructions outside that target. Static inspection complements emulator execution; neither establishes physical hardware compatibility by itself.

The retained Windows 86Box configurations select `machine=ibmxt86`, `cpu_family=8088`, `cpu_speed=4772728`, `cpu_use_dynarec=0` and `mem_size=640`. The official [86Box 4.2.1 CPU table](https://github.com/86Box/86Box/blob/v4.2.1/src/cpu/cpu_table.c) maps that family/speed to the Intel 8088 entry. CGA, EGA and VGA are tested in separate configurations. ROMs are obtained separately and are not distributed here.

## ELKS CPU-label discrepancy

Some guest boot captures show CPU index 2 (V20), despite the selected 8088. The pinned ELKS [CPU probe](https://github.com/ghaerr/elks/blob/89d09706f17c123f9e0f5ef7cba2eb6745e8478c/elks/arch/i86/boot/cputype.S) explicitly describes itself as obsolete and inaccurate. Its interrupt-enable instruction before the repeated-load test is commented out; a zero count branches toward the NEC classification. The [disk setup path](https://github.com/ghaerr/elks/blob/89d09706f17c123f9e0f5ef7cba2eb6745e8478c/elks/arch/i86/boot/setup.S) disables interrupts before calling this probe.

These source observations provide a plausible explanation for a false V20 label. They are not a guest execution trace proving the interrupt flag's value during detection. We retain the discrepancy and identify the emulator's configured CPU explicitly rather than treating the guest label as independent certification. The browser does not select a V20 instruction target from this boot message.

QEMU uses a 486 CPU for general ELKS integration testing. It supplies no 8088 timing evidence. Physical 8088, HP 200LX/Hornet and physical display adapters remain unvalidated. Speed and responsiveness are disclosed observations, excluded from the first-beta release decision.
