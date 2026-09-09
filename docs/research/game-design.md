# Game domain research and design record

Checked on 2026-09-09. Scope: the initial bluffing game, host authority, immutable domain state, and meaningful rule verification. The coordinator froze module `:core`, package `dev.partydeck.core`, and the public contract in [contracts/game-domain.md](../contracts/game-domain.md).

## Primary-source findings

| Source | Verified finding | Consequence for PartyDeck |
| --- | --- | --- |
| [Bicycle — I Doubt It](https://bicyclecards.com/how-to-play/i-doubt-it) | Players place face-down cards and claim a rank. A truthful claim penalizes the doubter; a false claim penalizes the claimant. Its last-card win still has to survive a challenge. | Preserve the clear truth/bluff reversal and ensure emptying a hand does not bypass the pending challenge. PartyDeck specifies a different round, deck, penalty, and victory flow. |
| [Curve Animation — Liar's Bar, developer Steam page](https://store.steampowered.com/app/3097560/Liars_Bar/) | Describes face-down cards matching a table value, bluff calls, random elimination penalties, and cards resetting after a penalty. | Adopt only this general interaction as requested. Design all missing edge cases explicitly; do not present third-party folklore as verified official rules. |
| [Kotlin — Random class](https://kotlinlang.org/api/core/kotlin-stdlib/kotlin.random/-random/) | `kotlin.random.Random` is an abstract random-generator type available in common Kotlin; common APIs include `nextInt`. | Inject a host-owned `Random`; tests can supply a seeded or scripted implementation without platform APIs or a dependency. |
| [Kotlin — seeded Random factory](https://kotlinlang.org/api/core/kotlin-stdlib/kotlin.random/-random.html) | `Random(seed: Int/Long)` is repeatable for the same Kotlin runtime version. Future runtimes may change its sequence. The returned JVM generator is not thread-safe. | Deterministic tests are runtime-local. Serialize all authority operations. Never promise persistent cross-version replay from a seed alone, or run gameplay entropy concurrently. |
| [Kotlin — Collections overview](https://kotlinlang.org/docs/collections-overview.html) | `List` is a read-only interface; mutable objects can still implement it. `val` does not make a mutable collection immutable. | Engine-produced authority collections must snapshot inputs and expose read-only snapshots, not caller-owned mutable backing lists. |
| [Kotlin — AbstractList](https://kotlinlang.org/api/core/kotlin-stdlib/kotlin.collections/-abstract-list/) | Common `AbstractList` provides the skeletal implementation of a read-only list through `size` and `get`. | An internal snapshot list can copy its input and expose a read-only implementation without an additional collection dependency. |
| [Kotlin — ConsistentCopyVisibility](https://kotlinlang.org/api/core/kotlin-stdlib/kotlin/-consistent-copy-visibility/) | The annotation makes generated data-class `copy` visibility match constructor visibility. | Explicitly apply it to host-only state types with internal constructors so external modules cannot use generated `copy` as a public state factory. |
| [Kotlin — Serialization](https://kotlinlang.org/docs/serialization.html) | `@Serializable` generates support for Kotlin models and supports standard collections, with multiplatform runtime libraries. | Annotate only intentionally public model types; never provide a serializer for the full authority state. |
| [Kotlin — kotlin.test](https://kotlinlang.org/api/core/kotlin-test/kotlin.test/) | Common test assertions include stable `assertEquals`, `assertTrue`, `assertFalse`, `assertNotNull`, and `assertIs` APIs. | Behavior tests use the platform-independent Kotlin test library already configured by the project. No testing library or experimental assertion overload is added. |

No external card art, text passages, sounds, character designs, logos, or implementation were imported. The public rules are written for PartyDeck in [game-rules.md](../game-rules.md).

## Chosen rule structure and tradeoffs

The initial game is **Last Light**. A 30-card deck supports all six five-card hands without replenishing during a round. Nine cards of each ordinary rank and three Wild cards make 12 of 30 cards truthful for any given table rank. Every rank has the same treatment. A five-card opening hand therefore has an expected two truthful cards. The chance of no truthful card is `C(18, 5) / C(30, 5)`, about six percent. These are deck arithmetic, not a playtest result.

Allowing up to three cards creates a visible tradeoff: shedding faster can require mixing truthful cards with a bluff, while a one-card play is easier to support with a truthful card. A new player needs to learn only Play and Challenge. There are no extra powers, changing bid quantities, resource purchases, or hidden exceptions in version 1.

Skipping accepted empty hands gives players a useful round objective without confusing it with the match win. Requiring the final nonempty hand to challenge prevents the finite deck from producing an all-empty state or asking a player to challenge their own play. This also gives a two-player round the same action vocabulary as a six-player round.

Six persistent fuse steps preserve escalating tension. The host preselects one hidden burnout step uniformly from one to six per player. Conditioned on survival, the next failure probability rises from one in six to certainty. This prevents infinitely surviving fixed-probability penalties. It bounds a six-player match to 35 resolved challenges, while animation uses original stage-light symbols and non-graphic burnout effects.

Every challenge produces one atomic rule outcome and ends the round. A distinct result phase gives all devices time to present the reveal without letting a renderer, sound cue, or timer decide the winner. Host continuation explicitly redeals. Opening turns rotate across survivors, separately from penalty ownership, to distribute the opener role.

## Implemented domain boundary

The domain uses common Kotlin and the standard library, plus the project's pinned serialization annotations on safe public models. It owns card/rule types, authoritative game state, validation, the reducer, and safe per-viewer projections. It contains no networking, persistence, coroutines, Compose, Android, iOS, or Godot APIs.

Core type outline (the exact accepted contract is in [contracts/game-domain.md](../contracts/game-domain.md)):

```kotlin
enum class CardRank { CROWN, MOON, STAR, WILD }
enum class GamePhase { PLAYING, ROUND_ENDED, FINISHED }

data class PlayerIdentity(val id: String, val displayName: String)
data class Card(val id: String, val rank: CardRank)

sealed interface GameAction {
    data class Play(val playerId: String, val cardIds: List<String>) : GameAction
    data class Challenge(val playerId: String) : GameAction
}

sealed interface GameDecision {
    data class Applied(val state: GameState) : GameDecision
    data class Rejected(val reason: GameRejection) : GameDecision
}

class LastLightEngine(private val random: Random) {
    fun start(players: List<PlayerIdentity>): GameState
    fun apply(state: GameState, action: GameAction): GameDecision
    fun advanceRound(state: GameState): GameDecision
    fun viewFor(state: GameState, viewerId: String?): GameView
}
```

`GameState` contains the complete private authority state, including secret burnout steps. Engine-produced collection values use defensive read-only snapshots, and reducers return fresh states without mutating earlier states or caller-owned selections. State constructors and generated copy methods are internal to `:core`. Start rejects malformed rosters as a programming/configuration error; player actions use typed rejection values. Validation always precedes random draws. A rejected action neither changes game state nor consumes gameplay entropy.

`GameView` includes public player rows, only the viewer's own cards, the required rank, round number, active actor, latest claim size/owner, forced-challenge status, phase, the public round outcome, and winner. The session wraps this serializable safe view in its separately versioned protocol DTOs. `GameState` is never annotated as a public wire payload. The hidden latest-play type is not reused for the public claim: doing so would risk serializing its cards later.

Card identifiers identify a card occurrence within a round and do not encode its rank. New rounds use a fresh namespace; combined with expected-revision validation, a stale card selection cannot refer to a newly dealt card. Internal exact identifiers and hidden cards are absent from public pending claims.

## Authority and entropy contract

The host owns the only game RNG and engine invocation sequence. Live authority must inject a platform-CSPRNG-backed implementation of `Random`; merely seeding Kotlin's deterministic generator with a secure seed is insufficient to claim cryptographic security. The engine has no default source, and neither `Random.Default` nor `Random(seed)` is assumed cryptographically secure. Bot policy randomness is separate from game randomness so bot deliberation cannot perturb a shuffle or penalty outcome. The security reviewer requested this integration requirement without changing the domain API.

Match start draws burnout steps, the opening seat, round rank, and shuffled deck in a documented deterministic order. Future penalties merely advance preselected fuse steps and consume no new entropy. A next-round transition draws only the next rank and deck. Tests that script entropy target `nextInt(until)` or provide known seeded sequences under the pinned runtime; they do not depend on platform-specific RNG implementation internals.

The session layer authenticates a device to a player ID and constructs domain actions from that binding. It validates request revision, handles duplicate/replayed action IDs, serializes calls, and invokes next-round transitions only through the host role. It also owns disconnect pauses and reconnection. Game state does not automatically forfeit or skip a disconnected player; a session ended by host loss is not falsely shown as a rules-level victory.

Long-term persistence or authority migration would require a versioned authority snapshot and a stable entropy/replay specification. That is separate from reconnecting a client to the current in-memory host and is not implied by seeded test support.

## Independent test acceptance

The test owner should work from [the rule acceptance cases](../game-rules.md#acceptance-cases), not copy implementation branches into tests. High-value examples include all-Wild truth; a single incorrect card among several matching cards; invalid commands leaving an injected counting RNG untouched; emptying a hand immediately followed by a successful challenge; the two-player forced challenge; eliminating an opener before rotating seats; round-specific stale card IDs; and field-level inspection of recipient projections.

State conservation and multiple seeded legal-match simulations should supplement small examples. They must show that no physical card duplicates across zones, each live turn has a legal action, challenge losers are correct, and matches reach a unique winner within the mathematical penalty bound. Performance work should focus on bounded, infrequent turn transitions rather than micro-optimizing a maximum of six hands of five cards.

## Validation evidence and remaining checks

On 2026-09-09, `:core:compileKotlinJvm` completed successfully. The first focused run, `flock /tmp/partydeck-gradle.lock ./gradlew :core:jvmTest`, completed successfully with six tests, zero failures, zero errors, and no skipped tests in `LastLightEngineTest`. These cover all-Wild truth, mixed matching/Wild truth, one mismatching card, challenging only the latest play, persistent penalties after redeal, and a unique winner after burnout. The bootstrap arithmetic test was removed once these behavioral tests were available.

The independent gameplay reviewer subsequently added eight tests in `LastLightAdversarialTest` and reran the same locked command successfully. The resulting suite contains **14 tests, zero failures, zero errors, and no skipped tests**. It includes 240 complete legal matches across every supported table size with early and delayed challenges, plus additional paired deterministic histories with rejected commands and repeated views injected as noise. Checks preserve all 30 cards, ensure compulsory challenges remain possible, verify penalty/round/winner invariants, reject stale/unowned selections, keep private hands confined to their recipients, and prevent caller lists or recipient views from mutating authority state. No domain defect was found in that review; details are maintained independently in [game-review.md](../game-review.md).

- Integrate the implemented frozen API with session, UI, and controller owners.
- Run the same common tests on iOS through macOS CI when available; JVM success is not iOS execution evidence.
- Complete integrated wire-snapshot security checks in the session review; object-level projection privacy and rejected-action entropy checks already pass in the independent domain suite.
- Playtest two-, four-, and six-player pacing. The arithmetic supports a starting design but does not establish enjoyment, bluff frequency, or ideal animation lengths.
