# Gameplay and results design

Research checked on 2026-09-09. Owner: `ui_game`. Implementation began after the coordinator's independently verified environment gate and interface freeze. The rule source of truth is [Last Light rules](../game-rules.md), not this presentation document.

## Implemented and locally qualified

The shared `GameplayScreen` and focused `GameTable`, `PrivateHand`, `GameCards`, and `GameResults` components now live under `composeApp/src/commonMain/kotlin/dev/partydeck/app/ui/game`. Localizable game strings/plurals are isolated in `composeApp/src/commonMain/composeResources/values/game_strings.xml`.

The screen consumes the frozen recipient-specific `GameView`, session action availability, host role, pending action, foreground state, and `privacyEpoch`; it emits only Play/Challenge/Next round/Back to room callbacks. The shell owns routes, insets, session notices, and native services. A new game-screen entry starts with the hand concealed. Hide and background/epoch changes clear selection and immediately remove private face semantics. Duplicate display names receive stable public seat numbers in claims, turns, challenges, and outcomes.

On 2026-09-09 at 17:15 UTC, `flock /tmp/partydeck-gradle.lock ./gradlew :composeApp:jvmTest --tests dev.partydeck.app.GameplayLayoutTest --console=plain` compiled the integrated shared/JVM application and passed all **seven gameplay UI tests** (zero failures/errors). The tests cover real engine-projected six-player views, fifth-card rail selection, large-text vertical cards, hidden-hand semantic removal, conflated background/foreground epochs, pending Play/Challenge callback gating, forced challenge, Wild-plus-mismatch proof, three-card selection limits, long claimant names, host round continuation, eliminated viewers, previous-round proof, and a real engine-simulated winner. Fixture outcomes are not fabricated UI scores or special production states. The final XML, HTML report, console log, and copies of screenshots are preserved locally in `/tmp/partydeck-gameplay-final-20260909` so later targeted JVM runs cannot replace this evidence.

Rendered captures under `composeApp/build/ui-snapshots/game-*` include the real shell header footprint at 360 × 640, 320 × 740 with 200% text, 844 × 390, and 1024 × 768 logical viewports, using Compose Multiplatform 1.12.0 / Skiko on Linux at density 1. They are generated test artifacts from the current working tree, not native-device evidence. Initial rendered review found and corrected a clipped compact claim, a crowded large-text hand header, and a fuse result below the first viewport. Compact play now puts rank/claim before the roster, which expands or becomes a rail according to the available height; enlarged hand headers stack; challenge results state the penalized player's settled outcome directly below the verdict. Long claimant labels retain full semantics while keeping horizontal action buttons within the viewport.

The winner uses the full available width in short landscape, placing a smaller ornament beside the name and continuation. At large text it uses the system-scaled `titleLarge` style and omits optional ornament/flavor copy; font scaling remains intact. The full long winner name and Back to room are asserted visible before any scrolling in all four viewports. The design reviewer independently cleared both winner corrections. Normal portrait keeps its original composition.

An eliminated viewer has no private-hand, reveal-hand, Play, or Challenge subtree, asserted against a real elimination during the simulated match and captured at all four sizes. Prior-round proof remains expandable during active play without reannouncing its verdict. The tests assert that a round-2 view presents a round-1 result under `ROUND 1`, then capture the verdict and actual card proof at deliberate scroll positions (`*-previous-reveal.png` and `*-previous-proof.png`).

Independent design review passed the phone, large-text, short-landscape, and tablet gameplay captures and the preserved seven-test report. All mandatory gameplay visual findings are closed. The tall tablet playing layout leaves generous unused space; fuller card sizing or roster grouping remains optional visual refinement.

The tests do not establish native TalkBack/VoiceOver behavior, safe-area behavior, background snapshot timing, physical touch/haptics, sustained-device frame performance, or Android–iOS LAN behavior. Those remain with the platform and integration qualification streams. Selection lift and the winner's restrained ornament fade honor the effective reduced-motion preference; game outcomes and actions never wait for either animation.

## Direction and visual contract

**Last Light should feel like a small, beautifully printed card game played after dark.** The table is the main composition. A few large, deliberate elements carry attention: the acting player, the required rank, the latest face-down claim, and the viewer's hand. Avoid a dashboard made of equal-sized boxes, unrelated statistics, nested panels, or a permanently animated background.

Shared shell/assets proposal:

| Token | Value / use |
| --- | --- |
| Ink | `#191526`, main canvas and text on bright fills |
| Paper | `#F4F0E8`, card faces and primary text |
| Citron | `#D6EF82`, the main Play action, turn marker, selected state |
| Copper | `#F16B48`, Challenge emphasis and small result accents |
| Surface | `#252133`, restrained supporting surfaces |
| Muted text | `#BAB5C4`, supporting text on ink |
| Line | `#575163`, nonessential separators |
| Typography | Fraunces SemiBold for short expressive titles; Manrope for names, rules, cards, and controls |
| Original vectors | `rank_crown`, `rank_moon`, `rank_star`, `rank_wild`, `card_back`, `partydeck_mark` |

Use ink text on citron/copper fills. The design reviewer measured paper-on-copper at only 2.66:1, so it is unsuitable for ordinary button text. Rank names always accompany their distinct symbols. WILD uses the assets owner's interlaced/orbit form so its silhouette differs from STAR. All faces, backs, and table ornament are original; no copied game imagery is needed.

The normal portrait composition has generous outer breathing room, a short turn headline, a restrained player rail, and a large rank/claim centerpiece. The private hand forms the lower edge of the table. Controls sit beneath it in the thumb area. A thin printed border, offset stack of card backs, and one large rank symbol establish the identity without a raster texture or expensive effect.

## Phone-first interaction

Reading and accessibility order:

1. `Round 4 · Last Light`, session status when relevant, and the leave/menu affordance supplied by the shell.
2. `Your turn` or `Mila's turn`, then `Crown table` and `Wild cards always match`.
3. Public player seats: full accessible name, card count, used fuse lights, and explicit `To play` / `Out` labels where relevant.
4. Latest claim: `Mila played 2 cards as Crowns`, represented only by card backs until a challenge resolves. Opening state: `Open the round — play 1–3 cards`.
5. `Your hand · 5 cards`, a visible `Hide hand` control, independently selectable card faces, and `2 of 3 selected`.
6. Primary `Play 2 cards` and separate `Challenge Mila` actions, followed by a short contextual explanation only when needed.

The rank centerpiece and previous claim belong to one visual table, not separate metric cards. Opponent seats are quieter than the actor and last claim. Names may truncate visually in compact seats, but their full values remain accessible. A seat never contains the opponent's actual cards.

### Hand and selection

- Tap to toggle a card. Dragging, swiping, long pressing, and tilt are never required to play.
- Use stable card IDs supplied by the viewer-safe model. Maintain only a local set of selected IDs; intersect it with the latest available hand after every authoritative update.
- A selected card has an ink/citron outline, a visible check, and a small lift within its reserved slot. Selection never relies on color or position alone.
- Give every selectable card a separate rectangular target. Start with a 2:3 face at approximately 64 × 96 logical units; use larger faces when space allows. Do not overlap the interactive targets to imitate a physical fan.
- Five 64-unit cards with four 8-unit gaps require 352 units of inner width. The implementation allows gaps from 6 through 8 units, then switches to a scrollable rail when even the 344-unit minimum row cannot fit its actual inner width. Large text uses a readable vertical card list. Do not shrink text or targets to preserve the five-card row.
- Once three cards are selected, unselected cards remain readable. A further selection does not replace an existing choice; explain `Choose up to 3 cards`. Every selected card remains deselectable.
- With no selection, label the primary control `Select cards`; explain the one-to-three rule nearby. When selected, show the resulting public claim before sending: `You'll claim 2 Crowns`. Do not warn about or decorate bluffing as an error: it is a legal move.
- `Hide hand` immediately replaces face components and their semantics with card backs and a single `Show hand` button. It is not an alpha fade: invisible composables can remain discoverable to screen readers. Pending or stale selection is never announced with private ranks in a live region.
- The platform/controller marks private content concealed when the scene becomes inactive. Return with the hand concealed until the viewer chooses `Show hand`. This is a privacy cover, not a promise to prevent screenshots or recordings.

### Action availability

The UI consumes legal-action availability from the domain projection and session/controller state. It does not decide the next actor, truth, penalty, or victory.

| Situation | Main UI behavior |
| --- | --- |
| Own opening turn | Select 1–3 cards; Play enabled for a valid selection; no Challenge action without a claim. |
| Own ordinary turn | Play the selected cards or Challenge the named latest claimant. Playing accepts their previous claim. |
| Own forced challenge | One strong `Challenge [name]` action; explain `You're the last player holding cards`. Remove irrelevant selection controls. |
| Another player's turn | Readable private hand and public table, with `Waiting for [name]`; no playable-looking submit button. |
| Empty hand, latest own claim still pending | `Your last play can still be challenged`; do not announce that the round is safely cleared. |
| Accepted empty hand | `You're clear for this round` and public table; the next round deals a new hand. |
| Command pending | Keep the selected IDs visible and replace submission text with `Sending play…` / `Calling challenge…`; disable both submission paths until controller acknowledgement/rejection. |
| Command rejected | Explain the human-readable reason near the controls, apply the latest view, and retain only still-valid selected IDs. No optimistic rule state remains. |
| Connection pause/reconnect | Keep current public context and the controller's connection message; disable commands. Do not invent a turn timeout or automatic forfeit. |
| Eliminated viewer | `You're out — stay and watch`, public state, and no private hand or gameplay actions. |
| Round ended | Inspectable challenge and fuse result; only the host has `Next round`. Others see `Waiting for the host`. |
| Match finished | Winner composition with the last public result still inspectable; session return/rematch availability comes from the controller. |

`Play` and `Challenge` do not require a second confirmation dialog. Selection is already a deliberate preparation, and a separate named Challenge button is sufficiently explicit. A leave/end-session confirmation belongs to the shell because it has session consequences.

## Reveal, fuse, and winner

### Challenge result

Use a result scene within the same table language, with this complete explanation visible from the authoritative update:

1. `Bo challenged Ada` and `Ada claimed 2 Crowns`.
2. The actually challenged card faces, each with rank text. Accepted older discards stay hidden.
3. `Bluff caught` or `The claim was true`.
4. `Ada tests their fuse` or `Bo tests their fuse`, followed by `Still in` or `Burned out · out of this match`.

For a truthful WILD, the card label can include `Wild · matches Crown`. For a bluff, underline/mark mismatching ranks as well as using accent color. The reveal should teach why the verdict occurred without making the player read the rules elsewhere.

All text and the final outcome exist independently of animation. Keep the result until the host continues. No timer, sound, haptic, or motion-only cue is required to understand it. If an outcome is already present when reconnecting, render its settled state; do not replay a dramatic sequence merely because the composable was recreated.

### Fictional fuse

The fuse is a simple row/arc of six original stage lights. Public used-light count is shown as `Fuse tested 2 of 6` alongside distinct tested/untested shapes. It is not a six-health bar and never labels remaining lights as guaranteed safe. The host's secret burnout step is never drawn, inferred, or requested by this UI.

On a safe penalty, the new used-light indicator settles and `Still in` appears. On a burnout, the player's badge and six-light ornament dim and `Out · watching` is explicit. A small contained spark/ring accent may accompany the result; no firearm, wound, death, flashing full screen, shaking camera, or jump scare. The outcome is already known before that ornament starts.

### Winner

One strong paper/citron rank/last-light emblem sits above `Nora wins` and the short supporting line `The last light at the table`. Show the real round number and public player identities only if useful. Do not invent point totals, bluff percentages, rankings, achievements, or loss counts absent from authoritative data.

The final challenge remains available below the winner or as an explicitly expandable explanation. The host's next step should be `Back to room` for another match unless the controller implements a genuine rematch command. Other players can follow the host or leave using the actual session contract. An elimination alone never routes a viewer to the winner scene.

## Motion and feedback budget

These timings are proposed product values to tune with visual review, not platform requirements.

| Event | Normal motion | Reduced motion |
| --- | --- | --- |
| Card select / deselect | About 140 ms; up to 8 logical units of lift and outline/check transition | Immediate selected outline/check; no translation |
| New actor / claim | About 180 ms small crossfade; incoming public pile always uses backs | Immediate update or a short nonmoving fade |
| Reveal | At most about 360 ms decorative face/back transition after the result is available | Immediate face and verdict |
| Fuse result | One contained accent, at most about 450 ms, followed by the settled light state | Immediate settled lights and text |
| Winner | About 240 ms opacity/short settle; no endless confetti or looping glow | Immediate composition |

Do not delay commands or host continuation until animation completes. Do not schedule animations as rule-engine events. Hoist outcome animation bookkeeping outside any lazy player/card list, and key it to an actual new result rather than recomposition. Pause/cancel decorative effects when the scene leaves composition or becomes inactive.

`effectiveReduceMotion` should be the app preference OR a platform preference, provided at the shell boundary. The iOS platform owner confirmed a plan to observe UIKit's Reduce Motion setting and scene activity. This document does not assume common Compose automatically covers every native setting. Audio and haptics are optional enhancements requested through the supplied platform feedback contract, gated by preferences and foreground state. Visible text remains the primary confirmation, and no sound is played while reconnecting to an old result.

Use simple Compose state animation and drawing modifiers for decoration. Avoid a game engine, frame loop, shader stack, blur layer, or large texture for this turn-based board. The source below specifically recommends lambda modifiers/graphics layers where appropriate to avoid unnecessary composition work while animating. Actual performance acceptance requires builds and profiling; it is not established by this proposal.

## Accessibility, resizing, and privacy acceptance

- Use at least 48 dp explicit interactive bounds in shared Compose. Verify iOS controls occupy at least 44 × 44 pt during platform review as our product floor. Android recommends 48 dp; Apple's current accessibility table distinguishes a 44 pt default from a 28 pt minimum, while its Buttons guidance recommends a 44 pt hit region. Do not describe 44 pt as a universal iOS hard minimum.
- Use semantic toggle/select state for hand cards, a clear click action label, and an accessible selected state. Group each public seat into a coherent reading unit. Decorative rank duplicates and back patterns have no redundant spoken description.
- A selected card announces its own rank only when the viewer intentionally navigates to that card. Never mark the hand as a live region. Public turn changes and completed verdicts may use a polite live region; never emit repeated countdown/light animation announcements.
- Use explicit heading and pane semantics where supported by the pinned Compose stack. Test real TalkBack and VoiceOver traversal; a semantics tree inspection does not prove the native experience.
- Support the shell's safe-area/inset policy exactly once. The bottom action area must stay above navigation/gesture regions; the top controls must avoid status bars/cutouts. Do not hardcode an iPhone notch or Android bar height.
- Design from the available window dimensions, including height, not an `isTablet` branch or device name. Portrait is the primary visual target; landscape/resized windows remain functional. A broad but short window can use a table/hand split if both areas remain readable; otherwise use vertical scrolling.
- At large text, let controls grow, stack Play/Challenge vertically, use a multirow/vertical hand, and allow public content to scroll. The current actor, rank, and primary action retain meaning at 200% text. Test long translated labels, player names, and right-to-left layout. Keep strings in the shared resource system once its naming convention is frozen.
- Aim for at least 4.5:1 for ordinary text, 3:1 for qualifying large text, and 3:1 for meaningful visual control boundaries/state indicators. A decorative border can be quieter; a selected state cannot rely on a faint line.
- A concealed hand must have no rank face/text nodes in either the visible or accessibility subtree. Incoming snapshots never include opponent ranks or secret fuse information. The game screen should not log or persist cards, snapshots, or selection identifiers.

Focused review matrix: 320 × 568, approximately 390 × 844, and approximately 844 × 390 logical viewports; large phone/tablet width; 100% and 200% text; two and six players; long names; own/other/forced turn; five/one/zero cards; shown/hidden hand; safe/burnout result; final winner; pending/rejected command; reconnect pause; reduced motion. These are test scenarios, not claims that every physical device maps to those measurements.

## Implementation boundary and integration

After the root freezes APIs, own `composeApp/src/commonMain/kotlin/dev/partydeck/app/ui/game/` (including results). Root has selected `dev.partydeck.app` for the app package and `dev.partydeck.resources` for generated resources. Split only at useful composition boundaries: `GameplayScreen`, a public table/claim component, `PrivateHand`, `ChallengeResult`, and `MatchResult`. Reuse shell theme/controls and assets; do not implement a second palette or duplicate route/controller state.

Proposed inputs, expressed conceptually until the domain/controller freeze:

- Recipient-specific `GameView`: phase, viewer identity and hand, public players, current actor, required rank, latest public claim, legal-action availability, outcome, and winner.
- Session/UI state: connected/paused/pending/rejected status, local host role, and available host/session actions.
- Presentation preferences: effective reduced motion and private-content concealment. Feedback is a supplied callback/service if available.
- Callbacks: selected-card Play, Challenge, host next round, result-to-room, and leave/menu intent. The controller supplies authenticated identity, request ID, expected revision, serialization, and networking.

No `GameState`, RNG, host transport, socket, raw wire envelope, another player's hand, or platform API belongs in the game components. The UI may hold selection and hand-visibility state; the domain and controller remain the owners of everything that changes the match.

Acceptance before integration: compile against pinned common Compose; render real viewer fixtures for the review matrix; inspect hidden/selected semantics; validate actions go through the controller once; inspect result truth/bluff/fuse text with the reviewer; verify responsive layouts with actual screenshots. Add only useful automated UI tests for private-hand concealment and critical action gating if the project's test harness supports them. Domain truth/penalty tests belong to the independent game-rule test stream.

## Authoritative sources checked

1. [Bicycle — I Doubt It](https://bicyclecards.com/how-to-play/i-doubt-it): face-down claims, challenge reversal, and a last-card play that remains challengeable. The interaction lesson is a clearly named claim and inspectable proof; PartyDeck's deck, turn flow, fuse, and visual treatment are original. Domain research also records the developer's [Liar's Bar description](https://store.steampowered.com/app/3097560/Liars_Bar/); this UI does not copy its presentation.
2. [Android — Compose accessibility defaults](https://developer.android.com/develop/ui/compose/accessibility/api-defaults): 48 dp touch-target recommendation, possible overlap from auto-expanded small targets, Foundation semantics, and null descriptions for decorative graphics.
3. [Android — Compose semantics](https://developer.android.com/develop/ui/compose/accessibility/semantics): heading, pane, selected/state descriptions, custom actions, and live-region guidance; warns against frequent live-region updates.
4. [JetBrains — Compose Multiplatform accessibility](https://kotlinlang.org/docs/multiplatform/compose-accessibility.html): common semantic properties, assistive technology support, and traversal grouping/index examples. Platform behavior still needs native verification.
5. [Android — Animation quick guide](https://developer.android.com/develop/ui/compose/animation/quick-guide): `AnimatedVisibility`, `animateFloatAsState`, `graphicsLayer`, effects reentering lazy layouts, and the accessibility caveat that alpha-zero content remains composed.
6. [Android — Set up window insets](https://developer.android.com/develop/ui/compose/system/insets-ui): `safeDrawingPadding` / `windowInsetsPadding` and inset consumption; use the shell's inset boundary rather than duplicate padding.
7. [Android — Window size classes](https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes): available window size changes dynamically; width and height are separate, and landscape phone height needs consideration. This does not require adding an adaptive library for a five-card board.
8. [Apple — Accessibility HIG](https://developer.apple.com/design/human-interface-guidelines/accessibility), read through Apple's [official documentation JSON](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/accessibility.json): target-size table, text/contrast guidance, simple gestures, and Reduce Motion alternatives.
9. [Apple — Motion HIG](https://developer.apple.com/design/human-interface-guidelines/motion), accessible through [official documentation JSON](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/motion.json), and [UIKit `isReduceMotionEnabled`](https://developer.apple.com/documentation/uikit/uiaccessibility/isreducemotionenabled): system preference exists; platform adapter observes it instead of guessing behavior in common UI.
10. [W3C — Contrast minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html): 4.5:1 ordinary text and 3:1 large text. [W3C — Animation from interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html): allowing nonessential interaction motion to be disabled is Level AAA web guidance; PartyDeck adopts the useful design principle without claiming certification.
11. [JetBrains — Compose resource usage](https://kotlinlang.org/docs/multiplatform/compose-multiplatform-resources-usage.html): verified XML vector resources, `painterResource`, formatted `stringResource`, and `pluralStringResource` APIs before implementation. The publisher's [Compose UI test 1.12.0 sources](https://repo.maven.apache.org/maven2/org/jetbrains/compose/ui/ui-test-desktop/1.12.0/ui-test-desktop-1.12.0-sources.jar) verify selection/disabled assertions, content-description matching, and scroll actions, including `hasScrollAction`, `hasAnyDescendant`, and `performSemanticsAction` for deliberate capture positioning. `performScrollTo` requires a scrolling ancestor, so tests use displayed controls directly when the portrait action area is pinned.

The Space Cowboys Skull page returned HTTP 403 during this research and is not used as evidence. No dependency version, unsupported platform behavior, measured performance, or native-device verification is inferred from these design recommendations.
