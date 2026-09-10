# Compose Standard large text — Natural visibility — preserved failure

Both strict no-scroll fixtures fail: Reveal bounds y780–856 exceed the 662dp viewport. Fresh and returned identities remain separate.

Original capture count: **2**. Review methods: 2 attributed direct original view.

Source: JVM Compose; no PCK or native runtime. [Compare all four iterations](../README.md). [Original preservation manifest](manifest.json).

| Original JUnit suite | Tests | Failures | Errors |
| --- | ---: | ---: | ---: |
| [StandardReturnLayoutTest[jvm]](test-results/jvmTest/TEST-dev.partydeck.app.StandardReturnLayoutTest.xml) | 2 | 2 | 0 |

### returned-concealed

<a href="ui-snapshots/standard-return-font2-10570808284129180959/returned-concealed.png"><img src="ui-snapshots/standard-return-font2-10570808284129180959/returned-concealed.png" width="240" alt="returned-concealed"></a>

Original filename: `returned-concealed.png` · **411 × 662** · 37,937 bytes.

SHA-256: `c600d0099006d1d881f587d78da1866d12680ca1977f7c574edbf75d311c751b`.

**[Attributed direct original view (`/root/ui_game`)](../provenance/ui-game-failure/review.json).** Round 2, Moxie current claim, turn/rank and hand count are readable. The concealed panel begins near y536 and its explanatory copy extends below the viewport. Reveal is absent from the image. Authentic JUnit records full Reveal bounds [36,780,375,856] against viewport [0,0,411,662] for this case; the whole-control assertion failed.

Scroll context: `no input or scrolling before capture`.

Source iteration: `fixture-failed-v2`; source file mtime: `2026-09-10T22:26:51.680031+00:00`.

### fresh-concealed

<a href="ui-snapshots/standard-return-font2-3094935607218232296/fresh-concealed.png"><img src="ui-snapshots/standard-return-font2-3094935607218232296/fresh-concealed.png" width="240" alt="fresh-concealed"></a>

Original filename: `fresh-concealed.png` · **411 × 662** · 37,937 bytes.

SHA-256: `c600d0099006d1d881f587d78da1866d12680ca1977f7c574edbf75d311c751b`.

**[Attributed direct original view (`/root/ui_shell`)](../provenance/ui-shell-before/direct-views.json).** Round 2, Moxie current claim, turn/rank and hand count are readable. The concealed panel begins near y536 and its explanatory copy extends below the viewport. Reveal is absent from the image. Authentic JUnit records full Reveal bounds [36,780,375,856] against viewport [0,0,411,662] for this case; the whole-control assertion failed.

Scroll context: `no input or scrolling before capture`.

Source iteration: `fixture-failed-v2`; source file mtime: `2026-09-10T22:26:51.786031+00:00`.
