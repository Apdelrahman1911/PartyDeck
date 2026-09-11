# Presentation picker disposal before native entry

The presentation picker captures a native choice in the coordinator at the click. Its existing
session generation, recipient, preferences and five-second selection deadline remain attached to
that choice. A picker-owned acknowledgement adds a disposal condition to the existing foreground
and native-close conditions. It neither grants focus nor starts a new timeout. Removing the picker
or replacing its controller cancels the acknowledgement, including after disposal when focus is
still pending. Coordinator updates continue to invalidate the captured choice on context changes.

The picker invokes the acknowledgement from `SideEffect` after its conditional `AlertDialog` has
left the composition. This is paired with local nonanimated dialog properties on Skiko platforms:

- Compose UI **1.12.0**, `skikoMain/androidx/compose/ui/window/Dialog.skiko.kt`, disposes through
  `DialogAppearanceController.hideDialog`. The animated branch closes its scene layer only after
  replacement content and an animation coroutine complete; the nonanimated branch calls
  `layer.close()` synchronously. `animateTransition` is a Skiko-only experimental property, so a
  small platform properties factory keeps it out of common code and leaves Android properties at
  their defaults. Only this picker changes; no global animation flag or dependency version changes.
- Compose runtime **1.12.0**, `commonMain/androidx/compose/runtime/Effects.kt`, specifies that all
  `DisposableEffect` and `RememberObserver` callbacks precede `SideEffect` on the apply dispatcher.
- Material3 **1.9.0** passes `AlertDialog` properties through to that `Dialog` implementation.

Authoritative published sources inspected for these decisions:

- [Compose UI simulator source archive](https://repo.maven.apache.org/maven2/org/jetbrains/compose/ui/ui-iossimulatorarm64/1.12.0/ui-iossimulatorarm64-1.12.0-sources.jar)
- [Compose runtime common source archive](https://dl.google.com/dl/android/maven2/androidx/compose/runtime/runtime/1.12.0/runtime-1.12.0-sources.jar)
- [Material3 UIKit source archive](https://repo.maven.apache.org/maven2/org/jetbrains/compose/material3/material3-uikitarm64/1.9.0/material3-uikitarm64-1.9.0-sources.jar)

The shipping diagnostic showed an invisible, nonhittable picker in accessibility queries while the
native 2D table was visible. It did not measure which internal Compose stage was pending. The
correction establishes disposal ordering without assuming a particular starvation stage. The
strict native picker-absence assertion and full shipping route remain execution gates.
