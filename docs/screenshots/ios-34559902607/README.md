# iOS simulator qualification — CI 34559902607

**Both production sessions passed; nine ordinary tests and three UIKit tests also passed.** This collection preserves all 51 original PNGs from attempt 1 at `39405bb0fd6ba0214e70ed251aab1f9f571dc9aa`: 20 production 2D, 21 production 3D and 10 ordinary UI captures. The separate UIKit gate exported no images.

Pixel coverage: **51 direct views, 0 reviewed byte matches and 0 unviewed originals**. Per-image captions name the reviewer and exact receipt.

Separate 2D and 3D reviews each cover eight direct views and one verified byte match among nine assigned identities. Those records remain attributed separately; duplicate files retain their original UUIDs, attachment timestamps and repeated-label occurrences.

| Original scope | Stills | Native result |
| --- | ---: | --- |
| [2D production practice](2d/README.md) | 20 | Passed, 316.893 s XCTest case wall time |
| [3D production practice](3d/README.md) | 21 | Passed, 532.216 s XCTest case wall time |
| [Ordinary UI](ordinary/README.md) | 10 | All nine ordinary native/UI tests passed |

[Capture manifest](manifest.json) · [Frozen original catalog](provenance/collector/current-original-still-catalog-v1.json) · [Independent native results](provenance/review/ios_review/dedicated-native-results-independent-review-v1.json) · [All-original pixel review](provenance/review/ios_review/original-screenshot-independent-review-v1.json)

Source attachment labels describe the test checkpoints. They are separate from pixel captions and native action receipts. Original manifest ordinals are preserved even where the manifest runs in reverse chronological order. Paired latest sanitized observations preserve exact attachment identities and timestamps; they are not asserted to be atomic with the PNGs.

The current 3D post-scroll checkpoint shows complete Play, Challenge and Return to lobby controls together with public round/claim context. The source-scoped body-scroll evidence records one gesture, retained selection and zero authority intents before and after; Challenge was available but was not executed. [Original body-scroll receipt](provenance/collector/ios-reports-and-simulator-app/build/ci/ios/godot-session/attachments/75A1761E-42C7-428B-8A13-6B882630E7BE.json).

The reviews retain initial 3D control clipping, later fully visible action bounds, and lower Standard-result viewport limitations. A 2D NEXT_ROUND action receipt does not make every immediately following still a frame of the new round. Per-image findings preserve these distinctions.

The timing record contains an individual completed 3D draw of 18.764 s and iteration of 18.735 s, already present by the first retained observation (sequence 853). The exact frame and CPU/GPU cause are unknown; unchanged later maxima do not exclude equal or shorter stalls. [Timing scope](provenance/review/ios_fix/ACTUAL-TIMING-INTERPRETATION-34559902607-v2.json).

XCTest durations and renderer timing observations have separate scopes. These passes do not establish hardware performance. The full run skipped shipping-picker tests. The gallery adds no physical-device, signing/store, physical-network or continuous-privacy qualification. No video asset, video decode or new screenshot was produced for this publication.
