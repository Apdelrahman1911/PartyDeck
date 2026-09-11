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

The manual Validate input `android_godot_session=true` builds an explicit
qualification profile and then requests the production session checks:

```sh
gh workflow run validate.yml --ref main -f platform=android -f android_api=35 -f android_godot_session=true
```

The input sets `PARTYDECK_ANDROID_GODOT_SESSION_SMOKE=1` for
`validate-android.sh`, which passes `-PpartydeckGodotQualificationModes=2d,3d`
to Gradle before packaging and records `build/ci/android/godot-activation-build.json`.
The APKs contain the `qualification` profile and `2d,3d` mode metadata. Default
shipping builds retain empty native mode lists. Explicit qualification makes the
real picker choices available for testing; it does not grant shipping acceptance.

For the equivalent local flow, use the same source checkout for both calls and
set the flag during the build as well as during execution:

```sh
PARTYDECK_ANDROID_GODOT_SESSION_SMOKE=1 xvfb-run -a ./scripts/validate-android.sh
PARTYDECK_ANDROID_GODOT_SESSION_SMOKE=1 PARTYDECK_SOURCE_REVISION="$(git rev-parse HEAD)" ./scripts/smoke-android-emulator.sh
```

`PARTYDECK_SOURCE_REVISION` must identify the full commit used to build the APKs;
it is caller provenance, not an embedded binary attestation. The wrapper compares
the build expectation with the decoded APK profile/modes before each Godot check,
and rejects a shipping or mismatched package. Use `-f android_api=36` in Validate,
or `PARTYDECK_ANDROID_API=36` for the local wrapper, with the API 36 image described
below when that separate runtime target is intended.

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
Its process-list reads request `ps -A -n -w -o PID,UID,NAME`. Each read preserves
exact stdout/stderr bytes as `runtime/logs/process-table-<sequence>.stdout.log`
and `.stderr.log`, with a matching JSON receipt for argv, timestamps, stream
availability, hashes and the observed exit code, before decoding or parsing.
Timeouts retain available partial bytes without inventing an exit code. These
files are covered by the existing report upload. Header padding is tolerated;
unknown schemas, nonnumeric IDs and inconsistent process identities still fail.

`build/ci/android/runtime-variants.json` includes both ordinary and requested
Godot phase statuses; any requested failure fails the workflow. Inspect the
recorded assertions for session/process continuity. Native chrome and Ready alone
do not establish rendered gameplay or pixel privacy, which need separate review.

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
45-second deadlines, and ADB commands are bounded. The ordinary APK CI step has
a 30-minute limit; requesting the Godot session checks raises it to 55 minutes.
This is a single-device application smoke, not LAN interoperability proof.

### API 36 adaptive Godot execution

The separate [Android adaptive workflow](../.github/workflows/android-godot-adaptive.yml)
has no dispatch inputs:

```sh
gh workflow run android-godot-adaptive.yml --ref main
```

One producer prepares the source-checked renderer pack and builds debug and
optimized unsigned APKs with `-PpartydeckGodotQualificationModes=2d,3d` and
`:androidApp:recordGodotPresentationActivation`. It uses
`prepare-android-runtime-apk.sh` to create one optimized copy with a disposable
CI identity. `android_godot_adaptive_inputs.py record` checks the APK metadata,
PCK, signing receipts and pinned checker files, then records the bundle at
`build/ci/android/adaptive-inputs` and evidence at
`build/ci/android/adaptive-producer`.

Four consumers cover **debug / optimized-test-signed × 1.0 / 2.0 text**, each
running **both 2D and 3D** on a fresh API 36 AVD. They download the producer's
exact artifact ID and verify its manifest SHA-256, same-run/source context and
APK/PCK/checker inputs before starting the emulator. The workflow selects
`PARTYDECK_ANDROID_GODOT_ADAPTIVE_SMOKE=1`,
`PARTYDECK_ANDROID_GODOT_SESSION_SMOKE=0` and `PARTYDECK_ANDROID_API=36`, and
supplies the selected variant, font scale and producer identifiers. This branch
uses the already packaged qualification APKs and exits before the ordinary baseline
flows; it runs `smoke_android_godot_adaptive.py` with the accepted session checker.

The scenarios cover both landscape directions, a held touch on the native `Standard table`
control during return to portrait, re-entry, and observed split-screen
entry/exit. Actual configuration, paired-window geometry, process/task continuity
and input observations are required. Unsupported exit **2** remains a failed CI
job and unqualified evidence. Success is labeled `passed-automated-scope`;
original transition pixels still require privacy review. Back-key/card dragging,
changes while opening, half-turns and divider dragging are outside these scenarios.
API 35 adaptive behavior, engine gameplay, physical-device/LAN and store acceptance
remain separate.

Producer uploads are named `android-adaptive-inputs-<run>-<attempt>` and
`android-adaptive-build-<run>-<attempt>`. Each consumer uploads
`android-adaptive-api36-<variant>-font-<scale>-<run>-<attempt>` even after failure.
Under `build/ci/android`, retain `godot-adaptive/package-inputs`,
`godot-adaptive/runtime` (original videos, screenshots, XML, state/input logs and
`godot-adaptive-result.json`), `godot-adaptive/execution.json`,
`godot-adaptive/device-provenance.json`, `preparation`, and the wrapper/display
logs. `device-provenance.json` binds the installed SDK image files and observed
guest identity. These artifacts and status labels preserve the actual attempted
scope; they do not turn an unsupported or failed case into a pass.

## iOS on macOS or GitHub Actions

Use an ARM64 Mac with Xcode 26.4.1, JDK 21, Python 3.11 or later with `venv`, Git, and the
Android SDK listed above for KMP configuration. The native build helper fetches
the pinned Godot source and installs the hash-pinned SCons dependency in its own
virtual environment.

Export the renderer PCK before either app wrapper. On macOS, set
`PARTYDECK_GODOT_EXECUTABLE` to a verified official Godot 4.7.2 executable;
the automatic installer supports Linux x86_64. `prepare-godot-renderer.sh`
can also reuse the PCK and export receipt already present at the default path
when they match the current sources. From the repository root:

```sh
export DEVELOPER_DIR=/Applications/Xcode_26.4.1.app/Contents/Developer
./scripts/prepare-godot-renderer.sh
./scripts/validate-ios-shared.sh
./scripts/validate-ios-app.sh
./scripts/validate-ios-device.sh
```

The default PCK is
`godot/qualification/build/renderer/partydeck-last-light.pck`; set
`PARTYDECK_IOS_GODOT_PACK` to select another PCK with a receipt matching the current sources.
Both shipping and qualification app builds require the native engine and camera
archives. Each app wrapper builds its native variant unless the corresponding
environment variable supplies a prepared engine root:

| App configuration | Explicit native preparation | Default engine root / reuse variable |
| --- | --- | --- |
| Debug Simulator | `bash godot/ios-host/build-probe.sh engine simulator-debug` | `godot/ios-host/build` / `PARTYDECK_IOS_SIMULATOR_GODOT_ENGINE_ROOT` |
| Release device | `bash godot/ios-host/build-probe.sh engine device-release` | `godot/ios-host/build/device-release` / `PARTYDECK_IOS_DEVICE_GODOT_ENGINE_ROOT` |

Run these native preparations sequentially in one checkout; the helper locks its
shared upstream path. Supplied roots must contain both archives under `artifacts/`
and their matching `evidence/engine-artifact.json`. Xcode's staging phase verifies
the native source and archive hashes, pinned PCK, architecture, SDK and
configuration. Rebuild the native inputs after their sources change.
A direct `xcodebuild` invocation needs these inputs prepared first; see
[the iOS project instructions](../iosApp/README.md).

The shared script runs the common suites on `iosSimulatorArm64` and links the
Debug device framework. The baseline app script chooses an installed iPhone
runtime matching the selected Xcode's simulator SDK, builds the actual
SwiftUI/Compose application with the shipping profile, and runs app-hosted
`PartyDeckTests` plus the existing `PartyDeckUITests` flows. A test-only JVM TLS
peer runs alongside XCTest, with its real port and certificate pin passed through
Xcode's documented `TEST_RUNNER_` environment forwarding. CI requires the named
Java–Swift interoperability test to pass, Java to exit successfully, and its result
to prove the complete exchanges in both directions. A skipped or missing fixture
cannot make this step pass. Manifest, process logs and results are retained in
`build/ci/ios/interop`. This checks native TLS interoperability over simulator
loopback; physical-device LAN behavior remains a separate gate.

`validate-ios-device.sh` compiles the actual Swift/Kotlin app in **Release** for a
generic iOS device with signing disabled. This covers optimized device-only
scanner/bridge code and retains linker maps for symbol/license review. The build
must report `:composeApp:linkReleaseFrameworkIosArm64`. Both app wrappers verify
the packaged resources, selected activation profile and production link, including
one static `PartyDeckKit` owner and the required native definitions.
The Xcode project drives `:composeApp:embedAndSignAppleFrameworkForXcode`; do not
invoke that task from a generic shell without its Xcode environment.

To request the separate production Godot qualification in GitHub Actions:

```sh
gh workflow run validate.yml --ref main -f platform=ios -f ios_godot_session=true
```

For a focused regression of the two production sessions on current sources:

```sh
gh workflow run validate.yml --ref main -f platform=ios-godot-production
```

This explicit platform choice enables the qualification profile and builds the
current renderer, native Simulator engine and production Kotlin framework. It
runs the same two session cases with unchanged checks and deadlines. Shared
native, ordinary app/interop, UIKit layout and unsigned-device validation are
excluded from this focused run. Full Validate remains required for final
qualification. Focused outputs use the distinct
`ios-focused-production-reports-and-simulator-app` artifact, including a scope
log, the original session XCResult, attachments and packaged application.

For the full `platform=ios` run, the session input defaults to false; omit it for
the baseline. When true, the Simulator job attempts the baseline, UIKit layout
and production session suites independently once their shared native inputs
succeed; a baseline or layout failure does not skip the session suite.
`validate-ios-godot-session.sh` uses a separate build/result directory. It selects
exactly these two cases in `PartyDeckUITests/PartyDeckGodotSessionUITests`:

- `testProduction2DPracticeSession`
- `testProduction3DPracticeSession`

Each enters the real practice session through the actual presentation picker,
uses measured coordinates for Reveal/card/Hide/Play input on the native surface, checks the real
accepted viewer receipt, returns to Standard, cancels and confirms Leave, and
re-enters with the retained engine. The checker requires both named cases to
start and pass exactly once, an independent XCResult summary with exactly two
passes, and original screenshots plus sanitized observation attachments.

For the default local paths, after preparing the PCK and Simulator native inputs:

```sh
PARTYDECK_IOS_GODOT_SESSION_SMOKE=1 \
PARTYDECK_IOS_SIMULATOR_GODOT_ENGINE_ROOT="$PWD/godot/ios-host/build" \
bash scripts/validate-ios-godot-session.sh
```

The session wrapper requires the supplied Simulator engine root. It generates
`build/ci/ios/godot-session/activation/Info.plist` and `expectation.json` using
`scripts/prepare-ios-godot-activation.py` with `--modes 2d,3d`. The app-only
`PARTYDECK_APP_INFO_PLIST` setting selects that plist, while
`PARTYDECK_GODOT_ACTIVATION_EXPECTATION` binds it to the explicit request; test
bundles keep their own generated plists. The wrapper also supplies
`PARTYDECK_SESSION_QUALIFICATION_CONDITION=PARTYDECK_GODOT_SESSION_QUALIFICATION`
and verifies that both app and UI-test Debug targets retain `DEBUG` plus the
observation condition. The tests launch with `--partydeck-observe-godot-session`,
which enables observation only. Mode availability comes from the generated
bundled qualification profile and the existing native/pack checks.

The checked-in shipping profile still has an empty
`PartyDeckQualifiedGodotPresentations` array. Qualification requests populate
`PartyDeckQualificationGodotPresentations` in the generated plist. The same
workflow input makes the separate device job generate a qualification profile
under `build/ci/ios/device-activation` for its unsigned Release package. Locally,
set `PARTYDECK_IOS_GODOT_SESSION_SMOKE=1` when invoking
`validate-ios-device.sh` to request that profile. Release contains no Debug
observation code, and the device job performs no runtime tests. Production native
runtime is not yet accepted; build/link receipts retain
`ios_runtime_executed: false` and `kmp_factory_qualified: false`.

CI exports the PCK once in the Linux `ios-renderer-pack` job. Both ARM64
`macos-26` jobs verify its source revision/receipt, select Xcode 26.4.1, and then
run independently on separate runners: `ios` has a **180-minute** ceiling and
`ios-device` has a **150-minute** ceiling. The device job does not wait for
Simulator XCTest. Native engine compilation has a 90-minute step limit per
variant; shared tests have 35 minutes, baseline Simulator and Release app steps
have 40 minutes each, and the optional production session step has 45 minutes.
The baseline Java/Xcode test supervisor retains its own 30-minute Xcode deadline.

Evidence is uploaded with a 14-day retention period:

| CI artifact | Main evidence paths |
| --- | --- |
| `ios-renderer-pack` and `ios-renderer-pack-evidence` | `godot/qualification/build/renderer/`: shared PCK, export receipt, source revision and validation logs |
| `ios-shared-native-reports` | Module `build/reports` and `build/test-results`, plus `build/ci/ios/*.json`; uploaded before app compilation |
| `ios-reports-and-simulator-app` | `build/ci/ios/`: baseline `PartyDeck.xcresult`, `interop/`, `attachments/`, logs, link/input receipts and `PartyDeck-simulator.app.tar.gz`; native receipts in `godot/ios-host/build/evidence/` |
| `ios-reports-and-simulator-app` (requested session check) | `build/ci/ios/godot-session/`: activation files, `PartyDeckGodotSessions.xcresult`, `attachments/`, `result.json`, logs, link/input receipts and `PartyDeck-session-simulator.app.tar.gz` |
| `ios-focused-production-reports-and-simulator-app` | The same original session evidence, native/link/input receipts and packaged app, plus `build/ci/ios/focused-production-scope.log`; excludes the baseline and device suites |
| `ios-unsigned-release-device-app` | `build/ci/ios/`: Release logs/link receipts/maps, `device-activation/` when requested, and `PartyDeck-device-unsigned.app.tar.gz`; native receipts in `godot/ios-host/build/device-release/evidence/` |

Preserve or move a prior `build/ci/ios/PartyDeck.xcresult` before repeating the
baseline app test; the session wrapper refuses an existing
`build/ci/ios/godot-session` directory. App tarballs preserve executable
permissions. Simulator and unsigned device artifacts still need the appropriate
runtime, signing and release qualification. Neither package alone qualifies
local-network privacy prompts or physical Android/iOS interoperability. Artifact
uploads retry once after ten seconds; if both attempts fail, the workflow fails
and the missing evidence stays explicit.

For a smaller native toolchain/rules/protocol check, manually dispatch
`gh workflow run toolchain-smoke.yml`. This runs only the `:core` and `:session`
Apple simulator tests. Both workflows pass the selected simulator UDID explicitly
to every native test task, so an unrelated newer installed runtime is not chosen.

The Validate workflow runs both platforms for normal pushes and pull requests.
Manual runs accept `platform=all` (default), `android`, `ios`, or the focused
`ios-godot-production` selection described above, for example:

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
