# Session authority and wire protocol

Research and frozen contract, 2026-09-09. Owner: session/protocol implementation stream. The coordinator approved `:session`, package `dev.partydeck.session`, depending on `:core`, package `dev.partydeck.core`, and stable kotlinx.serialization 1.11.0. Minimal model/API files are now under `session/src/commonMain`.

## Sources checked

- [Kotlin serialization documentation](https://kotlinlang.org/docs/serialization.html): serialization is available in common Kotlin through the compiler plugin and runtime libraries. Use the project's selected stable compiler/plugin version together.
- [kotlinx.serialization 1.11.0 release](https://github.com/Kotlin/kotlinx.serialization/releases/tag/v1.11.0): the stable release is based on Kotlin 2.3.20. The coordinator owns the final dependency matrix. The GitHub `releases/latest` endpoint returned `v1.12.0-RC` with `prerelease=false`; do not treat that metadata as proof of stability.
- [Stable sealed-polymorphism guide](https://github.com/Kotlin/kotlinx.serialization/blob/v1.11.0/docs/polymorphism.md), [stable JSON guide](https://github.com/Kotlin/kotlinx.serialization/blob/v1.11.0/docs/json.md), and [stable configuration source](https://github.com/Kotlin/kotlinx.serialization/blob/v1.11.0/formats/json/commonMain/src/kotlinx/serialization/json/JsonConfiguration.kt): sealed messages can have explicit `@SerialName` values; the JSON discriminator, strict parsing, unknown-key policy, and encoding defaults are configurable. Stable 1.11.0 does not expose the newer `maxNestingDepth` setting shown by current online RC API documentation.
- [OWASP session management guidance](https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/Session_Management_Cheat_Sheet.md): custom session credentials should use a CSPRNG with at least 128 bits of entropy; encrypted transport protects credentials in transit. This supports opaque, host-generated reconnect credentials. Cookie/browser-specific advice is not being applied to this native protocol.

## Ownership and boundaries

`:session` depends on the pure game module and kotlinx.serialization. It contains a synchronous, single-owner host authority, typed protocol messages, bounded codecs, and viewer-safe session projections. It has no sockets, platform APIs, persistence, coroutines, timers, UI, or cryptographic implementation.

The transport establishes an encrypted channel with strict host certificate pinning, assigns its connection identifier, bounds inbound frames, and closes revoked connections. It does not authenticate an individual client with a client certificate. Session admission and resume credentials establish player identity. The controller serializes all authority calls and adapts deliveries to transport and visible state. The domain owns all card/rule/penalty decisions and host randomness. Authority state is never serialized for clients.

Proposed shape:

```kotlin
data class SessionPeer(val connectionId: String)

class HostAuthority(/* session configuration, host peer/name, game engine, secret source */) {
    fun initialDispatch(): SessionDispatch
    fun handle(peer: SessionPeer, message: ClientMessage): SessionDispatch
    fun disconnect(peer: SessionPeer): SessionDispatch
    fun viewFor(peer: SessionPeer): SessionView?
}

data class SessionDispatch(
    val deliveries: List<Delivery>,
    val closeConnections: List<String>,
)
```

The factory creates the host seat and its first welcome/snapshot. Host-only authority checks compare immutable seat identity, independently of whether the host's game seat has been eliminated. All joins, resumes, revocations, commands, presence changes, and game applications run through the same serial ownership gate.

## Wire format and admission

Use bounded UTF-8 JSON with an explicit protocol version (`1`), session identifier, stable discriminator names, and a sealed set of messages. Require the version on received messages and reject unsupported versions. Reject unknown message types/fields, duplicate decoded object keys (including escaped aliases), malformed JSON, invalid UTF-8, oversized payloads, and excessive structural nesting before deserialization. Return a fixed, non-sensitive error code; do not log raw input or parser exceptions that may contain cards or credentials.

The exact frame limit is shared with transport; the proposed ceiling is 64 KiB, far above a six-player turn snapshot. The codec independently enforces it. A small bounded preflight for JSON nesting avoids relying on a release-candidate-only serialization setting.

Client messages:

- `Join(version, sessionId, admissionSecret, displayName)`: validates the room's invitation credential, is valid only in the lobby, and assigns a non-secret player ID. Repeated joins on the same admitted connection do not add a second seat.
- `Resume(version, sessionId, playerId, reconnectToken)`: validates the host-issued individual credential, then atomically replaces the old connection binding. No other client can identify an actor by naming that player's ID.
- `Command(version, sessionId, commandId, expectedRevision, intent)`: requires an admitted current connection. `commandId` is a positive, monotonically increasing integer scoped to that seat for the lifetime of the session.

Server messages:

- `Welcome`: recipient player ID, reconnect token, next command ID, and current per-recipient snapshot. It is sent only over that admitted authenticated channel.
- `Snapshot`: current per-recipient session view, including protocol/session IDs and revision.
- `Receipt`: command ID, accepted/rejected result, revision at processing, and a structured reason when rejected. A receipt is separate from current snapshot state.
- `AdmissionRejected` / `SessionEnded`: structured reason without private state.

Clients use the next command ID returned by welcome after reconnection; the host never resets a seat's replay protection. Controller storage of the token is separate from rendered state. Process restoration is only available if the reconnect credential was retained securely; otherwise the player rejoins a lobby as a new seat.

## Identity, reconnect, and secrets

The transport adapter supplies `SessionPeer`; no peer identity, host privilege, or actor field in a client payload is trusted. The authority maps the current connection binding to a seat before evaluating commands. A stale channel loses that mapping as soon as resume succeeds, so work arriving later on it is rejected.

The host receives a platform-backed secure secret source. `HostSessionConfig` supplies an opaque session ID, 32-byte lowercase-hex admission credential, host name, host peer, and a bounded replay-cache capacity (default 64). `HostAuthority(config, engine, secureToken)` creates reconnect credentials through the injected `secureToken: () -> String`. Credentials contain 32 random bytes encoded as lowercase hex, remain only in memory during the session, and never appear in `SessionView`, logs, discovery advertisements, other players' welcomes, or cached receipts. Tests inject deterministic secrets. The authority checks uniqueness and a bounded format; it cannot establish entropy from a string and must document that requirement on the injected source.

The selected native TLS transport authenticates the host through the invitation's complete certificate fingerprint. The invitation's admission secret authorizes room membership. The reconnect token is the individual seat credential. There is no claimed stable client TLS identity, and a transient connection ID is never treated as a stable identity across reconnects.

Tokens are invalidated when a player leaves or is kicked, or the host ends the session. No host migration or authority-state transfer is implemented. Rotating a token on every reconnect is unnecessary for this in-memory session and can strand clients when a welcome is lost; replacement-channel revocation and a stable secret make retries possible.

## Command and revision semantics

Each accepted state change increments one global session revision. Joining, leaving, readiness, starting, game actions, round progression, presence changes, and connection replacement are state changes. Rejected actions and exact no-ops do not advance it. Revisions are never reset when returning to the lobby.

For an admitted seat, the authority maintains its highest processed command ID and a bounded insertion-ordered cache of recent command envelopes and receipts (proposed 64 entries per seat):

1. A cached exact duplicate returns the original receipt and a fresh current snapshot; it never reapplies the game action or consumes randomness.
2. A cached command ID with different contents is rejected as an ID conflict.
3. Any command ID at or below the high-water mark but no longer cached is rejected as too old. Cache eviction cannot re-enable an old action.
4. A fresh command records its result and advances the high-water mark even if it is rejected for a stale revision or illegal action. The client must use a new command ID to retry with corrected state.
5. A fresh command with an incorrect expected revision is rejected before invoking the domain engine.

The wire/authority boundary rejects oversized fields and collections before retaining any envelope. Command IDs must be positive and less than `Long.MAX_VALUE`, so a recovered next command ID cannot wrap around. Structurally malformed envelopes are not admitted into the command history.

Successful commands produce a receipt to the actor and fresh individually generated views to all connected participants. A rejection supplies only the actor's receipt/current view. Cache receipts contain no hand or token. Snapshot consumers check session ID and accept only nondecreasing revisions; a delayed receipt does not roll state back.

## Lobby and host controls

The host starts ready. Display names are trimmed, bounded, nonempty, and reject control characters. The domain's player capacity is the sole source for minimum and maximum seats. A seat cannot join an active match; spectators are outside this first release.

Intents are `SetReady`, `StartGame`, `PlayCards`, `Challenge`, `AdvanceRound`, `ReturnToLobby`, `KickPlayer`, `Leave`, and `EndSession`. Play/challenge carry no actor ID. The authority adds the authenticated actor when calling the domain.

Start requires a lobby, the minimum player count, connected seats, and all nonhost players ready. Roster changes invalidate other guests' readiness so agreement reflects the current table. Only the host may start, advance a completed round, return to the lobby, kick a player in the lobby, or end the session. Host-only operations remain available after the host's seat is eliminated. A host cannot kick itself.

Returning to the lobby clears match state and guest readiness, retains session identity/replay state, and retains admitted seats and reconnect credentials. Seats that explicitly left the match are removed when the host returns to the lobby. Kicking closes that seat's current connection and destroys its binding, cache, and reconnect credential. Guest leave in the lobby removes its seat; during a match it invalidates the credential and makes the seat unavailable without fabricating a domain forfeit. The host can end the match and return to the lobby.

## Hidden information and interruption behavior

`SessionView` includes the recipient ID, host ID, roster (public IDs/names/readiness/presence), phase, revision, and the domain's viewer-safe `GameView`. It contains only the recipient's hand. Other players expose hand counts, public status, and publicly resolved challenge evidence. Deck order, unrevealed cards, truth of a pending claim, future penalties, and RNG state never leave the authority. The serialized host state type must not be reachable through any server DTO.

Any disconnected noneliminated participant pauses play until reconnect or host action, including a player whose hand is temporarily empty. The domain does not silently skip turns or create penalties. Eliminated seats do not block remaining play. Disconnected lobby seats remain visible and can be removed by the host. No reconnect timeout is invented: the first release keeps them for the lifetime of that in-memory session.

Host loss ends the client session with a recoverable UI route back to the main menu. Local practice uses the same authority and intents over in-memory authenticated peer bindings. Remote players cannot continue independently after host loss.

## Focused acceptance checks

- Ready/start gates, capacity/name validation, host-only controls, and privileges after host elimination.
- Correct actor binding; spoofed IDs and obsolete channels cannot play another seat.
- Reconnect restores only the seat's own hand, revokes the old connection, preserves high-water IDs, and rejects wrong/invalidated credentials.
- Exact duplicates, ID conflicts, cache eviction, stale revisions, rejections, and round advancement never double-apply penalties or randomness.
- Every recipient projection and serialized server message exclude every other private hand, deck state, pending truth, and future penalty state.
- Disconnect/reconnect revisions are monotonic, active-seat interruption is explicit, and host loss ends the session.
- Versioned round trips and rejection of malformed, unknown, oversized, deeply nested, and invalid UTF-8 input.

Implementation waits only for the coordinator's environment smoke test and API/module freeze; no independent product approval is needed for these documented defaults.
