# Verified regression candidate

The same candidate test and unchanged authority claim fixture failed the baseline and passed the fixed renderer at logical 389 × 215 with text scale 2.0. No shared files were edited. The patch applies cleanly to the shared test's recorded SHA-256 `5d36c98fc638ebeb28c906350950bb6e7b7e5f111d560e2c62461db0c5e3d32e`.

| Run | Renderer table SHA-256 | Actual result |
| --- | --- | --- |
| Baseline | `a9edd383b71832b41d3fd307d3cf4397fe33df099c54471cb16006da0246e061` | Exit 1 in 1.542 seconds: “The short viewport leaves no visible scroll space for public context or actions.” Both projected actions have empty clipped rectangles in the captured diagnostics. |
| Fixed | `a91e94b910f763efb9c108d9e7602230736c503c6e53e4bd018a61ad9eebeb4d` | Exit 0 in 7.724 seconds. `ROUND 4`, every character of `Orbit claimed 1 Crown. Challenge or play on.`, and both projected action rectangles were reachable. Body height 103 scene units; scroll reached 907. |

The fixed run also passed the existing reveal/select/selection-limit/deselect/cover/foreground/history/close checks. It satisfied the original Ready-only event assertion before the history checks. No engine error was logged for the fixed run. The baseline logged only the expected assertion error. Both runs used the pinned Godot 4.7.2 executable, OpenGL Compatibility, Mesa llvmpipe and Xvfb. The renderer source fingerprints, candidate test, authority fixture and private runner remained unchanged throughout execution.

The patch adds one opt-in behavior assertion and a nine-line clipping helper, and extracts the existing scroll-before-click code for reuse. It adds 90 lines and removes six. It does not call the renderer's private layout/fit helpers or add density hooks, fixture generation, production code, dependencies, or CI infrastructure.

The checks held `/tmp/partydeck-godot.lock` and the existing bulk-I/O lock from 02:49:06.051 UTC through 02:49:16.065 UTC on 2026-09-11. Fresh scene-launch memory margins above the reserved threshold were 995,131,392 and 997,060,608 bytes. Across live samples, MemAvailable stayed at or above 4,887,953,408 bytes and `/tmp` free space at or above 3,569,762,304 bytes. No guard or timeout fired. Final private work after execution was 5,754,082 bytes, below the 32 MiB bound; no arena lease was created.

`COPYLIST.json` identifies the single proposed repository file. `RUN.md` documents execution with the existing authority claim fixture. `CAPTURES.json` preserves all nine generated PNG identities: two baseline and seven fixed captures. These new captures have not received independent pixel review; the regression result is an executed geometry/input assertion. The source fix's separate exact-density evidence and independent visual review are unchanged.

Authoritative API sources are pinned to Godot commit `ed1daf0bf001b61586d9930840f2f1394092c079`:

- [`Label.get_character_bounds`](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/doc/classes/Label.xml): local character/grapheme bounds.
- [`Control.get_global_rect` and `clip_contents`](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/doc/classes/Control.xml): visible bounds and ancestor clipping.
- [`ScrollContainer.ensure_control_visible` and `scroll_vertical`](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/doc/classes/ScrollContainer.xml): native scrolling after layout settles.
- [`Node.find_children`](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/doc/classes/Node.xml): finding runtime-created labels with `owned=false`.

This bounded desktop check does not establish authority acceptance, native accessibility, physical-device rendering/input, or physical-network behavior. Independent review of the proposed test remains the coordinator's integration step.
