# PR #9 / #10 development integration — 27 November 2026

Branch: `dev/0.6.1-performance`, based on `492b1a4` (0.6.1dev keyboard shortcuts and help).

| Change | Decision | Commit |
| --- | --- | --- |
| Existing synchronous Nano-X event candidate | Preserve; physical validation pending | `715f01f` |
| [PR #9](https://github.com/l00nix/ELKSWeb/pull/9): skip unnecessary image reflow | Integrate | `b8c6b50` |
| PR #9: replay table plans | Defer due to documented truncation/layout difference and lack of hardware coverage of this path | — |
| [PR #10](https://github.com/l00nix/ELKSWeb/pull/10): direct image buffers and DNS reuse | Integrate with corrections | `1bdfbb1` |

Reviewed heads: #9 `2d8b29a0d1f95bb74e109e570a4f9d332c37f8e3`, #10 `ecf1af01be609001ad228dc1eacb758ca069c2be`.

PR #10 corrections: avoid a null write on HTTP 204 image responses; fall back to disk on direct allocation failure and retry after closing the connection; bound local reads to their allocation; reset DNS reuse on each document fetch and retry resolution once after a cached connection fails. Chunked and close-delimited downloads continue using disk. This is not EMS/XMS support or a reduction in the GIF decoder's workspace requirement.

The HP/PPC platform code and keyboard work remain in the branch. The synchronous Nano-X candidate is preserved separately from the performance changes. Passing emulator tests does not establish that it fixes the physical PPC deadlock; the earlier baseline also passed emulator stress tests.

## Validation

- `python -m unittest discover -s tests`: **394 passed**, 96.653 seconds on the host. Includes six image-reflow cases, DNS cache lifetime/retry tests, transient and persistent allocation failures, and empty-response recovery.
- Both production native builds passed their 8086 ISA and near-memory audits.
- Nano-X event tests passed; **19,200 pixel comparisons** passed.
- Both native binaries passed QEMU tests with loopback HTTP fixtures: an unsized GIF and an HTTP 204 image, exact first-frame/redraw equality, reload, theme, bars, help/history, held-arrow scrolling, and exit. Each browser fetched the GIF and empty image once per document load, across three loads.
- Direct browser used VGA; WebNX used the CGA Nano-X server from the PPC investigation with mouse disabled. QEMU configuration was 486 / 8 MB, so these are not 8088 timing or low-RAM hardware results.
- Visually inspected initial screenshots for both browsers, direct inverted rendering, Nano-X help and return to login. Process snapshots confirmed both browser and Nano-X server had exited.

| Binary | Near memory before argv/environment | SHA-256 |
| --- | ---: | --- |
| elksweb | 62,112 / 65,520 bytes | `1b99846a6493ea94810cfb9f1507dc11b73b2e18300ac3ceb651968bac9e2fef` |
| webnx | 60,544 / 65,520 bytes | `e4c6846300422ace6e31668838ee18e88ff6b8838fa672d08a63e9544fd1db1d` |

Private build logs, audit JSON, binaries, emulator screenshots and runtime scripts are retained in the parent workspace at `work/pr-integration-20261127/`. The independent HTTP 204 reproducer and original-PR/baseline results are at `work/pr-review-20261127/`.

## Remaining validation and publication

Physical PPC and HP runs are still required for memory pressure, networking, GIFs, keyboard/mouse and timing. Use the same frozen workloads and alternate baseline/candidate runs before claiming a performance gain. PR-reported measurements are not newly reproduced results for this combined build.

The two accompanying comment files were subsequently approved and posted: [PR #9 comment](https://github.com/l00nix/ELKSWeb/pull/9#issuecomment-7223393542), [PR #10 comment](https://github.com/l00nix/ELKSWeb/pull/10#issuecomment-7223393930). Neither PR was merged or closed. EPT and stable releases were not changed.

## Physical PPC smoke test — 27 November 2026

The exact combined binaries were installed separately in `/root/w061perf` on the physical Amstrad PPC 512 with PicoMEM 2. Read-back SHA-256 checks matched the audited builds above. The installed `/bin/elksweb`, `/bin/webnx`, Nano-X server, EPT ownership records, original console launcher and boot configuration were preserved and reverified, as was the older `/root/web050/elksweb` comparison binary.

Three automatic direct-console runs completed: installed 0.6.1dev welcome page, candidate welcome page, and candidate first-load `http://frogfind.8088retro.com/`. Raw CGA framebuffer captures taken 120 and 135 seconds after each launch were identical within each run. The current and candidate welcome captures were also byte-identical. Visual review confirmed both welcome logos and the FrogFind frog. All three processes exited with status zero after SIGTERM, and the machine returned to console login.

These were rendering and graceful-signal-exit smoke tests, not load-time measurements. Mouse input was disabled; FTP was stopped during the runs, with networking and Telnet available. No physical keyboard/mouse actions were injected. WebNX keyboard/scrolling/hang validation and HP testing remain pending.

Launchers on the PPC:

- `exec /root/startperf`: candidate direct browser with the existing Microsoft serial-mouse settings.
- `exec /root/startcur`: installed direct browser for comparison, with identical settings and page.
- `exec /root/nxperf`: candidate WebNX help page, images and mouse disabled for the initial hang/scrolling check.
- `exec /root/nxcur`: installed WebNX with the same initial settings for comparison.
- Add `gif` to either Nano-X launcher to open the shared welcome page with images enabled. Mouse remains disabled.

The physical capture runner, logs, screenshots, installation hashes and comparison results are retained privately at `work/ppc-perf061-20261127/` in the parent workspace. FTP was used briefly after the runs to retrieve captures and verify preservation, then stopped again for the interactive WebNX test.
