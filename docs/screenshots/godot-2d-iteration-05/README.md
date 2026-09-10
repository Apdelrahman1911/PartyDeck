# Godot 2D — iteration 05, proof reflow and retained header/gesture failures

[All screenshot collections](../README.md)

**Evidence status:** Public proof labels reflow without splitting Moon; forced challenge, observer and winner frames are readable. The six-player desktop lobby control wraps into a 199-pixel header, and the temporary emulated-touch probe fails before later capture stages.

Five static reports pass. Proof reflow places the third public card and the detailed explanation below the initial 200% viewport. The temporary gesture probe has only its initial capture and a supplied failure record; no gesture success or clean runtime report is claimed for it. Its failure record does not determine whether scrolling, selection, touch availability or coordinates caused the failure.

Actual Godot `4.7.2.stable.official.ed1daf0bf`, OpenGL Compatibility / Mesa llvmpipe / Xvfb. These are desktop renderer pixels at the recorded sizes and text settings. [Original source provenance](source-provenance.json) records a working tree over basis `91a4c9c50fb91f6f88ed596dfd1c27433c66ac11`; no exact capture commit is claimed. Implementation hashes are preserved, but the implementation files themselves were not frozen for this 2D iteration.

[The frozen inputs](../godot-2d-iteration-04/fixtures/) and [their Java generator](../godot-2d-iteration-04/PartyDeck2DEdgeFixtures.java) are retained once with iteration 04. Authority-derived inputs explicitly record seed 2; the lobby permission input is synthetic. The fixtures contain recipient-safe DTOs, not serialized authoritative GameState or live invitation credentials.

All 12 supplied PNGs are preserved, including repeated states and failed-attempt initial frames. Every unique image state was visually inspected and copied bytes were verified. Local checks can programmatically scroll controls into view; a passing report is not an initial-viewport, native touch, accessibility or native OS lifecycle pass. Concealed, covered, resumed, confirmation and public-outcome diagnostics retain zero private faces, labels and selection. Revealed forced-challenge input has two private cards and no selection; ordinary revealed hands have five faces/labels and two selected cards.

## Three card proof large text

[Original static report](three-card-proof-large-text/report.json).

| Original image | Scenario and provenance |
| --- | --- |
| <a href="three-card-proof-large-text/01-concealed.png"><img src="three-card-proof-large-text/01-concealed.png" alt="Public Moon, Star and Star reveal after a Star claim — 200% text" width="168"></a> | **Public Moon, Star and Star reveal after a Star claim — 200% text**<br>Godot 4.7.2 desktop, 2D Compatibility renderer<br>Original: [01-concealed.png](three-card-proof-large-text/01-concealed.png)<br>320 × 740 px; text 2×; seed 2<br>SHA-256: <code>7bce65c450f2f3c3754ac82c35a34eceb4979a88ff46f386ff70473c88da7da0</code><br>[Original diagnostics](three-card-proof-large-text/01-concealed.json)<br>Static seed-2 recipient-safe Kotlin-authority projection; renderer actions are not round-tripped to the authority.<br>Bartholomew Beaumont challenged Francesca Montenegro; Moon mismatched the Star claim, so Francesca used light 1 and stays in.<br>Moon and Star labels stay whole after reflow; the third card and detailed explanation extend below the initial viewport. |

## Forced challenge phone

[Original static report](forced-challenge-phone/report.json).

| Original image | Scenario and provenance |
| --- | --- |
| <a href="forced-challenge-phone/01-concealed.png"><img src="forced-challenge-phone/01-concealed.png" alt="Initial concealed own hand — forced challenge phone" width="168"></a> | **Initial concealed own hand — forced challenge phone**<br>Godot 4.7.2 desktop, 2D Compatibility renderer<br>Original: [01-concealed.png](forced-challenge-phone/01-concealed.png)<br>390 × 844 px; text 1×; seed 2<br>SHA-256: <code>17970f35dec022f589b2728085a70f0a81c444501fff03f49d8adc16f9a21d33</code><br>[Original diagnostics](forced-challenge-phone/01-concealed.json)<br>Static seed-2 recipient-safe Kotlin-authority projection; renderer actions are not round-tripped to the authority.<br>Duplicate claimant name is disambiguated as seat 2; Call the bluff is the only gameplay action. |
| <a href="forced-challenge-phone/02-revealed-selected.png"><img src="forced-challenge-phone/02-revealed-selected.png" alt="Forced challenge: own Crown and Moon revealed, zero selected cards" width="168"></a> | **Forced challenge: own Crown and Moon revealed, zero selected cards**<br>Godot 4.7.2 desktop, 2D Compatibility renderer<br>Original: [02-revealed-selected.png](forced-challenge-phone/02-revealed-selected.png)<br>390 × 844 px; text 1×; seed 2<br>SHA-256: <code>8e9f3ddcc6eedaed7117d4b7dbfa425178275d1d1c7d44b42948d6323b1b0bee</code><br>[Original diagnostics](forced-challenge-phone/02-revealed-selected.json)<br>Static seed-2 recipient-safe Kotlin-authority projection; renderer actions are not round-tripped to the authority.<br>Duplicate claimant name is disambiguated as seat 2; Call the bluff is the only gameplay action. |
| <a href="forced-challenge-phone/03-covered-again.png"><img src="forced-challenge-phone/03-covered-again.png" alt="Hand covered with selection cleared — forced challenge phone" width="168"></a> | **Hand covered with selection cleared — forced challenge phone**<br>Godot 4.7.2 desktop, 2D Compatibility renderer<br>Original: [03-covered-again.png](forced-challenge-phone/03-covered-again.png)<br>390 × 844 px; text 1×; seed 2<br>SHA-256: <code>17970f35dec022f589b2728085a70f0a81c444501fff03f49d8adc16f9a21d33</code><br>[Original diagnostics](forced-challenge-phone/03-covered-again.json)<br>Static seed-2 recipient-safe Kotlin-authority projection; renderer actions are not round-tripped to the authority.<br>Duplicate claimant name is disambiguated as seat 2; Call the bluff is the only gameplay action. |
| <a href="forced-challenge-phone/04-resumed-covered.png"><img src="forced-challenge-phone/04-resumed-covered.png" alt="Hand remains covered after background and resume — forced challenge phone" width="168"></a> | **Hand remains covered after background and resume — forced challenge phone**<br>Godot 4.7.2 desktop, 2D Compatibility renderer<br>Original: [04-resumed-covered.png](forced-challenge-phone/04-resumed-covered.png)<br>390 × 844 px; text 1×; seed 2<br>SHA-256: <code>17970f35dec022f589b2728085a70f0a81c444501fff03f49d8adc16f9a21d33</code><br>[Original diagnostics](forced-challenge-phone/04-resumed-covered.json)<br>Static seed-2 recipient-safe Kotlin-authority projection; renderer actions are not round-tripped to the authority.<br>Duplicate claimant name is disambiguated as seat 2; Call the bluff is the only gameplay action. |

## Observer phone

[Original static report](observer-phone/report.json).

| Original image | Scenario and provenance |
| --- | --- |
| <a href="observer-phone/01-concealed.png"><img src="observer-phone/01-concealed.png" alt="Unseated observer watches a six-player Star round" width="168"></a> | **Unseated observer watches a six-player Star round**<br>Godot 4.7.2 desktop, 2D Compatibility renderer<br>Original: [01-concealed.png](observer-phone/01-concealed.png)<br>390 × 844 px; text 1×; seed 2<br>SHA-256: <code>a1a89f0eb1e231f60026b27cea6f0acccd5cf0a2aa54d123254645817bdfdb66</code><br>[Original diagnostics](observer-phone/01-concealed.json)<br>Static seed-2 recipient-safe Kotlin-authority projection; renderer actions are not round-tripped to the authority.<br>No private hand, Reveal or gameplay action is exposed. |

## Winner phone

[Original static report](winner-phone/report.json).

| Original image | Scenario and provenance |
| --- | --- |
| <a href="winner-phone/01-concealed.png"><img src="winner-phone/01-concealed.png" alt="Orbit wins after Moxie’s Moon bluff against Crown" width="168"></a> | **Orbit wins after Moxie’s Moon bluff against Crown**<br>Godot 4.7.2 desktop, 2D Compatibility renderer<br>Original: [01-concealed.png](winner-phone/01-concealed.png)<br>390 × 844 px; text 1×; seed 2<br>SHA-256: <code>da5c155b9d7522b3dac01f53608ab8c113679fc04905cb410d8de4ccb8c86af0</code><br>[Original diagnostics](winner-phone/01-concealed.json)<br>Static seed-2 recipient-safe Kotlin-authority projection; renderer actions are not round-tripped to the authority.<br>Named final challenger, claimant, Crown claim, public Moon and Moxie’s light-4 burnout are visible. |

## Six long names desktop

[Original static report](six-long-names-desktop/report.json).

| Original image | Scenario and provenance |
| --- | --- |
| <a href="six-long-names-desktop/01-concealed.png"><img src="six-long-names-desktop/01-concealed.png" alt="Initial concealed own hand — six long names desktop" width="168"></a> | **Initial concealed own hand — six long names desktop**<br>Godot 4.7.2 desktop, 2D Compatibility renderer<br>Original: [01-concealed.png](six-long-names-desktop/01-concealed.png)<br>1280 × 800 px; text 1×; seed 2<br>SHA-256: <code>9c40a9754ee32e214c74efe7cca6137b27abb668df93aedfe9686afb6d72b64f</code><br>[Original diagnostics](six-long-names-desktop/01-concealed.json)<br>Static seed-2 recipient-safe Kotlin-authority projection; renderer actions are not round-tripped to the authority.<br>Visual failure: a 56-pixel-wide lobby control wraps into a 199-pixel-high header and the initial Reveal is below the viewport. |
| <a href="six-long-names-desktop/02-revealed-selected.png"><img src="six-long-names-desktop/02-revealed-selected.png" alt="Own hand revealed with first and last cards selected — six long names desktop" width="168"></a> | **Own hand revealed with first and last cards selected — six long names desktop**<br>Godot 4.7.2 desktop, 2D Compatibility renderer<br>Original: [02-revealed-selected.png](six-long-names-desktop/02-revealed-selected.png)<br>1280 × 800 px; text 1×; seed 2<br>SHA-256: <code>bf4d8a2b22945ecb72a6ce00d7626e9783365459effddba0c8cd314fc3521ea4</code><br>[Original diagnostics](six-long-names-desktop/02-revealed-selected.json)<br>Static seed-2 recipient-safe Kotlin-authority projection; renderer actions are not round-tripped to the authority.<br>Visual failure: a 56-pixel-wide lobby control wraps into a 199-pixel-high header and the initial Reveal is below the viewport. |
| <a href="six-long-names-desktop/03-covered-again.png"><img src="six-long-names-desktop/03-covered-again.png" alt="Hand covered with selection cleared — six long names desktop" width="168"></a> | **Hand covered with selection cleared — six long names desktop**<br>Godot 4.7.2 desktop, 2D Compatibility renderer<br>Original: [03-covered-again.png](six-long-names-desktop/03-covered-again.png)<br>1280 × 800 px; text 1×; seed 2<br>SHA-256: <code>1772957bfe438da88d2b643758f896fdccdfe365fccdbbd83efc3887673b3992</code><br>[Original diagnostics](six-long-names-desktop/03-covered-again.json)<br>Static seed-2 recipient-safe Kotlin-authority projection; renderer actions are not round-tripped to the authority.<br>Visual failure: a 56-pixel-wide lobby control wraps into a 199-pixel-high header and the initial Reveal is below the viewport. |
| <a href="six-long-names-desktop/04-resumed-covered.png"><img src="six-long-names-desktop/04-resumed-covered.png" alt="Hand remains covered after background and resume — six long names desktop" width="168"></a> | **Hand remains covered after background and resume — six long names desktop**<br>Godot 4.7.2 desktop, 2D Compatibility renderer<br>Original: [04-resumed-covered.png](six-long-names-desktop/04-resumed-covered.png)<br>1280 × 800 px; text 1×; seed 2<br>SHA-256: <code>1772957bfe438da88d2b643758f896fdccdfe365fccdbbd83efc3887673b3992</code><br>[Original diagnostics](six-long-names-desktop/04-resumed-covered.json)<br>Static seed-2 recipient-safe Kotlin-authority projection; renderer actions are not round-tripped to the authority.<br>Visual failure: a 56-pixel-wide lobby control wraps into a 199-pixel-high header and the initial Reveal is below the viewport. |

## Emulated drag phone

[Supplied failure record](emulated-drag-phone/failure.json) · [Original temporary probe](emulated-drag-phone/gesture-check.gd).

| Original image | Scenario and provenance |
| --- | --- |
| <a href="emulated-drag-phone/01-concealed.png"><img src="emulated-drag-phone/01-concealed.png" alt="Initial concealed frame before the temporary emulated-drag failure" width="168"></a> | **Initial concealed frame before the temporary emulated-drag failure**<br>Godot 4.7.2 desktop, 2D Compatibility renderer<br>Original: [01-concealed.png](emulated-drag-phone/01-concealed.png)<br>390 × 844 px; text 1×; seed 2<br>SHA-256: <code>c06b5faf2323627c93bf4e6fc2a3579d6fd06a22205eff03a770b340a1377697</code><br>[Original diagnostics](emulated-drag-phone/01-concealed.json)<br>Static seed-2 recipient-safe Kotlin-authority projection; renderer actions are not round-tripped to the authority.<br>Only the initial PNG exists. The supplied failure record does not isolate the cause; no drag success is claimed. |
