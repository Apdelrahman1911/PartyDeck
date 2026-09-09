# Frozen Last Light domain API

Module: `:core`. Package: `dev.partydeck.core`. Frozen by the coordinator on 2026-09-09. Public model declarations live in `core/src/commonMain/kotlin/dev/partydeck/core/GameModels.kt`; authoritative models, actions, and rejection codes live in `GameAuthority.kt`.

## Dependency boundary

Safe public views, cards, identity types, and enums use the project's pinned `kotlinx.serialization` annotations. Host-only `GameState`, `PlayerState`, `PendingPlay`, `GameAction`, and `GameDecision` deliberately have no serializers. The session wraps `GameView` in its versioned protocol and derives action actors from authenticated peer bindings. Screens and bots receive only `GameView`.

`PlayerId` and `CardId` are type aliases for `String`, not wrapper classes. No consumer should expect a `.value` property.

## Engine

```kotlin
class LastLightEngine(private val random: kotlin.random.Random) {
    fun start(players: List<PlayerIdentity>): GameState
    fun apply(state: GameState, action: GameAction): GameDecision
    fun advanceRound(state: GameState): GameDecision
    fun viewFor(state: GameState, viewerId: PlayerId?): GameView
}
```

The host owns one engine and serializes calls. Live authority injects a platform-CSPRNG-backed `Random` implementation; merely seeding Kotlin's deterministic generator with a secure seed does not make that generator cryptographically secure. The engine has no default RNG. Tests may use a seeded/scripted source, and bots use an independent policy source. `viewFor` never consumes random values. `apply` never consumes random values: truthful/bluff decisions and fuse steps come from authority state. A valid `start` or `advanceRound` is the only operation that consumes entropy. A rejected operation preserves the existing state and random stream.

The draw order is explicit for scripted tests: `start` calls `nextInt(6) + 1` for each seat's burnout step, then `nextInt(playerCount)` for the opener, `nextInt(3)` for the table rank, then Fisher–Yates swaps using bounds 30 down through 2. Every redeal calls `nextInt(3)` and the same 29 shuffle draws. The unshuffled rank list has nine Crown, nine Moon, nine Star, and three Wild entries in that order. Card identifiers are assigned only after shuffling, as `r{roundNumber}-c{shuffledSlot}`.

`start` requires two to six players, unique nonblank IDs of at most 64 characters, and nonblank display names of at most 24 characters. Names and IDs must have no ASCII control characters. Invalid rosters throw `IllegalArgumentException`; these are setup/programming errors, not player-action rejection responses. The session normalizes names before creation; the domain does not silently change identity strings.

`apply` takes either `GameAction.Play(playerId, cardIds)` or `GameAction.Challenge(playerId)`. It returns `GameDecision.Applied(state)` or `GameDecision.Rejected(reason)`. Rejection values are stable typed enum codes, with no secret card details in the response.

`advanceRound` is a host-controlled operation with no player actor. It therefore remains possible after the host's game seat is eliminated. The session checks host permission, expected revision, and request duplication before calling it. It succeeds only in `ROUND_ENDED`; `FINISHED` rejects with `GAME_FINISHED` and any active round rejects with `ROUND_NOT_ENDED`.

## Public view fields

`GameView` has these exact properties:

| Property | Type | Meaning |
| --- | --- | --- |
| `viewerId` | `PlayerId?` | Known recipient seat, or null for an unknown/spectator recipient. |
| `phase` | `GamePhase` | `PLAYING`, `ROUND_ENDED`, or `FINISHED`. |
| `roundNumber` | `Int` | Starts at one and increases on each successful redeal. |
| `tableRank` | `CardRank` | `CROWN`, `MOON`, or `STAR`; never `WILD`. |
| `players` | `List<PlayerView>` | All seats in fixed order, including eliminated seats. |
| `yourHand` | `List<Card>` | Only the known, noneliminated recipient's hand. |
| `turnPlayerId` | `PlayerId?` | The current actor during play; null in result/finished phases. |
| `latestClaim` | `PublicClaim?` | Pending claim owner and count, with no ranks or IDs. |
| `forcedChallenge` | `Boolean` | Global table state: the sole remaining card holder must challenge. False outside active play. |
| `availableActions` | `AvailableActions` | Recipient-specific play/challenge availability; all disabled for other actors and spectators. |
| `roundOutcome` | `RoundOutcome?` | Most recently resolved challenge; may be from a preceding round. Always display its own round number and table rank. |
| `winnerId` | `PlayerId?` | The sole survivor in `FINISHED`; null otherwise. |

`PlayerView` fields: `id`, `displayName`, `handCount`, `penaltyAttempts`, `eliminated`.

`Card` fields: `id`, `rank`; rank is `CardRank.CROWN`, `MOON`, `STAR`, or `WILD`.

`PublicClaim` fields: `playerId`, `cardCount`.

`AvailableActions` fields: `canPlay`, `canChallenge`, `maxPlayableCards`. These describe this recipient only. `maxPlayableCards` is zero when playing is unavailable, otherwise the smaller of the recipient hand count and three. Host continuation permission is a session concern and is not included here.

`RoundOutcome` fields: `roundNumber`, `tableRank`, `claimantId`, `challengerId`, `revealedCards: List<Card>`, `truthful`, `penalizedPlayerId`, `penaltyAttempt`, `burnedOut`. `revealedCards` contains exactly the challenged selection. The loser's other cards are never included, even when they burn out.

## Private authority state and invariants

`GameState` exposes `players`, `phase`, `roundNumber`, `tableRank`, `openerPlayerId`, `turnPlayerId`, `pendingPlay`, `discardedCards`, `undealtCards`, `roundOutcome`, and `winnerId` to trusted host code and domain tests. Its constructors are internal to the module. `PlayerState` holds `identity`, `hand`, `penaltyAttempts`, `burnoutStep`, and `eliminated`.

All 30 current-round cards occupy exactly one physical zone: a hand, the discard pile, or the undealt pile. A `PendingPlay` is evidence referencing cards already in the discard pile. On elimination, all unplayed cards from that player's hand move to the hidden discard pile before the hand is cleared. On redeal, every old zone is replaced by a new full deck and fresh round-scoped identifiers.

Before a legal play, at least two live hands are nonempty. If a play leaves exactly one nonempty hand, that holder can only challenge the different author of the last play. No active state has zero eligible actions for the actor. Secret burnout steps range from one through six; an eliminated player's penalty count equals their burnout step, while a survivor's count is strictly smaller.

Round outcomes persist through a redeal as public history. Pending plays clear on challenge and redeal. The latest claim is therefore null on the round-result screen, whose evidence comes from `roundOutcome`.

## Rules and tests

The normative transitions and behavioral acceptance cases are in [game-rules.md](../game-rules.md). Independent reviewers own meaningful tests outside the implementation files. Primary-source findings and runtime determinism limits are in [research/game-design.md](../research/game-design.md).
