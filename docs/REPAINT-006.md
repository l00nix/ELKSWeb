# Repaint correction after HP 200LX testing

The owner confirmed build005 starts and runs on the physical HP 200LX, then reported that the entire application frame is erased and rebuilt on every refresh. Inspection confirmed that `draw()` called `ew_clear()` unconditionally, including during network progress and address editing.

The new candidate separates page, address, status, title and static-frame damage. Scrolling and page focus changes preserve the header and frame borders. Network progress and hover update the status area; typing in the address updates its interior. Full-screen repaint remains necessary on initial display, inversion and toolbar visibility changes. The page still repaints its viewport for scrolling/control changes; this is not scroll blitting, double buffering or general per-widget damage tracking.

Drawing primitives now honor a content clip region. Text, rules, boxes, controls and images crossing a viewport edge cannot overwrite the retained frame. Full-screen clipping is restored before chrome and software-cursor drawing. Review also corrected stale address state on failed history navigation from the address editor and title invalidation after image-triggered reparsing.

## Validation

- 279 host tests pass, including 13 new repaint tests against actual browser/parser/font/image code. The new tests count writes even when the pixel value is unchanged; an identical final screenshot alone cannot prove absence of flicker.
- Those 13 tests produce 21 failing subtest reports against the previous renderer and pass against the corrected renderer. They cover scrolling/focus, status/hover, address/caret, viewport edges, downloads, failed navigation, mouse Back from the editor, inversion and hiding the bars.
- Actual display-driver tests pass across CGA/EGA/VGA, including randomized content clipping against a separate pixel model. Five separate primitive/cursor tests pass.
- Final QEMU runs pass CGA/EGA/VGA selection and console restoration, menu cancellation and invalid-option handling. All three local FrogFind screenshots are pixel-identical to build005. An independent reviewer found no visual regression across 18 candidate frames, including live FrogFind mirror and 68k.news. News scrolling, focus and Back appear coherent; the selected article still returns the upstream extraction-error page. No new preference vote was taken.
- Native ELKS IA16 build succeeds with `-march=i8086`, no compiler warnings, and a passing static audit of 25,823 instructions.
- Text: 64,448 bytes (+384); data: 12,128; BSS: 38,448 (+16). Near allocation including default heap/stack: 58,768 bytes before arguments/environment, leaving 6,752 bytes. Code-segment headroom is 1,088 bytes.

Executable SHA256: `70450a34d4a551631689a606fdeef688471094ff2d853db81934b1569076e925`.

The application was rebuilt against the prepared ELKS toolchain from clean-build001. This is not another fresh compiler/system bootstrap. The disposable QEMU image starts from clean-build005 with the new executable installed; its recorded hash and complete source checksums are in local `qa/repaint-006/manifest.json`.

Runtime and visual review results are retained under `qa/repaint-006/`. The complete previous beta comparison suite was not repeated for this focused fix, and prior blind comparison votes are not new votes for this candidate. After the owner reopened the serial console, this correction was installed as `/root/elksweb` on the HP. Its MD5 (`17397fb32aec17898cdd7ac342c49aa6`) matches the tested host binary; prior build005 was preserved and verified as `/root/elksweb.005`. Offline pages and launchers are unchanged, and the serial shell was exited for local testing. Physical repaint validation and Windows 86Box testing of this correction remain pending. Publication remains unapproved.

The display menu continues to list only modes reported by the adapter BIOS. CGA-only on the HP 200LX is expected; EGA/VGA choices remain available on supporting configurations.
