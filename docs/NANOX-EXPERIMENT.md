# Nano-X experiment: 0.6dev1-nx1

This separate experimental `elksnx` build combines astrobleem's
[PR #5](https://github.com/l00nix/ELKSWeb/pull/5) with the 0.6dev1 source,
including PR #3 and the independent colour GIF workspace fix. It is not a
release of 0.6 or a replacement for the direct-graphics `elksweb` package.
The direct executable still identifies as 0.6dev1. The Nano-X executable
identifies as 0.6dev1-nx1.

See the [initial validation record](NANOX-VALIDATION.md) for build checks,
emulator evidence, measured memory recovery and remaining limitations.

## Changes beyond PR #5

- Discard mouse events during network progress so a pending pointer event
  cannot prevent Escape or window-close events from being consumed. Preserve
  normal button ordering outside transfers and do not replay transfer clicks.
- Honour a window-manager close request as application exit, even while an
  address field, selection or download dialog is active. Escape retains its
  ordinary cancel/edit behaviour.
- Repaint exposure events during network progress, even if status text has
  not changed.
- Offer opt-in file lifecycle diagnostics and recommend the minimal server
  launch when connection fails.

These changes do not establish the cause of the physical PC-98 exit problem.
No kernel, EMS, Nano-X server or physical-machine configuration is modified.

## Build and host checks

Use a prepared ELKS IA16 toolchain and the Microwindows source corresponding
to the target server. Client and server must agree on the Nano-X protocol.

```sh
ELKSWEB_ELKS=/path/to/built-elks MWDIR=/path/to/microwindows \
    sh toolchain/build-nanox.sh
MWDIR=/path/to/microwindows sh toolchain/test-nanox.sh
```

Output is `build/nanox/elksnx`. Install separately from `/bin/elksweb`, with
the ordinary `/lib/elksweb/` HTML/GIF assets. The builder preserves the
medium-model signal-handler correction in the Nano-X client and stops if
the expected correction cannot be verified. Host checks cover Nano-X event
ordering/cancellation and compare batched/unbatched text pixels. They do
not validate the ELKS ABI, device drivers or physical hardware.

## Minimal physical test

Keep the known-working browser, server and boot configuration. Start with
networking stopped and a local page. From a fresh local text login, with no
other Nano-X clients running:

```sh
meminfo -m > /tmp/nx-before.txt
export ELKSWEB_NX_LOG=/tmp/elksnx.log
/bin/nano-x > /tmp/nx-server.log 2>&1 &
sleep 3
ps > /tmp/nx-processes.txt
ls -l /tmp/nxsock > /tmp/nx-socket.txt
meminfo -m > /tmp/nx-server-memory.txt
exec /bin/elksnx /lib/elksweb/color.htm > /tmp/nx-client.log 2>&1
```

The three-second wait is an initial diagnostic allowance, not a readiness
guarantee. If connection fails, inspect the saved process/socket/server logs;
do not delete a socket that may belong to a running server. `exec` releases
the launching shell's memory, so a clean exit normally returns to a login
prompt rather than to that shell. For a first failed run, retain the log files
before repeating; the browser lifecycle log appends to existing contents.

Redirecting diagnostics avoids adding new text-plane output after graphics
starts. It is not a fix for the PC-98 console driver's text-plane handling.
On IBM hardware, use a Nano-X server built for the installed graphics adapter.
For a keyboard-only IBM test, `export MOUSE_PORT=none` before starting the
server avoids serial-mouse initialization; this is a server setting, not an
ELKSWeb mouse setting.

## Exit diagnosis

`ELKSWEB_NX_LOG` records `GrOpen begin`, connection/window setup and
`GrClose begin`/`GrClose end`. Connection failures include the last errno,
which is a diagnostic clue, not proof of the underlying cause. Logging is
disabled unless a nonempty file path is set. A logging failure does not
prevent browser startup.

`window ready` means setup requests have been sent/queued; it is not a
rendering acknowledgement. `GrClose end` shows that the client close function
returned, not that the server restored the display or keyboard. Nano-X can
remain active when another client is connected or when started in persistent
mode. Preserve this distinction when reporting an apparent hang.

If the display/keyboard appears stuck, use an already-available serial shell
to record `ps` and the logs before rebooting. Do not enable an extra shell just
for a minimal-memory measurement without accounting for its memory cost.

## Validation matrix

| Test | Evidence needed |
| --- | --- |
| Fresh local startup | Version, kernel/server revisions, free memory, screenshot |
| Colour and transparent GIFs | Welcome, colour chart and transparent image screenshots |
| Keyboard and mouse | Links, fields, button press/release, Escape cancellation |
| Transfer cancellation | Pointer motion/clicks followed by Escape; no delayed click on the loaded page |
| Window close | Normal view, address editing, dialog and stalled HTTP request |
| Exposure | Repaint after another window covers/uncovers the browser, including during loading |
| Scrolling | Up/down and page/home/end; restored pixels and input responsiveness |
| Exit/relaunch | Client/server process state, close log, usable text console; repeat three times |
| Networking | Local baseline, then ktcp only, then HTTP and GIF loads; measure each stage |

Measure memory separately with the observer's own cost recorded. Compare
server-only, browser with a small local page, GIF decoding and ktcp + browser.
The PR's emulator memory figures do not establish requirements for PPC,
HP 200LX or physical PC-98. Keep physical PC-98, IBM emulator and PPC/HP
results labelled separately. The direct browser remains the PPC/HP baseline.
