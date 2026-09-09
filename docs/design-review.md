# PartyDeck design review and acceptance brief

Reviewer: dedicated independent design/UX reviewer. Research checked 2026-09-09.

**Initial decision:** proceed with the ink-and-paper direction below. This approves a direction for implementation, not the quality of an unseen interface. No application screenshots, device interactions, or accessibility trees have been reviewed yet. Commercial polish and accessibility remain acceptance gates.

The product must explain itself as a local party game on separate phones. PartyDeck is the collection; **Last Light** is the first game. The first release needs one compelling game presentation, without empty “coming soon” shelves. Rule-dependent text below follows [game-rules.md](game-rules.md), currently proposed pending coordinator freeze. Connection-dependent promises must follow the selected transport and session implementation.

## Visual direction: a lively printed card table

Use warm ink, substantial ivory paper cards, a small amount of citron, and copper for challenge or fuse feedback. Combine expressive display typography with calm readable controls. The distinctive visual device is the deck itself: oversized rank symbols, confident typography, paper borders, and a deliberate stack of cards. Avoid a dashboard of identical panels, conventional casino velvet, copied roulette props, emoji substitutes, generic gradient blobs, and excessive chrome.

The home composition should have an immediately readable PartyDeck identity, a memorable headline such as “A little trust. A lot of bluff.”, one oversized card composition, and obvious **Host a game** / **Join a game** actions. Place a literal descriptor close to the actions: “Bluff with friends, on your own phones.” Add the supported player count and connection requirement once confirmed. Personality cannot replace that basic explanation.

The shell and assets streams agreed this starting palette:

| Token | Value | Intended use |
| --- | --- | --- |
| Ink | `#191526` | Main canvas; text on paper and bright fills |
| Paper | `#F4F0E8` | Card faces; primary text on ink |
| Surface | `#252133` | Sparse grouping surfaces and sheets |
| Citron | `#D6EF82` | Primary actions; your turn; selection accent |
| Copper | `#F16B48` | Challenge and fuse accent, with a text/icon explanation |
| Muted | `#BAB5C4` | Secondary text, not a low-opacity substitute |
| Line | `#575163` | Decorative separators only |
| Outline | `#888190` | Essential unfocused input/control boundaries |

Opaque sRGB contrast was calculated using the W3C relative-luminance formula [9]. Paper/ink is **15.70:1**, ink/citron **14.05:1**, ink/copper **5.90:1**, muted/ink **8.92:1**, and muted/surface **7.81:1**. Paper/copper is only **2.66:1** and paper/citron **1.12:1**: bright filled buttons need ink labels. Line/ink is **2.35:1**, and line/surface **2.06:1**; that line cannot be the only meaningful focus, selection, or control indicator. The shell added Outline, **4.16:1** against Surface, for essential boundaries; use citron/paper for focus. Recheck actual composited colors, opacity, gradients, and pressed states in screenshots.

Use the assets stream's Fraunces SemiBold for large headings and rank display, and Manrope for body text and controls, subject to its verified bundled font licenses. Display lettering is seasoning: instructions, names, errors, and game outcomes need the readable face. Start body text around 16–17 logical text units, with comfortable line spacing. Do not use tiny uppercase labels to carry instructions. Keep fonts bundled, and verify the actual loaded family/weight on both targets.

Use a small spacing vocabulary, for example 4 / 8 / 12 / 16 / 24 / 32 logical layout units. Phone side margins begin around 20–24, but yield when enlarged text needs space. Primary controls begin at 56 units tall. Those values are product starting points, not platform specifications. Strong alignment and consistent spacing matter more than making every surface rounded.

## Simple journeys

| Journey | Required experience | Reject |
| --- | --- | --- |
| First open | Understand local bluff play; choose Host or Join. Name is requested inline when needed and remembered locally. Help and Settings are visible secondary actions. | Accounts, marketing carousels, permission prompts at launch, or a rules exam before joining. |
| Host | Enter/edit name, create table, land in a usable lobby with invitation and roster. Explain the actual connection requirement. | Several setup screens for defaults, raw protocol terms in the normal flow, or a room code that has no resolving mechanism. |
| Join | One obvious invitation/address entry path; show discovery only if implemented. Preserve entered name/invitation after a recoverable error. | A decorative search screen that never searches, undocumented format rules, or repeated re-entry after each failure. |
| Lobby | Show 2–6 seats, player name and distinct symbol, “You”, host, and honest connection/readiness status. Host sees one Start action and its unavailable reason until eligible. Clients see who can start. | Color-only player identity, fictional connected seats, ambiguous empty slots, or a permanently spinning Start button. |
| First turn | An inline hint explains that selecting 1–3 cards claims the required rank; the cards may match or bluff. Help stays available. | A compulsory tutorial replay or disabling off-rank cards, which would remove bluffing. |
| Round result | Inspect claim, revealed cards, verdict, penalized player, and fuse outcome; host explicitly continues. Retain the previous public result when a new round starts. | An auto-dismissed verdict, unreadable animation-only evidence, or a result silently replaced by a deal. |
| Match result | Name the winner, show the final public outcome, offer a real return/rematch path supported by session behavior. | Invented statistics, scores, achievements, or rematch controls disconnected from state. |

“How to play” should start with three concise illustrated ideas: **Claim a rank**, **Challenge a bluff**, **Keep your last light**. Then show the important exceptions: Wild always matches; any mismatching card makes the whole claim false; emptying your hand does not itself win; the sole player holding cards must challenge. The complete rules remain readable from Help. An optional illustrated explainer must be dismissible and must not be necessary to create or join a game.

## Gameplay hierarchy and hand interaction

The screen must answer these questions in order: **Whose turn? What rank are we claiming? What did the last player claim? What can I do?**

1. Keep a compact, stable public roster near the top or edge. Identify the active player with text and shape, not a pulsing color alone. Eliminated seats stay visible with an explicit “Out · watching” label; empty-handed survivors say “Waiting for next deal” once appropriate.
2. Make the required rank the table's visual anchor, with both **Crown / Moon / Star** text and its original symbol. Wild uses its own symbol and an “Always matches” explanation. Never rely on hue, suit knowledge, or an unlabeled drawing.
3. Show the last claim as a concrete sentence, for example “Ada played 2 · claims Moon”. Face-down backs convey count; they cannot expose card ranks, IDs, future fuse steps, or truth before a challenge.
4. Place the private hand and primary actions within easy reach. Tapping a card selects/deselects it. Selection gets a visible outline/check plus a small lift if motion is enabled, and an accessible selected state. Make “2 selected” and the legal maximum clear. Tapping a fourth card gives useful feedback without silently replacing a prior choice.
5. Use **Play 2 cards** and **Challenge Ada** rather than cryptic icon buttons. The play action communicates the current claimed rank nearby. Play submits the selection once; prevent repeated taps while awaiting authority. A selection is not a submitted play.
6. If the current player must challenge, explain “You're the last player holding cards. Challenge Ada to end the round.” Replace the ordinary choice with one strong Challenge action. At a round's opening, explain that no claim exists to challenge. Do not make people infer either rule from unexplained disabled buttons.

A five-card fan is attractive only while every exposed interactive region remains large, distinct, and unobscured. Do not expand invisible touch bounds into adjacent cards. At narrow widths or larger text, switch to a readable nonoverlapping hand grid or a clearly scrollable rail with accessible navigation. Cards must preserve their shape and text; a scaled-down desktop table is not a mobile layout. Drag-to-play and decorative tilt may be optional enhancements, never the only interaction.

Provide an explicit **Hide hand / Show hand** action. A hidden hand must hide ranks in both pixels and accessibility semantics; count can remain public. Private cards may be read deliberately by screen-reader focus while shown, but must never be spoken in unsolicited turn/live announcements. Backgrounding or leaving the app should obscure private content before a task-switcher snapshot where the platform permits; implementation and device evidence are required, not an assumed cross-platform guarantee. Returning should not auto-reveal a deliberately hidden hand.

## Suspense, feedback, and outcomes

The six-light fuse is an original, non-graphic stage-light motif. Label it as a fictional game penalty. Used lights and “Safe” / “Out” communicate meaning without sparks, audio, or color. Do not render a physical weapon, wound, death animation, or roulette prop. The host's already-decided result drives the presentation; the UI cannot reroll, choose the outcome, or imply that tapping at a precise time changes it.

Show public fuse progress consistently. If risk is displayed, it must match the rules: next burnout chance is **1 in (6 − used lights)** conditioned on survival, reaching certainty after five safe penalties. A fixed “1 in 6” on every turn would be false. The hidden burnout step never belongs in the UI or its accessible labels.

The challenge result should read like an inspectable receipt: “Ada claimed 2 Moons” → the two revealed cards → “Bluff” or “Truth” → “Ada tests a light” / “Bo tests a light” → “Safe” or “Out”. Explain which revealed card failed to match through shape/text, not red tint alone. Reveal only the challenged play. Older accepted discards remain hidden under the domain rules.

Suggested motion timings are design hypotheses to tune with actual devices: 80–120 ms touch acknowledgement, roughly 180–240 ms card selection/placement, and 240–400 ms reveal. Avoid stacking multiple delays on every turn. A brief optional fuse beat can add tension, but outcomes and controls must remain available without waiting for spectacle. Never require completion of a local animation before applying authoritative state.

Respect the system's reduced-motion preference and provide an app **Reduce motion** control. The stronger reduction wins. Use instant changes or restrained fades; remove card fly-ins, bouncing, shaking, repetitive pulsing, and large zooms. Avoid flashes by design, including in the normal mode. Audio and haptics supplement visible text and shape; provide separate controls and persist them. A silent, motion-reduced match must remain fully understandable [5][7].

## Connection, interruption, and error states

Connection UI describes what is known. A timeout alone does not prove a denied permission, a wrong network, or that the host deliberately left. Do not expose stack traces or raw exceptions to players. Developers still need diagnostic information outside the normal flow.

| State | User-facing information and action |
| --- | --- |
| Connecting | “Connecting to the table…” in context, visible Cancel, and a bounded path to retry. Preserve the form. A pending button shows its operation rather than looking frozen. |
| Permission needed/denied | Explain that local access connects PartyDeck devices. Trigger platform access when Host/Join requires it. Offer the supported settings recovery path when denial is known; do not claim the next retry will display the same system alert. |
| No discovered tables | Show this state only if discovery exists. Explain how a host creates a table and how to use the implemented manual invitation fallback. |
| Cannot reach host | “Couldn't reach the host. Check that both phones are on the same Wi-Fi, then try again,” if same-network transport is selected. Mention guest-network isolation in expandable help, not as a guessed diagnosis. |
| Invalid invitation | Identify the input problem near the field; preserve the rest. Example formatting must be genuinely accepted by the parser. |
| Full / already started / incompatible | State the specific known reason and a clear way back; ask for an update only when protocol incompatibility is established. |
| Reconnecting | Keep a privacy-safe last-known table, show who is reconnecting, and suspend actions against stale state. Restore the current sanitized hand/turn from authority after success. |
| Waiting for another player | Name the missing player and show that the match is paused. A grace countdown or removal/forfeit action exists only if the session implements it. |
| Pending action interrupted | Preserve selection where possible; resolve the same action's acknowledgement/revision on recovery. Never invite a second independent submit that might replay a penalty. |
| Host/session gone | Distinguish an explicit ended session from a temporary connection loss. When ended, “This table has ended” with **Back to games** is sufficient. Do not promise host migration or announce a game-rule winner. |
| Leaving | A client and the host get role-appropriate consequences; leaving an active hosted table requires a concise confirmation because it ends play for others. Settings and ordinary Back navigation should not silently destroy the session. |

Apple documents that the first qualifying local-network operation prompts, the decision persists, and permission can be changed in Settings. Its simulator does **not** support local-network privacy, so denial/re-enable acceptance requires a real iOS device [10]. Transport and native-platform agents own exact APIs and lifecycle behavior.

## Accessibility and responsive acceptance

These are product acceptance requirements informed by the sources below, not a claim that each is a mandatory store policy.

- **Touch:** at least 48 × 48 dp independently usable Android targets [1]. Verify at least 44 × 44 pt on iOS for this product. Apple's current accessibility table distinguishes a 44 pt default from a 28 pt minimum, while its button guidance still recommends a hit region of at least 44 pt [5][6]. Never use the smaller figure to justify a crowded hand.
- **Type:** use platform-scaled text, support at least 200% enlargement, and test the largest system text setting. Android's scaling is nonlinear; do not hand-multiply layout measurements or shrink text to undo it [4]. iOS Dynamic Type behavior in the selected Compose version needs actual verification, not an assumed mapping.
- **Contrast:** at least 4.5:1 for ordinary text; at least 3:1 for meaningful graphical boundaries/states. The proposed palette aims above the text floor even for large text. Decorative lines can be subtle, but focus and selection cannot depend on them [1][8][9].
- **Semantics:** each interactive card has rank, position, selected state, and action; each fuse/seat has a readable public status. Decorative artwork stays out of focus order. A custom Canvas has no automatic guarantee of useful per-card semantics [2]. TalkBack and VoiceOver must traverse the same decision sequence a sighted player uses.
- **Announcements:** politely announce public turn, connection, and result changes once. Do not interrupt focused card inspection, move focus on every state update, or disclose private ranks in live feedback. Focus stays stable while waiting, reconnecting, or selecting a card.
- **Inputs:** all primary paths work by taps and assistive activation. Optional gestures have visible alternatives. Keyboard focus is visible wherever keyboard navigation is offered. No essential action requires dragging, rapid timing, long press, or a multi-finger gesture [5].
- **Safe areas:** background art may extend to the edges; controls, rank text, and hand targets respect system bars, cutouts, keyboard, and gesture areas. Android drawing safety and gesture safety are distinct; verify both [3]. On iOS use the actual safe area instead of guessed status-bar/home-indicator heights [7].
- **Adaptation:** design phone portrait first, then handle short landscape windows, tablets, and resizing without a mandatory rotate gate. Reflow by available window dimensions, not a device model list. Apple explicitly calls for variations in orientation, text, safe areas, and localization [7]. Android's orientation/resizing behavior varies with target and game categorization; do not assume either a universal lock or a universal override [11].
- **Large text layout:** instructions and results wrap; actions can stack vertically; the roster may collapse to concise public summaries with an accessible expansion; the hand becomes a grid/rail. Scrolling must reach every action with the keyboard open and without trapping the hand under a fixed footer.
- **Localization:** resources contain real strings/plurals, not concatenated English fragments. Player names may wrap or be shortened visually with the complete accessible name preserved. Test long names, long translations, and RTL layout. Do not encode essential words inside bitmaps.
- **Settings:** reduced motion, sound, haptics, hand privacy, and Help are reachable before and during play; choices persist and change the actual behavior. A decorative toggle with no effect fails acceptance.

## Independent review gates

Before polishing animations, provide **real rendered screenshots** of Home, Join with an error, full six-seat Lobby, your turn with a five-card hand, forced Challenge, a truth/bluff reveal, reconnecting, eliminated spectator, Settings, and winner. Include one compact 360 × 640 logical viewport, a 320-wide stress case where supported, a common taller phone, a short landscape viewport, and a tablet-size window. These are test fixtures, not claims about specific shipping devices.

At least Home, Join, Gameplay, and Result must also be captured at 200%/largest supported system text and with long player names. Review both unselected and three-selected hands. Record screenshot provenance: commit, platform/runtime, viewport, font setting, and state. A desktop rendering can reveal layout problems but does not prove Android/iOS insets, typography, input, or accessibility correctness.

| Gate | Evidence needed | Failure severity |
| --- | --- | --- |
| First-use clarity | A new person can identify local multi-device play, host/join without reading a manual, and find the required next action. | High if a wrong or dead-end path is likely. |
| Visual distinction | The shipped home/table actually contains the deck motif, original ranks, expressive type, and consistent hierarchy; ordinary screens do not regress to default component stacks. | High for generic or placeholder final UI. |
| Compact interaction | Five cards, six seats, and the two turn choices remain readable and individually tappable; enlarged text and keyboard cause no inaccessible clipping. | Release blocking when a necessary action is inaccessible. |
| State honesty | Buttons reflect phase/role; loading, errors, reconnect, forced challenge, spectator, and terminal session states have correct actions. | Release blocking for illegal/duplicated actions or unrecoverable navigation. |
| Private information | Other hands are absent; hand hiding affects semantics; public announcements and snapshots do not unexpectedly expose private information. | Release blocking for hidden-information leakage. |
| Assistive play | TalkBack and VoiceOver allow host/join, select/unselect, play/challenge, inspect outcome, and leave; no motion/audio-only information. | High; release blocking when the core game is unusable. |
| Game feel | Actual device recording shows prompt touch acknowledgement, clear turn changes, restrained readable reveals, and a complete reduced-motion path. | High for delayed, confusing, or inaccessible feedback. |

Screenshots alone cannot pass touch targets, screen-reader behavior, privacy during backgrounding, haptics, networking, or animation smoothness. Those need interaction/device evidence. The Linux reviewer can inspect rendered artifacts and UI implementation immediately; native-device limitations must be explicit rather than counted as passes.

Open dependencies: coordinator rule/name freeze; exact invitation/discovery support; session reconnect and host-loss policy; native privacy/settings integration; actual compiled fonts and icons. Review findings should identify file/component, trigger, visible impact, and a concrete fix. Re-review meaningful corrections; do not repeatedly build unchanged screens for ceremony.

## Initial cross-stream review findings

Reviewed [shell research](research/ui-shell.md) and [gameplay research](research/ui-game.md) on 2026-09-09. Both incorporate the agreed direction and useful state distinctions; neither is an implementation-quality pass.

| Finding | Impact and requested correction | Status |
| --- | --- | --- |
| Hand-width assumption | Five 64-unit cards plus four 8-unit gaps and two 24-unit margins need **400 units**, exceeding common 360/390-wide review fixtures. Compute against the real hand width and reflow before clipping; verify both text and exposed hit regions. | Sent to gameplay owner; await rendered evidence. |
| Host-loss wording | A dropped connection does not establish that host authority ended. Attempt supported reconnect and reserve terminal copy for confirmed loss/termination. | Sent to shell owner; await state integration. |
| Low-contrast essential outlines | The subtle line token fails 3:1 against ink/surface. | Resolved in the proposed palette by separate Outline token; verify actual controls later. |
| All state-copy claims need backing | “Search”, invitation Copy/Share, “Ready”, Cancel, reconnect, and rematch imply implemented behavior. Rendering a plausible button is insufficient. | Inspect callbacks/controller behavior at the integration review. |

First fast visual gate: Home and a six-seat Lobby at 360 × 640; Join with an error/keyboard; your turn with five cards; the same constrained flows at 200% text; forced challenge and a bluff reveal. Expand to the full matrix at integration/final review. This catches layout and comprehension failures before effort goes into effects.

## Authoritative sources checked

1. [Android: Make apps more accessible](https://developer.android.com/guide/topics/ui/accessibility/apps) — 48 dp touch targets, text contrast, useful descriptions.
2. [Android Compose: Semantics](https://developer.android.com/develop/ui/compose/accessibility/semantics) — meaningful custom-control semantics and merged/unmerged trees.
3. [Android Compose: Window insets](https://developer.android.com/develop/ui/compose/layouts/insets) — drawing/gesture/safe-content distinctions.
4. [Android 14: Non-linear font scaling to 200%](https://developer.android.com/about/versions/14/features#non-linear-font-scaling) — scaled text and maximum-size testing.
5. [Apple HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility) — enlargement, controls, contrast, non-color information, alternatives, reduced motion, and time-limited interfaces. Read through Apple's [official documentation data](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/accessibility.json).
6. [Apple HIG: Buttons](https://developer.apple.com/design/human-interface-guidelines/buttons) — hit regions, press feedback, concise action labels, hierarchy, and pending feedback. Read through [official documentation data](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/buttons.json).
7. [Apple HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout) and [Motion](https://developer.apple.com/design/human-interface-guidelines/motion) — safe areas/adaptation and purposeful, brief, optional motion. Read through their official documentation-data endpoints.
8. [W3C: Understanding non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) — meaningful visual components/states at 3:1.
9. [W3C: Understanding contrast minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) — text contrast and sRGB relative-luminance calculation.
10. [Apple TN3179: Understanding local network privacy](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy) — permission lifecycle and real-device testing requirement. Read through [official documentation data](https://developer.apple.com/tutorials/data/documentation/technotes/tn3179-understanding-local-network-privacy.json).
11. [Android: App orientation, aspect ratio, and resizability](https://developer.android.com/develop/ui/compose/layouts/adaptive/app-orientation-aspect-ratio-resizability) — current target/large-screen behavior and game exceptions; verify against the shipping manifest rather than assuming a universal rule.
