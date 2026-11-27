Thanks for this work. I’ve integrated the conditional image-reflow change into `dev/0.6.1-performance` in commit `b8c6b50`.

- Images without explicit dimensions now trigger another layout pass only when a natural size became available. Failed images no longer cause an unnecessary full reparse.
- I’m deferring the table-plan reuse portion. The documented difference near the truncation limit matters on the PPC and HP, and the reported hardware tests did not exercise that optimization. Required reflows still use the complete table-measurement path.
- I added six regression cases covering missing images, explicit and partial dimensions, unsized images inside tables, and a mixture of successful and failed images. They pass within the combined 394-test suite.
- The combined native builds also pass emulator checks for first-load GIF drawing, redraw, scrolling, keyboard shortcuts and exit, using direct VGA and the PPC-compatible CGA Nano-X server.
- The reported 74.55 → 43.76 second improvement applies to the unsized-404 fixture. I haven’t independently reproduced those timings, and I wouldn’t describe this as a general page-loading speedup.

I wouldn’t merge this PR as written. I’d take the reflow check now and revisit table-plan reuse once it preserves layout under truncation and has hardware evidence for that path. Physical PPC/HP verification of the combined development build is still pending.

Thanks, Alex
