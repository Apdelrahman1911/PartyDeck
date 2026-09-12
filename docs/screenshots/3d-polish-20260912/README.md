# 3D table: before and after

The portrait pair below shows the same revealed hand before and after the renderer changes. Every image is an unchanged original PNG from the real Godot renderer.

| Before · 1080 × 2340, density 3 | Final candidate · 1080 × 2340, density 3 |
| --- | --- |
| [![Baseline: clipped rim and soft 3D detail](before/portrait-d3/02-revealed.png)](before/portrait-d3/02-revealed.png) | [![Final candidate: full rim and sharper 3D detail](after-final/portrait-d3/02-revealed.png)](after-final/portrait-d3/02-revealed.png) |

[Browse all original images in the repository](ALL-IMAGES.md). The [interactive HTML gallery](index.html) is optional: download this directory and open it locally.

The candidate renders the table at native pixel density, with sharper card details and the entire rim inside the stage. All nine capture/input/privacy checks passed in each of the three candidate cases.

| Physical window and density | 3D render target, before → after | Smallest side margin, logical px | Revealed originals |
| --- | --- | --- | --- |
| Portrait · 1080 × 2340 · density 3 | 328 × 333 → 984 × 999 | -23.75 → +14.42 | [Before](before/portrait-d3/02-revealed.png) · [After](after-final/portrait-d3/02-revealed.png) |
| Landscape · 2340 × 1080 · density 3 | 388 × 262 → 1164 × 786 | -28.10 → +17.05 | [Before](before/landscape-d3/02-revealed.png) · [After](after-final/landscape-d3/02-revealed.png) |
| Portrait · 720 × 1560 · density 1.75 | 379 × 470 → 663 × 822 | -27.44 → +16.66 | [Before](before/portrait-d1p75/02-revealed.png) · [After](after-final/portrait-d1p75/02-revealed.png) |

The fractional-density target differs from its physical stage by 0.25 px horizontally and 0.5 px vertically, within pixel rounding. Anti-aliasing changed from 2× to 4× MSAA. The short landscape details panel scrolls; these images preserve the initial scroll position.

Baseline: `e8e05709`, copied into scratch before import. Its original 160-file source inventory is unchanged and no import cache was created there. Candidate images were rendered from PCK `7ec66f903ed41b55bdb4c3d8972de56900c85fe765f1bf7cc81306150c86e9f2` with an external capture script and an empty project directory.

The focused before/after matrix uses recipient-safe fixture captures on Godot 4.7.2 with Mesa llvmpipe under Xvfb, not device GPU or multiplayer qualification. Reveal and selection used real mouse input; no gameplay intent or accepted play is claimed by the focused matrix. Reduced motion was enabled in both versions.

[Manifest and measurements](manifest.json) · [SHA-256 file inventory](SHA256SUMS) · [Fixture provenance](provenance/fixture-manifest.json) · [Reusable capture harness](../../../godot/renderer/tests/three_d_quality_capture.gd)

[All 82 original PNGs and iterations](ALL-IMAGES.md) are preserved with [full image identities](original-catalogue.json). The final archive includes six local/remote public-play motion frames and 22 full-match 2D/3D frames. The motion test passed 123 desktop renderer checks; its recipient snapshots are fixtures. The full-match comparison passed with the same actual KMP authority trace in both presentations, as recorded in its [report](authority-comparison-final/report.json). Earlier failed motion reports and the superseded candidate remain labeled in the archive.

[Independent review](review/INDEPENDENT-3D-REVIEW.md) approved the final pack after all 492 rendering/input assertions and direct review of the final portrait, landscape, and fractional-density images. It found no unresolved issue within the tested scope.
