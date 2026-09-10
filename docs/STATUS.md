# PartyDeck status report

**Snapshot: 2026-09-10, 04:24 UTC.** The original Compose application passed its
refreshed Android and iOS baseline in
[run 34428798269](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34428798269),
at `15ab6408d16c04941d133214b03d4e8c6c42ced9`. This includes the Rules→Practice
navigation fix. Both real Godot presentations work in the desktop comparison;
the native Godot hosts still have implementation and runtime qualification work.
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

The existing Compose application does not depend on Godot. Godot comparison
hosts currently use real local practice; their production LAN-shell integration
is unfinished. Host migration and restoring a match after host process death
are outside the agreed first-release scope.

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
| Engine and export | Official Godot 4.7.2 executable/AAR verified; isolated builds; deterministic 136-entry PCK independently reproduced byte-for-byte; replacement native-fix pack passes import/export and 41 packed boundary assertions | Native package/runtime checks for the replacement |
| Shared assets | Original artwork/fonts/audio and all 47 runtime resources loaded; all 19 Android notices verified in actual packages | Native filtering/playback and notice-screen execution |
| Authority bridge | Recipient-safe versioned codec, real rules authority, bounded events/revisions/lifetimes; common tests and all 20 iOS bridge tests pass | Native host event round trips and actual Swift factory/gameplay execution |
| 2D renderer | Final packed desktop match passes: 42 authority snapshots, 21 renderer events, two player plays, two challenges, thirteen continuations, winner/lobby/fresh entry and clean exit | Native input, lifecycle, text scaling and accessibility |
| 3D renderer | Same complete desktop match and identical authority trace; corrected winner rank, narrow/large-text layout and touch handling; deferred-scroll teardown race fixed and boundary-tested | Native input and lifecycle checks |
| Android host | Real official AAR, chooser, owned engine process, bounded bridge and privacy cover; all four cases reach native Ready; 2D/100% reaches a real winner and positively confirmed engine teardown | Full gate failed on test timing, post-winner confirmation expectations, 200% scroll overshoot and shader-warning classification; corrections and package audit underway |
| iOS diagnostic host | All five actual diagnostic lifecycle tests pass in 34431377938: rendering, foreground loss/resume, touch exit, deferred cleanup and initialization boundaries | Actual Last Light gameplay, repeat entry/dormancy and physical-device qualification remain separate |
| iOS authority host | Actual Swift caller links against the verified framework and engine; secure-default launch and real renderer Exit pass in 34434392993 | Four reference match cases fail at app/diagnostic/geometry/background checks and are being diagnosed; repeated entry/dormancy implementation remains open |
| Delivery | Both desktop previews run; matched screenshots and original failures published; Android packages retain exact notices and alignment | Playable native previews for both modes, production shell/LAN integration and mobile accessibility |

The previously accepted deterministic pack is 1,542,328 bytes, SHA-256
`26bfbb72efa55b63bef2e0ab989c82356c75b3bb3ca40bcf1c5e70e931bff890`.
Its independent export, all 136 mounted entries, 19 Android notices, package
alignment and both complete desktop matches passed. The native-fix replacement
is 1,542,296 bytes, SHA-256
`6599f825a418f9d2a7049b3ba9325e8e0dcb474685262899079231b7ec955938`.
Only the two intended compiled scripts change; all four import/export/check
stages and 41 packed boundary assertions pass. Its complete 2D/3D comparison
also passes: both 42-view traces and all 22 image bytes match the earlier run,
with clean exits. Native package/runtime checks are running; desktop results
do not establish mobile qualification.

[Android Godot run 34430556814](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34430556814)
at `83874c1` passed build/package/desktop checks, **24 JUnit tests and 54 checker
tests**. All four native cases failed before Ready with the actual message
“PartyDeck Android bridge did not provide its display density.” The host
recorded density 1.75; pinned-source review found that Android Java methods use
`has_java_method`, while the renderer checked only `Object.has_method`. The
3D/200% case additionally emitted the upstream renderer-exit timeout; native
destroy-return flags do not override that failure. Both fixes are pushed at `bf77ea7`. The next run,
[34433457249](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34433457249),
passes 27 JUnit cases, 54 checker tests and 41 packed boundary assertions. All
four native cases reach Ready. 2D/100% completes the real match and returns to
the chooser with positive render-thread/engine termination logs, but its mode
gate hits the deadline while incorrectly expecting a post-winner confirmation.
2D/200% repeatedly overshoots a scrolled action. Both 3D checks fail on a verified
shader-cache fallback warning logged at Android error priority. The narrow
warning classifier fix is pushed at `2334382` with 60 passing host tests; the
other checker corrections are underway. These partial results do not qualify
the full native suite.

[iOS diagnostic run 34428221586](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34428221586)
at `a04f22b` linked and ran five tests: **one passed, four failed**. Actual stderr
shows `Main::setup` rejected the host's `--path` because path overrides were
disabled. There were zero Ready events, draws and iterations. The corrected
`disable_path_overrides=no` build and explicit startup-stage diagnostics are
pushed at `4f7776a` and **all five diagnostic tests pass** in
[34431377938](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34431377938).
Nine paired images/measurements show actual OpenGL rendering, pause/resume,
touch-generated Exit and checked cleanup. Closed initialized cases release
the view/controller and OS singleton, stop the loop, and restore the prior
idle-timer policy. The reopen assertion confirms refusal after full cleanup;
it does not qualify another game entry. This diagnostic gate remains separate
from the new real-authority gameplay host. That host and parallel input builds
are pushed at `a8dbb19`. In
[34434392993](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34434392993),
the Swift caller links and the secure-default renderer-exit test passes. Four
reference match tests fail at distinct app-running, diagnostics, geometry and
background assertions. Actual process logs and measurements are being audited
before classifying their causes; no full native iOS match is accepted yet.

## Remaining release work

1. **Complete unblocked Godot implementation and native checks.** Verify the
   corrected Android failures; finish the real iOS caller/gameplay gate and
   lifecycle/re-entry behavior. Qualify both selectable native previews.
   Production integration still needs the existing LAN shell and accessible
   native controls: Godot desktop accessibility does not supply mobile
   TalkBack/VoiceOver support.
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
- [Screenshot gallery](screenshots/README.md): **837 original app/renderer PNGs**,
  **1,155 evidence files**, four linked artwork proofs and **1,997 verified
  checksums**, published at `0c0f0e2`. Newer batches are not included until pushed.
- [Main build instructions](../README.md), [validation scripts](../scripts/README.md),
  [iOS instructions](../iosApp/README.md), and
  [both desktop Godot preview commands](../godot/comparison/README.md).
- Exact artifacts, review limits and release gates are documented in
  [release qualification](release-qualification.md),
  [CI research](research/engine-ci.md), and the
  [Godot review records](../godot/reviews/).
