# Nano-X experiment: 0.6dev2-nx1

`webnx` is the optional ELKSWeb Nano-X client from astrobleem's
[PR #5](https://github.com/l00nix/ELKSWeb/pull/5). The direct browser remains
`elksweb` (0.6dev2); renaming it to `web` is a separate decision. Both retain
the 0.6dev1 rendering and GIF work, HP/PPC fixes and Nano-X event handling.
This nightly is not a stable 0.6 release and adds no kernel or EMS support.

## Install and migrate

The EPT nightly has three packages with distinct file ownership:

- `elksweb`: `/bin/elksweb`, direct graphics/input.
- `webnx`: `/bin/webnx`, Nano-X graphics/input.
- `webdata`: shared HTML, GIFs, licences and guides under `/lib/web/`.

EPT's file catalogue has no dependency resolver. Install `webdata` explicitly
before either new browser; installing just an executable does not fetch it.
With `REPO=http://ept.8088retro.com/local` in `/etc/ept.cfg` and networking up:

```sh
ept install -n webdata
ept install -n webnx
webnx --version
```

For the direct browser, use `ept install -n elksweb` after installing webdata.
It reports 0.6dev2; webnx reports 0.6dev2-nx1. Existing `elksweb` nightlies and
old `webnx` installations upgrade under their existing package names. Close
running browsers first. Back up any customized package files: EPT removes
files dropped by an upgraded package, including the old `/lib/elksweb/` and
`/lib/webnx/` managed assets. It does not move custom content automatically.

If you still have the earlier `elksnx` package, install webdata and webnx
successfully first, then `ept remove elksnx`. Update personal scripts or
Nano-X menu entries from `/bin/elksnx` to `/bin/webnx`.

The default pages are `/lib/web/welcome.htm` (direct monochrome),
`/lib/web/color.htm` (direct colour), and `/lib/web/welcnx.htm` (Nano-X).
All refer to the same image files. Paths fit FAT 8.3. Explicit URL/file
arguments still work; manually installed legacy default pages remain fallback
locations. With no page available, a bare launch prints the webdata install
command before initializing graphics. It can still open an explicit URL/file.

Removing either browser leaves webdata and the other browser intact. Keep
webdata while either browser needs these pages; EPT does not prevent its
removal. Remove it separately with `ept remove webdata` only when no longer
needed. A missing webdata installation can be restored with the install
command above. Stable 0.5 remains self-contained and unchanged.

## Normal Nano-X startup and exit

Install a Nano-X server built for your hardware and with a protocol compatible
with the client library. Then launch from the local console or an existing NX
session:

```sh
webnx
```

Use `exec /bin/webnx` when replacing a launching shell is useful to save RAM.
The client uses standard `GrOpen` at startup and `GrClose` at shutdown. The
client library can start an installed `/bin/nano-x` automatically if needed.
No manual server-start sequence, socket deletion, special browser shutdown
command or browser-controlled server kill is required for normal operation.

As [ghaerr clarified](https://github.com/l00nix/ELKSWeb/pull/5#issuecomment-7109375432),
the server decides when to exit (including its persistent `-p` mode and other
clients) and restores the text console when it exits. Closing webnx inside an
existing NX desktop should not forcibly terminate that session. `nxstart`'s
Close menu ends the desktop session; it is not a special way to close webnx.
Ghaerr plans an nxstart browser menu entry; this package does not modify
nxstart or claim that entry is already installed.

Nano-X supplies the keyboard and mouse. IBM Nano-X servers may support
`MOUSE_PORT=none` for keyboard-only testing. Native-browser cooked-key and
serial-mouse settings do not configure the Nano-X server. Function keys and
Page Up/Down depend on its keyboard driver; some older ELKS servers do not
translate all of them. Common browser flags (`-invert`, `-noimages`, explicit
URLs) retain their existing meaning. No new startup-options file is introduced.

## Diagnostics, not a required launch procedure

Optional file logging:

```sh
export ELKSWEB_NX_LOG=/tmp/webnx.log
exec /bin/webnx /lib/web/welcnx.htm
```

The existing environment variable name is retained for compatibility. The log
appends `GrOpen begin`, connection/window setup and `GrClose begin/end`.
`window ready` records queued setup, not a rendering acknowledgement;
`GrClose end` records the client call returning, not console restoration.
Logging failures do not stop the browser. Connection errors include errno.

If ordinary startup fails, record the kernel/server versions, launch command,
`ps`, `meminfo -m`, and `ls -l /tmp/nxsock`. Do not delete a live server's socket.
Starting `/bin/nano-x` separately with its output redirected, then retrying
webnx, can help distinguish server-start failures from connection failures.
A fixed sleep is not proof of readiness. Redirect diagnostics to files to
avoid writing console text over graphics.

Astrobleem reproduced the PC-98 white text overlay in DOSBox-X and reported
that `clear` immediately before `exec /bin/webnx ...` removed it. This is an
emulator-tested diagnostic workaround, not a confirmed physical RX fix and
not a fix for the reported exit hang. Preserve logs and client/server process
state before rebooting if an already-available serial shell still responds.
Record whether NX was started by the client library, by hand or by nxstart.

Avoid unnecessary telnetd/ftpd/nxterm processes when measuring memory, and
account for the observer's memory cost. Measure server-only, small local page,
GIF decoding and networking separately. No new 512 KB or general low-memory
support claim follows from the emulator results.

## Build and validation

```sh
ELKSWEB_ELKS=/path/to/built-elks MWDIR=/path/to/microwindows \
    sh toolchain/build-nanox.sh
MWDIR=/path/to/microwindows sh toolchain/test-nanox.sh
```

Output: `build/nanox/webnx`. The builder checks the medium-model signal
callback correction in the client library. The corresponding-source archive
contains the exact client sources, build provenance and validation record.
The [initial validation](NANOX-VALIDATION.md) is historical nx1 evidence.

Test normal startup, shared welcome/GIFs, links and fields, keyboard/mouse,
transfer cancellation, exposure repainting, arrow/page scrolling, and repeated
exit/relaunch. Record memory, console recovery and client/server processes.
Try window close during editing and network activity. Label physical PC-98,
IBM emulator and PPC/HP results separately. Physical PC-98 overlay/exit issues
remain open; no special shutdown behaviour has been added to mask them.
