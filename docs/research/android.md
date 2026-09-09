# Android platform research

Verified against the official sources below on **2026-09-09**. Android platform ownership is `androidApp/src` and `composeApp/src/androidMain`; the coordinator owns Gradle, versions, and release signing. Source verification is separate from successful build and device qualification.

## Shipping baseline

- **Approved:** `applicationId = dev.partydeck.app`, `compileSdk = 36`, `targetSdk = 36`, `minSdk = 26`. The minimum SDK is our product support decision, not a Compose requirement.
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

`ACCESS_NETWORK_STATE` is only needed if the final implementation actually queries connectivity state. No foreground service or notification permission is required for the approved foreground game design. Background hosting continuity is not guaranteed.

## Lifecycle, orientation, and safe areas

- Use `ComponentActivity`, Compose content, and AndroidX back APIs. Android 16 enables predictive back by default for target 36; do not override legacy `onBackPressed()` or disable the new behavior as a shortcut. Shared navigation should consume back through the Compose/AndroidX integration. [Predictive back](https://developer.android.com/develop/ui/compose/system/predictive-back)
- Keep the controller/session owner in an `AndroidViewModel` so a configuration change does not create a new host, discard a hidden hand, or duplicate network listeners. The retained owner may hold the application context, not the Activity, window, or a strong View reference. The current window's View is attached weakly for haptics and detached on Activity destruction. [ViewModel](https://developer.android.com/topic/libraries/architecture/viewmodel)
- Forward foreground state when the Activity starts/stops; stop audio and background discovery as appropriate. `onDestroy` during rotation must not terminate a retained session. Permanently clearing the owner closes feedback and the controller/session scope.
- Process death is different from rotation. Keep session secrets and authoritative cards in memory; an app process restart should return to a valid entry flow rather than restore a half-valid game snapshot. Reconnect policy belongs to the session/controller layer.
- Use edge-to-edge content and protect interactive content with the appropriate Compose insets. API 36 removes the edge-to-edge opt-out on Android 16. Backgrounds may draw behind system bars; controls and text must remain clear of bars, display cutouts, and the keyboard. Avoid applying both root and screen inset padding to the same edge. [Insets](https://developer.android.com/develop/ui/compose/system/insets), [Android 16 changes](https://developer.android.com/about/versions/16/behavior-changes-16)
- Support both portrait and landscape and window resizing; do not lock orientation. Android 16's large-screen restriction changes have a documented game-category exception, so they must not be described as applying universally to games. Responsive PartyDeck layouts remain the product decision independent of that exception. Test narrow-height landscape and `sw600dp` layouts.
- Apply `FLAG_KEEP_SCREEN_ON` only during an active table/game. Android automatically permits the display to sleep when such an Activity is backgrounded. No wake lock is needed. [Keep the screen on](https://developer.android.com/develop/background-work/background-tasks/awake/screen-on)

## Native service contract

The shared controller owner freezes these public interfaces in `dev.partydeck.app.controller`; platform implementations use constructor injection rather than platform checks throughout common UI:

- `AppSettings(displayName, soundEnabled, hapticsEnabled, reduceMotion)`.
- `SettingsStore`: suspending `load()` and `save(settings)`.
- `Feedback`: `play(cue, settings)`, `setForeground(Boolean)`, and `close()`.
- `PlatformServices`: `settingsStore`, `feedback`, `secureSeed(): Long`, and `secureToken(): String`.
- Cues: `CLICK`, `CARD_PLAY`, `CHALLENGE`, `ROUND_END`, `LIGHT_OUT`, `WIN`.

`secureSeed` uses a platform CSPRNG for authoritative game seeding. `secureToken` must use **32 directly generated CSPRNG bytes encoded as 64 lowercase hexadecimal characters**; deriving reconnection credentials from a seeded game RNG would expose them if the game RNG state were recovered. Android uses `java.security.SecureRandom`.

### Settings

Android recommends DataStore for asynchronous, consistent, transactional persistence; its official KMP documentation currently lists Preferences DataStore 1.2.1. [DataStore KMP](https://developer.android.com/kotlin/multiplatform/datastore)

For four small settings the coordinator explicitly selected dependency-free native `SharedPreferences`, isolated behind `SettingsStore`. Perform load and checked `Editor.commit()` on `Dispatchers.IO`; surface failed writes instead of pretending they succeeded. Serialize full-setting writes in the controller/store so rapid toggles cannot persist stale snapshots. Do not persist hidden cards or reconnect credentials in settings.

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

## Packaging and qualification

Use an original adaptive launcher icon, app label, dark launch background matching the app, explicit exported launcher Activity, and `android:appCategory="game"`. Keep app-private state out of logs. Release manifests should not accidentally gain unneeded permissions from dependencies.

Inspect packaged `.so` files even when PartyDeck has no direct native dependency: libraries can bring native code transitively. The current official page states target-35+ Play apps must support 16 KB memory page sizes on 64-bit devices and that updates without support are blocked starting **February 1, 2027**. This current page differs from older published deadlines; verify again before submission. AGP 8.5.1+ handles 16 KB ZIP alignment, NDK r28+ builds 16 KB-aligned ELF by default, but prebuilt libraries still need verification. Use `zipalign -c -P 16 -v 4` for APK alignment and inspect bundle alignment configuration. [16 KB page sizes](https://developer.android.com/guide/practices/page-sizes)

Required Linux checks after integration: shared Android compilation, debug APK assembly, Android lint, release assembly/bundle, manifest and asset inspection. Do not substitute successful compilation for lifecycle/discovery verification.

Device qualification: install and cold launch; API 26 and API 36+ smoke tests; orientation changes during hosting/playing; actual Android↔Android and Android↔iOS LAN host/join/challenge; app background/foreground and host loss; router client isolation; network changes; screen timeout policy; safe areas/IME/font scaling; haptics enabled/disabled; audio mute, focus, loading, and interruption; process restart; 16 KB device/emulator where applicable. When target SDK rises to 37, add permission grant/deny/revocation tests before enabling that target.
