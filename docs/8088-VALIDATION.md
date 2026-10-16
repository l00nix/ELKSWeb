# 8088 validation scope

The browser is compiled with the native ELKS IA16 GCC flags `-march=i8086 -mtune=i8086`, and the retained ELF is checked for instructions outside that target. Static inspection complements emulator execution; neither establishes physical hardware compatibility by itself.

The retained Windows 86Box configurations select `machine=ibmxt86`, `cpu_family=8088`, `cpu_speed=4772728`, `cpu_use_dynarec=0` and `mem_size=640`. The official [86Box 4.2.1 CPU table](https://github.com/86Box/86Box/blob/v4.2.1/src/cpu/cpu_table.c) maps that family/speed to the Intel 8088 entry. CGA, EGA and VGA are tested in separate configurations. ROMs are obtained separately and are not distributed here.

## ELKS CPU-label discrepancy

Some guest boot captures show CPU index 2 (V20), despite the selected 8088. The pinned ELKS [CPU probe](https://github.com/ghaerr/elks/blob/89d09706f17c123f9e0f5ef7cba2eb6745e8478c/elks/arch/i86/boot/cputype.S) explicitly describes itself as obsolete and inaccurate. Its interrupt-enable instruction before the repeated-load test is commented out; a zero count branches toward the NEC classification. The [disk setup path](https://github.com/ghaerr/elks/blob/89d09706f17c123f9e0f5ef7cba2eb6745e8478c/elks/arch/i86/boot/setup.S) disables interrupts before calling this probe.

These source observations provide a plausible explanation for a false V20 label. They are not a guest execution trace proving the interrupt flag's value during detection. We retain the discrepancy and identify the emulator's configured CPU explicitly rather than treating the guest label as independent certification. The browser does not select a V20 instruction target from this boot message.

QEMU uses a 486 CPU for general ELKS integration testing. It supplies no 8088 timing evidence. The owner confirms exact ELKSWeb 0.1 runs on the standard HP 200LX and the owner-identified DS HP 200LX, with smoother scrolling reported on the standard HP. These are owner observations, not independently captured graphics tests or controlled timings. Physical Intel 8088 and broader physical display-adapter compatibility remain unvalidated. Speed and responsiveness are disclosed observations, excluded from the first-beta release decision.

## Exact version 0.1 evidence

The 77,024-byte executable has SHA256 `5c652079e7cc27884091c9e3b1730fea5d37fa3cbeb690535fed94af16dcfce2` and MD5 `9618c7abec60bc79d5ce539b2516b04c`. Installation/version checks are retained locally in the parent project's `output/elksweb-hp01/` and `output/elksweb-ds01/`; later owner reports confirm use after those records were written. The DS system reported `ELKS0.9.2-dev hp200lx-3.8-beta1`. Its designation alone does not establish a clock frequency.

The final Windows 86Box 8088 run of this exact 0.1 executable is pending. Earlier build005 captures and its approximately eight-minute first-news-viewport observation remain historical evidence for build005, not a 0.1 timing result. The new help page/logo change runtime assets only; they do not change this executable identity. Their refreshed image SHA256 is `3c865e5edb81f67c50b88554ee0d040f07c474423e1a200313925db37c79711d`; default-page QA passes all three QEMU display modes, independently of the pending exact-version 8088 check.

## Exact 0.1 follow-up — incomplete

The refreshed help/logo was rendered by the exact 0.1 executable in Windows 86Box 4.2.1 build 6130 configured as an IBM XT (1986), Intel 8088 at 4.772728 MHz, 640 KB and CGA. Startup mode selection, welcome HTML/GIF and PageDown were observed. The staged 86Box image hash is `3751924dd62a3cd2f77c7f44e10136be61e46a85f17cde8e69ff874d48a1a774`; only boot/network settings and QA launchers differ from the QEMU image.

The first exit printed `ELKSWeb closed.` and then a Multi-Floppy BIOS initialization banner with INT40; a usable login did not return. This remains an unresolved test anomaly. A cold retry with the local FrogFind fixture, without scrolling or keyboard screenshot shortcuts, rendered its GIF and exited to a normal login; root login and a browser relaunch succeeded. The repeat welcome/scroll/exit test was interrupted by the host Mac locking. Live-site checks in this exact 86Box run remain pending. The initial failure must not be silently replaced by the successful narrower retry.

A separate 640 KB QEMU run completed welcome/scroll/invert/exit, root login and a typed shell command. It did not reproduce the anomaly, but its 486 CPU/BIOS differ from 86Box. No code defect or emulator cause has yet been established. Raw captures and result records are retained under `qa/86box-release01/` and `qa/welcome-01/qemu640K/` in the private working copy.
