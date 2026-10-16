# Private beta preparation — 16 October 2026

**Later HP feedback:** the owner confirms build005 runs on the physical HP 200LX. A subsequent frame-repaint correction is documented in [REPAINT-006.md](REPAINT-006.md); the build005 qualification record below remains specific to its original binary. The correction has not yet been installed on the HP.

The repository remains private. This iteration closes the scoped functional, visual and resource-recovery checks on build004, fixes an inaccurate failed-download cleanup message, and validates a fresh build of the resulting browser. **The fresh build and scoped final-artifact QEMU gates pass. The final Windows 8088 run also passes its scoped checks. Work is paused for owner review; publication remains unapproved.** Speed and responsiveness are excluded from the first-beta decision, as requested.

## Candidate identity and clean-build gate

Production source is pinned at `4fa4907bff0a5a11d82ec26ce503a255e5d9bf74`. Its only product change after build004 reports when a partial download remains because deletion failed. Later test/document changes do not alter production code. A separate reviewer found no blocking issue in that fix or its test approach.

A fresh Ubuntu 22.04 container successfully built the complete pinned ELKS toolchain and system from ELKS `89d09706f17c123f9e0f5ef7cba2eb6745e8478c`, without reusing the established builder's generated compiler, libc or kernel. The recipe now includes its missing `xxd` prerequisite; no upstream source patch was needed. Image SHA256 is `1e0e9e567fdb7ef782d20616be8517c39da89fbf80030acedad234e1a28d60a1`. See [the clean-build record](CLEAN-BUILD-001.md) for pins, hashes and the retained initial/resumed logs. Independent final-image runtime QA also passed; its [machine-readable review](QA-BUILD005.json) records the exact scope and limitations.

## Functional and recovery evidence

The following QEMU results were rerun on **clean build005**, image SHA256 `1e0e9e567fdb7ef782d20616be8517c39da89fbf80030acedad234e1a28d60a1`. Detailed final-run records are local under `qa/beta-gates-005/clean/`; earlier build004 evidence remains separate. Production code is unchanged since the pinned commit.

| Gate | Current evidence |
| --- | --- |
| Native compilation / instruction and memory limits | Final clean build passes; 25,712 decoded instructions, zero browser compiler warnings |
| Display selector and CGA/EGA/VGA | Clean build005 passes all three modes, cancel, invalid option and console restoration in QEMU; build004 Windows 86Box menu/image/restore sets independently reviewed; clean005 CGA startup/GIF/local navigation/exit also observed |
| History | Nine history checks pass on clean005: local↔HTTP, Back/Forward, branch replacement, failed Back preservation and eight-entry limit |
| Forms, controls and network framing | 39/39 native fixture gates and 8/8 field-encoding cases pass; actual DOS comparison has 6/10 exact request traces and four intentional differences |
| Address, mouse and lifecycle | Address editing, a 316-byte URL, explicit `file:` transition with no HTTP request, Back, reviewed mouse targets, exit and relaunch pass |
| Downloads | Exact binary bytes, existing-file preservation, invalid destination, recovery and real FAT ENOSPC pass; partial output removed after disk-full failure |
| Cancellation | Twelve checks pass, including unchanged prior viewport after parking the cursor outside it, cancellation status and subsequent navigation; no latency threshold |
| Live FrogFind mirror | Both browsers display homepage/GIF, submit `elks linux`, read the returned ELKS article and go Back |
| Live 68k.news | ELKSWeb settled homepage, Page Down, footer, article navigation and Back pass. The tested article returns the site's extraction-error page with HTTP 200 in both browsers; successful reading of that article is not claimed |
| Host recovery | Full suite passed 264 tests after the product fix. Expanded focused recovery suite subsequently passes 12 cases, including cache-error refetch, history allocation failure and embedded-GIF recovery; the full suite was not rerun after these test-only additions |
| Clean build/install and final-artifact runtime | Pass: fresh compiler/libc/kernel/userspace/app/image and final-image QEMU validation; image hash unchanged after isolated tests |
| Physical hardware | HP 200LX/Hornet, physical 8088 and physical display adapters untested |

The failure-injection harness uses actual production navigation/save/parser/network/image code with test-only adapters. It does not prove native far-allocation or physical-disk behavior. Separate native disk-full and recovery checks complement it. See [RESOURCE-FAILURES.md](RESOURCE-FAILURES.md) for precise claims and limits. Local evidence: `qa/resource-host-001/`, `qa/resource-host-002/`, and `qa/fullframe-beta-005/resource-review.json`.

## Visual and functional comparison

The latest blind content review remains **ELKSWeb 5, MicroWeb 0, tie 1** across six cropped pairs, judged by one fresh reviewer. A different fresh reviewer inspected eight full-frame pairs, including chrome and focus, with visible identities: **ELKSWeb 1, MicroWeb 3, ties 4**. Neither found a candidate visual blocker in its specified scope. The full-frame reviewer slightly preferred MicroWeb's roomier homepage/form layout; ELKSWeb is not an across-the-board visual winner.

The clean build matches all 17 retained FrogFind content viewports from build004 exactly in the declared crop; this is regression evidence, not a new blind vote. These are separate assessments with different scopes, not combined votes on release readiness. Static screenshots do not prove functionality. The independent actual-DOS functional run supplies request traces and explicitly records differences in select values, textarea preservation, entity encoding and relative redirects. See [COMPARISON.md](COMPARISON.md). No complete MicroWeb parity is claimed.

## Latest clean-image screenshot

![Build005 actual QEMU framebuffer](screenshots/68k-news-build005-qemu.png)

Captured on 16 October 2026 around 16:44 UTC from the final clean executable. A separate critic reviewed seven full news frames and found no visual blocker. QEMU uses a 486 CPU; this is integration evidence, not 8088 timing evidence.

## Current 8088 evidence

Clean build005 rendered live 68k.news and scrolled to later stories in Windows 86Box configured as Intel 8088 at 4.772728 MHz, 640 KB, CGA, NE2000 8-bit and SLiRP. The complete first viewport was observed approximately eight minutes after launch; this is an observation bound, not a benchmark or a beta blocker.

![Build005 actual Windows 86Box framebuffer](screenshots/68k-news-build005-86box.png)

[Scrolled native framebuffer](screenshots/68k-news-build005-86box-scrolled.png). A separate critic inspected both final native frames and found no visual blocker. Original captures and saved configurations are retained in `qa/86box-beta-001/`. The QEMU integration lane uses a 486 CPU and supplies no 8088 timing evidence. See [8088-VALIDATION.md](8088-VALIDATION.md) for the configured CPU, the guest V20-label discrepancy and its source-level explanation; no physical certification is implied.

## Resource measurements and limits

Build004 browser SHA256: `dbe320a6088ee8f9cba8ac02ff157510989ba2350b71bd803b72fe1ee09a5f85`. Code is 64,048 bytes, data 12,096, BSS 38,432. Near static data plus the default 4,096-byte heap and 4,096-byte stack totals 58,720 bytes, leaving 6,800 before arguments/environment. Far allocations are additional; these are not peak runtime RAM measurements. Code headroom is 1,488 bytes. Final clean-build executable SHA256 is `0c2dad923fd4ad715d1e7a32721976af1b251abc33d334383e4ec77facd14d81`: code 64,064 bytes (1,472 remaining), data 12,128, BSS 38,432; near total 58,752 bytes, leaving 6,768 before arguments/environment. These are static allocation budgets, not measured peak RAM.

All modes are monochrome. EGA needs a color display and at least 128 KB video RAM; its image-aspect correction is approximate. Images retain a 200-row display cap. GIF first-frame rendering is supported; PNG/JPEG pixels, native TLS, CSS and JavaScript are not. Forms have a 79-byte value cap and single-line textarea editing; HTML maxlength/size semantics are incomplete. Large pages remain bounded by fixed source/layout/link limits. Slow loads, redraws and delayed input/cancellation are known limitations.

## Review and publication

The [testing checklist](BETA-TESTING.md), [build instructions](BUILDING.md), source licenses, font provenance and attributed local FrogFind fixtures accompany the repository. No public binary release, visibility change or discussion announcement is authorized by this checkpoint. The final 8088 captures are saved, its VM is paused, and local QA/build/transfer processes have stopped. Wait for the owner's review before continuing. Speed and responsiveness remain excluded from this first-beta decision.

Build005's final source/artifact manifest is [candidate-build005.json](candidate-build005.json). Build004's historical manifest remains [candidate-build004.json](candidate-build004.json). Older build and screenshot records remain historical; neither those records nor this scoped matrix establish universal compatibility.
