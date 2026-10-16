# Draft response to ELKS discussion #2185

For review only — not posted. Intended destination: [Graphical Web browser](https://github.com/ghaerr/elks/discussions/2185).

The repository and release draft are still private. The repository links require authorized access, and the raw screenshot preview may be unavailable while the repository is private. Before posting an availability announcement, confirm download visibility and update the cold-boot exit status from the latest evidence. This draft does not claim that the remaining QA gate has passed.

---

This discussion inspired **ELKSWeb**, an original graphical browser for ELKS written in C using the native ELKS IA16 toolchain, with an 8088-compatible instruction target. Version **0.1** is an experimental beta.

[ELKSWeb repository](https://github.com/l00nix/ELKSWeb) · [Release downloads](https://github.com/l00nix/ELKSWeb/releases)

MicroWeb provided the visual and behavioral reference. ELKSWeb is a new implementation, with no MicroWeb C++ code or assets included. The concerns raised here shaped its design:

- Native C and ELKS libc, without a C++ runtime or OpenWatcom requirement.
- Native ELKS sockets and `ktcp`, without mTCP or a DOS packet driver.
- Direct CGA/EGA/VGA graphics, without Microwindows or Nano-X.
- Bounded document storage and a disk-backed page cache to work within 16-bit memory constraints.

At startup it offers the display modes detected on the machine: CGA 640×200, EGA 640×350 or VGA 640×480. **All three are monochrome in 0.1.** It supports HTTP and local HTML/text files, links, history, basic forms and tables, GIF images and binary downloads. The browser frame stays in place during ordinary vertical scrolling; existing page pixels move and the newly exposed strip is drawn. A local welcome page provides keyboard help and links to get started.

Here is an actual ELKSWeb 0.1 screenshot of **68k.news**, captured in QEMU:

![ELKSWeb 0.1 displaying the live 68k.news homepage in QEMU](https://raw.githubusercontent.com/l00nix/ELKSWeb/main/docs/screenshots/68k-news-0.1-qemu.png)

This capture predates the later welcome-page/logo packaging refresh; the browser executable is unchanged. [68k.news source](https://github.com/ActionRetro/68k-news) and the [FrogFind mirror](http://frogfind.8088retro.com/) have been useful test sites. Website content belongs to its respective providers.

I've tested 0.1 on my standard HP 200LX and DS HP 200LX, and scrolling is noticeably smoother on the standard HP. Automated QEMU checks cover the display modes, navigation, downloads and incremental scrolling. 86Box testing is configured for an Intel 8088, but physical Intel 8088 compatibility is not yet independently established. QEMU uses a 486 CPU for integration testing.

There are deliberate limits: HTTP only, no native TLS, CSS or JavaScript. GIF pixels render; JPEG/PNG dimensions are used for layout, with placeholders instead of decoded pixels. Loading can be slow, and complex pages can exceed the fixed document limits. One early cold-boot 86Box exit test produced a BIOS initialization banner; a subsequent normal-shell scrolling/exit test passed, but the original anomaly is still being investigated. Full MicroWeb parity is not claimed.

The normal package contains the executable, local welcome HTML, GIF logo and required notices. Corresponding source and an optional emulator test image with fixed FrogFind fixtures are separate downloads; the normal package does not include `webfrog`/`webnews` launchers or captured news articles.

Possible follow-ups include EGA/VGA colour GIF rendering, efficiency improvements and broader hardware coverage. Colour is deferred beyond 0.1, and JPEG decoding is outside the planned scope. Feedback on ELKS compatibility, rendering and reproducible functional bugs would be very welcome; please include the ELKS build, machine/display mode, URL or local fixture, and steps to reproduce.
