# Android screenshot publication queue

Copy `godot-android-adaptive-34496282263` and `android-34496267571` from `payload/docs/screenshots/` into the gallery. Merge the six collection records, 223 original screenshot records, evidence and index rows through review_design’s existing workflow. These files are fragments; do not replace the shared manifest or README. Root owns Git.

There are 30 API36 original capture triples and 193 API35 originals: 62 ordinary UI captures, 61 native-session triples, one emulator-preparation image and 69 Compose JVM snapshots. The two ordinary final screens retain their separately associated last-ui.xml files. The preparation image is setup evidence; the 69 JVM images are not emulator captures. Distinct original capture paths are never collapsed by shared content hashes. There are no new image derivatives or video frames.

API36 preserves review_design’s 28 direct original views and two named exact-byte reuses, plus ui_shell’s two earlier direct views. API35 preserves review_release’s seven direct native views. Further gallery-owner review receipts may be integrated separately without changing these original captures.

Debug 1× passed initial native landscape entry, then failed held rotation. Debug 2× passed initial entry, reported held rotation unsupported, then failed portrait Standard first-card reachability. Both optimized cases aborted during Godot JNI bootstrap. No 3D, transition-video or pixel-privacy qualification follows from this run.

Ordinary debug and optimized smokes passed. The debug native phase hit the executed ten-minute wrapper limit during partial 3d.renderer-death; no final debug result or complete check map exists. The optimized renderer aborted during Godot JNI startup. Neither native variant is fully qualified. Selected stills do not establish continuous privacy, engine gameplay or TalkBack speech/traversal.

All copied bytes, PNG header dimensions and staged page/metadata links are checked. Native original results, XML, capture receipts and compact frozen owner provenance are preserved. Video source references retain their original status and hashes without copying video. No APK, PCK, ZIP or source file is copied. See `copy-paths.tsv`, `validation-report.json`, `payload-SHA256SUMS` and `queue-freeze.json`.
