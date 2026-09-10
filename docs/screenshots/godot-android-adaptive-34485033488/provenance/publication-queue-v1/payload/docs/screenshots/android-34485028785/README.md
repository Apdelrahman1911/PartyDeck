# Android production captures — CI 34485028785

The ordinary UI smokes passed; the separate 2D native-entry checks failed. Exact source is `fc431ee775990943dfe152f4f20fb9365db4e72d`.

| Collection | Original PNGs | Outcome |
| --- | ---: | --- |
| [Debug ordinary flow](debug/README.md) | 31 | Ordinary UI smoke passed; no new full visual review. |
| [Optimized ordinary flow](optimized-test-signed/README.md) | 31 | Ordinary UI smoke passed; no new full visual review. |
| [Production table-style entry](godot-session/README.md) | 12 | Both native entry checks failed; no Godot renderer/Ready observed. |

The 72 named PNG/XML pairs and two distinct final PNGs preserve original failures and successes separately. [Existing owner result](provenance/RESULT.md) · [Original audit](provenance/runtime-evidence-audit-v2.json) · [Collection freeze](provenance/collection-frozen.json).
