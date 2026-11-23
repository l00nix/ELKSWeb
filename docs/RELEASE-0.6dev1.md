# ELKSWeb 0.6dev1 development candidate

Built for comparison with the retained 0.5 release. This candidate combines
astrobleem's VGA/scrolling PR #3 and independent GIF workspace improvement.
It does not integrate EMS or Nano-X and does not change the ELKS kernel.

## Changes and provenance

- VGA 640x480 now renders sixteen RGBI colours, including masked GIF rows and
  cursor background restoration. `-video vga-mono` retains monochrome output.
- VGA scrolling copies all planes with byte-string latch copies; CGA/EGA
  scrolling uses 8086 byte-string copies while preserving bank and overlap order.
- Colour GIF decoding splits the LZW workspace into two 8 KB allocations and
  separates palette/map storage. The column map is omitted at natural width.
  This reduces contiguous-block requirements; it does not add memory or promise
  faster decoding. The monochrome decoder keeps its existing 16 KB allocation.
- Wider colour row buffers support VGA's 640-column geometry. Existing Tandy/PCjr
  display reservations and input remain in place.

Contributed by [astrobleem (Chad Doebelin)](https://github.com/astrobleem):
[PR #3](https://github.com/l00nix/ELKSWeb/pull/3), commits
`b79cb97957d69b19874b0604acd8db043a382bdd`,
`c5454d5d6238495ab32abdbc782df54d61ef304c`,
`ba296ddca8dd2e6f815214de91d24ce8d51bdb28`, and standalone
[workspace commit 663cea0](https://github.com/astrobleem/ELKSWeb/commit/663cea00ca788007dd9de3ababcea35d9a46611c).
Their authorship is retained. Base main: `d6befa51ef8cc13b9bb713a81a9155219e4e2ca3`.

## Preservation and comparison

Keep 0.5 and its welcome assets/launcher intact. Use the separate `/root/web06`
layout in [INSTALL.md](INSTALL.md). The executable is still named `elksweb`.
The HP cooked-key option, serial-mouse handling, local `/dev/tty1` console,
inversion, diagnostics and the 0.5 startup/GIF improvements remain present.
CGA and EGA remain monochrome; an external LCD does not turn CGA into VGA.

## Validation and remaining tests

The packaged `VALIDATION.json` identifies the exact source, executable, native
ISA/memory audit, host checks and emulator checks. Contributor 86Box timings
are evidence for that contribution, not timings of this combined candidate.
Physical HP/PPC and VGA candidate qualification remains open.

Compare 0.5 and 0.6dev1 with the same RAM, network services, display and input:

- Welcome-page text and GIF, normal and inverted display; complete load time.
- `http://frogfind.8088retro.com/` including its GIF, link/search navigation.
- `http://68knews.8088retro.com/` and `http://httpedia.com/` loading and navigation.
- Line/page scrolling both ways, top/bottom boundaries, no trails or displaced bars.
- Mouse motion/clicks and cursor restoration over images and while scrolling.
- HP cooked keys, URL editing, mode-selector editing and Escape back to the shell.
- VGA colour, transparency and `vga-mono` fallback on a suitable VGA adapter.

Use frozen pages for timing comparisons; live Internet variability can obscure
browser differences. At 512 KB, record launch/GIF allocation failures rather
than assuming support. Colour decoding, networking and browser code still use
conventional RAM. No new low-memory compatibility claim is made.
