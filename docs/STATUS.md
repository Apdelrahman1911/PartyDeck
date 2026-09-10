# PartyDeck status report

**Snapshot: 2026-09-10, 20:55 UTC.** Published main source is through `8030efe`;
the published gallery includes the 3,433-original batch in this commit. Production and uninstrumented retained
iOS runs use `c65e264`; later integrations do not inherit their results.
Estimated completion of the original app release scope is **81%**. The added
Godot scope has **3 of 6 acceptance groups complete (50%)**. These are different
scopes and must not be averaged. **The app is not yet ready for production.**

The Standard app is implemented and its original baseline automated checks have passed. Both
real Godot presentations, **2D and 3D**, exist and remain until the user chooses.
Desktop scenarios and all four Android comparison cases passed. Expanded
production-app checks complete Android API 35 native lifecycle and API 36 native
Reveal, selection and Play in debug and optimized builds. Android checker and 2D
phone-layout fixes also pass the current-pack Android production run, and the
separate iOS UIKit layout gate passes. Current iOS production logs now reach
concealed entry, selection, Hide and accepted native Play in both modes, then
fail on Standard return. Adaptive recording/recovery, iOS return and retained
re-entry acceptance remain project work. Earlier passing
baselines do not qualify the current integrated release.

## Completion calculation

| Original release workstream | Weight | Complete | Evidence and remaining limit |
| --- | ---: | ---: | --- |
| Core features and architecture | 30% | 100% implemented | Rules, authority, protocol, transport, practice and app flows exist; physical multiplayer qualification is separate |
| UI, assets and accessibility implementation | 15% | 100% baseline implemented | Screens, assets, preferences and Standard controls exist; the expanded iOS feedback audit now passes after the minimum-height fix. Actual assistive-technology qualification remains |
| Configured baseline automated qualification | 20% | 100% | Android/JVM, shared iOS, Swift TLS and ordinary native app flows pass, including separate Android API 36; added Godot regressions remain separate |
| Builds and unsigned packaging | 15% | 100% | Original Android APK/AAB and iOS Simulator/unsigned device packages build; latest Godot production iOS links also verify |
| Physical-device release validation | 15% | 0% | Physical Android/iPhone release matrix has not run here |
| Publisher, signing and store readiness | 5% | 10% | Configuration and instructions exist; identities, policies, signing, store setup and submission remain |

Weighted result: **80.5%, rounded to 81%**. This is a milestone estimate, not test
coverage, a reliability guarantee or an estimate of time remaining. Reviewed
source and partial native runs do not automatically increase it.

| Additional Godot acceptance group | Status |
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
  reconnection and recoverable errors. Real LAN qualification remains.
- **Transport and privacy:** native TLS, full host-certificate pinning,
  admission/reconnect credentials, bounded messages/queues, replay/revision
  rejection, recipient-specific views and cryptographic randomness.
- **App flows:** Home, Host, Join, Lobby, Rules, Settings, gameplay, round results
  and winner; hand reveal/concealment; persistent sound, haptic and reduced-motion
  preferences. Rules-to-Practice navigation is verified.
- **Assets and architecture:** original cards, symbols, launcher artwork and
  sound; licensed typography and offline notices; shared KMP modules and native
  services. The optional desktop launcher reuses the app.
- **Godot:** real 2D/3D scenes, recipient-safe event bridge, attachment to the
  existing session, Android process-separated host and retained iOS engine with
  Swift adapter. Production native qualification remains incomplete.

The Standard table supplies the agreed accessible native controls route on the
same session. A second complete Godot accessibility overlay is not required.
The canvas has no mobile accessibility adapter. Feasible native assertions are
being extended; actual TalkBack/VoiceOver speech, focus and traversal remain
unqualified. The winner heading now has polite live-region semantics, with seven
passing focused UI tests.

Default shipping configuration exposes no Godot modes. Explicit build-time
qualification profiles enable both for testing. Completing qualification and
shipping activation remain project work. Host migration and restoring matches
after host process death are outside the agreed first-release scope.

## Automated results

Each result belongs to its stated source/run. Repeated runs are not added as new
coverage, and earlier successes are not assigned to a new pack or host.
The newest Android adaptive and retained results have completed original-artifact
audits. Current production iOS has independently audited shared tests; its
ordinary/UIKit successes have job-step evidence, and the original production
log proves progress through source-bound native action checks before Standard
return failures. Full XCTest/attachment audits and exact rejected fields remain pending.

| Verification | Executed result |
| --- | --- |
| Original app, [34428798269](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34428798269), `15ab640` | 118 Android/JVM tests, 83 shared iOS tests, three Swift TLS tests and three native iOS UI tests pass; Android debug/optimized flows and iOS Simulator/unsigned device builds pass |
| Rules framing, [34432935952](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34432935952), `8d8d429` | 118 tests and both APK flows pass; Rules button borders and navigation verified at normal/200% text |
| API 36 ordinary app, [34457458638](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34457458638), `f11f92e` | Both APK flows pass, 86 steps/thirty stage captures per APK; Godot session smoke disabled |
| Android production API 35, [34496267571](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34496267571), `410c938` | 256 JUnit cases in 40 suites and 131 Python checks pass; zero lint errors/eleven warnings. Ordinary debug/optimized flows pass. Debug completes the 2D sequence and reaches 3D renderer-death preparation before the cumulative ten-minute wrapper cutoff; no final debug result exists. Optimized reaches native initialization, then aborts on missing JNI methods |
| Android adaptive API 36, [34496282263](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34496282263), `410c938` | Producer and all four installations pass. Both debug normal/200% cases pass initial native 2D landscape entry. Normal text then fails rotation-retirement observation and video stream validation; 200% held rotation is unsupported and portrait Standard re-entry fails. Both optimized variants abort during JNI initialization. Later scopes, including 3D acceptance, remain unexecuted |
| Android comparison, [34478725424](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34478725424), `c6ea1dd` | All four normal/200% 2D/3D cases and twelve exits pass. Independently verified current pack/source, 445 host observations, 430 applied diagnostics, 112 taps, 42 swipes and 48 captures |
| iOS production, [34496252392](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34496252392), `410c938` | Shared tests: 150 cases/23 suites, one failure in a deferred mode switch. Ordinary native unit tests: 6/6 pass, including all three UIKit layout cases' unguarded assertions. Qualification-only geometry assertions were not compiled in that ordinary bundle. Ordinary UI: 2/3 pass; expanded practice fails the unfiltered hit-area audit for selection-count feedback. The separate layout gate and both production session gates are skipped. Unsigned device artifact retained; ordinary failure prevents the Simulator app archive step |
| Earlier iOS production, [34480503751](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34480503751), `7012ba0` | Simulator/device packages and real link maps verify. Both sessions reach ACTIVE/Ready but fail observation with a roughly 26-point-high native surface; this is the original evidence for the subsequent layout correction |
| iOS native hosts, [34488350932](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34488350932), `4f69429` | Authority 5/5 pass. Retained 2/3 pass: background/resume and repeated entries pass; stale-callback re-entry fails. Both retained qualification flags remain false. Long engine/main-thread intervals are measured; their blocking work is not yet identified |
| iOS retry, [34503244345](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34503244345), `1cd34a3` | Shared native suite passes 156/156 cases in 24 suites; unsigned device job passes. Ordinary app passes 9/9, including all five unchanged unfiltered Standard accessibility audits. Separate guarded UIKit gate passes 2/3: its negative fixture throws a controller-containment exception before the assertion. Both production Godot sessions are skipped. The one-line fixture correction is pushed in `b080780` |
| Android API 35 retry, [34503251315](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34503251315), `1cd34a3` | All four phase exits are zero. Debug native lifecycle: 21 checks pass; optimized: 19 pass and two renderer-death checks are explicitly skipped. Both final native results pass; crash logs are empty. 262 canonical JUnit cases/41 suites and 155 Python tests pass; zero lint errors/eleven warnings. Native Reveal/card/Play was disabled in this run and is not qualified by it |
| Retained diagnostic, [34505106959](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34505106959), `16d828e` | Retained suite passes 1/3. Repeated-entry and stale first-ready fail the unchanged diagnostics wait. One of six sampler invocations yields a usable identity-bound raw stack. Original app streams identify Apple Software Renderer; the stack shows GLES drawing and a separate LLVM compiler queue. This proves observed work, not exclusive causality for a stalled iteration. Sampling may affect timing; further renderer work is active |
| Android adaptive API 36, [34506161751](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34506161751), `d06f83a` | Producer and four installations pass; initial native entries no longer crash. Across 96 scopes: 15 pass, one fails, eight are unsupported and 72 are not reached. Both 1× variants scroll the wrong Standard pane during unsupported recovery. Debug 2× rejects a clipped read-only concealment marker; original before-UP success is unproved. Optimized 2× passes twelve 2D/3D entry/return/leave checks but held rotations and split-window automation remain unsupported. No held-transition or split acceptance is claimed |
| Android production API 36, [34506173394](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34506173394), `d06f83a` | Run succeeds: debug 30 native checks pass; optimized 28 pass and two renderer-death checks are explicitly skipped. 262 canonical JUnit cases and 172 Python tests pass. Original XML verifies actual Reveal, slot-zero selection and one Play in both modes/APKs: 2D hand count 5 → 4; 3D concrete same-round result. This acceptance uses the earlier `d6adbba1…` pack |
| iOS production retry, [34509634154](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34509634154), `b080780` | Shared 156/156, ordinary 9/9 with five unchanged unfiltered accessibility audits, and separate guarded UIKit layout 3/3 pass. Unsigned device job passes. Both production sessions fail during initial entry. The later original-stream audit identifies the second fresh-frame wait: presented frames remain 3 in 2D and 4 in 3D while other currentness fields advance. Final observations show ACTIVE/Ready and a 402 × 657-point surface; native selection/Play, Standard return, Leave and re-entry remain unreached |
| Initial MSAA diagnostic, [34512412329](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34512412329), `c058bdc` | All three retained cases stop at the unchanged exact-pack guard before native preparation. No engine iteration or rendering experiment is reached; no rendering, speed or MSAA-effect conclusion follows |
| Latest Android adaptive API 36, [34514544296](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34514544296), `286b7ff` | Producer and four installations pass. Completed original-byte/source audit verifies 28 passed, four failed, twelve unsupported and 52 unreached scopes out of 96. Each case passes six 2D lifecycle checks plus split capability. All twelve original recorder startups lack observed growth in their eight-second windows. All four cases then fail preparation/stabilization after unavailable split-entry recording, with owned-split cleanup errors. The `3d-landscape.initial-landscape` label does not establish a 3D launch: the 2D renderer remains active and no split-entry request is observed. Held transitions and split interaction remain unqualified |
| Android adaptive retry, [34528538284](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34528538284), `8030efe` | Dispatched with integrated recorder/recovery changes after 259 host tests and independent source/lifetime review. Debug and optimized builds, normal/200% text, both modes: native results pending |
| Android production API 36, [34515669045](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34515669045), `0f00f17` | Android job succeeds; the combined workflow fails because its separate iOS job fails. Debug: 30 native checks pass; optimized: 28 pass and two renderer-death checks are explicitly skipped. 262 JUnit cases/41 suites and 207 Python cases pass; zero lint errors/eleven warnings. Four original Reveal → slot-zero → one Play chains pass the same-round Standard public-result acceptance branch, with zero corrective swipes and verified sampled ownership/teardown. Current outcome XML has no card nodes: no current five-to-four or unchecked remaining-hand observation is claimed. Package audit binds the `557b2297…` pack |
| iOS in combined production, [34515669045](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34515669045), `0f00f17` | Completed original-artifact audit: shared 156/156, ordinary 9/9 with five unchanged unfiltered accessibility audits, and separate guarded UIKit layout 3/3 pass; unsigned device job passes. Production sessions are 0/2. Both fail initial entry at the second `live(after: opened)` fresh-frame wait: presented frames remain 4 in 2D and 3 in 3D while other currentness fields advance. Later gameplay/return checkpoints remain unreached. This iOS failure makes the combined workflow fail despite Android success |
| Corrected MSAA diagnostic, [34515678208](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34515678208), `3616960` | After the exact diagnostic pack pin correction, native producers pass and the retained suite executes: background/resume and repeated 2D/3D entry pass; stale first-ready/re-entry fails the current-renderer-diagnostics wait. Result: 2/3, overall failure. This isolated diagnostic does not establish production acceptance or an MSAA performance cause |
| Current iOS production, [34520365907](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34520365907), `c65e264` | Workflow fails. Shared XML independently verifies 156/156 cases in 24 suites; export and unsigned device job pass. Ordinary app and guarded UIKit steps succeed. The original production log, checked against exact throwing test control flow, verifies both modes reach concealed entry with advancing frames, real native selection/Hide and the authority-receipt accepted-Play checks. Both then fail on Standard return: 2D controller/port health assertion; 3D native-close/concealed-Standard return wait. Production: 0/2 by original log. Full XCTest/attachment audit and exact rejected fields remain pending; later return/action/re-entry acceptance is unproved |
| Current retained iOS, [34520375602](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34520375602), `c65e264` | Completed original-result/source/producer audit: background/concealment and repeated 2D/3D entries pass; stale first-ready/close-completion re-entry fails the unchanged diagnostics wait. Result: 2/3, exit 65, overall failure; retained lifecycle and same-process re-entry remain unqualified. Last rejected second-3D observation is prepared / WAITING_FOR_READY with empty diagnostics; a later observation passes the predicate. Main `557b2297…` pack and reviewed redraw are bound. These observations do not identify startup phase cost or MSAA/redraw causality |
| iOS startup-phase diagnostic, [34525504734](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34525504734), `fa0fabb` | Original artifacts/source audited: background and repeated 2D/3D entry pass; stale first-ready/re-entry fails, result 2/3 and exit 65. Complete samples measure 13.46 s and 11.69 s between pre/post-draw callback deliveries. The later snapshot still fails the cover predicate. Stack sampling is off, main pack unchanged. These intervals do not isolate GPU, shader or mesh cost; production qualification remains open |
| Packed renderer, `4d8bd92` / `c6ea1dd` | 677 real-render assertions pass: 155 boundary, 216 terminal-return and 306 redraw |

Historical screenshot reports are excluded from current test totals. The latest
API 35 report also verifies zero historical JUnit copies in its uploaded report.
Disposable CI signing is
not publisher signing. Comparison acceptance does not qualify the production
shell, physical LAN or hardware GPUs. API 36 native Play acceptance is inferred
from the immediate Standard UI outcome, with sampled ownership/currentness;
it is not an internal authority-revision receipt. The older `d06f83a` run
retains its own 2D five-to-four observation; the current `0f00f17` run shows
same-round public results in all four cases. Its 3D outcomes include later
opponent actions and do not directly expose acceptance of the human input.
The exact `0f00f17` and `c65e264` source snapshots are explicitly derived
from verified retained source; neither is a newly collected target-head archive.

## Fixes and parallel work

| Work | Done | What remains |
| --- | --- | --- |
| iOS linkage and test headers | Corrected archive extraction and native header search paths. Actual Simulator/device links, sole framework ownership, unit compilation and baseline XCTest pass | Closed for the tested packages; retain regression checks |
| Android presentation selection | Bounded pending choice integrated; 73 focused controller/lifecycle/observation tests passed. Completed API 35/36 production runs launch both modes in debug and optimized APKs, including the current main pack at `0f00f17` | Complete adaptive lifecycle acceptance and preserve regression checks for later source |
| Common deferred mode switch | Narrow correction integrated and pushed after two independent source reviews; 35 focused common tests pass. The original failing iOS regression and all six new common cases now pass in the 156-case native suite | Complete real production mode switching; factory, focus, binding, privacy and the original five-second deadline remain enforced |
| Optimized Android JNI | Independently reviewed retention rules pushed. Rebuilt APK passes all 122 selected native-interface declarations, versus 69/122 originally. Completed API 35/36 optimized lifecycle and API 36 gameplay pass; those optimized APKs share the complete DEX of the audited APK | Retain checks on current-source packages. The static audit covers the exercised string/primitive boundary, not every optional Godot reflection feature |
| Android adaptive scenarios | Recorder setup, split recovery and entry/exit wiring are integrated in `8030efe`; 259 root host tests pass. Independent review passes 29 cleanup, 18 composed-flow and 22 lifetime cases; final source pins/workflow match | Complete the full four-consumer native retry `34528538284`, preserving before-UP proof, visibility, privacy, deadlines and recorder growth. Unsupported/unreached scopes remain open |
| Android recorder foundation | Recorder observation/lifecycle foundation is pushed in `9b2a8c9`: 225 root host tests and 26 independent probes pass, with source-only security approval. Split integration is pushed in `8030efe` | Execute the integrated native qualification. Host-only results do not alter the earlier failed adaptive run |
| Android runtime budget | Bounded twenty-minute cumulative budget on API 35 and 36; both completed production retries finish debug and optimized sequences with passing final results | Closed for those tested runs; retain unchanged per-stage deadlines and current-source regression checks |
| iOS production layout | Content sizing, hidden-ancestor observation and the one-line negative-fixture correction are integrated. The actual separate guarded UIKit gate now passes 3/3; production failure observations show the enlarged native surface | Complete real production entry, interaction and return acceptance; the layout gate alone does not qualify engine responsiveness |
| iOS native responsiveness | Earlier `b080780` and `0f00f17` runs stall at the second entry-frame wait. Reviewed diagnostic redraw is integrated in `c65e264`, with nine independent source-derived host probes. Its production log now reaches advancing concealed entry and accepted native Play in both modes, then fails on Standard return. Retained retry passes 2/3. Separate startup-phase diagnostic is dispatched at `fa0fabb` | Audit exact rejected return fields, resolve production Standard return and retained READY/re-entry failures, and complete acceptance. The earlier static-frame failure is not assigned to this run; source settings and partial passes do not establish exclusive causality |
| Retained pack preflight | `67fe711` adds retained-only actual pack size/hash and unique native-pin checks before Swift build/runtime. Nineteen root host tests, seven independent probes and the real current pack/pin check pass; the subsequent phase run passes staging and executes native tests | Preserve the native guards; no separate native rerun is needed solely for this preflight |
| Android Standard accessibility | Extended five-card, checked-state, selection-limit, Hide and Standard action checks pass in completed API 35/36 sequences. Current engine actions clear local renderer selection and pass the public-result acceptance branch | Complete adaptive return scenarios and preserve later-source regression checks; actual TalkBack remains separate. Current public-result XML has zero cards, so unchecked remaining Standard cards are an evidence limit, not an added release gate |
| iOS Standard accessibility | Feedback semantics have a 48-dp minimum height. Seven layout tests and ordinary iOS 9/9 pass, including five unchanged unfiltered audits. The failed production sessions also reach five Standard hand checkpoints each before native entry | Qualify authoritative Standard action after Godot return. Those production checkpoints do not invoke the ordinary unfiltered audits; actual VoiceOver remains separate |
| Android native gameplay evidence | Qualification geometry and the real Reveal/card/Play checker are integrated. The current `0f00f17` / `557b2297…` original audit verifies one actual Play per mode/APK and immediate same-round Standard public results, with 198 stable sampled owner records and teardown | Preserve newer-source regression checks and complete adaptive/physical qualification. Local renderer state and sampled observations remain distinct from an internal authority receipt |
| 2D initial phone layout | One-file Reveal-fit correction and canonical export are integrated. Twenty-two geometry cases, source and packed input/privacy/drag checks pass; the current `557b2297…` native API 36 run completes 2D Reveal/selection/Play in both APKs | Complete remaining adaptive visual/interaction and hardware acceptance. The existing 200% scrolling path remains; 3D source is unchanged on main |
| 3D large-text scrolling | Independent audit verifies seven original images and 29 fully clipped-safe touch geometries. Tested controls remain reachable by native scrolling; no source patch is warranted by this evidence | Human usability and hardware acceptance remain separate |
| Screenshots | 3,433 originals plus 13 supplements are published, with 14,123 evidence files, 17,561 checksum entries and 129 collections. All 4,413 paths in the latest delta were independently hash-verified; preserved original bytes remain unchanged | The 618 additions include 53 direct views, 84 prior published-byte matches and 481 explicitly unviewed originals. Seventeen new videos remain unviewed. Later retained/phase and current iOS production batches remain pending |

Agents use **gpt-6-astra with max reasoning**. Android, iOS, checker,
accessibility and rendering work proceeds concurrently with independent review.
Root owns shared builds, integration and Git. Security review remains source-only.

The current main PCK is **1,549,560 bytes / 136 entries**, SHA-256
`557b2297bed133a433acc25efa4837462465dd4e06da659ae5a4cbd792f77fe0`.
It contains the integrated 2D layout correction and is byte-bound to the current
Android production and `c65e264` retained runs. The `c65e264` 3D source requests
MSAA_2X; effective GPU sample count is not measured. Its iOS diagnostics redraw
changes native runtime source, while the PCK stays unchanged. The separate MSAA diagnostic pack
is **1,549,656 bytes / 136 entries**, SHA-256
`c8d2b0989524c66715fd7469b7a8315a6fd2fb8563ec87bd2294d60b4ebbcd4a`.
Each branch's native module pins its own exact pack. Independent review verifies
that each pin change replaces only one hash literal; all guard logic remains.
Earlier accepted Android runs retain their original `d6adbba1…` pack identity.
The v7 timing instrumentation, reviewed CoreAudio dormancy and main-loop access
patches remain; the optional mouse patch remains unapplied. No cover, lifecycle,
input-currentness or timeout gate is relaxed for a pass.

## What still needs to be done to finish

1. **Complete implementation and automated native qualification.** Qualify
   the integrated Android recorder/recovery changes in affected adaptive
   cases, and resolve iOS Standard return and retained READY/re-entry failures.
   Current-pack Android production gameplay passes; current iOS logs reach
   accepted native Play but fail return. Complete current iOS production and
   retained acceptance plus later-source regressions. Complete both platforms' 2D/3D gameplay,
   lifecycle/return/process-loss and remaining adaptive cases. Finish supported
   accessibility assertions and visual review, rerun affected baselines, publish
   the next reviewed evidence batch, and enable shipping Godot modes only after
   their gates pass. This software work continues without publisher or
   physical-hardware inputs.
2. **Execute physical-device release validation.** Android-to-iPhone and
   same-platform LAN with two-to-six players, rematches, QR/camera, permissions,
   sharing, network loss/reconnect, host loss, background/lock/privacy/process
   death; minimum/current devices, phones/tablets, orientation and large text;
   actual TalkBack/VoiceOver; startup, frame pacing, memory, battery, sound/haptics
   and network use. Required hardware is unavailable here.
3. **Complete publisher/store setup.** Publisher/support/privacy identities,
   public policy, Android signing and Apple team/provisioning, Play Console/App
   Store Connect listings/disclosures, signed test tracks/TestFlight and
   submission. Publisher assessment of Adobe DNG SDK commercial terms remains;
   notices alone do not settle it.

## Published deliverables

- Main source milestones pushed through `8030efe`; the published gallery includes the 3,433-original batch in this commit.
  Android adaptive retry `34528538284` is running. The separate `fa0fabb`
  startup-phase diagnostic completes 2/3 and remains unqualified.
- [Screenshot gallery](screenshots/README.md): **3,433 original PNGs plus 13 supplemental images**,
  with 14,123 evidence files, 17,561 checksum entries and 129 collections. The
  618-image addition preserves its actual run/failure and viewing context.
  Later retained/phase and current iOS production evidence remains pending.
- [Verified Android 2D/3D preview download](../godot/comparison/README.md),
  [main instructions](../README.md), [validation commands](../scripts/README.md)
  and [iOS setup](../iosApp/README.md).
- [Release qualification](release-qualification.md),
  [CI research](research/engine-ci.md) and [Godot reviews](../godot/reviews/).
  New successes do not rewrite earlier failed results.
