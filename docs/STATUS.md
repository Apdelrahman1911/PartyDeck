# PartyDeck status report

**Snapshot: 2026-09-10, 12:10 UTC.** Source milestones are pushed through `0222e6f`.
The original Compose application retains its successful refreshed Android/iOS
baseline and separate API 36 qualification. Both desktop Godot presentations
complete matches, and the latest completed Android comparison passes all four normal/200%
2D/3D cases and all twelve exit routes. Native iOS host qualification remains
partial: retained tests pass two of three cases; authority tests pass two of five.

Production integration has separate open gates. Android's first qualification
run passes both ordinary APK smokes but fails both native-session phases before
the picker on process-list parsing. The correction passes 33 checker regressions
and all 29 adaptive-runner regressions; its production and adaptive native runs
are now executing in parallel with the refreshed full comparison.
Both iOS native engines compile. The generated Kotlin linker dependency is now
declared, and a new production run is testing that correction plus actual 2D/3D
practice sessions. A parallel native-host run tests the newly exported scene
currentness correction. Neither run has completed at this snapshot.
Implementation/runtime corrections and physical-device and publisher gates remain
distinct.
**The app is not yet cleared for public distribution.**

## Completion percentages

**Original Compose release scope: 81% estimated completion.** This is the
weighted milestone calculation below: 80.5%, rounded to 81%. It is not code
coverage, a reliability guarantee, or an estimate of time remaining. Refreshed
baseline qualification has now passed, including the separate API 36 baseline;
hardware and publisher gates remain. The Rules screenshot framing follow-up also
passes independent review. Closing API 36 does not change the rounded estimate:
the configured baseline milestone was already fully counted.

| Workstream | Weight | Completion | Meaning and remaining limit |
| --- | ---: | ---: | --- |
| Core features and architecture | 30% | 100% | Game, authority, protocol, transport, practice and app flows implemented |
| UI, assets and accessibility implementation | 15% | 100% | Screens, responsive layouts, original assets, preferences and Compose accessibility semantics implemented; physical-device qualification remains separate |
| Configured baseline automated qualification | 20% | 100% | Refreshed Android/JVM, iOS shared, Swift TLS, iOS UI and both API 35/API 36 APK flows pass; Godot integration has separate open gates |
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
without creating another session. That common integration and both platform
adapters are implemented and reviewed; their production runtime is still being
qualified. Both shipping availability sets remain empty. Explicit Android and iOS
build-time qualification profiles expose selected native modes for testing;
default shipping packages keep those modes unavailable. Compose remains the default
accessible fallback. Host migration and restoring a match after host process
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

### API 36 baseline qualification

[Run 34457458638](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34457458638)
at `f11f92ed4ec4f91630396bf493ba2fd984f07bb9` passes the existing debug and
disposable-test-signed optimized APK flows: **86 recorded steps and 30 stage
captures per APK**, with both exit codes zero. The independent audit passes all
23 evidence checks. Actual guest API 36, the default x86_64 image revision 2,
Emulator 37.1.11, 720 × 1600 / 280 dpi, usable KVM and the four-CPU / 15,989 MiB
runner are recorded. Empty-AVD preparation passes on the first boot without a
reboot. No matching ANR/fatal exception/fatal signal appears in the retained logs.

This closes the baseline API 36 runner/runtime gap. The reports ZIP matches
GitHub's published digest; optimized executed-input and disposable signing
receipts agree. The independent audit did not redownload the separate 474 MB
package artifact. Native Godot session smoke was explicitly disabled, so its
gameplay/lifecycle and physical-device behavior remain outside this result.

## Godot implementation and qualification

| Workstream | Completed | Still required |
| --- | --- | --- |
| Engine/export/assets | Verified official Godot 4.7.2 executable/AAR; reproducible 136-entry PCK; original artwork, fonts/audio; frame-safe reconciliation, compact 2D Reveal and terminal-return corrections exported; all 19 bundled notices exposed through Settings Credits | Remaining iOS/production pack qualification; physical GPU/audio checks |
| Authority bridge | Recipient-safe versioned codec, real shared rules, bounded events/revisions/lifetimes; 20 bridge cases in the latest Android producer | Complete production native adapter qualification |
| 2D renderer | Complete desktop match and matching authority trace; Android normal/200% native matches and exits pass; latest iOS normal match passes | Resolve latest iOS 200% revision observation failure; native visual/accessibility qualification |
| 3D renderer | Complete desktop match and matching authority trace; Android normal/200% native matches and all requested exits pass | Resolve both latest iOS control-observation failures; native visual/accessibility qualification |
| Common production integration | Both presentations use the existing session authority; captured revisions/generations, Ready ordering, bounded cleanup, lobby return and concealed Compose fallback; 28 focused tests pass; source review complete | Qualify native adapters with real shell sessions |
| Android runtime library | Shared official engine/plugin, bounded queues, covered-input generation rejection, PCK staging and R8 reflection rules; 17 focused tests pass; comparison Close barriers and process teardown pass all twelve routes | Production broker/renderer lifecycle, real app transitions and adaptive-window runtime qualification |
| Android production host | Private shell-process broker and separate renderer Activity; explicit build-time qualification activation implemented; both ordinary production-run APK smokes pass; process-list correction passes 33 host regressions | Execute corrected debug/optimized native sessions, return, process death, re-entry and shell feedback; execute the four-consumer API 36 adaptive workflow |
| iOS diagnostic/authority host | Five earlier diagnostic lifecycle tests pass; real Swift authority caller links; latest normal 2D and secure renderer Exit pass | Latest 2D/200% and both 3D failures; complete native interaction/privacy qualification |
| iOS production/retained engine | Reviewed dormancy/main-loop patches, Kotlin callback port, retained owner and Swift adapter integrated; both native engines compile; production staging succeeds; generated Kotlin linker output declared; explicit qualification activation and two real production-session XCTest cases implemented and source-reviewed | Complete current app builds/XCTest and native-host reruns; resolve retained 3D stalls and qualify production lifecycle |
| Delivery | Both desktop previews run; native successes and failures preserved; original screenshots published | Both qualified selectable native previews; production LAN/accessibility/performance qualification |

The current exported pack is **1,548,520 bytes with 136 entries**, SHA-256
`91eeb2fba17dd291564bf2e005f85c0924f813f044f945297f10b281e608b2e6`.
Its import, source-scene, export and packed-scene checks pass. It adds
generation-backed `sceneStateApplied` diagnostics: a Ready event or current
revision alone cannot claim that the scene has actually applied that state.
Android/iOS parsers require the strict Boolean, and iOS cover/input gates require
it to be true. The exported pack passes **155 boundary and 216 terminal-return
assertions (371 total)** under real Xvfb/OpenGL rendering. All **71 Android
comparison host tests** pass and the Android host compiles. The integrated iOS
observation compiles for Simulator ARM64 and passes **75 shared app tests**.

This pack preserves the terminal-return, frame-safe reconciliation, compact 2D
Reveal and Android orientation corrections. It has not inherited native
acceptance from the previous `a47392b4…` pack. Native landscape, rotation and
split-screen qualification remains pending. A separate 3D change will avoid
continuously redrawing an unchanged foreground scene; it is still under focused
render testing and is not included in this pack or the two active iOS runs.

### Android native comparison evidence

[Run 34463877910](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34463877910)
at `bbfde024d95f5e4d62a26b57495a6a90447d6033` passes **all four API 35 debug
cases**: 2D and 3D, each at normal and 200% text. Each completes a full match,
match return, a fresh scene Exit and native Close/Back: **all twelve requested
routes pass**. Every route records Close dispatch, a native barrier and a main
callback, with no fallback. Barriers arrive **5–34 ms** after the request; native
destruction takes 111–260 ms. The **250 ms fallback and 1,500 ms exit gate remain
unchanged**, as do the strict native checker and relevant host/bridge code.

The read-only audit verifies installed-input/source hashes, OS process death,
chooser recovery, 48 scene-capture crops, input geometry and all 80 Android
artifact PNGs. Producer evidence passes **37 JUnit cases, 69 checker host tests,
111 packed boundary assertions, 164 terminal-return assertions**, and matching
42-view desktop authority traces. All six artifact ZIPs and 599 extracted files
match their original receipts. Independent original-image/privacy/accessibility
review remains separate and pending. This comparison run does not qualify API
36 native gameplay, optimized native runtime, production sessions or hardware.

Earlier [34446327045](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34446327045),
[34450246541](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34450246541)
and [34456443339](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34456443339)
retain the original Back/Close failures and their exact packs. In 34456443339,
both 3D matches reached the winner but recorded no Close dispatch/barrier before
the 250/251 ms fallback; the newer run closes that observed comparison failure.
The earlier cold-start timeout and resumed GL-thread SIGSEGV in
[34439587132](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34439587132)
remain historical evidence. Later success does not establish their root cause
or hardware GPU qualification; driver/shader warnings remain in the originals.

### Production Android integration checkpoint

The earlier integrated Compose baseline in
[Validate 34456441354](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34456441354)
at `dad1c11741bd4322bb8b2afb9f18f3db5f50c919` passes **223 tests across 38 XML
reports**, zero failures/errors/skips, plus 36 separate Python checker tests.
Both API 35 ordinary APK flows pass with 30 screenshot/XML pairs per APK.
Independent review verifies the executed APK hashes, all 60 stage captures and
unchanged optimized payloads after disposable test signing. Godot session smoke
was disabled, so this remains Compose evidence with integrated native libraries.

The new build-time qualification profile is implemented and independently
reviewed. The preserved local checkpoint passes **50 Android app tests** across
six suites, with zero failures/errors/skips, shipping debug lint/build, and
qualification debug/release APK and release AAB packaging. All four inspected
packages contain the exact current PCK. Decoded metadata keeps shipping modes
empty and explicitly selects `2d,3d` only in qualification packages. These local
results establish implementation and packaging; repeated test checkpoints are
not added together as new coverage.

[Production Validate 34467682627](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34467682627)
at `b24655dfc0f9a99653682d876bbadeea5a2073d5` is **completed with failure**.
Tests, lint and packaging succeed: **228 JUnit tests across 39 reports and 46
Python checker tests pass**, with zero lint errors and 11 warnings. Both ordinary
debug/optimized APK smokes pass (exit codes 0/0). Both native-session phases fail
(1/1) with `Unrecognized Android ps PID/UID/NAME output`, before the picker.
Installation, installed-APK hash verification and cold launch had passed; the
inherited readiness stage label does not establish an emulator boot failure.
Independent auditing verifies qualification metadata for `2d,3d` in all four
packages and unchanged payloads in the disposable-signed optimized APK. No native
mode entry, session continuity, interruption or renderer-death acceptance is
established. The original raw process-list output was not retained.

The corrected production session checker normalizes only header whitespace,
keeps exact process names and numeric PID/UID requirements, and saves raw stdout,
stderr and command status before parsing. Android 15/16 Toybox source establishes
a padded-header incompatibility; absent original output prevents proving that
exact header caused the failed run. All **33 session regressions and 29 composed
adaptive regressions pass**. The new API 36 workflow builds once and runs four
independent consumers: debug/optimized APKs at normal/200% text, both modes in
each. It checks landscape, rotation during native-control touch, stable reentry
and split-window geometry. Actual native execution is still required.

Three fresh Android runs at `0222e6f` are now active with the new `91eeb2fb…`
pack and strict scene-currentness checks:

- [Production API 35 sessions: 34475047307](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34475047307).
- [Four parallel API 36 adaptive consumers: 34475052568](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34475052568).
- [Complete 2D/3D comparison: 34475057938](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34475057938).

The comparison observer now requests at most four follow-up diagnostics after
matching healthy pending responses. Fully applied state remains mandatory for
input, and all follow-ups share the original deadlines. **83 host tests plus six
independent boundary traces pass**. These host checks do not establish the actual
native outcomes of the active run.

The session checker exercises actual picker entry, shell/session continuity,
process identity, return, leave and renderer death. Native Ready/chrome alone does not
qualify in-engine gameplay, pixel privacy, card dragging, physical LAN or
adaptive-window behavior. Qualification activation does not enable shipping modes.

### Latest iOS native evidence

[Native-host run 34464316979](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34464316979)
at `ea84bf49e799675c181545cc3511460b11e0e23d` compiles and executes both hosts
with the previous `a47392b4…` PCK. **Retained: two passed, one failed.** Background transitions
and repeated 2D/3D cases pass. The stale-Ready/close-completion case fails while
waiting for current renderer diagnostics; it never reaches the old-handle probe.
The rejected sample waits **13.183 seconds for the main run loop** and still
reports its privacy cover visible; the failure is not established as a queue or
epoch defect. Later uncovered snapshots do not replace that rejected observation.
The generation-backed scene-currentness fix and preserved rejected-observation
attachments are now being exercised in
[native-host run 34473325295](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34473325295)
at `0f666e0`. All three producers pass with the exact new pack; both native
consumer tests remain running at this snapshot. Existing deadlines and gameplay
expectations remain unchanged.

**Authority: two passed, three failed.** Normal 2D and secure renderer Exit pass;
2D at 200% text fails an expected-revision comparison (42 versus 41), and both
3D cases fail with `controlMissing`. Current scene/revision and control observation
remain open. The frozen audit binds six original ZIPs, 4,422 extracted files,
five job logs and exact source; all 515 exported attachment payloads match the
original xcresults. These Simulator results leave broader lifecycle,
same-process/all-authority and production KMP qualification open. Original mouse
and texture-conversion messages and ambiguous XCTest restarts remain preserved;
no clean-log or no-crash conclusion is claimed.

The earlier [34439760695](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34439760695)
normal 2D/3D matches and secure Exit successes remain historical, alongside its
two 200% failures. The subsequent input/Home and retained Swift concurrency
corrections are integrated, but latest failures still require new execution.
The CoreAudio startup RPC abort in 34434392993 remains an unresolved historical
qualification concern; later runs do not establish its root cause. Physical
Metal, motion and audio-interruption behavior remain unqualified.

### Production iOS integration checkpoint

[Validate 34467184471](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34467184471)
at `0aa574b3e830116b47682a87163bf24c7e411db0` is **completed with failure**.
Both Simulator/device native engine compiles pass, and **139 shared native tests
across 23 suites pass**, with zero failures/errors/skips. The native source,
engine/module/variant, required symbols and new pack/export receipts pass
independent audit. Both production staging steps succeed, including
the Python 3.9 compatibility correction and all nine recorded resource hashes.

Both app builds then fail final `Ld`: Xcode reports the force-loaded PartyDeckKit
binary as a missing build input under `composeApp/build/xcode-frameworks/Debug/iphonesimulator26.4`
and `Release/iphoneos26.4`. Kotlin's pinned implementation confirms those paths;
the Compile Kotlin script did not declare that generated output. The reviewed
correction now declares the existing configuration/SDK-dependent framework binary
as an output, preserving its path and both force-load flags. This is a build
dependency fix; the original path was correct.

[Production run 34473324178](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34473324178)
at `0f666e0` tests the corrected device/Simulator builds. It also requests a
separate qualification app after the ordinary shipping baseline, with exactly
two real 2D/3D practice-session XCTest cases. Those tests use actual renderer
input and accepted authority receipts, Standard-table continuity, leave
cancel/confirm and new-session retained-engine reentry. The observation is
compiled only for Debug qualification and exports public counters/enums, not
private card identities or session secrets. All three independent source reviews
pass. Explicit packaged activation selects qualification modes; shipping modes
remain empty. All **139 shared native tests** and both engine compiles now pass
in this run. App compilation and native runtime remain pending.

In the preceding `34467184471` run, raw native archives and staged resource bytes
were not uploaded; those audit checks are receipt-bound, not independent
rehashes of absent files. Retained-host
successes do not substitute for production app packaging/session qualification.
Historical failures and review limits remain in
[CI research](research/engine-ci.md) and [the review gallery](screenshots/README.md).

## Remaining release work

1. **Finish Godot implementation and native qualification.** Execute the corrected
   Android process-list checker in production debug/optimized native sessions;
   qualify shell/IPC lifecycle, same-session return, process loss/re-entry and
   sound/haptic continuity. Complete the iOS generated-input correction's app builds
   and XCTest, and resolve retained diagnostics and authority scene/control failures.
   Finish and test the 3D on-demand redraw change, export its pack, and repeat the
   affected native cases. Execute the integrated bounded Android diagnostic
   follow-up correction without relaxing current-scene or input acceptance.
   Complete actual native visual/privacy review and repeat affected app baselines.
   Both renderers remain in source for comparison. Android's adaptive orientation
   policy is implemented; native landscape, rotation and split-screen execution
   remains. Table guidance, native return descriptions and stable enlarged-hand
   identity are implemented. Godot canvas screen-reader controls remain
   unimplemented. Compose accessibility requires actual TalkBack/VoiceOver
   gameplay, privacy, focus and same-session continuity qualification. Both
   shipping availability sets stay empty; explicit test activation is implemented
   but does not grant shipping acceptance.
2. **Execute physical-device release validation.** Android↔iPhone and
   same-platform LAN matches/rematches with two-to-six players; camera/QR,
   permission denial/recovery, real sharing/clipboard, network loss/reconnect,
   host loss, background/lock/privacy/process death; supported minimum/current
   OS, TalkBack/VoiceOver, large text, phone/tablet/orientation; release launch,
   frame pacing, memory, battery and network use. Hardware is unavailable here.
3. **Complete publisher/store setup.** Publisher name, public privacy URL and
   support contact; Android signing identity and Apple team/provisioning; Play
   Console/App Store Connect listings, disclosures and submission; signed
   testing-track/TestFlight installation. These details were already requested.
   Publisher assessment of Adobe DNG SDK commercial terms also remains; bundled
   notices alone do not settle those terms.

## Published deliverables

- Source and coherent milestones are pushed through `0222e6f`.
- [Screenshot gallery](screenshots/README.md): **1,584 original app/renderer PNGs**,
  including original failed attempts, with four linked artwork proofs. The
  latest extension adds 124 originals and is verified and published at
  [bbf33f1](https://github.com/Apdelrahman1911/PartyDeck/commit/bbf33f1c33c67fe1b910b821aaa1c0d0dd6bd398).
- [Main build instructions](../README.md), [validation scripts](../scripts/README.md),
  [iOS instructions](../iosApp/README.md), and
  [both desktop Godot preview commands](../godot/comparison/README.md).
- Exact artifacts, review limits and release gates are documented in
  [release qualification](release-qualification.md),
  [CI research](research/engine-ci.md), and the
  [Godot review records](../godot/reviews/).
