# Developer-preview status — 16 October 2026

The latest Windows 86Box test used an unchanged original C browser executable, compiled with the native ELKS toolchain. The emulated machine was an Intel 8088 at 4.77 MHz with 640 KB RAM and CGA.

| Check | Result |
| --- | --- |
| ELKS boot and local welcome | Passed |
| Live 68k.news rendering | Passed first viewport and site footer |
| Page Down / End | Worked, with substantial input delay |
| Clean browser exit | Passed in the first run |
| Practical 8088 performance | Failed: about eight minutes to first live-page frame, additional minutes before queued input took effect |
| Back from HTTP to prior local file | Failed: local path rebased onto HTTP origin, producing 404 |
| FrogFind | Attempt ended “Host name not found”; upstream availability not established |
| Physical HP 200LX / Hornet | Not tested |
| Same-machine DOS MicroWeb timing | Not tested |

Times are approximate observations, not controlled benchmarks. The clean screenshots are direct 640×200 emulator captures without image edits. Full-page reachability is not byte-for-byte response equality. No fresh blind comparison was performed for this Windows run.

## Candidate identity

- Browser SHA256: `1089c3198f235ede1adb6ae6e5cdb19be7b97033001221946a48268484f3b224`.
- Original boot image SHA256: `2dced9f6a546fb73d0829dcdeca191cc39c514e7f4093111b8e74d2f6c0d375d`.
- 86Box image after bootopts-only adaptation, before guest writes: `f58fdb29fb13b91c09996073608ecefe3373caf901bfd18992d7e4cfb257ddd0`.
- Code: 63,216 bytes; data: 11,744 bytes; BSS: 37,920 bytes. These are executable sections, not peak runtime RAM consumption.

## Before a public beta

Fix local-file history identity; profile and reduce parsing/rendering costs on the 8088; make progress and cancellation usable; repeat navigation and resource-failure QA; validate a clean build/install workflow; publish a clearly scoped compatibility matrix. Additional resolutions require new backend work. A CGA-only beta is possible once its documented behavior is usable.

The repository is being prepared privately. This document does not announce a public release.

## Source-package verification

The packaged production sources match all 23 files in the tested candidate manifest. See [source and screenshot checksums](candidate-provenance.json). On 16 October 2026, standalone-package host verification passed 224 core tests, five framebuffer tests and 13 font tests. The image scripts passed 24 GIF cases plus truncations/1,000 mutations, and 16 dimension fixtures plus prefixes/5,000 random inputs. These are host checks, not a new native build or emulator run.
