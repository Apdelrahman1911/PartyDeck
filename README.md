# PartyDeck

A Kotlin Multiplatform party-game app for Android and iOS. **Last Light**, the first game, is an original local bluffing card game for two to six people. Practice with bots, host a table, or join a friend's encrypted invitation. The optional desktop launcher shares the same rules and interface.

## Play

Each round names a rank: Crown, Moon or Star. Play one to three cards face down and claim they match. Wilds always match. The next player can play or challenge. A caught bluff costs its author a light; a truthful claim costs the challenger. Burn out and you're eliminated. The last player lit wins.

Hosts and guests use the same reachable Wi-Fi network. Create a table, share its invitation or display its QR code, and have guests paste or scan it. Ready up, then the host starts. Invitations contain a host certificate fingerprint and private admission credential; share them only with intended players. No account or central matchmaking service is required. Some guest/public networks isolate devices and will prevent local connections.

Full rules and edge cases are in [docs/game-rules.md](docs/game-rules.md).

## Build and run

Use JDK 21. The checked-in wrapper installs Gradle 9.7.0 and verifies its distribution checksum. Android needs command-line tools, platform-tools, **platform 37.1** and build-tools 36.0.0. Runtime target is Android 36; minimum Android 26.

```bash
sdkmanager 'platform-tools' 'platforms;android-37.1' 'build-tools;36.0.0'
# Set ANDROID_HOME to your SDK directory, or put sdk.dir=/your/sdk in local.properties.
./gradlew :androidApp:assembleDebug
adb install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk
```

Run the shared desktop application:

```bash
./gradlew :composeApp:run
```

iOS requires macOS 26.2+ and Xcode 26.4.1, with the iOS simulator runtime installed. Open `iosApp/PartyDeck.xcodeproj`, select the shared **PartyDeck** scheme and an arm64 simulator. The Xcode build phase builds and embeds `PartyDeckKit` automatically. Device signing needs your own Apple team. Deployment minimum is iOS 15. Linux development uses the repository's macOS GitHub Actions job for native compilation and app tests.

The compatibility decisions and primary sources are in [docs/research/toolchain.md](docs/research/toolchain.md).

## Validation

Focused rules/protocol/network tests:

```bash
./gradlew :core:jvmTest :session:jvmTest :transport:jvmTest :games:jvmTest
```

Linux application validation, including Compose UI tests, Android lint and packaging:

```bash
# Install xvfb and the graphics libraries listed in .github/workflows/validate.yml.
xvfb-run -a ./scripts/validate-android.sh
```

On macOS, run `./scripts/validate-ios-shared.sh` and `./scripts/validate-ios-app.sh`. The **Validate** workflow runs Linux and macOS checks and retains reports, screenshots, debug APK, unsigned release bundle and simulator app artifacts. See [scripts/README.md](scripts/README.md) for exact commands and signing variables.

## Architecture

| Module | Responsibility |
|---|---|
| `core` | Immutable Last Light rules, authoritative secrets, recipient-specific public views |
| `session` | Host authority, versioned protocol, lobby, authorization, replay protection, reconnect |
| `transport` | Native TLS, certificate-pinned invitations, bounded frames and LAN discovery |
| `games` | Game catalog and coarse optional engine extension |
| `composeApp` | Shared UI, app/session controller, practice, native service interfaces, desktop launcher |
| `androidApp` / `iosApp` | Native lifecycle, platform services, QR scanner and app packaging |

The shell owns navigation and lifecycle. Last Light renders in Compose. A future Godot renderer can use the engine extension; no Godot runtime is started by this game. Clients send intents, the host validates actions and owns cryptographic randomness, and every guest receives only their own private hand. Disconnects preserve a seat for reconnection. Host loss ends the session; host migration and persistence of live matches are not implemented.

See [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) for ownership and acceptance criteria, [docs/security-review.md](docs/security-review.md) for the threat model, and [docs/ASSETS.md](docs/ASSETS.md) for original assets and third-party licenses.

## Release qualification

Signing credentials are supplied through environment variables and never stored in source. A release build without credentials produces an unsigned bundle. The exact automated evidence and remaining hardware/store gates are maintained in [docs/release-qualification.md](docs/release-qualification.md). Native compilation alone does not qualify mixed Android/iOS Wi-Fi behavior, physical-device performance, local-network permission prompts or store submission.

The privacy inventory is in [docs/privacy.md](docs/privacy.md). The app stores preferences locally; transient names, cards and session credentials are exchanged with the host over the local encrypted connection. Camera frames used for QR scanning are not retained.
