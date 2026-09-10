# Independent gameplay and protocol review

Reviewer: gameplay/protocol correctness, independent of domain and session implementation. Reviewed 2026-09-09 against `plan.md`, the rule/contract documents, and the implemented domain/session/controller boundaries. The initial design review is supplemented below by independently authored and executed tests.

## Decision

The implemented Last Light domain, session authority, and reviewed controller boundaries passed the independent gameplay/progression review and targeted JVM suites. The forced final-holder challenge is essential and implemented correctly. Eliminating a player conserves their unplayed cards without revealing them. Controller findings below were fixed and verified. Arithmetic, state exploration, and automated tests do not establish enjoyable pacing or equal practical win rates; human playtesting remains necessary.

## Implementation evidence

The reviewer independently ran these commands after implementation landed, using the coordinator's shared Gradle lock:

| Command | Result | Evidence |
| --- | --- | --- |
| `flock /tmp/partydeck-gradle.lock ./gradlew :core:jvmTest --console=plain` | Passed, 14 tests, zero failures/errors; build 13 seconds. | Eight independently authored tests in `core/src/commonTest/kotlin/dev/partydeck/core/LastLightAdversarialTest.kt`, plus six domain-owner focused tests. Independent suite execution time was 1.056 seconds. |
| `flock /tmp/partydeck-gradle.lock ./gradlew :session:jvmTest --console=plain` | Passed, 27 tests, zero failures/errors; build 4 seconds. | Six independently authored tests in `session/src/commonTest/kotlin/dev/partydeck/session/AuthorityAdversarialTest.kt`, eleven security-reviewer tests, and ten session-owner tests. Gameplay reviewer suite execution time was 0.248 seconds. |
| `flock /tmp/partydeck-gradle.lock ./gradlew :composeApp:jvmTest --tests '*ControllerAdversarialFlowTest*' --console=plain` | Passed, 8 tests, zero failures/errors; final targeted build 2 seconds. | Independently authored `composeApp/src/commonTest/kotlin/dev/partydeck/app/controller/ControllerAdversarialFlowTest.kt`; suite execution time was 0.418 seconds. |

The core suite completed **240 full matches** across every table size from two through six and both voluntary/compulsory-challenge strategies. After transitions it checked all 30 card occurrences, rank counts, hand ownership, recipient action availability, fuse persistence, correct challenge liability, clockwise opener rotation, old-round ID rejection, and a unique winner within the proved bounds. Separate cases cover malformed rosters before entropy use, hostile selections, eliminated-opener/nonempty-challenger card retirement, caller collection mutation, and two identically seeded engines remaining identical despite rejected-command/view-query noise.

The session suite completed **20 full matches through authenticated intents and public views**, across every supported table size. It independently checked recipient addressing, revision increments, challenge evidence, duplicate receipts with fresh snapshots, stale-action counter consumption, resume counter recovery, late disconnect no-ops, eliminated-host continuation, disconnected eliminated guests, a disconnected empty-hand claimant blocking the compulsory challenge, and leave/rematch replay/readiness behavior.

The controller tests use virtual time, actual protocol codecs, valid domain-generated private views, and a transport whose deliveries and blocked writes are controlled independently. They verify both receipt/snapshot arrival orders, rejection of unrelated receipts and stale views, command-counter protection against repeated welcomes, wrong-room/seat rejection with actionable errors, cancellation closing the correct link, no retries in background, authenticated resume without replaying an unacknowledged move, bounded missing-acknowledgement recovery, terminal private-card purge, immediate host pause before a rejected socket finishes flushing, and old-session cleanup isolation from a replacement practice session.

These results exercise common Kotlin code on the JVM. Real TLS controller integration, native iOS execution, cross-device transport, human balance/pacing, and actual device performance have separate qualification owners/evidence. No outstanding gameplay or controller-boundary defect remained after this review's fixes and targeted checks.

## Controller findings resolved during implementation

| Finding | Resolution and independent evidence |
| --- | --- |
| An admitted peer rejected by the protocol remained marked connected until its response/socket flush completed. | Authority disconnect now occurs inside the serialized dispatch immediately. A regression test holds the socket writer blocked and confirms that the host has already paused play and marked the guest disconnected. Finishing the flush does not repeat the revision change. |
| `openLink` captured the timeout child Job as link owner, while cancellation cleanup compared it against the outer connection-loop Job. | The outer owner is captured before nested timeouts and passed into link construction. The background-cancellation test confirms the old link closes, queued frames cannot replace the view, no retry occurs while backgrounded, and cleanup does not close the replacement link. Kotlin 1.11 source confirms that `withTimeoutOrNull` creates a separate child Job. |
| Explicit `SessionEnded` retained the previous game and private hand in an ENDED session. | Terminal handling now clears game/private hand, paused seats, controls, and credentials. Tests cover both an acknowledged Leave without a final snapshot and a host-ended pending move; later queued snapshots cannot resurrect the hand. |
| Wrong-room or wrong-seat snapshots on an established link disconnected terminally without publishing an error/recovery. | The initial independent test reproduced a null issue after disconnection. Terminal `failLink` now reports the reason with recovery; both mismatch cases pass, preserve the last accepted private view, and stop retries. |
| A failed asynchronous Leave from a discarded session could publish its error into a newly started session. | Cleanup reporting now checks the departing session generation. A regression starts practice before the old Leave fails and verifies that neither a late old private snapshot nor its error can overwrite the new session. |

## Discovery and reconnect follow-up

The bounded review of `ClientSessionRuntime.kt` and `ClientDiscoveryFlowTest.kt` accepted discovery cleanup, cancellation, endpoint selection, and deadlines. Direct connection can succeed independently of discovery startup. Fallback requires an exact service-name match and a transport availability, timeout, or I/O failure; authentication and permission failures do not switch endpoints. Every attempt retains the invitation's original full certificate pin and admission/resume identity. Discovery's five-second matching wait remains inside the eight-second attempt deadline and the ten-second initial or thirty-second resume batch. Serialized connection-loop lifetimes and noncancellable final cleanup prevent old browsing cleanup from interfering with a replacement loop. The native boundary requires prompt-return methods; adapter stop does not wait for native completion.

One finding was fixed: permission denial during an admitted client's reconnect continued the automatic retry batch. The batch now ends immediately while retaining the seat credentials for explicit Retry after permission restoration. The new regression checks disconnected state, permission recovery, disabled actions, preserved session view, stopped browsing, no additional automatic attempts over sixty virtual seconds, and successful explicit resume with the original token and certificate pin. Public controller `setBackgrounded` controls transport suspension; `setForeground` controls interaction, privacy, and audio so an iOS permission alert does not cancel Join merely by making the app inactive.

The controller owner executed the focused `ClientDiscoveryFlowTest` class under the shared Gradle lock. This reviewer independently inspected the production change, regression, and resulting XML: **8 tests, 0 failures, 0 errors, 0 skipped**, suite time 0.258 seconds. `git diff --check` passed. No Gradle run was launched by this reviewer for this follow-up. No finding remains open within this review scope; native and physical-device qualification remain separate evidence.

## Rules-to-practice navigation follow-up, 2026-09-10

**Accepted for controller behavior.** The Rules screen's practice action reaches `startPractice` when no session exists; its live-session action uses Back to return to the current table. The fix explicitly selects `SESSION` after attaching practice. The existing start guard still prevents replacement of a live session, and the snapshot collector still preserves an open Rules or Settings overlay during authority updates.

This reviewer inspected the owner's failing regression (`expected SESSION, actual HOW_TO`) and subsequent nine-test passing controller result, then independently executed only `rulesPracticeOpensTheTablePreservesLiveRulesAndLeavesCleanly` under the shared Gradle lock. **One test passed, zero failures/errors/skips**, suite time 0.250 seconds. The regression starts a real practice match from Rules, receives an actual bot/authority revision while Rules remains open, verifies duplicate start preserves session identity, then checks Back, leave confirmation and clean Home after sixty seconds of virtual time.

```sh
flock /tmp/partydeck-gradle.lock ./gradlew :composeApp:jvmTest \
  --tests '*PartyDeckControllerTest.rulesPracticeOpensTheTablePreservesLiveRulesAndLeavesCleanly*' \
  --console=plain
```

Gradle exited zero. Preserved independent XML: `/tmp/partydeck-rules-practice-review/independent.xml`, SHA-256 `3115972dbce7a75058dbb931c1fd084db7282ffe5aa214e17c289331cac492bb`. Owner red/green evidence remains at `/tmp/partydeck-rules-practice-regression/`. No new test or implementation change was needed from this reviewer. Actual Android CTA/input acceptance remains with its native execution owner.

## Findings and required decisions

| Priority | Finding | Required behavior / status |
| --- | --- | --- |
| High | Skipping empty hands alone would eventually leave no next actor or make a player act against their own claim. | **Implemented and independently tested:** when exactly one surviving player holds cards, that player must challenge the latest different author. Reject Play before removing any cards. |
| High | Eliminating a challenger who still has cards can silently lose cards if the implementation just clears their hand. It can also accidentally reveal their remaining hand if all removed cards are reused as the public reveal. | **Implemented and independently tested:** remaining cards move into hidden `discardedCards` before clearing the hand. The pending play references cards already in that zone; it is not a fourth zone. All 30 occurrences remain across hands, discards, and undealt cards. Public reveal contains only the challenged selection. |
| High | A duplicate request could apply a second penalty or consume a fresh shuffle. A cached old snapshot could also roll a client back after later actions. | **Authority and controller behavior independently tested:** cache receipts only, send a fresh current view separately, retain replay protection after cache eviction, and accept only the current room/recipient with nondecreasing view revisions. A receipt alone does not release a pending action before its revision is visible. |
| High | A reconnecting process may restart its command counter; an old connection may still have queued work. | **Authority and controller behavior independently tested:** resume restores the next command ID from the retained high-water mark and revokes the old peer. Late disconnect does not affect its replacement; old link frames and cleanup cannot rewrite a replacement session. |
| High | An eliminated host could leave everyone stuck on the result screen if host permissions were tied to an active game seat. | **Independently tested through public session intents:** host permissions survive elimination; guests still cannot advance. A disconnected eliminated guest does not prevent remaining players from continuing. |
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

Tests use the finalized public domain/protocol APIs in separately allocated files. They construct legal sequences or independently check invariants, rather than restate reducer branches. The matrix below records the important acceptance behavior, including areas exercised by the implementation and security-review owners' complementary tests.

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
5. [Kotlin coroutines — runTest](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-test/kotlinx.coroutines.test/run-test.html), [advanceTimeBy](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-test/kotlinx.coroutines.test/advance-time-by.html), and [runCurrent](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-test/kotlinx.coroutines.test/run-current.html). Verify common coroutine test usage, automatic background-scope cancellation, and virtual-time scheduling. [Pinned kotlinx.coroutines 1.11.0 timeout implementation](https://github.com/Kotlin/kotlinx.coroutines/blob/1.11.0/kotlinx-coroutines-core/common/src/Timeout.kt) explicitly creates a lexically scoped child coroutine/new Job, supporting the connection-owner finding.

The probability calculations and progression proof above are derived from PartyDeck's proposed rules. No unverified external game behavior or library API is needed for them.
