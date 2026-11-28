# ELKSWeb and WebNX 0.7

0.7 brings the 0.6.1dev keyboard controls, corrected image-loading optimizations and faster monochrome GIF repainting into the general release. Both executables continue to use `/lib/web/welcome.htm`. The direct browser retains the HP 200LX and Amstrad PPC console, cooked-key, serial-mouse and display fixes.

## Changes

- **Keyboard controls and offline help:** Ctrl-R reloads, Ctrl-D redraws without downloading, Ctrl-V changes theme, Ctrl-T toggles the bars and Ctrl-G opens help. Ctrl-L still edits the URL; Ctrl-B/F navigate history and Ctrl-N/W select controls. Existing function keys remain available. Thanks to ghaerr for the guidance and Takahiro Yamada for PC-98 testing.
- **Image loading:** the safe part of PR #9 skips unnecessary reflow after failed or explicitly sized images. PR #10 loads known-size GIF bodies directly into far memory, with spill-file fallback and allocation retry after closing the socket. HTTP 204, growing local files and failed-allocation cleanup are covered. DNS reuse is limited to one navigation, with a fresh lookup after a cached-address connection failure. Thanks to astrobleem for these contributions.
- **Nano-X responsiveness:** synchronous event polling avoids the pending-reply/socket deadlock seen during PPC redraws. Startup avoids a redundant map exposure and separate starting-screen paint. Scaled monochrome GIFs are sent as packed rows rather than individual pixel rectangles; scrolling uses the decoded image and does not download the page again.
- **ELKS distribution integration:** `toolchain/build-external.sh` builds both clients and stages shared data. A companion ELKS patch adds WebNX to `buildext.sh`/`ExtApplications`, installs pages under `/lib/web`, and prepares the Microwindows dependency for standalone builds. This follows ghaerr's request for HD images and the Nano-X launcher, without EPT at image-build time.

## Install

With `REPO=http://ept.8088retro.com` in your EPT configuration:

```sh
ept install elksweb
elksweb --version
webnx --version
```

Both executables report **0.7**. `elksweb` uses the graphics console; `webnx` needs a compatible Nano-X server. The runtime archive contains `bin/` and `lib/` trees for manual installation. Keep the notices and corresponding source. [Migration instructions](NANOX-EXPERIMENT.md#install-and-migrate) apply to older separate `webnx`, `webdata` or `elksnx` packages: remove those packages **before** installing the combined package. Ordinary combined-package upgrades need no removal.

## Validation and remaining work

The release's validation record accompanies the downloadable assets. Candidate hardware feedback includes Takahiro's confirmed first-load frog and Ctrl-key operation on PC-98, and the PPC user's working mouse and preliminary clean scrolling with screen-copy disabled. These are candidate observations, not a fresh final-release HP/PC-98 hardware certification.

WebNX still repaints visible content when scrolling on the PPC. An experimental screen-copy path improved speed but produced corruption on hardware, so it is **not included**. The row-based GIF improvement remains. The direct browser's existing scrolling acceleration is unchanged.

PR #9's table-plan reuse remains deferred. [Issue #8](https://github.com/l00nix/ELKSWeb/issues/8), the unconfirmed live FrogFind page-cache failure, remains open. The independent EMS work in PR #4 is not included. No new kernel, Nano-X server, EMS support or 512 KB online-browsing claim is part of this release. Current-upstream build compatibility does not establish protected-mode runtime support.

Releases [0.6](https://github.com/l00nix/ELKSWeb/releases/tag/v0.6) and [0.5](https://github.com/l00nix/ELKSWeb/releases/tag/v0.5) remain available for comparison.
