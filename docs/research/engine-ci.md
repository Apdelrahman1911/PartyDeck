# Game engine boundary and CI research

Verified on 2026-09-09 against upstream documentation, source, release metadata, and GitHub runner manifests. This document distinguishes the initial implementation from the additional work required to ship an embedded engine game.

## Recommendation

Ship the first game with Compose inside the KMP application shell. Register only implemented, playable games in the common catalog. Keep engine presentation optional through a common event interface and a platform-provided factory; do not install, start, or simulate Godot for the initial release.

Android has an official Godot embedding path. Equivalent iOS embedding into an existing application is a separate integration project with unresolved upstream surface/lifecycle work. Claiming Android/iOS Godot parity now would exceed the evidence. A future engine game must pass the gate below before it becomes selectable.

## What the Godot sources establish

| Area | Verified evidence | Consequence for PartyDeck |
| --- | --- | --- |
| Stable engine release | The official repository reports **4.7.2-stable**, released 2026-08-18. | This is research context, not a dependency selected for the Compose release. Recheck compatible engine/export-template versions when starting an engine integration. |
| Android embedding | The official Android library guide documents an AAR published as `org.godotengine:godot`, a host-owned lifecycle, `GodotHost`, `GodotFragment`, and bidirectional communication through a runtime `GodotPlugin`. | An Android factory can eventually create a game-only host and translate coarse events through plugin signals/methods. The shell remains the application owner. |
| Android constraints | The guide warns: “Currently only a single instance of the Godot Engine is supported per process.” It also warns that automatic resizing/orientation configuration events are unsupported and may crash. | Do not instantiate one engine per card/game tile. Prove repeated entry/exit, process recreation, backgrounding, insets, and supported size/orientation changes on actual target devices. Do not assume an orientation lock resolves every Android window configuration. |
| Android assets | The guide supports packaged project assets or a PCK/ZIP selected with `--main-pack`, and describes asset filtering needed for Godot's hidden directories. | A future integration needs a real asset export/package pipeline and matching engine resources. An empty view or dummy scene is not shipping support. |
| iOS export/plugins | Official iOS documentation covers exporting a Godot-owned Xcode application and extending it with static-library/XCFramework plugins. It does not document an Android-equivalent drop-in host view. | Exporting a Godot project or writing an iOS Godot plugin does not by itself prove the KMP-owned application can embed and dispose of the engine. |
| Library C API | The 4.7.2 source has `libgodot_create_godot_instance` and `libgodot_destroy_godot_instance`, marked `@since 4.6`. The header does not provide the native rendering-surface injection proposed upstream. | A library entry point is useful evidence, but is not proof of mobile host-window integration or lifecycle correctness. |
| iOS/native-view work | Official proposal [#1473](https://github.com/godotengine/godot-proposals/issues/1473), for an embeddable iOS view, remains open. Proposal [#14435](https://github.com/godotengine/godot-proposals/issues/14435), opened around native-surface injection for LibGodot, also remains open. The latter describes fragile platform workarounds; these are a contributor's reported experience, not a supported API guarantee. | Do not implement proposed functions as if they already exist. Budget an iOS native integration spike, source maintenance, and device validation before selecting a renderer. |

The Android integration cost includes an engine AAR, exported assets, a platform host, lifecycle/thread dispatch, GPU memory, and additional testing. iOS adds native source/library packaging and proof that the existing SwiftUI/KMP host can own presentation and teardown. No startup-time, binary-size, frame-rate, or engineering-duration measurements have been made, so no numeric cost estimate is claimed.

Sources:

- [Godot 4.7.2 release](https://github.com/godotengine/godot/releases/tag/4.7.2-stable).
- [Official Android library guide source](https://github.com/godotengine/godot-docs/blob/stable/tutorials/platform/android/android_library.rst). The rendered documentation endpoint returned HTTP 403 in this environment; the official source was read instead.
- [Official iOS export guide source](https://github.com/godotengine/godot-docs/blob/stable/tutorials/export/exporting_for_ios.rst).
- [Official iOS plugin guide source](https://github.com/godotengine/godot-docs/blob/stable/tutorials/platform/ios/ios_plugin.rst).
- [LibGodot API at the researched release](https://github.com/godotengine/godot/blob/4.7.2-stable/core/extension/libgodot.h).
- [Apple application delegate source at the researched release](https://github.com/godotengine/godot/blob/4.7.2-stable/drivers/apple_embedded/godot_app_delegate.h).

## Proposed common boundary

These are PartyDeck-owned concepts, not claims about upstream Godot API names:

1. A `GameCatalog` contains stable game identifiers, player limits, presentation choice, and the metadata required by the shell. The first catalog contains only the implemented Compose game.
2. An optional embedded-game factory advertises its supported game/protocol identifiers. An absent factory means the engine capability is unavailable. There is no fake engine returning successful initialization.
3. The shell creates a presentation session only when entering a supported game and releases it when leaving. Navigation, settings, permission prompts, network ownership, and application lifecycle remain outside the engine.
4. Shell-to-renderer commands carry initialization, a **recipient-safe** game view, lifecycle changes, and disposal. Renderer-to-shell events carry readiness, player intents, completion, and explicit failures. There are no frame/tick, per-card transform, or animation-position messages.
5. The host-authoritative domain validates all player intents regardless of renderer. The engine never receives host-private decks, other players' hands, reconnect secrets, or authority to choose random outcomes.
6. The boundary uses a versioned message envelope and a bounded payload. Protocol/session mismatches, stale messages after disposal, duplicate readiness, and unsupported games fail explicitly. Rendering data does not become a second networking protocol or source of game rules.

A small common interface plus platform factory is enough. Keep platform view types out of `commonMain`; add Android/iOS adapters only when there is a real engine implementation. Wire the game catalog into the first-release UI so that it is an exercised boundary rather than an unused architecture sample.

Before a Godot game can ship on either platform, require a real scene and event round trip, entry/exit/re-entry, foreground/background transitions, host-view ownership, teardown without a running render loop, hidden-information checks, device GPU/input/audio checks, and a reproducible engine/assets build. Android and iOS must each pass independently. Optional engine support must never hold the Compose shell open or start in the lobby.

## CI toolchain and action selection

The coordinator selected Kotlin **2.4.20**, Compose Multiplatform **1.12.0**, Gradle **9.7.0**, AGP **9.3.1**, and JDK **21**. The [official Kotlin compatibility table](https://kotlinlang.org/docs/multiplatform/multiplatform-compatibility-guide.html) lists Kotlin 2.4.20 with Gradle through 9.7.0, AGP through 9.3.1, and Xcode 26.4.

Use `ubuntu-24.04` for Android/common validation and **`macos-26`** for Apple validation. GitHub's [hosted runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) identifies `macos-26` as ARM64; the separate Intel label is `macos-26-intel`. The [official ARM64 manifest](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md) lists **`/Applications/Xcode_26.4.1.app`**. Set `DEVELOPER_DIR=/Applications/Xcode_26.4.1.app/Contents/Developer`, and print `xcodebuild -version`, `xcodebuild -showsdks`, Java, and wrapper versions. Do not silently fall back to the runner's default Xcode 26.6 or a preview. Use `iosArm64` and `iosSimulatorArm64`; no Intel target is needed for this runner.

Official repository release metadata and commit endpoints resolved these action pins:

| Action | Release | Commit |
| --- | --- | --- |
| `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/setup-java` | v6.0.1 | `de7274f081f381c8f8158605e0321c36c376e2e6` |
| `actions/upload-artifact` | v7.0.1 | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |
| `gradle/actions/setup-gradle` | v6.3.0 | `9c971963bec38e04b3d30dcc455b5382be2fdbfb` |
| `android-actions/setup-android` | v4.0.1 | `40fd30fb8d7440372e1316f5d1809ec01dcd3699` |

Pin the full commits with release comments, as [GitHub's security guidance recommends](https://docs.github.com/en/actions/reference/security/secure-use). `android-actions` is a community-maintained project; prefer its small SDK setup task over importing an unrelated build framework. Explicitly request the selected platform/build-tools packages. Repository builds use the checked-in wrapper, never a runner-preinstalled Gradle.

[Gradle's v6.3.0 documentation](https://github.com/gradle/actions/blob/v6.3.0/docs/setup-gradle.md) states that setup automatically validates wrapper JARs. Do not add a redundant wrapper-validation action. Set **`cache-provider: basic`**: this explicitly selects the free open-source cache provider instead of the default proprietary enhanced provider, whose private-repository availability is described as a free preview. Do not also enable a second Gradle cache in setup-java. PR caches should be read-only. Use `contents: read`, checkout without persisted credentials, and normal `pull_request` events. CI has no store credentials.

## Required validation jobs

### Android and shared behavior

- Run the shared rule/session/protocol/catalog behavior suites on JVM through their actual registered Gradle tasks.
- Build `:androidApp:assembleDebug` and run `:androidApp:lintDebug` plus any meaningful Android-local tests. Run an unsigned release bundle build at a packaging checkpoint.
- Install exact selected Android SDK/build-tools packages; initial coordinator baseline is compile/target API 36 and minimum API 26.
- Upload test/lint reports on failure as well as success. Upload the APK and unsigned release bundle under clearly named artifacts. Never label a debug or unsigned artifact as store-ready.
- A real emulator smoke should exercise install/launch and key navigation once platform instrumentation exists. This cannot prove several physical Android/iOS devices interoperate over a local network.

### iOS on macOS

- Run the common behavior suites on `iosSimulatorArm64`, not only compile metadata on Linux. Build the iOS device framework as an additional architecture check at qualification.
- Build the real `iosApp/PartyDeck.xcodeproj`, shared scheme `PartyDeck`, with the Compose framework integrated through `:composeApp:embedAndSignAppleFrameworkForXcode`.
- Follow the [official direct-integration guidance](https://kotlinlang.org/docs/multiplatform/multiplatform-direct-integration.html): declare a framework binary, run the Gradle phase before Compile Sources, and disable User Script Sandboxing for that phase/project configuration. Do not invoke the embedding task outside the required Xcode build environment and claim it proves the app build.
- Discover an available iPhone simulator from the selected Xcode installation rather than hard-code a device marketing name or stale UDID. Run `xcodebuild test` against `PartyDeckUITests`, with a concrete simulator destination and `CODE_SIGNING_ALLOWED=NO`. The platform owner supplies a launch test asserting an actual shared-UI accessibility marker.
- Preserve `xcodebuild` failure status through any log piping. Save the `.xcresult`, build log, and a simulator screenshot. Tar the `.app` before artifact upload when retaining executable permissions matters; the [artifact action documents archive permission loss](https://github.com/actions/upload-artifact/blob/v7.0.1/README.md#permission-loss).
- Record the exact Xcode, SDK, simulator runtime, and CI run URL in qualification evidence. A framework-only link is not an application launch test; a launch test is not device networking/privacy verification.

Apple documents the `xcodebuild test`, `build-for-testing`, `test-without-building`, scheme, and destination commands in [TN2339](https://developer.apple.com/library/archive/technotes/tn2339/_index.html). Additional installed-tool options should be verified from `xcodebuild -help` and `xcrun simctl help` on the runner before use.

Set bounded job timeouts and concurrency cancellation for superseded PR runs. Keep the macOS work parallel to the Linux job, since both are required shipping targets. Use small, retained artifacts instead of publishing whole Gradle caches or signing directories.

## Release signing contract

Unsigned/debug CI must work with no credentials. Signing is a distinct environment-gated workflow or documented local command, never a silent fallback to a debug key.

- **Android:** a future signing configuration consumes a private upload keystore path, store password, key alias, and key password from environment/secrets. CI may decode a Base64 keystore into a runner-temporary path; do not commit the keystore, generate an upload identity during routine validation, or print passwords. The Android owner must align the actual environment variable names with the Gradle configuration. [Android's signing guide](https://developer.android.com/studio/publish/app-signing) documents keeping signing information out of shared build files.
- **iOS:** release signing requires the selected bundle identifier and Apple team, a distribution certificate/private key (`.p12`), its password, a matching provisioning profile, and export configuration. [GitHub's official certificate guide](https://docs.github.com/en/actions/use-cases-and-examples/deploying/installing-an-apple-certificate-on-macos-runners-for-xcode-development) documents `BUILD_CERTIFICATE_BASE64`, `P12_PASSWORD`, `BUILD_PROVISION_PROFILE_BASE64`, and `KEYCHAIN_PASSWORD` as example secret names. Use a temporary keychain and remove it/profile in an always-running cleanup step. A simulator `.app` cannot be submitted as an iOS release.
- **Distribution:** no App Store Connect or Play upload is implied by a passing build. Store listing, privacy declarations, cross-device local-network testing, accessibility/device performance, and the actual signed archive remain explicit qualification work owned with release review.

At research completion, workflows and application builds have not yet run. Exact test tasks and output paths will be resolved against the bootstrapped modules before workflow implementation; planned checks are not reported as passing evidence.
