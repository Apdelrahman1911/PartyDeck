# PartyDeck shell: research and implementation contract

Research and implementation date: 2026-09-09. Owner: `ui_shell`. The shared shell is implemented after the coordinator's contract freeze and independently verified bootstrap. Implementation ownership is `composeApp/.../ui/shell`, `composeApp/.../ui/theme`, `PartyDeckApp.kt`, `values/shell_strings.xml`, and the dedicated `ShellLayoutTest.kt`. Gameplay, domain rules, platform entry points, application/session controller, and font/vector source files have separate owners.

Coordinator freeze: package `dev.partydeck.app`; generated resources `dev.partydeck.resources`; Compose Multiplatform 1.12.0, independently pinned stable Material 3 1.9.0, Kotlin 2.4.20, lifecycle 2.11.0, coroutines 1.11.0. Simple controller-owned `AppScreen` routing uses no Navigation dependency. Android minimum 26; iOS minimum 15. UI owns `values/shell_strings.xml`, gameplay owns its separate game strings, and assets owns fonts/vectors/notices. The bootstrap gate has passed; target-device qualification remains distinct from JVM rendering evidence.

## Verified foundations

| Area | Authoritative evidence | Application decision |
| --- | --- | --- |
| Shared UI | [JetBrains: Compose relationship](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-multiplatform-and-jetpack-compose.html) confirms common Foundation, Material 3, UI, runtime, animation, lifecycle, and navigation APIs; Android-only APIs remain excluded. | Use common Compose UI, with platform services injected at the app boundary. No platform conditionals inside screen components. |
| Versions | [JetBrains compatibility](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-compatibility-and-versioning.html), updated 2026-08-25, describes Compose Multiplatform 1.12.0 and its Android Compose 1.12.0 mapping. | Coordinator owns the complete toolchain/version freeze and smoke test; this stream does not add independent versions. |
| Navigation | [JetBrains navigation](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-navigation.html) documents typed routes, small route arguments, a single underlying state source, and platform back gestures. Its example currently uses a prerelease. [Maven Central metadata](https://repo.maven.apache.org/maven2/org/jetbrains/androidx/navigation/navigation-compose/maven-metadata.xml) lists 2.9.2 as the highest stable release and 2.10.0-beta01 as the latest published release. | Six explicit shell destinations suffice. Prefer a single controller-owned route and a small platform back adapter unless stable Navigation is already included. Do not duplicate session/game state in route arguments. A visible back affordance is required on secondary screens; native back integration must be verified. |
| State and lifecycle | [JetBrains lifecycle](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-lifecycle.html) confirms common lifecycle ownership and iOS event mapping. [JetBrains common FlowExt source](https://github.com/JetBrains/compose-multiplatform-core/blob/jb-main/lifecycle/lifecycle-runtime-compose/src/commonMain/kotlin/androidx/lifecycle/compose/FlowExt.kt) verifies `StateFlow<T>.collectAsStateWithLifecycle()` and its default `STARTED` threshold. [Compose state guidance](https://developer.android.com/develop/ui/compose/state) covers state hoisting and immutable observable values. | Render one immutable `AppUiState` from a controller `StateFlow`. Collect with the verified lifecycle artifact if included; screen composables receive values and callbacks. Platform foreground events also go to the controller because privacy and transport behavior cannot depend on whether a screen is currently collecting. |
| Resources | [JetBrains resource usage](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-multiplatform-resources-usage.html) verifies `composeResources/font`, composable `Font(Res.font.name, FontWeight...)`, XML string resources, positional substitutions, plurals, and vector resources. | Bundle offline fonts; use generated `Res` accessors and resource-backed user-facing copy. Android XML vectors work across targets. Avoid runtime font downloads. |
| Touch and semantics | [Android Compose accessibility defaults](https://developer.android.com/develop/ui/compose/accessibility/api-defaults) specifies 48 dp minimum interactive bounds, explains expanded touch targets, and recommends Foundation/Material semantics. [JetBrains iOS accessibility](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-ios-accessibility.html) confirms semantics mapping to VoiceOver and `testTag` mapping to `accessibilityIdentifier`. | Give every action at least 48 dp of actual layout space, not overlapping invisible hit extensions. Use real buttons/toggles and meaningful state labels. Decorative art has no spoken description. |
| Safe areas / keyboard | [Android insets guidance](https://developer.android.com/develop/ui/compose/system/insets-ui) verifies `safeDrawingPadding`, `imePadding`, inset consumption, and the risk of obscured final text fields. | Apply safe insets once at the shell boundary; forms scroll and account for the IME. Do not hard-code status or navigation bar sizes. Check the integrated iOS safe-area behavior before calling it verified. |
| Responsive layout | [Android adaptive display guidance](https://developer.android.com/develop/ui/compose/layouts/adaptive/support-different-display-sizes), updated 2026-09-02, directs layouts to react to the available space; notes orientation restrictions are ignored on relevant Android 16 large-screen configurations. It documents the extra layout work of `BoxWithConstraints`. | Portrait-first, never portrait-dependent. Use one screen-level width/height decision and regular Row/Column layouts; avoid nested constraint readers. Compact-height and large-font screens scroll instead of shrinking text or targets. |
| Contrast | [WCAG 2.2 contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) specifies 4.5:1 normal text and 3:1 large text, with exact sRGB luminance calculation. | Use the measured palette below; do not put paper/white lettering on bright accents. State is communicated with copy and icon/shape as well as color. |
| Reduced motion | [Compose MotionDurationScale](https://developer.android.com/reference/kotlin/androidx/compose/ui/MotionDurationScale) says scale 0 completes motion on the next frame. The iOS platform stream is separately verifying UIKit Reduce Motion and notifications. | Effective reduction = user preference OR platform setting. No mandatory animated intro, continuous background animation, looping shake, or motion-only state communication. Do not assume Compose duration scaling proves iOS Reduce Motion integration. |

The generic Android state article still labels `collectAsStateWithLifecycle` Android-only; the JetBrains common source above is the evidence for the multiplatform port. Verify the resolved artifact in the smoke build rather than importing an API solely from a documentation snippet.

## Visual direction agreed with assets and design review

PartyDeck is an intimate, slightly mischievous card table: near-black ink, warm paper, a crisp citron action, and restrained copper tension. Large paper-card compositions and editorial type make the product identifiable. Avoid a dashboard of rounded panels, casino ornament, borrowed game branding, weapon imagery, gradients/glow as decoration, and tiny decorative status text.

| Token | Hex | Intended use |
| --- | --- | --- |
| Ink | `#191526` | Page background; lettering on paper and accents |
| Surface | `#252133` | Subtle input/overlay/seat surfaces |
| Paper | `#F4F0E8` | Main text; illustrated card faces |
| Muted | `#BAB5C4` | Secondary readable text |
| Citron | `#D6EF82` | Primary action, selected/ready indication |
| Copper | `#F16B48` | Tension, significant game action, warning accent |
| Divider | `#575163` | Decorative separation only |
| Outline | `#888190` | Essential unfocused input/control boundaries |

Measured opaque sRGB contrast: paper/ink **15.70:1**; muted/ink **8.92:1**; muted/surface **7.81:1**; ink/citron **14.05:1**; ink/copper **5.90:1**; outline/surface **4.16:1**. Paper/copper is **2.66:1** and paper/citron is **1.12:1**, so those combinations are prohibited for text. Divider/ink is only **2.35:1**, suitable for decoration but not the sole essential boundary or focus indicator. Focus uses citron/paper with a distinct stroke.

Typography resources agreed with `assets` (license records are owned there): `fraunces_semibold.ttf`, `manrope_regular.ttf`, `manrope_medium.ttf`, `manrope_semibold.ttf`. Fraunces is for expressive large headings and large rank marks only. Manrope is for body copy, numerals that carry instructions, input, and controls. Body starts at 16 sp, important instructional body at 17–18 sp. Large titles around 36–48 sp adapt by layout, not by suppressing the user's font scale. Small labels stay comfortably readable; uppercase tracking is limited to short editorial eyebrows.

Use an 8 dp spacing rhythm with 4 dp detail increments, 24 dp compact-screen margins (16 dp on very narrow screens), and controls at least 52–56 dp high that can grow for multiline labels. Paper corners are restrained (roughly 12–16 dp); major buttons may be pill-shaped. Decorative card art can rotate; playable controls and body copy remain straight and stable. No interactive control overlaps another's touch area.

Implemented shared theme contract:

```kotlin
@Composable
fun PartyDeckTheme(reduceMotion: Boolean = false, content: @Composable () -> Unit)

// MaterialTheme.colorScheme / typography / shapes are the primary API.
// A small PartyDeckColors object supplies intentional paper-card accents.
// LocalReduceMotion supplies the effective motion policy to decorative UI.
```

The game stream has agreed to these colors/fonts and the common 48 dp interactive floor. It will consume the effective reduced-motion and foreground/privacy flags rather than checking platforms.

## Screen and interaction plan

### Home

A compact PartyDeck wordmark sits above a distinctive paper-card composition. Headline: “A little trust. A lot of bluff.” A literal descriptor near the actions explains “Bluff with friends, on your own phones.” Actual transport constraints (for example “Use the same Wi-Fi”) accompany the actions once verified. Host table is the single citron primary; Join table is an equal-height secondary. Practice and How to play remain quieter, available without an account. Settings is a clear, labeled header affordance. There is no onboarding carousel or invented online lobby.

At roomy widths, hero art sits beside the actions. On compact height, art shrinks or disappears while the description/actions remain intact. The maximum readable content width prevents the screen from becoming a stretched desktop form.

### Host / Join

Each is one screen with a back action, a title, a guest-name field, and the minimum connection information required by the chosen transport. Name validation is inline, human-readable, and mirrors the controller's actual bound. Host starts after the explicit button; entering the screen does not trigger permissions. Join accepts the actual verified invitation/address format with a visible label and example supplied by the protocol owner. No fake six-digit room-code field or idle “Searching” animation if discovery is not implemented.

Busy state names the operation (“Opening your table…” / “Joining the table…”), disables the submitting action, and offers cancellation. A problem stays visible beside the form and preserves name/address input. Error copy distinguishes malformed invitation, unreachable address, permission/network failure when knowable, incompatible version, rejected/full table, and ended session. Avoid claiming that an ambiguous socket failure proves permission denial.

Any connection key displayed in the invite is explicitly a private table invitation, not an authentication guarantee. Copy/share actions appear only with a functioning implementation. Never expose private resume credentials or hidden cards in the invitation. No telemetry/account/privacy claims beyond implemented behavior.

### Lobby

An editorial title (“Your table is taking shape”) leads to a shareable invitation section and a clear seat roster. Each row has a stable avatar/initial, display name, “You” / “Host” as appropriate, and textual ready/connected/reconnecting state. Empty seats are calm placeholders with the true minimum/maximum player count from rules. Ready is a reversible guest action. The host's Start action is available only when the controller permits it, with a visible reason when unavailable. Host ready behavior follows the shared session rule rather than a separate UI rule.

Leaving a live hosted table warns that the table ends for everyone; leaving as a guest says only that guest is leaving. Back triggers this concise confirmation. Declining stays at the same table. A disconnected player is visibly retained if reconnection exists; roster disappearance must not imply elimination. Host loss is terminal when migration is not implemented, with Return home and an honest explanation.

Distinguish a dropped connection from confirmed session termination: a socket timeout alone is not evidence that the host is permanently gone. Use supported reconnection first and reserve terminal copy for known session end/authority loss.

The transport freeze uses native TLS and a full pinned host certificate fingerprint carried out of band. `HostInvitation(joinAddress, displayAddress)` contains an opaque join string and a short display endpoint. The invitation also carries an admission secret; it is not a short numeric code. A compact address plus working Copy/Share is necessary. A full QR display-and-scan flow is preferred if implemented; do not show a decorative or nonfunctional QR placeholder. Copy on the host alone requires another channel to transfer the string to a guest, so native sharing/QR is an explicit product-integration concern raised with the coordinator. Advertised nearby discovery must wait for functioning discovery, and permission failures must be inferred only from concrete native evidence.

Coordinator approved native Share/Copy and requested QR implementation if clean and offline. The controller adds `copyInvitation()` / `shareInvitation()` backed by platform `copyText()` / `shareText()`; bounded failures stay in `UiProblem`, and successful copy uses `UiNoticeCode.INVITATION_COPIED`. Native camera scanning returns the exact invitation into the Join form; it never silently joins a different table.

### QR dependency verification

Recommended dependency: `io.github.alexzhirkevich:qrose:1.2.0`. [Official repository](https://github.com/alexzhirkevich/qrose) is unarchived and currently maintained; [Maven metadata](https://repo.maven.apache.org/maven2/io/github/alexzhirkevich/qrose/maven-metadata.xml) identifies stable 1.2.0, published 2026-09-07. Tag `1.2.0` resolves to commit `d286c1b5a1739488a7b22340cf1eb6ff124a2725`. [Published POM](https://repo.maven.apache.org/maven2/io/github/alexzhirkevich/qrose/1.2.0/qrose-1.2.0.pom) uses Kotlin 2.4.0, Compose UI 1.12.0, and its `qrose-core` 1.2.0 module. [MIT license](https://github.com/alexzhirkevich/qrose/blob/1.2.0/LICENSE), copyright 2023 Alexander Zhirkevich, requires the notice to remain with distributions; assets owner has been notified.

The [tagged API source](https://github.com/alexzhirkevich/qrose/blob/1.2.0/qrose/src/commonMain/kotlin/io/github/alexzhirkevich/qrose/QrCodePainter.kt) verifies:

```kotlin
import io.github.alexzhirkevich.qrose.rememberQrCodePainter
import io.github.alexzhirkevich.qrose.options.QrOptions
import io.github.alexzhirkevich.qrose.options.QrErrorCorrectionLevel

val options = remember { QrOptions(errorCorrectionLevel = QrErrorCorrectionLevel.Medium) }
val painter = rememberQrCodePainter(data = invitation.joinAddress, options = options)
```

Use an unaltered black square pattern on white, with an explicit quiet zone. The source defaults to `scale = 1f`, so a quiet margin is not automatically supplied. [DENSO WAVE's official guidance](https://www.qrcode.com/en/howto/code.html) requires at least four modules of clear margin on every side. Do not embed logos, round modules, invert colors, animate the code, or include surrounding text inside that margin. Render a large QR in an accessible, scrollable invitation sheet/dialog rather than squeezing it into the six-seat lobby. Keep Share/Copy available as alternatives. QR creation is remembered for the invitation, not repeated each frame. Validate the actual rendered invite with a decoder and native cameras; a plausible-looking square is not evidence of successful scanning. A QR painter's `toString()` includes data in the tagged source, so never log the painter or invitation.

### Settings / How to play

Settings contains only functional preferences: sound/haptics when implemented, reduced motion, and privacy/credits/license information supported by the app. Entire setting rows are accessible toggles with the switch itself treated as part of the row, avoiding duplicate focus/actions. User preference persistence belongs to the app controller/platform store.

The implemented Settings screen gives large-text descriptions the full row width and removes decorative headings/icons at 200% text. The complete bundled notices are read and split off the UI thread into sections of at most 1,200 characters, preferring line or word boundaries and preserving every character. A `LazyColumn` lays out visible sections; Done stays in the dialog's fixed action slot. [Official lazy-list guidance](https://developer.android.com/develop/ui/compose/lists) explains why a regular scrolling `Column` still composes all children and why lazy items must each have bounded content. The [common Material 3 dialog source](https://github.com/JetBrains/compose-multiplatform-core/blob/jb-main/compose/material3/material3/src/commonMain/kotlin/androidx/compose/material3/AlertDialog.kt) verifies the bounded, weighted text slot and separate button slot. This avoids measuring the approximately 258 KB legal bundle as one giant text layout; it does not omit or truncate notices.

How to play is a short scrollable rules narrative with numbered steps and original rank/card illustrations: select cards, claim the required rank, call the bluff, resolve the fictional penalty, survive. Actual rank names, wild behavior, player bounds, challenge timing, and elimination rules must be read from the frozen domain; shell does not invent them. A Practice action provides hands-on learning only if the controller implements the full offline session.

## Agreed controller boundary

The controller stream published `dev.partydeck.app.controller.AppUiState`; relevant shape:

```kotlin
data class AppUiState(
    val screen: AppScreen, // HOME, HOST, JOIN, SESSION, SETTINGS, HOW_TO
    val displayName: String,
    val joinAddress: String,
    val settings: AppSettings,
    val connection: ConnectionUiState,
    val session: SessionView?,
    val invitation: HostInvitation?,
    val problem: UiProblem?,
    val pendingAction: PendingAction?,
    val systemReduceMotion: Boolean,
    val leaveConfirmationRequested: Boolean,
)
```

Frozen application root signature:

```kotlin
package dev.partydeck.app

@Composable
fun PartyDeckApp(
    controller: dev.partydeck.app.controller.PartyDeckController,
    modifier: Modifier = Modifier,
)
```

`SESSION` derives Lobby / Playing / Result exclusively from `session.phase`; no stale, duplicated game route. The shell never receives authority state, opponents' hands, shuffle state, random seeds, or reconnect credentials. Game UI receives only the safe projection from this state. Typed problem code/recovery and operation identity are preferred over free-form transport messages; copy belongs to the UI resources.

User actions: `navigate(screen)`, `setDisplayName`, `setJoinAddress`, `host()`, `join()`, `startPractice()`, `setReady(Boolean)`, `startGame()`, `leaveSession()`, `retryConnection()`, `dismissProblem()`, `updateSettings(...)`, `requestBack(): Boolean`, `dismissLeaveConfirmation()`. `requestBack()` returns false at Home so the platform can handle its default; elsewhere it navigates or requests the shared leave dialog. Gameplay has its own callbacks mapped to the same controller. Platform owner calls `setForeground(Boolean)`, `setSystemReduceMotion(Boolean)`, and `close()`; composable recomposition never creates or tears down the session. Android owner handles system back and edge-to-edge; common root handles safe inset padding. No extra controller is created per screen.

Copy/share/scan, operation cancellation, authority-provided `SessionControls`, effective reduced motion, and shared back confirmation are implemented through the controller. Host/Join busy state includes initial and retried connections. The game receives foreground state and `privacyEpoch`, which requires a fresh hand reveal after backgrounding even if lifecycle collection skipped the inactive value. The shell offers hosts a confirmed return to the lobby when a disconnected seat pauses a match and the authority permits that action. The official common [ui-backhandler source](https://github.com/JetBrains/compose-multiplatform-core/blob/jb-main/compose/ui/ui-backhandler/src/commonMain/kotlin/androidx/compose/ui/backhandler/BackHandler.kt) currently marks BackHandler experimental and deprecated in favor of NavigationEventHandler, so it is not added just for the shell. iOS visible back is provided; native gesture integration is verified by the platform owner rather than inferred from custom route state.

## Motion, accessibility, and performance acceptance

- Motion reinforces events: roughly 150–220 ms route/press changes and 250–350 ms decorative card settling, finalized by visual review. No animation gates a required action or delays network state. Reduced motion removes movement; immediate feedback and readable event text remain.
- All core actions have visible labels and >=48 dp bounds. TalkBack/VoiceOver order follows title, status, fields/roster, primary action. Ready/connection states include words. Errors use polite live-region announcements when suitable and are not emitted every frame.
- User text scaling at 200%, a 320 dp compact width, short landscape height, and a >=600 dp wide window must preserve every action through reflow/scroll. Text does not shrink to fit, and fixed-height labels do not clip.
- Root applies safe insets once; forms use keyboard-aware scrolling. Verify gesture bars, iOS notch/home indicator, split view, keyboard, and rotate/recreate behavior on actual target builds.
- `AppUiState` is immutable; screen functions are stateless outside ephemeral confirmation/focus/scroll UI. Lists use stable player IDs. Network I/O, persistence, invitation generation, and effects do not run during composition.
- Art is original local vector/Compose geometry. Fonts load from the installed bundle. No bitmap-heavy backgrounds, continuously ticking decorative clocks, uncontrolled infinite transitions, or repeated constraint-based subcomposition.
- The sensitive game hand hides whenever platform state becomes inactive/background; a decorative cover is not enough if the underlying semantics still expose cards. This is coordinated with game/controller/platform owners.

## Validation and dependencies

1. Coordinator passes Kotlin/KMP/Compose/Android smoke and independent environment review before major shell implementation.
2. Freeze controller/session/game models and the font/vector resource names, then implement the shared theme and stateless shell screens.
3. Compile common + Android + optional desktop targets against resolved APIs. Use desktop screenshots as rapid visual evidence; do not call them Android/iOS device verification.
4. Run meaningful navigation/session tests: Home→Host→Lobby, invalid Join retains input, busy operation cancels, Back from an active table confirms, host loss recovers without stale game UI. Domain/game rules remain tested by their owners.
5. Obtain design review at the first actual home/lobby render, after game integration, and at final small/large-font layouts. Correct weak hierarchy and clipped controls before adding decorative polish.
6. macOS CI validates iOS compilation/XCTest where available. Physical-device VoiceOver, LAN permission, keyboard, hand privacy/app switcher, touch, and haptics are explicitly recorded as device verification when performed, otherwise documented as open.

## Completed shared-shell qualification

Final focused run: **2026-09-09 17:02 UTC**, `ShellLayoutTest`: **10 tests, zero failures or errors**; JVM compilation and the test task completed successfully in 15 seconds. Stable local evidence is `/tmp/partydeck-shell-ui5.log` and `/tmp/partydeck-shell-ui5-results/TEST-dev.partydeck.app.ShellLayoutTest.xml`. Screenshots are generated under `composeApp/build/ui-snapshots/`.

| Check | Executed evidence |
| --- | --- |
| Home reflow | `HomeLayoutTest` passed all four cases after the final Home changes: 390×844, 320×740 at 200% text, 844×390 short landscape, and 1000×700. Host, Join, Practice, How to play, and Settings remain reachable. Independent review accepted the intact enlarged wordmark and the compact landscape composition. |
| Six-seat lobbies | Host and guest fixtures at 360×640 and 320×740/200% preserve every player name and the Start/Ready actions. Normal text docks the primary action; enlarged text uses page scrolling. Guest readiness toggles both ways, and pending actions disable duplicate submission. Redundant ready checkmarks are omitted at large text so long names retain their width. |
| Constrained Join | At 320×420/200%, edited name and full invitation survive a connection problem. Recovery and dismissal remain visible together, and reconnecting state disables the form even when the initial pending action is clear. This is a constrained viewport fixture, not a native keyboard test. |
| Global recovery | An actual `PartyDeckController` and its authority runtime receive a synthetic transport startup failure. The bounded error panel leaves Home usable; Retry and Dismiss are visible immediately while only the explanation scrolls. Retry reaches the controller and dismissal restores navigation. |
| Paused match | The host's authority-permitted Return to lobby action stays visible in the bounded status banner. The 200% confirmation keeps both actions reachable and ends the match only after confirmation. Duplicate paused-player names use the same seat labels as gameplay. |
| Invitation transfer | The real QRose dialog rendered at 320 dp decodes with ZXing to the exact canonical synthetic invitation, retaining the full 64-character certificate fingerprint. Share, Copy, and Done are reachable. The Android owner additionally decoded this same 272×272 pixel fixture through production `QrInvitationDecoder` at all four rotations. This verifies image decoding, not a physical camera scan. |
| Settings | At 320×740/200%, all three preference switches remain reachable, readable, and functional. Descriptions reflow below the title/switch row. |
| Complete legal text | The actual final **258,084-byte** bundled aggregate renders in **222 bounded sections**. Test reassembly equals the complete source text; no section exceeds the 1,500-character acceptance bound (implementation cap: 1,200). Initial credits, first notice, and final legal text are reachable at 320×740/200%; Done stays visible and closes the dialog. The verified bundle SHA-256 is `1cbfc067e97159c272953f363f5b0729faa656a55b1bf76c0c9200c6dd90a455`. |

The design reviewer independently inspected the corrected Home/lobby/error/Settings/confirmation images and the final license start/first/end images, then independently checked the preserved ten-case XML. No mandatory shell visual correction remains from these fixtures. Reproduce the final shell checks with `xvfb-run -a ./gradlew :composeApp:jvmTest --tests dev.partydeck.app.ShellLayoutTest --console=plain` on Linux with the configured JDK/SDK.

The shell uses resource-backed copy, the bundled fonts/vectors, native service callbacks, and controller-owned state throughout. Android's `testTagsAsResourceId` stays in the Android owner; common code uses portable test tags. JVM fixtures do not qualify native IME behavior, safe areas, TalkBack/VoiceOver, physical cameras, native sharing, or platform lifecycle/privacy behavior. Those remain with the Android/iOS execution evidence and device qualification recorded in the platform and release documents.
