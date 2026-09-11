# Private 3D short-surface context correction

The old renderer puts rank, turn and the latest claim in a fixed VBox above
`TableBodyScroll`. At the retained 681 × 377 physical Android surface and
density 1.75, the actual logical viewport is 389.1428528 × 215.4285736. A real
desktop replay of the exact baseline source shows the claim at y=192 with
height 45, extending below the viewport, and the scroll body at y=249 with
height zero. That claim is absent from the scroll content, so body scrolling
cannot recover it. The retained Android claim and this deterministic fixture
come from different authority states; the source and geometry match.

Candidate V2 measures the real labels at the integer inner width used by
MarginContainer. It accounts for margins, header minimum, context label
heights and VBox separations, and reserves the existing 220-unit scroll-stage
height. Context remains fixed when that budget fits. Otherwise the existing
public body renders rank, turn and full claim plus guidance. A secondary
ROUND label preserves the current round number under the existing narrow
header-hide condition. That last detail resolves independent finding
D2SEA-ROUND-001 from candidate V1. No authority, observer, control gating,
hand logic, or shared test file changes are included.

Final source is `candidate-v2-table.gd`; `candidate-v2.patch` changes only
`godot/renderer/presentations/three_d/table.gd`. `COPYLIST.json` pins the exact
integration bytes. Root owns integration, the PCK rebuild and native CI.
The renderer README's description of always-pinned compact context should
be updated to say that pinning requires room for the scrollable table area.

## Executed checks

All final runs use the verified Godot 4.7.2 executable, actual X11/OpenGL
Compatibility with Mesa llvmpipe, and muted Dummy audio. The ordinary and
duplicate-name claim fixtures were generated with the existing installed
QualificationAuthorityDriver and LastLightWireCodec at seed 2. No rules or
outcomes are implemented in the fixture helper; exact safe-view/envelope
provenance and installed JAR hashes are retained in `inputs/`.

| Final case | Logical geometry | Result |
|---|---|---|
| Retained short surface | 389.14 × 215.43 at density 1.75, text scale 2 | ROUND visible initially; complete claim and guidance scroll into a 103-unit body; Select cards and Challenge Orbit each become wholly enclosed |
| Tall surface | 389.14 × 688 at density 1.75, text scale 2 | Rank/round, turn and claim stay pinned; body height 423 |
| Ordinary names | 389.14 × 500 at density 1.75, text scale 2 | Context stays pinned; body height 235 |
| Duplicate long names | 389.14 × 500 at density 1.75, text scale 2 | Context and round move into body; full claim/guidance and 155-unit Challenge label fit/reach |
| Duplicate long names | 389.14 × 560 at density 1.75, text scale 2 | Wrapped claim stays pinned; body height 247; actions fit/reach |
| Strict input with density adapter | 681 × 377 physical, density 1.75, text scale 2 | Reveal, drag, selection/limit/deselection, cover, lifecycle and history pass; passive drag moves 827 → 1151 with no selection and only Ready |
| Original scene checker, unchanged bytes | 390 × 844, density 1, text scale 2 | Same strict input/privacy checks pass; passive drag moves 80 → 404 |
| Original redraw checker, unchanged bytes | Its own real portrait/landscape/reduced-motion scenarios | 306/306 assertions; 50 actual pixel-buffer frames; zero PNGs by design |

The private density adapter preserves the original `_click` and
`_check_hand_drag` bodies after normalizing only the input-dispatch function
name. It converts logical coordinates to physical Window input before the
engine applies its inverse transform. Every original clip-enclosure,
at-least-eight-unit drag, selection and event assertion remains intact.

The focused layout probe uses real wheel input over the actual VScrollBar
and records the engine's hovered control plus logical/physical coordinates.
The horizontal roster intentionally routes wheel input horizontally, so a
fixed body-center pointer is unsuitable for testing the outer scroll route.
Action enclosures are separate geometry observations: no Play or Challenge
intent is dispatched or authority-accepted. Empty selection, erased private
nodes, revision and Ready-event checks cover their recorded endpoints, not
continuous native privacy or physical touch behavior.

## Sources, iterations and retained evidence

`research/sources.json` binds authoritative Godot source bytes and URLs to
commit `ed1daf0bf001b61586d9930840f2f1394092c079`. The relevant APIs and layout
behavior are in Label::_shape/get_minimum_size, MarginContainer sorting,
BoxContainer::_resort, Window::_update_viewport_size/get_final_transform,
Viewport::_make_input_local, and ScrollContainer/ScrollBar::gui_input.
No dependency or version changed.

All 63 new PNGs remain in their original run directories with individual
receipts and `CAPTURES.json` bindings. Thirty are retained baseline or
superseded iterations; 33 are from final V2 checks. Failed harness attempts
remain failures: one initial probe parse error produced no image; an
unscaled input attempt produced two; a wrong expectation at 560 logical
height produced two although the measured context fit; and an outer-scroll
probe stopped at the horizontal roster and produced four. Their probe and
runner bytes are retained by hash. The baseline reproduction is defect
evidence and is not a layout acceptance pass. Pixel-review attribution is
provided in the independent review receipt, separately from these execution
receipts. Earlier Android pixel receipts remain immutable old-source evidence.

`VALIDATION.json` verifies every PNG/hash/dimension, every source fingerprint,
all retained execution inputs, and all eight final successful runs. Final
jobs reserved 768 MiB for the engine plus 32 MiB for bounded output above the
3 GiB MemAvailable floor, used the nonblocking shared Godot lock, and exited
cleanly. The complete private bundle stays below 32 MiB.

These checks establish this source correction on the desktop renderer and
the stated fixtures/geometries. They do not complete native reruns, physical
touch/accessibility, device GPU performance, signing, stores, or networking.
