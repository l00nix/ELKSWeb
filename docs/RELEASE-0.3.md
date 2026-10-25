# ELKSWeb 0.3 — experimental beta

A navigation and startup update for the native ELKS browser, based on
[@ghaerr's feedback](https://github.com/ghaerr/elks/discussions/2185#discussioncomment-19170548).
See the [changelog](../CHANGELOG.md) for changes and credits.

## Changes

- Keep the requested address visible while loading; show the final redirected
  address on success and restore the old page's address on failure.
- Allow Backspace editing in the startup display selector. Enter with an empty
  choice selects CGA.
- Add a guarded fallback to a graphics-capable read/write terminal on stdin when
  `/dev/tty` is unavailable. Restore terminal flags and settings on exit.
- Update the welcome page, including the **68k news mirror** link, while retaining
  FrogFind, HTTPedia and offline keyboard help.

## Downloads and installation

- `ELKSWeb-0.3-runtime.tar.gz`: executable, welcome page, GIF logo and notices.
- `elksweb`: the same executable separately, for an existing installation.
- `ELKSWeb-0.3-source.tar.gz`: corresponding browser and ELKS/libc sources.
- Matching `.sha256` sidecars and `SHA256SUMS` identify the exact downloads.

Follow [INSTALL.md](INSTALL.md). Install `/bin/elksweb` and the support files in
`/lib/elksweb`; retain executable permissions. The `/root/welcome.htm` fallback
supports older installations. This release does not include an operating-system
image. Keep notices and matching corresponding source with redistribution.

## Validation and scope

Release checks cover host browser and platform regressions, native 8086
instruction and memory limits, and matching output from the audited developer
builder and lightweight external builder. QEMU checks use a 486 CPU and cover
the newly versioned executable, welcome/GIF rendering, scrolling and console
restoration in CGA/EGA/VGA normal and inverted modes. Emulator checks are not
physical-adapter certification.

l00nix completed a real-hardware checklist for **0.3-dev1** on the Amstrad PPC 512
with PicoMEM 2 and the HP 200LX DS with the HP-specific ELKS 4.0 local kernel.
There were 16 passes on the PPC and 17 on the HP: startup, pending-URL display,
display-choice editing/defaults, welcome text/GIF, FrogFind, news, HTTPedia,
scrolling, keyboard links, exit restoration, mouse movement/clicking and inverted
display. HP cooked-key input also passed; that test was N/A on the PPC.
Address entry remains partly open on both machines, although bare hostnames
were confirmed to load. No controlled timings were entered.

The tested candidate's SHA256 is
`5a6ed7e4662a0caac05fe1d005fd8dc1f5db03e106076098d0fb70e33a488856`.
The final 0.3 build changes the version string and ships revised help; its
checksum is separate, and it has not received a separate hardware retest.
Detailed test sheets, logs and installation records remain local.

## Remaining limits

The intermittent controlling-console issue reported upstream remains under
investigation. The guarded fallback passes a related detached-session QEMU
reproduction; successful hardware startup does not prove that this fallback was
used or that the upstream issue is resolved. The earlier 86Box cold-boot exit
anomaly remains open. Large-page parsing and loading can still be slow, and
filesystem space and fixed memory limits can restrict browsing.

HTTP only: no TLS, CSS or JavaScript. GIFs display their first frame in monochrome;
JPEG/PNG dimensions inform layout but pixels are not decoded. Wider hardware,
PS/2, forms and download coverage remain development priorities. No new speed
multiplier or minimum-RAM claim is made.

## Build and architecture

The 8086/8088 instruction target, native ELKS networking and direct CGA/EGA/VGA
abstraction remain. No Nano-X dependency or HP-specific integration defaults
are introduced. `toolchain/build-external.sh` remains the lightweight builder;
`toolchain/build-app.sh` separately retains ISA and memory auditing.
