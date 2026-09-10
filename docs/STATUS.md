# PartyDeck status report

**Snapshot: 2026-09-10, 08:40 UTC.** The original Compose application passed its
refreshed Android and iOS baseline in
[run 34428798269](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34428798269),
at `15ab6408d16c04941d133214b03d4e8c6c42ced9`. This includes the Rules→Practice
navigation fix. Both real Godot presentations complete desktop matches. Android
2D now passes native reference matches at normal and 200% text; iOS 2D and 3D
pass at normal text. The latest Android run passes both 2D cases and 3D at 200%
text, including corrected native Back. Normal-text 3D reaches the winner but
fails its Close acknowledgment. Production Android integration passes 215 tests,
lint and debug/release packaging at the preceding pack checkpoint. The first
retained iOS engine compile found two private-method access errors; a reviewed
access patch is now integrated. Production Swift/Xcode wiring and parallel iOS
validation jobs are implemented, with Apple execution pending. These are active
implementation and qualification tasks, alongside the external
device/publisher gates.
**The app is not yet cleared for public distribution.**

## Completion percentages

**Original Compose release scope: 81% estimated completion.** This is the
weighted milestone calculation below: 80.5%, rounded to 81%. It is not code
coverage, a reliability guarantee, or an estimate of time remaining. Refreshed
baseline qualification has now passed; hardware, API 36 and publisher gates
remain. The Rules screenshot framing follow-up also passes independent review.

| Workstream | Weight | Completion | Meaning and remaining limit |
| --- | ---: | ---: | --- |
| Core features and architecture | 30% | 100% | Game, authority, protocol, transport, practice and app flows implemented |
| UI, assets and accessibility implementation | 15% | 100% | Screens, responsive layouts, original assets, preferences and Compose accessibility semantics implemented; physical-device qualification remains separate |
| Configured baseline automated qualification | 20% | 100% | Refreshed Android/JVM, iOS shared, Swift TLS, iOS UI and both API 35 APK flows pass; API 36 is not qualified |
| Builds and unsigned packaging | 15% | 100% | Android debug/release APK and AAB, iOS Simulator and optimized unsigned device app built; renewed device-package differential review passes |
| Physical-device release validation | 15% | 0% | Physical Android/iPhone release matrix not executed here |
| Publisher, signing and store readiness | 5% | 10% | Configuration and instructions exist; actual identities, public policy, store setup and submission remain |

**Godot comparison: 3 of 6 acceptance groups fully satisfied (50%).** This is an
unweighted count of the acceptance groups in [the Godot plan](../godot/README.md),
not a production-readiness or effort percentage. Engine/export/package evidence,
shared bridge checks, and matched desktop gameplay are complete. Native
lifecycle, complete mobile interaction/accessibility qualification, and delivery
of both playable native previews remain partial or open. The percentages cover
different scopes and must not be added or averaged. Both renderers are retained
until the user chooses.

## Implemented product

- **Last Light:** original two-to-six-player bluffing game, a 30-card deck,
  private hands, one-to-three-card claims, challenges, six-light penalties,
  elimination, round advancement, winner and rematch flows.
- **Practice:** playable bot matches using the same authority as multiplayer.
  Starting Practice from Rules now opens the new session correctly; Rules can
  still remain open during updates to an already active session.
- **Local multiplayer:** host-authoritative sessions, lobby readiness,
  invitation sharing/pasting, QR display and native scanning, optional
  discovery, reconnection to the same seat, and recoverable connection errors.
- **Transport and privacy:** native TLS with full host-certificate pinning,
  admission/reconnect credentials, bounded messages and queues, replay and
  revision checks, recipient-specific views, and cryptographic randomness.
- **App experience:** Home, Host, Join, Lobby, Rules, Settings, gameplay,
  round-result and winner screens; deliberate hand reveal/concealment;
  persisted sound, haptic and reduced-motion preferences.
- **Assets and architecture:** original cards, symbols, launcher artwork and
  sounds; licensed typography and offline notices; shared KMP rules, sessions,
  transport, catalog and UI with native Android/iOS services and an optional
  shared desktop launcher.

The accepted Compose baseline runs independently of Godot. The new common
controller can attach either renderer to the existing practice or LAN authority
without creating another session. That common integration is implemented and
reviewed; Android and iOS platform wiring is still being completed and qualified.
Compose remains the default accessible fallback, and unqualified native choices
are not advertised. Host migration and restoring a match after host process
death remain outside the agreed first-release scope.

## Refreshed Compose validation

All results below refer to `15ab640` and the actual assertions executed in
[run 34428798269](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34428798269).
The workflow completed successfully. Independent Android and iOS test-evidence
reviews are complete.
The refreshed device-package differential review passes: all 75 resources, six
privacy manifests, notices and metadata are unchanged; only executable bytes
change. Actual compiled controller code and release-link logs tie the new
binary to the navigation fix. No signature/provisioning/test payload is present.

| Verification | Result and practical limit |
| --- | --- |
| Android/JVM tests | **118 passed**, zero failures/errors/skips: core 14, session 27, transport 18, games 7, shared app 48, Android QR 4 |
| Android builds | Debug APK, optimized unsigned APK and unsigned AAB built; lint passes |
| Android runtime | **Both debug and optimized test-signed APKs pass** on standard API 35, including Rules→Practice→confirmed leave→Home at normal and 200% text, settings persistence, hand privacy/background/play, hosting/invitation/share teardown, invalid-invitation recovery and real soft-keyboard flows |
| Android evidence | Exact executed APK hashes verified; 60 stage captures plus two final Home images, 132 input-geometry records; no matched crash/ANR in retained preparation or app logs |
| Shared iOS tests | **83 passed**, zero failures/errors/skips, including all nine controller tests |
| Native Swift TLS | **3 tests passed**; pinned transport and real Java–Swift exchange in both directions, with successful exits and both remote-close results |
| Native iOS UI | **3 tests passed:** Settings, actual hosting/invitation, and playable practice with reveal/select/hide/play/leave; eight original screenshots retained |
| iOS builds | Simulator test app and optimized unsigned ARM64 device app built; release Kotlin framework task executed, minimum iOS 15 and iPhoneOS 26.4 metadata verified |

The Rules labels and actual navigation routes pass at both text scales. The
original optimized normal capture clipped its button's lower border; that image
remains preserved. **The follow-up is now fixed and verified:**
[Android recapture 34432935952](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34432935952)
at `8d8d429` passes all 118 tests and both APK flows. Independent review confirms
all four complete button borders/labels, 63 pixels of bottom clearance, the
exact executed checker, and four Rules→game→confirmed leave→Home routes. The
harness's eleven host regressions also pass.

Exact artifacts from the refreshed baseline:

| Artifact | SHA-256 |
| --- | --- |
| Android debug APK | `fb5ab7ffc54d5f01cd7a93761c03f10743f4b5d3e6f8019f0486fddee0079d0b` |
| Optimized Android APK, CI test signed | `a0adb50939b13eb83b21e37bd0d0604aba309e3d106d1f0c38dd0746a7115724` |
| Optimized unsigned iOS device archive | `d77f59a8272803879a31ed6b56fb32db7d1ab4ae8deae940f7874e871e10b89f` |

Earlier Android run 34421746656 and iOS run 34398824935 remain historical
receipts. The old expired Launcher3 ANR occurred before app installation in
34421746656 and was not an app runtime failure. The refreshed run has its own
evidence; earlier images or package hashes are not relabeled as current.

## Godot implementation and qualification

| Workstream | Completed | Still required |
| --- | --- | --- |
| Engine/export/assets | Verified official Godot 4.7.2 executable/AAR; reproducible 136-entry PCK; original artwork, fonts/audio; frame-safe reconciliation and compact 2D Reveal correction exported; all 19 bundled notices exposed through Settings Credits | Qualify the final pack on native hosts; physical GPU/audio checks |
| Authority bridge | Recipient-safe versioned codec, real shared rules, bounded events/revisions/lifetimes; 20 bridge cases in the latest Android producer | Complete production native adapter qualification |
| 2D renderer | Complete desktop match and matching authority trace; Android normal/200% native matches pass; iOS normal native match passes | Correct and rerun iOS 200% input handling; remaining native visual/accessibility checks |
| 3D renderer | Complete desktop match and matching authority trace; iOS normal native match passes; Android 200% completes all native routes, including corrected Back | Resolve and rerun normal Android Close acknowledgment; rerun iOS 200% Home observation; native visual/accessibility checks |
| Common production integration | Both presentations use the existing session authority; captured revisions/generations, Ready ordering, bounded cleanup, lobby return and concealed Compose fallback; 28 focused tests pass; source review complete | Native adapter/runtime execution with real shell sessions |
| Android runtime library | Shared official engine/plugin, bounded queues, covered-input generation rejection, PCK staging and R8 reflection rules; 17 focused tests pass with the Close correction; both hosts pass lint and debug/release packaging with the adaptive pack | Native execution of the render-barrier Close observation and lifecycle |
| Android production host | Private shell-process broker and separate renderer Activity implemented; lifecycle/source reviews complete; 45 app tests pass including 22 lifecycle, 12 IPC and 7 close-handshake cases plus 4 existing QR cases; debug/optimized APK and AAB built | Real Binder/app switches, same-session return, process death and re-entry; shell sound/haptic continuity |
| iOS diagnostic/authority host | Five diagnostic lifecycle tests pass; real Swift authority caller links; secure-default Exit and normal 2D/3D full matches pass | Both 200% cases must pass; prior CoreAudio startup abort remains an unresolved qualification concern |
| iOS production/retained engine | Reviewed audio dormancy and main-loop access patches; Kotlin callback port with 11 portable tests; retained native owner, Swift adapter and Xcode wiring implemented and source-reviewed; separate Simulator/device CI prepared | Replacement Apple compilation after two private-access errors; harness review corrections, actual dormancy/re-entry proof, production shell packaging and qualification |
| Delivery | Both desktop previews run; actual native successes and failures preserved; original screenshots published | Both qualified selectable native previews; production LAN/accessibility/performance qualification |

The current exported pack is 1,546,376 bytes with 136 entries, SHA-256
`8f24944d61b0430cfec4a32bb1d03d2c7da9f55918264e9cfcded1c675d21539`.
Its source/import/export and packed-scene checks pass. It includes frame-safe
resource reconciliation, the compact 2D Reveal correction, and an Android-only
orientation override matching the resizable/fullUser native manifests. The iOS
orientation default is unchanged. Native landscape, rotation and split-screen
qualification remain pending. The preceding `0440dc8a…` pack and all exact
Android APK/AAB bytes are preserved. The earlier
frame pack, `0ed324c1…`, passed 111 source and 111 packed boundary assertions,
both complete 42-view desktop reference traces and two additional 3D/200%
input/scroll/lobby cases. All previous packs and failed captures are retained;
new exports do not inherit old native acceptance.

### Android native evidence

[Run 34446327045](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34446327045),
exact source `b7f2f4f2c2d03b8e599d4b0fc73bf2d35f6640eb`, uses frame pack
`0ed324c19016f28987d6294f915c107f62234670b149f73bab585af93e29ae6d`.
Its independently checked producer passes **29 JUnit cases, 69 checker tests,
111 packed boundary assertions and both desktop matches**.

Both 2D scales report complete native success. Both 3D scales now complete full
matches (two plays, two challenges, thirteen advances, round-14 winner) and the
separate renderer Exit entry, then fail the fresh native Back entry because the
recorded close reason is `renderer_exit` instead of the required native route.
Destruction markers are present and the final failure snapshots contain no live
engine PID. Independent audit verifies all four full matches, 48 scene captures, 156 scene
input records and actual process death for all twelve attempted entries. Ten
entries complete their requested exit route; both 3D Back entries still fail.

Pinned source identifies the route: the focused Godot view consumes Back and
turns it into a scene quit request before the Activity's ordinary Back callback.
The native dispatch correction is committed at `a727868` and passes local
comparison-host lint and debug/release packaging. The strict test expectation
is unchanged. [Run 34450246541](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34450246541)
executed that source with pack `0440dc8a…`: **three of four native cases pass**.
Both 2D cases pass. 3D/200% passes corrected `native_back`, with received events
unchanged at one and complete teardown. Normal 3D completes the round-14 winner
and accepted lobby return, then fails `closeSignalAcknowledged=false`; it never
attempts fresh scene Exit or native Back. All ten attempted engine processes
actually die; nine requested exit routes qualify. Independent audit checks 75
native PNGs, 22 desktop PNGs and all original failure logs.

The Close correction records delivery only at the existing actual render-thread
barrier and preserves that observation across disposal. The qualifier samples it
after bounded renderer exit. It keeps the callback, 250 ms fallback, 1,500 ms exit
wait and strict checker. The original failure cannot distinguish an absent
barrier from a lost or late main-thread notification; no runtime fix is claimed
until the new run succeeds.

The earlier cold-start timeout and resumed GL-thread
SIGSEGV from [run 34439587132](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34439587132)
did not recur in these later entries. That does not identify the original
crashing callback or establish hardware GPU qualification. Original failure and
driver-error evidence remain in the gallery.

### Production Android integration checkpoint

The local combined checkpoint finished at 07:10 UTC with **215 tests passed,
zero failures/errors/skips**: core 14, session 27, transport 18, games 7, shared
app 75, bridge 20, shared Android renderer 9 and Android app 45. Debug and
optimized unsigned APKs and the unsigned AAB built with the final pack.
The first report counted a six-module subtotal of 186; the additional 29 results
are from the two Godot projects whose directories differ from their Gradle names.
All XML and the original subtotal are preserved.

The first combined command failed four lint checks on the physical Back
interception. Independent source research confirmed the public Activity hook
and the separately registered predictive-Back callback. A method-scoped lint
annotation preserves that behavior without a global baseline. **The follow-up
production and comparison-host lint and debug/release APK/AAB builds all pass.**
The 215 passing tests are retained from the combined run; the annotation-only
production change did not require repeating them.

The subsequent Close/adaptive checkpoint passes **17 focused runtime-library
tests**, zero failures/errors/skips, including eight new dispatch-interleaving
cases. Both production and comparison hosts pass lint, debug/optimized APK and
AAB packaging with pack `8f24944d…`. Tests and package hashes were preserved
under the Gradle lock. The earlier 215-test checkpoint remains separate evidence;
the new native behavior still requires execution. Changes are committed at
`d8f9d15`; the reviewed production iOS integration and build corrections are at
`4168c4d`.

A real-picker production session smoke checker and its CI integration are ready.
All 25 checker host regressions pass independent review, including malformed
image preservation and invitation-capture refusal. Native execution remains
pending. These checks exercise shell/session continuity, process identity, return,
leave and renderer death; native Ready/chrome alone does not qualify in-engine
gameplay or pixel privacy.

### Latest iOS native evidence

[Run 34439760695](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34439760695),
exact source `f85f8158054ab70cc3f981c23a6854bb7b0630b6`, executed **five cases:
three passed, two failed**, with none skipped. Normal 2D and 3D each reach the
round-14/revision-41 winner with two plays, two challenges and thirteen advances,
then complete native cleanup and leave a responsive shell. Secure-default
renderer Exit also passes. The two-test subtotal after the test-runner relaunch
is not the full run count.

At 200% text, 2D exhausts a shared input/layout retry limit after only three
actual drags. The final diagnostic places Next round fully inside the viewport,
but there is no subsequent confirmed stable observation or tap. This is an input
checker failure; it does not prove an unreachable app control. The committed correction
separates bounded layout observations from bounded scroll gestures and uses the
measured target gap, explicit slower velocity and an end hold. Native rerun is
still required.

The 3D/200% test fails its background assertion: XCTest reports foreground even
though retained system logs show Home appeared within the deadline, the screenshot
shows Home, and later native metrics show paused rendering, a privacy cover and
zero private bindings. The test must independently verify actual Home visibility
and native lifecycle without relabeling that contradictory application-state
receipt as a pass. The committed Home correction independently observes the system Home screen
while retaining the contradictory XCTest state. Both failed cases require new
native execution. All 285 exported
attachments, including 36 PNGs, match the original xcresult payloads.

The earlier iOS run `34434392993` includes a genuine CoreAudio startup RPC abort.
It did not recur in the newer run; that does not establish a root-cause fix.
Retained-engine support first compiled in
[run 34451058187](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34451058187)
at `3bb0eed`, but Clang rejected two private main-loop calls. There was no final
engine archive or runtime execution. The integrated narrow access patch exposes
two iOS-only wrappers around those existing methods, preserving retirement order.
Fresh source staging passes with both maintained patches; the receipt consumer
accepts the exact pair and rejects seven incomplete or inconsistent variants.
Apple compilation remains required.

The production Swift adapter, Xcode static-library/resource wiring and separate
device Release builder pass independent source review. The new Validate workflow
exports one checked pack on Linux, then runs Simulator/shared tests and unsigned
device compilation in parallel. These source checks do not qualify Swift APIs,
final Apple linkage or native lifecycle. Historical failed runs and exact evidence remain documented in
[CI research](research/engine-ci.md) and [the review gallery](screenshots/README.md).

## Remaining release work

1. **Finish Godot implementation and native checks.** Resolve and rerun Android
   Close acknowledgment and qualify the integrated shell/IPC lifecycle and feedback;
   execute the corrected iOS input/Home checks; finish retained iOS engine,
   Swift adapter and native packaging integration. Build and run both native
   modes, verify same-session return,
   process loss and re-entry, then repeat the affected app baseline. Both modes
   remain available in source for the user to compare. The Android adaptive
   orientation/window policy is implemented in both manifests and the packed
   engine override; its actual landscape, rotation and split-screen tests remain.
   Mobile TalkBack/VoiceOver
   and complete native accessibility still require explicit qualification.
2. **Qualify Android API 36.** Standard runner attempts have failed during empty
   emulator preparation before installation. API 35 passes do not qualify API
   36; physical or suitable alternative runner evidence remains necessary.
3. **Execute physical-device release validation.** Android↔iPhone and
   same-platform LAN matches/rematches with two-to-six players; camera/QR,
   permission denial/recovery, real sharing/clipboard, network loss/reconnect,
   host loss, background/lock/privacy/process death; supported minimum/current
   OS, TalkBack/VoiceOver, large text, phone/tablet/orientation; release launch,
   frame pacing, memory, battery and network use. Hardware is unavailable here.
4. **Complete publisher/store setup.** Publisher name, public privacy URL and
   support contact; Android signing identity and Apple team/provisioning; Play
   Console/App Store Connect listings, disclosures and submission; signed
   testing-track/TestFlight installation. These details were already requested.
   Publisher assessment of Adobe DNG SDK commercial terms also remains; bundled
   notices alone do not settle those terms.

## Published deliverables

- Source and coherent milestones are pushed to the repository.
- [Screenshot gallery](screenshots/README.md): **1,279 original app/renderer PNGs**,
  **3,022 evidence files**, four linked artwork proofs and **4,306 verified
  checksums**, published at `d36cf6b`. Run 34450246541 captures are being collected
  in the next batch and are not included until pushed.
- [Main build instructions](../README.md), [validation scripts](../scripts/README.md),
  [iOS instructions](../iosApp/README.md), and
  [both desktop Godot preview commands](../godot/comparison/README.md).
- Exact artifacts, review limits and release gates are documented in
  [release qualification](release-qualification.md),
  [CI research](research/engine-ci.md), and the
  [Godot review records](../godot/reviews/).
