# Android Godot comparison evidence

**All four API 35 debug cases passed in [run 34463877910](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34463877910).**

Exact revision: `bbfde024d95f5e4d62a26b57495a6a90447d6033`. Candidate PCK: `a47392b4ca50e0433e1f42043b9473b08e9641d24117e251a4ab88e11027e3db` (1,547,096 bytes, 136 checked entries). The debug runtime APK is `7aa1a9296e759729869f0a7542ea477d19bf0a5d16eb3a8953ce2ee56ec08d06`.

Both 2D and 3D at standard and 200% text completed match return, scene Exit, and native Close/Back. All 12 routes recorded a Close dispatch, native barrier and main callback with no fallback. Native barriers arrived 5–34 ms after the request; main callbacks arrived 25–206 ms after it. Native destruction took 111–260 ms. The native job/checker/host/bridge and 250 ms Close fallback / 1,500 ms renderer-exit bounds are unchanged from the prior failed checkpoint.

The reused read-only audit verified source and installed-input hashes, strict teardown, OS process-death events, chooser recovery, 48 scene-capture crop hashes, input geometry, and all 80 Android artifact PNGs. Producer evidence has 37 JUnit cases, 69 checker host tests, 111 packed boundary assertions, 164 terminal-return assertions, and matching 42-view desktop authority traces.

All six original artifact ZIP digests and sizes match GitHub metadata; all 599 extracted files match their ZIP members. Five complete job logs and the exact source archive are retained. The original capture inventory contains 76 native runtime frames, four empty-AVD preparation frames, and 22 desktop frames.

Independent original-image/privacy/accessibility review is pending. API 36, optimized native runtime, production app integration, physical devices, mixed-device LAN, signing and store acceptance are outside this run. Known driver/shader warnings remain in the originals.

Receipts: [originals-frozen.json](originals-frozen.json), [native-evidence-automated.json](native-evidence-automated.json), [source-close-barrier-correlation.json](source-close-barrier-correlation.json), [original-capture-inventory.json](original-capture-inventory.json), and [collection-frozen.json](collection-frozen.json).
