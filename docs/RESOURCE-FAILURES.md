# Resource-failure recovery checks

`tests/test_browser_failures.py` compiles the actual browser entry-point, navigation, save, parser, HTTP, storage and image code with test-only display and fault adapters. It complements the lower-level allocation/cache tests and native QEMU harnesses. It does not run the event loop, BIOS code or 16-bit allocator.

The twelve host cases cover:

- Malformed or incomplete HTTP responses, truncated chunked bodies and refused connections: preserve the tested document title, current URL, links and history; subsequent navigation and Back work.
- Cache creation, stream creation, write, flush and rewind failure: preserve the old page and allow a retry.
- First-document allocation failures: show the memory error and allow the next load to succeed.
- All five direct transparent-GIF allocation stages (URL cache, compressed data, pixels, opacity and decoder workspace): report a memory error and allow a fresh load to succeed. This is direct-image navigation, not the embedded-image I/O path.
- Embedded-GIF decoder-pixel allocation failure on an HTML reload: retain surrounding text and the continuation link, remove the temporary image file, and decode the image successfully after navigating away and Back. Embedded-image I/O-failure combinations are not exhaustively injected.
- History-slot allocation failure: display the loaded page and history warning, retain the prior entry without increasing tracked live allocations, allow Back while allocation failure persists, then allow new navigation and Back once memory is available.
- Empty, malformed and truncated image documents: leave usable navigation and explicit status text.
- Download short writes and EINTR: complete the exact payload. Partial writes followed by ENOSPC, zero writes, close failure and cancellation: remove the incomplete output and allow a successful save retry.
- Source-cache read failure while saving: remove the incomplete output and keep the dialog cancellable. The cache error stays sticky even after the injected fault is cleared; another filename in the same dialog still fails safely. Cancel, refetch the same URL, and save succeeds with exact payload bytes. Two observed GET requests establish the fresh fetch.
- Unwritable destinations and existing files: do not overwrite bytes; cancelling the save returns to working navigation.
- Cleanup deletion failure: preserve the actual error state and report that the incomplete file remains. Earlier code incorrectly claimed removal even when `unlink` failed.

After each case, the test resets the browser and checks that tracked far-storage and GIF allocations return to zero. This establishes eventual post-reset cleanup, not an immediate allocation baseline after every failed operation or exhaustive accumulated-session exhaustion recovery. The test-only shims inject failures into production call sites; they do not replace the browser state machines. Host libc/stdio allocations and OS descriptor internals are outside this allocation tracker.

Run:

```sh
python3 -m unittest discover -s tests -p 'test_browser_failures.py' -v
```

These checks establish recovery logic under simulated faults, not physical disk behavior, native low-memory availability, timing or full resource-exhaustion coverage. Native disk-full, download, navigation and image QA remain separate evidence. Complete HTTP error pages, including a valid 404 body, are documents the browser may display; they are not treated as failed transfers by this suite.
