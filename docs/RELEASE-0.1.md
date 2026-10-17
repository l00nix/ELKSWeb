# ELKSWeb 0.1 — experimental beta

ELKSWeb is an original C graphical browser for ELKS Linux, built with the native ELKS IA16 toolchain for 8088-compatible processors. Inspired by the ELKS graphical-browser discussion and MicroWeb, it uses native ELKS networking and direct graphics without Microwindows or a C++ runtime. The scoped QA and owner hardware feedback informed this experimental public beta. The repository and release downloads are public. Runtime, corresponding-source and optional test-image packages are supplied separately. The original cold-boot 86Box exit anomaly remains unresolved; the later normal-shell welcome/scroll/exit sequence passed. This is an experimental beta, not a claim that all QA gates are closed.

## Included in 0.1

- CGA 640×200, EGA 640×350 and VGA 640×480 monochrome display selection, limited to detected support.
- A stable application frame, separate address/status updates and incremental vertical scrolling. Existing pixels move; only the newly exposed strip is drawn again. Large jumps, horizontal scrolling and other page changes can still require full viewport painting.
- HTTP and local HTML/text pages, relative links, redirects, history, forms, tables, GIF images and binary downloads.
- Version identification through `--version` and the display selector.
- A normal runtime package containing the executable, default HTML help page, original GIF logo and required notices. Corresponding source is separate; the QEMU image and offline fixtures are optional testing artifacts. Project-specific `webfrog` and `webnews` launchers are excluded from the normal package.

## Installation and testing

For a download-only installation with no compiler, follow [Install ELKSWeb from a release](INSTALL.md). It covers the runtime package, standalone executable, host checksum verification, transfer destinations, upgrades and HP 200LX startup.

Read the package's `README.txt`, then verify it with `sha256sum -c SHA256SUMS`.

For an existing ELKS installation, install the supplied executable as `/bin/elksweb`, `share/welcome.htm` as `/root/welcome.htm`, and `share/elksweb.gif` as `/root/elksweb.gif`; retain the accompanying notices. A graphics-capable console and writable `/tmp` are required. HTTP browsing additionally requires configured native ELKS networking. Launching without a URL opens the default help page. Neither offline website fixtures nor the project's `webfrog`/`webnews` launchers are needed.

For optional QEMU testing, install `qemu-system-i386` and mtools and follow the test artifact's instructions. From a source checkout with its test image prepared, run `bash toolchain/run-qemu.sh`, or `bash toolchain/run-qemu.sh http://68k.news/`. The launcher boots a disposable image copy with a 486 CPU for ELKS integration testing; it does not emulate an 8088. Downloads in that temporary session disappear on exit. Install the optional FrogFind fixtures separately when following the fixture checklist; the normal help page is not a bundled website demo.

On the project's HP 200LX ELKS 3.8 beta 1 setup, use translated keyboard input:

```sh
export ELKSWEB_COOKED_KEYS=1
elksweb -video cga /root/welcome.htm
```

The generic floppy image is intended for emulator testing; use the executable on the existing HP installation. The owner confirms the exact **0.1** executable runs on the standard HP 200LX and reports smoother scrolling there; the owner also confirms it works on the DS HP 200LX. These are owner reports, not independently captured graphics tests or timing measurements.

The verified executable is 77,024 bytes with MD5 `9618c7abec60bc79d5ce539b2516b04c` and the SHA256 below. Local installation records are retained in the parent project's `output/elksweb-hp01/` and `output/elksweb-ds01/`. They verify identity and version separately from the later owner feedback; their earlier “graphics test pending” fields describe the installation-time state. The DS machine is identified by the owner; no clock-speed claim is inferred from its name.

## Validation and identity

Final validation is recorded in `QA-0.1.json` in the browser source documentation. The native application was rebuilt against the prepared toolchain from clean-build001; this was not another fresh compiler/system bootstrap. The validated QEMU image derives from clean-build005 with the new executable, the earlier welcome page and attributed offline fixtures installed. The subsequent default-help/logo packaging refresh does not rebuild or change the executable; its image identity and dedicated welcome-page QA are recorded separately below. Each distribution archive has a SHA256 sidecar and an internal file manifest. The executable and test-image identities below remain unchanged by this documentation refresh.

- Executable SHA256: `5c652079e7cc27884091c9e3b1730fea5d37fa3cbeb690535fed94af16dcfce2`.
- Previously validated QEMU image SHA256 (before the help/logo packaging refresh): `7c51c3df6becacbe2ddbe7eb7d446d67e0d57cff89d1be14531e998d844191f5`.
- Refreshed help/logo image SHA256: `3c865e5edb81f67c50b88554ee0d040f07c474423e1a200313925db37c79711d`.
- ELKS source: `89d09706f17c123f9e0f5ef7cba2eb6745e8478c`.
- The package's `PACKAGE.json` pins the complete browser source revision; its source archive contains all files used to build the browser.
- Native build: no warnings; static 8086 audit passes for 25,970 instructions.
- Memory: 64,816 bytes code, 12,176 initialized data, 38,448 BSS. Including default heap/stack, near allocation is 58,816 bytes before arguments/environment, leaving 6,704 bytes; code headroom is 720 bytes.
- Host tests: 288 pass; seven additional platform tests pass.
- Native scroll oracle: all 54 incremental/full-redraw comparisons match exactly across CGA/EGA/VGA. Tests separately count render writes so identical final screenshots are not mistaken for proof of incremental drawing.
- Native display selection, cancellation, unsupported-option handling and console restoration pass.
- Native history and receive cancellation: 12 checks pass.

All 39 native fixture scenarios pass their request/capture assertions. Download bytes, edited filenames, existing-file protection and recovery after save errors pass. Disk-full testing removes the incomplete file and returns to the welcome page. Live FrogFind mirror search/article/Back and 68k.news homepage/scroll/Back were visually checked. The selected news article displays an upstream extraction error, so successful article reading is not claimed. The independent reviewer inspected 59 frames and recomputed all 54 scroll comparisons without finding a visual regression. Details and evidence limits are recorded in the accompanying QA record. Earlier 8088 Windows 86Box and DOS MicroWeb comparisons remain scoped to their recorded builds. Exact-version Windows 86Box welcome, scrolling and normal-shell exit passed; the original cold-boot exit anomaly remains open, and exact-version live-site checks in that emulator remain pending. No new blind preference vote or physical 8088 timing claim is made for 0.1.

The refreshed help/logo image passes dedicated QEMU checks in CGA, EGA and VGA: no-URL startup opens `/root/welcome.htm`, the original GIF renders, the third link opens `#keys`, scrolling and Home/End behave correctly, two inversions restore identical pixels, and exit restores the text login screen. Twenty original frames were visually inspected without finding a defect; a separate reviewer inspected 16 frames and found no visual blocker. The full page fits in VGA, so anchor/End movement is correctly clamped. A VGA anchor capture was repeated after the first capture preceded completion of the local reload. This asset-only check does not repeat the baseline 39-case suite. [CGA welcome](screenshots/0.1/welcome-cga-qemu.png) · [Selector](screenshots/0.1/selector-qemu.png).

## Future enhancements

Colour GIF rendering for EGA/VGA is deferred beyond 0.1; CGA and HP 200LX monochrome support will be preserved. Further work may improve page-load efficiency, HTML/input handling and hardware coverage. These are investigation areas without committed delivery dates. The prepared blue artwork is not installed by 0.1, and JPEG decoding remains outside the planned scope. See the README’s future-enhancements section for details.

## Known limitations

GIF pixels are supported; JPEG/PNG dimensions are recognized but their pixels are not decoded. JPEG decoding is explicitly outside the 0.1 scope. HTTP only: no native TLS, CSS or JavaScript. Document/layout and form-field limits, accent transliteration and single-line textarea editing remain as described in the main README. Displayed images retain a 200-row limit. EGA requires a color adapter with at least 128 KB video RAM.

Scrolling now avoids repeated drawing, but page loading and other operations can still be slow. Speed and responsiveness are excluded from the first-beta decision. The standard HP owner reports smoother scrolling with 0.1, but no controlled timing measurement is claimed. QEMU does not establish physical adapter compatibility or complete MicroWeb parity.

Optional offline FrogFind fixtures use fixed sample results with their retained license and provenance. They are separate from the normal runtime package. The default help page may link to live sites; the runtime package does not bundle captured news articles. No MicroWeb executable, proprietary BIOS ROM or physical-disk writing tool is included.

The repository and [0.1 experimental prerelease](https://github.com/l00nix/ELKSWeb/releases/tag/v0.1) are public. The discussion announcement remains a draft.

### Current final-QA hold

The exact 0.1 8088 follow-up found an unresolved exit anomaly in its first welcome-page run. A narrower local-FrogFind retry exited and logged in successfully; 640 KB QEMU also passed exit and a shell command. After host unlock, a repeat launched from the normal shell passed welcome, PageDown, Escape and `pwd` returning `/root`. This is narrower than the original cold-boot autorun sequence; that failure remains unexplained. Exact-version live 86Box captures remain pending. See [8088 validation](8088-VALIDATION.md). Public release readiness is not signed off while this investigation is incomplete.
