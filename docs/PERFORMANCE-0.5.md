# Monochrome loading performance work

This work starts from 0.5dev1 and retains its Tandy/PCjr colour support and the
HP/PPC input, console, mouse and inversion fixes. It is an unreleased performance
candidate; the version string is still 0.5dev1. Do not replace a published
release asset with this executable.

## Changes

- A clipped packed monochrome row writer updates framebuffer bytes instead of
  making a platform call and a far-memory read/modify/write for each pixel.
  Natural-width GIF rows and monochrome glyph rows use it. It preserves masking,
  inversion, unaligned edges, the viewport boundary and CGA scanline banking.
- Monochrome GIF decoding stages one row in near memory before writing its bytes
  to the decoded far-memory bitmap. The Bayer thresholds and output pixels are
  unchanged, including partial frames and CGA pixel aspect. Colour decoding
  keeps its existing packed-nibble path and bounded allocation retries.
- Scaled monochrome image rendering retains the existing sampling/coverage
  algorithm. The decoder improvement applies independently of drawing scale.

There is no larger heap or retained image cache. The candidate adds 16 bytes of
fixed data and 168 bytes to the decoder's estimated individual stack frame
(112 to 280 bytes). The existing 4 KB stack allocation is unchanged. The native
near-memory audit is 61,392 / 65,520 bytes before arguments/environment.

## Validation and limits

337 browser tests, 26 platform tests (including packed-row byte comparisons),
6 font tests, 7 colour-GIF tests, the monochrome GIF differential suite and
ASan/UBSan parser fuzzing pass. Monochrome GIF cases include full/partial frames,
transparency, interlacing, both pixel aspects, 640x480, truncation and mutations.
The minimal and audited native builders produce identical executables; the
8086 ISA audit passes.

Eight native QEMU browser frames match the published 0.5dev1 QA frames exactly:
CGA/EGA/VGA welcome, inverted welcome, direct GIF, cooked-key startup, detached
launch and redirected startup. Selector editing/cancellation and exit back to a
working shell also pass. These are QEMU 486 checks, not new physical HP or
Tandy/PCjr certification. Keyboard, console, mouse and network initialization
code is unchanged.

The repeatable loading workloads are listed in [tests/README.md](../tests/README.md#performance-checks-on-hpppc).
FrogFind includes the frog GIF, not just the HTML. Frozen LAN fixtures and live
Internet results must be reported separately. Pixel equality and successful
navigation are separate requirements from timing.

## Physical PPC results (2026-11-17)

Three alternating fresh-process runs per build, with identical local welcome
assets and frozen news/FrogFind content served over LAN HTTP:

| Completed workload | 0.5dev1 median | Candidate median | Reduction |
| --- | ---: | ---: | ---: |
| Welcome including logo GIF | 60.44 s | 46.59 s | 22.9% |
| 68k news mirror snapshot | 29.69 s | 28.76 s | 3.1% |
| FrogFind snapshot including frog GIF | 25.81 s | 22.08 s | 14.5% |

The welcome GIF decode changed from 24.69 to 21.33 seconds, and its final draw
from 11.12 to 1.16 seconds. News parsing is essentially unchanged; its gain is
in drawing. First-frame latency is also unchanged (6.14 vs 6.15 seconds): both
builds take about four seconds before main. These are full-page improvements,
not a claim of faster executable loading.

A separate diagnostic 0.4 run placed the extra 0.5dev1 time in executable/runtime
startup, decoding and drawing. The larger medium-model executable and colour
branches are plausible contributors; their individual costs were not isolated.
The candidate retains both rather than weakening device support.

This PPC configuration has a 574 KB kernel main-memory pool after reservations;
it is not a stock 512 KB qualification. All 21 page loads completed without
truncation or image errors. These timings are frozen-content LAN comparisons,
not fresh live-Internet measurements. Raw per-run timing records are retained in
the local `work/ppc-opt-20261117` evidence directory.

## First-frame follow-up (2026-11-17)

The subsequent `perf/0.5-startup` candidate keeps the loading changes above and
replaces monochrome framebuffer fill loops with 8086 `REP STOSW` plus an odd-byte
tail, using the same approach as the colour backend. Clears and the full-byte
interior of horizontal lines use it; clipped edge pixels retain their masks.
It preserves ES, handles CGA banking through the existing scanline offsets, and
does not change keyboard, console, mouse, colour or network initialization.

Three alternating fresh-process runs per build on the same physical PPC gave:

| Phase | Previous performance candidate | With bulk fills |
| --- | ---: | ---: |
| Before main | 4.00 s | 4.00 s |
| Platform initialization, including clear | 0.54 s | 0.24 s |
| Initial browser chrome draw | 1.68 s | 0.76 s |
| Launch to first frame | 6.21 s | 4.97 s |

These are medians of individual phases; their sum need not equal the median of
whole launches. First-frame time fell by 1.24 seconds (20.0%). The baseline is
the preceding GIF/text performance candidate, whose first-frame time was
previously measured as essentially unchanged from published 0.5dev1.

The diagnostic copies timestamp entry to main, completion of platform setup,
and completion of the first browser draw, then exit before loading a document.
A native runner timestamps immediately before flushing its timestamp and exec;
therefore the pre-main figure includes that small flush overhead and C runtime,
not just the kernel loader. No Telnet or FTP connections were made during the
reported batch. The range was 6.19–6.24 seconds before and 4.95–5.00 after.
A preliminary batch with collection interference is excluded. This remains the
574 KB main-pool PPC configuration, not a stock 512 KB qualification. These are
first-frame measurements, not updated full-page or live-Internet timings.

The remaining four-second pre-main delay is unresolved. The 0.5 medium-model
binary contains 824 segment relocation records, versus none in the retained
0.4 small-model binary. The inspected ELKS loader reads each record separately;
this is a plausible contributor, not a measured attribution of the whole delay.
The change does not strip relocations, remove colour support, or alter deployed
kernels. Linker relaxation produced no size reduction in an exploratory build;
LTO failed with the installed toolchain and was not adopted.

Validation: all 26 platform tests pass, including full-aperture clear checks
and independent clipped-line pixel comparisons. All eight native QEMU browser
frames remain pixel-identical to the preceding candidate (and hence its
published 0.5dev1 reference). Selector editing/cancellation, redirected/detached
startup, cooked-key GIF navigation, inversion and shell restoration pass. The
minimal and audited builds are byte-identical; the 8086 ISA audit passes.
The executable grows by 32 bytes to 97,776 bytes; data, BSS, heap and stack
budgets remain unchanged. Near-memory audit: 61,392 / 65,520 before argv/env.
Physical HP and Tandy/PCjr retesting remains open.

Raw runs, build evidence and pixel comparisons are retained locally in
`work/ppc-startup-20261117`. The ordinary executable has SHA-256
`ba6c28ee5bfb936c54ce5c200a25a50529ed4b9b5380028c8d1f572157016dbc`.
It remains an unreleased candidate with the 0.5dev1 version string.
