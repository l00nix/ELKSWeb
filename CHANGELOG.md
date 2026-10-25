# Changelog

## 0.3 — experimental beta (2026-10-25)

- Keep the requested URL visible while fetching a new page. Successful redirects
  show the final URL; failed loads restore the current page's address.
- Read the startup display choice as a complete line so ELKS handles Backspace.
  Erasing the choice and pressing Enter selects the default CGA mode.
- When `/dev/tty` is unavailable, try a read/write terminal on standard input,
  verify that it supports graphics, and restore shared terminal settings on exit.
  This guarded fallback does not establish a fix for the intermittent upstream
  console problem; that investigation remains open.

These changes follow [@ghaerr's feedback](https://github.com/ghaerr/elks/discussions/2185#discussioncomment-19170548).
Thanks also to @l00nix for the PPC 512 and HP 200LX DS hardware checklist,
including serial-mouse checks on both devices.

The welcome page identifies 0.3, describes the new behavior, and labels the
updated `http://68knews.8088retro.com/` link **68k news mirror**. FrogFind and
HTTPedia remain available. The standalone executable remains `elksweb`; runtime
and corresponding-source packages remain separate. Both build workflows and
the 8086/8088 target are preserved.

User checks of 0.3-dev1 recorded 16 passes on the PPC and 17 on the HP, with
address editing still partly open on both and the HP-only cooked-key test N/A
on the PPC. These are candidate hardware observations, not controlled speed
measurements or a separate retest of the newly versioned 0.3 executable.
See [0.3 release notes](docs/RELEASE-0.3.md) for release validation and remaining
limits, including the unresolved 86Box cold-boot exit anomaly.


## 0.2 — experimental beta (2026-10-24)

ELKSWeb remains a native graphical HTTP browser for IBM PC compatibles running
ELKS, including the HP 200LX. The executable is named `elksweb`.

### Navigation and drawing

- Add `http://` to address-field input without `://` or a leading `/`, while
  preserving explicit schemes and local paths. Suggested by
  [@ghaerr](https://github.com/ghaerr/elks/discussions/2185#discussioncomment-19129624).
- Reduce startup, address-editing and keyboard-focus redraws. Tab/Shift-Tab repaint
  affected focus bands; clicking a link no longer repaints the old page before
  starting navigation. Based on
  [@ghaerr's blinking report](https://github.com/ghaerr/elks/discussions/2185#discussioncomment-19083542),
  [@sammothxc's 8088 report](https://github.com/ghaerr/elks/discussions/2185#discussioncomment-19089146),
  and Alex (@l00nix)'s PPC 512 click testing.
- Repaint image areas when declared dimensions already fix the layout; retain
  reflow when image dimensions require it. Skip redundant GIF background
  initialization for a full-canvas first frame, preserving initialization for
  partial frames. @sammothxc's image-placeholder and slow-GIF feedback guided this
  work. These changes benefit qualifying GIFs on any page, not just the welcome
  logo; no hardware speed multiplier is claimed.

### Fonts and mouse

- Replace the previous fonts with public-domain X.Org fixed fonts: 6x10 small,
  6x13 body and 7x14 large, with dedicated bold body/large faces. Adjust controls
  and clipping for the taller text. @ghaerr suggested X11 6x13; @sammothxc also
  reported CGA legibility problems, and Alex selected and checked the PPC font.
- Honor ELKS `MOUSE_TYPE`/`MOUSE_PORT` conventions with browser-specific overrides.
  Use ttyS0 for serial mice on hardware and ttyS1 with the QEMU environment flag.
  Keep PS/2 support and keyboard-only operation. Suggested by @ghaerr.
- Improve Microsoft serial packet handling, use a larger pointer and slower
  subpixel motion, and coalesce bounded motion input while preserving button
  transitions. Alex's PPC tests used Microsoft Serial Mouse 2.0A and E6QMOUSE X31
  mice through a 9-pin/25-pin mouse adapter. Hardware coverage remains limited.

### Installation and help

- Install welcome HTML, logo, provenance and consolidated notices under
  `/lib/elksweb`; retain `/root/welcome.htm` as a compatibility fallback.
  Requested by [@ghaerr in PR #2837](https://github.com/ghaerr/elks/pull/2837#issuecomment-6297863588).
- Refresh the welcome page with 0.2 identification, hostname entry, networking
  instructions and FrogFind, 68k.news and HTTPedia links. Explain `net start`
  following [@djohanse's report](https://github.com/ghaerr/elks/discussions/2185#discussioncomment-19086934).
- Retain the lightweight external builder alongside the separately audited
  developer build. Publish the standalone `elksweb` executable and separate
  runtime/corresponding-source archives with checksums.

### Validation and remaining work

The release checks cover host regressions, GIF differential decoding, the native
8086 instruction and memory audit, agreement between both builders, and QEMU
CGA/EGA/VGA normal/inverted welcome and GIF rendering with console restoration.
See [release notes](docs/RELEASE-0.2.md) for the distinction between automated,
emulator and hardware evidence. Detailed development logs remain local.

Large-page parsing, some click/load latency and broader hardware coverage remain
work in progress. The earlier 86Box cold-boot exit anomaly is still unresolved.
HTTP only; no TLS, CSS or JavaScript. GIFs display their first frame; JPEG/PNG
pixels are not decoded. HTTPedia availability depends on external DNS/site
service and was not established in the latest development checks.

## 0.1 — experimental beta

See [the historical 0.1 release notes](docs/RELEASE-0.1.md). Its hardware and
emulator evidence belongs to that executable and is not a 0.2 certification.
