# ELKSWeb 0.2 — experimental beta

A usability and rendering update for the native ELKS browser. See the
[attributed changelog](../CHANGELOG.md) for changes and contributor feedback.
The executable is `elksweb`; install it as `/bin/elksweb`.

## Downloads and installation

- `ELKSWeb-0.2-runtime.tar.gz`: executable, welcome page, GIF logo and notices.
- `elksweb`: the same executable separately, for an existing installation.
- `ELKSWeb-0.2-source.tar.gz`: corresponding browser and ELKS/libc sources.
- Matching `.sha256` sidecars and `SHA256SUMS` identify the exact downloads.

Follow [INSTALL.md](INSTALL.md). Assets now belong in `/lib/elksweb`; the old
`/root/welcome.htm` fallback supports existing ELKS image installations. The
runtime package does not install an operating system. No new HD image is part
of this release. Keep corresponding source and notices with redistribution.

## Evidence and its limits

The release process checks host browser/font/platform regressions, GIF decoding
against reference pixels and malformed inputs, native 8086 instructions and
memory limits, and identical output from the audited and external builders.
Native QEMU checks use a 486 CPU and cover CGA/EGA/VGA in normal and inverted
modes, the updated default welcome page, a fixed FrogFind GIF fixture and exit
back to a usable console. QEMU results do not certify physical adapters.

Alex (@l00nix) tested development candidates on an Amstrad PPC 512 with PicoMEM 2,
the internal LCD and serial mice. He reported improved mouse movement, readable
fonts and much better link-click behavior. That machine reported 735 KiB RAM;
this is not a minimum-memory claim for an unexpanded 512 KiB PPC. The integrated
GIF candidate was transferred and its identity verified, but no controlled PPC
GIF timing was recorded. The newly versioned release executable has a different
checksum and has not received a separate physical-hardware retest.

HP 200LX results and the community's Compaq Portable Plus report are historical
0.1 evidence. HP support remains a target; a new 0.2 HP test is still needed.
The 86Box cold-boot exit anomaly remains unresolved. Some slow parsing/loading
and hardware-dependent flicker may remain. HTTPedia DNS/site availability was
not established in the latest development checks. Testers are welcome to report
machine, ELKS version, `elksweb --version`, executable checksum, URL and steps.

## Build and architecture

The 8086/8088 target, native ELKS networking and direct CGA/EGA/VGA abstraction
remain. There is no Nano-X dependency or HP-specific default. The lightweight
`toolchain/build-external.sh` builds with a prepared ELKS toolchain; the separate
`build-app.sh` retains ISA and memory auditing. Generated font and cursor data
are checked in, so external builds do not require Python or font tooling.

Large pages can still exhaust fixed layout/near-memory limits. HTTP only; no
TLS, CSS or JavaScript. GIFs show the first frame in monochrome. JPEG/PNG sizes
inform layout but their pixels are not decoded. No broad GIF speedup factor is
claimed; the optimization removes redundant work for qualifying images.
