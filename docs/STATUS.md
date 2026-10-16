# Private beta-preparation status — 16 October 2026

ELKSWeb remains private and is **not ready for public beta**. The current candidate adds a text-mode display selector, genuine CGA/EGA/VGA monochrome backends and a local-file history fix. Speed and responsiveness are excluded from the first public beta decision by the project owner. Slow loads and delayed input remain documented limitations; clean-build and remaining functional/resource-failure validation are still pending.

## Current candidate

Native build004 uses the original C implementation, the ELKS IA16 toolchain and the 8086 instruction target. The local build records are `build/native-beta-004.log` and `build/isa-audit.json`:

- Browser SHA256: `dbe320a6088ee8f9cba8ac02ff157510989ba2350b71bd803b72fe1ee09a5f85`.
- Test image SHA256: `d7884117a6ba037a4ce28cda76df20b5cec6e5eb00d3730da3b44faaf4f20d02`.
- Code: 64,048 bytes; data: 12,096 bytes; BSS: 38,432 bytes.
- Near memory: 58,720 bytes including the ELKS default 4,096-byte heap and 4,096-byte stack; 6,800 bytes remain before arguments and environment. Far allocations are additional, so these figures are not peak runtime RAM use.
- Static ISA and near-memory budget gates pass. Static disassembly does not prove physical 8088 execution or BIOS compatibility.

Builds, screenshots and detailed QA logs under `build/` and `qa/` are local artifacts, not published release files.

| Check | Current evidence |
| --- | --- |
| Native build004 | IA16 compilation, static ISA and memory gates pass |
| CGA 640×200, EGA 640×350, VGA 640×480 | All three modes, text selector, cancel, invalid argument and console restoration passed native QEMU build004 and independent visual review; all status separators and bottom rows are intact |
| Windows 86Box build004 CGA/EGA/VGA | All three exported menu, natural/half-size GIF fixture and text-restoration sets independently passed review: 640×200 CGA, 640×350 EGA and 640×480 VGA. This is display/function evidence, not live-page timing or physical hardware validation |
| Local → HTTP → Back → Forward | Nine native QEMU history checks pass on build001, including no HTTP request for the restored local file, failed-load recovery, branching and the eight-entry limit |
| FrogFind fixed HTTP and local-file fixtures | Build004 passes all three named request/capture gates across 17 states; exact form query, article navigation and local Back have independent review |
| CGA image appearance | Natural-size striping improved in build003; build004 visibly fixes the nearly empty half-size frog. Fifteen of 17 fixture frames are unchanged from build003; only the two half-size-image states change |
| Host regression suite | 254 tests pass with Pillow available in the bundled Python environment |
| Driver and parser safety checks | Nine driver scenarios pass ASan/UBSan; 10,000 deterministic parser/URL/layout fuzz cases pass ASan/UBSan |
| Current-candidate 8088 timing/navigation | Build004 timing pending. Windows build003 first live 68k.news frame appeared roughly 5–9 minutes after launch; PageDown completed by the next observation, approximately 15 seconds later. These are observation bounds, not exact benchmark results |
| Physical HP 200LX/Hornet or physical graphics adapters | Not tested |
| Clean-checkout build/install | Pending; tested kernel configuration is now retained |

Evidence locations: `qa/display-native-001/`, `qa/display-native-003/`, `qa/display-native-004/`, `qa/86box-beta-001/`, `qa/history-beta-001/`, `qa/frogfind-candidate-003/`, `qa/frogfind-candidate-004/`, `qa/live-beta-004/`, `qa/blind-frog003/`, `qa/blind-frog004/`, `qa/gif-aspect-001/`, `qa/sanitizer-beta-001/`, and `build/display-host-tests/`. Native QEMU uses a 486 CPU; its results do not establish 8088 speed. The independent display review knew the browser identities and was not a blind preference vote. A single display fixture does not exhaustively validate tall-mode scrolling, forms or error handling.

A fresh blind critic reviewed six balanced anonymous content pairs for build003: **four preferred ELKSWeb, one preferred MicroWeb, and one tied**. These are six content states judged by one critic, not six reviewers or functionality scores. Both sides were identically cropped to rows 22–191, excluding browser chrome; full frames were retained untouched. The critic preferred MicroWeb on the image-size comparison because ELKSWeb’s half-size frog was nearly absent. That defect was subsequently fixed in build004 and verified in native captures; the historical vote count remains unchanged and is not release approval. The key was revealed only after the written verdict (`qa/blind-frog003/decoded-outcome.json`).

A second fresh critic reviewed the six balanced content pairs for build004: **five preferred ELKSWeb and one tied; none preferred MicroWeb**. The corrected half-size image no longer produced a blocking visual finding in these views. This is one critic’s judgment of six cropped content states, not six critics, functionality scores or public-beta approval. Fine print remains cramped and crop-cut in the homepage views; the limited packet does not assess browser chrome, live interaction or performance. The written verdict preceded key reveal (`qa/blind-frog004/decoded-outcome.json`); the original build003 verdict is retained.

The display defaults to a text selector; choose a mode and press Enter, or Q and Enter to quit. `-video cga|ega|vga` bypasses it. Packaging defaults to an empty `/root/qavideo`, so an ordinary image opens the selector. Use `ELKSWEB_VIDEO=cga bash toolchain/package-image.sh` for unattended CGA QA. Unknown or unsupported adapters are rejected conservatively; EGA needs a color display and at least 128 KB video RAM. EGA image aspect is approximate, and images remain limited to 200 displayed rows in every mode.

## Sites and fixed fixtures

Live FrogFind QA uses the supplied `http://frogfind.8088retro.com/` mirror. Build004 fetched the actual mirror homepage and GIF and rendered the first 68k.news viewport (`qa/live-beta-004/`). Both were visible at the first approximately 10-second capture and unchanged at the final capture. These observations are not exact load-time measurements or 8088 benchmarks. Live search submission, article activation and footer navigation were not exercised in this run. The original `frogfind.com` is skipped per user instruction; no current upstream availability claim is made.

Repeatable examples live in [tests/fixtures/frogfind](../tests/fixtures/frogfind/README.txt), with source attribution, captured homepage and unchanged GIF retained. Use guest `/root/frog/index.htm` for local-file sample navigation, or host-served `http://10.0.2.2:18787/http.htm` for the fixed search-form example. These sample results are not a substitute for a live-site result. See [BUILDING.md](BUILDING.md) for setup.

## Historical 8088 run

The earlier Windows 86Box run used Intel 8088 at 4.77 MHz, 640 KB RAM and CGA. It booted ELKS, displayed the local welcome page, rendered live 68k.news through the footer, scrolled and exited. Performance was unacceptable: approximately eight minutes to the first live-page frame and further minutes before queued input took effect. Local-file Back navigation failed by rebasing the saved path onto the HTTP origin. That history defect is fixed in the current source and has native QEMU coverage; the old timing is **not** a current-candidate measurement.

Historical identities:

- Browser SHA256: `1089c3198f235ede1adb6ae6e5cdb19be7b97033001221946a48268484f3b224`.
- Original image SHA256: `2dced9f6a546fb73d0829dcdeca191cc39c514e7f4093111b8e74d2f6c0d375d`.
- 86Box image after bootopts-only adaptation, before guest writes: `f58fdb29fb13b91c09996073608ecefe3373caf901bfd18992d7e4cfb257ddd0`.
- Code: 63,216 bytes; data: 11,744 bytes; BSS: 37,920 bytes.

The README now leads with the newer build003 Windows CGA live68k capture and links build004 QEMU news/mirror captures. Its separately linked older scrolled/footer images remain historical. The earlier run’s approximate timings were observations, not controlled benchmarks; no same-machine DOS MicroWeb timing or fresh blind comparison accompanied that older run.

## Before a public beta

Complete remaining functional and visual checks; repeat resource-failure QA; validate a clean build/install workflow; and publish a scoped compatibility matrix. Speed, redraw/input latency and delayed cancellation are accepted first-beta limitations, not release blockers. Further timing measurements and responsiveness improvements are deferred follow-up work; preserve existing observations in release notes. The tested [kernel configuration](config/elks-generic.config) is preserved, but a reproducible clean build is still unverified. No full MicroWeb parity, physical hardware certification or public release is claimed.

The earlier source-package manifest and [screenshot checksums](candidate-provenance.json) describe the historical candidate, not the modified build004 sources. That package previously passed 224 core tests, five framebuffer tests, 13 font tests, 24 GIF cases with truncations/1,000 mutations, and 16 dimension fixtures with prefixes/5,000 random inputs. Preserve those records as historical evidence; they do not replace current-candidate verification.

The recorded ELKS base commit is provenance information, not proof of a clean builder: the actual builder directory has no Git metadata (`qa/build004-builder-state.txt`). Its local modifications cannot be established through a Git diff. Rebuilding the committed browser and retained kernel configuration against a fresh checkout is still required.

Exported 86Box configurations independently verify an IBM XT (1986), Intel 8088 selected at 4.772728 MHz, 640 KB and dynamic recompilation disabled for the current Windows mode tests. Some guest boot captures report CPU index 2, identified in the kernel mapping as NEC V20; this conflicts with the selected 8088 configuration and remains an unexplained guest-detection discrepancy. It does not justify silently relabeling the configured CPU or claiming physical hardware certification.

The current [build004 provenance manifest](candidate-build004.json) records exact source, binary, image and screenshot identities; all 26 listed source files matched during independent review. This improves traceability but does not resolve the missing ELKS-builder Git metadata or replace a clean rebuild.
