Approved for the tested desktop 3D framing and card clarity. The final exported PCK is `7ec66f903ed41b55bdb4c3d8972de56900c85fe765f1bf7cc81306150c86e9f2`. I independently executed all 492 geometry/input assertions against this PCK under actual Godot 4.7.2 Compatibility/OpenGL (Mesa llvmpipe); all passed with no engine errors. The PCK and review script hashes remained unchanged throughout execution.

The real mesh triangles now fit with visible margins on both sides. The 3D render target covers the physical stage within one pixel, including fractional density. The portrait density-3 target increased from 328 × 333 to 984 × 999 pixels while its logical stage stayed 328 × 333. The original 7.25-unit camera width clipped an 8.3-unit rim; the final camera width is 9.1 in these cases.

| Physical window | Density | Final render target | Left / right margin, logical pixels |
| --- | ---: | --- | ---: |
| 1080 × 2340 | 3 | 984 × 999 | 14.42 / 14.42 |
| 2340 × 1080 | 3 | 1164 × 786 | 17.05 / 17.05 |
| 720 × 1560 | 1.75 | 663 × 822 | 16.66 / 16.66 |
| 390 × 844 | 1 | 358 × 423 | 15.74 / 15.74 |
| 844 × 390 | 1 | 425 × 292 | 18.68 / 18.68 |
| 1080 × 2400 | 3 | 984 × 1059 | 14.42 / 14.42 |

The exact 48 × 48 minimum is preserved in actual Control dimensions. Outward rounding fixes the observed 47.9999847-width failure without changing any existing test expectation. Card hit regions remain separate, projected first/last card centers select the correct cards, the lifted first card can be deselected, and covering the hand erases private faces, hit targets and selection. These local interactions emitted only the initial Ready event.

I viewed the final selected originals for 1080 × 2340 at density 3, 2340 × 1080 at density 3, and 720 × 1560 at density 1.75. I also reviewed the matching baseline and earlier candidate revealed frames, plus portrait concealed frames. The final images retain the full rim, sharp faces and emblems, smooth rounded outlines, readable rank names and distinct selection. The final-versus-prior image comparison is recorded in INDEPENDENT-3D-REVIEW.json. Landscape's action sidebar still requires vertical scrolling, as in baseline.

The 512 × 768 card textures are sufficient for the largest measured card footprint, approximately 156 × 191 physical pixels. Independent pixel comparison confirmed each card asset changed only 868 fully transparent pixels' RGB; alpha and all visible RGB stayed identical. No dark edge halos were observed.

Evidence: candidate-gl-final-results/report.json, candidate-gl-final-run.json, baseline-final-results/report.json, baseline-final-run.json, card-padding-review.json, and INDEPENDENT-3D-REVIEW.json in this directory. The same final review script still detects 30 expected native-resolution/framing failures in the frozen baseline, which was executed headlessly as a sensitivity check. Final review script: `6357dabbfe1f4205f3a1f6ae768523361af94dcf72ff05eb7ff9ba1a4156a7eb` at `godot/reviews/tests/three_d_quality_review.gd`.

Authoritative references: Godot 4.7.2-stable [SubViewportContainer source](https://github.com/godotengine/godot/blob/4.7.2-stable/scene/gui/subviewport_container.cpp), [Window source](https://github.com/godotengine/godot/blob/4.7.2-stable/scene/main/window.cpp), [Viewport documentation](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Viewport.xml), and [Camera3D documentation](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Camera3D.xml). Exact downloaded-source identities are recorded in OFFICIAL-SOURCES.json.

This review does not qualify physical-device GPU performance, native touch/accessibility, or authority-accepted gameplay.
