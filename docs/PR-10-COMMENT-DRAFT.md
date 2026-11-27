Thanks for the image-loading optimization. I’ve integrated an amended version into `dev/0.6.1-performance` in commit `1bdfbb1`.

- Sized HTTP images and local image files can load directly into far memory, avoiding the temporary-file round trip. Chunked and unknown-length bodies retain the disk path.
- I found and reproduced a blocking crash: an image response with HTTP 204 attempted to terminate a null output buffer. Empty responses now fail safely, and a regression test verifies that the next image still loads.
- If the direct allocation fails, the browser now falls back to disk and retries allocation after closing the connection. This preserves the opportunity to load an image with the RAM released by the connection. Persistent allocation failure still reports the memory problem and cleans up.
- DNS reuse is limited to a document load and its image requests, with a fresh lookup on reload. A failed cached connection gets one fresh-resolution retry. I’m not accepting the process-lifetime cache as written.
- Local-file reads are bounded by the allocated buffer, including when a file grows after its size was checked.

The combined 394 host tests and both native 8086 audits pass, including new DNS-lifetime and allocation-recovery coverage. Native emulator runs also pass GIF loading, HTTP 204 recovery, keyboard, scrolling and exit checks in both browsers. The PR’s measured gain was about 2% on its six-GIF fixture; DNS savings were not measured. PPC/HP timing and low-memory validation remain pending, so this is integrated for development testing rather than promoted to a release.

Thanks, Alex
