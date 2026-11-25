# ELKSWeb and WebNX 0.6

One `elksweb` package contains the direct `/bin/elksweb` browser, the optional
`/bin/webnx` Nano-X client, and shared pages/images under `/lib/web/`.
Both executables report **0.6** and open `/lib/web/welcome.htm` by default,
including in native colour modes. The page shows both logos, common controls,
and the differences between direct-console and Nano-X browsing. Colour tests
are linked from the welcome page. This follows ghaerr's PR #5 guidance.

The Nano-X contribution and WebNX branding are from astrobleem's PRs #5/#6.
The rendering, GIF, HP/PPC and 0.5 performance fixes are retained. This is a
nightly development build, available through EPT nightly; no EMS/kernel support is added.

## First-load image redraw (0.6)

Successful mouse navigation could leave a decoded image behind its placeholder:
the old focus repaint clipped out the pending image update. F2 or F5 made the
image visible. The shared fix preserves the pending image repaint without adding
a full-page redraw. It covers links, linked images and form-submit controls in
ELKSWeb and WebNX.

The user confirmed the frog appears on the first mouse-click load on the physical
PPC with the fixed 0.6.4test1 build promoted here. Regression tests reproduce the
old failure and pass in both compile paths at 200, 350 and 480 pixel heights.
PC-98 verification is still requested; this does not resolve the separate page-cache
report in issue #8 or establish additional low-memory support.

## Form and download fixes (issue #7)

0.6.3dev changed form-field typing, deletion and caret movement to repaint the
focused field band. Astrobleem verified that packaged fix on his CompuADD
386SX/16; QEMU also passed form submission and exit. His physical FrogFind
search encountered a separate page-cache error, so the results page was not
verified in that run.

0.6.4dev applies his [two follow-up patches](https://github.com/l00nix/ELKSWeb/issues/7#issuecomment-7156977194):
filename editing redraws only the download controls, and a successful save
calls `sync()` after closing the file and before showing “File saved”. This
flushes ELKS filesystem buffers. It is not a guarantee against media errors
or device caches, and the ELKS sync interface provides no per-file error result.
Existing write/close failure handling and cancellation are retained.

Both clients share these changes. No kernel or Nano-X server changes are
included. Issue #7 stays open for verification of the packaged 0.6.4dev build;
astrobleem's power-cycle result applies to his own patched build.

## Install and migrate

With networking up and `REPO=http://ept.8088retro.com` in `/etc/ept.cfg`,
a fresh installation needs just:

```sh
ept install -n elksweb
elksweb --version
webnx --version
```

Both version commands should report **0.6**. The main mirror's nightly
catalogue contains the combined **0.6** candidate; `/local` is no longer
required. `-n` selects the nightly catalogue of the configured repository.
The old `/local` address still works for compatibility, including instructions
inside previously published packages. A first-time install, or an upgrade from
0.5 with no separate `webnx`, `webdata` or `elksnx` packages, needs no removals.

Choose `elksweb` for the direct console or `webnx` for Nano-X. Installing both
executables uses disk space; only the one you launch consumes process memory.
A compatible Nano-X server is still a separate system prerequisite, not bundled
with the browser. Stable 0.5 remains unchanged in the general catalogue.

### One-time migration from split nightlies

Close the browsers and back up customized package files before upgrading.
Use `ept list -n` to check which packages are installed. If present, remove
**only the old separate packages before installing the combined package**:

```sh
ept remove webnx
ept remove webdata
```

If the older `elksnx` package is installed, remove it too (`ept remove elksnx`).
Skip commands for packages that are not installed. Then run:

```sh
ept install -n elksweb
elksweb --version
webnx --version
```

Both should report 0.6. Do not remove the old packages after installing
the combined one: older EPT clients retain their file ownership records and
could delete its files. If this happened, remove the remaining old package
records and reinstall `elksweb` using the command above. Do not hand-edit the
EPT database. The `webnx`, `webdata` and `elksnx` packages are no longer listed
in this nightly catalogue; the executable is still named `webnx`.

Earlier direct-only `elksweb` installations upgrade normally. Existing explicit
page paths are retained as compatibility copies of the same common sources:
`/lib/web/welcnx.htm`, `start.htm`, `startnx.htm`, `/lib/elksweb/welcome.htm`,
`/lib/webnx/welcome.htm` and `/lib/elksnx/welcome.htm`. Old colour-page paths also
remain available. These copies use absolute `/lib/web/` asset links. Source
maintainers edit only `share/welcome.htm` and `share/color.htm`; the staging
script generates all compatibility copies. Paths fit FAT 8.3. Personal files
under `/root` are not replaced, and explicit URL/file arguments still work.
Update any old `/bin/elksnx` launch commands to `/bin/webnx`.

A bare launch without any default page prints `ept install -n elksweb` before
initializing graphics. `ept remove elksweb` removes both clients and the bundled
assets. Downgrading to general 0.5 also removes the nightly's Nano-X client and
shared/compatibility assets, restoring the self-contained stable package.

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
exec /bin/webnx /lib/web/welcome.htm
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
IBM emulator and PPC/HP results separately. Takahiro Yamada subsequently
[reported successful 0.6.4dev startup, browsing, mouse links and closing on a
physical PC-9801RX](https://github.com/l00nix/ELKSWeb/pull/5#issuecomment-7167416434),
launching from nxterm after nxstart with XMS enabled and httpd/ftpd stopped.
That validates the reported configuration, not every earlier startup path;
no special shutdown behaviour has been added to mask failures. His FrogFind
photo shows an image placeholder, and download verification remains pending.
