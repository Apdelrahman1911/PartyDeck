# iOS Godot session presentation

`PartyDeckOwner` installs one `GodotPresentationPort` on its existing `IosAppHandle`.
The port presents a disposable native table over the existing Compose controller.
Returning to the standard table preserves that session; Leave table reaches its
existing leave confirmation. Installation starts no engine. The first qualified
entry creates the retained `PDGodotEngineOwner`.

## Production target integration

- Compile the Swift files in this directory in the PartyDeck application.
- Set `SWIFT_OBJC_BRIDGING_HEADER` to
  `$(SRCROOT)/PartyDeck/Godot/PartyDeckGodot-Bridging-Header.h` and expose
  `godot/ios-host/modules/partydeck_ios_probe` through the header search path.
- Link the matching retained native engine, camera archive, and required Apple
  frameworks using the native build receipt. The Swift adapter imports the real
  `PartyDeckKit` framework and native header unconditionally.
- Regenerate `PartyDeckKit` with `IosGodotNativePort`, its callback protocols,
  `IosGodotRegistration`, and `IosAppHandle.setPresentationTextScale` exported.
- Bundle the audited pack at
  `ProbeResources/partydeck-last-light.pck`. Its project path is the application's
  resource root. Native code checks this path and the compiled pack digest before
  acquisition; a standalone `project.godot` is unnecessary with this main pack.
- The shipping Info.plist uses `PartyDeckQualifiedGodotPresentations`, which is
  currently empty. For a comparison build, generate a qualification plist and
  expectation using the [app instructions](../../README.md#compare-2d-and-3d).
  That profile selects `PartyDeckQualificationGodotPresentations`, with values
  `2d` and/or `3d`. Without an installed pack and an explicit mode, the adapter
  offers no Godot choice.

The native owner is source-coupled to the pinned Godot build. Its header is
[`PDGodotEngineOwner.h`](../../../godot/ios-host/modules/partydeck_ios_probe/PDGodotEngineOwner.h).
The production target does not use the isolated qualification app or its Kotlin
framework.

## Lifetime and privacy

The native child uses UIKit containment inside a full-screen controller with an
opaque cover, Standard table, and Leave table controls. The cover hides the native
accessibility tree and blocks input while opening, interrupted, or closing.
Native code retains its own cover until a current projection has been drawn.
The outer cover opens only after a successful current-generation foreground
delivery and Ready confirmation.

Scene, Kotlin host, and actual presentation visibility are separate facts. The
adapter applies them synchronously, then publishes the native lifecycle generation
before common code can enqueue a projection. Delivery preserves that captured
generation and the unchanged wire document. It completes only when the native
bridge reports actual delivery. A common foreground-false command remains
restrictive even when native interactivity is available. Renderer events go to the
existing Kotlin codec and event gate; this adapter owns no rules or authority.

Closing immediately covers the view, clears callbacks, and drops pending work.
Success requires both native dormancy and completed UIKit dismissal. A 2.5-second
deadline stays inside Kotlin's 3-second close deadline; failure quarantines future
native entries. Native child removal follows dormancy. Completion releases the
active lifetime before it can synchronously open a pending replacement.

The toolbar follows Dynamic Type, uses controls at least 48 points tall, and offers
VoiceOver and keyboard Escape routes to Leave table. `PartyDeckOwner` forwards
Reduce Motion and the preferred body-font scale to the existing controller, which
clamps renderer text scale to 1.0–2.0. A size change after the native viewport is
established returns to the standard table while retaining the session.

## Verification

Compile and exercise this adapter in the real PartyDeck Xcode target with the
matching native archives and regenerated Kotlin framework. Kotlin adapter checks
cover the common boundary but do not compile UIKit or prove native delivery,
rendering, input, or teardown. Production validation must cover both modes,
Ready, background/resume, interruption, switching modes, Standard table, Leave
table, and return after a viewport change.

UIKit behavior used here is documented by Apple:

- [Container view controllers](https://developer.apple.com/library/archive/featuredarticles/ViewControllerPGforiPhoneOS/ImplementingaContainerViewController.html)
- [Presentation completion](https://developer.apple.com/documentation/uikit/uiviewcontroller/present(_:animated:completion:))
- [Dismissal completion](https://developer.apple.com/documentation/uikit/uiviewcontroller/dismiss(animated:completion:))
- [Disappearance callback](https://developer.apple.com/documentation/uikit/uiviewcontroller/viewwilldisappear(_:))
- [Preferred font and trait collection](https://developer.apple.com/documentation/uikit/uifont/preferredfont(fortextstyle:compatiblewith:))
- [Content-size change notification](https://developer.apple.com/documentation/uikit/uicontentsizecategory/didchangenotification)
