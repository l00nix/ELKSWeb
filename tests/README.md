# Browser comparison harness

This harness executes the actual DOS MicroWeb reference and an independently built native ELKS candidate. Fixtures and harness code are independent of MicroWeb source/assets. MicroWeb's binary and data remain isolated inside its upstream DOS reference floppy.

Requirements: Python 3 standard library and a host C compiler (`cc`) for core regression tests; QEMU system i386, mtools `mcopy`, an available localhost port 18786, and upstream MicroWeb's FreeDOS 720K image. No Pillow, GUI automation, DOSBox or HP hardware access is required.

From the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/parity.py --output qa/reference-NEW
python3 tests/parity.py --candidate tests/candidate.example.json --output qa/comparison-NEW
```

Output directories must be new. Reference-only runs exit **2**, explicitly indicating `candidate_pending`; failed prerequisites/scenarios/comparisons exit **1**. Exit **0** means only measured fixture parity passed. `release_pass` remains false because ISA, memory, timing and hardware gates are outside this harness.

## Candidate integration

The example manifest expects `build/elksweb.img`, a FAT floppy image with an autorun startup script that reads `/root/qaurl` and executes `/bin/elksweb "$url"` after networking starts. ELKS `ne0` must use IRQ 3, I/O port 0x300. Its local file loader must accept `/root/local.htm` (lowercase is significant to ELKS FAT lookup). Every scenario copies the candidate image to a temporary directory, writes its URL file and identical local HTML using `mcopy`, then boots with QEMU snapshot mode. Original images are never edited.

Manifest image paths resolve relative to the manifest. Arguments can contain `{image}`, `{qmp}`, `{url}`, `{port}`, `{case}`, `{fixture_dir}` and `{output}`. Custom launcher scripts may be supplied in `argv` for other image formats, provided they expose the QMP socket and exit when their QEMU exits. Without `image`, the manifest controls its own isolated setup. QMP must be enabled with the provided socket, graphics must be 640x200 CGA, and startup must open the requested URL automatically. CPU is deliberately marked 486, never misrepresented as 8088.

## What is measured

- Local document and Tab focus.
- HTTP page with text styles/entities, links, list, table, a real 16x16 GIF checker, form, and long scroll area.
- Tab, Home, End, Ctrl+L, link activation, GET form submission, F2 inversion, F3 chrome visibility, and F5 reload.
- Absolute redirect, 404 page, and relative redirect. The pinned MicroWeb baseline renders an `Invalid protocol` error for relative Location. That observed baseline defect is preserved as its own scenario; it is not evidence of standards compliance.
- Server request method/path/status/body hash, raw QMP PPM captures, normalized PNGs, immutable fixture hashes and QEMU arguments/version.
- Candidate comparison requires exact request trace equality and pixel equality across every recorded state. No dynamic region is silently masked, no geometry is rescaled, and every differing pixel counts as a failure.
- Extended scenarios cover POST text editing and checkbox toggling, chunked framing, premature EOF, malformed status, redirect loops, a72KiB resource page and actual configured HTTP proxy routing. The proxy case writes `/root/qaproxy`; candidate startup must export its nonempty value as `HTTP_PROXY`, or unset it when empty.

Normalization accepts 640x200 unchanged or proves every adjacent row in 640x400 is identical before removing CGA scanline doubling. Unexpected dimensions or unequal row pairs fail. Font, clipping, focus and scrollbar differences therefore remain visible.

`comparison/*-diff.png` marks differing pixels red. `*-blind.png` randomly places the two captures left/right with a grey gutter. Give only these anonymous pair images to the independent reviewer, record preference and concrete defects, then reveal `blind-key.json`. Keep the key and filenames identifying lanes away from that reviewer until their assessment is saved. Random placement is independent per state; no claim of a completed blind review is made merely by generating pairs.

## Limits and failure discipline

Successful HTTP requests do not establish correct rendering. Successful capture does not establish that local startup reached the browser: inspect baseline evidence and pixel comparisons. Fixed settle delays make the lane reproducible on this machine, but a slow candidate may need a longer explicit `--settle` or `--boot-timeout`; do not hide transient rendering defects by choosing flattering captures. Blink phases may produce real pixel mismatches which must be documented before any proposed masking change.

This is an initial deterministic corpus, not complete browser coverage. Editing every form control, exhaustive malformed/chunked/truncated responses, slow/disconnecting servers, complete proxy behavior, measured low-memory recovery, large/animated/interlaced GIFs, history/drag/mouse interactions and exhaustive HTML remain additional gates. Fixed-window captures of a stalled or partially parsed reference page do not prove completion. QEMU does not validate8088 opcodes/timing or Hornet/HP peripherals. A true8088 execution lane, compiled binary ISA audit, memory/stack measurements and physical HP tests are required independently. No HP serial port is opened by this harness.

Every owned QEMU process is quit and waited for on completion, terminated on exceptions, and killed only if its own termination times out. HTTP server is localhost-only and shuts down. The reference may make additional network requests only as directed by the deterministic fixtures, all hosted on the local machine.

## Actual C core regression and sanitizer tests

`test_core_regression.py` compiles the real C parser, URL, HTTP and source-memory implementations with actual font metrics into a temporary host library. Tests cover bounded buffers, malformed headers/chunks, POST/307 behavior, proxy request targets, forms, nested layout, deterministic minimized fuzz regressions, strict IPv4 classification,40K/59999/60000byte transfers and source-storage lifecycle. Graphics are stubbed only for these core tests. The native ELF/QEMU lane remains necessary because a host compiler does not emulate16-bit arithmetic or far-pointer access.

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/run_sanitizer.py --output qa/sanitizer-NEW
```

Sanitizer fuzzing uses seed0x01868088 and10,000 bounded HTML/URL iterations plus the explicit16-bit table-position accumulation regression. It compiles actual parser/URL/font code under ASan+UBSan and saves source hashes, command and failure input. macOS LeakSanitizer is unavailable and is explicitly not claimed.

## Live sites

`live_qa.py` separately loads actual `http://frogfind.com/` and `http://68k.news/` in DOS MicroWeb and native ELKSWeb through QEMU networking. It saves bounded early/final screenshots, raw network captures, URLs/timestamps and reviewed errors. It uses no fixture substitutions and no HTTP proxy. FrogFind timeout skips only that run; the next invocation always retries. Reference binaries are not bundled; supply `--reference-image /path/to/freedos.boot.disk.720K.img`. Live changing content never enters deterministic pixel comparisons.

## Control and text behavior inventory

Additional actual-reference cases cover `form_inventory`, `field_limits`, `radio_action`, `textarea_action`, `select_action`, `anchors`, `entities_link`, and `entities_form`. These preserve observed MicroWeb behavior, including unsupported or surprising behavior. They do not assume HTML standards compliance. The `embedded_url` regression checks relative links whose query contains `https://`; `typography` isolates centered/small text and list styling.

`test_allocation_failure.py` injects failures only into a test compilation of the real memory implementation: first/second legacy source allocation, document/URL allocation, private cache creation, write, flush, seek, read, and recovery. Tests check explicit errors and ensure failed cache seeks cannot expose stale bytes. `test_image_integration.py` links the actual HTML/HTTP/GIF/image-cache implementations, verifies source preservation through image loading/reflow and successful/failed duplicate resource caching.

`interaction_qa.py --relaunch` requires the generic QA image's documented empty root password; it restores text mode, logs in, launches the browser again, checks an exact request, and captures the second exit to a shell prompt. It never contacts HP hardware.

## Field encoding and bounded input

`field_encoding_qa.py` exercises native UTF-8 cursor movement, insertion, Delete/Backspace, password masking, and legacy/meta-charset submissions. Controls use canonical UTF-8 internally while serialization retains each control's original encoding. The value buffer stores at most **79 UTF-8 bytes**, not 79 Unicode characters; complete code points are retained at that boundary. Names have a separate31-byte limit. ASCII transliteration makes unsupported glyphs readable but does not claim faithful accented glyph rendering. Untouched legacy values must preserve their original wire bytes, percent-encoded safely.

`candidate_controls_qa.py --grouped-radio` tests the corrected one-tab-stop radio group with arrow selection. The common `radio_action` comparison also requires a real submit request, so focus-only screenshots cannot silently pass it.

For a slower reference parse, pass `--news-timeout 90` to give 68k.news a separate observation window while keeping FrogFind at `--timeout 35`. A final capture that still says parsing is not settled-page evidence.

Framebuffer primitives and cursor edge checks:

```sh
python3 -m unittest discover -s platform/tests -p 'test_*.py'
```

The horizontal-line test compares 14,256 clipped CGA byte-buffer cases against an independent pixel model, including odd/even banks and preservation of untouched bits. This is host framebuffer evidence, not an 8088 timing measurement.

## Reference setup

Download the reference image separately from upstream MicroWeb and supply `--reference-image /absolute/path/to/freedos.boot.disk.720K.img` to parity.py or live_qa.py. The optional default is reference/freedos.boot.disk.720K.img. No MicroWeb executable, source, BIOS ROM or captured website HTML is included in this repository. Historical examples require a separately built candidate image.
