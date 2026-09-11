# 3D context fitting — desktop correction evidence

This collection preserves **63 original PNGs**: **33 final V2 captures** and **30 baseline, superseded or failed-harness captures**. Review by **/root/pixel_d2_sea** records **36 direct views, one reviewed byte match and 26 historical images without attributed pixel review**. The final V2 subset has **32 direct views, one byte match and zero unviewed images**.

The correction keeps rank, turn and latest claim fixed when they fit above a useful scroll area. On the short tested surface, that context moves into the existing scroll body and the current round is shown in the initial view. Actual scrollbar wheel input exposes the complete claim, guidance and each action label in the tested layouts.

The exact final `table.gd` SHA-256 is `a91e94b910f763efb9c108d9e7602230736c503c6e53e4bd018a61ad9eebeb4d`. Each capture retains its source file, project fingerprint, fixture and original run receipt; a base Git revision is not a whole-tree candidate claim.

The baseline desktop replay uses the same table source as Android run 34540229407 and its 681 × 377 surface at density 1.75 and text scale 2. Its authority-derived Orbit/Crown round-4 fixture differs from the original native Star-round state. The [old Android issue](../supplemental/android-adaptive-34540229407-frames/provenance/layout-issue/issue.json) remains unchanged.

Eight final desktop runs passed: five focused layout cases, two strict scene/input runs and the unchanged redraw checker. The redraw checker passed 306 assertions over 50 real pixel-buffer frames and wrote no PNGs. Long duplicate-name layouts were checked at logical heights 500 and 560. The strict click checks use ensure_control_visible; manual scrollbar reachability is recorded separately. No Play or Challenge intent was activated or authority-accepted by these probes.

These are actual Godot desktop X11/OpenGL Compatibility captures with Mesa llvmpipe. They establish the recorded fixture states and interactions. Native, physical-touch/accessibility and continuous-privacy acceptance remain separate.

[Capture manifest](manifest.json) · [Independent approval and limits](provenance/review/INDEPENDENT-REVIEW.json) · [Owner correction and executed checks](provenance/owner/CORRECTION.md)

## Final V2 desktop checks

| Original run | PNGs | Direct | Byte match | Unviewed |
| --- | ---: | ---: | ---: | ---: |
| [candidate-v2-long-500](runs/candidate-v2-long-500/README.md) | 3 | 3 | 0 | 0 |
| [candidate-v2-long-560](runs/candidate-v2-long-560/README.md) | 3 | 3 | 0 | 0 |
| [candidate-v2-ordinary-500](runs/candidate-v2-ordinary-500/README.md) | 3 | 3 | 0 | 0 |
| [candidate-v2-original-input](runs/candidate-v2-original-input/README.md) | 8 | 8 | 0 | 0 |
| [candidate-v2-redraw](runs/candidate-v2-redraw/README.md) | 0 | 0 | 0 | 0 |
| [candidate-v2-short-density-final](runs/candidate-v2-short-density-final/README.md) | 5 | 5 | 0 | 0 |
| [candidate-v2-short-input](runs/candidate-v2-short-input/README.md) | 8 | 7 | 1 | 0 |
| [candidate-v2-tall-density](runs/candidate-v2-tall-density/README.md) | 3 | 3 | 0 | 0 |

## Retained baseline and earlier attempts

One PNG reproduces the baseline defect, 21 belong to superseded iterations and eight belong to failed harness attempts. Four of these historical images were directly reviewed; the other 26 retain their unviewed labels even when their bytes happen to match another capture. Zero-PNG import and failed-parse runs remain listed with their original receipts.

| Original run | Outcome | PNGs | Direct | Byte match | Unviewed |
| --- | --- | ---: | ---: | ---: | ---: |
| [baseline-import-v1](runs/baseline-import-v1/README.md) | Superseded iteration | 0 | 0 | 0 | 0 |
| [baseline-short-density-v1](runs/baseline-short-density-v1/README.md) | Failed harness attempt | 0 | 0 | 0 | 0 |
| [baseline-short-density-v2](runs/baseline-short-density-v2/README.md) | Baseline defect reproduction | 1 | 1 | 0 | 0 |
| [candidate-import-v1](runs/candidate-import-v1/README.md) | Superseded iteration | 0 | 0 | 0 | 0 |
| [candidate-long-name-500-v1](runs/candidate-long-name-500-v1/README.md) | Superseded iteration | 1 | 0 | 0 | 1 |
| [candidate-long-name-medium-v1](runs/candidate-long-name-medium-v1/README.md) | Failed harness attempt | 2 | 0 | 0 | 2 |
| [candidate-original-input-v1](runs/candidate-original-input-v1/README.md) | Superseded iteration | 8 | 0 | 0 | 8 |
| [candidate-short-density-v1](runs/candidate-short-density-v1/README.md) | Failed harness attempt | 2 | 0 | 0 | 2 |
| [candidate-short-density-v2](runs/candidate-short-density-v2/README.md) | Superseded iteration | 3 | 3 | 0 | 0 |
| [candidate-short-input-v1](runs/candidate-short-input-v1/README.md) | Superseded iteration | 8 | 0 | 0 | 8 |
| [candidate-tall-density-v1](runs/candidate-tall-density-v1/README.md) | Superseded iteration | 1 | 0 | 0 | 1 |
| [candidate-v2-short-density](runs/candidate-v2-short-density/README.md) | Failed harness attempt | 4 | 0 | 0 | 4 |
