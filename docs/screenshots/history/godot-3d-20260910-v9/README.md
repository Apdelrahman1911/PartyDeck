# Godot 3D — v9, retained parse-error screens

[All screenshot collections](../../README.md)

**Evidence status:** All three runs exit 1 after a GDScript type-inference parse error prevents the game scene from rendering. The three original blank renderer captures are retained as failure evidence, with no game-layout qualification.

All 3 original PNGs are retained, including repeated image states and failed attempts. Every unique state was visually inspected; original bytes, filenames, dimensions and source locations are preserved. Inline thumbnails open the original file.

Actual Godot `4.7.2.stable.official.ed1daf0bf`, OpenGL Compatibility / Mesa llvmpipe / Xvfb. Each case retains its original command, exit code, source-before/source-after hashes, exact `fixture.json`, diagnostics and runtime log. The recorded 8-file [source subset](source/) is frozen and independently matches every corresponding receipt. No exact capture commit was recorded. Passing logs contain no engine/script errors; failing logs retain their original errors.

The per-case fixture copies match the original hashes recorded in the receipts. The input recipes and seed provenance are retained with the [final v10 collection](../../godot-3d-20260910-v10/README.md); all cases here use seed 2.

The original error is `Cannot infer the type of "clip" variable because the value doesn't have a set type.` Godot cannot load `table.gd`, and the shared controller rejects the fixture. The solid background images are actual captured renderer outputs, not game scenes. Requested 100%/200% text settings are recorded, but no text or controls render. Zero private counters here describe a failed scene and do not qualify privacy behavior.

## Large text touch

[Capture basis](large-text-touch/capture-basis.json) · [Runtime log](large-text-touch/runtime.log) · [Frozen input](large-text-touch/fixture.json).

| Original image | Scenario and provenance |
| --- | --- |
| <a href="large-text-touch/failure.png"><img src="large-text-touch/failure.png" alt="Blank renderer after GDScript type-inference parse failure — large text touch" width="168"></a> | **Blank renderer after GDScript type-inference parse failure — large text touch**<br>Godot 4.7.2 desktop 3D, Compatibility renderer<br>Original: [failure.png](large-text-touch/failure.png)<br>320 × 740 px; text 2× configured; no game text rendered; seed 2<br>SHA-256: <code>ec5fb01fc45d6b52ed9c27670517d7517b82058b5ed7c8ddbbecc0cbb9a53ca7</code><br>[Original diagnostics](large-text-touch/failure-diagnostics.json)<br>The configured input is a recipient-safe seed-2 authority projection, but the game scene never renders.<br>Runtime exits 1: Godot cannot infer the type of the clip variable; table.gd fails to load and the controller rejects the fixture. Font scale is a requested setting only. Empty controls and zero private counts do not qualify game layout or runtime privacy. |

## Narrow touch

[Capture basis](narrow-touch/capture-basis.json) · [Runtime log](narrow-touch/runtime.log) · [Frozen input](narrow-touch/fixture.json).

| Original image | Scenario and provenance |
| --- | --- |
| <a href="narrow-touch/failure.png"><img src="narrow-touch/failure.png" alt="Blank renderer after GDScript type-inference parse failure — narrow touch" width="168"></a> | **Blank renderer after GDScript type-inference parse failure — narrow touch**<br>Godot 4.7.2 desktop 3D, Compatibility renderer<br>Original: [failure.png](narrow-touch/failure.png)<br>320 × 568 px; text 1× configured; no game text rendered; seed 2<br>SHA-256: <code>3925432db1088afaaee923458294a6da491d425fb860cb94416f7697de5d9a50</code><br>[Original diagnostics](narrow-touch/failure-diagnostics.json)<br>The configured input is a recipient-safe seed-2 authority projection, but the game scene never renders.<br>Runtime exits 1: Godot cannot infer the type of the clip variable; table.gd fails to load and the controller rejects the fixture. Font scale is a requested setting only. Empty controls and zero private counts do not qualify game layout or runtime privacy. |

## Six long names large text

[Capture basis](six-long-names-large-text/capture-basis.json) · [Runtime log](six-long-names-large-text/runtime.log) · [Frozen input](six-long-names-large-text/fixture.json).

| Original image | Scenario and provenance |
| --- | --- |
| <a href="six-long-names-large-text/failure.png"><img src="six-long-names-large-text/failure.png" alt="Blank renderer after GDScript type-inference parse failure — six long names large text" width="168"></a> | **Blank renderer after GDScript type-inference parse failure — six long names large text**<br>Godot 4.7.2 desktop 3D, Compatibility renderer<br>Original: [failure.png](six-long-names-large-text/failure.png)<br>320 × 740 px; text 2× configured; no game text rendered; seed 2<br>SHA-256: <code>ec5fb01fc45d6b52ed9c27670517d7517b82058b5ed7c8ddbbecc0cbb9a53ca7</code><br>[Original diagnostics](six-long-names-large-text/failure-diagnostics.json)<br>The configured input is a recipient-safe seed-2 authority projection, but the game scene never renders.<br>Runtime exits 1: Godot cannot infer the type of the clip variable; table.gd fails to load and the controller rejects the fixture. Font scale is a requested setting only. Empty controls and zero private counts do not qualify game layout or runtime privacy. |
