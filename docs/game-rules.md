# Last Light — PartyDeck rules, version 1

Status: approved for the initial PartyDeck implementation on 2026-09-09. These are original PartyDeck rules. They are not a claim to reproduce another game's full rules. The frozen Kotlin API is documented in [contracts/game-domain.md](contracts/game-domain.md).

## Quick instructions

1. Two to six players join. Everyone receives five private cards.
2. The table names a rank: Crown, Moon, or Star. Wild cards always match it.
3. On your turn, place one to three cards face down, claiming they all match the table rank. Or challenge the immediately previous claim.
4. If even one challenged card does not match, its player loses the challenge. If every card matches, the challenger loses.
5. The loser advances their six-light fuse. A safe light keeps them in; a burnout eliminates them. Deal a new round to everyone still in.
6. The last player still in wins.

Empty your hand to sit out the remainder of that round, once your last claim is accepted. When only one player still holds cards, they must challenge the latest claim.

## Table, cards, and dealing

The lobby supplies a fixed clockwise seat order of two to six distinct players. Seat order does not change during a match. An eliminated player's seat remains visible, but that player receives no turns or cards in later rounds.

The deck contains exactly 30 cards:

| Rank | Count | Matches the table |
| --- | ---: | --- |
| Crown | 9 | When the table asks for Crown |
| Moon | 9 | When the table asks for Moon |
| Star | 9 | When the table asks for Star |
| Wild | 3 | Always |

Wild is never selected as the table rank. Suits, numeric values, and card ordering have no meaning.

At match creation, the host selects an initial opening seat uniformly. At the beginning of every round, it independently selects one of the three table ranks uniformly, shuffles the complete 30-card deck, and deals five cards to each surviving player. Deal clockwise, one card per player, beginning with the opening seat and repeating five times. Undealt cards remain hidden and unused for the whole round. Cards are never drawn or replenished during a round.

The same rank may occur in consecutive rounds. The full deck is recreated and reshuffled after every completed challenge. All survivors return to five cards; eliminated players have none. Each round has fresh card identifiers so that an action containing a previous round's card cannot become valid again.

## Playing and accepting a claim

The opener must play; no claim exists to challenge. Later, only the current player may act. An action is one of:

- **Play:** select one, two, or three distinct cards currently in your hand. Place them face down. The claim is automatically “this many of the table rank.” The selection may be truthful, mixed, or entirely a bluff.
- **Challenge:** challenge the latest face-down play by the previous eligible player. Only this play is examined, not earlier discarded cards.

A play accepts the preceding claim permanently and replaces it with the new claim. The played cards leave the player's hand immediately. The public table shows the claimant and card count, without showing the ranks, identifiers, or whether they match. Previous accepted cards remain discarded and hidden until the round ends; they are never revealed merely because a later play is challenged.

Passing, drawing, challenging yourself, challenging an older claim, and challenging out of turn are illegal. A player cannot change the claimed rank, play zero cards, repeat a card identifier, or use another player's card.

## Empty hands and compulsory challenges

Running out of cards does not win the match and does not immediately protect the latest play from challenge. The next eligible player may still challenge that play.

After a play, find the next surviving player clockwise whose hand is nonempty, skipping empty hands and eliminated seats. Players whose emptying claim has been accepted sit out until the next round.

If exactly one survivor still has cards, that player becomes the current player and **must challenge the latest play**. Playing is disabled. This also applies in a two-player match as soon as one player empties their hand. It prevents a player from taking another turn against their own claim and ensures the round cannot reach a state where everyone has empty hands.

Example: Ada plays her last card, leaving Bo with two cards and Cy with none. Bo must challenge Ada. If Ada bluffed, Ada receives the penalty even though her hand is empty. If Ada told the truth, Bo receives it. A fresh round follows either result.

At the start of a round there are at least two nonempty hands. Each accepted play removes at least one card, and the final holder must challenge. Therefore every round reaches a challenge after finitely many accepted plays, provided players take their turns. The session may pause for a missing player; there is no rule-level timer that silently decides for them.

## Challenge and six-light fuse

Reveal all cards in the challenged play to everyone. A claim is truthful only when **every** revealed card either has the required rank or is Wild. A group of only Wild cards is truthful. One mismatching non-Wild card makes the entire claim a bluff.

- Bluff: the claimant receives exactly one fuse penalty.
- Truth: the challenger receives exactly one fuse penalty.

Each player starts the match with zero used lights. The host independently chooses that player's hidden burnout step uniformly from 1 through 6. A penalty increases used lights by one. Before the hidden step, the player survives; at that step, their fuse burns out and they are eliminated. The fuse never resets between rounds and is never rerolled after a safe penalty. Public views show the number of used lights and whether the player is eliminated. They never expose the hidden future burnout step.

This is a fictional, non-graphic stage-light mechanic: original light symbols, a brief spark, and a dimmed player badge. The game uses no firearm, injury, death animation, copied roulette prop, or wager. A burnout means sitting out and spectating the match.

Conditioned on survival, the next penalty's burnout probability is `1 / (6 - usedLights)`. It begins at one in six and reaches certainty after five safe penalties. This probability describes the preselected hidden step; implementations must not incorrectly reroll a constant one-in-six chance.

Every challenge ends the round, even if the loser survives. The authoritative result records the revealed claim, truth/bluff decision, penalized player, new used-light count, and whether the penalty eliminated them. On elimination, any unplayed cards in that player's hand move to the hidden discard pile before the hand is cleared; they are not part of the public reveal. Cards and fuse resolution are decided once by the host; animation merely presents that result.

## Round result, next round, and victory

If exactly one player survives a penalty, the match finishes immediately and names that player as the winner. There is no extra deal or next turn. Since a challenge penalizes only one player and requires at least two survivors, a valid match cannot end in a draw with zero survivors.

Otherwise, the match waits on the round-result screen. The host explicitly starts the next round through the session authority. Ordinary play and challenge actions are rejected while waiting. Repeated continue requests cannot redeal an already active round.

The next opening seat is the next surviving seat clockwise after the previous round's opener, regardless of who lost the challenge. The host deals new hands, selects the new table rank, clears the pending claim, and resumes play. Everyone keeps their fuse progress. The most recent result may remain available as public history while the new round is active, but it must be labeled with its round number.

At most `6 × playerCount - 1` completed challenges can occur before the match ends: each eliminated player can receive at most six penalties, and the eventual winner can survive at most five. For six players, this bound is 35 challenges. This bounds game progress, not elapsed wall-clock time.

## Hidden information and session responsibilities

The domain state held by the host contains all hands, the hidden discard pile, and burnout steps. It is never a wire message or an input to a nonhost game screen or bot.

A recipient-specific projection contains only:

- Public player identities, seat order, hand counts, used lights, and elimination status.
- That recipient's own hand, if the recipient occupies a player seat.
- Round number, table rank, phase, current actor, latest claimant and claim size.
- Whether the current actor must challenge; the recipient's legal action availability.
- Challenged cards after their reveal, the public round outcome, and any winner.

No projection exposes another player's remaining ranks, undealt cards, accepted hidden discards, pending claim ranks, hidden burnout step, or random seed. Eliminated players spectate with no private hand. Unknown recipients receive no private cards.

Connection state does not change game rules. The session authenticates actions to a seat, checks revisions and duplicate action IDs, serializes authority operations, and pauses action processing while a required player is disconnected. Reconnection restores that player's current sanitized view. The initial release does not silently skip disconnected seats, grant an automatic win, or migrate secret authority to a client. Explicit session termination is separate from a rules-level winner.

## Acceptance cases

The domain implementation and independently owned tests must cover these behaviors:

| Area | Required evidence |
| --- | --- |
| Setup | Reject fewer than two, more than six, duplicate identities, or invalid names/IDs; all supported table sizes receive exactly five distinct cards per survivor. |
| Deck | Exactly 9 Crown, 9 Moon, 9 Star, and 3 Wild; a shuffle preserves every card; fresh round identifiers cannot collide with the previous round. |
| Turn validation | Wrong actor, eliminated actor, empty selection, selection over three, duplicate IDs, stale IDs, and unowned IDs are rejected without mutating the original state or consuming randomness. |
| Truth | Required ranks, rank-plus-Wild, and all-Wild plays are truthful; any nonmatching ordinary rank makes the whole claim false. |
| Challenge | No initial challenge; only the latest claim can be challenged; exactly one penalty goes to the correct party; only challenged ranks become public. |
| Empty hands | Emptying a hand remains challengeable; accepted empty-hand seats skip; final holder is forced to challenge, including with two players and separated eliminated seats. |
| Penalty | Safe penalties accumulate; burnout occurs exactly at the preassigned step; eliminated hands are cleared; no reroll or double penalty on a rejected action. |
| Progression | Round result blocks ordinary actions; only next-round transition redeals; opener rotates through survivors; fuse counts persist; all survivors return to five cards. |
| Victory | Exactly one survivor finishes the match; further player actions and redeals are rejected; there are no zero-survivor valid terminal states. |
| Projection | Other hands, pending ranks, undealt cards, hidden discards, burnout steps, and RNG state are absent for players and spectators; revealed cards are accurate. |
| Determinism | The same valid action sequence and injected random stream produce identical results; rejected actions leave both state and entropy position unchanged. |
| Conservation | Each card in a round occupies exactly one of a hand, discard pile, or undealt pile; a play moves cards and never duplicates or fabricates them. |
| Completion | Simulated legal matches across multiple seeds finish within the penalty bound without self-challenges or empty-hand deadlocks. |

## Sources and original decisions

Sources were checked on 2026-09-09:

1. [Bicycle: I Doubt It](https://bicyclecards.com/how-to-play/i-doubt-it) — primary card publisher's rules document face-down claimed ranks, lying, challenge resolution in either direction, and the need to resolve a challenge against a last-card play. PartyDeck adopts the general bluff/challenge interaction, not that game's deck, sequence, all-player challenge window, pick-up penalty, or win condition.
2. [Curve Animation: Liar's Bar on Steam](https://store.steampowered.com/app/3097560/Liars_Bar/) — developer/publisher product description confirms a required table value, face-down claims, challenges, a random elimination penalty, and resetting cards after the penalty. The description is not a complete formal rules reference; unspecified deck composition and end-of-hand behavior are not inferred from it.

PartyDeck's 30-card composition, two-to-six-player support, one-to-three-card limit, forced final challenge, rotating opener, explicit result phase, and six-light presentation are design decisions specified above. They require playtesting for pacing and enjoyment; this document does not claim measured commercial balance.
