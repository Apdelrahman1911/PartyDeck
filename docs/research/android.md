# Android platform research

Verified against the official sources below on **2026-09-09**. Android platform ownership is `androidApp/src` and `composeApp/src/androidMain`; the coordinator owns Gradle, versions, and release signing. Source verification is separate from successful build and device qualification.

## Shipping baseline

- **Approved:** `applicationId = dev.partydeck.app`, compile SDK **37.1**, `targetSdk = 36`, `minSdk = 26`. The higher compile SDK satisfies the selected current AndroidX dependencies; the target SDK remains 36. The minimum SDK is our product support decision, not a Compose requirement.
- Google Play has required new phone/tablet apps and updates to target **Android 16 / API 36 since August 31, 2026**. The current official page was updated September 1, 2026. API 35 is no longer sufficient for a new PartyDeck submission. [Target API requirements](https://developer.android.com/google/play/requirements/target-sdk)
- Use a separate Android application module and the supported Android KMP library plugin in shared modules. Do not use a combined KMP + `com.android.application` module under modern AGP. [Android KMP plugin](https://developer.android.com/kotlin/multiplatform/plugin)
- Keep release signing credentials external to the repository. Build a release AAB and inspect its merged manifest and packaged libraries before store submission. Store accounts, signing identity, listing/rating declarations, and real devices are external qualification steps.

## Application and shared-library layout

`androidApp` applies `com.android.application` and the Kotlin Compose compiler plugin. AGP 9 enables built-in Kotlin; it replaces `org.jetbrains.kotlin.android` for the application module. Shared modules still apply Kotlin Multiplatform plus `com.android.kotlin.multiplatform.library`. [Built-in Kotlin migration](https://developer.android.com/build/migrate-to-built-in-kotlin)

The shared Android target uses `kotlin { android { ... } }`. The official Android KMP guide says `androidLibrary {}` is deprecated on modern AGP, and Android resources and Android host/device tests require explicit opt-in. Shared Android resources belong in `src/androidMain/res`; application resources and the launcher manifest belong in `androidApp/src/main`. [Plugin configuration and migration](https://developer.android.com/kotlin/multiplatform/plugin)

The coordinator's Kotlin 2.4.20 / AGP 9.3.1 selection is within the current JetBrains compatibility table. Do not copy the Android guide's illustrative dependency versions as a compatibility matrix. [KMP compatibility](https://www.jetbrains.com/help/kotlin-multiplatform-dev/multiplatform-compatibility-guide.html)

Verified Google Maven metadata lists stable `androidx.activity:activity-compose:1.13.0` and `androidx.lifecycle:lifecycle-viewmodel-ktx:2.11.0` / `lifecycle-runtime-ktx:2.11.0`. Higher listed versions are prereleases. The coordinator keeps these in the version catalog. [Activity metadata](https://dl.google.com/dl/android/maven2/androidx/activity/activity-compose/maven-metadata.xml), [ViewModel metadata](https://dl.google.com/dl/android/maven2/androidx/lifecycle/lifecycle-viewmodel-ktx/maven-metadata.xml), [Lifecycle metadata](https://dl.google.com/dl/android/maven2/androidx/lifecycle/lifecycle-runtime-ktx/maven-metadata.xml)

## LAN permissions and discovery

The current official local-network documentation is explicit about target SDK differences:

| App target | Android local-network behavior | PartyDeck action |
| --- | --- | --- |
| API 36 or lower | `INTERNET` implicitly grants LAN access, including on Android 17. | Declare `INTERNET`. **Do not declare or request `ACCESS_LOCAL_NETWORK` yet.** |
| API 37 or higher | LAN access is blocked by default unless permission or a documented system-mediated exception applies. | Before raising target SDK, add and request `ACCESS_LOCAL_NETWORK` at the user-initiated host/join/discovery entry point. Handle denial and revocation. |
| Android 16 opt-in test mode | The compatibility opt-in temporarily uses `NEARBY_WIFI_DEVICES`. | Keep this in a targeted compatibility test, not the production API 36 permission flow. |

`ACCESS_LOCAL_NETWORK` is part of the existing Nearby Devices permission group. The permission covers incoming and outgoing LAN TCP/UDP as well as local-name resolution. Android 17 offers an NSD system picker that authorizes selected service endpoints without broad LAN permission; that is not a replacement for a host accepting multiple peers. [Local network permission](https://developer.android.com/privacy-and-security/local-network-permission), [Android 17 target changes](https://developer.android.com/about/versions/17/behavior-changes-17)

For platform NSD, Android provides `NsdManager` / DNS-SD service registration and discovery. Use the protocol owner's agreed service type. Start discovery only while users need it, unregister advertisements when hosting stops, and close outstanding callbacks/listeners during teardown. The official guide explicitly calls discovery expensive and recommends stopping it when unnecessary. [Android NSD guide](https://developer.android.com/develop/connectivity/wifi/use-nsd)

PartyDeck's baseline does not scan Wi-Fi SSIDs, use Wi-Fi Direct, create a hotspot, or use Bluetooth; do not add location, Bluetooth, or Wi-Fi scan permissions for ordinary LAN sockets/NSD. Raw multicast is a separate implementation choice: a custom multicast receiver with a `WifiManager.MulticastLock` would require the corresponding multicast permission. Platform NSD should not acquire an app multicast lock speculatively. The transport owner implements discovery and sockets; the Android shell owns any future permission UI.

`ACCESS_NETWORK_STATE` is only needed if the implementation queries connectivity state. CameraX `camera-view` pulls in `camera-video`, which pulls in Media3; `media3-common:1.9.0` declares this permission. Inspection of the published CameraX 1.6.2 sources and the app's NSD/socket adapter found no connectivity queries or use of Media3's lazily initialized `NetworkTypeObserver`. The application manifest explicitly removes the unused permission. The NSD adapter uses the ordinary `registerService`, `discoverServices`, and `resolveService` APIs under `INTERNET`. [CameraX published sources](https://dl.google.com/dl/android/maven2/androidx/camera/camera-view/1.6.2/camera-view-1.6.2-sources.jar), [Media3 published sources](https://dl.google.com/dl/android/maven2/androidx/media3/media3-common/1.9.0/media3-common-1.9.0-sources.jar)

No foreground service or notification permission is required for the approved foreground game design. Background hosting continuity is not guaranteed.

## Lifecycle, orientation, and safe areas

- Use `ComponentActivity`, Compose content, and AndroidX back APIs. Android 16 enables predictive back by default for target 36; do not override legacy `onBackPressed()` or disable the new behavior as a shortcut. Shared navigation should consume back through the Compose/AndroidX integration. [Predictive back](https://developer.android.com/develop/ui/compose/system/predictive-back)
- Keep the controller/session owner in an `AndroidViewModel` so a configuration change does not create a new host, discard a hidden hand, or duplicate network listeners. The retained owner may hold the application context, not the Activity, window, or a strong View reference. The current window's View is attached weakly for haptics and detached on Activity destruction. [ViewModel](https://developer.android.com/topic/libraries/architecture/viewmodel)
- Treat interactivity and actual OS background as separate signals. `setForeground` is true only while the Activity is resumed and its window has focus, so a permission dialog or chooser immediately hides the hand, clears its reveal state, and stops audio. `setBackgrounded` follows `onStart` / `onStop` and controls LAN-client suspension/reconnect. Suppress backgrounding during `isChangingConfigurations`, preserving the retained session and client socket through rotation. Ignore callbacks from an obsolete Activity after a replacement attaches to the owner. Permanently clearing the owner closes feedback and the controller/session scope. [Activity lifecycle and configuration API](https://developer.android.com/reference/android/app/Activity#isChangingConfigurations())
- Process death is different from rotation. Keep session secrets and authoritative cards in memory; an app process restart should return to a valid entry flow rather than restore a half-valid game snapshot. Reconnect policy belongs to the session/controller layer.
- Use edge-to-edge content and protect interactive content with the appropriate Compose insets. API 36 removes the edge-to-edge opt-out on Android 16. Backgrounds may draw behind system bars; controls and text must remain clear of bars, display cutouts, and the keyboard. Avoid applying both root and screen inset padding to the same edge. [Insets](https://developer.android.com/develop/ui/compose/system/insets), [Android 16 changes](https://developer.android.com/about/versions/16/behavior-changes-16)
- Support both portrait and landscape and window resizing; do not lock orientation. Android 16's large-screen restriction changes have a documented game-category exception, so they must not be described as applying universally to games. Responsive PartyDeck layouts remain the product decision independent of that exception. Test narrow-height landscape and `sw600dp` layouts.
- Apply `FLAG_KEEP_SCREEN_ON` only during an active table/game. Android automatically permits the display to sleep when such an Activity is backgrounded. No wake lock is needed. [Keep the screen on](https://developer.android.com/develop/background-work/background-tasks/awake/screen-on)

### Private hands and inactive windows

Before drawing the Activity, disable Recents screenshots on API 33+ with `setRecentsScreenshotEnabled(false)`. This API specifically excludes the Activity's screenshot from Recents while preserving normal user screenshots. On API 26–32, set `FLAG_SECURE` while a session exists, including on Activity recreation before the first frame. [Activity API](https://developer.android.com/reference/android/app/Activity#setRecentsScreenshotEnabled(boolean)), [Secure window guidance](https://developer.android.com/security/fraud-prevention/activities)

An opaque native cover appears immediately on pause or loss of window focus while a session exists; it also hides the Compose accessibility subtree. Restore only when both resumed and focused. The same interactivity change clears shared private-hand reveal state and stops feedback; it does not suspend LAN clients until actual OS background. The cover does not depend on asynchronous Compose recomposition finishing before a snapshot. The camera scanner also excludes its preview from Recents. Older manufacturer behavior still requires device qualification; the secure-window documentation notes limitations on older Android releases.

Android's `ValueAnimator.areAnimatorsEnabled()` (API 26+) exposes the system animation setting and applicable system disabling, and feeds the controller's system-reduced-motion preference on resume. [ValueAnimator API](https://developer.android.com/reference/android/animation/ValueAnimator#areAnimatorsEnabled())

## Native service contract

The shared controller owner freezes these public interfaces in `dev.partydeck.app.controller`; platform implementations use constructor injection rather than platform checks throughout common UI:

- `AppSettings(displayName, soundEnabled, hapticsEnabled, reduceMotion)`.
- `SettingsStore`: suspending `load()` and `save(settings)`.
- `Feedback`: `play(cue, settings)`, `setForeground(Boolean)`, and `close()`.
- `PlatformServices`: `settingsStore`, `feedback`, `gameRandom(): Random`, `secureToken(): String`, `copyText`, `shareText`, `showsCopyConfirmation`, `canScanInvitation`, and callback-based `scanInvitation`.
- Cues: `CLICK`, `CARD_PLAY`, `CHALLENGE`, `ROUND_END`, `LIGHT_OUT`, `WIN`.

Every production `gameRandom()` output comes directly from Android's `java.security.SecureRandom` through the standard `asKotlinRandom()` adapter. A seeded deterministic generator is not appropriate for secret authoritative outcomes, even when its initial seed is secure. `secureToken` uses **32 directly generated CSPRNG bytes encoded as 64 lowercase hexadecimal characters**, separate from game randomness. [SecureRandom](https://developer.android.com/reference/java/security/SecureRandom), [Kotlin adapter](https://kotlinlang.org/api/core/kotlin-stdlib/kotlin.random/as-kotlin-random.html)

### Settings

Android recommends DataStore for asynchronous, consistent, transactional persistence; its official KMP documentation currently lists Preferences DataStore 1.2.1. [DataStore KMP](https://developer.android.com/kotlin/multiplatform/datastore)

For four small settings the coordinator explicitly selected dependency-free native `SharedPreferences`, isolated behind `SettingsStore`. Perform load and checked `Editor.commit()` on `Dispatchers.IO`; surface failed writes instead of pretending they succeeded. Serialize full-setting writes in the controller/store so rapid toggles cannot persist stale snapshots. Do not persist hidden cards or reconnect credentials in settings.

`Editor.commit()` returns whether the preferences were successfully written to persistent storage; it is synchronous, which is why this implementation uses the IO dispatcher. [Editor API](https://developer.android.com/reference/android/content/SharedPreferences.Editor#commit())

Make backup policy explicit. `allowBackup=false` alone does not disable every manufacturer's device-to-device transfer on Android 12+; use `dataExtractionRules` when exclusion is required. [Android backup](https://developer.android.com/identity/data/autobackup)

### Sound and haptics

Use a small `SoundPool` with game/sonification audio attributes and a fixed concurrent-stream limit. The official API documents a one-megabyte decoded limit per sample, asynchronous sample loading, and mandatory resource release. Wait for successful `OnLoadCompleteListener` notification before playing a sample. Stop any active cue on backgrounding and release the pool at owner teardown. Do not queue stale gameplay cues to play when loading finishes. [SoundPool](https://developer.android.com/reference/android/media/SoundPool)

The asset owner provides original mono PCM WAV files at 44,100 Hz / 16-bit, under `composeResources/files/audio/`:

| Cue | File |
| --- | --- |
| CLICK | `ui_tap.wav` |
| CARD_PLAY | `card_place.wav` |
| CHALLENGE | `challenge.wav` |
| ROUND_END | `safe.wav` |
| LIGHT_OUT | `light_out.wav` |
| WIN | `victory.wav` |

Load shared files with suspending `Res.readBytes("files/audio/...")` on IO and write small cache files for SoundPool. This avoids a second platform-specific asset copy and does not depend on a generated Android asset directory name. Compose officially supports raw resources and packages them as Android assets. [Compose resource usage](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-multiplatform-resources-usage.html)

Use `View.performHapticFeedback` with action-oriented `HapticFeedbackConstants`. This respects system haptic preferences and does not need `VIBRATE`. `CONFIRM` / `REJECT` require API 30; use older action constants on API 26–29. Do not use flags that override system settings. [Haptic feedback guide](https://developer.android.com/develop/ui/views/haptics/haptic-feedback), [Haptic constants reference](https://developer.android.com/reference/android/view/HapticFeedbackConstants)

Sound and haptic settings are independent. Reduced motion is consumed in common UI. A background or closed feedback service must ignore new cues. If audio focus is requested, respect focus loss and abandon the same request when finished; target 35+ can request focus only while topmost or running an appropriate foreground service. PartyDeck must not introduce a foreground service to play short effects. [Audio focus](https://developer.android.com/media/optimize/audio-focus)

The implementation requests transient focus with ducking only for ready-to-play clips, stops on focus loss, and abandons focus after the generated clip duration plus a short decoder tail. It tracks at most four stream IDs and does not grow a list of historical playback handles. Exact clip durations are in `assets/audio_manifest.json`.

### Invitations: copy, share, and offline scan

Copy and share happen only after explicit user actions. Mark clipboard invitations sensitive using `ClipDescription.EXTRA_IS_SENSITIVE` before `setPrimaryClip`; the shared controller shows a copied confirmation only below API 33 because newer Android already displays one (`showsCopyConfirmation`). Launch the standard Sharesheet with `ACTION_SEND`, MIME type `text/plain`, and `Intent.createChooser`. Keep the attached Activity weak and detach it by identity so a rotating window cannot leak. [Clipboard guidance](https://developer.android.com/develop/ui/views/touch-and-input/copy-paste), [Android Sharesheet](https://developer.android.com/training/sharing/send)

The approved offline scanner is **CameraX 1.6.2** (`camera-camera2`, `camera-lifecycle`, `camera-view`) plus **ZXing core 3.5.4**, scoped to QR decoding. CameraX's current release table identifies 1.6.2 as stable; its code example also lists a newer alpha, which we deliberately do not copy. ZXing's official 3.5.4 release is dated November 11, 2025. Its README describes maintenance mode with fixes and minor enhancements; that is an accepted tradeoff for this mature, bounded decoder. We do not embed the unsupported old ZXing Barcode Scanner app. [CameraX releases](https://developer.android.com/jetpack/androidx/releases/camera), [ZXing release](https://github.com/zxing/zxing/releases/tag/zxing-3.5.4), [ZXing status](https://github.com/zxing/zxing)

Alternatives researched: Google Code Scanner requires an unbundled module downloaded before use. ML Kit's bundled barcode library 17.3.0 makes its model immediately available but adds approximately 2.4 MB and its SDK/privacy integration. The approved ZXing decoder needs neither a model download nor cloud processing. [Google Code Scanner](https://developers.google.com/ml-kit/vision/barcode-scanning/code-scanner), [ML Kit barcode integration](https://developers.google.com/ml-kit/vision/barcode-scanning/android)

The separate scanner Activity requests `CAMERA` only after Scan is chosen. Camera hardware is optional in the manifest, preserving manual invitation entry on devices without cameras. Denial provides an explanation and retry/settings action; cancel returns to Join. Bind CameraX to the Activity lifecycle, use keep-only-latest analysis backpressure and a single worker, throttle decoder work, honor Y-plane row and pixel strides, and close every `ImageProxy` in `finally`. Clear the copied luminance buffer after each attempt, clear the analyzer/unbind camera/shut down its worker on destruction, and never save images or log QR contents. [CameraX analysis](https://developer.android.com/media/camera/camerax/analyze), [Preview](https://developer.android.com/media/camera/camerax/preview), [Activity result API](https://developer.android.com/training/basics/intents/result)

Only a successfully parsed `LanInvitation` of at most 2,048 characters is returned. Scanning fills the Join field; it does not automatically connect. All four pure decoder tests pass, covering exact invitation recovery through padded/interleaved camera memory, quarter-turn orientation, invalid/oversized QR payloads, and truncated-plane rejection. The shared renderer's `ShellLayoutTest` also exports a synthetic 272 × 272 px invitation QR at a 320 dp viewport. That actual PNG passed the compiled Android decoder and canonical invitation parser at all four rotations, preserving the exact payload and full 64-character certificate pin. Camera frame capture and physical scanning remain device checks.

The assets owner bundles ZXing's Apache 2.0 license and NOTICE, AndroidX's Apache 2.0 license, and CameraX's additional published libyuv notices. Dependency provenance is recorded in `assets/software_notice_sources.json`.

### Bundled typography and startup

CameraX's UI dependencies also bring in Emoji2 1.4.0. Its default `EmojiCompatInitializer` configures a system downloadable-font provider and requests its font shortly after the first resume. PartyDeck uses bundled typography and has no need for that automatic provider request. The manifest removes only `androidx.emoji2.text.EmojiCompatInitializer` metadata using the exact AndroidX opt-out recipe, preserving `ProcessLifecycleInitializer` and `ProfileInstallerInitializer`. Normal system text/emoji fallback remains available. [EmojiCompat initializer API](https://developer.android.com/reference/androidx/emoji2/text/EmojiCompatInitializer), [exact published 1.4.0 sources](https://dl.google.com/dl/android/maven2/androidx/emoji2/emoji2/1.4.0/emoji2-1.4.0-sources.jar)

App Startup 1.2.0 is an explicit application dependency because the manifest directly references `InitializationProvider`. Relying only on CameraX's runtime dependency packaged the class but left the manual manifest reference absent from the lint/compile classpath. [App Startup 1.2.0 artifact](https://dl.google.com/dl/android/maven2/androidx/startup/startup-runtime/1.2.0/startup-runtime-1.2.0.pom)

## Packaging and qualification

Use an original adaptive launcher icon, app label, dark launch background matching the app, explicit exported launcher Activity, and `android:appCategory="game"`. Keep app-private state out of logs. Release manifests should not accidentally gain unneeded permissions from dependencies.

Inspect packaged `.so` files even when PartyDeck has no direct native dependency: libraries can bring native code transitively. The current official page states target-35+ Play apps must support 16 KB memory page sizes on 64-bit devices and that updates without support are blocked starting **February 1, 2027**. This current page differs from older published deadlines; verify again before submission. AGP 8.5.1+ handles 16 KB ZIP alignment, NDK r28+ builds 16 KB-aligned ELF by default, but prebuilt libraries still need verification. Use `zipalign -c -P 16 -v 4` for APK alignment and inspect bundle alignment configuration. [16 KB page sizes](https://developer.android.com/guide/practices/page-sizes)

Required Linux checks after integration: shared Android compilation, debug APK assembly, Android lint, release assembly/bundle, manifest and asset inspection. Do not substitute successful compilation for lifecycle/discovery verification.

### First integrated Android qualification milestone

On 2026-09-09, the following command completed successfully in **1 minute 6 seconds**, including optimized release shrinking. This is implementation-milestone evidence; later UI and license-notice edits require the coordinator's final validation again.

```sh
flock /tmp/partydeck-gradle.lock ./gradlew \
  :androidApp:assembleDebug :androidApp:testDebugUnitTest \
  :androidApp:lintDebug :androidApp:bundleRelease --console=plain
```

- Four QR decoder tests passed, with zero failures, errors, or skips. The recorded run began at `2026-09-09T16:42:21.970Z`.
- Lint completed with zero errors. Its five warnings were the intentional target-36 baseline, the older-device-ignored predictive-back manifest attribute, two launcher-resource variant advisories (the API-33 icon has its monochrome layer), and a dependency-wide Bouncy Castle trust-manager finding forwarded for independent security reachability review. No broad lint baseline was added.
- Debug APK: 22,590,680 bytes; SHA-256 `2ff5e86d72e30fe5c7a9f6d7a15742d7323cd682ab1944b2ac6f0c84bc01ebfb`.
- Optimized unsigned release AAB: 7,588,784 bytes; SHA-256 `17ac426c4608d945eb2b3135db54eeb715e21f2e05297b1b5d268af71223064c`. No archive signing entries were present; this is not a signed production deliverable.
- Debug and release merged manifests contained `INTERNET`, `CAMERA`, and AndroidX's internal signature permission, with only lifecycle/profile-installer startup metadata. Neither the network-state permission nor the emoji-font initializer remained.

### Runtime smoke evidence and limits

The accelerated Android job in [CI run 34378549932](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34378549932) installed the app and returned a successful cold launch in 6,745 ms. Its screenshot showed the rendered Home screen behind a **System UI** ANR dialog. The active accessibility tree contained that system dialog, so the first Home selector timed out. This does not establish passed app navigation. The unaccelerated local emulator was also unusable for acceptance and is not counted as device evidence.

The expanded `scripts/smoke-android-ui.py` requires three consecutive fresh trees from the device's resolved HOME Activity before installing the app, and aborts with the actual crash/ANR dialog title instead of disguising a system failure as a missing app tag. It exercises rules, persisted switches across process restart, private-card selection/concealment/background restoration/play, local hosting and invitation actions, invalid-Join editing, and 200% text reachability. The same script accepts debug and **test-signed optimized** variants; its test key is separate from production signing. Actual success is recorded only by a completed per-variant run.

Saved UI/log text redacts invitation bearer URIs. Screenshots are omitted while a live QR invitation or system share preview can be visible. The script restores font and animation settings in `finally` and preserves bounded main/system/crash/events buffers plus the last ANR report for failure diagnosis. The Android-16 source confirms the used `input keycombination` command, `dumpsys activity lastanr`, and the `mInputShown` diagnostic that prevents Back from leaving a form when the emulator has no soft keyboard. [Input command source](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/services/core/java/com/android/server/input/InputShellCommand.java), [Activity diagnostics source](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/services/core/java/com/android/server/wm/ActivityTaskManagerService.java), [IME visibility source](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/services/core/java/com/android/server/inputmethod/ImeVisibilityStateComputer.java)

Device qualification: install and cold launch; API 26 and API 36+ smoke tests; orientation changes during hosting/playing; actual Android↔Android and Android↔iOS LAN host/join/challenge; app background/foreground and host loss; router client isolation; network changes; screen timeout policy; safe areas/IME/font scaling; haptics enabled/disabled; audio mute, focus, loading, and interruption; process restart; 16 KB device/emulator where applicable. When target SDK rises to 37, add permission grant/deny/revocation tests before enabling that target.
