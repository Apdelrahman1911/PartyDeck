# PartyDeck for iOS

Open `PartyDeck.xcodeproj` and select the shared **PartyDeck** scheme. Use an ARM64 Mac with Xcode **26.4.1**, JDK **21**, Python 3.11 or later with `venv`, Git, and the repository's Gradle/Android SDK setup. The app supports iPhone and iPad on **iOS 15+**. Kotlin device and simulator targets are arm64; Intel simulators are not configured.

Xcode's first build uses the committed SwiftPM lock to resolve Swift Certificates **1.20.0** and its dependencies, then invokes `:composeApp:embedAndSignAppleFrameworkForXcode`. That task builds the static **PartyDeckKit** framework and packages Compose resources. A Run Script phase runs before Swift compilation; user script sandboxing is disabled as required by JetBrains' direct integration. Kotlin integration does not use CocoaPods.

The app also requires a renderer PCK exported from the current sources and the matching native Godot engine and camera archives. On macOS, set `PARTYDECK_GODOT_EXECUTABLE` to your verified official **Godot 4.7.2** executable before exporting; the automatic tool installer supports Linux x86_64. A current PCK and its receipt from the same source revision can also be reused. For a simulator build from the repository root, prepare these inputs before invoking Xcode:

```sh
export DEVELOPER_DIR=/Applications/Xcode_26.4.1.app/Contents/Developer
./scripts/prepare-godot-renderer.sh
bash godot/ios-host/build-probe.sh engine simulator-debug
xcodebuild -project iosApp/PartyDeck.xcodeproj -scheme PartyDeck \
  -configuration Debug -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO build
```

The native helper fetches the pinned upstream source, applies the repository patches, installs the pinned SCons dependency in its own virtual environment, and records archive/source receipts under `godot/ios-host/build`. Xcode's Prepare Godot inputs phase verifies the PCK, native source hashes, archive hashes, architecture, SDK and configuration before staging them. Supported pairs are **Debug/iphonesimulator** and **Release/iphoneos**. For device or archive builds, first run `bash godot/ios-host/build-probe.sh engine device-release`; those inputs live under `godot/ios-host/build/device-release`.

## Compare 2D and 3D

The default build above uses the shipping profile with **Standard table**,
**2D table** and **3D table** available in the same session. Standard table remains
the initial, accessible gameplay route. An explicit qualification app remains
available for separate comparison and validation. After preparing the PCK and
Simulator native inputs above, build that app from the repository root:

```sh
PARTYDECK_IOS_PREVIEW="$PWD/build/ios-godot-preview"
python3 -B scripts/prepare-ios-godot-activation.py --modes 2d,3d \
  --output-plist "$PARTYDECK_IOS_PREVIEW/activation/Info.plist" \
  --expectation "$PARTYDECK_IOS_PREVIEW/activation/expectation.json"
xcodebuild -project iosApp/PartyDeck.xcodeproj -scheme PartyDeck \
  -configuration Debug -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath "$PARTYDECK_IOS_PREVIEW/DerivedData" \
  "PARTYDECK_APP_INFO_PLIST=$PARTYDECK_IOS_PREVIEW/activation/Info.plist" \
  "PARTYDECK_GODOT_ACTIVATION_EXPECTATION=$PARTYDECK_IOS_PREVIEW/activation/expectation.json" \
  CODE_SIGNING_ALLOWED=NO build
```

Boot one compatible iPhone Simulator with the selected Xcode, then install and
launch the app. These commands use `booted` for that one running simulator:

```sh
xcrun simctl install booted "$PARTYDECK_IOS_PREVIEW/DerivedData/Build/Products/Debug-iphonesimulator/PartyDeck.app"
xcrun simctl launch booted dev.partydeck.app
```

Start Practice, open **Table style**, and choose **2D table** or **3D table**.
Use the native **Standard table** button to return to the same session before
trying the other style. These settings enable the comparison profile; they do
not grant native production acceptance. Standard table remains the accessible
gameplay route.

To reuse a CI Simulator build, select a Validate run requested with
`platform=ios` and `ios_godot_session=true`, and download its
`ios-reports-and-simulator-app` artifact. Replace `RUN_ID` with that run's ID:

```sh
gh run download RUN_ID --repo Apdelrahman1911/PartyDeck \
  --name ios-reports-and-simulator-app --dir partydeck-ios-preview
tar -xzf partydeck-ios-preview/build/ci/ios/godot-session/PartyDeck-session-simulator.app.tar.gz \
  -C partydeck-ios-preview
xcrun simctl install booted partydeck-ios-preview/PartyDeck.app
xcrun simctl launch booted dev.partydeck.app
```

For a focused `platform=ios-godot-production` run, use artifact name
`ios-focused-production-reports-and-simulator-app`; the session tarball path is
the same. The baseline `PartyDeck-simulator.app.tar.gz` contains the shipping
profile. Check the chosen run's source revision and test results: archives can
be retained after a failed test. Artifacts normally expire after fourteen days;
the local build above remains available. An unsigned device archive needs the
device build and signing steps below and cannot replace the Simulator app.

## Automated validation

After PCK preparation, run `scripts/validate-ios-app.sh` on macOS for the baseline **Debug Simulator** build and native transport/shared UI tests. It builds the Simulator engine unless `PARTYDECK_IOS_SIMULATOR_GODOT_ENGINE_ROOT` names prepared inputs with matching receipts. The script discovers an available iPhone simulator, verifies the packaged resources and production link, and saves `PartyDeck.xcresult`, screenshots, logs, link maps, and `PartyDeck-simulator.app.tar.gz` under `build/ci/ios`.

The three `PartyDeckTests` cases exercise the real Swift TLS adapter: pinned connections with ordered framed data and close callbacks, wrong-pin rejection, and Java/Swift interoperability. A Java fixture runs on the Mac while the simulator verifies both Swift-host and Java-host connections, exact certificate pins, and framed payloads up to 64 KiB. The validation script requires both XCTest success and the Java fixture's completion result. Running the scheme directly without that fixture skips only the mixed Java/Swift test.

The three `PartyDeckUITests` flows use the actual Compose accessibility tree:

- Practice: reveal a hand, select a card, hide it and clear the selection, reveal and play, then confirm leaving. Concealed hands must expose no private card accessibility elements.
- Native hosting: enter a host name, create a table, open its invitation, check the QR and invitation controls, close the dialog, then confirm leaving.
- Settings: open the shared settings screen, check its controls, and return home.

Explicit screenshots cover home, settings, practice states, and the host lobby before and after closing its invitation. The capture helper skips an open invitation dialog.

Request the separate production Godot session qualification from GitHub Actions with:

```sh
gh workflow run validate.yml --ref main -f platform=ios -f ios_godot_session=true
```

`ios_godot_session` defaults to false. When requested, the workflow attempts the baseline Simulator suite, UIKit layout suite and production session suite independently after the shared native inputs succeed. `scripts/validate-ios-godot-session.sh` selects exactly `testProduction2DPracticeSession` and `testProduction3DPracticeSession` in `PartyDeckGodotSessionUITests`. These use the real practice controller and presentation picker, measured coordinates for Reveal/card/Hide/Play input on the native surface, Standard return, canceled and confirmed Leave, and re-entry with the retained native owner. The result checker requires both named cases to execute and pass, plus original screenshots and sanitized observation attachments.

The session wrapper generates a qualification `Info.plist` and expectation using `scripts/prepare-ios-godot-activation.py` with `--modes 2d,3d`. It supplies the app-only `PARTYDECK_APP_INFO_PLIST` override and `PARTYDECK_GODOT_ACTIVATION_EXPECTATION`; test bundles keep their own generated plists. It also sets `PARTYDECK_SESSION_QUALIFICATION_CONDITION=PARTYDECK_GODOT_SESSION_QUALIFICATION` for the app and UI-test Debug targets, preserving inherited `DEBUG`. The tests' `--partydeck-observe-godot-session` argument enables observation only; the generated bundled profile grants the requested modes subject to the native/pack checks. The checked-in shipping profile lists `2d` and `3d` in `PartyDeckQualifiedGodotPresentations`; observation remains confined to explicit qualification builds. The dedicated shipping picker smoke remains pending. A qualification request or successful package/link receipt does not by itself grant native production acceptance.

Session evidence uses a separate `build/ci/ios/godot-session` directory, including `activation/`, `PartyDeckGodotSessions.xcresult`, `attachments/`, `result.json`, the link receipt, and `PartyDeck-session-simulator.app.tar.gz`. CI includes it in `ios-reports-and-simulator-app`. Preserve the previous baseline `.xcresult` and the entire session evidence directory before rerunning. See [the validation commands](../scripts/README.md#ios-on-macos-or-github-actions) for local qualification and artifact details.

## Device builds and signing

Run `scripts/validate-ios-device.sh` separately on macOS to build an unsigned arm64 device app with Xcode's **Release** configuration. It requires the current PCK and builds the device engine unless `PARTYDECK_IOS_DEVICE_GODOT_ENGINE_ROOT` supplies matching prepared inputs. This selects the optimized Kotlin/Native release framework and Swift release settings. The script checks that the build reports `:composeApp:linkReleaseFrameworkIosArm64`, verifies the packaged resources and production link, and saves `xcodebuild-device.log`, a link map, and `PartyDeck-device-unsigned.app.tar.gz` under `build/ci/ios`. With `ios_godot_session=true`, CI also builds this unsigned device app with a generated qualification profile; it performs no device runtime test and enables no Debug observation code in Release. CI runs the device and Simulator jobs independently after one shared PCK export. Signing and device execution remain separate steps.

For a physical device or archive, prepare the Release/device native inputs above, copy `Configuration/Signing.xcconfig.example` to `Configuration/Signing.xcconfig`, enter your Apple team, and choose a bundle identifier registered to that team. The local file is ignored by Git. Automatic signing remains enabled; CI disables signing only for its verification artifacts. Use Xcode's Release configuration and Archive and Validate App flows with your distribution identity before TestFlight or App Store submission.

The SwiftUI scene retains one `IosAppHandle`. Inactive scenes cover the UI, hide the underlying accessibility tree, quiet feedback, and pause camera capture. The separate background signal handles network lifetime without treating a permission alert as a departed app. System Reduce Motion changes are observed and combined with the saved in-app setting.

Native preferences contain only display name and feedback/motion settings. Private cards and resume credentials remain in memory. The pasteboard keeps copied invitations local to this device and removes them after two minutes. The share sheet opens only on a user action. QR scanning uses AVFoundation metadata entirely on-device, asks for camera access only after Scan, and fills the Join form for confirmation.

`PrivacyInfo.xcprivacy` declares app-private defaults, app-container file metadata, and timing used by the shared renderer. Audit the final archive and dependency manifests before submission; this source manifest does not replace that check. Local multiplayer declares only `_partydeck._tcp` and a local-network usage explanation. It does not require Apple's restricted multicast entitlement or an unrestricted ATS exception.

Simulator tests do not exercise Apple's Local Network privacy prompt. Physical iPhone↔Android and iPhone↔iPhone tests must cover allow/deny/re-enable, host loss, background/resume, camera denial/interruption, VoiceOver privacy, large text, haptics, silent mode, and performance. Store accounts, distribution signing, and those device checks remain release qualification steps. See [the release qualification record](../docs/release-qualification.md) and [the verified iOS sources](../docs/research/ios.md).
