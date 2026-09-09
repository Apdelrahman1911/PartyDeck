# Validation and release commands

Use the checked-in Gradle wrapper with JDK 21. The Android SDK must contain
`platforms;android-37.1`, `build-tools;36.0.0`, and `platform-tools`. Set the normal
`ANDROID_HOME` or an untracked `local.properties` SDK path for local builds.
The application targets API 36 and supports API 26 onward; compile SDK 37.1 is
required by the selected Compose/lifecycle artifacts.

## Android and common behavior

```sh
./scripts/validate-android.sh
```

On Linux without a display, install Xvfb and the graphics libraries listed in
[the workflow](../.github/workflows/validate.yml), then run:

```sh
xvfb-run -a ./scripts/validate-android.sh
```

The script runs the shared JVM behavior/UI suites, Android local unit tests
where present, Android lint, a debug APK, and an optimized release AAB. A task
with `NO-SOURCE` is not test evidence. Reports live under each module's
`build/reports` and `build/test-results`; Android packages live under
`androidApp/build/outputs`. Debug APKs use debug signing. The release AAB is
unsigned unless the complete signing environment below is supplied.

For focused work, run the affected module's `jvmTest` task instead of the full
script. Use the complete script at integration and release checkpoints.

The full workflow also installs the real debug APK into an API 36 emulator and
checks Home → Settings → Home → Practice → leave confirmation → Home. It locates
controls by their accessibility resource IDs and derives taps from actual node
bounds, rather than assuming screen coordinates. Each screen must expose its
expected marker before a screenshot is captured. UI XML, screenshots, launch
output, logcat, and a JSON result are retained under `build/ci/android`, including
failure diagnostics.

To run that separate smoke on Linux with usable KVM:

```sh
sdkmanager 'emulator' 'system-images;android-36;default;x86_64'
./scripts/smoke-android-emulator.sh
```

It requires accessible `/dev/kvm` and passes `-accel on`; it does not silently
fall back to slow software CPU emulation. The emulator uses an isolated AVD under
`build/ci/android/avd`, resets the test app's data, and is stopped on exit. The
default serial is `emulator-5554`; choose another unused even port with
`PARTYDECK_EMULATOR_PORT`. Boot has a 180-second deadline, UI states have
45-second deadlines, ADB commands are bounded, and the CI step has a 12-minute
limit. This is a single-device application smoke, not LAN interoperability proof.

## iOS on macOS or GitHub Actions

The workflow uses the ARM64 `macos-26` image and explicitly selects Xcode 26.4.1.
To run the same validation on a compatible Mac:

```sh
export DEVELOPER_DIR=/Applications/Xcode_26.4.1.app/Contents/Developer
./scripts/validate-ios-shared.sh
./scripts/validate-ios-app.sh
```

The shared script runs the common suites on `iosSimulatorArm64` and links the
device framework. The app script chooses an installed iPhone runtime matching
the selected Xcode's simulator SDK, builds the actual SwiftUI/Compose application,
and runs `PartyDeckUITests`. It also compiles the actual Swift app for a generic
iOS device with signing disabled, covering device-only scanner/bridge code. It
preserves Xcode's error status through log piping.
The Xcode project drives `:composeApp:embedAndSignAppleFrameworkForXcode`; do not
invoke that task from a generic shell without its Xcode environment.

The simulator result, logs, runtime/device metadata, XCTest screenshot attachments and app tarballs
are retained under `build/ci/ios` and uploaded by CI. Move or remove a prior
`PartyDeck.xcresult` before repeating an app test. The app tarball preserves
executable permissions; it is a simulator artifact, not a device or App Store
package. The separate device `.app` is unsigned. Neither artifact qualifies local-network privacy prompts or
physical Android/iOS interoperability.

Linux contributors can run the **Validate** workflow from GitHub Actions or
`gh workflow run validate.yml`. A successful framework link alone does not count
as an application smoke test; inspect the native suites and XCTest result too.

For a smaller native toolchain/rules/protocol check, manually dispatch
`gh workflow run toolchain-smoke.yml`. This runs only the `:core` and `:session`
Apple simulator tests. Both workflows pass the selected simulator UDID explicitly
to every native test task, so an unrelated newer installed runtime is not chosen.

## Android release signing

The application Gradle configuration consumes all four variables together:

| Variable | Value |
| --- | --- |
| `PARTYDECK_KEYSTORE_PATH` | Path to the publisher's private upload keystore |
| `PARTYDECK_KEYSTORE_PASSWORD` | Keystore password |
| `PARTYDECK_KEY_ALIAS` | Upload key alias |
| `PARTYDECK_KEY_PASSWORD` | Upload key password |

Set these through a local secure environment or protected GitHub environment
secrets, then run `./gradlew :androidApp:bundleRelease`. An incomplete set fails
configuration. When none are present, the build deliberately produces an
unsigned release artifact. Never commit a keystore or passwords, generate a new
publisher identity during validation, or replace release signing with a debug
key. The Validate workflow supplies no signing secrets and performs no upload
to an app store.

## iOS release signing

Distribution needs the publisher's Apple team, registered bundle identifier,
matching provisioning profile, distribution certificate/private key, and Xcode
export configuration. The current simulator workflow uses
`CODE_SIGNING_ALLOWED=NO` and does not create a distributable IPA.

For a future protected signing workflow, GitHub's documented secret contract is
`BUILD_CERTIFICATE_BASE64` (the `.p12`), `P12_PASSWORD`,
`BUILD_PROVISION_PROFILE_BASE64`, and `KEYCHAIN_PASSWORD` for a temporary
keychain. Import into a runner-temporary keychain, use the matching team/profile
for archive/export, and clean the keychain/profile in an always-running step.
These are documented inputs, not a configured distribution workflow. Do not
store signing files in `build/ci`, which is an uploaded artifact directory.

Authoritative sources and verified action pins are in
[engine-ci research](../docs/research/engine-ci.md); device/store qualification
is tracked in [release qualification](../docs/release-qualification.md).
