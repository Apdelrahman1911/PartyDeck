# PartyDeck status report

**Snapshot: 2026-09-10, 02:19 UTC.** Latest completed Android baseline validation commit:
`d3418f150e908667560767e4b825f8968b337df3`.

**Historical production-release estimate for the original Compose scope: 81%,
pending refreshed qualification.** The planned features were implemented at the
validated baseline. Later review found that starting Practice from Rules could
leave Rules visible over the new session. The shared-controller fix and a local
regression pass are recorded below; fresh Android/iOS validation is running in
[run 34428798269](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34428798269)
at `15ab6408d16c04941d133214b03d4e8c6c42ced9`.
Physical-device verification, Android API 36 qualification, and publisher/store
setup also remain. The app is **not yet cleared for public distribution**.

These historical percentages are milestone estimates, not code coverage, a guarantee of
reliability, or an estimate of time remaining. The weighted calculation below
is 80.5%, rounded to 81%, for the previously validated baseline. Both Android APK
variants passed that run's complete configured flow on standard API 35,
independently verified; it did not tap the Rules Practice button. The estimate
has not been refreshed for the subsequent fix.

**Expanded scope:** the user requested **both 2D and 3D Godot presentations**,
built in parallel for comparison. The 81% estimate applies only to the original
Compose scope. Godot progress is recorded separately below without a readiness
percentage; engine compilation and screenshots do not establish a playable
native integration.

| Workstream | Weight | Historical baseline completion | What the percentage means |
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

## Verified baseline results

These results apply to the cited revisions and executed assertions. They do not
qualify the newer shared-controller fix or the Godot hosts.

| Verification | Result and practical limit |
| --- | --- |
| Android/JVM tests | **117 passed**, zero failures/errors/skips in independently inspected reports: core 14, session 27, transport 18, games 7, shared app 47, Android QR 4 |
| Android builds | Debug APK, optimized unsigned APK and unsigned AAB built; lint has zero errors and five classified warnings |
| Android packages | Manifest, permissions, assets/notices, shrinking and native-library alignment inspected; production signing remains separate |
| Android debug and optimized APK runtime | **Both passed the configured flow** on standard API 35 in run 34421746656: Rules display, settings persistence, hand selection/concealment/background/play/leave, hosting/invitation/share teardown, invalid-invitation recovery, real soft keyboard and 200% text flows. All 52 stage captures and 115 input-geometry records independently inspected. Rules→Practice was not tapped |
| iOS shared-native tests | **82 passed**, zero failures/errors/skips: core 14, session 27, transport 10, games 7, app 24 |
| Native Swift TLS tests | **3 passed:** ordered pinned TLS/closure, incorrect-pin rejection, and real Java–Swift interoperability in both host directions |
| iOS UI tests | **3 passed:** Settings navigation, real native hosting/invitation flow, and playable practice with reveal/select/hide/play/leave |
| iOS builds | Simulator test app and optimized unsigned arm64 device app built successfully; iOS 15 deployment metadata and iOS 26.4 SDK confirmed |
| iOS package audit | All 75 expected resource files match source; app plus five Swift Crypto privacy manifests present; no test bundle or provisioning profile in the device app |
| Design review | Shared-layout tests and actual Android/iOS captures independently inspected; this historical evidence did not cover the newly found Rules→Practice navigation defect |

The complete iOS job passed at `987d380` in
[run 34398824935](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34398824935).
Its 82 native tests, six XCTest results, both TLS fixture terminal states
(`Closed`), screenshots and app archives were independently inspected. The new
Rules→Practice fix changes the shipping shared controller and its common tests
after that validated revision. The earlier iOS pass remains historical evidence;
it does not qualify the changed shipping sources.

## Godot comparison progress

| Workstream | Completed evidence | Still required |
| --- | --- | --- |
| Engine and build setup | Official Godot 4.7.2 executable and Android AAR independently checksum-verified; isolated Gradle outputs; both initial and refreshed 136-entry packs independently mounted; all refreshed payloads match an independent export | Archive byte reproducibility: notice payload order still varies in upstream export; tooling correction is underway |
| Shared artwork/fonts/audio | 54 mapped source files and 47 import settings independently hash-checked; all 47 runtime resources loaded; initial PCK resources/notices independently verified; all 19 Android notice sources audited | Final package inclusion and device filtering/playback |
| Rules bridge | Source findings closed; 12 JVM behavior tests passed independently; all 15 real-authority fixtures reproduce byte-for-byte; GDScript JSON parser corpus has 61 passes | Remaining renderer/native boundary qualification |
| 2D renderer | Latest touch/large-text fixes passed the full packed desktop match and independent review: 21 renderer events, 42 authority snapshots, 2 player plays, 2 challenges, 13 round continuations, winner/lobby/fresh-entry/exit and clean exit | Native input/lifecycle execution and refreshed deterministic archive |
| 3D renderer | Latest narrow/large-text, selection and winner-information fixes passed the same complete packed match, clean exit and independent review; its 42-view authority trace exactly matches 2D | Native input/lifecycle execution and refreshed deterministic archive |
| Android host | Real official AAR host, chooser, engine-process ownership, bounded bridge and privacy cover implemented; 4 queue tests pass; refreshed debug APK, optimized unsigned APK and unsigned AAB built with all notice sources; lint has zero errors and 8 classified warnings | Final package audit; correct transient UI-dump handling and execute both-mode input, background, exit/re-entry and teardown checks |
| iOS host | Native engine/archive compiled and audited. Attempts 34423784931 and 34425278588 failed at link, with zero lifecycle tests executed. Reviewed platform glue and shell idle-timer restoration fixes are pushed; run 34428221586 is executing them | Successful link and all five lifecycle tests with the fixes; native view, cleanup and re-entry qualification remain open |
| iOS authority facade | Real authority facade passed owner/independent JVM tests and all 20 native bridge tests in run 34427976260; actual framework compiled, nine declarations checked and Swift import typechecked | Actual Swift caller and factory execution, host integration and an authority-driven iOS match |
| Delivery and comparison | Runnable desktop 2D/3D commands committed; identical complete authority traces and clean exits independently verified; 22 matching capture records published | Refreshed comparison after UI fixes and installable native previews with executed platform checks |

The first workflow scheduling native Android checks for both Godot modes,
[run 34427418175](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34427418175),
**failed** at `c0474960f76459bf07160ec3dba6dcbb084af3ea`.
Its build, desktop gameplay and package checks passed. All four native cases
installed the app and tapped their real launch button, then stopped while
reading a missing fresh UI-automation XML file during match entry. No gameplay
action or complete native entry was accepted. The checker is being corrected
to retry transient dump failures within its existing deadline while retaining
failure evidence and crash rejection. This run also predates the final renderer
changes and the shipping-controller fix.

The refreshed local PCK is 1,542,328 bytes, SHA-256
`0b3de6b276d15972708cfc7919d7f2f5bf2aefe8a05afb8859357e7139057d37`.
Its mounted content, final complete matched gameplay and 22 capture receipts
passed independent review; rebuilt Android packaging passed locally. A second
export contains the same 136 payloads but orders nine notice payloads differently.
The archive-order correction and final package inspection remain open.

The first iOS host link failed because its archive search path was missing.
After that path was corrected, the second link identified two SDL UIKit device
query symbols and two Apple export-plugin hooks. The frozen source supplies
those platform definitions and restores the shell's previous idle-timer policy
on terminal paths. Their new native probe is
[run 34428221586](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34428221586)
at `a04f22be8623bec9fbf38d4e74d8f96a94ebb225`; it has not completed.
Separately, the authority framework passed
[run 34427976260](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34427976260)
at `cf6434df2fd32909f70feee68bfcb82e527e2b70`. Its framework/header and Swift
module import do not establish a compiled Swift gameplay caller or native match.
The [iOS host record](../godot/ios-host/README.md) and
[independent facade review](../godot/reviews/ios-facade-review.md) keep source,
common-code, framework, host and runtime evidence separate.

[The Godot work plan](../godot/README.md) records ownership and acceptance.
Godot mobile accessibility, physical-device graphics/performance, networking
integration and publisher gates remain separate. Neither renderer is selected
for production; both are retained for the user's comparison.

## Still unfinished

### 1. Refreshed native qualification and additional Android platforms

The Rules Practice button was located and captured in the completed Android
baseline flow, without being tapped. Later review found that a new practice
session could start while the Rules screen stayed open. The shared controller
now opens the session when starting new practice. The updated controller suite
has **9 passing JVM tests**, including a regression for Rules→Practice entry,
preserving Rules during an existing live session, and clean leave/teardown.
This is local common-code evidence; the changed app still needs native Android
and iOS qualification. The historical 117-test and API 35 receipts above must
not be relabeled as validation of this fix.

Both debug and optimized test-signed APKs passed the then-configured acceptance flow in
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
- The committed and published [screenshot gallery](screenshots/README.md)
  contains **477 app/renderer captures**, 469 evidence files, and four
  linked artwork proofs after publication commit `19501a2`. The count is checked
  against the committed manifest; no pending batch is included.
- Build, test and signing commands are documented in [the main README](../README.md),
  [script instructions](../scripts/README.md) and [iOS instructions](../iosApp/README.md).
- Verified iOS archives and independent test summaries are copied locally to
  `artifacts/delivery/`, with hashes in `ios-artifacts.json`.
- Exact package hashes, inspected evidence and the complete release gate matrix
  are in [release qualification](release-qualification.md).
- Supporting records: [game review](game-review.md), [design review](design-review.md),
  [security review](security-review.md), [privacy inventory](privacy.md), and
  [dependency licenses](dependency-licenses.md).

The **81%** original-scope estimate is retained as a historical baseline after
the two configured API 35 passes, pending refreshed qualification of the shared
controller fix. Native reruns, additional platform, physical-device and
publisher gates remain open. Godot has no supported production-readiness
percentage; both renderers remain available for comparison.
