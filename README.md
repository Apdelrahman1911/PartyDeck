# PartyDeck

A Kotlin Multiplatform party-game app for Android and iOS. **Last Light**, the first game, is an original local bluffing card game for two to six people. Practice with bots, host a table, or join a friend's table over an encrypted connection. The optional desktop launcher shares the same rules and interface.

## Play

Each round names a rank: Crown, Moon or Star. Play one to three cards face down and claim they match. Wilds always match. The next player can play or challenge. A caught bluff costs its author a light; a truthful claim costs the challenger. Burn out and you're eliminated. The last player lit wins.

Hosts and guests use the same reachable Wi-Fi network. Create a table, share its invitation or display its QR code, and have guests paste or scan it. Ready up, then the host starts. Invitations contain a host certificate fingerprint and private admission credential; share them only with intended players. No account or central matchmaking service is required. Some guest/public networks isolate devices and will prevent local connections.

Keep the host app open during play. Guests can reconnect to their existing seat after a brief interruption; ending the host process ends that table. Live matches are not saved across process termination.

Full rules and edge cases are in [docs/game-rules.md](docs/game-rules.md).

## Screenshots and visual feedback

Browse the [app screenshot gallery](docs/screenshots/README.md) for captured app
views, with platform, scenario and review-status labels. Refer to the image
filename when sharing feedback. The gallery includes both Godot presentations
and preserves failed and superseded iterations.

## Try both Godot tables

Both real presentations are implemented and retained for comparison. iOS shipping
builds offer **Standard table**, **2D table** and **3D table** in the same app
session, with Standard table selected initially. Android shipping builds offer
**Standard table**; explicit qualification builds enable the two Godot styles.

| Target | Build, install and compare |
| --- | --- |
| Android app session | [Enable both styles in PartyDeck](godot/android-host/README.md#production-session-preview) |
| Android standalone practice | [Download the comparison APK or build it locally](godot/android-host/README.md#build-and-run) |
| iOS Simulator app session | [Compare both styles in PartyDeck](iosApp/README.md#compare-2d-and-3d) |
| Linux desktop practice | [Run either packed presentation interactively](godot/comparison/README.md#build-and-run) |

Native qualification remains in progress. The comparison profiles and unsigned
device packages do not establish physical-device or store acceptance.

## Build and run

Use JDK 21 and Python 3.11 or later. The checked-in wrapper installs Gradle 9.7.0 and verifies its distribution checksum. Android needs command-line tools, platform-tools, **platform 37.1** and build-tools 36.0.0. Runtime target is Android 36; minimum Android 26.

```bash
sdkmanager 'platform-tools' 'platforms;android-37.1' 'build-tools;36.0.0'
# Set ANDROID_HOME to your SDK directory, or put sdk.dir=/your/sdk in local.properties.
bash scripts/prepare-godot-renderer.sh
./gradlew :androidApp:assembleDebug
adb install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk
```

The Android package includes the resources for both real Godot presentations. The preparation
script verifies an existing renderer pack or exports one with checksum-verified
Godot 4.7.2 on Linux x86_64. On another host, supply an official executable with
`PARTYDECK_GODOT_EXECUTABLE=/path/to/godot`. Native session integration remains
under qualification; Compose is the default gameplay surface.

Run the shared desktop application:

```bash
./gradlew :composeApp:run
```

iOS requires an ARM64 Mac with macOS 26.2+ and Xcode 26.4.1, with the iOS simulator runtime installed. Follow the [iOS setup](iosApp/README.md) to prepare the renderer PCK and matching native engine archives before opening `iosApp/PartyDeck.xcodeproj`. Select the shared **PartyDeck** scheme and an arm64 simulator. The Xcode build phase builds and embeds `PartyDeckKit` automatically. Device signing needs your own Apple team. Deployment minimum is iOS 15. Linux development uses the repository's macOS GitHub Actions job for native compilation and app tests.

The compatibility decisions and primary sources are in [docs/research/toolchain.md](docs/research/toolchain.md).

## Validation

Focused rules/protocol/network tests:

```bash
./gradlew :core:jvmTest :session:jvmTest :transport:jvmTest :games:jvmTest
```

Linux application validation, including Compose UI tests, Android lint and packaging:

```bash
# On Ubuntu 24.04, install the required graphics packages if missing.
./scripts/setup-ubuntu-graphics.sh
xvfb-run -a ./scripts/validate-android.sh
```

On macOS, run `./scripts/validate-ios-shared.sh`, `./scripts/validate-ios-app.sh`, and `./scripts/validate-ios-device.sh`. These check the native shared code, Simulator navigation and Java–Swift TLS interoperability, and the optimized unsigned device app. The **Validate** workflow also exercises debug and optimized Android APKs in an emulator and retains reports, screenshots, and build artifacts. See [scripts/README.md](scripts/README.md) for exact commands and signing variables.

## Architecture

| Module | Responsibility |
|---|---|
| `core` | Immutable Last Light rules, authoritative secrets, recipient-specific public views |
| `session` | Host authority, versioned protocol, lobby, authorization, replay protection, reconnect |
| `transport` | Native TLS, certificate-pinned invitations, bounded frames and LAN discovery |
| `games` | Game catalog and coarse optional engine extension |
| `composeApp` | Shared UI, app/session controller, practice, native service interfaces, desktop launcher |
| `androidApp` / `iosApp` | Native lifecycle, platform services, QR scanner and app packaging |
| `godot` | Active, isolated 2D/3D renderer comparison, shared authority bridge and native embedding qualification |

The shell owns navigation and lifecycle. The existing Last Light production baseline renders in Compose. Both [2D and 3D Godot presentations](godot/README.md) are implemented for hands-on comparison, with independent native platform qualification in progress. Clients send intents, the host validates actions and owns cryptographic randomness, and every guest receives only their own private hand. Disconnects preserve a seat for reconnection. Host loss ends the session; host migration and persistence of live matches are not implemented.

See [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) for ownership and acceptance criteria, [docs/security-review.md](docs/security-review.md) for the threat model, and [docs/ASSETS.md](docs/ASSETS.md) for original assets and third-party licenses.

## Release qualification

Signing credentials are supplied through environment variables and never stored in source. A release build without credentials produces an unsigned bundle. The exact automated evidence and remaining hardware/store gates are maintained in [docs/release-qualification.md](docs/release-qualification.md). Native compilation alone does not qualify mixed Android/iOS Wi-Fi behavior, physical-device performance, local-network permission prompts or store submission.

The detailed [status report](docs/STATUS.md) lists completed features, remaining work, and estimated milestone completion percentages.

The privacy inventory is in [docs/privacy.md](docs/privacy.md). The app stores preferences locally; transient names, cards and session credentials are exchanged with the host over the local encrypted connection. Camera frames used for QR scanning are not retained.
