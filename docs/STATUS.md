# PartyDeck status report

**Snapshot: 2026-09-10, 23:04 UTC.** Published main source is through `4ee4563d`;
the 3,559-original gallery batch was published in `e3a1478`. Main now uses
the `541ded4c…` pack from `6de14e2`. Android gameplay at `0f00f17` and iOS at
`c65e264` used the earlier `557b2297…` pack; they do not qualify the new pack.
On the new pack, retained iOS passes 2/3 and focused production passes 1/2;
both complete acceptance gates remain unqualified.
Estimated completion of the original app release scope is **81%**. The added
Godot scope has **3 of 6 acceptance groups complete (50%)**. These are different
scopes and must not be averaged. **The app is not yet ready for production.**

The Standard app is implemented and its original baseline automated checks have passed. Both
real Godot presentations, **2D and 3D**, exist and remain until the user chooses.
Desktop scenarios and all four Android comparison cases passed. Recorded
production runs complete Android API 35 native lifecycle and API 36 native
Reveal, selection and Play in debug and optimized builds, including the 2D
phone-layout correction on `557b2297…`. The separate iOS UIKit layout gate passes.
The completed `c65e264` iOS artifact audit proves concealed entry, selection, Hide
and accepted native Play in both modes, followed by Standard-return failures.
Reviewed iOS close fixes and 3D resource reuse are now integrated. On the new
pack, the focused 3D production case passes; 2D fails an accessibility lookup
after Leave. Retained iOS still passes 2/3. Android adaptive failures, iOS cleanup
and retained re-entry acceptance remain project work. Earlier passing baselines do not
qualify the current integrated release.
Standard large-text control ordering and the iOS status-lookup correction are
now pushed. Authentic JVM checks pass 2/2 targeted Standard-return cases and
9/9 affected layout cases. Full Validate `34538972728` is running on `dd6df8a5`
with Android API 36 and both Godot session flags; it has no final result yet.
The Android diagnostic update in `4ee4563d` passes all 282 host tests and
20 independent recorder/input lifetime cases. Adaptive run `34540229407` is
running its one producer and four consumers on that commit, with native results pending.

## Completion calculation

| Original release workstream | Weight | Complete | Evidence and remaining limit |
| --- | ---: | ---: | --- |
| Core features and architecture | 30% | 100% implemented | Rules, authority, protocol, transport, practice and app flows exist; physical multiplayer qualification is separate |
| UI, assets and accessibility implementation | 15% | 100% baseline implemented | Screens, assets, preferences and Standard controls exist; the expanded iOS feedback audit now passes after the minimum-height fix. Actual assistive-technology qualification remains |
| Configured baseline automated qualification | 20% | 100% | Android/JVM, shared iOS, Swift TLS and ordinary native app flows pass, including separate Android API 36; added Godot regressions remain separate |
| Builds and unsigned packaging | 15% | 100% | Original Android APK/AAB and iOS Simulator/unsigned device packages build; audited `c65e264` Godot production iOS links also verify |
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
The `c65e264` production iOS audit now binds complete original archives,
XCTest results, package/source identity and exact return predicates. The earlier
retained audits retain their recorded scopes. The latest Android adaptive audit
now binds all four consumer results and installed packages. New-pack retained
original/source/producer evidence verifies 2/3. Focused production iOS verifies
1/2 with exact source and packaged-app/PCK checks; its full-workflow exclusions
remain explicit.

| Verification | Executed result |
| --- | --- |
| Original app, [34428798269](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34428798269), `15ab640` | 118 Android/JVM tests, 83 shared iOS tests, three Swift TLS tests and three native iOS UI tests pass; Android debug/optimized flows and iOS Simulator/unsigned device builds pass |
| Rules framing, [34432935952](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34432935952), `8d8d429` | 118 tests and both APK flows pass; Rules button borders and navigation verified at normal/200% text |
| API 36 ordinary app, [34457458638](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34457458638), `f11f92e` | Both APK flows pass, 86 steps/thirty stage captures per APK; Godot session smoke disabled |
| Android production API 35, [34496267571](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34496267571), `410c938` | 256 JUnit cases in 40 suites and 131 Python checks pass; zero lint errors/eleven warnings. Ordinary debug/optimized flows pass. Debug completes the 2D sequence and reaches 3D renderer-death preparation before the cumulative ten-minute wrapper cutoff; no final debug result exists. Optimized reaches native initialization, then aborts on missing JNI methods |
| Android adaptive API 36, [34496282263](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34496282263), `410c938` | Producer and all four installations pass. Both debug normal/200% cases pass initial native 2D landscape entry. Normal text then fails rotation-retirement observation and video stream validation; 200% held rotation is unsupported and portrait Standard re-entry fails. Both optimized variants abort during JNI initialization. Later scopes, including 3D acceptance, remain unexecuted |
| Android comparison, [34478725424](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34478725424), `c6ea1dd` | All four normal/200% 2D/3D cases and twelve exits pass. Independently verified that run’s pack/source, 445 host observations, 430 applied diagnostics, 112 taps, 42 swipes and 48 captures |
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
| Android adaptive API 36, [34514544296](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34514544296), `286b7ff` | Producer and four installations pass. Completed original-byte/source audit verifies 28 passed, four failed, twelve unsupported and 52 unreached scopes out of 96. Each case passes six 2D lifecycle checks plus split capability. All twelve original recorder startups lack observed growth in their eight-second windows. All four cases then fail preparation/stabilization after unavailable split-entry recording, with owned-split cleanup errors. The `3d-landscape.initial-landscape` label does not establish a 3D launch: the 2D renderer remains active and no split-entry request is observed. Held transitions and split interaction remain unqualified |
| Android adaptive retry, [34528538284](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34528538284), `8030efe` | Completed original/source/producer/installed-package audit: four installations pass; 66 of 96 adaptive scopes pass, two fail, 28 are unreached and zero are unsupported. Both normal-text variants pass all 24 scopes. Debug 200% passes 17, then fails 3D seascape held rotation; six scopes are unreached. Optimized 200% passes initial 2D landscape, then fails held rotation; 22 are unreached. Both failures lack required concealed-before-UP proof. All 23 recorder startup-growth and observer-join receipts pass, but clips retain `captured-review-required`. Workflow fails. Pack: earlier `557b2297…`; adaptive checks do not qualify native gameplay or transition pixels |
| Android production API 36, [34515669045](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34515669045), `0f00f17` | Android job succeeds; the combined workflow fails because its separate iOS job fails. Debug: 30 native checks pass; optimized: 28 pass and two renderer-death checks are explicitly skipped. 262 JUnit cases/41 suites and 207 Python cases pass; zero lint errors/eleven warnings. Four original Reveal → slot-zero → one Play chains pass the same-round Standard public-result acceptance branch, with zero corrective swipes and verified sampled ownership/teardown. Its outcome XML has no card nodes: no current five-to-four or unchecked remaining-hand observation is claimed. Package audit binds the `557b2297…` pack |
| iOS in combined production, [34515669045](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34515669045), `0f00f17` | Completed original-artifact audit: shared 156/156, ordinary 9/9 with five unchanged unfiltered accessibility audits, and separate guarded UIKit layout 3/3 pass; unsigned device job passes. Production sessions are 0/2. Both fail initial entry at the second `live(after: opened)` fresh-frame wait: presented frames remain 4 in 2D and 3 in 3D while other currentness fields advance. Later gameplay/return checkpoints remain unreached. This iOS failure makes the combined workflow fail despite Android success |
| Corrected MSAA diagnostic, [34515678208](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34515678208), `3616960` | After the exact diagnostic pack pin correction, native producers pass and the retained suite executes: background/resume and repeated 2D/3D entry pass; stale first-ready/re-entry fails the current-renderer-diagnostics wait. Result: 2/3, overall failure. This isolated diagnostic does not establish production acceptance or an MSAA performance cause |
| iOS production, [34520365907](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34520365907), `c65e264` | Completed original-artifact/source audit: shared 156/156 cases in 24 suites, ordinary 9/9 with all five unchanged unfiltered accessibility audits, and separate guarded UIKit 3/3 pass. Simulator and unsigned-device packages verify. Production: 0/2. Both modes pass concealed entry with advancing frames, real native selection/Hide and one authority-accepted native Play (hand 5 → 4). Standard return fails: 2D health rejects `port.quarantined=true`; 3D’s first dormant guard rejects `native.authorityForegroundGrant=true`. Cached endpoint observations do not establish close timing. Later concealed-return, Leave, re-entry and final-cleanup assertions are unreached. Pack: `557b2297…` |
| Retained iOS, [34520375602](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34520375602), `c65e264` | Completed original-result/source/producer audit: background/concealment and repeated 2D/3D entries pass; stale first-ready/close-completion re-entry fails the unchanged diagnostics wait. Result: 2/3, exit 65, overall failure; retained lifecycle and same-process re-entry remain unqualified. Last rejected second-3D observation is prepared / WAITING_FOR_READY with empty diagnostics; a later observation passes the predicate. The `557b2297…` pack and reviewed redraw are bound. These observations do not identify startup phase cost or MSAA/redraw causality |
| iOS startup-phase diagnostic, [34525504734](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34525504734), `fa0fabb` | Original artifacts/source audited: background and repeated 2D/3D entry pass; stale first-ready/re-entry fails, result 2/3 and exit 65. Complete samples measure 13.46 s and 11.69 s between pre/post-draw callback deliveries. The later snapshot still fails the cover predicate. Stack sampling is off, main pack unchanged. These intervals do not isolate GPU, shader or mesh cost; production qualification remains open |
| Retained iOS after close/Card3D integration, [34531867786](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34531867786), `6de14e2` | Completed original/source/producer audit preserves all five ZIPs and 148 selected originals. Background/concealment and repeated 2D/3D entries pass; stale first-Ready/close-completion re-entry fails. Result: 2/3, exit 65; retained lifecycle and same-process re-entry remain unqualified. The rejected wait has unapplied scene state and a visible privacy cover; later metrics have applied state but the cover remains visible. Later closure/old-handle/Play assertions are unreached. Stack sampling is off. Actual engine/framework/PCK bytes and native staged/source receipts bind `541ded4c…`. No latency or exclusive-cause conclusion follows |
| Focused iOS production, [34532837557](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34532837557), `e4871e1` | Original log, summary and gate agree: 1/2, exit 65, workflow failure. The 3D production case passes; 2D fails an accessibility snapshot lookup for `godot-session-status` after Leave. Exact source and actual Simulator app/PCK bytes verify `541ded4c…`; standalone native archive hashes remain runner-receipt evidence. Shared tests, ordinary app/interop, guarded UIKit and unsigned-device validation are excluded from this focused selection. This run does not replace full validation |
| Standard large-text JVM layout, `eeb1bfb7` | Authentic root execution passes StandardReturnLayoutTest 2/2 at 411 × 662 dp and 200% text: fresh and returned concealed Show hand is fully visible before scrolling. Final GameplayLayoutTest 7/7 and PresentationLayoutTest 2/2 also pass, including six-seat roster reachability and selection preservation. Independent source/pixel reviews approve the bounded change. JVM results do not establish Android nonlinear-font or held-input native acceptance |
| Full Validate after UI/lookup fixes, [34538972728](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34538972728), `dd6df8a5` | Running: platform=all, Android API 36, android_godot_session=true and ios_godot_session=true. This is the full workflow, with ordinary/shared/package gates and both platforms' production-session selections enabled. No final job, suite or native acceptance result is claimed |
| Android adaptive after large-text correction, [34540229407](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34540229407), `4ee4563d` | Running: debug and optimized APKs, normal and 200% text, both Godot modes. The updated checker retains bounded rejected original XML after recorder cleanup. All 282 host tests and 20 independent lifetime executions pass; these do not establish a native result |
| Card3D source-project and package checks, `6de14e2` | Real desktop source-project execution passes 560 numbered assertions: 306 redraw, 216 terminal/lifetime and 38 resource sharing/lifetime. All 20 baseline/candidate PNG pairs are byte-identical on the tested Godot/OpenGL llvmpipe/Xvfb stack. Separate canonical export and source/packed scene checks pass; independent package review finds exactly two compiled-script changes and 134 unchanged entries. Nineteen pack-preflight host checks pass. No native latency benefit is established |
| Packed renderer, `4d8bd92` / `c6ea1dd` | 677 real-render assertions pass: 155 boundary, 216 terminal-return and 306 redraw |

Historical screenshot reports are excluded from current test totals. The latest
API 35 report also verifies zero historical JUnit copies in its uploaded report.
Disposable CI signing is
not publisher signing. Comparison acceptance does not qualify the production
shell, physical LAN or hardware GPUs. API 36 native Play acceptance is inferred
from the immediate Standard UI outcome, with sampled ownership/currentness;
it is not an internal authority-revision receipt. The older `d06f83a` run
retains its own 2D five-to-four observation; the `0f00f17` run shows
same-round public results in all four cases. Its 3D outcomes include later
opponent actions and do not directly expose acceptance of the human input.
The exact `0f00f17`, `c65e264`, `8030efe` and `6de14e2` source snapshots are
explicitly derived from verified retained source; none is a newly collected
target-head archive. The `c65e264` predicate proof has been reconciled to the
complete original ZIP. Its 2D attachment preserves the decoded health rejection;
its 3D attachment preserves the last decoded observation before timeout. These
cached documents do not expose every poll or the exact native/Swift interleaving.
The recovered XCTest accessibility stream separately binds 294 values. Fourteen
intermediate 2D samples show covered, input-disabled, empty-tree cleanup with the
native surface still attached and no frame/draw/iteration progress before
quarantine. The exact UIKit stop selector or Swift timeout callback is not logged.

## Fixes and parallel work

| Work | Done | What remains |
| --- | --- | --- |
| iOS linkage and test headers | Corrected archive extraction and native header search paths. Actual Simulator/device links, sole framework ownership, unit compilation and baseline XCTest pass | Closed for the tested packages; retain regression checks |
| Android presentation selection | Bounded pending choice integrated; 73 focused controller/lifecycle/observation tests passed. Completed API 35/36 production runs launch both modes in debug and optimized APKs, including `0f00f17` with the earlier `557b2297…` pack | Complete adaptive lifecycle acceptance and preserve regression checks for later source |
| Common deferred mode switch | Narrow correction integrated and pushed after two independent source reviews; 35 focused common tests pass. The original failing iOS regression and all six new common cases now pass in the 156-case native suite | Complete real production mode switching; factory, focus, binding, privacy and the original five-second deadline remain enforced |
| Optimized Android JNI | Independently reviewed retention rules pushed. Rebuilt APK passes all 122 selected native-interface declarations, versus 69/122 originally. Completed API 35/36 optimized lifecycle and API 36 gameplay pass; those optimized APKs share the complete DEX of the audited APK | Retain checks on current-source packages. The static audit covers the exercised string/primitive boundary, not every optional Godot reflection feature |
| Android adaptive scenarios | Recorder setup, split recovery and entry/exit wiring are integrated in `8030efe`; 259 root host tests pass. Independent review passes 29 cleanup, 18 composed-flow and 22 lifetime cases. Completed native/source/package audit verifies 66 adaptive passes, two failures and 28 unreached scopes; both normal-text variants pass all 24 | Resolve the two failed 200% held returns and complete remaining adaptive gates on current main/new pack. Preserve before-UP proof, marker visibility, privacy, deadlines and recorder growth; transition pixel review remains separate |
| Android recorder foundation | Recorder observation/lifecycle foundation is pushed in `9b2a8c9`: 225 root host tests and 26 independent probes pass, with source-only security approval. Split integration is pushed in `8030efe`. Its completed native audit verifies positive startup growth before eight seconds and joined observers for all 23 original recordings | Complete visual/transition privacy review and remaining adaptive failures on current source. All original clips retain `captured-review-required`; recorder growth alone does not qualify their pixels |
| Android runtime budget | Bounded twenty-minute cumulative budget on API 35 and 36; both completed production retries finish debug and optimized sequences with passing final results | Closed for those tested runs; retain unchanged per-stage deadlines and current-source regression checks |
| iOS production layout | Content sizing, hidden-ancestor observation and the one-line negative-fixture correction are integrated. The actual separate guarded UIKit gate now passes 3/3; production failure observations show the enlarged native surface | Complete real production entry, interaction and return acceptance; the layout gate alone does not qualify engine responsiveness |
| iOS native responsiveness | Earlier `b080780` and `0f00f17` runs stall at the second entry-frame wait. Reviewed redraw in `c65e264` reaches advancing entry and accepted native Play, then distinct return failures. After the close/Card3D fixes, focused `e4871e1` passes its 3D case; 2D fails a status lookup after Leave. New-pack retained `6de14e2` remains 2/3 | Qualify the pushed status-lookup correction in full Validate and resolve the retained scene/cover wait, then complete native acceptance. The earlier static-frame failure is not assigned to these later runs; measured callback intervals and partial passes do not isolate GPU, shader or mesh cost |
| Standard large-text controls | `eeb1bfb7` places hand/actions before secondary roster/history and moves the genuine Show hand control ahead of concealed-hand decoration. Public turn/rank/claim context, privacy and selection semantics remain. The strict fresh/return fixture passes 2/2; final gameplay/presentation layouts pass 9/9. Independent review approves source and affected pixels | Complete Android current-source native and held-return qualification. JVM font scale and screenshots do not replace Android nonlinear-font rendering, before-UP proof or TalkBack |
| iOS production status lookup | `dd6df8a5` obtains status identity and value from one captured application snapshot. Two independent source reviews approve the exact change; decoding, privacy/currentness, authority/cleanup predicates, deadlines and failure propagation remain unchanged | Actual SDK compilation and native execution of the corrected production path remain pending in full Validate `34538972728`; earlier `e4871e1` remains 1/2 |
| Android CI evidence uploads | `54a033ff` adds three renderer/toolchain evidence upload globs. The iOS workflow body and qualification gates remain unchanged | Verify the added producer evidence in the current full Validate artifacts; upload selection is not a native acceptance result |
| Android rejected-return evidence | `4ee4563d` retains bounded original rejected UI dumps after all recorder/input cleanup, with the producer pinned to the reviewed checker. All 282 host tests and 20 independent lifetime checks pass; source/privacy and pin/workflow reviews approve the change | Collect the new native adaptive result. Stored rejected XML is diagnostic evidence and cannot replace actual concealed-return or before-UP acceptance |
| iOS close and leave authority | `0a2d0a0` waits for the native close result before UIKit dismissal and revokes current foreground/Ready permission on admitted leave. Retained assertions now require both permission fields to be present and false. Independent source reviews approve the exact fixes; deadlines, neutral maintenance and existing cleanup guards are preserved. New-pack retained is 2/3; focused production is 1/2 with 3D passing | Complete 2D post-Leave cleanup and retained re-entry qualification. Source review and partial retained passes do not establish complete runtime acceptance |
| Card3D resource reuse | `6de14e2` shares three meshes and two solid materials within each presentation while keeping private faces, nodes, labels and input closures fresh. Source-project behavior/pixel checks pass; canonical export and independent pack/pin binding pass | Qualify the new pack in native production/retained execution. Native latency improvement and hardware rendering remain unproved |
| Focused iOS production workflow | `e4871e1` adds the focused selection after independent release/security review and integrated actionlint. The full workflow and two production tests retain their existing behavior; usage documentation is pushed in `3e09f2c`. Run `34532837557` executes both cases and finishes 1/2 | Resolve the failed 2D case and complete the unchanged production gates. Shared, ordinary, UIKit and unsigned-device checks still require full validation when affected |
| Retained pack preflight | `67fe711` adds retained-only actual pack size/hash and unique native-pin checks before Swift build/runtime. Nineteen original root host tests, seven independent probes and the then-current pack/pin check pass; the phase run passes staging and executes native tests. After repin, nineteen root host checks and independent package/pin binding pass again; actual new-run producer/staged bytes also verify | Preserve the native guards. No separate native rerun is needed solely for this preflight |
| Android Standard accessibility | Extended five-card, checked-state, selection-limit, Hide and Standard action checks pass in completed API 35/36 sequences. The `0f00f17` engine actions clear local renderer selection and pass the public-result acceptance branch | Complete adaptive return scenarios and preserve later-source regression checks; actual TalkBack remains separate. That run’s public-result XML has zero cards, so unchecked remaining Standard cards are an evidence limit, not an added release gate |
| iOS Standard accessibility | Feedback semantics have a 48-dp minimum height. Seven layout tests and ordinary iOS 9/9 pass, including five unchanged unfiltered audits. The failed `c65e264` production sessions also reach five Standard hand checkpoints each before native entry | Qualify authoritative Standard action after Godot return. Those production checkpoints do not invoke the ordinary unfiltered audits; actual VoiceOver remains separate |
| Android native gameplay evidence | Qualification geometry and the real Reveal/card/Play checker are integrated. The `0f00f17` / `557b2297…` original audit verifies one actual Play per mode/APK and immediate same-round Standard public results, with 198 stable sampled owner records and teardown | Preserve newer-source regression checks and complete adaptive/physical qualification. Local renderer state and sampled observations remain distinct from an internal authority receipt |
| 2D initial phone layout | One-file Reveal-fit correction and canonical export are integrated. Twenty-two geometry cases, source and packed input/privacy/drag checks pass; the earlier `557b2297…` native API 36 run completes 2D Reveal/selection/Play in both APKs | Complete remaining adaptive visual/interaction and hardware acceptance. The existing 200% scrolling path remains; later 3D resource changes require their own native qualification |
| 3D large-text scrolling | Independent audit verifies seven original images and 29 fully clipped-safe touch geometries. Tested controls remain reachable by native scrolling; no source patch is warranted by this evidence | Human usability and hardware acceptance remain separate |
| Screenshots | `e3a1478` publishes 3,559 originals plus 13 supplements, with 14,955 evidence files, 18,519 checksum entries and 135 collections. All 979 paths in the latest delta were independently hash-verified; preserved original bytes remain unchanged | The 126 additions include nine owner views, two prior assets views, 36 reviewed published-byte matches and 79 explicitly unviewed originals. Four new videos remain unviewed/undecoded. Android `34528538284` transition-video review and later native-run batches remain outside this publication |

Agents use **gpt-6-astra with max reasoning**. Android, iOS, checker,
accessibility and rendering work proceeds concurrently with independent review.
Root owns shared builds, integration and Git. Security review remains source-only.

The current main PCK from `6de14e2` is **1,550,440 bytes / 136 entries**, SHA-256
`541ded4c5074b56a9e320882a23f357ff8162520fac099e32567ac3a678f2751`.
It retains the 2D layout correction and adds Card3D resource reuse. Independent
package review verifies exactly two changed compiled scripts and 134 unchanged
entries; export settings and all other payloads are unchanged. The native pack
pin is updated by one literal replacement. Retained `34531867786` verifies actual
engine/framework/PCK and staged-source binding, with a 2/3 native result. Focused
production `34532837557` verifies the actual Simulator app/PCK and passes 1/2.
Its standalone native archive hashes remain runner-receipt evidence because those
archives are absent from the focused artifact. Neither complete native gate passes.

The earlier PCK is **1,549,560 bytes / 136 entries**, SHA-256
`557b2297bed133a433acc25efa4837462465dd4e06da659ae5a4cbd792f77fe0`.
It is byte-bound to Android production `0f00f17` and `c65e264` production/retained
runs. The `8030efe` adaptive producer audit verifies this earlier pack in all
three APKs and completes all four installed-consumer bindings. The `c65e264`
3D source requests MSAA_2X; effective GPU
sample count is not measured. Its diagnostics redraw changes native runtime
source while that PCK stays unchanged. The separate MSAA diagnostic pack is
**1,549,656 bytes / 136 entries**, SHA-256
`c8d2b0989524c66715fd7469b7a8315a6fd2fb8563ec87bd2294d60b4ebbcd4a`.
Each branch's native module pins its own exact pack. Independent review verifies
that each pin change replaces only one hash literal; all guard logic remains.
Earlier accepted Android runs retain their original `d6adbba1…` pack identity.
The v7 timing instrumentation, reviewed CoreAudio dormancy and main-loop access
patches remain; the optional mouse patch remains unapplied. No cover, lifecycle,
input-currentness or timeout gate is relaxed for a pass.

## What still needs to be done to finish

1. **Complete implementation and automated native qualification.** Resolve
   the two failed Android 200% held returns and qualify remaining supported
   recorder/recovery cases on current main. Complete transition pixel review.
   Qualify the pushed Standard large-text and iOS status-lookup corrections in
   full Validate `34538972728`; resolve the retained scene/cover wait and complete
   cleanup and re-entry qualification with the new pack.
   Earlier Android gameplay passes and `c65e264` accepted-Play milestones do not
   qualify `541ded4c…`. Complete current iOS production and retained acceptance,
   affected full-workflow checks and later-source regressions. Complete both
   platforms' 2D/3D gameplay, lifecycle/return/process-loss and remaining adaptive
   cases. Finish supported accessibility assertions and visual review, publish
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

- Main source milestones are pushed through `4ee4563d`. Gallery `e3a1478`
  follows the previous `46b1cf2` batch. iOS close fixes `0a2d0a0`, Card3D/new pack
  `6de14e2`, focused production workflow `e4871e1` and usage documentation
  `3e09f2c` are integrated. CI evidence globs `54a033ff`, Standard large-text UI
  `eeb1bfb7` and iOS snapshot lookup `dd6df8a5` are also pushed. Full Validate
  `34538972728` is running with both production-session flags enabled.
  Android diagnostic retention `4ee4563d` is pushed; adaptive run `34540229407`
  is running all four consumers after 282 passing host tests.
  Android adaptive `34528538284` has a completed original and
  package audit: 66 adaptive passes, two failures and 28 unreached scopes.
  New-pack retained `34531867786` passes 2/3; focused production `34532837557`
  passes 1/2 with the 3D case successful. Both complete gates remain unqualified.
  The separate `fa0fabb` startup-phase
  diagnostic remains 2/3.
- [Screenshot gallery](screenshots/README.md): **3,559 original PNGs plus 13 supplemental images**,
  with 14,955 evidence files, 18,519 checksum entries and 135 collections. The
  126-image addition includes `c65e264` production/retained, startup-phase and
  Card3D source-project evidence with its actual run/failure and viewing context.
  Android `34528538284` transition-video review and later native-run batches
  remain outside this publication.
- [Verified Android 2D/3D preview download](../godot/comparison/README.md),
  [main instructions](../README.md), [validation commands](../scripts/README.md)
  and [iOS setup](../iosApp/README.md).
- [Release qualification](release-qualification.md),
  [CI research](research/engine-ci.md) and [Godot reviews](../godot/reviews/).
  New successes do not rewrite earlier failed results.
