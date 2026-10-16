# Public-beta preparation

ELKSWeb 0.1 is being prepared for public beta on the strength of scoped native QA, independent visual review and owner-confirmed runs on two HP 200LX systems. The repository and release draft remain private until owner approval. Separate runtime/source/test-image packages carry checksum sidecars and internal manifests. The exact-0.1 86Box cold-boot exit anomaly remains open; successful normal-shell exit checks and earlier screenshots do not establish its cause.

## Preparation completed in build005

- Text-mode display selection before graphics, explicit CLI modes, unavailable-mode handling and clean console restoration.
- Local-file history identity with native local → HTTP → Back → Forward regression checks.
- Live FrogFind mirror search/image/article checks plus separately attributed local and fixed HTTP fixtures.
- A fresh native toolchain/system/application build, static ISA and memory checks, native functional/error-recovery QA, and independent visual review.

The 0.1 help/logo refresh also passes dedicated default-page QEMU QA in all three modes, including the local help anchor, scrolling, inversion and readable console return. This asset-only check does not replace the earlier functional suite.

The exact final candidate and checkpoint decision are recorded in [STATUS.md](STATUS.md). The owner confirms exact 0.1 runs on the standard HP and DS HP, with smoother scrolling reported on the standard HP. Independent physical graphics capture, broader hardware coverage and controlled performance measurements remain follow-up work. Public visibility and release publication still require the owner's approval.

## Version 0.1 distribution scope

The normal runtime package contains the executable, default help HTML, original GIF logo and required notices. Corresponding source is supplied separately; the QEMU test image and attributed website fixtures are optional. Project-specific `webfrog`/`webnews` launchers are excluded from normal installation. GIF rendering remains supported; JPEG/PNG dimensions are recognized for layout, and JPEG pixel decoding is explicitly outside 0.1 scope.

## Release gates

For the first public beta, speed and responsiveness are explicitly excluded from the release decision, per the project owner on 16 October 2026. Slow loads, redraw delays and delayed input/cancellation must be disclosed as known limitations. Performance improvements and further timing measurements are follow-up work, not prerequisites. Functional correctness, compatibility, resource-failure recovery and build/install validation remain required.

- Native C build with the ELKS IA16 toolchain; executable code and near-data budgets pass; static instruction audit rejects post-8086 instructions.
- Actual ELKS/QEMU startup, display selection, navigation, image rendering, forms, cancellation when input is polled and clean exit pass. Cancellation latency is not a first-beta gate. QEMU does not certify 8088 timing.
- An 8088 emulator run demonstrates successful navigation on the local fixture and live lightweight sites, without a latency threshold. Publish available load-time observations and limitations; no claim of physical HP compatibility without hardware tests.
- Independent visual and functional comparison with pinned DOS MicroWeb on fixed local content, with defects and preferences recorded honestly. Pixel identity is not a requirement for an original font, but legibility, geometry, images and controls must be reviewed.
- A clean-checkout build/install recipe, candidate binary/image checksums, source provenance, complete licenses and documented networking setup accompany release artifacts.
- Known limitations, supported display modes, memory requirements and recovery steps are visible in the README and release notes.

## Checkpoints

At the next hourly checkpoint, finish the current build and report its actual 68k.news screenshot, functional results, comparison votes and unresolved blockers. Wait for user approval before the next iteration, as requested. Do not publish a discussion reply or change repository visibility as part of an intermediate checkpoint.

### Current final-QA hold

The exact 0.1 8088 follow-up found an unresolved exit anomaly in its first welcome-page run. A narrower local-FrogFind retry exited and logged in successfully; 640 KB QEMU also passed exit and a shell command. After host unlock, a repeat launched from the normal shell passed welcome, PageDown, Escape and `pwd` returning `/root`. This is narrower than the original cold-boot autorun sequence; that failure remains unexplained. Exact-version live 86Box captures remain pending. See [8088 validation](8088-VALIDATION.md). Public release readiness is not signed off while this investigation is incomplete.
