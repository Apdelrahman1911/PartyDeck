# Shared Android Godot runtime

This Android library supplies the runtime plugin, bounded render-thread queues,
confirmed-exit helper and verified renderer assets. The comparison application
uses the same implementation that the session-powered Android host consumes.
It contains no game authority, session credentials or practice bot driver.

The owning Activity installs `PartyDeckBridgePlugin` through `getHostPlugins()`.
Consumer R8 rules preserve its reflected Godot methods. A production owner must
disable input immediately with `setInputEnabled(false)`, then enable it only
after the common bridge accepts Ready, the current foreground command is
delivered, and the native owner observes fresh draws. Losing focus disables
input synchronously; an earlier queued player event cannot become valid after
resume. Ready, failure and exit events remain available while covered.

Both Gradle builds map this directory to `:androidRenderer`. Before packaging,
export the renderer with `godot/tools/renderer.py pack`; `stageGodotAssets` checks
the PCK receipt against current sources on every build. The library shares the
canonical 19 notice files under `../android-host/src/main/assets/notices`.

Run `:androidRenderer:testDebugUnitTest` for queue, privacy-generation and exit
behavior, and `:androidRenderer:lintDebug` for Android source checks. These checks
do not replace native input, lifecycle or production-session qualification.

Build APIs were checked against [Android library guidance](https://developer.android.com/studio/projects/android-library),
[AGP built-in Kotlin](https://developer.android.com/build/migrate-to-built-in-kotlin)
and the pinned AGP 9.3.1 `SourceDirectories` API. Native APIs retain the verified
Godot 4.7.2 AAR and Fragment 1.8.6 dependencies used by the comparison host.
