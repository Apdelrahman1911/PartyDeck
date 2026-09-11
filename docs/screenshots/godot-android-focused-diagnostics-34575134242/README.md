# Android 3D scroll diagnostics — run 34575134242

**Both selected result JSONs report failed half-page overlap.** This diagnostic collection preserves four original PNG members from the Debug and optimized test-signed variants at font scale 2.0, source `094ea9aee48d927173f3afa659a0bf35101d1b3d`, attempt 1. All four were directly viewed once at original detail by `/root/pixel_d1_split`.

| Selected variant | Original positions | Final content displacement | Half-page limit | Result |
| --- | --- | ---: | ---: | --- |
| [Debug](debug/README.md) | 06 → 07 | 52 logical units | 51.5 | Failed |
| [Optimized test-signed](optimized-test-signed/README.md) | 11 → 12 | 86 logical units | 51.5 | Failed |

The selected PNGs and result JSONs were obtained by **bounded HTTP-range diagnostic extraction**. The retained extraction receipts attribute ZIP CRC checks to the selected members, and the pixel reviewer independently matched the selected PNG/result SHA-256 values. No complete ZIP is retained and no whole-archive hash was verified. **This selection carries no whole-archive, canonical-collection or native acceptance.**

[Capture manifest](manifest.json) · [Original extraction receipt](provenance/extraction/run10-diagnostic-pngs.json) · [Independent direct pixel observations](provenance/review/pixel-observations.json)

The recorded final gestures in both variants run from physical `[476,637]` to `[476,565]` over 600 ms. The Debug origin lies in blank roster space. In the optimized before-image it lies inside a partly clipped Last round review button. The optimized after-image has a bright yellow-green border compatible with hover/pressed styling; **the border does not prove focus**. No native receiver/focus event trace establishes a numerical breakdown of the jumps. The earlier optimized upper-body gesture from `[476,601]` is a different step.

Reviewer’s qualified interpretation: The debug placement supports a timing/inertia explanation without a visible button at the origin. The optimized placement, the clipped history button and inspected follow-focus code support an additional focus-induced scroll contribution. The records contain no native receiver/focus event trace and do not establish an exact numerical decomposition of either jump.

Native chrome and Show hand are visible in all four selections. Full current-claim text, Play, private rank text and card faces are outside these selected views. The images do not establish full public-context coverage or continuous privacy. Recorded geometry and sequential screenshot/UI captures retain their separate scope.

Only these four PNGs are selected for this addition. The two unmodified result JSONs also reference other captures, XML and artifacts; those references do not add images, extracted files or review credit to this selection. Candidate-fix review, focused host verification and any later native run remain separate. No new view, download, archive audit or native test was performed to prepare this gallery.
