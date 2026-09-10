# Card3D resource reuse — desktop source comparison

[All collections](../README.md) · [Preserved evidence](evidence-index.md) · [Copy/review binding](../godot-ios-retained-34520375602/provenance/publication-review/publication-binding.json) · [Completed focused review](provenance/publication-review/partydeck-gallery-after-3433-card3d-visual-review-v1.json) · [Frozen source mapping](provenance/source-map/source-map.json)

Forty originals form 20 separate baseline/candidate pairs: six portrait, six short landscape, seven enlarged-text/emulated-touch and one resolved public-proof pair. All 20 pairs are byte-identical on Godot 4.7.2.stable.official.ed1daf0bf, OpenGL Compatibility under Xvfb/software Mesa, with unchanged MSAA_2X. The original commands use --path; no PCK was executed. Baseline is the frozen c65e264 renderer source; the candidate changes two of 155 source files through patch `a904d39cb259cae75085001f4733a0d7ee49cd1f2693f8c723ae914541c9b484`. Later integration/export is a separate identity.

Assets previously viewed two selected-hand candidate originals: portrait shows upright ranks, selected first/last borders/checks, Hide hand and Play 2; the scrolled enlarged-text frame shows the lower card strip, selected hand-choice buttons and Play 2. These prior observations are attributed to assets. Thirty-six other identities match reviewed published bytes; the two public-proof originals remain explicitly unviewed. No image was reopened for publication. The source map keeps its original actually_viewed flags unchanged; publication byte-match provenance is separate.

Both variants pass the four original desktop scene scenarios. Owner validation separately reports 560 numbered assertions: 306 redraw, 216 terminal-return and 38 resource sharing/lifetime. Independent review_game checked source and JSON/pairs without media viewing. These recorded frames do not prove native latency, shader-compilation reduction, accessibility, gameplay or native qualification. Foreground/resume refers to desktop checker commands; enlarged dragging uses emulated touch. Per-image timestamps remain null; execution-receipt timestamps are separate. The generic round-ended/01-concealed.png filename is captioned Resolved round with public proof.

[All 20 separate baseline/candidate pairs](pairs.md) · [Mapped source and validation references](source-references.md)

| Collection | Original PNGs | Original outcome and scope |
| --- | ---: | --- |
| [Card3D baseline — desktop source run](baseline/README.md) | 20 | All four recorded scene scenarios pass; exact paired frames match. Native qualification is not established. |
| [Card3D candidate — desktop source run](candidate/README.md) | 20 | All four recorded scene scenarios pass; exact paired frames match. Native qualification is not established. |
