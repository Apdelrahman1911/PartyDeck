# PartyDeck implementation and acceptance plan

The user brief is preserved in `plan.md`. This is the executable plan, prepared from independent toolchain, gameplay, security, platform, design and release research before feature implementation. The coordinator integrates changes; ten implementation owners and five independent reviewers use `gpt-6-astra` with `max` reasoning.

## Product and scope

Ship a Kotlin Multiplatform application shell for Android and iOS, with one complete original game, **Last Light**. A JVM launcher reuses the same UI and rules for local development and smoke validation. Android/iOS drive all design decisions. The first renderer uses Compose: a turn-based card game does not need a continuously running engine. The catalog and coarse event-based engine interface allow future Godot games, but no nonfunctional Godot entry appears in the product. Native Godot integration is a future renderer-specific qualification gate, not a dependency of this release.

People can learn through a short rules sheet and a full practice match, host a LAN table, or join a host's invitation. Hosts and guests use the same versioned authority and game rules as practice. Accounts, a hosted backend, advertising, analytics and internet matchmaking are unnecessary. Devices must share a reachable local network; access-point isolation and permission failures must produce actionable errors. No Bluetooth/offline-hotspot compatibility is claimed without verification.

## Architecture and ownership

| Module / files | Responsibility | Implementation owner | Review owner |
|---|---|---|---|
| Root Gradle, version catalog, wrapper, integration | Compatible reproducible build, shared dependency boundaries, integration fixes | Coordinator | review_environment |
| `core/src` | Immutable rules/state, cards, deterministic injected randomness, safe player views, focused tests | game_domain | review_game |
| `session/src` | Lobby authority, protocol DTOs, peer authorization, revisions, receipts, reconnection, tests | session_protocol | review_security + review_game |
| `transport/src`, `iosApp/PartyDeck/Networking` | TLS hosts/clients, certificate pinning, framing, LAN discovery, native connection lifetime | network_transport | review_security |
| `composeApp/.../controller` | StateFlow app controller, session runtimes, practice bots, shared platform contracts | app_controller | review_game + review_release |
| `composeApp/.../ui/theme`, `ui/shell`, `PartyDeckApp.kt` | Theme, navigation, home, host/join, lobby, settings, onboarding/error UX | ui_shell | review_design |
| `composeApp/.../ui/game` | Card hand/table, challenge/penalty/round/results presentation | ui_game | review_design |
| `composeResources`, `assets` | Licensed fonts, original vector symbols/marks, audio, asset inventory | assets | review_design + review_release |
| `androidApp/src`, shared `androidMain` | Android entry point, lifecycle, preference/audio/haptic services, manifest | android_platform | review_release |
| `iosApp` except Networking, shared `iosMain` | SwiftUI shell/Xcode project, native services, local-network privacy, framework integration | ios_platform | review_release |
| `games/src`, `.github/workflows`, `scripts` | Game catalog/engine boundary, CI build/test/package/simulator automation | engine_ci | review_environment + review_release |

Owners may communicate directly to agree interfaces. Root owns shared Gradle changes. Reviewers independently run checks and report failures; they do not mark work accepted because an implementation agent says it works. New review tests use explicitly separate files. No agent pushes or performs destructive Git operations; the coordinator makes coherent milestone commits and pushes the authorized repository.

## Toolchain and platform strategy

Research pins Kotlin 2.4.20, Compose Multiplatform 1.12.0, stable Material3 1.9.0, AGP 9.3.1, Gradle 9.7.0, JDK 21, coroutines 1.11.0, serialization 1.11.0 and lifecycle 2.11.0. Shared Android modules use `com.android.kotlin.multiplatform.library`, with a separate application module. Compile SDK 37.1 satisfies current Compose Android AAR requirements; target API 36 meets current Play policy, minimum API 26. iOS targets are arm64 device and arm64 simulator, deployment 15.0, Xcode 26.4.1 selected on macOS 26 ARM64 CI. Versions and primary sources are recorded under `docs/research`.

Bootstrap must compile common Kotlin/tests, Compose JVM and an Android debug APK, then an independent reviewer must run the same important paths. Native iOS compilation and actual Swift bridge APIs must be verified by macOS CI. No NDK or Godot installation is needed for this Compose renderer. Toolchain defects are fixed before major features.

## Rules and authority

`docs/game-rules.md` is the detailed rules specification. Two to six players use a thirty-card deck: nine each Crown/Moon/Star plus three Wilds. Deal five to each survivor. One required rank is public each round. A legal turn plays one to three selected cards face down or challenges the immediately preceding claim. Wilds match any required rank. Empty hands wait until redeal; the final nonempty hand must challenge, which avoids all-empty deadlocks.

Challenge examines only the challenged cards. A bluff penalizes its author; a truthful claim penalizes the challenger. Each player starts with a secret random burnout step from one through six. Penalties expose the next fuse light; burnout eliminates that player. These fictional lights are shown without weapons or graphic content. A penalty ends the round. The host explicitly continues, redealing survivors and rotating the opener. The final survivor wins; return-to-lobby enables a rematch.

Domain state is immutable, owns cards exactly once, validates actor/phase/card identities, and has no platform/network dependencies. The host injects a native CSPRNG-backed Kotlin Random; every secret outcome uses fresh cryptographic randomness. Tests inject deterministic seeded generators. Clients never choose outcomes. Secret hand/deck/burnout fields are absent from serializable public views. Each viewer sees their own cards and opponents' counts only; reveal payloads contain only the challenged cards.

## Secure local multiplayer

Use established platform TLS implementations: JVM/Android JSSE and iOS Network.framework/Security, with per-host certificate identity and exact SHA-256 certificate pinning. Bouncy Castle and Apple's Swift Certificates only construct certificates; do not create custom ciphers or bundle a shared private key. An out-of-band invitation carries endpoint, session identity, full host certificate fingerprint and high-entropy admission secret. Discovery records contain no admission/reconnect secrets and are untrusted hints. Manual invitation entry must bypass discovery failures. Authentication is completed before acting on application messages.

The transport exposes ordered bounded byte messages plus connection/discovery/lifetime events. The session owns JSON protocol versioning, admission, individual reconnect credentials, authority decisions, validation and snapshots. The authenticated connection determines actor identity; a client cannot nominate another actor. Incoming messages, names, card selections, connection counts, queues and timeouts are bounded. Actions carry monotonic command IDs and expected revisions. A high-water mark and bounded receipt cache reject replays even after cache eviction. Repeated commands return the receipt with a current snapshot instead of replaying old state. Resume rotates/rebinds connection state and recovers the command counter under the same serial authority gate.

Disconnect pauses the match without silently playing hidden cards. Reconnection restores the same seat/private hand. The host can return to the lobby when a seat is lost. Host loss ends the session cleanly and offers return home; migration is deliberately unsupported because transferring hidden authoritative state would change the threat model. Matches are transient and not restored across host process death. Discovery, listeners, sockets, audio, coroutines and pending commands close with their owner.

## UI, assets, accessibility and performance

Original editorial card-club direction: warm ink, ivory paper, citron and restrained copper, licensed Fraunces and Manrope typography, original Crown/Moon/Star/Wild vectors and light/sound cues. Assets must have source and license evidence; no copied game branding, textures or audio. Native launcher icons are finished assets.

Phone-first portrait composition adapts to compact widths, landscape and larger screens without forced orientation hacks. All screens respect system bars, keyboard and iOS safe areas. Main flow: Home → Host/Join → Lobby → Game → Round outcome → Winner; Settings/Rules are accessible without disrupting a live session. Lobby names connection/ready state, host control and invite sharing. Gameplay emphasizes current actor, required rank, selected cards, a clear play claim and challenge opportunity. Round/winner presentation explains who was truthful and why a light was lost. Loading, rejection, permission denial, network loss and empty states have clear recovery.

Minimum controls are 48 dp; readable 16 sp body type, contrast, non-color status cues, accessible names, private-hand semantics and large text are reviewed. Reduced motion and sound/haptic toggles persist. Motion conveys selection/turn/reveal and does not delay authority updates. English resources are structured for future localization; no unsupported language is advertised. Sound is optional and stops in background. No continuous renderer loop outside the active game; no frame-by-frame platform bridge; expensive IO/crypto occurs off the UI thread. State has one owner, snapshots are bounded, coroutine scopes and listeners have explicit teardown.

## Dependency-ordered milestones

1. **Research/bootstrap:** install JDK/SDK/Gradle, create the minimal project, compile tests/Compose/Android, independently repeat, fix environment defects. Research network and platform APIs before choosing adapters. Commit/push bootstrap.
2. **Freeze contracts:** safe domain views; session requests/responses/dispatches; bounded transport factory/connection interface; app state/platform services; theme tokens/game screen contract. Review rules, threat model and first screen design before expanding implementation.
3. **Parallel foundation:** domain engine and tests; session authority against those types; native TLS adapters and pairing; catalog/engine extension; platform shells/services; typography/vectors/audio. Controller implements practice and lifecycle once domain/session contracts exist. Review core invariants continuously.
4. **Product UI/integration:** shell and gameplay owners consume controller/view contracts and shared theme. Wire host/join/discovery, lobby readiness, actions, round progression, reconnect and rematch. Show real errors and pending state. Verify Android and macOS compilation early, then fix integration issues.
5. **Qualification/iteration:** independent rule simulation/adversarial protocol tests; TLS loopback/pinning/malformed data/reconnect tests; controller practice/navigation tests; Android lint/debug+release and JVM visual smoke; iOS framework/Xcode/simulator build/run on CI. Review actual rendered narrow and large-text UI, improve weak work. Profile meaningful rule/network paths and check resource lifetime.
6. **Delivery:** coherent commits/pushes, working workflows and build artifacts, signing instructions, privacy/asset inventory, README quick start, review findings resolved or explicitly classified external. Verify clean tracked work and CI at delivered commit. Do not claim store/device qualification from compilation alone.

## Meaningful verification and acceptance

- Rules: thirty unique cards, truthful/wild/bluff outcomes, legal turn/card/phase checks, force-challenge behavior, eliminated-player handling, round opener progression and finite winners across seeded simulations.
- Privacy/protocol: serialize per-player snapshots and prove other hands, undealt cards, future burnout positions and tokens cannot appear; reject spoofed actors, unauthorized hosts, stale/out-of-order/duplicate/replayed commands, protocol mismatch, malformed/oversized payloads and admission attempts; resume restores only the proper seat.
- Transport: two independently constructed identities, correct full pin connects, wrong pin fails closed, messages remain ordered/framed, invalid/oversized frames terminate safely, unauthenticated resource use is bounded, disconnect/cancel releases ports. Real Android↔iOS LAN behavior remains a mandatory physical-device release gate if hardware is unavailable here.
- App: practice reaches a winner with the same authority; host/join/lobby/game/round/rematch flows connect; settings persist; background/foreground and back/leave behavior do not leak resources or expose cards; recoverable errors remain actionable.
- Packaging: debug and optimized release Android artifacts, lint, wrapper integrity, macOS iOS build and simulator smoke, signing without committing secrets, no placeholder launcher/assets, licenses/privacy included.
- Production claims: owner signing identities, Play/App Store accounts and physical-device LAN/accessibility/performance checks are external gates. Record exact unverified behavior rather than representing it as completed. Continue all implementation and automated checks that do not depend on those gates.
