# Last Light 2D

[`table.tscn`](table.tscn) is the real flat Godot presentation selected by
`presentationMode: "2d"`. It remains alongside the separately owned 3D scene.
The shared main scene calls `bind(controller)`; this presentation renders
`presentation_state()`, listens to `state_changed`, and requests only the
controller's reveal, cover, selection, play, challenge, next-round, lobby and
exit methods. The [bridge contract](../../../bridge/CONTRACT.md) and existing
Kotlin authority own legality, identity, pending actions and outcomes.

The table shows the required rank, public claim count, numbered seats, public
hand counts and lights already used. Only a resolved outcome from the current
round shows card proof. Duplicate names retain seat numbers. Eliminated players
and observers can watch the public table. No rules, networking, random outcome,
opponent hand or future burnout threshold is implemented in this directory.

Private faces exist only while the controller reveals the recipient's hand.
Cover, background and close erase card textures, rank labels, IDs, tooltips and
accessibility text before removing their nodes. Public challenge-proof cards
are separate from the private-node groups. Selection uses an outline, check
badge and short lift; Reduce Motion removes the tween. Optional local audio
uses the shared foreground/sound preferences and `partydeck_feedback` group.

Phone layouts put the hand before the seats; short landscape puts it before
the public table. Wide five/six-player tables use three seat columns. At large
text scales, ornament gives way to text and actions join the scrolling page;
proof cards wrap as complete cards. Buttons are at least 56 renderer units high.
Card/action input passes to enclosing scroll containers, which cancel a tap
after an 8-unit drag threshold. Keyboard focus remains available. Control
accessibility properties do not qualify native TalkBack or VoiceOver support.

Run an interactive authority-backed comparison from the repository root after
building the [comparison launcher](../../../comparison/README.md):

```sh
godot/qualification/build/modules/comparison/install/partydeck-godot-compare/bin/partydeck-godot-compare \
  --presentation 2d --interactive
```

The owned check is excluded from the renderer export by `checks/.gdignore`.
It loads a recipient-safe fixture through the real bridge and sends actual
engine mouse press/release events. It checks reveal, first/last card selection,
cover, background/close erasure, public proof and the absence of gameplay events
from local hand operations. Use a fresh absolute output directory for each run:

```sh
env LIBGL_ALWAYS_SOFTWARE=1 xvfb-run -a -s '-screen 0 1440x1100x24' \
  /opt/partydeck-godot/godot --audio-driver Dummy --path godot/renderer \
  --script "$PWD/godot/renderer/presentations/two_d/checks/scene_check.gd" \
  -- --manual-bridge \
  --check-fixture="$PWD/godot/bridge/fixtures/launch-2d.json" \
  --check-output=/tmp/partydeck-2d-check-01 \
  --check-width=390 --check-height=844 --check-text-scale=1 \
  --check-touch-drag=true
```

The optional touch-emulation check requires an actionable, overflowing hand
and a scrollable page. A vertical swipe starting on Reveal must scroll without
revealing. A card tap with 2 units of movement must select, a second tap must
deselect, and a horizontal swipe must scroll without selection. It then runs
the ordinary tap/privacy checks. Repeat at `320×740` and `--check-text-scale=2`
for large text. `--check-lobby=true`, with a live-match fixture whose native
controls permit lobby return, also checks open/cancel/confirm and pending state.

Actual accepted play, challenge, complete match, lobby, re-entry and exit belong
to the comparison launcher's full Kotlin-authority run. Its README records the
matched packed evidence for both presentations. All captured iterations,
including failed layout/gesture checks, go through the independent design owner
to the [screenshot gallery](../../../../docs/screenshots/README.md). Desktop
captures use real OpenGL Compatibility rendering under Mesa/Xvfb. They do not
qualify native touch delivery, mobile screen readers or device GPU performance.

API choices were checked against the pinned **Godot 4.7.2-stable** sources:
[Control input propagation](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Control.xml),
[ScrollContainer](https://github.com/godotengine/godot/blob/4.7.2-stable/scene/gui/scroll_container.cpp)
and [BaseButton press cancellation](https://github.com/godotengine/godot/blob/4.7.2-stable/scene/gui/base_button.cpp),
[HFlowContainer](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/HFlowContainer.xml),
[TranslationServer](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/TranslationServer.xml)
and [RenderingServer.force_draw](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/RenderingServer.xml).
Static captures force a fresh frame because low-processor mode may not schedule
another draw on its own. The scene's persisted root `unique_id` comes from the
first qualified PCK, keeping later exports reproducible.
