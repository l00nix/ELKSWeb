# Public-beta preparation

The repository remains private during preparation. A candidate is not beta-ready merely because a screenshot or host test passes.

## Current work

- Add text-mode display selection before browser graphics, with explicit CLI selection for unattended testing. Exercise every advertised mode and unsupported-adapter handling.
- Fix local-file history identity and verify local → HTTP → Back → Forward in the native browser.
- Reduce avoidable URL comparisons, cache seeks and image-free document reparsing; measure the result on the 8088 lane before claiming a performance improvement.
- Use http://frogfind.8088retro.com/ for live FrogFind QA. Preserve a separately labelled local homepage/image/form fixture for repeatable offline tests.

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
