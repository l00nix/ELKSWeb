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

The two accompanying comment files are drafts. No PR comments, approvals, merges or closures were submitted as part of this integration. EPT, installed device binaries and stable releases were not changed.
