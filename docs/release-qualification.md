# Release qualification

Review date: **2026-09-10**. This records executed evidence and remaining
acceptance work for PartyDeck's first release. Source inspection, JVM rendering,
mobile runtime tests, physical-network tests, and distribution signing are
recorded separately.

## Current decision

**Not yet qualified for public distribution.** Independent inspection of the
refreshed Compose baseline's optimized unsigned iOS device package passed at
**`15ab6408d16c04941d133214b03d4e8c6c42ced9`** in
[run 34428798269](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34428798269).
Current implementation and native-runtime qualification are tracked in
[STATUS.md](STATUS.md). Physical-device multiplayer, accessibility/performance
measurements, production signing, store validation, and publisher review of
the DNG commercial terms remain open.

## Refreshed Compose iOS device package

The independently inspected artifacts from **15ab640 / run 34428798269** are:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Optimized unsigned device app, `.tar.gz` | 15,624,845 | `d77f59a8272803879a31ed6b56fb32db7d1ab4ae8deae940f7874e871e10b89f` |
| Packaged `PartyDeck` executable | 50,360,472 | `611a9d4669fd07e07ae6314fdd99ca719fbe02544534700fd3d9053eace38b75` |

All **14 package-review checks passed**. Compared with the accepted `987d380`
device app, the file set remains **118 files / 51,902,947 bytes**; only the
executable changed. The other **117 files** are byte-identical. All **75**
font/audio/license resources match the inspected repository source, including
the complete **258,067-byte** notice aggregate, SHA-256
`d5c47822bd82a0f2b775b1f8c76863a4e5d5de7fbe6ca1aa1ad2713794a32066`.
All **six privacy manifests** and the entire `Info.plist` are unchanged; the
app privacy manifest also matches source.

The app remains one **ARM64** executable with minimum **iOS 15.0**, built with **iOS SDK
26.4 / Xcode 26.4.1**, identifier `dev.partydeck.app`, version **1.0.0 / 1**.
Imported libraries and inspected privacy-related imports are unchanged. No
Mach-O code signature, `_CodeSignature`, provisioning profile, test bundle,
key-container file, or inspected test-fixture marker was found. The Swift lock
is byte-identical, retaining Certificates **1.20.0**, Crypto **4.5.2**, and
ASN.1 **1.7.2**. The new link map retains **1,635 live DNG symbols across 58
objects**, so the DNG publisher gate remains open.

The shipping controller changed at `15ab640`: its source sets
`AppScreen.SESSION` during practice startup. Both link maps and executable
symbol tables identify the live `PartyDeckController.startAuthority#internal`
body, which changed from **2,856 to 3,512 bytes**. Retained CI logs establish
the exact checkout, `:composeApp:linkReleaseFrameworkIosArm64`, and successful
Release device build with `CODE_SIGNING_ALLOWED=NO`. This establishes that the
changed controller body is linked into the inspected package.

The receipt is
`/tmp/partydeck-release-qa/final-15ab640/ios/device-audit-summary.json`;
`device-package-review.json` and `device-binary-and-controller-review.json` in
the same directory preserve the detailed comparisons and linked function
hashes. This review did not rerun native tests or execute the device app.
Runtime behavior, Apple codesign validation, publisher signing, and physical
device qualification remain separate evidence. This acceptance applies to the
exact Compose artifact above; it does not qualify replacement engine packages.

## Earlier Compose baseline evidence

The following gate table, package tables, and earlier executed evidence are
historical records. iOS shared-native and XCTest validation, simulator execution,
and optimized unsigned device-package inspection passed at
**`987d380967149d80d8ba5761e206ecdf7386af25`** in
[run 34398824935](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34398824935).
Android build/tests/package inspection passed there, but its emulator failed
before app installation. The Android-only follow-up at
**`6bb4dd7d28026443c0d4b286afbbf75ef127ec19`**, in
[run 34402895350](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34402895350),
also failed during empty-AVD preparation. Android runtime was unqualified at
that checkpoint; later outcomes are tracked in [STATUS.md](STATUS.md).

| Gate | Historical evidence at 987d380 |
| --- | --- |
| Game/session correctness | 117 Android/JVM and 82 iOS shared-native tests passed in the preserved CI reports; independent behavioral review is in [game-review.md](game-review.md) |
| Android application | Build/lint and optimized package inspection passed; full debug/optimized runtime qualification remains open |
| iOS application | 3 native TLS and 3 UI XCTest tests passed; actual simulator and optimized unsigned device bundles inspected |
| LAN integration | Real JVM and Java–Swift TLS in both host directions passed; physical mixed Android/iPhone sessions and six devices remain unverified |
| Lifecycle | Controller/callback tests and earlier Android emulator practice concealment passed; actual phone suspension, app-switcher images, and process-death checks remain open |
| Accessibility and presentation | Shared layout tests and captured Android/iOS screens independently reviewed; native spoken traversal, large-text iOS, and device performance remain open |
| Privacy and dependency notices | Android and iOS packaged manifests/resources inspected; all 64 notice entries preserved. DNG code is confirmed in the optimized iOS executable; see [privacy.md](privacy.md), [security-review.md](security-review.md), and [dependency-licenses.md](dependency-licenses.md) |
| Signing and distribution | No production identity or provisioning profile supplied; store installation/validation remains required |

The following Android artifacts are from **987d380 / run 34398824935**. Their
optimized contents match the audited local packages apart from recorded Git
revision metadata; this run did not install either APK.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Android Debug APK | 22,645,979 | `26490a291e028d02b0c3a005ff2a642ba809caba6768d5f655ae77c76a58d9a1` |
| Optimized unsigned APK | 4,522,956 | `daf4aa1a3a2133d4241de540c7cabbb10f1ea0bf4e7ff0a5ffe82648a9a3d531` |
| Optimized unsigned AAB | 7,655,558 | `f091e4b8f44572085c9682806bfa74e59e31d5f55eb3a6ac9e75075775196ba3` |

The actual iOS app archives from the same revision/run were independently hashed
and inspected. The simulator archive includes its XCTest support; the device
archive is an unsigned build, not an installable store release.

| App archive | Bytes | SHA-256 |
| --- | ---: | --- |
| Simulator test app, `.tar.gz` | 27,711,617 | `5ea685a6dd4e5f2a0f0f3bb979c40834127b73d7aaccbc07145bb71b7f93d93a` |
| Optimized unsigned device app, `.tar.gz` | 15,625,434 | `db8be5bd25a5f895a21f21bc04f04cb29620cb09c70153c6814e2551f71b24e4` |

Local delivery copies are under `artifacts/delivery/` when present. Independent
inspection records are in `/tmp/partydeck-release-qa/final-987d380/`; the earlier
local Android audit is retained in `/tmp/partydeck-release-qa/final-c73a659/`.
CI artifacts and local copies are qualification evidence, not public releases.

## Verified platform baseline

- The checked-in Android configuration selects application ID
  `dev.partydeck.app`, minimum SDK 26, compile SDK 37.1, and target SDK 36. The
  compile SDK was raised to satisfy the selected dependencies' AAR metadata;
  the target SDK remains a separate runtime-policy choice.
- Google Play requires new phone apps and updates to target **Android 16 / API
  36 or later from August 31, 2026**. This requirement was verified against the
  official page updated September 1, 2026. [1]
- Apple's upload requirement since **April 28, 2026** is **Xcode 26 or later
  using the iOS 26 SDK or later**. This is the build-SDK floor, not a requirement
  to exclude older supported iPhones. CI selects **Xcode 26.4.1 / iOS SDK 26.4**
  on ARM64 `macos-26`; the app's deployment target is **iOS 15**. [2]
- The selected toolchain, compatibility sources, and independent bootstrap
  results live in [research/toolchain.md](research/toolchain.md). Version pins
  are not evidence that every platform has built successfully.
- Current Android local-network documentation requires the
  `ACCESS_LOCAL_NETWORK` runtime permission for apps targeting SDK **37 or
  later**. For target SDK below 37, `INTERNET` receives an implicit local-network
  grant; the documentation says not to request the new permission before
  targeting 37. Android 16's restriction opt-in is a separate compatibility
  test. Revisit this behavior when increasing the target SDK. [3]
- Apple's local-network permission applies to outgoing local TCP connections
  regardless of networking API. Add `NSLocalNetworkUsageDescription`. Add
  `NSBonjourServices` only when the implementation registers or browses the
  corresponding Bonjour services. Multicast/broadcast behavior has separate
  entitlement requirements and must be reviewed if introduced. **The simulator
  does not support local-network privacy testing.** [4]

## Executed evidence at the earlier Compose baseline

Unless a different revision is named, this section records **987d380 / run
34398824935**. Its test counts and runtime outcomes do not establish those of
the refreshed Compose baseline or replacement engine packages.

### Automated tests and presentation

The reviewer independently parsed **20 Android/JVM XML reports: 117 tests,
0 failures, 0 errors, 0 skips** at `987d380`: core 14, session 27, transport 18,
games 7, Compose app 47, and Android QR decoder 4. The complete local validation
at `c73a659` also passed 117 tests. The formerly failing immediate TCP-refusal
assertion now checks that the incoming stream closes and the listener refuses
connections within a bound; the repeated CI suite passed.

The preserved **13 iOS shared-native XML reports contain 82 tests**, with zero
failures, errors, or skips: core 14, session 27, transport 10, games 7, and
Compose app/controller 24. This is now a parsed artifact count, superseding the
earlier run whose XML upload failed.

The independent [design review](design-review.md) closed the observed shared-UI
findings. The 7 gameplay, 10 shell, and 4 Home tests include compact/large-text
layouts, selection/concealment, scrolling, and results. The complete legal text
was reached at **320 dp / 200%** through **222 bounded sections**. Native
Android and iOS captures have also been reviewed with their execution limits;
none establishes spoken screen-reader traversal or physical-device performance.

### Android runtime

At `987d380`, the build, lint, and package tasks passed. Empty-AVD preparation
then captured a **System UI ANR** on both its first boot and the single permitted
reboot. The reviewer verified changed kernel boot IDs, empty PartyDeck presence
checks, retained failure trees/images/logs, and refusal of another recovery.
**Neither APK was installed.** The follow-up Android-only run above also failed
before installation. Its graphics change reduced shader initialization time,
but a System UI startup ANR remained. These failures preceded later runtime work
tracked in [STATUS.md](STATUS.md).

Earlier `c73a659` execution of a disposable-test-signed optimized APK passed
practice reveal/select/hide, background-return concealment, one-card play,
settings persistence, real native hosting, invitation actions, and normal-size
invalid Join recovery before failing a 200% text-entry automation step. Its APK
SHA-256 was `2c4adc0151dbcc2330507d3761eebc4732a699037557a0db0a73ed8fc615efb9`.
It remains partial runtime evidence. The old failures, diagnosis, bounded
preparation policy, and helper verification are recorded in
[engine/CI research](research/engine-ci.md) and [Android research](research/android.md).
No clean runtime result is inferred from a helper replay or an infrastructure fix.

### iOS runtime and packaged application

The successful `987d380` macOS job used **Xcode 26.4.1 / iOS SDK 26.4** and
recorded the actual Simulator and Release device builds:

- **Three native TLS XCTest tests passed:** ordered pinned frames/closure,
  wrong-pin rejection, and real Java–Swift TLS in both host directions with
  exact **65,536-byte and 20,000-byte** payloads and shutdown. These are native
  simulator/host-loopback exchanges, not physical Wi-Fi tests.
- **Three UI XCTest tests passed:** shared Settings navigation; real native
  hosting and invitation/QR/action visibility followed by closing/leaving;
  and playable practice with reveal/select/hide, private accessibility-node
  removal, selection clearing, accepted play, round continuation, and leave.
  The host test does not execute native Copy or Share effects.
- All **eight planned screenshots** were exported from an iPhone 17 simulator
  at **1206 × 2622**. Independent design review found no visual blocker or
  captured invitation credential. These portrait/default-text images do not
  cover iOS large text, landscape/iPad, visible keyboard layout, VoiceOver,
  settings persistence, backgrounding, or app-switcher privacy.
- The device build executed `:composeApp:linkReleaseFrameworkIosArm64` and
  produced the actual optimized app with `CODE_SIGNING_ALLOWED=NO`.
  Both bundles encode **arm64, minimum iOS 15, SDK 26.4**, identifier
  `dev.partydeck.app`, version **1.0.0 / 1**, phone/iPad families, camera/local
  network descriptions, Bonjour service `_partydeck._tcp`, and expected
  orientation/icon metadata. This verifies build metadata, not execution on
  an iOS 15 device.
- Both apps contain all **75 source-exact font/audio/license resources**,
  including the entire 258,067-byte aggregate. The device bundle has the app's
  privacy manifest plus **five Swift Crypto manifests**. The app reasons are
  `CA92.1`, `C617.1`, and `35F9.1`; its packaged dictionary matches source.
  Inspecting manifests and binary symbols does not replace Xcode's aggregated
  privacy report for the final distribution archive.
- The optimized device app contains one executable, **50,360,472 bytes**,
  SHA-256 `9df831ae5350bd48e6165f31bc22d31b12b0cc9e085d89581fd5565729b4a283`.
  It has **no Mach-O code signature**, provisioning profile, test bundle,
  debug dylib, key-container files, or inspected test-fixture names. Simulator
  PartyDeck code has linker-generated **ad-hoc** signatures without a team/CMS
  identity; its separate XCTest support is test-only. Signature metadata was
  inspected on Linux; Apple signing verification and store validation remain open.

Package records, resource hashes, Mach-O inventories, and final link-map checks
are retained under `/tmp/partydeck-release-qa/final-987d380/ios/`. The earlier
`c73a659` iOS run passed narrower tests/builds but lost its artifact upload;
the uploaded `987d380` bundles closed that historical inspection gap.

### Android package inspection and signing

The original `c73a659` local packages passed **12 independent tool checks** with
Android Build Tools 36.0.0, `readelf`, `jarsigner`, and hash-verified official
bundletool 1.18.3. The reviewer compared all **492 optimized APK entries and
499 AAB entries** from `987d380` against them: the only content change is
`META-INF/version-control-info.textproto` (under `base/root` in the AAB).
Executable code, manifests, resources, native libraries, and alignment-relevant
ZIP metadata are identical. The package findings therefore remain applicable:

- Actual launcher/version **1.0.0 / 1**, minimum SDK **26**, target **36**,
  optional camera, disabled backup/cleartext, and non-debuggable optimized code.
  Only Internet, Camera, and AndroidX's app-owned signature permission remain.
  Startup has lifecycle/profile initialization; unused network-state permission
  and EmojiCompat font downloading are absent.
- The launcher is the only unprotected exported component. The scanner,
  metadata service, and resource providers are private; ProfileInstaller's
  receiver requires `android.permission.DUMP`. Adaptive icons include the API
  33 monochrome layer.
- Optimized APK/AAB are **unsigned**. Bundle validation passes; APKs pass
  `zipalign -c -P 16 -v 4`, and the AAB declares `PAGE_ALIGNMENT_16K` with
  uncompressed native-library support. All **12 native libraries** across four
  ABIs have ELF LOAD alignment **`0x4000`**. An executed 16 KB device/image is
  still a separate gate.
- All **75** inspected font/audio/license resources match source. No
  key-container files or named test-fixture classes were found in the inspected
  package entries/DEX. Android Debug signing is a development identity.

Lint has **0 errors / 5 warnings**. Bouncy Castle's flagged trust-all EST helper
is removed completely by R8 (`JcaJceUtils`, `$1`, `$2`); it was not blanket
suppressed. The other warnings concern the selected target SDK and icon/API
fallback metadata. Actual monochrome resources were checked in both variants.

The disposable signing helper separately passed six independent acceptance/
rejection cases, preserving the original unsigned package and ZIP contents.
Its private key is created outside artifacts and deleted on exit. Such runtime
copies are explicitly **test signed**, without a production identity.

### Assets and dependency notices

The final aggregate is **258,067 bytes**, SHA-256
`d5c47822bd82a0f2b775b1f8c76863a4e5d5de7fbe6ca1aa1ad2713794a32066`.
All **64 notice entries**, including 56 runtime entries, were independently
checked against source hashes, resource copies, complete text, and titles.
All **279 cached dependency artifacts** matched the recorded binary inventory.
The actual `987d380` Xcode lock preserves Swift Certificates **1.20.0**, Swift
Crypto **4.5.2**, and Swift ASN.1 **1.7.2** at their audited revisions.

The optimized iOS link map confirms **1,635 live symbols across 58 DNG SDK
objects**; twelve symbol addresses were cross-checked in the actual executable.
DNG inclusion is established, and its complete notices/acknowledgment ship in
both app bundles. The commercial terms remain a publisher obligation; see
[dependency licenses](dependency-licenses.md).

All four font binaries matched pinned upstream files. All six original WAVs
passed format/signal checks: 44.1 kHz mono 16-bit PCM, 0.07–1.28 seconds,
zero-valued endpoints, no clipped samples. Android and iOS packaging now pass;
physical-device listening and feedback behavior remain separate checks.

## Runnable build and integration gates

Record the exact commit and tool versions before final verification. Keep test
reports, CI links, APK/AAB or app artifacts, and screenshots associated with
that commit. Record a later source change if it invalidates earlier evidence.

### Android

1. Build the real `androidApp` launcher and common code from a clean checkout.
   Run the meaningful JVM tests and Android lint. Verify the launcher intent,
   exported components, app label/icon, minimum/target SDK, backup policy, and
   only permissions actually needed by the final implementation.
2. Build the optimized release variant as well as debug. Check serialization,
   resource loading, transport factories, and shrinker behavior in that variant.
   An unsigned release artifact is useful build evidence, not a distributable
   signed release. Never substitute debug signing for a production identity.
3. Inspect APK/AAB contents for accidental debug assets, secrets, full game
   states, bundled development certificates, and unnecessary native engines.
   Verify all packaged native ABIs and 16 KB compatibility. For native
   libraries, check both ELF segment alignment and APK zip alignment; do not
   infer compatibility from the Gradle version. Google's documented APK check
   is `zipalign -v -c -P 16 4 APK_NAME.apk`; its bundle guidance also checks
   `PAGE_ALIGNMENT_16K`. Use the installed SDK tool path. [5]
4. Install and cold-launch on an available emulator; exercise menu, rules,
   settings, local practice, host/join, gameplay, results, and Back navigation.
   Record whether this is debug or release. An emulator with loopback routing
   does not prove ordinary Wi-Fi interoperability.
5. Produce the release AAB, verify its signing identity when one is supplied,
   and validate the store-delivered APKs through a testing track. Play App
   Signing and the upload key are distinct. Keep private keys and passwords
   outside Git, build logs, and downloadable CI artifacts. [6]

### iOS

1. On the macOS runner, record `xcodebuild -version` and `xcodebuild -showsdks`.
   Compile the Kotlin/Native simulator framework **and build the actual iOS
   application target** with its Swift entry point, resources, Info.plist, and
   privacy manifest. A framework-only success leaves the shipping app untested.
2. Build the device architecture too. Clearly label unsigned compile/link
   validation; it does not produce an installable App Store release.
3. Boot a supported simulator, install the built app, launch it, and execute the
   critical navigation smoke test. Save XCTest results and a screenshot from
   the running application. Check Compose resources, safe areas, keyboard
   dismissal, portrait/landscape policy, and the real framework bridge.
4. Inspect the final app bundle's Info.plist, bundle identifier/version,
   deployment target, embedded frameworks/resources, app icons, entitlements,
   and included `PrivacyInfo.xcprivacy` files. Generate Xcode's privacy report
   from the final archive and audit required-reason APIs in app and dependencies.
   Empty manifest arrays are not a substitute for that audit. [7][8]
5. With the publisher's team/certificates/profiles, archive, validate, and upload
   to TestFlight. Record signing/export results separately from simulator CI.
   Complete encryption/export-compliance answers for the actual transport;
   using TLS alone does not answer the publisher's questionnaire.

### Transport and session integration

Use the real chosen socket implementation, not only a fake transport. Verify:

- Host creation, correct invitation, invalid invitation, wrong protocol,
  occupied/full lobby, and cancelled joins; input errors must not crash the app.
- Public lobby updates, readiness, match start, a truthful and a bluff
  challenge, elimination, spectating, round continuation, winner, and rematch.
- Every recipient gets only their private projection. Inspect encoded traffic
  at the application boundary: another player's hand, unrevealed claim,
  burnout step, seed, and resume secret must not enter public messages or logs.
- Duplicate/replayed and stale actions cannot advance state twice; a malformed
  or oversized frame cannot terminate the host or grow memory without bound.
- A legitimate reconnect reclaims the same seat and current hand. Invalid
  capability, competing reconnect, old connection, and abandoned handshake
  paths fail predictably. Never recover a seat from display name alone.
- A disconnected required player pauses progression. Explicit host loss ends
  or suspends the session with a clear recovery path; it does not fabricate a
  winner or silently migrate hidden state. Check timeouts are bounded and
  described by the interface.
- Repeated host/join/leave cycles close listeners, sockets, jobs, and native
  callbacks. Reusing the app after an error must not need a process restart.

## Physical-device qualification

These are executable acceptance scenarios that remain open until device
evidence exists. Use at least one Android phone and one iPhone on the same
ordinary Wi-Fi network. Repeat with each platform hosting; include a six-player
session before claiming the advertised maximum. Record phone models, OS builds,
app artifact/commit, router/hotspot arrangement, and timestamps.

| Scenario | Acceptance |
| --- | --- |
| First join, two players, both host directions | New users can find/copy the actual invitation and complete a full match without documentation or a developer console |
| Six players | All clients converge on each result; no private-hand leaks, lost turns, duplicate penalty, or unusable small-screen layout |
| iOS local-network prompt | Allow, deny, initial request race, Settings re-enable, and retry all yield clear recoverable behavior; no false claim that a simulator passed this gate |
| Invitation QR scan, copy, and share | Both platforms scan without uploading frames; denial/cancel leaves the Join form intact; decoded invites require an explicit join; system sharing exposes only the room invitation |
| Wi-Fi disabled, wrong subnet, client isolation, unreachable host | Join fails within a bounded period with actionable guidance; leaving or retrying remains responsive |
| Client backgrounds, locks screen, or briefly loses Wi-Fi | Authority does not invent turns; recovery restores the authenticated seat and latest state within the supported reconnect policy |
| Host backgrounds, locks, is killed, or loses Wi-Fi | Peers receive an understandable paused/ended state within the implemented timeout; return-home/rehost works |
| Android recreation and process death | Recreation follows the documented session policy; a killed process is not promised a recoverable seat unless credentials/state actually survive securely |
| iOS app switcher | Hidden cards and invitations do not appear in the background snapshot if the product promises concealment; background resources stop as intended |
| Voluntary leave and rematch | Destructive leaving is clear, listeners close, and a new room works without old peers or state leaking into it |

iOS can suspend background scenes and disconnect them to reclaim resources.
Continuous host service in the background must not be advertised without a
separately justified platform design and device evidence. [9]

## Accessibility, presentation, and performance

- Test TalkBack and VoiceOver against the real platform app: focus order,
  distinct selected-card states, action labels, current turn, round results,
  and disabled actions must make sense without looking at the screen. Never
  announce another player's private cards. A hand reveal should be deliberate.
- Test large system text, a small phone, a tall phone, and a tablet. Controls and
  critical guidance must remain reachable; safe-area/IME insets and scrolling
  must prevent overlap. Test contrast against rendered backgrounds and do not
  communicate rank, readiness, danger, or result by color alone.
- Adopt at least 48 dp interactive targets in common mobile UI. Android's
  Compose guidance uses 48 dp; Apple's current iPhone guidance lists 44×44 pt
  as its default control size. These are platform guidance, not interchangeable
  physical units. [10][11]
- Respect reduced motion and mute/haptic settings. Game decisions cannot depend
  on an animation completing or an audio cue being heard. An interrupted result
  animation must not repeat the penalty or block the next valid action.
- Profile a release build on the named physical devices. Record cold-launch
  time, missed frames during card selection/reveal, memory through a full match,
  and network traffic while idle/active. The product target is smooth interaction
  at the device's refresh rate with no sustained frame stalls, unbounded memory
  growth, main-thread network I/O, or unused engine running behind the menu.
  Report measurements and devices; do not claim “60 fps” from a desktop image.
- Desktop is an optional shared-UI smoke and screenshot aid. Its fonts,
  permission model, window insets, and networking do not substitute for Android
  or iOS qualification.

## Distribution gates outside an unsigned build

The publisher must supply or confirm the production signing identity, store
accounts, public support/privacy URL and contact, app name/identifier ownership,
listing screenshots, content/age-rating answers, and applicable export answers.
The final optimized iOS executable includes Adobe DNG SDK code from Skiko.
Its [license](../assets/licenses/runtime/skia_dng_sdk_LICENSE) permits
redistribution but includes a commercial-product indemnification clause (§5);
its [patent license](../assets/licenses/runtime/skia_dng_sdk_PATENTS) requires
the stated DNG acknowledgement. The release reviewer independently read those
terms and confirmed live linked symbols and packaged acknowledgments. The
publisher must assess the commercial terms before commercial distribution.
Adding a notice alone does not resolve that separate obligation.

Rate the shipped **non-graphic six-light fuse** presentation and actual content;
do not assign a rating by analogy to another game. Complete store validation,
testing-track/TestFlight installation, and physical-device checks before calling
the build store-ready. Missing access to these gates does not block ordinary
implementation, CI, or unsigned packaging work.

## Authoritative sources

Sources were accessed on 2026-09-09; recheck time-sensitive store policies before
submission.

[1]: https://developer.android.com/google/play/requirements/target-sdk
[2]: https://developer.apple.com/news/upcoming-requirements/
[3]: https://developer.android.com/privacy-and-security/local-network-permission
[4]: https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy
[5]: https://developer.android.com/guide/practices/page-sizes
[6]: https://developer.android.com/studio/publish/app-signing
[7]: https://developer.apple.com/documentation/bundleresources/describing-data-use-in-privacy-manifests
[8]: https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api
[9]: https://developer.apple.com/documentation/uikit/managing-your-app-s-life-cycle
[10]: https://developer.android.com/develop/ui/compose/accessibility/api-defaults
[11]: https://developer.apple.com/design/human-interface-guidelines/accessibility
