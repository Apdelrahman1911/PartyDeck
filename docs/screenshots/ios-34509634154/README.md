# iOS ordinary and production sessions — CI 34509634154

[All collections](../README.md) · [Preserved evidence index](evidence-index.md) · [Copy/review binding](../android-34515669045/provenance/publication-review/partydeck-gallery-3433-publication-binding-v1.json) · [Completed focused review](provenance/publication-review/partydeck-gallery-after-2815-production34509634154-visual-review-v1.json) · [Source mapping](provenance/source-map/partydeck-gallery-after-2815-production34509634154-source-map-v1.json)

Nine ordinary XCTest cases and five unfiltered .all accessibility audits pass. Three guarded UIKit layout cases pass separately and produce zero PNGs. Both actual native production cases fail at the second fresh-frame wait in initial enter(), before native selection/Play/return/Leave/reentry. Production-session Standard checkpoints do not invoke the ordinary .all audit callback. Manual isAssociatedWithFailure=false attachment metadata is preserved and does not imply success.

The directly reviewed ordinary maximum-selection checkpoint shows all five named cards, three checks, 3 of 3 selected, count-only feedback and full lower actions. The old-pack 2D failure clips the Reveal label at the body edge. The 3D failure renders a covered table with full Show hand/Select/Challenge, horizontally clipped seats and a clipped Return to lobby. Three priority originals were directly viewed; 19 others remain explicitly unviewed.

Pack SHA-256: `d6adbba1b5cbd6a1ac3a5754e4294363eae70ae9540af4ba12040cd4cfff44e0`. Both original videos remain unviewed and undecoded. No hit-area, assistive-technology traversal, continuous-privacy or timeout-cause conclusion follows from these stills.

| Collection | Original PNGs | Original outcome and scope |
| --- | ---: | --- |
| [Ordinary shared UI — iOS CI 34509634154](ordinary/README.md) | 10 | Nine ordinary cases and five unfiltered .all audits pass; pixel review remains individually scoped. |
| [Production native sessions — iOS CI 34509634154](godot-session/README.md) | 12 | Both native cases fail the second initial-entry freshness wait; later native gameplay remains unreached. |
