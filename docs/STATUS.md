# PartyDeck status report

**Updated 2026-09-11, 04:14 UTC. The app is not yet production-ready.**
The original release scope remains **81%** complete by the existing milestone
estimate. The additional Godot scope remains **3 of 6 acceptance groups (50%)**.
These scopes are separate and are not averaged.

Last Light, practice, the Standard interface, host-authoritative multiplayer,
recipient-private game views, TLS transport, reconnect handling, settings and
licensed/original assets are implemented. Both real **Godot 2D and 3D**
presentations and native hosts are retained for comparison. Android and iOS
shipping profiles currently expose Standard table; Godot selection is enabled
in explicit qualification builds while native acceptance is completed.

## Current verified results

| Work and source | Verified result | Remaining limit |
| --- | --- | --- |
| [Full Android — 34538972728](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34538972728), `dd6df8a5` | 264 JUnit tests and 259 Python checks pass; lint has zero errors and 11 warnings. Godot debug has 30 passes; optimized has 28 passes and two explicit renderer-death skips. Native Reveal, selection, Play and Standard return pass in both modes. Package, PCK, signature and alignment audits are sealed; the additional content/fixture/R8 screen passes. | The overall workflow failed on iOS. Optimized renderer-death cases were skipped; these results do not establish physical-device behavior. |
| [Adaptive Android — 34540229407](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34540229407), `4ee4563d` | All 96 adaptive scopes and four installations pass; 16 held proofs are accepted. All six original archives, producer/source/four-consumer package bindings and the inclusion audit are complete and frozen. Review receipts cover all 2,476 frame identities from the 32 recordings, directly or by verified identical bytes. | This run captured 3D latest-claim truncation in short split-screen views at 200% text. The correction is now integrated and reviewed on desktop; affected native presentation acceptance is open. Full review coverage does not establish offscreen privacy or interaction reachability. |
| [Android rerun — 34555402070](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34555402070), `aa10e0bd` | CI reports success for the producer and all four consumer jobs. | Originals are being collected and package/source bindings remain open. The new 96-scope outcomes and native pixels are not yet accepted; focused public-claim scrolling proof remains open. |
| [Retained native iOS — 34540908385](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34540908385), `65e4d86e` | All three lifecycle, concealment and re-entry cases pass; source, artifact and package binding is frozen. | This retained-host result does not complete production-session or hardware performance acceptance. |
| [Full iOS retry — 34545222517](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34545222517), `3d73b343` | Shared Native 156/156 and ordinary Simulator 9/9 pass. The separate UIKit execution passes 3/3; those case identities also occur in the ordinary nine. Three actual Simulator app packages and the unsigned device package pass inspection. Collection and final preservation are frozen. | Production Godot is **0/2**: both cases fail their initial Home observation decoding before Practice. The rejected value was not retained, so the failing field is still unknown. |
| [Focused iOS — 34554200601](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34554200601), `253e9656` | **3D passes; 2D fails: one passed, one failed, zero skipped.** Collection and source/package bindings are frozen; final preservation is independently approved. | The combined two-case gate failed. The 2D failure is “Observe fresh, current production renderer diagnostics,” before gameplay iteration; its actual cause is unproven. This run predates the corrected 3D pack. |
| [JVM TLS and measurements — 34547302716](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34547302716), `5341ffe8` | All three real TLS integration cases pass, including six-seat winner, rematch and same-controller rehost. Both measured suites complete two warmups and five samples; independent raw-data interpretation and accounting pass. The planned JVM integration and meaningful profiling work is complete. | These are JVM and local TLS measurements. Physical LAN and mobile hardware measurements remain separate. |

The earlier [iOS diagnostic, 34550903117](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34550903117),
at `ac2200ae`, failed both cases with `data_corrupted` at `$` and 512 bytes.
Its originals and final preservation are independently reviewed; the decoder
cause remains unproven. The [previous diagnostic, 34547924733](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34547924733)
stopped before XCTest and remains frozen.

The [new full iOS run, 34556241013](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34556241013),
at `f4832799`, was cancelled after device staging failed on a stale retained-engine
PCK pin; production tests did not run. That pin is corrected in `fd3c8366`.
Reviewed startup timing diagnostics are integrated in `39405bb0`; native
validation remains pending, and the diagnostics do not establish or fix the cause.
The [full iOS follow-up, 34559902607](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34559902607),
on `39405bb0`, started at 03:49:39 UTC and is in progress; no native outcome is
available at this snapshot.

The reviewed 3D correction is integrated in `aa10e0bd`: public rank, turn and
claim text moves into the body when the short layout cannot keep it readable.
All eight final desktop runs pass, and the independently reviewed regression
is committed in `456d40e1`. Native public-claim scrolling acceptance remains open.

The current exported renderer pack is **1,551,096 bytes / 136 entries**, SHA-256
`83b79592cb1542f2b0f7ad18222f686f9bc23cd7810b8072662bf502b9d605b1`.
Test-signed Android packages and unsigned iOS device packages are qualification
artifacts; publisher signing remains open.

## Work remaining

1. **Finish iOS production qualification.** Validate the integrated startup
   diagnostics and retained-engine pack pin, resolve the 2D failure using actual
   evidence, and pass both production cases. Keep observations, privacy and
   lifecycle checks strict; complete affected integrated checks.
2. **Finish Android adaptive acceptance.** Complete the new run's collection,
   package bindings and outcome/pixel review. Implement, independently review
   and execute the focused 3D public-claim scrolling check at 200% text in a
   short split-screen view. The desktop correction and older accepted outcomes
   do not complete this native check.
3. **Complete native delivery work.** Finish mobile presentation acceptance,
   enable accepted native modes through
   the shipping configuration, and verify integrated delivery, including the
   shipping-profile smoke checks. Standard table remains the accessible route;
   both real Godot implementations stay available for the user's comparison.
4. **Execute the physical-device release matrix.** Android/iPhone and mixed LAN
   sessions with 2–6 players, reconnect/rematch and host loss; actual permissions,
   QR/sharing, background privacy and process loss; TalkBack/VoiceOver, responsive
   layouts, sound/haptics, frame pacing, memory, battery and network behavior.
5. **Complete publisher and store requirements.** Supply publisher/support/privacy
   identities and public policy URL, production signing and store accounts;
   complete signed test tracks/TestFlight, listings and submission. Publisher
   assessment of the Adobe DNG SDK commercial terms remains open.

The final two items require external hardware or publisher access. The earlier
software and publication work can continue independently. Acceptance details are
in the [implementation plan](IMPLEMENTATION.md), [Godot plan](../godot/README.md)
and [release qualification record](release-qualification.md). Current work is
assigned in the [30-agent ownership ledger](AGENT-OWNERSHIP.md).

## Completion accounting

The inherited original-scope estimate is unchanged: **80.5 weighted points,
rounded to 81%**. It describes milestones, not test coverage or remaining time.

| Original scope | Weight | Milestone complete |
| --- | ---: | ---: |
| Features and architecture | 30% | 100% implemented |
| UI, assets and accessibility implementation | 15% | 100% baseline implemented |
| Configured baseline automated qualification | 20% | 100% baseline |
| Builds and unsigned packaging | 15% | 100% baseline |
| Physical-device release validation | 15% | 0% |
| Publisher, signing and store readiness | 5% | 10% |

Godot's completed groups are real engine/import/export verification, the safe
authority bridge, and matched 2D/3D gameplay scenarios with desktop launch
instructions. Native lifecycle, mobile presentation/accessibility acceptance,
and both qualified native previews remain partial. New test counts and images
do not increase these estimates by themselves.

## Included deliverables and earlier evidence

- [Run the app](../README.md), [compare 2D and 3D](../godot/comparison/README.md),
  and [build or qualify iOS](../iosApp/README.md).
- [Review gallery](screenshots/README.md): **4,699 original images + 2,806
  supplements + four asset proofs** are published, including the 27 focused-iOS
  stills and nine desktop regression captures. Each collection retains its
  actual result and viewing scope; publication does not imply every original
  was viewed.
- [Verified JVM baseline](measurements/jvm-20260911/README.md) and
  [measurement method](jvm-rule-network-measurements.md): the eight-file report
  and raw-data bundle is independently verified and included in this delivery.
- [Prior detailed status](https://github.com/Apdelrahman1911/PartyDeck/blob/6e7ef324c93fcde3f033947c42b2ec114442ab6e/docs/STATUS.md),
  [pause checkpoint](RESTART.md), and [historical release evidence](release-qualification.md)
  retain the earlier investigations and results.
