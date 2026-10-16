# ELKSWeb 0.1 — private beta

ELKSWeb is an original C graphical browser for ELKS Linux, built with the native ELKS IA16 toolchain for 8088-compatible processors. Inspired by the ELKS graphical-browser discussion and MicroWeb, it uses native ELKS networking and direct graphics without Microwindows or a C++ runtime. This package remains private for owner review.

## Included in 0.1

- CGA 640×200, EGA 640×350 and VGA 640×480 monochrome display selection, limited to detected support.
- A stable application frame, separate address/status updates and incremental vertical scrolling. Existing pixels move; only the newly exposed strip is drawn again. Large jumps, horizontal scrolling and other page changes can still require full viewport painting.
- HTTP and local HTML/text pages, relative links, redirects, history, forms, tables, GIF images and binary downloads.
- Version identification through `--version` and the display selector.
- A 2.88 MB QEMU image with a welcome page and offline FrogFind samples, plus the native executable, corresponding browser/ELKS source archives, notices and checksums.

## Installation and testing

Read the package's `README.txt`, then verify it with `sha256sum -c SHA256SUMS`.

For QEMU, install `qemu-system-i386` and mtools, then run `bash toolchain/run-qemu.sh` from the extracted directory. Select a display mode and follow the welcome page's offline FrogFind link. Alternatively, run `bash toolchain/run-qemu.sh http://68k.news/`. The launcher boots a disposable image copy with a 486 CPU for ELKS integration testing; it does not emulate an 8088. Downloads in that temporary session disappear on exit.

For an existing ELKS installation, install `build/elksweb` as `/bin/elksweb`, `share/welcome.htm` as `/root/welcome.htm`, and the offline fixture files under `/root/frog`. A graphics-capable console and writable `/tmp` are required. HTTP browsing additionally requires configured native ELKS networking.

On the project's HP 200LX ELKS 3.8 beta 1 setup, use translated keyboard input:

```sh
export ELKSWEB_COOKED_KEYS=1
elksweb -video cga /root/welcome.htm
```

The generic floppy image is intended for emulator testing; use the executable on the existing HP installation. The owner confirmed the earlier build006 runs on the HP and preserves the application frame. Physical testing of **0.1's new scrolling path remains pending**.

## Validation and identity

Final validation is recorded in `QA-0.1.json` in the browser source documentation. The native application was rebuilt against the prepared toolchain from clean-build001; this was not another fresh compiler/system bootstrap. The QEMU image derives from clean-build005 with the new executable, welcome page and attributed offline fixtures installed.

- Executable SHA256: `5c652079e7cc27884091c9e3b1730fea5d37fa3cbeb690535fed94af16dcfce2`.
- Image SHA256: `7c51c3df6becacbe2ddbe7eb7d446d67e0d57cff89d1be14531e998d844191f5`.
- ELKS source: `89d09706f17c123f9e0f5ef7cba2eb6745e8478c`.
- The package's `PACKAGE.json` pins the complete browser source revision; its source archive contains all files used to build the browser.
- Native build: no warnings; static 8086 audit passes for 25,970 instructions.
- Memory: 64,816 bytes code, 12,176 initialized data, 38,448 BSS. Including default heap/stack, near allocation is 58,816 bytes before arguments/environment, leaving 6,704 bytes; code headroom is 720 bytes.
- Host tests: 288 pass; seven additional platform tests pass.
- Native scroll oracle: all 54 incremental/full-redraw comparisons match exactly across CGA/EGA/VGA. Tests separately count render writes so identical final screenshots are not mistaken for proof of incremental drawing.
- Native display selection, cancellation, unsupported-option handling and console restoration pass.
- Native history and receive cancellation: 12 checks pass.

All 39 native fixture scenarios pass their request/capture assertions. Download bytes, edited filenames, existing-file protection and recovery after save errors pass. Disk-full testing removes the incomplete file and returns to the welcome page. Live FrogFind mirror search/article/Back and 68k.news homepage/scroll/Back were visually checked. The selected news article displays an upstream extraction error, so successful article reading is not claimed. The independent reviewer inspected 59 frames and recomputed all 54 scroll comparisons without finding a visual regression. Details and evidence limits are recorded in the accompanying QA record. Earlier 8088 Windows 86Box and DOS MicroWeb comparisons remain scoped to their recorded builds. No new blind preference vote or physical 8088 timing claim is made for 0.1.

## Known limitations

GIF pixels are supported; JPEG/PNG dimensions are recognized but their pixels are not decoded. HTTP only: no native TLS, CSS or JavaScript. Document/layout and form-field limits, accent transliteration and single-line textarea editing remain as described in the main README. Displayed images retain a 200-row limit. EGA requires a color adapter with at least 128 KB video RAM.

Scrolling now avoids repeated drawing, but page loading and other operations can still be slow. Speed and responsiveness are excluded from the first-beta decision; smoothness on the HP has not yet been measured for this version. QEMU does not establish physical adapter compatibility or complete MicroWeb parity.

The offline FrogFind pages use fixed sample results with their retained license and provenance. The package uses a live 68k.news link; it does not bundle captured news articles. No MicroWeb executable, proprietary BIOS ROM or physical-disk writing tool is included.

The repository and release remain private. Public publication and a discussion announcement await owner approval.
