# MicroWeb comparison scope

MicroWeb is a separately obtained DOS reference, not an implementation dependency. The reference image SHA256 is `302b6b6b3f0a4b10e706184350b296f86363e88e8b2faaeac3fad2d4bba4e62a`. ELKSWeb uses original C code, the ELKS network stack and direct monochrome graphics. It does not claim complete behavior or pixel identity.

## Functional comparison, 16 October 2026

Actual DOS and native ELKS build004 were run against identical fixed content. Request traces, screenshots and assertions are retained locally under `qa/beta-gates-005/`; `functional-comparison.json` records the matching evidence paths. This is an identity-visible functional assessment, not a preference vote.

| Tested action | Result |
| --- | --- |
| FrogFind fixed search and article | Both submit the required query and reach the fixture article; local-file Back and direct GIF navigation also have captured evidence |
| Edited POST with unchecked checkbox | Both send the exact body `q=xseed`, omitting the unchecked field |
| Field `maxlength` fixture | Both send `text=abcseed&password=secretxyz`, exceeding the fixture's declared limits; this is a shared limitation |
| Select control | ELKSWeb submits the option value `one`; reference submits its displayed label `One` |
| Textarea | ELKSWeb retains initial text and newline while editing; reference submits only the inserted `x` |
| Entity-containing form value | ELKSWeb decodes and percent-encodes the value; the reference sends different, malformed field syntax |
| Relative HTTP redirect | ELKSWeb resolves the destination; reference reports an invalid protocol |
| Chunked body and explicit HTTP proxy | Both render the named fixture responses; this does not test native TLS or HTTPS conversion |

The differences above are deliberate scope disclosures, not exact-parity passes. Correctly handling a value or redirect does not require reproducing a reference defect. Neither browser's result establishes general HTML standards compliance.

Live-site checks on the same day separately reached the FrogFind mirror homepage and GIF, submitted `elks linux`, opened the returned ELKS article, and returned to results in both browsers. On 68k.news, the selected article returned the site's own extraction-error page with HTTP 200 in both browsers. ELKSWeb's settled homepage, scrolling, footer, article navigation and Back passed, but this is not evidence of successful reading of that 68k.news article. Local evidence: `qa/beta-gates-005/live/independent-review.json`. Live results are time-specific and distinct from fixed-fixture assertions.

## Visual reviews

The build004 blind **content-only** review covered six balanced pairs, cropped identically to exclude browser chrome. One fresh reviewer preferred ELKSWeb in five states and tied one. The original frames and written verdict before identity reveal are retained in `qa/blind-frog004/`.

A separate fresh reviewer inspected **16 complete uncropped frames**, covering eight matched FrogFind states, including browser chrome and focus. Browser identities were visible, so this review was **not blind**. Preferences were **ELKSWeb 1, MicroWeb 3, ties 4**. The reviewer found no candidate visual blocker in those states, while slightly preferring MicroWeb's roomier homepage/form spacing. The evidence is `qa/fullframe-beta-005/review.json`.

These are two reviewers assessing different scopes, not interchangeable scores or votes on release approval. Neither review proves runtime behavior, image fidelity on every page, or physical display compatibility. The subsequent source change in commit `4fa4907` affects only a failed-download status message; it is not visible in the reviewed build004 frames.

## Final clean-build regression

The full candidate fixture suite was rerun on clean build005. All 39 cases and eight focused field-encoding cases passed their defined assertions. Against the pinned actual-DOS traces, six of ten overlapping cases match exactly; the four differences are the select, textarea, entity-form and relative-redirect behaviors above. All 17 retained FrogFind content viewports match build004 pixel for pixel in the declared content crop (x0–639, y22–191); full frames remain retained. This carries the prior visual evidence forward as a regression check, not a new preference vote. A separate critic inspected seven final clean-build live news frames and found no visual blocker; the upstream article error remains disclosed.
