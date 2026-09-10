Run **34478720554**, archived head **c6ea1dd9f7966517fbee87a06b633d01c432c24d**: `AuthorityHostUITests/testReferenceMatchIn2DAt200Percent()` remains a failure at `app.launch()` with a recorded duration of 92.267462 seconds. The retained video nevertheless shows the Authority chooser late in the recording. A subsequent `start-2d` tap is explicitly attempted in the test activities; event delivery and native scene entry are not established.

The original recording is `856F498D-90C1-48CC-8225-0A35C78305BA.mp4`, 1,756,068 bytes, SHA-256 `399b9f05d4f06728d0709e16fd80a989ad81299a6985376aac8c62e774b2fa25`. The original issue export, database and complete job log were read from the existing run collection and independently matched their expected hashes. The issue export matches the database description exactly. Its source location is `AuthorityHostUITests.swift:118`, the `app.launch()` call. The case has one video attachment and one CI-exported issue text, with no measurement, touch-geometry, observed-control or rejected-diagnostics attachments.

The decoder preserved all **129 original video samples** as 1206 × 2622 PNG files, totaling 52,882,395 bytes. This is variable-frame-rate H.264 video with an 88.843333-second duration and a 1/600 time base. The large gaps between early sample timestamps belong to the recording; no decoded frames were discarded. FFmpeg performed H.264 decoding and YUV-to-RGB conversion only, without scaling, cropping, interpolation, annotation or generated visual content. These PNGs are derived video frames, not original CI screenshot attachments.

Nine frames were visually inspected. Their sequence supports the following observations:

| Preserved frame | Original PTS, seconds | Visible state |
| --- | ---: | --- |
| `frame-0001.png` | 0.000000 | iOS Home, clock 12:59 |
| `frame-0002.png` | 58.351667 | iOS Home, clock 1:00 |
| `frame-0003.png` | 76.285000 | iOS Home, with a new `LastLightComp...` icon |
| `frame-0025.png` | 79.708333 | White app window expanding over blurred Home |
| `frame-0060.png` | 80.850000 | Blank white app view |
| `frame-0072.png` | 81.008333 | Blank white app view |
| `frame-0073.png` | 84.510000 | Faint Authority chooser during fade-in, including `Idle` |
| `frame-0100.png` | 85.190000 | Full Authority chooser, `Idle` |
| `frame-0129.png` | 88.831667 | Full Authority chooser, `Idle` |

Frames 72 and 73 are consecutive retained samples, separated by 3.501667 seconds. They bound the observed blank-to-chooser transition at that sample boundary, without establishing an exact onset time within the gap. The later frames show `Play in 2D`, `Play in 3D`, `Sound`, and `Repeatable comparison scenario`. These labels and the `Idle` text match the archived host source. The nine inspected frames are not a claim that every decoded frame was visually reviewed.

The database supplies the following event times. Its raw timestamps use the 2001 epoch; adding 978,307,200 seconds gives Unix time. This conversion matches both the first activity's embedded UTC title and the collector's exported recording timestamp. Raw values and millisecond conversions are retained in `timeline.json`.

| Retained event | UTC on 2026-09-10 |
| --- | --- |
| Test start | 12:58:59.472 |
| Recording attachment timestamp | 12:59:02.094 |
| Launch activity starts | 12:59:02.191 |
| Launch-timeout issue timestamp | 13:00:02.349 |
| Automation session setup starts | 13:00:22.627 |
| Launch activity finishes | 13:00:27.777 |
| Wait for `start-2d` begins | 13:00:27.797 |
| `Tap "start-2d" Any` activity | 13:00:29.144–13:00:30.560 |
| Teardown starts | 13:00:30.927 |

The MP4's creation metadata is **12:59:01 UTC**, 1.094 seconds earlier than the attachment timestamp. Recording user information contains orientation and scale only; it does not resolve the mapping from PTS zero to wall-clock time. `timeline.json` therefore retains both conditional alignments, rather than treating their difference as a proven timing bound. Under either candidate origin, the faint chooser frame falls around 13:00:25.510 or 13:00:26.604, after the timeout issue and before the `start-2d` wait. The exact absolute frame clock remains unresolved.

The outer CI timestamps cannot substitute for those event times: for example, the launch-timeout issue appears in the CI log at **13:00:14.847**, while its database timestamp is **13:00:02.349**. The retained log excerpts keep the outer timestamps, embedded timestamps and relative test times intact. The post-test restart message says “unexpected exit, crash, or test timeout”; that generic alternative list does not identify a specific cause.

The complete failed-case activity tree contains **17 activities**. The tap attempt contains idle, element lookup and interruption-check children, but **no `Synthesize event` activity**. The complete failed-case log also has no such line. The next normal-scale 2D case, which passed, explicitly records `Synthesize event` beneath its first `start-2d` tap. This comparison supports distinguishing an attempted action from proven delivery; absence of the synthesis record does not prove that no event reached the app. Nested activities have null `testCaseRun_fk` values, so the retained SQL queries recursively include children rather than filtering only that column.

The source sets `continueAfterFailure = false`, but the observed subsequent activities still include the tap attempt. The source alone therefore cannot justify “the button was never tapped.” The source also eagerly constructs `PDGodotRuntime()`; actual authority creation and `runtime.prepare(...)` occur inside `start(mode:...)`. It would be too strong to claim that no runtime object was instantiated. What remains unproven is native scene entry and gameplay qualification. The test's `--text-scale=2` argument is consumed when starting the renderer; these chooser frames do not establish a 200% Dynamic Type setting or 200% renderer behavior.

The debugger-version and duplicate-accessibility-class warnings also appear around the next passing normal-scale 2D case. They do not establish an OS or debugger root cause. The reviewed evidence identifies no source-supported implementation fix, and does not justify retries, longer deadlines, a successful-launch classification or native acceptance. Suitable status wording is: **“2D/200% failed at the XCTest launch timeout; the retained video later shows the Idle chooser. A 2D tap attempt is logged, but event delivery and native entry remain unproven.”**

Evidence is retained in this separate review directory:

- `decoded-frame-manifest.json`: all 129 frame hashes, sizes and original frame metadata.
- `viewed-frames.json`: the nine inspected frames, observations and publication queue provenance. Every viewed frame was queued to `/root/review_design`; publication review is separate.
- `decoder/`: authorized FFmpeg installation receipt, tool versions, exact probe/decode commands, stdout and stderr. Installed Ubuntu package version: `6.1.1-3ubuntu5`.
- `xcresult-readonly-query-results.json`, `timeline.json`, `retained-log-excerpts.json`, and `archived-source-excerpts.json`: exact retained inputs supporting the findings.
- `input-provenance.json`, `inspection-checks.json`, and `export-review-command.*`: expected input identities, reproducible metadata export and successful checks.
- `collection-frozen.json`: final file inventory and SHA-256 hashes for this bounded review.

Verification matched the original video, issue, database and log hashes; confirmed the complete activity tree and exact issue text; and checked every decoded PNG's hash, byte count and dimensions. The original input identities remained unchanged during the export, including the original collection freeze SHA-256 `e154d73f2f5b91571b107b9d9c81ebc2372563f11ac8546c0112bb558814e3f5`. This review ran no native build or test, performed no new CI collection, and made no shared-source or Git changes.
