<p align="center">

  <img src="artwork/elksweb-wordmark-yellow-globe.png" alt="ELKSWeb logo" width="640">
</p>

# ELKSWeb 0.3

An experimental graphical web browser for [ELKS Linux](https://github.com/ghaerr/elks), written in C with the native ELKS IA16 toolchain and targeting 8088-compatible machines.

Inspired by [the ELKS graphical-browser discussion (#2185)](https://github.com/ghaerr/elks/discussions/2185) and [MicroWeb](https://github.com/jhhoward/MicroWeb). ELKSWeb is an original implementation.

**Version 0.3 — experimental beta.** Keep the requested URL visible during loading, correct display selections with Backspace, and improve console startup handling. See the [changelog and feedback credits](CHANGELOG.md), [0.3 release notes](docs/RELEASE-0.3.md) and [downloads](https://github.com/l00nix/ELKSWeb/releases/tag/v0.3).

The 0.3-dev1 candidate passed user hardware checks on the Amstrad PPC 512 with PicoMEM 2 and HP 200LX DS, including browsing, GIFs, keyboard navigation and serial-mouse movement/clicking. Address editing remains partially tested; the intermittent upstream console issue remains open. General IBM PC compatibility remains the goal.

## Live browsing on retro hardware

### Amstrad PPC 512

The FrogFind mirror and its frog GIF displayed on the Amstrad PPC 512's original LCD during ELKSWeb testing with PicoMEM 2. Photograph by l00nix.

![FrogFind mirror and frog GIF displayed by ELKSWeb on the Amstrad PPC 512 LCD](docs/screenshots/ppc512/frogfind-lcd-photo.jpg)

HTTPedia displayed on the PPC 512 during 0.3-dev1 hardware testing. Photograph by l00nix.

![HTTPedia displayed by ELKSWeb on the Amstrad PPC 512 LCD](docs/screenshots/ppc512/httpedia-lcd-photo.jpg)

### HP 200LX

ELKSWeb 0.2 on a physical HP 200LX, showing the welcome page and the FrogFind mirror with its GIF. Photographs by l00nix.

![ELKSWeb 0.2 welcome page on a physical HP 200LX](docs/screenshots/hp200lx/0.2/welcome-photo.png)

![ELKSWeb 0.2 displaying FrogFind and its frog GIF on a physical HP 200LX](docs/screenshots/hp200lx/0.2/frogfind-photo.png)

## Design

The C++, networking, graphics-dependency and memory concerns raised in [the ELKS graphical-browser discussion (#2185)](https://github.com/ghaerr/elks/discussions/2185) guide the implementation:

- **C and the native ELKS toolchain:** IA16 GCC and ELKS libc; no C++ runtime or OpenWatcom requirement.
- **ELKS networking:** native sockets and the ELKS `ktcp` service; no DOS packet driver or mTCP dependency. Direct access is HTTP only.
- **Direct graphics:** the browser draws directly to CGA, EGA or VGA video memory and uses ELKS console interfaces. Microwindows/Nano-X is not required.
- **Bounded memory:** segmented storage, explicit document limits and a small disk-backed source cache. These choices reduce conventional-memory pressure but currently incur substantial CPU and disk costs.

## Tested configuration and requirements

- An ELKS system with graphics-capable console interfaces and a working native network stack.
- 8088-compatible processor target. Earlier candidates were exercised in 86Box with an Intel 8088 at 4.77 MHz and 640 KB RAM. The owner confirms the exact 0.1 executable runs on the standard HP 200LX and DS HP 200LX, with smoother scrolling reported on the standard HP. Installation identities were verified separately from those owner graphics reports. Exact-0.1 86Box welcome, scrolling and a normal-shell exit passed; an earlier cold-boot exit anomaly remains unresolved. See the release notes.
- CGA 640×200, color EGA with at least 128 KB video RAM at 640×350, or VGA at 640×480. All browser modes are monochrome. Mode selection and console restoration are exercised in QEMU and Windows 86Box; 0.1-specific results are recorded in the release notes. [CGA capture](docs/screenshots/frogfind-build004-cga-86box.png) · [EGA capture](docs/screenshots/frogfind-build004-ega-86box.png) · [VGA capture](docs/screenshots/frogfind-build004-vga-86box.png).
- A writable `/tmp` for page caching.
- Keyboard navigation and serial-mouse input; 0.3-dev1 mouse movement and clicking passed user checks on the PPC 512 and HP 200LX DS. PS/2 coverage remains limited.

640 KB is the tested configuration, not a proven minimum. General ELKS compatibility is the priority.

### HP 200LX keyboard compatibility

On the [tested HP-specific ELKS setup](https://github.com/l00nix/elks-on-hp200lx), set this flag in the same shell before launching the browser:

```sh
export ELKSWEB_COOKED_KEYS=1
elksweb
```

`ELKSWEB_COOKED_KEYS=1` keeps ELKS-translated keyboard input (characters and escape sequences) instead of enabling the browser's default raw scan-code input. It is a compatibility setting for that HP setup, not a general requirement for IBM PCs or the PPC 512. Leave it unset for normal operation; use `unset ELKSWEB_COOKED_KEYS` to restore the default for subsequent launches.

Serial-mouse setup uses the same settings as the PPC 512, with the HP's cooked-key setting retained. The standard HP Connectivity Pack cable also needs a null-modem adapter for a mouse. See [HP 200LX mouse setup](docs/INSTALL.md#hp-200lx-serial-mouse) for wiring, port ownership and the complete launch command.

## Current features

HTTP and local HTML/text files, relative links, redirects, anchors, scrolling, forms, tables, lists, monochrome GIF images and binary downloads. PNG/JPEG dimensions are recognized for layout, but their pixels are not decoded. JPEG decoding is outside the current scope and is likely to remain outside future releases, similar to MicroWeb. Features have differing levels of test coverage; see [tests](tests/README.md).

## Limitations

- HTTP only; no native TLS, CSS or JavaScript. `HTTP_PROXY` is supported, but HTTPS conversion requires an external service and is not provided here.
- Graphics adapter detection is conservative: unsupported or unrecognized modes are rejected. EGA image aspect correction is approximate, and displayed images retain a 200-row limit in every mode.
- Large or complex pages can exceed fixed layout limits. HTML source is capped at 120 KB; layout at 24 KB of text, 1,024 runs and 256 links.
- Some accented characters are transliterated rather than rendered faithfully.
- Form fields retain at most 79 UTF-8 bytes; textarea editing is single-line. HTML `maxlength` and `size` semantics are not fully implemented. Form support does not imply modern HTML standards compliance.
- No claim of complete MicroWeb parity or physical 8088 certification. Further beta testing and feature enhancements are ongoing.

## Future enhancements

Version 0.3 keeps the monochrome renderer. Follow-up work under consideration includes:

- **EGA/VGA colour GIF rendering**, while retaining monochrome CGA and HP 200LX output. This requires palette-aware image storage, video-plane drawing, scrolling and cursor handling, plus work to fit the 64 KB code-segment limit. The blue logo artwork is prepared for this future work; it is not the installed 0.1 logo.
- **Faster page loading and rendering**, with measured reductions in CPU, disk and memory use.
- **Broader compatibility testing**, including additional ELKS systems, physical 8088 machines and display adapters, and investigation of the remaining 86Box cold-boot exit anomaly.
- **HTML and input improvements**, including form controls, accented text and clearer handling of document limits.

These are directions, not promised features or dates. JPEG decoding remains outside the planned scope; ELKSWeb displays GIF pixels and uses JPEG/PNG dimensions for placeholders.

## Keyboard shortcuts

| Key | Action |
| --- | --- |
| F6 / Ctrl-L | Edit address |
| Tab / Shift-Tab | Select link or control |
| Enter | Activate selection |
| Arrows / Page Up / Page Down | Scroll |
| Home / End | Start / end of document |
| Backspace | Back |
| F5 | Reload |
| F2 | Invert monochrome output |
| F3 | Show/hide browser bars |
| Escape | Exit; cancel a network load when input is polled |

These navigation shortcuts apply to normal page browsing. In an address or text field, Left/Right, Home/End and Backspace edit the field; select/radio controls use arrows to change choices. Escape first dismisses address editing, an open select list or a download prompt.

## Command-line options

```text
elksweb [-video cga|ega|vga] [-invert] [-noimages] [http://URL or local-file]
```

Without `-video`, ELKSWeb displays a text-console selector before entering graphics. Choose 1, 2 or 3 and press Enter; Enter alone selects CGA, and Q followed by Enter quits. Only detected modes are listed. `-video cga`, `-video ega` or `-video vga` bypasses the selector; unsupported modes fail without changing graphics or console settings.

`--version` prints the version without entering graphics. `-noimages` disables image loading. It does not establish a performance target. EMS and XMS options are not implemented.

## How to install a release

Download the [0.3 beta runtime package](https://github.com/l00nix/ELKSWeb/releases/tag/v0.3) on a modern computer, verify its checksum, and transfer it to an existing ELKS installation. Install `bin/elksweb` as `/bin/elksweb` and the files in `lib/elksweb/` under `/lib/elksweb/`. The executable is always named `elksweb`. Keep the included notices and corresponding-source archive available.

```sh
chmod 755 /bin/elksweb
elksweb --version
elksweb
```

The version reports **0.3**. Choose a detected display mode to open the local welcome page. Configure native ELKS networking and run `net start` before using HTTP. Enter a hostname such as `68knews.8088retro.com` in the address field or an explicit URL.

See [INSTALL.md](docs/INSTALL.md) for exact file paths, checksums, mouse settings and upgrades. The runtime is a standalone application package, not an ELKS disk image. [BUILDING.md](docs/BUILDING.md) describes both source-build workflows.

## Test sites and related projects

- [68k news mirror](http://68knews.8088retro.com/) — linked from the welcome page; historical screenshots also used the original 68k.news site; [ActionRetro/68k-news source](https://github.com/ActionRetro/68k-news).
- [FrogFind](http://frogfind.com/) — current live QA uses the supplied [HTTP mirror](http://frogfind.8088retro.com/). The original hostname failed in the historical Windows run. Repeatable file and HTTP examples are under [tests/fixtures/frogfind](tests/fixtures/frogfind/README.txt); these are labelled fixed fixtures, not live search. [Source](https://github.com/ActionRetro/FrogFind).
- [HTTPedia](http://httpedia.com/) — additional testing target; external availability may vary.
- [MicroWeb](https://github.com/jhhoward/MicroWeb) — inspiration and independent comparison reference.
- [ELKS](https://github.com/ghaerr/elks) — operating system, toolchain and networking.

These projects are credited for their respective work; no endorsement or affiliation is implied.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [beta testing checklist](docs/BETA-TESTING.md). See the [0.3 release notes](docs/RELEASE-0.3.md) for current validation scope. Historical checks remain in STATUS; broader compatibility and performance feedback are welcome. Testers and feedback are welcome.

## License and attribution

Original browser code is GPL-2.0-or-later; see [COPYING](COPYING). Independently sourced font data retains its [X.Org public-domain notice](font/COPYING) and [provenance](font/provenance.json). No MicroWeb source, font, image assets or executable is embedded in ELKSWeb. The separately attributed FrogFind test fixture retains its GPL-3.0 license and provenance under [tests/fixtures/frogfind](tests/fixtures/frogfind/README.txt). Website content visible in screenshots belongs to its respective providers.
