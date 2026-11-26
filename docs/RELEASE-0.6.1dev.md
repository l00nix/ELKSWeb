# ELKSWeb / WebNX 0.6.1dev

Development candidate following ghaerr's PR #5 request for control-key alternatives
and Takahiro Yamada's report that the PC-98 keyboard driver lacks function keys.

Both clients retain Ctrl-L for address editing. Ctrl-R reloads, Ctrl-D redraws
without a fetch or image decode, Ctrl-V toggles inversion/theme, Ctrl-T toggles
browser bars, and Ctrl-G opens the image-free offline /lib/web/keys.htm page.
Ctrl-B/F navigate history; Ctrl-N/W select the next/previous link or control.
Existing F2/F3/F5/F6, Tab/Shift-Tab, editing, mouse and scrolling controls remain.

Ctrl-I and Ctrl-H cannot be used as independent shortcuts: they are Tab and
Backspace. Ctrl-A is reserved by the ELKS Nano-X server for quit, Ctrl-P may be
Print, and Ctrl-S/Q may be terminal flow control. No new mappings use them.
The Nano-X adapter accepts both ASCII control bytes and letters with a Ctrl
modifier; direct raw and HP cooked input keep their existing decoding paths.

Navigation shortcuts follow existing modal behaviour: finish/cancel address
editing, a download prompt or an open list before reload/help/history. Ctrl-D
preserves edits. Navigation from a form field may discard its unsaved entries.
Missing help reports an error without replacing the current document.

Install with `ept install -n elksweb`, using REPO=http://ept.8088retro.com.
Both `elksweb --version` and `webnx --version` should report 0.6.1dev.
One package owns both executables and /lib/web/ assets. Existing split-package
users must follow docs/NANOX-EXPERIMENT.md migration instructions first.
General remains 0.6; 0.5 remains available for comparison.

The HP/PPC console, cooked-key, mouse, GIF workspace, scrolling, download and
first-load image repaint fixes are retained. This build does not change the
Nano-X server or claim to fix the PPC's slow/corrupted Nano-X drawing. Physical
PPC and PC-98 verification of the new shortcuts remains required.
