# Resource-failure recovery checks

`tests/test_browser_failures.py` compiles the actual browser entry-point, navigation, save, parser, HTTP, storage and image code with test-only display and fault adapters. It complements the lower-level allocation/cache tests and native QEMU harnesses. It does not run the event loop, BIOS code or 16-bit allocator.

The ten host cases cover:

- Malformed or incomplete HTTP responses, truncated chunked bodies and refused connections: preserve the rendered document, current URL, links and history; subsequent navigation and Back work.
- Cache creation, stream creation, write, flush and rewind failure: preserve the old page and allow a retry.
- First-document allocation failures: show the memory error and allow the next load to succeed.
- All five transparent-image allocation stages (URL cache, compressed data, pixels, opacity and decoder workspace): report a memory error, allow retry, and release tracked allocations.
- Empty, malformed and truncated image documents: leave usable navigation and explicit status text.
- Download short writes and EINTR: complete the exact payload. Partial writes followed by ENOSPC, zero writes, close failure, source-cache read failure and cancellation: remove the incomplete output and keep the save dialog usable.
- Unwritable destinations and existing files: do not overwrite bytes; cancelling the save returns to working navigation.
- Cleanup deletion failure: preserve the actual error state and report that the incomplete file remains. Earlier code incorrectly claimed removal even when `unlink` failed.

Each case resets the browser and checks that the tracked far-storage and GIF allocations return to zero. The test-only shims inject failures into production call sites; they do not replace the browser state machines. Host libc/stdio allocations and OS descriptor internals are outside this allocation tracker.

Run:

```sh
python3 -m unittest discover -s tests -p 'test_browser_failures.py' -v
```

These checks establish recovery logic under simulated faults, not physical disk behavior, native low-memory availability, timing or full resource-exhaustion coverage. Native disk-full, download, navigation and image QA remain separate evidence. Complete HTTP error pages, including a valid 404 body, are documents the browser may display; they are not treated as failed transfers by this suite.
