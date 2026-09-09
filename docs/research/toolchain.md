# Toolchain evidence and independent environment review

Research date: 2026-09-09. Sources below were fetched directly from the official
documentation, release APIs, and artifact repositories. This document distinguishes
documented compatibility from builds actually executed by the independent reviewer.

Current iOS qualification: [run 34398824935][37] at
`987d380967149d80d8ba5761e206ecdf7386af25` passed the complete iOS job, including
**82 shared-native tests, three Swift TLS tests, three UI tests, and the optimized
unsigned device build**. All three evidence artifacts were downloaded and the
test results and interop JSON independently inspected. Earlier incomplete runs
below are historical checkpoints; their missing artifacts do not describe the
current qualification. Physical-device, minimum-OS, LAN, and signing gates remain
separate.

## Selected versions

| Component | PartyDeck selection | Evidence and reason |
| --- | --- | --- |
| Kotlin Multiplatform, serialization compiler plugin, Compose compiler plugin | **2.4.20** | Kotlin's latest stable release, published 2026-09-07. The Compose compiler plugin must match Kotlin. [1][2][3] |
| Compose Multiplatform | **1.12.0** | Latest stable release, published 2026-08-25. Official documentation says latest stable Compose supports latest stable Kotlin. [3][4] |
| Gradle wrapper | **9.7.0** | Within Kotlin 2.4.20's documented 7.6.3–9.7.0 range and above AGP 9.3's 9.5.0 minimum. The current Gradle release is 9.7.1; selecting 9.7.0 preserves the explicitly documented intersection. [1][5][6] |
| Android Gradle Plugin | **9.3.1** | Kotlin 2.4.20 documents AGP 8.5.2–9.3.1 compatibility. Google's Maven metadata confirms 9.3.1 is published. Newer stable 9.3.2 and 9.4.0 exist but exceed that table's tested ceiling. [1][5][7] |
| Gradle runtime JDK | **21**; installed Ubuntu **21.0.12+8-1-24.04** | Gradle 9.7.0 supports Java 17–26; AGP 9.3 requires at least 17. AGP 9.3.2 notes a JDK 17 lint crash fixed after 9.3.1, making JDK 21 the sensible runtime for this pin. [5][8] |
| Android compileSdk / targetSdk | **37.1 / 36** | Compose Android 1.12.0 and lifecycle 2.11.0 AAR metadata require compileSdk ≥37. The installed stable SDK is `platforms;android-37.1`, revision 1. Target 36 still meets Google Play policy and preserves the selected runtime behavior. [9][10] |
| Android SDK Build Tools | **36.0.0** | AGP 9.3's documented minimum and default; published in the stable SDK channel. [5][9] |
| Android command-line tools | Installed **19.0**, archive **13114758** | Official repository confirms this stable archive. Latest stable is 23.0 / 16111833, but updating a working SDK 36 bootstrap is unnecessary. [9] |
| Xcode for iOS CI | **26.4.1**, iOS SDK **26.4** | Kotlin documents Xcode 26.4 compatibility. GitHub's macOS 26 ARM64 image supplies Xcode 26.4.1 and its 26.4 SDK. Apple requires macOS 26.2 or later for this Xcode. [1][11][12] |
| iOS deployment target | **15.0 minimum** | Current Kotlin/Native defaults to iOS 15; Xcode 26.4.1 supports deployment targets 15–26.4. Compose alone lists iOS 14, which is not the complete toolchain floor. [3][11][13] |

The current Temurin 21 distribution is **21.0.12.1+1** according to Adoptium's API.
PartyDeck uses the already installed supported Ubuntu OpenJDK 21 distribution;
these are separate vendor build numbers, not an assertion that Ubuntu's patch
number equals Temurin's. [14]

The official Gradle 9.7.0 binary distribution SHA-256 is:

```text
84fbba45c7f4c64abc77460e1c00f541e9f960e3c7ed2538f1ede19eacd873ae
```

Source: [Gradle distribution checksum][15]. Pin this in the wrapper properties.

## Configuration constraints that affect implementation

- Use `org.jetbrains.kotlin.multiplatform` with Google's
  `com.android.kotlin.multiplatform.library` in shared modules. Google directs
  Android applications into a separate `com.android.application` module. The old
  KMP + `com.android.library` integration depends on deprecated AGP APIs. [16]
- The Android KMP plugin configures its Android target inside `kotlin { android { ... } }`.
  It has one variant, and host/device tests are disabled until explicitly enabled.
  Its minimum versions are AGP 8.10.0 and Kotlin 2.0.0. [16]
- Select SDK 37.1 in **both app and KMP modules** using the documented API below.
  `CompileSdkSpec.release` and `CompileSdkReleaseSpec.minorApiLevel` exist since
  AGP 8.13.0. Inspection of the downloaded AGP 9.3.1 API JAR also confirmed that
  `compileSdkMinor` shorthand exists on `CommonExtension` but **does not exist**
  on `KotlinMultiplatformAndroidLibraryExtension`. [18][19][20]

  ```kotlin
  compileSdk {
      version = release(37) { minorApiLevel = 1 }
  }
  ```

  The first compileSdk 36 smoke failed `checkDebugAarMetadata`. Directly reading
  `META-INF/com/android/build/gradle/aar-metadata.properties` in the resolved
  `androidx.compose.ui:ui-android:1.12.0` and
  `androidx.lifecycle:lifecycle-runtime-compose-android:2.11.0` AARs confirmed
  `minCompileSdk=37`, `minCompileMinorSdk=0`, and
  `minAndroidGradlePluginVersion=9.1.0`. Framework compatibility tables alone
  were insufficient to choose the application's compile SDK.
- Apply `org.jetbrains.kotlin.plugin.compose` at version 2.4.20 anywhere Compose
  compilation is needed. Do not infer the compiler version from Compose's 1.12.0
  runtime version. [3]
- Compose 1.12.0's release table includes **Material3 1.12.0-alpha03** and
  **Navigation 2.10.0-alpha02**. The core framework's stable status does not make
  these components stable. UI/navigation owners must verify and pin stable
  component releases independently. [4]
- Use `iosArm64()` and `iosSimulatorArm64()`: both are Kotlin/Native Tier 1.
  Apple targets require a macOS host. `iosX64()` is Tier 3 and is unnecessary for
  the selected ARM64 CI runner. [13]
- GitHub documents **`macos-26` as ARM64**, with `macos-26-intel` as the separate
  Intel label. Select `DEVELOPER_DIR=/Applications/Xcode_26.4.1.app/Contents/Developer`;
  the image's default Xcode is currently 26.6. The runner inventory is evidence
  of tool availability, not proof that PartyDeck's iOS build has passed. [12][17]
- A Compose/KMP Android application does not need a separately installed Kotlin
  CLI for its Gradle compilation. A project NDK/native build is only warranted
  if an actual native integration requires it; AGP lists its NDK minimum as N/A. [5]

## Bootstrap and verification status

- **Independent Linux environment gate passed, 2026-09-09.** The reviewer ran
  the following fresh invocation after the coordinator's bootstrap succeeded:

  ```sh
  ./gradlew --no-daemon --no-build-cache --rerun-tasks --console=plain \
    :core:jvmTest :transport:jvmTest :composeApp:compileKotlinJvm \
    :androidApp:assembleDebug
  ```

  Result: **BUILD SUCCESSFUL in 35s; 109 actionable tasks, 109 executed**.
  This executed Kotlin/JVM and Android compilation, Compose compilation,
  AAR metadata checks, dexing, and APK packaging. Core's bootstrap test ran
  **1 test, 0 failures, 0 errors**. Transport's test task was **NO-SOURCE**;
  this proves its dependencies resolve and its contracts compile, not that
  TLS or multiplayer functionality has been tested. Local execution log:
  `/tmp/partydeck-independent-bootstrap.log`.
- Independently executed `java -version`, `./gradlew --version`, and
  `sdkmanager --list_installed`: **passed**. The installed tools are OpenJDK
  `21.0.12+8-1-24.04-Ubuntu`, Gradle 9.7.0, SDK 37.1 revision 1, Build Tools
  36.0.0, platform-tools 37.0.1, and command-line tools 19.0. Gradle's reported
  embedded Kotlin 2.4.0 is its script runtime; the project's compiler plugin
  remains pinned to 2.4.20.
- The wrapper JAR SHA-256 matched the official published checksum:
  `7a9ce74cff467ca1bf60a4fcd9f05185acceda4d0f382434d393e17864262c5d`.
  The wrapper properties also contain the verified distribution checksum above. [21]
- Independently inspected the generated debug APK with `aapt2 dump badging`
  and `apksigner verify --verbose`: **passed**. Package `dev.partydeck.app`,
  version `1.0.0` / code `1`, minimum SDK **26**, target SDK **36**, compile
  API **37**, launcher `dev.partydeck.app.MainActivity`, valid v2 signature.
  Bootstrap artifact size: **16,541,418 bytes**; SHA-256:
  `c19f3756c8b75f18f56a7e7eda3f48179655fd7c41a8ee092fe5764cf9540b00`.
- The second bootstrap failed on duplicate `META-INF/LICENSE.md` resources
  from Bouncy Castle 1.85. The coordinator merged them with
  `packaging.resources.merges`; independent ZIP inspection confirmed all three
  license texts are retained in the APK's 3,513-byte entry. [22]
- Coordinator reports that the initial JDK apt installation failed because
  `/usr/share/man/man1` was missing; creating that directory and rerunning dpkg
  configuration resolved it. This installation incident is reported history,
  not an independently reproduced failure. Independent `dpkg --audit` is clean.
- Nonblocking output: a dependency's `libandroidx.graphics.path.so` was packaged
  without symbol stripping, and plugins emitted Gradle 10 deprecation notices.
  Gradle is pinned to 9.7.0; neither warning prevented the smoke build.
- iOS application compilation and simulator execution require the macOS workflow. Physical
  device behavior, signing, and distribution must be qualified separately from
  a successful unsigned simulator build. The release reviewer owns Android
  emulator launch validation, keeping that separate from this build gate.

## Independent CI and Apple toolchain checkpoint

The reviewer independently resolved all five action tags to the full commits
recorded in `docs/research/engine-ci.md` and inspected each pinned `action.yml`.
Checkout 7.0.1, setup-java 6.0.1, upload-artifact 7.0.1, Gradle actions 6.3.0,
and setup-android 4.0.1 all use Node 24. Shell/Python syntax checks passed;
the workflow uses read-only repository permissions, explicit Xcode selection,
the checked-in wrapper, and failure-preserving Xcode log piping.

Kotlin 2.4.20's published plugin sources revealed that the default native-test
device selector scans all available runtime groups and retains a device from
the last group for each platform. It is not tied to the selected SDK. The CI
owner corrected this by passing the SDK-matching simulator UDID through the
verified `KotlinNativeSimulatorTest` `--device` option for each native test task.
The selection script was independently checked with SDK 26.4 / runtime 26.4.1
fixtures and an additional booted 26.5 device; it selects 26.4.1 and fails
explicitly if that matching runtime is unavailable. These fixture checks were
script validation; the actual native execution evidence follows. [23]

**Native core/session gate passed:**
[Apple toolchain smoke run 34370981268][24], commit
`7c476586983bed92688c2715dd7ed1c6fedb20f4`, completed 2026-09-09 at 15:37:32 UTC.
The reviewer downloaded and inspected the run log, simulator JSON, and JUnit XML
reports, rather than relying only on the workflow conclusion.

| Execution evidence | Observed result |
| --- | --- |
| Runner / host | Actions runner 2.337.0; macOS 26.6.2, aarch64 |
| JDK | Temurin 21.0.12.1+1 LTS |
| Xcode / SDK | Xcode 26.4.1, build 17E202; iOS SDK 26.4 |
| Simulator | iPhone 17; iOS runtime 26.4.1, build 23E254a |
| Native compilation | Core and session `compileKotlinIosSimulatorArm64` and `linkDebugTestIosSimulatorArm64` executed |
| Core native tests | **14 passed**, 0 failed, 0 errors, 0 skipped |
| Session native tests | **21 passed**, 0 failed, 0 errors, 0 skipped |
| Gradle result | **28 tasks executed**, success in 2m 46s |

This manual job excludes transport implementation, the Compose framework, and
the Swift application/UI tests. Their full native qualification was open at this
checkpoint; the completed qualification in run 34398824935 below supersedes it.
The executed job confirms that the selected action pins, Android SDK setup for
KMP configuration, Kotlin/Native compiler, and Apple simulator work together.

The log identifies three nonblocking warnings: intentionally disabled Android
host tests; `val javaMain by creating` deprecations in the transport build script
(the indicated replacement is `val javaMain = create("javaMain")`); and a native
compiler warning that its four threads exceed the runner's three processors.
None prevented compilation or tests. Android host tests should be enabled when
meaningful Android-specific host tests are added, rather than hiding the warning.

Static iOS review confirmed that `:transport` is both an `api` dependency and an
explicit framework export, sufficient for the callback driver/observer facade.
The Swift-used app-handle/native-action types live in `composeApp` itself; no
transitive export of rules/session/coroutines is required by that facade.
JetBrains explicitly discourages unnecessary `transitiveExport` because it
expands the framework API, code retention, and compilation work. [25]

New Android scanner dependencies were also checked directly: CameraX
`camera-camera2`, `camera-lifecycle`, and `camera-view` **1.6.2** each declare
minimum SDK **23**, minimum compile SDK **36**, and minimum AGP **8.9.1** in their
published AARs. These fit PartyDeck's minimum 26 / compile 37.1 / AGP 9.3.1.

### First integrated native run

[Integrated run 34376593582][27], commit
`b1c24bb421b1f01b3b6a92b300dee9e6aad4fe19`, reached the full native module graph.
The reviewer independently downloaded completed iOS job **102550842446** logs.
SDK/JDK/Xcode setup succeeded and production
`:transport:compileKotlinIosSimulatorArm64` completed. Compilation then failed in
`SecurityTransportLifecycleTest.PausedDispatcher` at lines 109–114: its
unqualified `Runnable` was unresolved on Native and therefore its `dispatch`
method did not override the common coroutine dispatcher method.

The reviewer checked coroutines **1.11.0**'s published source archive:
`commonMain/CoroutineDispatcher.kt` takes `kotlinx.coroutines.Runnable`,
`commonMain/Runnable.common.kt` declares its `expect fun interface`, and
`nativeMain/Runnable.kt` provides the native implementation. Its JVM
representation is `java.lang.Runnable`, explaining why the missing common
import escaped JVM compilation. The transport owner added the verified
`import kotlinx.coroutines.Runnable`; the next integrated run below validated
that correction. [26]

This failed run did **not** compile or launch the Swift application: the app
step was skipped after shared-test compilation failed. The CI owner is allowing
independent framework/app diagnostics to continue after a shared-test failure
while preserving the overall failed result. No Swift or physical-device success
is inferred from this run.

### Full shared-native gate and first Swift compile

[Integrated run 34378549932][28], commit
`303abb651165497402794ae857e182a2581645cb`, completed the full shared-native
gate successfully at 16:56:54 UTC on 2026-09-09. The reviewer independently
downloaded iOS job **102557400358** logs and artifact **10115636035**, then
parsed every native JUnit report:

| Native module | Tests passed | Failures / errors / skips |
| --- | ---: | --- |
| Core rules | 14 | 0 / 0 / 0 |
| Session authority/protocol | 27 | 0 / 0 / 0 |
| Transport callback/security | 10 | 0 / 0 / 0 |
| Game catalog/engine boundary | 7 | 0 / 0 / 0 |
| Compose app controller | 16 | 0 / 0 / 0 |
| **Total** | **74** | **0 / 0 / 0** |

The native invocation completed in **12m 8s; 92 actionable tasks, all
executed**. All five modules compiled and linked their simulator tests.
`:composeApp:linkDebugFrameworkIosArm64` succeeded; the subsequent Xcode
invocation also executed `:composeApp:linkDebugFrameworkIosSimulatorArm64`
successfully. The archive contains the generated `PartyDeckKit.h` for both
architectures, including the public `CallbackLanTransport(driver:)`
constructor and synchronous native driver/observer protocols.

The actual Swift application reached Xcode compilation but **failed before
XCTest execution** at `NativeActions.swift:7`: `NativeActions` did not conform
to `IosNativeActions`. Both the compiler diagnostic and generated header
require `func doCopyText(value: String) -> Bool`; the Swift implementation
used `copyText(value:)`. The reviewer routed this exact diagnostic and the
generated header to the iOS owner. Remaining Swift bodies, simulator UI tests,
and the unsigned device application were unverified in this run and passed in
later runs below. This artifact contains no completed app archives; shared transport tests
do not substitute for execution of the Swift TLS implementation.

Local evidence is preserved under
`/tmp/partydeck-toolchain-review/integrated-ios-34378549932/`, including JUnit
XML, framework headers, Xcode result bundle/log, simulator metadata, and the
actual resolved Swift package file. The complete job log is
`/tmp/partydeck-toolchain-review/integrated-ios-34378549932.log`.

### Integrated Swift tests and optimized device build passed

In [run 34384326819][36], commit
`c73a659221f94a5ba7eeafa38a4b7a0754a54265`, the reviewer independently saved and
read the complete iOS job **102576688218** log. Both build/test steps succeeded;
the job failed only in artifact creation with
`Failed to CreateArtifact: Unable to make request: ENOTFOUND`. The artifact API
returned an empty list. This infrastructure failure is not a Swift build or
test failure, but it prevents independent inspection of this run's binaries,
native JUnit XML, fixture JSON, screenshots, and link maps.

| Executed gate | Evidence in the completed job log |
| --- | --- |
| All five shared-native suites and device framework | Successful native invocation; **13m 22s, 92 tasks executed** |
| Swift ordered TLS frames and peer closure | XCTest passed, 2.162 s |
| Swift–Java TLS in both host directions | XCTest passed, 0.460 s |
| Swift wrong-pin rejection | XCTest passed, 1.688 s |
| Shared Settings navigation | UI test passed, 14.808 s |
| Playable practice table | UI test passed, 10.349 s |
| XCTest totals | **3 native + 2 UI**, zero failures; `TEST SUCCEEDED` |
| Optimized device Kotlin framework | `:composeApp:linkReleaseFrameworkIosArm64` executed; native build **23m 51s** |
| Actual Release Swift device app | `BUILD SUCCEEDED`, `iphoneos`, generic iOS destination, signing disabled |

The required mixed XCTest ran without a skip. The checked-in supervisor also
returned successfully before the script entered device compilation, which
requires JVM exit zero and the complete two-direction PASS result. Independent
inspection of that run's JSON terminal-state values was unavailable because
its upload failed. Similarly, the expected **82** shared-native test count is
not presented as an independently parsed count for this run without its missing
XML. The subsequent run below supplies both current XML and complete fixture JSON.

The complete log and API metadata are preserved as
`/tmp/partydeck-toolchain-review/integrated-ios-34384326819.log`,
`integrated-ios-34384326819-job.json`, and
`integrated-ios-34384326819-artifacts.json`. The app/test script completed at
18:38:34 UTC on 2026-09-09, including both app-archive commands. Archive content
and minimum-OS runtime behavior still require their own evidence.

The next workflow separates shared-test preservation, Simulator tests/artifacts,
and a bounded optimized-device step. Independent source review confirmed that
artifact failures remain job failures while explicit status conditions permit
the remaining independent build diagnostics. The device script retains the
Release configuration, no-signing flag, link maps, and required optimized Kotlin
task. This review is distinct from successful execution of the new split.

### Complete iOS qualification and preserved artifacts

[Run 34398824935][37], commit `987d380967149d80d8ba5761e206ecdf7386af25`,
completed iOS job **102625289447** successfully, including every build/test and
artifact-upload step. The reviewer independently downloaded all three artifacts:

| Artifact | GitHub artifact ID | Preserved evidence |
| --- | --- | --- |
| `ios-shared-native-reports` | `10122764571` | Native JUnit XML and HTML reports, simulator selection |
| `ios-reports-and-simulator-app` | `10123022960` | Simulator app archive, Xcode log and result bundle, interop JSON/logs, eight UI screenshots, debug headers and link maps |
| `ios-unsigned-release-device-app` | `10123371908` | Actual unsigned Release device app archive, Xcode log, release framework header and link maps |

All **13** native JUnit reports were parsed and their declared counts checked
against individual testcase elements: **82 tests, zero failures, errors, or
skips**. The breakdown is core **14**, session **27**, transport **10**, games
**7**, and app controller **24**. The job log shows all five native test tasks
executing; the full native invocation completed in **4m 14s**, with **92 tasks:
73 executed and 19 from cache**.

The actual Xcode log contains exactly these six named passing XCTest records:

| XCTest | Duration |
| --- | ---: |
| `testPinnedTLSExchangesOrderedFramesAndClosesBothPeers` | 1.744 s |
| `testSwiftAndJavaTLSInteroperabilityInBothDirections` | 0.615 s |
| `testWrongCertificatePinFailsBeforeOutgoingConnectionIsAnnounced` | 0.934 s |
| `testNativeHostCanNavigateSharedSettings` | 21.573 s |
| `testSharedControllerHostsANativeTableAndShowsItsInvitation` | 25.946 s |
| `testSharedHomeOpensAPlayablePracticeTable` | 29.517 s |

Both XCTest suites report **three tests and zero failures**, followed by
`TEST SUCCEEDED`. The recorded destination is an **iPhone 17 Simulator running
iOS 26.4.1**, selected against SDK **26.4**. These results do not establish
execution on iOS 15 or a physical phone.

The downloaded fixture result is the complete version-1 PASS record:

```json
{
  "version": 1,
  "status": "PASS",
  "forwardBytesReceived": 65536,
  "forwardBytesSent": 20000,
  "reverseBytesSent": 20000,
  "reverseBytesReceived": 65536,
  "forwardTerminalState": "Closed",
  "reverseTerminalState": "Closed"
}
```

`orchestration.json` independently records `passed: true`, `xcodeExitCode: 0`,
`javaExitCode: 0`, and the required mixed-test name. The fixture log records both
host directions, acknowledged payloads, and peer closure. This replaces the
previous run's evidence limitation with inspected JSON; no skipped interop test
is counted as success.

The actual `:composeApp:linkReleaseFrameworkIosArm64` task executed in a native
invocation lasting **6m 50s**; the Release `iphoneos` Swift application then
reported `BUILD SUCCEEDED`. Both application archives, generated framework
headers, and link maps are present in the downloaded artifacts. Bundle contents,
notices, privacy declarations, and signing inspection are recorded separately
in `docs/release-qualification.md`.

Evidence root: `/tmp/partydeck-toolchain-review/integrated-ios-34398824935/`.
It contains the complete `ios-job.log`, run/job/artifact API snapshots, original
artifact ZIPs and extracted trees, `independent-native-junit-summary.json`, and
`independent-xctest-result-summary.json`. No Gradle or device command was rerun
locally for this artifact review.

### Native warning classification

Both successful Swift configurations warn about `retainedActions` and
`retainedHandle` captured by the main-queue cleanup closure in
`PartyDeckOwner.deinit`. Swift's SE-0371 confirms that a plain synchronous
`deinit` does not inherit its class's `@MainActor` isolation. The implementation
retains the two dependencies in local references, avoids an escaping `self`,
and performs their cleanup on the main thread. These are unresolved Sendable
annotation warnings; passing tests alone do not prove every deinitialization
interleaving safe. No blanket suppression or unchecked Sendable conformance was
added. Adopting Swift 6.2's `isolated deinit` would need a separate deployment
compatibility review for the retained iOS 15 minimum. [40]

The simulator linker warning names Skiko **0.150.1**'s
`libicu.icudtl_dat.o`, whose minimum simulator version is **18.5** while the
app links for **15.0**. The reviewer verified the resolved simulator/device KLIB
SHA-256 values against published module metadata, unwrapped their universal
static archives, and inspected all four arm64/arm64e ICU data objects using
Apple's Mach-O header layouts. The simulator objects contain **zero instruction
bytes, zero relocations, and zero undefined symbols**. Their only nonempty
section is **6,296,800 bytes of constant data**, byte-identical to the device
objects; the device arm64/arm64e minimum versions are **12.0/14.0**. The Skia
`m150-1f14f1166a` build and generator sources confirm that this member is emitted
from ICU's data file as assembly constants. [41][42][43][44][45]

This specific warning is a dependency data-object deployment-metadata mismatch,
with no newer-OS API reference in that object. It does not justify raising the
application's minimum OS or globally suppressing linker warnings. It also does
not establish minimum-OS compatibility of the entire dependency graph. The
inspection is preserved in
`/tmp/partydeck-toolchain-review/skiko-icu/independent-icu-object-inspection.json`.

### Android preparation and JVM close-test review

The extracted Android readiness method preserves the strict launcher and crash
dialog checks before APK installation. The wrapper's preparation phase permits
at most one recovery, requiring confirmed app absence, the exact System UI ANR
in both fresh UI evidence and logcat, successful settings restoration, and a
new kernel boot ID with completed boot. It preserves the first failing UI before
collecting fresh diagnostics. A diagnostic exception cannot bypass restoration
or grant recovery. The later application-driver cleanup correction likewise
retains the original application failure, records cleanup failures separately,
and prints success only after cleanup and result writing succeed.

Run 34398824935 exercised the failure boundary: System UI failed startup on the
first boot and after the single permitted reboot. Both attempt records confirm
PartyDeck absent; the second forbids recovery, and neither APK acceptance run
started. This establishes preparation behavior, not application runtime success.
The preserved second-boot log shows high CPU pressure and **43.86 seconds** of
RenderEngine shader-cache generation, with no corresponding memory-pressure
signal. The subsequent `swangle` candidate is supported by both installed
emulator help and Android's documentation: ANGLE with SwiftShader for GLES,
while Vulkan still uses SwiftShader. Pixel 7 dimensions/density, API 36, KVM,
memory, preparation limits, and application assertions are unchanged. Its
performance requires a new runtime result. [47]

The manual workflow platform selector is a required single-choice string with
default `all`. Source review confirms normal push/PR events select both jobs,
while manual `android` or `ios` selects only the named job. [46]

The JVM listener-close test now requires the incoming stream to finish and a
loopback `ConnectException` within two seconds. Successful probes retry only
within that bound; timeouts and unrelated I/O exceptions fail. OpenJDK 21's
`NioSocketImpl.close()`, `tryClose()`, and `endAccept()` confirm why an in-flight
accept can defer final descriptor closure. The correction changes only the
test's observation of closure, with no production transport modification.
[38][39]

### JVM–Swift interoperability harness source review

The independent reviewer inspected the JVM fixture, Swift native test/probe,
classpath export, Python runner, shell integration, and artifact paths before
the next macOS execution. Four exact patterned payloads match across the peers:
65,536 bytes and 20,000 bytes in each host direction. ACKs establish remote
receipt before each close; the Java fixture waits for terminal states and
closes its transport before publishing PASS. Swift incrementally parses framed
bytes, handles zero-length heartbeats separately, and asserts complete payload
content, ordering, and application-write results.

The original runner could block indefinitely on Xcode stdout and signalled only
direct child processes. The CI owner corrected it after review: selector-based
pipe reads check a **30-minute Xcode deadline** and premature nonzero Java exit;
both children own new process sessions, with bounded process-group TERM/KILL
cleanup. The Python documentation confirms these POSIX process and Unix-pipe
semantics. [29][30][31]

Success requires a named XCTest **passed** record, Xcode and JVM zero exit
statuses, fresh version-1 PASS JSON, all four exact byte counts, and both
terminal-state fields in `Closed`, `Failed:UNAVAILABLE`, or `Failed:IO_ERROR`.
Missing environment delivery cannot become a silent successful skip: Swift
fails when its required flag is present but the manifest is absent; if both
forwarded values are absent, the runner rejects the missing test-pass record.
The manifest publishes only a loopback port and public certificate fingerprint;
fixture outputs do not write private keys. Both identities remain in memory.

Python AST parsing, shell syntax, and whitespace checks passed. This was a
**source review**, with no additional local Gradle execution. Actual
`TEST_RUNNER_` delivery, Simulator loopback reachability, and
JSSE–Network.framework interoperability were subsequently established by the
required mixed test and complete fixture evidence in run 34398824935 above.
Installed Xcode help/manual output is retained; Apple documents the test's async
expectation waits as concurrency-safe and timeout-bounded. [32]

The reviewer also independently checked the Ubuntu graphics setup correction:
the exact hosted-image source configures `ubuntu.sources`; official Noble
documentation confirms its deb822 format, signed-keyring verification, and
acquisition retries. Installed `apt-config` independently confirmed the
`Dir::Etc::sourcelist` and `Dir::Etc::sourceparts` keys. Both update and install
receive the restricted source options, without changing persistent APT
configuration or disabling authentication. Shell syntax passed; this reviewer
did not execute a package update/install. Actual missing-package installation
remains a CI check. [33][34][35]

## Authoritative sources

[1]: https://kotlinlang.org/docs/multiplatform/multiplatform-compatibility-guide.html
[2]: https://github.com/JetBrains/kotlin/releases/tag/v2.4.20
[3]: https://kotlinlang.org/docs/multiplatform/compose-compatibility-and-versioning.html
[4]: https://github.com/JetBrains/compose-multiplatform/releases/tag/v1.12.0
[5]: https://developer.android.com/build/releases/agp-9-3-0-release-notes
[6]: https://services.gradle.org/versions/current
[7]: https://dl.google.com/dl/android/maven2/com/android/tools/build/gradle/maven-metadata.xml
[8]: https://docs.gradle.org/9.7.0/userguide/compatibility.html
[9]: https://dl.google.com/android/repository/repository2-3.xml
[10]: https://support.google.com/googleplay/android-developer/answer/11926878?hl=en
[11]: https://developer.apple.com/xcode/system-requirements
[12]: https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md
[13]: https://kotlinlang.org/docs/native-target-support.html
[14]: https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture=x64&image_type=jdk&os=linux&vendor=eclipse
[15]: https://services.gradle.org/distributions/gradle-9.7.0-bin.zip.sha256
[16]: https://developer.android.com/kotlin/multiplatform/plugin
[17]: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
[18]: https://developer.android.com/reference/tools/gradle-api/9.3/com/android/build/api/dsl/CompileSdkSpec
[19]: https://developer.android.com/reference/tools/gradle-api/9.3/com/android/build/api/dsl/CompileSdkReleaseSpec
[20]: https://developer.android.com/reference/tools/gradle-api/9.3/com/android/build/api/dsl/KotlinMultiplatformAndroidLibraryExtension
[21]: https://services.gradle.org/distributions/gradle-9.7.0-wrapper.jar.sha256
[22]: https://developer.android.com/reference/tools/gradle-api/9.3/com/android/build/api/dsl/ResourcesPackaging
[23]: https://repo.maven.apache.org/maven2/org/jetbrains/kotlin/kotlin-gradle-plugin/2.4.20/kotlin-gradle-plugin-2.4.20-sources.jar
[24]: https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34370981268
[25]: https://kotlinlang.org/docs/multiplatform/multiplatform-build-native-binaries.html#export-dependencies-to-binaries
[26]: https://repo.maven.apache.org/maven2/org/jetbrains/kotlinx/kotlinx-coroutines-core/1.11.0/kotlinx-coroutines-core-1.11.0-sources.jar
[27]: https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34376593582
[28]: https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34378549932
[29]: https://docs.python.org/3/library/subprocess.html
[30]: https://docs.python.org/3/library/os.html#os.killpg
[31]: https://docs.python.org/3/library/selectors.html
[32]: https://developer.apple.com/documentation/xctest/xctestcase/fulfillment(of:timeout:enforceorder:)
[33]: https://github.com/actions/runner-images/blob/ubuntu24/20260907.300/images/ubuntu/scripts/build/configure-apt-sources.sh
[34]: https://manpages.ubuntu.com/manpages/noble/en/man5/apt.conf.5.html
[35]: https://manpages.ubuntu.com/manpages/noble/en/man5/sources.list.5.html
[36]: https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34384326819
[37]: https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34398824935
[38]: https://github.com/openjdk/jdk21u/blob/master/src/java.base/share/classes/sun/nio/ch/NioSocketImpl.java
[39]: https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/net/ConnectException.html
[40]: https://github.com/swiftlang/swift-evolution/blob/main/proposals/0371-isolated-synchronous-deinit.md
[41]: https://github.com/JetBrains/skia/blob/m150-1f14f1166a/third_party/icu/BUILD.gn
[42]: https://github.com/JetBrains/skia/blob/m150-1f14f1166a/third_party/icu/make_data_assembly_for_skiko.py
[43]: https://github.com/apple-oss-distributions/cctools/blob/main/include/mach-o/loader.h
[44]: https://github.com/apple-oss-distributions/cctools/blob/main/include/mach-o/fat.h
[45]: https://github.com/apple-oss-distributions/cctools/blob/main/include/mach-o/nlist.h
[46]: https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions#onworkflow_dispatchinputs
[47]: https://developer.android.com/studio/run/emulator-acceleration
