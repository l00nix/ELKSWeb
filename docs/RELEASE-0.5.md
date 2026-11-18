# ELKSWeb 0.5

Released 2026-11-18. This freezes the 0.5dev2 implementation as 0.5, retaining
its performance improvements, the colour contribution and the HP/PPC fixes.
The executable remains `elksweb`.

## What changed since 0.4

- Native Tandy/PCjr 320×200 16-colour display, colour GIF decoding, basic HTML
  text/background/link colours, light/dark themes, narrower layout and keyboard
  handling, contributed by [@astrobleem](https://github.com/astrobleem) in
  [issue #2](https://github.com/l00nix/ELKSWeb/issues/2). His original commits,
  colour welcome page, logo and palette chart are retained and credited.
- Bounded colour-image storage and lower-resolution retries when allocation
  fails. These retries do not apply to monochrome images.
- Faster monochrome text and GIF drawing with packed framebuffer rows; lower
  GIF decoding overhead using row staging; faster screen clears and fills.
- Preserve the HP cooked-key option, PPC/HP serial mouse, local `/dev/tty1`
  selection/input, display-selector editing, inversion, console restoration and
  image-memory diagnostics. Thanks to [@ghaerr](https://github.com/ghaerr) for
  the console and usability feedback incorporated in the earlier releases.
- Medium-model native executable with near/far instruction and memory audits.
- Both welcome pages now identify 0.5. The README includes astrobleem’s
  0.5dev2 colour test photographs with his permission.

Controlled physical PPC tests measured first-frame startup at **6.21 → 4.97
seconds**. Earlier GIF/text tests measured complete welcome loading at
**60.44 → 46.59 seconds**, a FrogFind snapshot with its GIF at **25.81 → 22.08
seconds**, and the 68k news snapshot at **29.69 → 28.76 seconds**. These are
instrumented development-build measurements with fixed local/LAN content,
not new timings of final 0.5 or live Internet sites. Page measurements precede
the further screen-fill optimization. See [PERFORMANCE-0.5.md](PERFORMANCE-0.5.md).

## Install

Use `ELKSWeb-0.5-runtime.tar.gz` for the executable, both welcome pages,
GIF assets and notices. Verify its checksum before transfer and follow
[INSTALL.md](INSTALL.md). The corresponding-source archive includes browser
and ELKS/libc sources and notices for redistribution.

On EPT configured for `http://ept.8088retro.com`, use the general catalogue:

```sh
ept install elksweb
elksweb --version
```

Expect `0.5`. The nightly `-n` flag is no longer required. EPT replaces
`/bin/elksweb` and `/lib/elksweb/` assets; preserve a previous installation
if you want a comparison copy. No kernel, bootloader or startup script changes
are installed. Retain working mouse exports, `-invert` if preferred, and
`ELKSWEB_COOKED_KEYS=1` on HP setups which require it.

## Requirements and scope

The ELKS kernel must enable `CONFIG_EXEC_MMODEL`. CGA/EGA/VGA remain
monochrome. Tandy/PCjr colour requires reserved video memory reported by
`MEM_GETTANDY`/`MEM_GETPCJR`:

- [Tandy kernel documentation](https://github.com/astrobleem/elks/blob/tandy-video-v0.9.2/Documentation/tandy-video.txt):
  branch `tandy-video-v0.9.2`, published revision
  `29b5867c1a18bf1f8e6fbcb552118cfd0c7577d6`, with `tandyvideo=1` in `/bootopts`.
- [PCjr kernel/loader documentation](https://github.com/astrobleem/elks/blob/pcjr-video-v0.9.2/Documentation/pcjr-video.txt):
  branch `pcjr-video-v0.9.2`, published revision
  `af39803997e40330dac2aa8df6f2acad58194503`. Build and install the matching
  kernel and MINIX bootloader together; replacing only the kernel is insufficient.

These system components are separate from the browser package. Published
revisions were supplied by the contributor; they are not a claim that every
historical emulator run used those exact commits.

Use 640 KB or more as a starting point; free memory, services, fragmentation
and page content still matter. No EMS/XMS image storage, broader automatic
memory budgeting or new 512 KB online-browsing support is included. HTTP only;
no native TLS, CSS or JavaScript engine. GIF first frames are decoded;
JPEG/PNG dimensions are used for placeholders.

## Validation

The attached `VALIDATION.json` identifies the exact final source and executable,
independent build comparison, native instruction/memory audits, host tests and
QEMU graphics checks. Packages include checksums and corresponding source.
The 0.5 promotion changes version text, documentation and packaging; it does
not alter the dev2 rendering or HP/PPC input paths.

Physical PPC performance results and historical HP/PPC compatibility tests
are documented separately. Astrobleem reported a working 0.5dev2 colour run
and supplied the README photos. The original contribution also includes
86Box Tandy and DOSBox-X PCjr emulator results. These observations are not a
complete hardware qualification of the newly version-stamped 0.5 binary,
every Tandy/PCjr configuration, or stock 512 KB systems. Remaining test areas
include physical PCjr coverage, Tandy keyboard variants and low-memory limits.
