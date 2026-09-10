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

On Ubuntu 24.04 without a display, `./scripts/setup-ubuntu-graphics.sh` verifies
Xvfb and the required graphics libraries, installing missing packages from the
configured Ubuntu sources. It skips APT network access when they are present.
Then run:

```sh
xvfb-run -a ./scripts/validate-android.sh
```

The script runs the shared JVM behavior/UI suites, Android local unit tests
where present, Android lint, a debug APK, and optimized release APK/AAB. A task
with `NO-SOURCE` is not test evidence. Reports live under each module's
`build/reports` and `build/test-results`; Android packages live under
`androidApp/build/outputs`. Debug APKs use debug signing. The release AAB is
unsigned unless the complete signing environment below is supplied, as is the
original release APK.

It first runs `prepare-godot-renderer.sh`, which verifies or exports the real
renderer PCK and its source receipt. Linux x86_64 can install the checksum-pinned
Godot tool automatically; another host must set `PARTYDECK_GODOT_EXECUTABLE` to
its official Godot 4.7.2 executable. Bridge and shared native-runtime tests are
included. Packaging verifies the pack again and includes the same original
notices as the comparison host.

For focused work, run the affected module's `jvmTest` task instead of the full
script. Use the complete script at integration and release checkpoints.

The full workflow runs the same native UI smoke against debug and an optimized
APK, sequentially on one standard API 35 emulator boot by default. It checks rules, persisted settings,
practice hand actions and privacy after backgrounding, host/invite/leave, invalid
join recovery, and large-text reachability. Controls are found through actual
accessibility nodes and their bounds. Each captured screen must expose its expected
marker. Crash/ANR dialogs fail explicitly; launcher readiness is checked before
opening the app. Native screenshots, redacted XML/logcat, launch output and JSON
results are retained under `build/ci/android/debug` and
`build/ci/android/optimized-test-signed`, including failure diagnostics.

Before installing either APK, `prepare-android-emulator.py` checks the empty AVD
with the same strict launcher assertions. An observed first-boot System UI ANR
may trigger one clean reboot, only after preserving its failing XML and full
diagnostics and confirming PartyDeck is absent. The kernel boot ID must change,
boot must finish, and launcher checks must pass again. Other preparation errors
stop the run. Preparation evidence is retained under `build/ci/android/preparation`;
each app variant runs once on the resulting boot and rejects every crash/ANR.

`prepare-android-runtime-apk.sh` signs a **separate copy** of the unsigned optimized
APK with a newly generated two-day CI test key. It rejects production signing
variables and already signed input, verifies the APK signature and 16 KiB ZIP
alignment, records both APK hashes and the public certificate fingerprint, and
deletes its temporary keystore. The original unsigned APK and AAB remain separate.
The copy is named `PartyDeck-release-ci-test-signed.apk` and is for runtime tests;
it has no publisher identity. The debug app is uninstalled before switching keys.

To run that separate smoke on Linux with usable KVM:

```sh
sdkmanager 'emulator' 'system-images;android-35;default;x86_64'
./scripts/smoke-android-emulator.sh
```

The manual Validate workflow also has `android_godot_session`, defaulting to
false. Root enables this check after qualifying the real native prerequisites
and enabling the production presentation choices in source. The option only
requests checks; it cannot enable a renderer or bypass a missing picker.
The equivalent local invocation sets `PARTYDECK_ANDROID_GODOT_SESSION_SMOKE=1`
and `PARTYDECK_SOURCE_REVISION` to the full commit used to build the APKs.
That revision is caller provenance, not an embedded binary attestation.

The optional check reuses both APKs and the same prepared emulator boot. It
verifies each packaged PCK against the source-checked export, ties the optimized
copy to its disposable-signing receipt, and runs
`smoke-android-godot-session.py` through the real presentation picker for both
2D and 3D at normal text scale 1.0. The checker compares the installed base APK
bytes with the supplied APK. Each variant has a ten-minute command limit. Debug requests the renderer
death case and preserves unsupported exit 2 as a failure; the non-debuggable
optimized APK explicitly uses `--skip-renderer-death`. Its omitted death case
is recorded separately and cannot qualify optimized renderer-death handling.

Original screenshots, XML, input geometry, process observations, package hashes,
command logs and results are retained below `build/ci/android/godot-session`
by the report upload, including malformed screenshot bytes for failure review.
The pulled `installed-base.apk` remains in the runner directory; its matching
input APK is retained by the existing package upload, while the report retains
the pull log and both hashes. The checker writes to a fresh `runtime`
subdirectory within each variant and refuses to overwrite previous evidence.
`runtime-variants.json` includes both optional
phase statuses, and any requested failure fails the workflow. Native chrome
and Ready establish session lifecycle behavior only; rendered gameplay and
pixel privacy remain separate review requirements.

Set `PARTYDECK_ANDROID_API=36` and install
`system-images;android-36;default;x86_64` to select Android 16 instead. Both the
wrapper and CI restrict the image choice to API 35 or 36. The installed image
metadata and actual guest API are recorded, and the actual API must match the
requested value before either APK installs.

Verified API 36 baseline (2026-09-10): [run 34457458638](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34457458638)
at `f11f92ed4ec4f91630396bf493ba2fd984f07bb9` passed first-boot preparation
with PartyDeck absent and no reboot, then both debug and disposable-test-signed
optimized app flows at standard and 200% text, including real soft-keyboard
checks. The public `ubuntu-24.04` runner supplied **four CPUs**, **15,989 MiB RAM**,
usable KVM, and runner image `20260831.293.1`. It ran the full official API 36
image above, revision **2**, with actual guest API **36** and the
`swangle`/720 × 1600/280 dpi configuration below.

The earlier two-CPU System UI preparation failures remain historical; the latest
failure used this same runner image version. This pass establishes the API 36
baseline for the ordinary app flows at that revision.
`android_godot_session=false`, so native Godot presentation, session, and lifecycle
qualification remain separate. Physical devices, mixed-device LAN, camera frames,
distribution signing, and store acceptance are outside this run. See the
[detailed toolchain evidence](../docs/research/toolchain.md#android-preparation-and-jvm-close-test-review).

It requires accessible `/dev/kvm` and passes `-accel on`; it does not silently
fall back to slow software CPU emulation. Graphics use the supported `swangle`
mode (ANGLE GLES with SwiftShader). The Pixel 7 logical viewport is preserved
with a 720 × 1600 framebuffer at 280 dpi to reduce software rendering load.
The wrapper sets both numeric skin keys and the three LCD keys before boot,
then requires actual `wm size` and `wm density` to match before installing either
APK. Expected and actual values are retained in `display-configuration.json`.
The emulator uses an isolated AVD under
`build/ci/android/avd`, resets the test app's data, and is stopped on exit. The
default serial is `emulator-5554`; choose another unused even port with
`PARTYDECK_EMULATOR_PORT`. Boot has a 180-second deadline, UI states have
45-second deadlines, ADB commands are bounded, and the CI step has a 30-minute
limit. This is a single-device application smoke, not LAN interoperability proof.

## iOS on macOS or GitHub Actions

The workflow uses the ARM64 `macos-26` image and explicitly selects Xcode 26.4.1.
To run the same validation on a compatible Mac:

```sh
export DEVELOPER_DIR=/Applications/Xcode_26.4.1.app/Contents/Developer
./scripts/validate-ios-shared.sh
./scripts/validate-ios-app.sh
./scripts/validate-ios-device.sh
```

The shared script runs the common suites on `iosSimulatorArm64` and links the
device framework. The app script chooses an installed iPhone runtime matching
the selected Xcode's simulator SDK, builds the actual SwiftUI/Compose application,
and runs app-hosted `PartyDeckTests` plus `PartyDeckUITests`. A test-only JVM TLS
peer runs alongside XCTest, with its real port and certificate pin passed through
Xcode's documented `TEST_RUNNER_` environment forwarding. CI requires the named
Java–Swift interoperability test to pass, Java to exit successfully, and its result
to prove the complete exchanges in both directions. A skipped or missing fixture
cannot make this step pass. Manifest, process logs and results are retained in
`build/ci/ios/interop`. This checks native TLS interoperability over simulator
loopback; physical-device LAN behavior remains a separate gate.

After Debug XCTest passes, `validate-ios-device.sh` compiles the actual Swift/Kotlin app in
**Release** for a generic iOS device with signing disabled. This covers optimized
device-only scanner/bridge code and retains linker maps for symbol/license review.
The build must report `:composeApp:linkReleaseFrameworkIosArm64`. Both Xcode test
and device-build failure statuses are preserved.
The Xcode project drives `:composeApp:embedAndSignAppleFrameworkForXcode`; do not
invoke that task from a generic shell without its Xcode environment.

The simulator result, logs, runtime/device metadata, XCTest screenshot attachments and app tarballs
are retained under `build/ci/ios` and uploaded by CI. Move or remove a prior
`PartyDeck.xcresult` before repeating an app test. The app tarball preserves
executable permissions; it is a simulator artifact, not a device or App Store
package. The separate Release device `.app` is unsigned. Neither artifact qualifies local-network privacy prompts or
physical Android/iOS interoperability.

CI uploads shared native test reports before app compilation, then simulator/XCTest
evidence before starting the separate optimized device build. A long Release link
therefore cannot hide completed test results. The iOS job has a 90-minute ceiling;
simulator and device steps each have 40-minute limits, and the test supervisor's
Xcode command has its own 30-minute deadline.
Artifact uploads retry once after ten seconds for transient service failures;
if both attempts fail, the workflow fails and the missing evidence stays explicit.

Linux contributors can run the **Validate** workflow from GitHub Actions or
`gh workflow run validate.yml`. A successful framework link alone does not count
as an application smoke test; inspect the native suites and XCTest result too.

For a smaller native toolchain/rules/protocol check, manually dispatch
`gh workflow run toolchain-smoke.yml`. This runs only the `:core` and `:session`
Apple simulator tests. Both workflows pass the selected simulator UDID explicitly
to every native test task, so an unrelated newer installed runtime is not chosen.

The Validate workflow runs both platforms for normal pushes and pull requests.
Manual runs accept `platform=all` (default), `android`, or `ios`, for example:

```sh
gh workflow run validate.yml --ref main -f platform=android
```

The manual `android_api` choice defaults to `35`; add `-f android_api=36` for
the Android 16 application smoke.

Verify the resulting run's `headSha` against the intended commit. A platform-only
run records that platform's evidence; cite the separate unchanged-platform run
when reusing earlier qualification results.

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
publisher identity during validation, or replace production signing with a debug
key. The explicitly named CI test-signed APK described above is a separate copy.
The Validate workflow supplies no signing secrets and performs no upload
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
