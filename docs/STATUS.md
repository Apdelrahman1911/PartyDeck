# PartyDeck status report

**Updated 2026-09-11, 02:29 UTC. The app is not yet production-ready.**
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
| [Adaptive Android — 34540229407](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34540229407), `4ee4563d` | All 96 adaptive scopes and four installations pass; 16 held proofs are accepted. All six original archives, producer/source/four-consumer package bindings and the inclusion audit are complete and frozen. Review receipts cover all 2,476 frame identities from the 32 recordings, directly or by verified identical bytes. | The 3D latest-claim text is truncated in short split-screen views at 200% text; it sits outside the body scroll area. The proposed correction remains under review; affected native presentation acceptance is open. Full review coverage does not establish offscreen privacy or interaction reachability. |
| [Retained native iOS — 34540908385](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34540908385), `65e4d86e` | All three lifecycle, concealment and re-entry cases pass; source, artifact and package binding is frozen. | This retained-host result does not complete production-session or hardware performance acceptance. |
| [Full iOS retry — 34545222517](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34545222517), `3d73b343` | Shared Native 156/156 and ordinary Simulator 9/9 pass. The separate UIKit execution passes 3/3; those case identities also occur in the ordinary nine. Three actual Simulator app packages and the unsigned device package pass inspection. Collection and final preservation are frozen. | Production Godot is **0/2**: both cases fail their initial Home observation decoding before Practice. The rejected value was not retained, so the failing field is still unknown. |
| [JVM TLS and measurements — 34547302716](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34547302716), `5341ffe8` | All three real TLS integration cases pass, including six-seat winner, rematch and same-controller rehost. Both measured suites complete two warmups and five samples; independent raw-data interpretation and accounting pass. The planned JVM integration and meaningful profiling work is complete. | These are JVM and local TLS measurements. Physical LAN and mobile hardware measurements remain separate. |

The [focused iOS diagnostic, 34550903117](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34550903117),
at `ac2200ae`, failed both production cases. Both case diagnostics report
`data_corrupted` at `$` (the root), with a byte count of **512**. The
original native log and all three original archives are preserved and frozen;
independent preservation review remains pending. The reviewed change to read
the live observation value is integrated at `253e9656`. Its
[focused rerun, 34554200601](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34554200601),
dispatched at 02:19:55 UTC, is in progress with no native outcome at this snapshot.
The implementation cause is not established. The
[previous diagnostic, 34547924733](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34547924733),
stopped before XCTest and supplied no decoder result; its available originals
remain frozen.

The current real renderer pack is **1,550,440 bytes / 136 entries**, SHA-256
`541ded4c5074b56a9e320882a23f357ff8162520fac099e32567ac3a678f2751`.
Test-signed Android packages and unsigned iOS device packages are qualification
artifacts; publisher signing remains open.

## Work remaining

1. **Finish iOS production qualification.** Validate the integrated change to
   observation reads and pass both focused production cases. Keep required
   observations, privacy checks and lifecycle conditions strict; complete
   affected integrated checks.
2. **Finish Android adaptive acceptance.** Review the proposed correction for
   3D claim-text truncation at 200% text in short split-screen views, and validate
   the affected native presentation. Keep the completed 100 outcomes and full frame-review coverage
   separate from acceptance of the corrected layout and remaining interaction.
3. **Complete native delivery work.** Publish later diagnostic captures with
   the final review labels.
   Finish mobile presentation acceptance, enable accepted native modes through
   the shipping configuration, and verify the integrated delivery, including
   the shipping-profile smoke checks. Standard
   table remains the accessible route; both real Godot implementations stay
   available for the user's comparison.
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
- [Review gallery](screenshots/README.md): **4,598 original images + 2,806
  supplements + four asset proofs** are included, with independent authored-file
  and destination verification complete. This includes the 12 full-iOS stills
  and 2,476 adaptive frame identities. Each collection retains its actual result
  and viewing scope; publication does not imply every original was viewed.
- [Verified JVM baseline](measurements/jvm-20260911/README.md) and
  [measurement method](jvm-rule-network-measurements.md): the eight-file report
  and raw-data bundle is independently verified and included in this delivery.
- [Prior detailed status](https://github.com/Apdelrahman1911/PartyDeck/blob/6e7ef324c93fcde3f033947c42b2ec114442ab6e/docs/STATUS.md),
  [pause checkpoint](RESTART.md), and [historical release evidence](release-qualification.md)
  retain the earlier investigations and results.
