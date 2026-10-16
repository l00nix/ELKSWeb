# First-beta testing checklist

This checklist defines what testers should report; it does not assert that a release has passed. The repository remains private until the owner approves publication. See [STATUS.md](STATUS.md) for the tested candidate and outstanding gates, and [BUILDING.md](BUILDING.md) for installation and networking.

Speed and responsiveness are excluded from the first-beta release decision. Record slow loads, redraws and delayed input as observations. Functional failures—incorrect results, crashes, corrupt downloads, lost navigation state or a console that cannot be restored—remain defects. A delayed response alone is not evidence that an action failed.

## Record the environment

Include the browser commit and executable SHA256, ELKS version/configuration, emulator version or physical machine, selected CPU, conventional RAM, display adapter/video RAM, chosen resolution and network configuration. State whether the page is live, a fixed HTTP fixture or a local file. QEMU integration tests do not establish 8088 execution or timing. The owner has confirmed the exact 0.1 binary runs on the standard HP 200LX and DS HP 200LX, with smoother scrolling reported on the standard HP. This does not replace independent captures or a complete hardware feature matrix; identify your own machine and build precisely.

## Test sequence

1. Start without `-video`. Check that the text selector appears before graphics, lists only available modes, accepts a selection followed by Enter, and supports Q followed by Enter without entering graphics.
2. Exercise each available mode: CGA 640×200, color EGA 640×350 with at least 128 KB video RAM, and VGA 640×480. All browser output is monochrome. Check the address field, page, scrollbar and bottom status row; exit with Escape and verify the text console is usable.
3. Launch without a URL and check the default HTML help page and original GIF logo. If testing offline website fixtures, install the optional fixture bundle as described in BUILDING and open `/root/frog/index.htm`. Follow the sample results and article links, then use Back and Forward. These sample pages require no Internet access. Open `images.htm` and inspect both natural-size and reduced GIFs, inversion and scrolling.
4. Serve the fixed HTTP fixture and open `http://10.0.2.2:18787/http.htm` from QEMU. Submit its sample form, follow the result, and navigate Back. Keep this evidence separate from live search.
5. Open `http://frogfind.8088retro.com/`, inspect its frog image, search for `elks linux`, open a result and return. Record the actual destination and any server error; live-site availability is an external dependency.
6. Open `http://68k.news/`, capture the first viewport, scroll, follow an article and return. Capture the resulting article or the exact error. A successful homepage load alone does not demonstrate article navigation.
7. Exercise text fields, checkbox/radio/select controls, keyboard focus, relative links, anchors, reload and history branching using the supplied fixtures. If testing a mouse, record its protocol/device and test clicks separately from keyboard actions.
8. Download a known binary into a disposable writable directory and compare its bytes or checksum. Attempt an existing filename and an unwritable destination. On a disposable full disk, verify that failed saving reports failure, handles partial files accurately and allows a later retry. Never fill a real system disk for this test.
9. Test a refused connection or deliberately truncated local HTTP response, then load a valid page. Check that the previous usable page/history survives a failed navigation. Cancellation must behave correctly when input is polled; cancellation latency is not a first-beta gate.

The normal runtime package contains the executable, help HTML, original GIF logo and notices; website fixtures and QEMU images are optional test artifacts. `webfrog` and `webnews` are project-specific helpers, not normal-package commands. GIF pixels are supported; JPEG/PNG dimensions alone are recognized, and JPEG decoding is outside the 0.1 test/release scope.

The fixed fixture instructions and licensing are in [tests/fixtures/frogfind/README.txt](../tests/fixtures/frogfind/README.txt). The automated suite provides request traces and failure injection beyond this manual checklist; see [tests/README.md](../tests/README.md).

When switching from an HTTP page to a local file through the address field, use an explicit URL such as `file:/root/frog/index.htm`. A bare `/root/frog/index.htm` entered while on an HTTP page is a path on that website. The same bare path passed at browser startup is local because there is no HTTP base.

## Report format

Provide the environment, starting page, exact actions, expected result, observed result and whether retrying recovers. Attach an unedited emulator framebuffer screenshot and relevant request or serial logs when available. Remove credentials and private page contents before sharing. Distinguish a reproducible browser defect from a live site's response or outage.

MicroWeb comparisons use a separately obtained, pinned DOS reference and identical fixed content. Report visual preferences separately from functional pass/fail results. A preference vote is not proof of complete parity or release approval.
