# PartyDeck status report

**Snapshot: 2026-09-10.** Latest completed baseline validation commit:
`d3418f150e908667560767e4b825f8968b337df3`.

**Estimated progress toward public production release for the original Compose scope: 81%.** The
planned first-release application features are implemented. The remaining work
is mainly physical-device verification, additional Android API 36 qualification, and
publisher/store setup. The app is **not yet cleared for public distribution**.

These percentages are milestone estimates, not code coverage, a guarantee of
reliability, or an estimate of time remaining. The weighted calculation below
is 80.5%, rounded to 81%. Both Android APK variants now pass the complete
configured runtime flow on standard API 35, independently verified.

**Expanded scope:** the user requested **both 2D and 3D Godot presentations**,
built in parallel for comparison. The 81% estimate applies only to the original
Compose scope. Godot progress is recorded separately below; engine compilation
and screenshots do not establish a playable native integration.

| Workstream | Weight | Completion | What the percentage means |
| --- | ---: | ---: | --- |
| Core features and architecture | 30% | 100% | Planned first-release game, authority, protocol, transport, practice and app flows implemented |
| UI, assets and accessibility implementation | 15% | 100% | Screens, responsive layouts, original assets, controls, preferences and accessibility semantics implemented; device validation is separate |
| Configured baseline automated qualification | 20% | 100% | Android/JVM, iOS shared, Swift TLS and iOS UI suites passed; debug and optimized APKs both pass the complete API 35 runtime gate. This does not qualify API 36 or physical devices |
| Builds and unsigned packaging | 15% | 100% | Android debug/release APK and AAB, iOS Simulator and optimized unsigned device app built and inspected |
| Physical-device release validation | 15% | 0% | No physical Android/iPhone release matrix has been executed in this environment |
| Publisher, signing and store readiness | 5% | 10% | Signing configuration and release/privacy instructions exist; actual identities, public policy, store setup and submission remain |

## Implemented

- **Last Light:** original two-to-six-player bluffing game, a 30-card deck,
  private hands, one-to-three-card claims, challenges, six-light penalties,
  elimination, round advancement, winner and rematch flows.
- **Practice:** playable bot matches using the same game authority as
  multiplayer, rather than a separate rules implementation.
- **Local multiplayer:** host-authoritative sessions, lobby readiness,
  invitation sharing/pasting, QR display and native QR scanning, optional
  discovery, reconnection to the same seat, and recoverable connection errors.
- **Transport and privacy:** native TLS with the full host-certificate pin,
  admission and reconnect credentials, bounded messages and queues, replay and
  revision checks, recipient-specific state, and cryptographic game randomness.
- **App experience:** Home, Host, Join, Lobby, Rules, Settings, gameplay,
  round-result and winner screens; deliberate hand reveal/concealment;
  persisted sound, haptic and reduced-motion preferences.
- **Visual/audio assets:** original cards, rank symbols, launcher artwork and
  sounds; licensed typography; offline credits and the complete notice bundle.
- **Architecture:** shared Kotlin Multiplatform modules for rules, sessions,
  transport, game catalog and UI, with native Android/iOS services and an
  optional shared desktop launcher.

The existing shipping baseline uses Compose and does not require a Godot runtime.
The newly requested Godot comparison is active alongside that baseline, as
described above. Host migration and restoring a live match
after host process death are deliberately outside the agreed first-release
scope; they are not unfinished advertised features.

## Verified results

| Verification | Result and practical limit |
| --- | --- |
| Android/JVM tests | **117 passed**, zero failures/errors/skips in independently inspected reports: core 14, session 27, transport 18, games 7, shared app 47, Android QR 4 |
| Android builds | Debug APK, optimized unsigned APK and unsigned AAB built; lint has zero errors and five classified warnings |
| Android packages | Manifest, permissions, assets/notices, shrinking and native-library alignment inspected; production signing remains separate |
| Android debug and optimized APK runtime | **Both complete passes** on standard API 35 in run 34421746656: rules, settings persistence, hand selection/concealment/background/play/leave, hosting/invitation/share teardown, invalid-invitation recovery, real soft keyboard and 200% text flows. All 52 stage captures and 115 input-geometry records independently inspected |
| iOS shared-native tests | **82 passed**, zero failures/errors/skips: core 14, session 27, transport 10, games 7, app 24 |
| Native Swift TLS tests | **3 passed:** ordered pinned TLS/closure, incorrect-pin rejection, and real Java–Swift interoperability in both host directions |
| iOS UI tests | **3 passed:** Settings navigation, real native hosting/invitation flow, and playable practice with reveal/select/hide/play/leave |
| iOS builds | Simulator test app and optimized unsigned arm64 device app built successfully; iOS 15 deployment metadata and iOS 26.4 SDK confirmed |
| iOS package audit | All 75 expected resource files match source; app plus five Swift Crypto privacy manifests present; no test bundle or provisioning profile in the device app |
| Design review | Shared-layout tests and actual Android/iOS captures independently inspected; no blocking defect in the reviewed images |

The complete iOS job passed at `987d380` in
[run 34398824935](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34398824935).
Its 82 native tests, six XCTest results, both TLS fixture terminal states
(`Closed`), screenshots and app archives were independently inspected. Subsequent
commits change validation scripts, documentation and isolated Godot comparison
files, not the shipping app or iOS test sources.

## Godot comparison progress

| Workstream | Completed evidence | Still required |
| --- | --- | --- |
| Engine and build setup | Official Godot 4.7.2 executable and Android AAR independently checksum-verified; isolated Gradle outputs; actual 1,532,712-byte PCK with 136 entries imported/exported and independently mounted | Refreshed UI package and deterministic export recheck after fixing generated scene-node IDs |
| Shared artwork/fonts/audio | 54 mapped source files and 47 import settings independently hash-checked; all 47 runtime resources loaded; initial PCK resources/notices independently verified; all 19 Android notice sources audited | Final package inclusion and device filtering/playback |
| Rules bridge | Source findings closed; 12 JVM behavior tests passed independently; all 15 real-authority fixtures reproduce byte-for-byte; GDScript JSON parser corpus has 61 passes | Remaining renderer/native boundary qualification |
| 2D renderer | Actual packed desktop match passed: 21 accepted renderer events, 42 authority snapshots, 2 player plays, 2 challenges, 13 round continuations, winner/lobby/fresh-entry/exit and clean process exit; matched captures published | Latest touch/large-text fixes require refreshed artifact review; native runtime remains open |
| 3D renderer | Same complete packed match and clean exit passed; its 42-view authority trace exactly matches 2D; real local selection/privacy checks and captures exist | Latest narrow/large-text, selection and winner-information fixes require refreshed artifact review; native runtime remains open |
| Android host | Real official AAR host, chooser, engine-process ownership, bounded bridge and privacy cover implemented; 4 queue tests pass; debug APK, optimized unsigned APK and unsigned AAB built; debug/release lint has zero errors and 8 classified warnings | Repackage latest UI and nine added dependency notices; execute both-mode input, background, exit/re-entry and teardown checks |
| iOS host | Native engine/archive compiled and audited; new runtime, Swift host and five XCTest sources compile on macOS. First executable attempt failed on a missing archive search path; correction pushed and another diagnostic run dispatched | Successful executable link/runtime tests, repeat entry, real KMP practice facade and native-view qualification |
| Delivery and comparison | Runnable desktop 2D/3D commands committed; identical complete authority traces and clean exits independently verified; 22 matching capture records published | Refreshed comparison after UI fixes and installable native previews with executed platform checks |

[The Godot work plan](../godot/README.md) records ownership and acceptance.
Godot mobile accessibility, physical-device graphics/performance, networking
integration and publisher gates remain separate. Neither renderer is selected
for production; both are retained for the user's comparison.

## Still unfinished

### 1. Additional Android platform qualification — API 35 gate complete

Both debug and optimized test-signed APKs passed the complete acceptance flow in
[run 34421746656](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34421746656),
at `d3418f1`. Independent review verified 117 actual test cases, package integrity,
the optimized test signature/payload, all 52 stage captures and 115 input records.
The actual APK SHA-256 values are:

- Debug: `69c168aaec7c5bf3900515d1c12e6d99f379d596046a78be41047b3d5f911598`.
- Optimized test-signed: `a3c7f01fc586dc76d868bce781951048def30d69cda662521e29a4ba447e7a60`.

The viewport fix is exercised by both APKs, including normal and 200% Join
submission. An expired Launcher3 ANR at 00:45:38–39 is retained in the empty-AVD
preparation logs; launcher readiness and the first PartyDeck installation at
00:46:06 occurred afterward. No reboot or crash-dialog dismissal occurred, and
no new ANR/crash appeared during either application's acceptance flow.

Recent API 36 runs failed while preparing an **empty emulator**, before either
APK was installed. ANGLE reduced shader startup substantially, but System UI
still hit startup ANRs on the two-core runner. Reducing physical resolution to
720 × 1600 at 280 dpi preserved the logical layout but did not resolve it.

Standard API 35 runs 34413839964, 34417204089 and 34421746656 passed first-boot
preparation with actual API and 720 × 1600/280 dpi verified. The earlier cached
HOME handoff defect is fixed and runtime-proven. The post-keyboard focus fix is
also exercised by both APKs. **API 36 remains an unresolved runner/runtime
qualification**; the API 35 results do not close it. All soft keyboard, focus,
text, crash, deadline and application assertions remained enforced.

### 2. Physical devices, accessibility and performance — not executed

- Android-to-iPhone, iPhone-to-Android and same-platform Wi-Fi sessions,
  including two-to-six players and a complete match/rematch.
- Camera scanning, local-network permission denial/recovery, real share and
  clipboard behavior, Wi-Fi loss, reconnection and host loss.
- Backgrounding, locking, app-switcher privacy, process death and cleanup on
  actual phones.
- TalkBack/VoiceOver traversal, large text, small/large screens, iPad/landscape,
  and supported minimum OS versions.
- Release-build launch, frame pacing, memory and battery/network measurements.

Simulator/JVM results do not close these gates. No physical-device performance
numbers or guaranteed frame rate have been claimed.

### 3. Publisher configuration and store release — external input required

- Publisher name, public privacy-policy URL and support contact. These have
  been requested; the public in-app policy route depends on those details.
- Production Android signing identity and Apple signing team/provisioning.
- Play Console/App Store Connect access, store listing/screenshots, age/content
  and privacy disclosures, and applicable export answers.
- Signed testing-track/TestFlight installation and final store validation.
- Publisher assessment of Adobe DNG SDK's commercial terms. DNG code is
  confirmed in the optimized iOS renderer. Required notices are bundled;
  including notices alone does not settle its commercial indemnification terms.

## Existing deliverables

- Source and coherent milestone commits are pushed to the private repository.
- The [screenshot gallery](screenshots/README.md) contains 325 published app
  captures and historical iterations, plus linked artwork proofs. New Godot
  and native captures are added with their platform/source/qualification labels.
- Build, test and signing commands are documented in [the main README](../README.md),
  [script instructions](../scripts/README.md) and [iOS instructions](../iosApp/README.md).
- Verified iOS archives and independent test summaries are copied locally to
  `artifacts/delivery/`, with hashes in `ios-artifacts.json`.
- Exact package hashes, inspected evidence and the complete release gate matrix
  are in [release qualification](release-qualification.md).
- Supporting records: [game review](game-review.md), [design review](design-review.md),
  [security review](security-review.md), [privacy inventory](privacy.md), and
  [dependency licenses](dependency-licenses.md).

The original-scope estimate is now **81%** after both API 35 runtime passes.
The additional platform, physical-device and publisher gates must be completed
before claiming 100% production readiness. Godot work continues separately from
that percentage, with both renderers retained for the user's choice.
