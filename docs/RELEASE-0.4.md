# ELKSWeb 0.4 — experimental beta

Released 2026-11-17. This freezes the 0.35dev browser candidate; it does not
include the proposed Tandy/PCjr colour contribution or change the ELKS kernel.

## Changes since 0.3

- Open `/dev/tty1` directly for the graphics keyboard and startup display
  selector, following [@ghaerr's console guidance](https://github.com/ghaerr/elks/discussions/2185#discussioncomment-19257446).
  Remove the old `/dev/tty` and borrowed-stdin fallback. Restore console settings
  on exit, cancellation and startup failure.
- Display inline image allocation failures in the status bar, including GIF
  workspace failures. Clear the error when loading a new page. This makes
  [low-memory failures](https://github.com/l00nix/ELKSWeb/issues/1) easier to diagnose;
  it does not lower decoder memory requirements.
- Preserve HP `ELKSWEB_COOKED_KEYS=1`, serial-mouse settings, inversion, fonts,
  navigation and monochrome CGA/EGA/VGA rendering.
- Update the executable and welcome page to 0.4. The welcome links remain
  FrogFind, 68k news mirror and HTTPedia.

## Installation and architecture

The executable remains `elksweb`. Publish the standalone executable and separate
runtime and corresponding-source archives with checksums. Runtime assets belong
under `/lib/elksweb`; `/root/welcome.htm` remains a compatibility fallback.
See [installation instructions](INSTALL.md).

The 8086/8088 instruction target and small memory model are retained. Native ELKS
networking and direct graphics remain; no Nano-X dependency is introduced. Both
build workflows use the prepared ELKS/libc base at
`e1469b64c5809c44d5c822eaeebd0e97d5996289`, supplied in the corresponding-source
archive. This release does not install HP-specific NIC, keyboard or boot fixes.

## Validation scope

Release checks cover host browser/platform regressions, GIF/dimension tests,
native instruction and memory auditing, agreement between the audited and
lightweight builders, and QEMU display selection, redirected console input,
HP-style cooked keys, welcome/GIF rendering and console restoration. The release
asset `VALIDATION.json` records the exact executable hash and results.

The owner tested the 0.35dev candidate on the PPC and reported it working on the
HP 200LX after separate system-image repairs. Candidate photographs show the PPC
welcome page and GIF. These reports are not a complete checklist or an exact-0.4
hardware retest. Earlier 0.3 hardware checks retain their original scope.
QEMU uses a 486 CPU and does not certify physical 8088 timing or peripherals.

## Remaining limits

512 KB online browsing is not supported by the observed tests: even with only
`ktcp`, both 0.3 and 0.35dev failed to start on the reduced-memory PPC setup.
Use 640 KB or more as the practical starting point for testing; available RAM
also depends on the kernel, services and fragmentation. Offline `exec` launch
can free the waiting shell's memory but is not a general memory guarantee.

The intermittent upstream console failure and historical 86Box cold-boot exit
anomaly remain open. There is no new GIF speed claim. HTTP only; no native TLS,
CSS or JavaScript. GIF first frames render in monochrome; JPEG/PNG pixels are
not decoded. Tandy/PCjr colour integration is planned separately for 0.5dev.
