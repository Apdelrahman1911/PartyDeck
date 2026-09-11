# Android adaptive recording frames — CI 34540229407

This batch preserves **2,476 full-resolution WebP frame identities** from 32 original recordings: **1,379 directly viewed identities**, **1,097 verified byte matches**, and **0 unviewed identities**. Views are attributed to the named reviewers; the publication assembler did not inspect pixels.

Source revision: `4ee4563def1c9a1b5060572efa2c3959c7d7677e`. These are lossless WebP derivatives of the documented FFmpeg conversion from the original MP4 video, preserving the 1600 × 720 source canvas. The original videos are reused from the existing adaptive gallery.

Each recording index links every source frame and its original packet PTS. Identical bytes retain separate source identities. Packet PTS establishes media order only; it is not aligned to host UTC or input DOWN/UP. Captured frames do not establish continuous device privacy between frames, physical-device behavior, control reachability, or accessibility.

Reviewers reported no visible private card faces in represented reviewed frames. Some native and returned hand/control areas lie outside captured viewports. The receipts distinguish those visible limits from offscreen concealment or interaction claims.

**Recorded layout defect:** the latest-claim text is truncated in the debug and optimized font-2.0 3D split-exit views. [Source/evidence triage](provenance/layout-issue/issue.json) confirms that this label sits outside the body scroll container, so scrolling that body cannot recover it. These recordings retain the affected old source and do not validate a correction. Other offscreen scroll-body content keeps its separate evidence limits.

[Media manifest](manifest.json) · [Review counts and limits](review-summary.json) · [Existing original-capture gallery](../../godot-android-adaptive-34540229407/README.md)

| Recording | Source frames | Direct | Byte matches | Unviewed |
| --- | ---: | ---: | ---: | ---: |
| [debug-font-1.0/2d-landscape-rotation](recordings/debug-font-1.0/2d-landscape-rotation/README.md) | 89 | 43 | 46 | 0 |
| [debug-font-1.0/2d-seascape-rotation](recordings/debug-font-1.0/2d-seascape-rotation/README.md) | 91 | 48 | 43 | 0 |
| [debug-font-1.0/2d-split-entry](recordings/debug-font-1.0/2d-split-entry/README.md) | 81 | 51 | 30 | 0 |
| [debug-font-1.0/2d-split-exit](recordings/debug-font-1.0/2d-split-exit/README.md) | 65 | 37 | 28 | 0 |
| [debug-font-1.0/3d-landscape-rotation](recordings/debug-font-1.0/3d-landscape-rotation/README.md) | 82 | 50 | 32 | 0 |
| [debug-font-1.0/3d-seascape-rotation](recordings/debug-font-1.0/3d-seascape-rotation/README.md) | 80 | 51 | 29 | 0 |
| [debug-font-1.0/3d-split-entry](recordings/debug-font-1.0/3d-split-entry/README.md) | 84 | 50 | 34 | 0 |
| [debug-font-1.0/3d-split-exit](recordings/debug-font-1.0/3d-split-exit/README.md) | 69 | 38 | 31 | 0 |
| [debug-font-2.0/2d-landscape-rotation](recordings/debug-font-2.0/2d-landscape-rotation/README.md) | 91 | 43 | 48 | 0 |
| [debug-font-2.0/2d-seascape-rotation](recordings/debug-font-2.0/2d-seascape-rotation/README.md) | 84 | 38 | 46 | 0 |
| [debug-font-2.0/2d-split-entry](recordings/debug-font-2.0/2d-split-entry/README.md) | 84 | 41 | 43 | 0 |
| [debug-font-2.0/2d-split-exit](recordings/debug-font-2.0/2d-split-exit/README.md) | 69 | 33 | 36 | 0 |
| [debug-font-2.0/3d-landscape-rotation](recordings/debug-font-2.0/3d-landscape-rotation/README.md) | 85 | 52 | 33 | 0 |
| [debug-font-2.0/3d-seascape-rotation](recordings/debug-font-2.0/3d-seascape-rotation/README.md) | 87 | 40 | 47 | 0 |
| [debug-font-2.0/3d-split-entry](recordings/debug-font-2.0/3d-split-entry/README.md) | 78 | 46 | 32 | 0 |
| [debug-font-2.0/3d-split-exit](recordings/debug-font-2.0/3d-split-exit/README.md) | 68 | 34 | 34 | 0 |
| [optimized-font-1.0/2d-landscape-rotation](recordings/optimized-font-1.0/2d-landscape-rotation/README.md) | 83 | 51 | 32 | 0 |
| [optimized-font-1.0/2d-seascape-rotation](recordings/optimized-font-1.0/2d-seascape-rotation/README.md) | 81 | 44 | 37 | 0 |
| [optimized-font-1.0/2d-split-entry](recordings/optimized-font-1.0/2d-split-entry/README.md) | 75 | 47 | 28 | 0 |
| [optimized-font-1.0/2d-split-exit](recordings/optimized-font-1.0/2d-split-exit/README.md) | 57 | 36 | 21 | 0 |
| [optimized-font-1.0/3d-landscape-rotation](recordings/optimized-font-1.0/3d-landscape-rotation/README.md) | 84 | 52 | 32 | 0 |
| [optimized-font-1.0/3d-seascape-rotation](recordings/optimized-font-1.0/3d-seascape-rotation/README.md) | 79 | 52 | 27 | 0 |
| [optimized-font-1.0/3d-split-entry](recordings/optimized-font-1.0/3d-split-entry/README.md) | 73 | 47 | 26 | 0 |
| [optimized-font-1.0/3d-split-exit](recordings/optimized-font-1.0/3d-split-exit/README.md) | 63 | 37 | 26 | 0 |
| [optimized-font-2.0/2d-landscape-rotation](recordings/optimized-font-2.0/2d-landscape-rotation/README.md) | 79 | 38 | 41 | 0 |
| [optimized-font-2.0/2d-seascape-rotation](recordings/optimized-font-2.0/2d-seascape-rotation/README.md) | 82 | 37 | 45 | 0 |
| [optimized-font-2.0/2d-split-entry](recordings/optimized-font-2.0/2d-split-entry/README.md) | 74 | 45 | 29 | 0 |
| [optimized-font-2.0/2d-split-exit](recordings/optimized-font-2.0/2d-split-exit/README.md) | 59 | 34 | 25 | 0 |
| [optimized-font-2.0/3d-landscape-rotation](recordings/optimized-font-2.0/3d-landscape-rotation/README.md) | 83 | 41 | 42 | 0 |
| [optimized-font-2.0/3d-seascape-rotation](recordings/optimized-font-2.0/3d-seascape-rotation/README.md) | 85 | 46 | 39 | 0 |
| [optimized-font-2.0/3d-split-entry](recordings/optimized-font-2.0/3d-split-entry/README.md) | 77 | 48 | 29 | 0 |
| [optimized-font-2.0/3d-split-exit](recordings/optimized-font-2.0/3d-split-exit/README.md) | 55 | 29 | 26 | 0 |
