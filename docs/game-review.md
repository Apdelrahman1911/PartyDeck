# Independent gameplay and protocol review

Reviewer: gameplay/protocol correctness, independent of domain and session implementation. Reviewed 2026-09-09 against `plan.md`, `docs/game-rules.md`, and `docs/research/game-design.md`. This is initially a design review; implementation and automated-test results will be added after the module contracts are frozen.

## Decision

The proposed Last Light rules are implementable and have a finite progression bound. The forced final-holder challenge is essential, and the written rules now specify it correctly. The rule design is ready to implement with the resolved card-accounting decision below and the listed domain/session acceptance checks. Arithmetic and state exploration do not establish enjoyable pacing or equal practical win rates; human playtesting remains necessary.

## Findings and required decisions

| Priority | Finding | Required behavior / status |
| --- | --- | --- |
| High | Skipping empty hands alone would eventually leave no next actor or make a player act against their own claim. | **Resolved in the proposed rules:** when exactly one surviving player holds cards, that player must challenge the latest different author. Reject Play before removing any cards. |
| High | Eliminating a challenger who still has cards can silently lose cards if the implementation just clears their hand. It can also accidentally reveal their remaining hand if all removed cards are reused as the public reveal. | **Resolved by agreement with domain owner:** move remaining cards into hidden `discardedCards` before clearing the hand. The pending play references cards already in that zone; it is not a fourth zone. Preserve all 30 occurrences across hands, discards, and undealt cards. Public reveal contains only the challenged selection. |
| High | A duplicate request could apply a second penalty or consume a fresh shuffle. A cached old snapshot could also roll a client back after later actions. | Session owner agreed to cache receipts only, send a fresh current view separately, retain replay protection after cache eviction, and require session identity plus monotonically applied snapshot revisions. Verify independently. |
| High | A reconnecting process may restart its command counter; an old connection may still have queued work. | Session owner agreed that resume restores the next command ID from the authority's retained high-water mark, revokes the old peer, and shares one serialized gate with command application and presence changes. Verify independently. |
| High | An eliminated host could leave everyone stuck on the result screen if host permissions were tied to an active game seat. | Domain has no acting-player requirement for round advancement. Session owner agreed that host permissions survive elimination. Test this explicitly. |
| Medium | Hidden gameplay randomness must remain independent of bots, retries, animation, and reconnect. | Burnout thresholds are drawn once at match start. Challenge consumes no randomness. A new round draws its rank/deck only after validation. Bot randomness is a separate source. Rejections consume no entropy. |
| Medium | A technically valid multiplayer session can stop progressing when a required player disconnects or refuses to act. | The documented rule-level guarantee is finite accepted actions, not finite elapsed time. Pause visibly, allow authenticated resume, and provide explicit session termination. Do not silently skip, reroll, auto-penalize, or fabricate a winner. |

## Progression proof

Let `N` be the number of surviving players at a round's start, with `2 <= N <= 6`. Every survivor starts with five cards. Let `H` be the total number of cards still in surviving hands and `K` the number of nonempty surviving hands.

1. Initially `H = 5N`, `K = N`, and there is no claim, so the opener must play.
2. Every accepted Play requires `K >= 2` and removes one to three distinct owned cards. Therefore `H` strictly decreases, at least one different player still holds cards, and the following actor exists.
3. The following actor is selected clockwise among surviving nonempty hands. It differs from the new claim's author. Emptying a hand does not remove that author's pending liability.
4. If `K` becomes one, the remaining holder must challenge and cannot play. Therefore an all-empty state and a self-challenge are unreachable.
5. A voluntary or forced Challenge penalizes exactly one of two different surviving players and ends the round. Since `H >= 1` before that challenge, a round contains at most `5N - 1` accepted plays, followed by one challenge.

For a match, each player's fixed burnout threshold is at most six. Eliminated players have each received at most six penalties; the eventual sole survivor has received at most five. Thus at most `6N_initial - 1` challenges occur before a unique winner. The bound is 11 challenges at two players and 35 at six players. Only one player can be eliminated per challenge, so zero survivors are unreachable from a valid state. Result-screen continuations, disconnected sessions, and players who decline to act are outside the accepted-gameplay-action bound.

An independent Python state exploration enumerated every reachable hand-count/current-actor/latest-author state reachable by choosing all legal play sizes before challenging. It asserted a nonempty current hand, a different latest author, an available next actor after every Play, and an existing challenge target at compulsory states:

| Players | Reachable states | Legal Play edges | Compulsory-challenge states |
| ---: | ---: | ---: | ---: |
| 2 | 36 | 70 | 7 |
| 3 | 224 | 477 | 18 |
| 4 | 1,122 | 2,488 | 34 |
| 5 | 5,150 | 11,613 | 55 |
| 6 | 22,584 | 51,274 | 81 |

No invariant failed. This validates the proposed turn model, not the future Kotlin implementation. Eliminated seats can be removed from this round-local topology because their relative surviving clockwise order is preserved; concrete implementation tests must still cover holes in seat order and opener elimination.

## Fairness and information boundaries

The deck treats the three ordinary ranks symmetrically. For any required rank, 12 of 30 cards match, including Wilds. A uniformly dealt five-card hand contains an expected two matching cards. Its probability of containing none is `C(18,5) / C(30,5) = 0.060123784`, about 6%. These are direct combinatorial calculations, independent of the number of players, when each hand is a uniform five-card sample. Undealt cards remain unknown at smaller tables.

A uniformly preselected burnout threshold from one through six gives the next penalty conditional risk `1 / (6 - usedLights)` for a surviving player. The threshold must stay fixed; a new constant one-in-six roll after every penalty would remove both escalation and the finite bound. Public used-light counts communicate the changing risk without exposing future thresholds.

Randomizing the first opener and rotating thereafter avoids always assigning the opener role to the host or challenge loser. It does not prove that seating has no strategic effect. Two-player forced challenges, six-player card counting, the incentive to shed cards quickly, spectator downtime, and the length of the reveal/fuse presentation need human playtesting. A three-card selection must not provide extra animation time or a different failure opportunity compared with another legal selection.

The host process is the trusted authority and necessarily holds every hand and burnout threshold. Privacy means that other clients, spectators, public messages, and ordinary UI/bot inputs do not receive that state; it is not protection against a modified malicious host. The projection must have a separate public latest-claim type containing only player and count. Do not reuse the private pending-play type with its card list. A challenged play alone becomes public; earlier accepted discards, the deck remainder, eliminated unplayed cards, RNG state, and future burnout thresholds remain absent.

## Independent test contract

Tests will use the finalized public domain/protocol APIs in separately allocated files. They should construct legal sequences or independently check invariants, rather than restate reducer branches.

### Domain properties and adversarial examples

- For every supported table size and many deterministic entropy streams, all survivors begin each round with five cards; all 30 occurrences occupy exactly one hand, hidden-discard/retired zone, or undealt zone. Card IDs are unique, do not encode rank, and cannot refer to the previous round.
- Drive complete legal matches with both frequent voluntary challenges and delayed compulsory challenges. Check turn legality, a different pending author, no all-empty active state, monotonic fuse counts, correct challenge loser, a unique winner, and the `6N - 1` penalty bound.
- Reject zero/four-card selections, repeated IDs, another player's IDs, old-round IDs, wrong/unknown/eliminated actors, initial challenges, and all ordinary actions outside PLAYING. Compare the entire authority state and a counting entropy source before/after rejection.
- Cover all-Wild truth, matching-rank-plus-Wild truth, and one mismatching rank in a multi-card selection. Challenge checks the latest selection only, independently of older hidden discards.
- Force the final-holder situation at two players and with several empty/eliminated seats. Attempt an illegal Play, then challenge the empty-handed latest author. Cover each direction of penalty ownership.
- Eliminate a nonempty challenger. Their leftover cards remain hidden and conserved; only challenged cards appear in the outcome. Eliminate the opener and verify the next surviving clockwise opener.
- Give players thresholds at both endpoints and a late threshold. Check exact burnout, no threshold rerolls, persistent exposure across redeals, no dealing after victory, and no repeated penalty on result-screen/replayed actions.
- Check every recipient and an unknown/spectator view against an independent allowlist of visible information. Check private ownership and actual serialized wire fields as well as ordinary object projections.
- Mutate caller-owned roster or action-selection collections after use. Prior accepted states and later projections must not change.

### Session and protocol adversaries

- Only the authenticated current peer supplies actor identity. A body cannot nominate another player or grant host permission. Normal player requests cannot start, advance, kick, or end the session through a forged intent.
- For a fixed player, replay an accepted request, reuse its ID with a changed body, replay it after cache eviction, send a stale revision, and send the same numeric ID from another authenticated seat. Exactly the intended first command can apply; no stale/replayed path consumes entropy.
- Resume with the correct credential, a wrong credential, and a credential for a different seat. The original channel loses authority immediately; reconnect restores only that player's current private hand and command-counter position.
- Deliver old-session and out-of-order snapshots. Previously accepted game state must not regress, even when an action receipt arrives after later snapshots.
- Disconnect during a playable turn, a compulsory challenge, a result screen, and after elimination. Pause/continue behavior matches the chosen session policy. An eliminated connected host can advance a round. Host loss ends the session without leaking hidden authority or claiming a rules-level win.
- Reject unsupported protocol versions, unknown/malformed intent types, invalid ID/revision values, oversized selections, and excessive payloads at the appropriate boundary. Failures do not crash or partially mutate the authority.

## Verified sources

Retrieved directly on 2026-09-09:

1. [Bicycle — I Doubt It](https://bicyclecards.com/how-to-play/i-doubt-it). The card publisher documents face-down claimed ranks, truthful/false challenge reversal, and a last-card play remaining subject to challenge. This supports the interaction and final-claim liability, not PartyDeck's custom deck, penalty, or eligible-challenger policy.
2. [Pagat — Cheat / I Doubt It](https://www.pagat.com/beating/cheat.html). A specialist rules reference independently describes challenging the most recent play, a false claim when any selected card disagrees, and surviving a challenge against the final play. It explicitly distinguishes a variant that keeps one rank until challenged. This is contextual comparison, not an official PartyDeck rule source.
3. [Kotlin — Random API](https://kotlinlang.org/api/core/kotlin-stdlib/kotlin.random/-random/) and [seeded Random factory](https://kotlinlang.org/api/core/kotlin-stdlib/kotlin.random/-random.html). Confirm a common abstract random-generator type and bounded integer APIs suitable for injection. The seeded factory explicitly limits sequence repeatability to the same Kotlin runtime version and states that its JVM generator is not thread-safe. No cryptographic-security guarantee is inferred. Tests use the pinned runtime and authority operations must be serialized.
4. [OWASP — WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html). Requires authorization for each message, validation and message limits, and replay protection. These support the protocol acceptance checks; they do not prescribe PartyDeck's exact command-counter or snapshot design.

The probability calculations and progression proof above are derived from PartyDeck's proposed rules. No unverified external game behavior or library API is needed for them.
