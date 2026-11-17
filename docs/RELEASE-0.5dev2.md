# ELKSWeb 0.5dev2 — development test candidate

Packaged 2026-11-17 as a performance follow-up to 0.5dev1. This is an experimental prerelease
for testing, not the finished 0.5 release. Keep 0.4 available for comparison.

## New in dev2

- Faster monochrome glyph and GIF drawing using packed framebuffer rows.
- Lower monochrome GIF decoding overhead by staging a single row before writing to far memory; output pixels, transparency, interlacing and colour decoding remain unchanged.
- Faster screen clears and solid fills using 8086 string instructions.

On the physical PPC, three alternating runs per build measured first-frame
startup at **6.21 → 4.97 seconds (20% faster)**. Earlier tests of the GIF/text
changes measured the complete welcome page at **60.44 → 46.59 seconds** and a
FrogFind snapshot including its GIF at **25.81 → 22.08 seconds**. The latter
measurements precede the additional fill optimization. They use fixed local/LAN
content and instrumented candidates, not a fresh timing claim for the versioned
release or live Internet. The PPC main-memory pool was 574 KB after reservations;
this does not qualify stock 512 KB systems. About four seconds before main remains
unresolved. See [PERFORMANCE-0.5.md](PERFORMANCE-0.5.md) for methods and limits.

The native near-memory budget remains 61,392 / 65,520 bytes before argv/env.
Compared with original dev1, GIF staging adds 16 bytes of fixed data and 168 bytes
to the decoder's estimated individual stack frame, within the existing 4 KB
stack allocation. No retained image cache or enlarged heap is added.

## Retained from dev1

Thanks to [@astrobleem](https://github.com/astrobleem) for the
[contribution in issue #2](https://github.com/l00nix/ELKSWeb/issues/2).
His four original commits through `6dbd3b29639efeae621255f60b344a18be5f9a85`
remain in the branch history.

- Direct Tandy/PCjr 320x200 16-colour rendering without Nano-X.
- Colour GIF decoding/dithering, basic HTML text/background/link colours,
  light/dark themes, narrower layout and Tandy/PCjr keyboard handling.
- Bounded colour-image storage and smaller-resolution retries on allocation
  failure. Monochrome images do not yet use those retries.
- Preserved HP/PPC local-console handling, selector Backspace, HP cooked keys,
  serial-mouse support, inversion, console restoration and image-memory errors.
- Medium-model native build, with audits of both near and far code sections.

## Requirements and limits

The executable remains `elksweb`, targeting 8086-compatible instructions. The
ELKS kernel must enable `CONFIG_EXEC_MMODEL`. This model allows more code; it
does not add physical RAM or remove the near-data limit.

CGA/EGA/VGA remain monochrome. Tandy/PCjr colour mode requires matching kernel
and loader support which reserves video memory and reports it through
`MEM_GETTANDY`/`MEM_GETPCJR`. We still need the contributor's exact matching
revisions and reproducible colour emulator configuration. No kernel, bootloader
or system-image change is included in these packages.

EMS/XMS image storage is not included. Astrobleem's EMS work is separate and
unfinished. Broader automatic memory budgeting is also not implemented. There
is no new 512 KB online-browsing support.
Use 640 KB or more as a starting point for testing; available memory, services,
fragmentation and page contents still matter. HTTP only; no native TLS,
JavaScript or CSS engine. GIF first frames are supported; JPEG/PNG pixel decoding
is not included.

## Install and test

Download `ELKSWeb-0.5dev2-runtime.tar.gz` for the executable, both welcome pages,
GIF assets and notices. The standalone executable alone does not update those
assets. Verify the checksums on a modern computer before transfer. Follow
[INSTALL.md](INSTALL.md); keep the matching corresponding-source archive when
redistributing binaries.

For an isolated PPC/HP test, transfer the executable to `/root/web05d2/elksweb`
and all files from the package's `lib/elksweb/` to `/root/web05d2/`. Then run from
the device's own graphics console:

```
chmod 755 /root/web05d2/elksweb
/root/web05d2/elksweb --version
/root/web05d2/elksweb -video cga /root/web05d2/welcome.htm
```

Expect version `0.5dev2`. On the HP retain `export ELKSWEB_COOKED_KEYS=1` where
required; retain the working serial-mouse exports and add `-invert` if preferred.
This isolated launch leaves the existing startup script and 0.4 files intact.
Start networking with your existing configuration only when testing HTTP.

Check welcome text/GIF, launch and Escape restoration, URL editing, navigation,
scrolling, forms, mouse clicks, inversion, and FrogFind/68k news mirror/HTTPedia.
Compare memory and responsiveness with 0.4 under the same RAM and service settings.
Treat 512 KB runs as boundary tests, not promised support.

## Validation scope

The performance changes passed 337 browser tests, 26 platform tests, 6 font
tests, 7 colour-GIF tests, monochrome GIF/dimension differential tests and
parser sanitizers. Eight native QEMU frames matched published dev1 exactly
before the version text changed. The final package is rebuilt from committed
source with two build paths, instruction/memory audits and native QEMU checks;
the attached `VALIDATION.json` records the exact binary and checks separately.

QEMU uses a 486 and does not certify physical 8088 timing. The performance
candidate ran on the physical PPC; full user hardware testing of the final
versioned binary, HP retesting and matched Tandy/PCjr colour integration tests
remain open. Host colour raster tests do not exercise native video hardware.
The HP/PPC input, console and mouse code and the colour path are retained.
