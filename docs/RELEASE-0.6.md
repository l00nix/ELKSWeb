# ELKSWeb 0.6

ELKSWeb 0.6 includes the direct browser and WebNX, its Nano-X client, in one
package with a shared welcome page. Both executables report 0.6.

## Changes since 0.5

- Astrobleem's VGA 640x480 colour support, faster scrolling, cursor restoration
  and colour GIF workspace improvements (PR #3 and related contribution).
- Astrobleem's Nano-X port and WebNX branding (PRs #5/#6), with batched text
  drawing and the standard Nano-X client lifecycle.
- One package and common `/lib/web/welcome.htm`, following ghaerr's guidance.
- Astrobleem's form-field and download-filename repaint fixes and filesystem
  flush after saving (issue #7).
- Fix images remaining as placeholders after mouse navigation. Successful
  navigation now keeps its pending image redraw instead of clipping it to the
  old focus region; no additional full-page redraw or network retry is added.
- Preserve HP cooked keys, PPC/HP serial mouse, inversion, console handling,
  startup/GIF performance improvements and low-memory diagnostics.

## Install

Set `REPO=http://ept.8088retro.com` in `/etc/ept.cfg`, then:

```sh
ept install elksweb
elksweb --version
webnx --version
```

The same release is initially also in nightly (`ept install -n elksweb`).
Close running browsers before replacing them. Users of older separate `webnx`,
`webdata` or `elksnx` packages must follow the [migration guide](NANOX-EXPERIMENT.md#install-and-migrate)
before installing the combined package. Ordinary 0.5 upgrades need no removals.

For a manual installation, extract the runtime archive on a modern host and
copy its `bin/` and `lib/` contents to the corresponding ELKS directories,
preserving executable permissions. Both clients use `/lib/web/welcome.htm`.
A compatible Nano-X server is required only for `webnx` and is not bundled.
Use the direct browser from the local graphics console. Medium-model execution
support (`CONFIG_EXEC_MMODEL`) is required. Colour modes require compatible
hardware and video-memory reservations. Configure networking separately.

## Validation and remaining reports

- All 366 core tests passed with the redraw fix, including first-load mouse
  navigation through text links, linked images and forms in both compile paths
  at 200, 350 and 480 pixel heights. The new cases fail before the fix.
- Both release binaries pass native 8086 and memory audits; Nano-X event tests
  and 19,200 pixel comparisons pass.
- On the physical PPC, the user confirmed the frog appears on the first
  mouse-click load without F2/F5 in the fixed 0.6.4test1 build promoted here.
- Takahiro Yamada reported successful 0.6.4dev WebNX startup, browsing, mouse
  links and exit on PC-9801RX, with XMS enabled and httpd/ftpd stopped. His photos
  are credited in the README. The 0.6 redraw fix still needs his verification.
- No new HP hardware retest, EMS implementation or 512 KB online-browsing claim.
  Issue #7 download verification and issue #8 page-cache investigation remain open.
  The PPC fix does not establish that every earlier Nano-X logo or console report
  has the same cause.

See the accompanying VALIDATION.json for exact package and installation checks.
Release 0.5 remains available for comparison.
