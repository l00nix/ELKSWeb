# ELKSWeb 0.5dev integration

This branch starts from released **0.4**, then merges @astrobleem's
[Tandy/PCjr contribution](https://github.com/l00nix/ELKSWeb/issues/2) through
`6dbd3b29639efeae621255f60b344a18be5f9a85`. The contributor's four original commits
remain in history. This is an integration branch, not a released hardware build.

## Included and preserved

- Native 320x200 16-colour Tandy/PCjr rendering without Nano-X, colour GIFs,
  basic HTML colours, themes, narrow-screen layout and keyboard handling.
- Colour image pixel-cache limit and smaller-resolution allocation retries.
  These retries do not yet apply to monochrome GIFs and do not establish a speedup.
- 0.4's `/dev/tty1` keyboard and selector, canonical Backspace handling, console
  restoration, HP cooked keys, mouse support, inversion and inline GIF allocation
  diagnostics. Merge conflicts were resolved to retain these behaviours.
- Medium-model build with separate near/far code segments. Both builders retain
  the 8086 target. The audit disassembles a symbol-stripped copy to avoid symbols
  inside far-jump operands, then matches bytes against the original ELF and both
  text segments in the native executable. The original ELF is retained.
- Colour welcome assets installed by the disposable test-image packager. The
  historical versioned release packagers still target their original versions.

## Requirements and open work

The kernel must support medium-model executables (`CONFIG_EXEC_MMODEL`). Colour
mode additionally requires certified video-memory reservation via `/dev/kmem`
(`MEM_GETTANDY`/`MEM_GETPCJR`); a BIOS mode or machine name alone is insufficient.
No HP/PPC kernel or physical device is changed by this merge.

Before a public 0.5 beta:

- Obtain exact matching kernel/bootloader revisions and installation instructions
  from the contributor; review the reservation ABI and memory ownership together.
- Repeat HP/PPC tests on the exact medium-model build: raw/cooked keys, serial
  mouse, launch/exit, GIFs, navigation, memory pressure and online browsing.
- Measure code, RAM, page-load and GIF costs against 0.4, including failures at
  512 KB and practical operation at 640 KB. Medium model does not add RAM or lift
  the near-data limit. Consider a separate monochrome build if needed.
- Reproduce Tandy/PCjr emulator results with the matching kernels and obtain
  physical tests. The contributor's Tandy 90-key mappings are provisional.
- Exercise colour mode, themes, images, forms, scrolling, transparency, allocation
  failures and console restoration. Host raster tests do not exercise ia16 assembly.
- Prepare a versioned development/runtime packager with colour assets and notices.

The supplied branch does not contain EMS image storage. EGA/VGA remain
monochrome. PMR mouse support is absent. Hardware certification and performance
claims are explicitly deferred until measured.
