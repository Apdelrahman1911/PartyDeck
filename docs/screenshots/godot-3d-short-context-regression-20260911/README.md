# 3D short-context desktop regression

**The same short-window regression failed on the baseline and passed on the fixed renderer.** The nine original PNGs preserve two baseline identities and seven fixed-source identities at 389 × 215 pixels with text scale 2.0.

Independent pixel review records **8 direct views, 1 reviewed byte match and 0 unviewed images**. The second baseline image is retained as a distinct capture.

| Source run | Stills | Preserved execution outcome |
| --- | ---: | --- |
| [Baseline](baseline/README.md) | 2 | Expected failure, exit 1: no visible scroll space for context or actions. |
| [Fixed renderer](candidate/README.md) | 7 | Passed, exit 0. |

[Capture manifest](manifest.json) · [Independent pixel review](provenance/pixel-review/capture-review.json) · [Independent test/source review](provenance/test-source-review/INDEPENDENT-REVIEW.json)

The executed regression checks a nonempty body viewport, the current round, every non-whitespace character of the claim/guidance text and the full projected action rectangles at reachable scroll positions. It uses programmatic native scrolling before the existing mouse-input checks. Its test/source reviewer verified the recorded baseline failure and fixed success without rerunning Godot.

The saved pixels support a narrower conclusion: the baseline claim is visibly clipped; the fixed initial capture shows Your turn, ROUND 4 and a body scrollbar. Later fixed images show full selection controls or Challenge Orbit at saved positions. **None of these nine images shows the complete ordinary current-claim sentence or a complete readable Play control.** The history capture shows Hide last round with the previous-reveal heading clipped below. Static images do not establish interaction reachability.

Baseline table-file SHA-256: `a9edd383b71832b41d3fd307d3cf4397fe33df099c54471cb16006da0246e061`. Fixed table-file SHA-256: `a91e94b910f763efb9c108d9e7602230736c503c6e53e4bd018a61ad9eebeb4d`. These are file hashes, not Git commits; each run retains its own project fingerprint. The independently reviewed test-file SHA-256 is `3524494dd0f1baa6f1016e2e6bb3ef9f746472202c2018559f0515140bf604d7`.

Both runs use the same authority-derived Orbit/Crown round-4 fixture. The producer’s original pending-pixel-review labels remain unchanged in its frozen receipts; the separate pixel review supplies the current attributed coverage. [Earlier context-correction evidence](../godot-3d-context-fit-20260911/README.md) retains its own captures and scrollbar-wheel checks.

The source manifest records no per-frame export timestamp. Source filesystem mtime and run intervals are retained separately. This desktop fixture evidence adds no authority-accepted action, continuous-privacy, native-accessibility, physical-device, physical-network or 3D artwork qualification.
