# PartyDeck for iOS

Open `PartyDeck.xcodeproj` and select the shared **PartyDeck** scheme. Use Xcode **26.4.1**, JDK **21**, and the repository's Gradle/Android SDK setup. The app supports iPhone and iPad on **iOS 15+**. Kotlin device and simulator targets are arm64; Intel simulators are not configured.

Xcode's first build uses the committed SwiftPM lock to resolve Swift Certificates **1.20.0** and its dependencies, then invokes `:composeApp:embedAndSignAppleFrameworkForXcode`. That task builds the static **PartyDeckKit** framework and packages Compose resources. A Run Script phase runs before Swift compilation; user script sandboxing is disabled as required by JetBrains' direct integration. Kotlin integration does not use CocoaPods.

For a simulator build from the repository root:

```sh
export DEVELOPER_DIR=/Applications/Xcode_26.4.1.app/Contents/Developer
xcodebuild -project iosApp/PartyDeck.xcodeproj -scheme PartyDeck \
  -configuration Debug -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO build
```

Run `scripts/validate-ios-app.sh` on macOS for a **Debug Simulator** build and the native transport and shared UI tests. The script discovers an available iPhone simulator and saves the `.xcresult`, screenshots, logs, link maps, and `PartyDeck-simulator.app.tar.gz` under `build/ci/ios`.

The three `PartyDeckTests` cases exercise the real Swift TLS adapter: pinned connections with ordered framed data and close callbacks, wrong-pin rejection, and Java/Swift interoperability. A Java fixture runs on the Mac while the simulator verifies both Swift-host and Java-host connections, exact certificate pins, and framed payloads up to 64 KiB. The validation script requires both XCTest success and the Java fixture's completion result. Running the scheme directly without that fixture skips only the mixed Java/Swift test.

The three `PartyDeckUITests` flows use the actual Compose accessibility tree:

- Practice: reveal a hand, select a card, hide it and clear the selection, reveal and play, then confirm leaving. Concealed hands must expose no private card accessibility elements.
- Native hosting: enter a host name, create a table, open its invitation, check the QR and invitation controls, close the dialog, then confirm leaving.
- Settings: open the shared settings screen, check its controls, and return home.

Explicit screenshots cover home, settings, practice states, and the host lobby before and after closing its invitation. The capture helper skips an open invitation dialog.

Run `scripts/validate-ios-device.sh` separately on macOS to build an unsigned arm64 device app with Xcode's **Release** configuration. This selects the optimized Kotlin/Native release framework and Swift release settings. The script checks that the build reports `:composeApp:linkReleaseFrameworkIosArm64` and saves `xcodebuild-device.log`, a link map, and `PartyDeck-device-unsigned.app.tar.gz` under `build/ci/ios`. These artifacts support packaging review; signing and device execution are separate steps.

For a physical device or archive, copy `Configuration/Signing.xcconfig.example` to `Configuration/Signing.xcconfig`, enter your Apple team, and choose a bundle identifier registered to that team. The local file is ignored by Git. Automatic signing remains enabled; CI disables signing only for its verification artifacts. Use Xcode's Archive and Validate App flows with your distribution identity before TestFlight or App Store submission.

The SwiftUI scene retains one `IosAppHandle`. Inactive scenes cover the UI, hide the underlying accessibility tree, quiet feedback, and pause camera capture. The separate background signal handles network lifetime without treating a permission alert as a departed app. System Reduce Motion changes are observed and combined with the saved in-app setting.

Native preferences contain only display name and feedback/motion settings. Private cards and resume credentials remain in memory. The pasteboard keeps copied invitations local to this device and removes them after two minutes. The share sheet opens only on a user action. QR scanning uses AVFoundation metadata entirely on-device, asks for camera access only after Scan, and fills the Join form for confirmation.

`PrivacyInfo.xcprivacy` declares app-private defaults, app-container file metadata, and timing used by the shared renderer. Audit the final archive and dependency manifests before submission; this source manifest does not replace that check. Local multiplayer declares only `_partydeck._tcp` and a local-network usage explanation. It does not require Apple's restricted multicast entitlement or an unrestricted ATS exception.

Simulator tests do not exercise Apple's Local Network privacy prompt. Physical iPhone↔Android and iPhone↔iPhone tests must cover allow/deny/re-enable, host loss, background/resume, camera denial/interruption, VoiceOver privacy, large text, haptics, silent mode, and performance. Store accounts, distribution signing, and those device checks remain release qualification steps. See [the release qualification record](../docs/release-qualification.md) and [the verified iOS sources](../docs/research/ios.md).
