# Release qualification

Review date: **2026-09-09**. This records executed evidence and remaining
acceptance work for PartyDeck's first release. Source inspection, JVM rendering,
mobile runtime tests, physical-network tests, and distribution signing are
recorded separately.

## Current decision

**Not yet qualified for public distribution.** Local Android/JVM validation and
the final Android package audit passed at source commit
**`c73a659221f94a5ba7eeafa38a4b7a0754a54265`**. The same commit passed native
iOS TLS/UI tests and an optimized device build. Repeated Android CI found one
transport-test failure, a preinstall emulator ANR, and a text-entry automation
failure after several optimized-app flows passed. Follow-up execution and
inspection of the iOS bundle remain open; its artifact upload failed.
Physical-device multiplayer, accessibility/performance measurements, production
signing, and store validation remain open.

| Gate | Evidence required | Current evidence |
| --- | --- | --- |
| Common game/session correctness | Domain, serialization, authority, replay, projection, and reconnect tests | 117 local tests passed; repeated CI ran 117 with one transport shutdown assertion failing. See [game-review.md](game-review.md) for independent behavioral review |
| Android application | Actual launcher, optimized APK/AAB, lint, launch and critical navigation | Local build/lint and package audit passed; CI debug failed before install and optimized smoke failed after successful practice/host/settings subflows |
| iOS application | Actual SwiftUI/UIKit app builds for device and simulator and executes XCTest | Shared-native gate, 3 native TLS tests, 2 UI tests, and optimized unsigned device build passed at `c73a659`; artifact upload failed, so bundle audit remains open |
| LAN integration | Real transport tests and two-to-six-device mixed Android/iOS sessions | JVM socket/session integration and Java–Swift native TLS in both directions passed; physical Android/iOS LAN sessions pending |
| Lifecycle | Client recovery, host loss, background/foreground, process termination, clean teardown | Controller/callback tests and Android emulator practice concealment on return passed; physical suspension/process-death checks pending |
| Accessibility and presentation | Independent visual review, TalkBack/VoiceOver, large text, insets, reduced motion | Shared visual review passed: 7 gameplay, 10 shell and 4 Home tests. Android captures show no material product defect; soft keyboard, spoken traversal, and physical-device checks remain open |
| Release privacy/security | Final data-flow/dependency audit, packaged manifests, transport protection | Source fixes, Android packages, and all 64 notice entries independently reviewed. iOS bundle/native-network audit pending; see [privacy.md](privacy.md), [security-review.md](security-review.md), and [dependency-licenses.md](dependency-licenses.md) |
| Signing and distribution | Owner-controlled signing identities, signed packages, store validation and metadata | External credentials/store access required |

The following **local** artifacts were frozen and independently inspected at
that commit. CI rebuilds have their own hashes and runtime evidence.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Debug APK, Android Debug identity | 22,819,660 | `9b9224ef89f711f78bcd3763e87a61f87078ab8306f90ce218e1845466d950f2` |
| Optimized unsigned APK | 4,522,956 | `f3d619df91a5e7d384745533415c6e34693c05f4fe6be7467d4aaafa9da6c4e5` |
| Optimized unsigned AAB | 7,655,558 | `fd74a9958b9aa295dc0237b0d7dcb4632b7f2b91cec1e92389c1ad4718e44618` |

Frozen artifacts, command results, manifests, R8 reports, and inspection records
are in `/tmp/partydeck-release-qa/final-c73a659/`. Temporary local evidence is
not a public release or a store-delivered package.

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

## Executed evidence

### Local tests and shared presentation

The coordinator's complete local `scripts/validate-android.sh` invocation
passed at **`c73a659`**, including Android lint and all three package tasks.
The release reviewer independently parsed the frozen **117** test reports:
core 14, session 27, transport 18, games 7, Compose app 47, and Android QR
decoder 4; zero failures, errors, or skips. The invocation reused Gradle's
up-to-date results for unchanged suites and reran the complete Compose suite,
including the new permission regression. It completed in 31 seconds.

The complete XML set, command log, and module totals were frozen in
`/tmp/partydeck-c73a659-local-validation/`. The independent parse/hashes are in
`/tmp/partydeck-release-qa/final-c73a659/independent-test-report-review.json`.
This supersedes the earlier 116-test milestone and intervening focused runs.

The independent [design review](design-review.md) closed the observed shared-UI
findings. Its final gameplay set has 7 passing tests covering phone, 200% text,
short landscape, tablet, spectator, concealment, actions, and result/history
presentation. Shell and Home sets passed 10 and 4 tests respectively. The large
license document reached its final text at **320 dp / 200%** in **222 bounded
text sections**, with Done still reachable. These are executed Compose/JVM
layout and semantics results; native spoken traversal and device rendering
remain separate gates.

### Mobile CI

[Run 34384326819](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34384326819)
tests `c73a659`. Its first Android attempt failed during `apt-get update` with
a Google Chrome repository **Hash Sum mismatch**, before Gradle or emulator
work. The reviewer read the retained job log; no app/runtime result is inferred.

**Android attempt 2 failed.** The reviewer independently parsed its uploaded
XML: **117 tests, 1 failure, 0 errors, 0 skips**. The failure is
`JavaTlsTransportTest.completePinProtectsOrderedMaximumSizeFramesAndPeerClosure`:
after `host.close()`, line 55 expected a `SocketException` from raw TCP connect,
but connect completed. The transport owner is investigating; the earlier local
117-test pass remains valid historical evidence, not a green CI result.

Both emulator variants exited **1**, on an accelerated API 36 AVD at
1080 × 2400 / density 420:

- **Debug:** a captured **System UI isn't responding** dialog failed readiness
  before APK installation; no application steps executed.
- **Optimized, disposable test signature:** cold launch passed with
  **`Status: ok` / 2,752 ms**. Home/rules, settings persistence across process
  restart, reveal/select/hide, background-return concealment and selection
  clearing, one-card play/leave, real native hosting, invitation QR/Copy/Share
  cancellation, teardown, and normal-size invalid-invitation editing passed.
  The run reached 200% Home/rules/settings/invalid Join, then failed replacement
  text entry. The actual editable field contained
  `not-an-invitedited-invitationtion` instead of `edited-invitation`.

The executed optimized APK SHA-256 is
`2c4adc0151dbcc2330507d3761eebc4732a699037557a0db0a73ed8fc615efb9`;
its CI unsigned input is
`7324d29cca91e405c34f619acb57feaefbb293f6a67ba6b1ebf16672edbb459b`.
The signing record explicitly says `distributionSigned: false`. These hashes
differ from the separately audited local packages above.

Independent image/tree review confirmed five revealed cards with one selected,
zero private-card nodes while concealed or after returning from background,
and four cards after the accepted play. The inspected captures contain no
invitation URI. Design review found no material product defect in these images.
No screenshot shows a soft keyboard, and the large-text final-rules capture
shows only a clipped slice of the last step; neither is complete coverage of
those conditions. The run did not reach large-text hand acceptance.

The corrected text-entry helper was independently replayed against the actual
failed XML with Select All ignored and the cursor at the start, middle, and end.
It requires an empty focused EditText before typing and exact final editable
text. This validates the helper correction; mobile execution remains required.
The next wrapper separates empty-AVD preparation from app acceptance. Its
single reboot is restricted to the observed System UI boot ANR with retained
tree/log evidence, verified app absence, a changed kernel boot ID, and restored
settings. Eleven independent injected boundary cases passed; installed-app
failures, other errors, and a second preparation failure stop validation.
Neither APK acceptance run is retried.
Reports/captures are under `/tmp/partydeck-c73a659-android-report/`; independent
test and capture reviews are in `/tmp/partydeck-release-qa/final-c73a659/`.

**iOS attempt 1:** the reviewer independently read
`/tmp/partydeck-c73a659-ios-job.log`:

- The complete shared-native test/framework gate passed in **13m 22s**, with
  all 92 tasks executed. Its expected 82-test count cannot yet be independently
  confirmed because the XML artifacts were not uploaded; do not report that
  expected count as a parsed result.
- **Three native XCTest tests passed**, with zero failures: ordered pinned-TLS
  frames and connection cleanup; wrong-pin rejection before a client connection
  is announced; and **Java–Swift TLS in both host directions**, including exact
  65,536-byte and 20,000-byte payloads and peer shutdown. These use the real
  native driver and an external JVM peer on simulator/host loopback. They do
  not establish physical Android/iPhone Wi-Fi behavior.
- **Two UI XCTest tests passed**, with zero failures: Home→Practice rendering
  and Settings→Home navigation. `TEST SUCCEEDED` is recorded at **18:09:20 UTC**.
  These tests do not cover native hand actions, host/join UI, large text, or
  background concealment. A test-only expansion is staged for the next run.
- The optimized device invocation executed
  `:composeApp:linkReleaseFrameworkIosArm64`, then built the actual
  **Release-iphoneos/PartyDeck.app** with `CODE_SIGNING_ALLOWED=NO`.
  `BUILD SUCCEEDED` is recorded at **18:38:30 UTC**. This is successful device
  compile/link evidence, not installation or distribution signing.
- The upload step then failed at **CreateArtifact / `ENOTFOUND`**. Independent
  artifact-list queries returned no artifacts. Consequently screenshots,
  XCTest bundles, packaged Info/privacy/resources, and link maps from this run
  cannot yet be independently inspected. The overall failed job does not erase
  the recorded test/build passes or supply the missing package audit.

Earlier Android runs also encountered emulator ANRs, including accelerated
[run 34378549932](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34378549932)
and a local software emulator without KVM. Their partial launch/rendering
evidence contributes no clean runtime pass. Earlier bootstrap/transitional
artifact hashes are superseded for final qualification.

### Android package and signing review

The three final local artifacts listed above passed **12 independent tool
checks** using Android Build Tools 36.0.0, `readelf`, `jarsigner`, and the
hash-verified official bundletool 1.18.3:

- Packaged manifests contain `dev.partydeck.app`, version **1.0.0 / 1**, SDK
  **26 / 36**, optional camera hardware, disabled backup and cleartext traffic,
  and the actual launcher. Optimized packages are not debuggable. Only Internet,
  Camera, and AndroidX's app-owned signature permission remain. Startup metadata
  contains lifecycle/profile initialization; the unused network-state permission
  and EmojiCompat downloadable-font initializer are absent.
- The scanner, camera metadata service, and resource/startup providers are not
  exported. The launcher is the only unprotected exported component;
  ProfileInstaller's receiver requires `android.permission.DUMP`. Adaptive
  launcher resources, including the API 33 monochrome layer, are present in
  debug and optimized APKs.
- Debug APK Signature Scheme v2 verifies as **Android Debug**. The optimized
  APK and AAB are **unsigned**; they contain no signing entries. Bundle validation
  passes. Both APKs pass `zipalign -c -P 16 -v 4`, and the bundle declares
  `PAGE_ALIGNMENT_16K` with uncompressed native-library support.
- All **12 native libraries** across four ABIs are byte-identical between the
  three packages. Every ELF LOAD segment has **`0x4000` alignment**. The libraries
  are AndroidX path and CameraX image/surface utilities. This is binary inspection;
  an executed 16 KB Android device/image remains a separate check.
- All **75** inspected font/audio/license resources match source bytes in each
  package: four fonts, six WAVs, and 65 license files, including the final complete
  aggregate. No key-container files or named test-fixture classes were found in
  the package-entry/DEX inspection.

Lint reports **0 errors and 5 warnings**. Its Bouncy Castle trust-all warning is
in the unused EST helper: final R8 usage lists the complete
`JcaJceUtils`, `$1`, and `$2` classes as removed, and none appears in the mapping.
The warning was not blanket-suppressed. The other warnings concern the deliberate
target-SDK choice, an API 33 attribute, a redundant versioned icon folder, and the
older icon fallback; the actual API 33 monochrome resource was independently
verified in both APKs. Review records include `package-review.json`,
`launcher-icon-review.json`, and `packaged-fixture-and-native-review.json`.

The reviewer also executed `prepare-android-runtime-apk.sh` on a preceding
optimized integration artifact.
Its six acceptance/rejection cases passed: valid temporary signing, existing
signature, production-signing environment, identical paths, symlinks, and hard
links. Every original ZIP entry and the unsigned input hash were preserved.
The helper creates a short-lived private key outside the artifact tree and
deletes it on exit. Resulting APKs are explicitly **test signed, not distribution
signed**. Exact hashes and checks are recorded in
`/tmp/partydeck-release-qa/runtime-signing-review/independent-review.json`.

### Assets and dependency notices

The final aggregate is **258,067 bytes**, SHA-256
`d5c47822bd82a0f2b775b1f8c76863a4e5d5de7fbe6ca1aa1ad2713794a32066`.
The reviewer independently verified all **64 notice entries** against source
hashes, resource bytes, complete aggregate text, and titles. The runtime set has
56 entries; duplicate exact texts are retained where components require them.
All **279 cached dependency artifacts** also matched the recorded binary
inventory. Audit records are in `/tmp/partydeck-release-qa/`, including
`all-notices-source-review-final.json` and `dependency-binary-hash-review.json`.

The actual Xcode `Package.resolved` from run 34378549932 locks Swift Certificates
**1.20.0**, Swift Crypto **4.5.2**, and Swift ASN.1 **1.7.2**. The license owner
verified its commits and license/notice objects against the audit; see
[dependency licenses](dependency-licenses.md). Final iOS linker coverage and
iOS packaged notice inclusion remain required.

All four font binaries independently matched their pinned upstream files.
All six original WAVs passed format and signal checks: 44.1 kHz mono 16-bit PCM,
0.07–1.28 seconds, zero-valued endpoints, no clipped samples, and 285,150 bytes
combined. Android resource inclusion passed; actual mobile listening and iOS
resource inclusion remain separate.

Source review also verified local-only QR decoding, scanner cleanup, preference
contents, interaction/background distinction, and the iOS inactive-scene cover's
hidden accessibility tree. Runtime permission, native privacy, and teardown
checks remain in the following acceptance scenarios.

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
The dependency audit also found Adobe DNG SDK objects in the selected Skiko iOS
KLIB. Its [license](../assets/licenses/runtime/skia_dng_sdk_LICENSE) permits
redistribution but includes a commercial-product indemnification clause (§5);
its [patent license](../assets/licenses/runtime/skia_dng_sdk_PATENTS) requires
the stated DNG acknowledgement. The release reviewer independently read those
terms. Final link coverage remains unverified, so the notices are included
conservatively and the publisher must assess the commercial terms before
distribution. Adding a notice alone does not resolve that separate obligation.

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
