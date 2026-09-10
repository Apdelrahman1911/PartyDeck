All 20 existing baseline/candidate Card3D PNG pairs match byte for byte. This handoff maps their 40 separate original capture identities for gallery publication; it creates no new images or canonical edits.

Use [source-map.json](source-map.json) for original paths, filenames, byte counts, SHA-256 hashes, dimensions, 3D scenario/state labels, recorded text scale, diagnostics, execution/source references and per-original view status. [MAPPING.md](MAPPING.md) is the complete human-readable index. The planned gallery root is `docs/screenshots/godot-card3d-reuse-desktop-20260910`, with `baseline/` and `candidate/` children.

Coverage is six portrait pairs, six short-landscape pairs, seven enlarged-text/emulated-touch pairs and one resolved public-proof pair. The two direct views are the selected-hand candidate images in portrait and enlarged text. They were viewed during the earlier validation pass by assets; the new attestation records that history and does not represent a new view. Other originals retain `actually_viewed=false`.

These are source-project runs under Godot 4.7.2 OpenGL Compatibility, Xvfb and software Mesa, with unchanged MSAA_2X. Baseline source is frozen c65e264; the candidate is the two-file a904d39c resource-sharing patch. The original commands use `--path`; no PCK was the input. The associated retained baseline pack hash is contextual provenance only. Root’s later integration/export must remain a separate identity.

Original desktop validation reports all four scene scenarios passed for both source projects, plus 560 numbered owner assertions across redraw, terminal-return and resource sharing/lifetime. Independent review_game verified the source delta, original receipts and exact image pairs, explicitly without viewing images. These checks and screenshots do not prove native entry latency, native cover timing, native accessibility or a shader-compilation reduction. The source checker uses a safe fixture and submits no authority-accepted gameplay.

Original owner and independent evidence:

| Evidence | Original file | SHA-256 |
| --- | --- | --- |
| owner freeze | [freeze.json](/tmp/partydeck-card3d-reuse-candidate-assets-v1-n6xs0bjq/freeze.json) | `7c274914ff2f3d8e500458ef5303492e02d2af2144c04e2d16f3659bf8a8b5e3` |
| candidate patch | [card3d-resource-reuse.patch](/tmp/partydeck-card3d-reuse-candidate-assets-v1-n6xs0bjq/card3d-resource-reuse.patch) | `a904d39cb259cae75085001f4733a0d7ee49cd1f2693f8c723ae914541c9b484` |
| owner result | [RESULT.md](/tmp/partydeck-card3d-reuse-candidate-assets-v1-n6xs0bjq/RESULT.md) | `50ab3ce841661e9fb3ff78eae33cb2f84822474c2328e8e3e60e5b6d24200400` |
| owner validation summary | [validation-summary.json](/tmp/partydeck-card3d-reuse-candidate-assets-v1-n6xs0bjq/receipts/validation-summary.json) | `abcd5171d3536396a051c9748223f9b045625f76a2e16f413d469b50f0dee76f` |
| original pixel comparison | [pixel-comparison.json](/tmp/partydeck-card3d-reuse-candidate-assets-v1-n6xs0bjq/evidence/pixel-comparison.json) | `52949f7e68018aff80760409f95958825a91e2714fe6703dce2c3cfff37519cd` |
| engine version receipt | [godot-version.json](/tmp/partydeck-card3d-reuse-candidate-assets-v1-n6xs0bjq/receipts/godot-version.json) | `e15e966f3e6617fc193eda2773b44dfe6ea3c5a2681f841a1191b6bcd85f0516` |
| rendering review | [REVIEW.md](/tmp/partydeck-card3d-reuse-review-game-v1/REVIEW.md) | `ddc36c9f95035704c4de0aa1027a7c486b8e076e2424091f1530b9cdd165b90b` |
| rendering review freeze | [FROZEN.json](/tmp/partydeck-card3d-reuse-review-game-v1/FROZEN.json) | `e00c4432163f26425bc01bd37977de1d88810ee50adfa5af6a14d3462ee9038b` |
| security source review | [SOURCE-REVIEW.md](/tmp/partydeck-3d-resource-reuse-security-candidate-v1/SOURCE-REVIEW.md) | `facf043271ceb3fb6fd0f58dc63dfa2897337108d446c9fc8db7ded7856ae989` |

Publication claims should stay with the recorded frames and source scope. Label the generic `round-ended/01-concealed.png` capture as the resolved public-proof scenario. Label foreground/resume states as desktop command checks and enlarged-text dragging as emulated touch. Keep all 40 paths even when hashes repeat, and retain explicit unviewed labels. The complete supported claims and limits are in `source-map.json`.
