# Compact 2D seat clipping review

The clipped lower seat text is intentional scroll-boundary clipping. No correction is justified by these originals.

I viewed the exact retained screenshot from run 34520375602 and the published production screenshot from run 34515669045. Both show seat numbers, names, card counts and the active-player status. The separate turn line above the scrolling body remains fully visible. The bottom “No lights used” line crosses the scrolling edge; a visible vertical scrollbar indicates further content below.

The retained companion records a 378 × 655 renderer viewport and TableScroll clip rectangle [16, 118, 346, 391], ending at y=509. Fixed actions begin at y=521 and y=587, each 56 units high; Reveal is also 56 units high. These measurements are a separate observation, not an atomic screenshot measurement. Full screenshot dimensions include the native shell and were not used as the renderer viewport.

Exact c65e264 source intentionally places the hand before seats inside TableScroll on phones, while TurnMessage and normal-text actions stay outside it. Seats and labels have natural content height. Pinned Godot source retains that full child height, computes the vertical scroll range and clips only at the scroll viewport. Thus this is continuation of readable content below the initial viewport, with turn and primary controls retained, not permanently cropped seat content.

Four relevant archived source files were independently checked against the frozen source binding and match current working bytes. Official ScrollContainer sources were fetched at pinned commit ed1daf0bf001b61586d9930840f2f1394092c079 and matched the local upstream source. Full image/source hashes, metric fields and source line references are in findings.json.

No native swipe, accessibility behavior or missing frame is inferred. No test, native run, fresh screenshot, shared edit or candidate was made. Original outcomes remain unchanged.
