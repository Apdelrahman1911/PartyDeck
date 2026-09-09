# Release qualification

Review date: **2026-09-09**. This is the acceptance plan and evidence ledger for
PartyDeck's first release. A passing compile, a desktop screenshot, and a
simulator launch are different forms of evidence; none establishes physical
mobile multiplayer or store readiness by itself.

## Current decision

**Not qualified for public distribution.** Implementation and independent
verification are in progress. Replace pending entries with the exact commit,
command or workflow run, artifact, device/OS, result, and remaining limitation.
Do not mark an unexecuted check as passing.

| Gate | Evidence required | Current evidence |
| --- | --- | --- |
| Common game/session correctness | Independent domain, serialization, authority, replay, projection, and reconnect tests | Pending implementation milestone |
| Android application | Installable APK from the actual launcher; release AAB; lint; launch and critical navigation | Initial source scaffolding inspected; build and launch pending |
| iOS application | Actual SwiftUI/UIKit app links PartyDeckKit, builds for device and simulator, and launches in simulator | macOS workflow and app wrapper pending |
| LAN integration | Real transport tests and two-to-six-device mixed Android/iOS sessions | Pending; same-process simulation alone is insufficient |
| Lifecycle | Client recovery, host loss, background/foreground, process termination, clean session teardown | Pending |
| Accessibility and presentation | Independent visual review plus TalkBack/VoiceOver, large text, insets, and reduced motion | Pending |
| Release privacy/security | Final dependency/data-flow audit, manifests, transport protection, no secret leakage | Pending; see [privacy.md](privacy.md) and security review |
| Signing and distribution | Owner-controlled signing identities, signed packages, store validation and metadata | External credentials/store access required |

## Verified platform baseline

- The checked-in Android configuration initially selects application ID
  `dev.partydeck.app`, minimum SDK 26, and compile/target SDK 36. The merged
  **release** manifest must be inspected again after integration.
- Google Play requires new phone apps and updates to target **Android 16 / API
  36 or later from August 31, 2026**. This requirement was verified against the
  official page updated September 1, 2026. [1]
- Apple's upload requirement since **April 28, 2026** is **Xcode 26 or later
  using the iOS 26 SDK or later**. This is the build-SDK floor, not a requirement
  to exclude older supported iPhones. Record the selected Xcode and deployment
  target separately. [2]
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
