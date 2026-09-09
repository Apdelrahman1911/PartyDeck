# PartyDeck status report

**Snapshot: 2026-09-09, 22:07 UTC.** Latest validation commit:
`b192d342e7830841451063ad642e71159dce6be2`.

**Estimated overall progress toward public production release: 77%.** The
planned first-release application features are implemented. The remaining work
is mainly Android runtime qualification, physical-device verification, and
publisher/store setup. The app is **not yet cleared for public distribution**.

These percentages are milestone estimates, not code coverage, a guarantee of
reliability, or an estimate of time remaining. The weighted calculation below
is 76.5%, rounded to 77%.

| Workstream | Weight | Completion | What the percentage means |
| --- | ---: | ---: | --- |
| Core features and architecture | 30% | 100% | Planned first-release game, authority, protocol, transport, practice and app flows implemented |
| UI, assets and accessibility implementation | 15% | 100% | Screens, responsive layouts, original assets, controls, preferences and accessibility semantics implemented; device validation is separate |
| Automated qualification | 20% | 80% | Four of five major gates passed: Android/JVM tests, iOS shared tests, Swift TLS tests, iOS UI tests; full Android APK runtime gate remains open |
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

Godot has an extension interface for future games. Last Light uses Compose and
does not require a Godot runtime. Host migration and restoring a live match
after host process death are deliberately outside the agreed first-release
scope; they are not unfinished advertised features.

## Verified results

| Verification | Result and practical limit |
| --- | --- |
| Android/JVM tests | **117 passed**, zero failures/errors/skips in independently inspected reports: core 14, session 27, transport 18, games 7, shared app 47, Android QR 4 |
| Android builds | Debug APK, optimized unsigned APK and unsigned AAB built; lint has zero errors and five classified warnings |
| Android packages | Manifest, permissions, assets/notices, shrinking and native-library alignment inspected; production signing remains separate |
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
commits change validation scripts and documentation, not the shipping app or
iOS test sources.

## Still unfinished

### 1. Complete Android APK runtime qualification — active work

There is not yet a complete passing run of **both** debug and optimized APK
acceptance flows. Earlier optimized-app execution verified several real flows,
including practice, concealment, settings persistence, hosting and sharing, but
the overall run failed on a text-entry automation defect. That defect was fixed
and reviewed; the corrected complete run still needs execution evidence.

Recent API 36 runs failed while preparing an **empty emulator**, before either
APK was installed. ANGLE reduced shader startup substantially, but System UI
still hit startup ANRs on the two-core runner. Reducing physical resolution to
720 × 1600 at 280 dpi preserved the logical layout but did not resolve it.

The latest standard API 35 run,
[34409391037](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34409391037),
also stopped before app installation, but its evidence shows a healthy launcher
and no ANR. The automation cached Android's temporary setup Activity as the HOME
target, then kept waiting for it after setup handed control to Launcher3. That
specific readiness race is now being fixed and reviewed. API 35 is the configurable
functional baseline; **neither API 35 nor API 36 full runtime acceptance is
currently claimed passed**.

Required remaining evidence includes the actual soft keyboard, 200% system text,
invalid-invitation editing/recovery, final rules action, and the complete
practice/host/leave sequence for both APK variants. Crash checks, deadlines and
acceptance assertions remain enforced.

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
- Build, test and signing commands are documented in [the main README](../README.md),
  [script instructions](../scripts/README.md) and [iOS instructions](../iosApp/README.md).
- Verified iOS archives and independent test summaries are copied locally to
  `artifacts/delivery/`, with hashes in `ios-artifacts.json`.
- Exact package hashes, inspected evidence and the complete release gate matrix
  are in [release qualification](release-qualification.md).
- Supporting records: [game review](game-review.md), [design review](design-review.md),
  [security review](security-review.md), [privacy inventory](privacy.md), and
  [dependency licenses](dependency-licenses.md).

Work continues on the Android runtime blocker. A successful complete Android
run would move the weighted estimate from **77% to about 81%**. The remaining
device and publisher gates must then be completed before claiming 100% production
readiness.
