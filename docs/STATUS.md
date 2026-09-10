# PartyDeck status report

**Snapshot: 2026-09-10, 13:23 UTC.** Source is pushed through
`7012ba031a4129c81cd118206f727a46a1c846e4`. Estimated completion of the original
app release scope is **81%**. The additional Godot comparison has **3 of 6
acceptance groups complete (50%)**. These measure different scopes and must not
be added or averaged. **The app is not yet production-ready.**

Both real Godot presentations exist and remain until the user chooses. Desktop
matches pass. The newest Android comparison passes all four normal/200% 2D/3D
cases and all twelve exits with the new renderer. iOS remains partial: the newest
authority run passes two of five cases and retained tests pass one of three.
The workflow failed; original artifacts are collected and detailed review is in
progress. Production-app integration has further open gates.

Reviewed iOS linker/header corrections and the winner announcement fix are now
pushed. Production iOS is retrying. Android picker and adaptive-observer fixes
are being composed for new native runs. Separate owners are extending native
Standard-table accessibility assertions while collectors and reviewers work in
parallel. Only actual completed evidence is counted below.

## Completion calculation

| Original release workstream | Weight | Complete | Evidence and remaining limit |
| --- | ---: | ---: | --- |
| Core features and architecture | 30% | 100% | Rules, authority, protocol, transport, practice and app flows implemented; physical multiplayer qualification is separate |
| UI, assets and accessibility implementation | 15% | 100% | Screens, original assets, preferences and native accessible Standard controls implemented; current winner correction has seven passing focused UI tests |
| Configured baseline automated qualification | 20% | 100% | Refreshed Android/JVM, shared iOS, Swift TLS and native app flows pass, including separate Android API 36; final Godot regressions remain separate |
| Builds and unsigned packaging | 15% | 100% | Original Android APK/AAB and iOS Simulator/optimized unsigned device packages built; current Godot production builds remain open |
| Physical-device release validation | 15% | 0% | Physical Android/iPhone matrix not executed here |
| Publisher, signing and store readiness | 5% | 10% | Configuration and instructions exist; actual identities, policies, signing, store setup and submission remain |

Weighted result: **80.5%, rounded to 81%**. This is a milestone estimate, not test
coverage, a reliability guarantee or an estimate of time remaining. Source fixes
and partial runs do not automatically increase the percentage.

| Godot acceptance group | Status |
| --- | --- |
| Verified engine, imports and real exported resources | Complete |
| Common authority bridge, privacy and message validation | Complete |
| Matched 2D/3D gameplay scenarios and desktop launch instructions | Complete |
| Native entry, lifecycle, concealment, exit/re-entry and teardown on both platforms | Partial |
| Mobile visual, interaction, responsive and accessibility acceptance | Partial |
| Both qualified, independently selectable native previews | Partial |

Exact definitions are in [the Godot plan](../godot/README.md).

## What is implemented

- **Last Light:** original two-to-six-player bluffing game, thirty-card deck,
  private five-card hands, one-to-three-card claims, challenges, six-light
  penalties, elimination, round advancement, winners and rematches.
- **Practice:** complete bot matches using the same authority as multiplayer.
- **Local multiplayer:** hosting, joining, lobby readiness, invitation sharing
  and pasting, QR display/native scanning, optional discovery, same-seat
  reconnection and recoverable errors. Physical LAN qualification remains.
- **Transport and privacy:** native TLS, full host-certificate pinning,
  admission/reconnect credentials, bounded messages/queues, replay/revision
  rejection, recipient-specific views and cryptographic randomness.
- **App flows:** Home, Host, Join, Lobby, Rules, Settings, gameplay, round results
  and winner; hand reveal/concealment; persistent sound, haptic and reduced-motion
  settings. Rules-to-Practice navigation is fixed and verified.
- **Assets and architecture:** original cards, symbols, launcher artwork and
  sound; licensed typography and offline notices; shared KMP modules and native
  services. The optional desktop launcher reuses the app.
- **Godot:** real 2D/3D scenes, recipient-safe event bridge, common attachment to
  the existing session, Android process-separated host and retained iOS engine
  with Swift adapter. Production native qualification is in progress.

The Standard table already supplies the agreed native accessible controls route
on the same session. A second complete Godot accessibility overlay is not required
by that option. The Godot canvas has no mobile accessibility adapter. Feasible
native assertions are being extended; actual TalkBack/VoiceOver speech, focus and
traversal remain unqualified. The winner heading now has polite live-region
semantics. Seven focused tests pass, including stable winner identity, quiet
history and pending-rematch behavior.

Default shipping configuration currently exposes no Godot modes. Explicit build-time
qualification profiles enable both for testing. Completing qualification and
shipping activation are project work. Host migration and restoring matches after
host process death are outside the agreed first-release scope.

## Completed automated evidence

Each result belongs to its stated source/run. Repeated runs are not added together
as new coverage, and earlier success is not assigned to a new pack.

| Verification | Executed result |
| --- | --- |
| Refreshed original app, [34428798269](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34428798269), `15ab640` | 118 Android/JVM tests, 83 shared iOS tests, three Swift TLS tests and three native iOS UI tests pass; Android debug/optimized flows and iOS Simulator/unsigned device builds pass |
| Rules framing follow-up, [34432935952](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34432935952), `8d8d429` | 118 tests and both APK flows pass; full Rules button borders and actual navigation verified at normal/200% text |
| API 36 baseline, [34457458638](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34457458638), `f11f92e` | Both ordinary APK flows pass, 86 steps/thirty stage captures per APK; 23 independent evidence checks pass; Godot session smoke disabled |
| Android production integration, [34475047307](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34475047307), `0222e6f` | 228 current JUnit cases in 39 suites and 83 Python checks pass; zero lint errors/eleven warnings; both ordinary app flows pass with 88 steps/thirty stage pairs each; both native-session phases fail before entry |
| Previous Android comparison, [34475057938](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34475057938), `0222e6f` | All four normal/200% 2D/3D cases and all twelve exits pass; 444 host observations, 430 fully applied diagnostics and 48 capture hashes verified |
| New Android comparison, [34478725424](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34478725424), `c6ea1dd` | Workflow succeeds with all four cases and all twelve exits; current PCK/source and producer checks verified; final detailed native evidence review is in progress |
| Previous iOS native hosts, [34473325295](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34473325295), `0f666e0` | Both hosts build; authority 5/5 passes; retained 1/3 passes, with dormant observation and second-3D cover/timing failures preserved |
| iOS production integration, [34473324178](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34473324178), `0f666e0` | Both native engines, staging and 139 shared native tests pass; app links and Simulator unit-test header scanning fail; production Godot XCTest is not reached |
| Current packed renderer, `4d8bd92` / `c6ea1dd` | Real-render checks pass: 155 boundary, 216 terminal-return and 306 redraw assertions, 677 total |

The Android production audit excludes 76 historical documentation suites from
current test totals. Disposable CI test signing is not publisher signing.
Comparison evidence does not qualify production-shell sessions, physical LAN or
hardware GPUs. Earlier failures retain their exact sources and artifacts.

## Current pack and unfinished corrections

Current PCK: **1,549,656 bytes, 136 entries**, SHA-256
`d6adbba1b5cbd6a1ac3a5754e4294363eae70ae9540af4ba12040cd4cfff44e0`.
The 3D SubViewport now redraws when the scene, actual card poses, camera or size
changes. It retains pending draws until consumed, preserves final animation
poses/concealment, and recovers after skipped or zero-size draws. One initial
layout pass fixes an observed first-frame issue and disables itself. Source
review and desktop assertions pass; native performance improvement is unproven.

The v6 native freeze changes only the exact runtime pack literal from v5.
Reviewed CoreAudio dormancy and main-loop access patches remain; the optional
mouse patch stays unapplied. Scene, lifetime, authority, cover and input predicates
remain. An incorrect root boundary invocation used a manual-bridge flag; its
failure is preserved separately. The corrected invocation passes with unchanged
product/PCK bytes.

| Open issue | Evidence and completed work | What closes it |
| --- | --- | --- |
| iOS static framework linkage | Whole-archive loading exposes overlapping Skiko archive members. All 6,221 emitted device duplicate-symbol blocks correlate with identical dependency members. Reviewed fix removes two force-load tuples, keeps framework linkage and strengthens Kotlin class ownership checks; pushed in `d26bfb2`. | Actual Simulator/device links and real link-map verification |
| iOS unit-test header lookup | Original PartyDeckTests transitive bridge-header scan lacks the native include path. Added only its Debug/Release header settings; independent composition review passes. | Actual unit-test compilation and XCTest |
| Android production picker | Original XML has enabled/clickable/checkable choices but no dialog/choice IDs. Checker waits on absent IDs; static analysis shows generic clearance would also reject the retained radio-row bounds. Bounded visible-label selection is being finalized. | Debug/optimized sessions entering both modes and completing lifecycle checks |
| Android adaptive observer | All four consumers in [34475052568](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34475052568) fail before scenarios. Actual activity text uses `Hist  #0`; parser demands one space. Override bypasses raw process capture. Both fixes pass twelve original-sample replays and independent review. | Final composed pins and four real API 36 adaptive consumers |
| Retained dormant observation | Wait previously accepted background progress before activation finished. Reviewed fix waits for actual foreground activation within the original deadline; pushed in `c6ea1dd`. | Dormant activation accepted in the current run; later second-3D entry remains failed |
| iOS 3D cover/timing and current Authority failures | Prior rejected retained sample has current applied scene state but visible cover. New Authority run fails both 3D diagnostics waits and 2D/200% startup. Original evidence is collected and being diagnosed; cover and deadlines remain intact. | Timely accepted native observations, complete gameplay/lifecycle and the unreached old-handle probe |
| Native accessibility/session acceptance | Standard route exists. Android/iOS owners are adding labels/states, fifth-card reachability, deselection, selection-limit feedback, Hide privacy and real Standard authority actions after Godot return. | Supported native automated acceptance, then separate hardware AT testing |

The iOS link verifier has 29 synthetic checks; twelve existing activation checks
also pass on integrated source. Neither proves an Apple link/runtime result.
Android's previous process-list correction is now verified against actual output:
all 24 original production command receipts succeed and parse correctly.

The newest retained failure evidence confirms that the revised dormant wait
accepted actual active/foreground state. Its next 3D entry then remains warming,
waiting for Ready at revision zero with empty diagnostics: 77.065 seconds elapsed
for the configured 60-second wait. The stale-reentry case rejects the same state
after 22.417 seconds for its 15-second wait. Those are separate from the earlier
covered-but-current failure; the original rejected payloads are preserved.

## Work running in parallel

| Work | State at this snapshot |
| --- | --- |
| [iOS production retry 34480503751](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34480503751), `7012ba0` | Running with linker/header fixes, current pack and explicit 2D/3D production-session qualification |
| [iOS native hosts 34478720554](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34478720554), `c6ea1dd` | Producers pass. Workflow failed. Authority 2/5: normal 2D and secure Exit pass; 2D/200% launch and both 3D diagnostics fail. Retained 1/3: repeated entry passes; background and stale-reentry cases fail on subsequent 3D warmup diagnostics. Six ZIPs/five logs collected; detailed review continues. Ambiguous XCTest restarts remain without inferred cause. |
| [Android comparison 34478725424](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34478725424), `c6ea1dd` | All jobs pass; complete artifact/source collection preserved, final offline evidence review running |
| Android checker correction | Observer accepted; picker review and final hash composition in progress, then production/adaptive retries |
| Native Standard accessibility | Android and iOS implementations progressing independently with reviewers |
| Visual review and screenshots | Next original-image batches in progress; prior published bytes/failures unchanged |

All agents use **gpt-6-astra with max reasoning**. Root owns shared build/export
integration and Git. Collectors, implementers and independent reviewers have
separate boundaries; security review remains source-only.

## Remaining work to finish

1. **Finish implementation and automated native qualification.** Complete actual
   iOS app links/XCTest, fix remaining native failures, run corrected Android
   production modes and four adaptive consumers, finish lifecycle/return/process
   loss, supported native accessibility assertions and visual review. Retest
   affected baselines at delivered source, and complete shipping activation when
   its acceptance gates are met. These are project work, not external blockers.
2. **Execute the physical-device release matrix.** Android-to-iPhone and
   same-platform LAN with two-to-six players, rematches, QR/camera, permissions,
   sharing, network loss/reconnect, host loss, background/lock/privacy/process
   death; minimum/current devices, phones/tablets, orientation and large text;
   actual TalkBack/VoiceOver; startup, frame pacing, memory, battery, sound/haptics
   and network use. Required hardware is unavailable here.
3. **Complete publisher/store setup.** Publisher/support/privacy identities,
   public policy, Android signing and Apple team/provisioning, Play Console/App
   Store Connect listings/disclosures, signed testing tracks/TestFlight and
   submission. These inputs were already requested. Publisher assessment of
   Adobe DNG SDK commercial terms remains; notices alone do not settle it.

## Published deliverables

- Source and coherent milestones pushed through `7012ba0`.
- [Screenshot gallery](screenshots/README.md): **1,717 original app/renderer PNGs**,
  5,376 supporting evidence files and 7,098 checksum entries. Latest batch adds
  133 originals, independently verifies prior bytes/source copies, and is pushed
  at [9a19739](https://github.com/Apdelrahman1911/PartyDeck/commit/9a197392ccaa2605e55f9f751c1e3c3f610e623e).
  More recently generated images are queued for review/publication.
- [Main instructions](../README.md), [validation commands](../scripts/README.md),
  [iOS setup](../iosApp/README.md), [both desktop previews](../godot/comparison/README.md).
- Detailed external gates in [release qualification](release-qualification.md),
  native history in [CI research](research/engine-ci.md), and
  [Godot reviews](../godot/reviews/). Newer successes do not rewrite old failures.
