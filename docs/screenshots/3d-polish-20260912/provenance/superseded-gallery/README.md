# 3D table: before and after

[Open the interactive gallery](index.html) to compare concealed, revealed, and selected hands. Every linked PNG is an unchanged original from the real Godot renderer.

The candidate renders the table at native pixel density, with sharper card details and the entire rim inside the stage. All nine capture/input/privacy checks passed in each of the three candidate cases.

| Physical window and density | 3D render target, before → after | Smallest side margin, logical px | Revealed originals |
| --- | --- | --- | --- |
| Portrait · 1080 × 2340 · density 3 | 328 × 333 → 984 × 999 | -23.75 → +14.42 | [Before](before/portrait-d3/02-revealed.png) · [After](after/portrait-d3/02-revealed.png) |
| Landscape · 2340 × 1080 · density 3 | 388 × 262 → 1164 × 786 | -28.10 → +17.05 | [Before](before/landscape-d3/02-revealed.png) · [After](after/landscape-d3/02-revealed.png) |
| Portrait · 720 × 1560 · density 1.75 | 379 × 470 → 663 × 822 | -27.44 → +16.66 | [Before](before/portrait-d1p75/02-revealed.png) · [After](after/portrait-d1p75/02-revealed.png) |

The fractional-density target differs from its physical stage by 0.25 px horizontally and 0.5 px vertically, within pixel rounding. Anti-aliasing changed from 2× to 4× MSAA. The short landscape details panel scrolls; these images preserve the initial scroll position.

Baseline: `e8e05709`, copied into scratch before import. Its original 160-file source inventory is unchanged and no import cache was created there. Candidate images were rendered from PCK `1a8642527d6115817a0683d95ded2619d7396122db1acba167decbcb63e8d06b` with an external capture script and an empty project directory.

These are recipient-safe fixture captures on Godot 4.7.2 with Mesa llvmpipe under Xvfb, not device GPU or multiplayer qualification. Reveal and selection used real mouse input; no gameplay intent or accepted play is claimed here. Reduced motion was enabled in both versions.

[Manifest and measurements](manifest.json) · [SHA-256 file inventory](SHA256SUMS) · [Fixture provenance](provenance/fixture-manifest.json) · [Reusable capture harness](../../../godot/renderer/tests/three_d_quality_capture.gd)
