# Nano-X experiment validation — 23 November 2026

Candidate: **0.6dev1-nx1**, executable source commit `494e5f0`, based on
0.6dev1 `b4a162f` and PR #5 head `5e876a2` (both contributor commits retained).
This is development evidence, not a release or physical PC-98 certification.

## Build and regression results

- The ELKS IA16 medium-model Nano-X build succeeded. `elksnx` is 100,728 bytes
  on disk; that is not its total runtime memory requirement.
- The direct `elksweb` build passed its 8086 ISA audit and is byte-for-byte
  identical to the published 0.6dev1 comparison executable. Native HP/PPC
  display/input code and the integrated GIF workspace fix are preserved.
- 389 existing host unittest cases passed without skips or failures, plus
  GIF/dimension differential checks and 10,000 sanitizer-backed core fuzz
  iterations.
- New Nano-X event checks passed for button ordering, mouse-before-Escape,
  mouse-before-close, discarded transfer clicks, held buttons, exposure and
  persistent close state.
- 19,200 batched/unbatched text pixel comparisons passed. The sample italic
  line used 10 bitmap calls instead of 94. Both Nano-X host checks also passed
  AddressSanitizer and UndefinedBehaviorSanitizer.

Executable SHA256 values:

```text
elksnx  bbe8b049b095482a492d74836aaf30746db403d293de52cec23ce09ed2712017
elksweb 1e88f4a36dab48567843223f488564e59e849e52ebbbadfaac30845df8725087
```

## IBM-compatible emulator results

QEMU ISA PC, 486 CPU, 8 MB configured RAM, standard VGA; existing ELKS 0.9.2
FAT image with `hma=kernel`, `buf=8`, `xms=on`. Networking was disabled and the
server used `MOUSE_PORT=none`. The retained VGA Nano-X server's SHA256 is
`05a5067328cadd59edcc3cf81808cae2a2d210f3fb1dc25a8c92da27c8f68809`.
This is the project's older retained server, not a fresh latest-upstream build.

- The colour page, ELKSWeb colour GIF and sixteen-colour chart rendered.
- Three consecutive minimal-server/browser launches returned to a usable
  login prompt on Escape. The log recorded three complete GrOpen/GrClose
  sequences; neither browser nor server remained in the final process list.
- Address editing opened and could be cancelled before exiting the browser.
- A separate long-page test scrolled on Down and returned on Up with an
  exact pixel match to the initial frame.
- **Page Down did not scroll** with this server. Its ELKS keyboard decoder
  excludes the numeric Page Up/Down escape-sequence mapping. This needs a
  current-server comparison; it is not classified as a browser regression.

The first smoke harness captured an incomplete GIF repaint and typed later
login commands too early. It was superseded by runs with longer readiness
allowances and inspected screenshots. No performance measurements or speed
claims are derived from these fixed waits.

## Memory observations

The `meminfo -m` snapshots, including the observer command's own memory,
reported:

| Stage | Main memory used / total | Main memory free |
| --- | --- | --- |
| Before server launch | 94 / 541 KiB | 447 KiB |
| Server running, before browser replaces shell | 174 / 541 KiB | 367 KiB |
| After three browser/server exit cycles | 94 / 541 KiB | 447 KiB |

The server stage therefore added about 80 KiB in this configuration. The
post-exit result shows no retained allocation at the displayed KiB precision;
it does not prove the absence of every leak. These snapshots do **not** measure
the browser's steady-state or peak GIF-decoding allocations. The emulated
system also uses XMS-backed storage/buffers. Do not interpret its free-memory
figures as PPC/HP requirements or as browser use of EMS/XMS.

## Still required

- Physical PC-98 retest of text-plane overlap and the reported apparent hang.
- Latest Nano-X server comparison, including Page Up/Down and other special keys.
- Native Nano-X mouse tests and live stalled-transfer cancellation, beyond
  the host event-adapter tests.
- Window-manager close during editing/download and exposure on the real server.
- Browser/decoding memory measurements, then ktcp-only networking and HTTP/GIF
  regression checks. No networking result is claimed for this experiment yet.
- A documented server/build combination and reproducible runtime package before
  considering an EPT nightly publication.

See [the experiment guide](NANOX-EXPERIMENT.md) for launch and diagnostic steps.
