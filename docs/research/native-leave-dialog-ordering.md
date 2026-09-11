# Shared Leave dialog after native close

Native Leave keeps its immediate shared intent, which blocks authority submissions and new native
selection and conceals the returning hand. The shared app now creates LeaveTableDialog only when
the presentation lifecycle is COMPOSE. Selecting COMPOSE is insufficient: stop selects Standard
while the native presentation still has lifecycle CLOSING.

For a successful iOS close, IosGodotPresentationHost.NativeSession.close awaits the native
completion callback. GodotPresentationPort completes that callback after both native dormancy and
UIKit dismissal. EmbeddedPresentationCoordinator.completeClose then publishes lifecycle COMPOSE.
The new rendering condition uses that existing boundary. It adds no timer, deferred exit callback,
framework retry, platform API, or dependency change. Standard's native return still requests no
Leave dialog; Back in the shared table still requests its dialog immediately.

The controller's intent remains unchanged throughout closing. Cancel still preserves the same
session. Clearing the session, replacing it through the existing runtime path, or closing the
controller clears the intent before a late native completion can expose a dialog. Navigating from
cleared Home to Settings is covered; this change does not redefine navigation within a retained
table.

## Pinned framework source

Compose UI 1.12.0's official annotated tag v1.12.0 resolves through tag object
5290ec35fa8f0aff7ff153765e74f9feb61001a0 to core commit
f29d2f99f3beafc60992c6a73dbbaa9f841c5d4c.

- [Dialog.skiko.kt](https://github.com/JetBrains/compose-multiplatform-core/blob/f29d2f99f3beafc60992c6a73dbbaa9f841c5d4c/compose/ui/ui/src/skikoMain/kotlin/androidx/compose/ui/window/Dialog.skiko.kt)
  creates a focusable scene layer before running its appearance animation.
  SHA-256: 73663622a20df26884293c57e49eb6c72d318bb8c8776763f3b0fec60a5c00ca.
- [ComposeLayersViewController.ios.kt](https://github.com/JetBrains/compose-multiplatform-core/blob/f29d2f99f3beafc60992c6a73dbbaa9f841c5d4c/compose/ui/ui/src/iosMain/kotlin/androidx/compose/ui/scene/ComposeLayersViewController.ios.kt)
  calls show for the first attached layer. Lines 182–197 find the hosting view's ancestor immediately
  beneath the current window; show returns if that ancestor is absent. Lines 223–235 attach the
  layer. SHA-256: afbc15729c835b9ca806360b0e0d30d1185f488815bcfa0754e06c1bc95d2bc9.
- [ComposeContainer.ios.kt](https://github.com/JetBrains/compose-multiplatform-core/blob/f29d2f99f3beafc60992c6a73dbbaa9f841c5d4c/compose/ui/ui/src/iosMain/kotlin/androidx/compose/ui/scene/ComposeContainer.ios.kt)
  updates window context when the host moves and resumes scene work in sceneDidAppear.
  Neither path retries the layer's show. SHA-256:
  384305efd1678dbb72c4aacb17f82628c2ebe04f7b07ab8153b20f1810fa0cc5.
- [CMPViewController.m](https://github.com/JetBrains/compose-multiplatform-core/blob/f29d2f99f3beafc60992c6a73dbbaa9f841c5d4c/compose/ui/ui-uikit/src/iosMain/objc/CMPUIKitUtils/CMPUIKitUtils/CMPViewController.m)
  calls composeContainerWillAppear from viewWillAppear without requiring view.window
  (lines 134–150). Its structural hierarchy check also follows parent and presenting controllers
  when view.window is nil (lines 56–65). Independently verified source SHA-256:
  c7f26b962bac140da1e6e97bd9beb897891b9d616dce0c59ed7772fe59b170da.
- [ComposeContainerLifecycleDelegate.ios.kt](https://github.com/JetBrains/compose-multiplatform-core/blob/f29d2f99f3beafc60992c6a73dbbaa9f841c5d4c/compose/ui/ui/src/iosMain/kotlin/androidx/compose/ui/window/ComposeContainerLifecycleDelegate.ios.kt)
  marks the container appeared at composeContainerWillAppear, allowing STARTED/RESUMED from scene
  facts before didAppear (lines 90–104). SHA-256:
  abde56944cd58c7271c38fb23b48783dd1118573acd6a57b98c69800162b75a8.

These sources establish an attachment-order risk when shared confirmation is created during native
return. Disabling dialog animation would not order initial layer attachment after native dismissal.

## Tests and limits

PresentationLeaveConfirmationTest drives the actual PartyDeckController and PartyDeckApp with
real practice rules and a contract-only host that can hold native close completion. It covers both
modes with immediate and delayed close, absence of the actual dialog layer while closing, exactly
one enabled dialog after release, an otherwise legal play rejected by the immediate intent guard,
native re-entry rejection, cancel preserving the same session, native Standard return, shared Back
and confirm, cleared intent across replacement/Home-to-Settings/owner-close, and false/timeout
fallback. Controller time is explicit virtual time; the tests add no production sleep.

Run the focused test after integration:

    ./gradlew :composeApp:jvmTest --tests dev.partydeck.app.PresentationLeaveConfirmationTest

On 2026-09-11, all four new test methods and both existing PresentationPickerDisposalTest methods
passed on JVM, with zero failures, errors or skipped tests. The new methods exercise ten scenarios.

These shared UI tests do not execute UIKit or Godot. Independent review of #46 records two failed
cases: both original failure screenshots lack the requested dialog, while linked last-validated
observations report the Leave intent and successful native closure. That evidence supports testing
this attachment-order correction; it does not establish the internal cause or change the failed
run. Fresh native execution remains required.

Failed-close behavior is preserved. The coordinator also publishes COMPOSE after a failed or
timed-out close. Swift's deadline path may initiate its fallback dismissal without waiting for that
dismissal's completion. COMPOSE on this path is therefore not proof that UIKit detached. The test
checks the existing shared fallback and retained intent, without treating a failed close as a
successful native disposal.
