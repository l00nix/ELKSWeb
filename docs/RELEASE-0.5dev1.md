# ELKSWeb 0.5dev1 — development test candidate

Packaged 2026-11-17 from the 0.4 baseline. This is an experimental prerelease
for testing, not the finished 0.5 release. Keep 0.4 available for comparison.

## Included

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
is no new 512 KB online-browsing support or measured speed improvement.
Use 640 KB or more as a starting point for testing; available memory, services,
fragmentation and page contents still matter. HTTP only; no native TLS,
JavaScript or CSS engine. GIF first frames are supported; JPEG/PNG pixel decoding
is not included.

## Install and test

Download `ELKSWeb-0.5dev1-runtime.tar.gz` for the executable, both welcome pages,
GIF assets and notices. The standalone executable alone does not update those
assets. Verify the checksums on a modern computer before transfer. Follow
[INSTALL.md](INSTALL.md); keep the matching corresponding-source archive when
redistributing binaries.

For an isolated PPC/HP test, transfer the executable to `/root/web05/elksweb`
and all files from the package's `lib/elksweb/` to `/root/web05/`. Then run from
the device's own graphics console:

```
chmod 755 /root/web05/elksweb
/root/web05/elksweb --version
/root/web05/elksweb -video cga /root/web05/welcome.htm
```

Expect version `0.5dev1`. On the HP retain `export ELKSWEB_COOKED_KEYS=1` where
required; retain the working serial-mouse exports and add `-invert` if preferred.
This isolated launch leaves the existing startup script and 0.4 files intact.
Start networking with your existing configuration only when testing HTTP.

Check welcome text/GIF, launch and Escape restoration, URL editing, navigation,
scrolling, forms, mouse clicks, inversion, and FrogFind/68k news mirror/HTTPedia.
Compare memory and responsiveness with 0.4 under the same RAM and service settings.
Treat 512 KB runs as boundary tests, not promised support.

## Validation scope

The integration passed 337 browser, 25 platform, 7 colour-GIF and 11 ISA-audit
regressions, keyboard/mouse C checks, and GIF/dimension differential tests.
Its two native builders agreed. QEMU monochrome CGA/EGA/VGA checks covered
welcome/GIF, selector editing/cancellation, redirected and detached console
launch, cooked keys, inversion and exit restoration.

Those integration records are in `docs/QA-integration-0.5.json`. The accompanying
`VALIDATION.json` records the exact packaged executable, rebuild and candidate
checks separately. QEMU uses a 486: it does not certify physical 8088 timing.
Physical HP/PPC tests of this candidate and Tandy/PCjr colour integration tests
remain pending. Host colour raster tests do not exercise the native video code.
