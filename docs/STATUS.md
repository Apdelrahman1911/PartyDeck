# PartyDeck status report

**Fixed snapshot, 2026-09-11 17:37:51 UTC. The app is not yet production-ready.**
The original release scope remains **81%** complete by the existing milestone
estimate. The additional Godot scope remains **3 of 6 acceptance groups (50%)**.
These scopes are separate and are not averaged.

Last Light, practice, the Standard interface, host-authoritative multiplayer,
recipient-private game views, TLS transport, reconnect handling, settings and
licensed/original assets are implemented. Both real **Godot 2D and 3D**
presentations and native hosts are retained for comparison. iOS now enables both
Godot modes in shipping source configuration after reviewed native, package and
visual acceptance. Shipping rerun #45 now has independently reviewed original
route and screenshot results; its actual app/package review remains open.
Android Godot remains qualification-only, with Standard in its shipping profile. Standard also
remains available on iOS.

The picker-disposal correction is pushed in `5d6b1f86`: selection waits for
picker removal before committing a native presentation. **45 focused JVM tests**,
including both real Skiko popup tests, and **Android shared compilation** pass;
the exact integration is independently approved. Focused Android qualification now uses
the continuous-touch helper integrated in `ef568520`. Its **APK build**, **472
configured Python tests**, **131 independent behavior controls** and **13
integration controls** pass. Run-specific original outcomes and remaining
native acceptance gates are recorded below.

## Current qualification

| Work and source | Recorded result | Remaining limit |
| --- | --- | --- |
| [Android adaptive rerun — #8 / 34555402070](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34555402070), `aa10e0bd` | All 96 adaptive outcomes and four installations are independently accepted. Package/source/four-consumer closure is complete, and all six original ZIPs survive. Four reviewed stills are now published. | The recorded stills and adaptive passes do not complete focused public-claim scrolling or offscreen interaction reachability acceptance. |
| [Focused Android — #9 / 34568971032](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34568971032), `69500a9c` | Independent original-outcome accounting remains **2 focused passes, 2 failures and 4 not reached**, plus **2 installation passes**. Debug failed while staging the real claim; optimized failed the body sweep. Whole-collection metadata closure is now independently approved. | Collection closure preserves the failed run. Package, native/pixel and public-action acceptance remain separate; the scenario difference from #8 is explained below. |
| [Focused Android rerun — #10 / 34575134242](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34575134242), `094ea9ae` | The producer passed and both native consumers failed. Root’s bounded diagnostics record successful installation, real-claim/native entry and short split in both variants, followed by a failed half-page-overlap check during the body sweep. Four diagnostic images are now published. | These selected diagnostics and images are not canonical full-archive or native acceptance. The reviewed correction is integrated in `b2566f53` for #11; complete package bindings and independent 3D claim/guidance/Challenge reachability acceptance remain open. |
| [Focused Android rerun — #11 / 34587116038](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34587116038), `b2566f53` | Independent outcome review verifies **6 focused passes, 1 failure and 1 not reached**, plus **2 installation passes**. Whole-collection metadata closure is now independently approved. Source/package/consumer metadata and original/installed APK identity bindings are independently accepted. | The optimized body sweep still failed: **104 units against a 51.5-unit limit**, with cause unproven. Metadata closure does not establish native public-action, pixel, shipping or performance acceptance. |
| [Focused Android rerun — #12 / 34609437169](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34609437169), `ef568520` | Independent original-outcome review confirms **8 focused passes and 2 installation passes, with zero failures or not-reached checks**. Both debug and optimized pass real-claim entry, short split, body sweep and Standard return on the continuous-touch input integration. | Collection finalization, actual helper/package/installed-byte bindings, **52 planned screenshot reviews** and Android shipping acceptance remain open. An installation acknowledgement does not establish installed helper bytes. |
| [Full adaptive Android — #13 / 34610555458](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34610555458), `ef568520` | CI succeeded for the producer and all four debug/optimized consumers at 1.0x/2.0x text. The six-source collector is installed and independently approved within source/installation scope. | Original collection and adaptive testcase accounting, actual packages and independent pixel/native acceptance remain pending. Collector installation does not establish those results. |
| [Full iOS follow-up — 34559902607](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34559902607), `39405bb0` | Shared Native passes 156 tests across 24 suites; ordinary Simulator passes 9/9, separate UIKit passes 3/3, and the actual production 2D/3D cases pass 2/2. The dedicated original-result/64-observation audit and inspection of all four actual app packages are independently accepted. All 51 original screenshots have direct independent review; both assigned mode reviews and canonical metadata preservation are sealed. | This Debug arm64 Simulator qualification skipped the shipping-picker test. The measured timing concern and capture limits below remain open; metadata sealing creates no reboot-persistent bulk archive. |
| [Dedicated iOS shipping — #41 / 34577058494](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34577058494), `4df1b611` | The sole shipping XCTest failed at first 2D entry after nativeReady: **0 passed / 1 failed / 0 skipped**. All three ZIPs, two logs and assigned independent reviews are complete. Its one shipping Simulator app is **accepted within packaged-byte scope**, with 2D/3D enabled, no qualification override and the old `83b79592` PCK. All three pre-entry PNGs are independently reviewed. | Package acceptance does not repair the failed native route. No post-entry or failure-associated PNG was retained; Standard return, 3D, Leave and shipping native-frame acceptance remain unverified. This package does not qualify later source or the new PCK. |
| [iOS shipping diagnostic — #42 / 34589069960](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34589069960), `d9ae0500` | The shipping case remains **0 passed / 1 failed / 0 skipped**. All three ZIPs and two logs are collected; independent execution/metadata closure and the six-original join are complete. Selected original review records visible native 2D with no visible picker, while fresh and retained picker queries exist and are nonhittable. | The actual delayed internal stage remains unproven. Source review supports a Dialog-disposal hypothesis; later source/test work does not retroactively prove #42’s cause or native success. Package, complete shipping routes and broader native/pixel acceptance remain separate. |
| [iOS timing — #43 / 34593991142](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34593991142), `825b730d` | The producer passed, but the native Simulator engine step failed during strict input staging because `frame_timing.h` was absent from the allowlist. The focused session/timing step was explicitly skipped. | No native testcase or timing outcome was produced. The reviewed one-line staging correction is integrated in `56bb91f1` for #44. |
| [iOS timing rerun — #44 / 34600728293](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34600728293), `56bb91f1` | Producer and focused production CI jobs passed, including native Simulator engine compilation and session step 17. All three original archives and two logs are collected, with independent collection metadata closure. Dedicated shipping execution was skipped. | The original timing audit and independent interpretation remain pending. CI success and collection closure supply no timing, performance, package or shipping acceptance. |
| [iOS shipping rerun — #45 / 34607946293](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34607946293), `5d6b1f86` | Independent original review confirms **1 passed / 0 failed / 0 skipped**: both native 2D/3D picker routes and both Standard returns passed. **All 9 original PNGs** are independently approved within their visible scope, with the clipping limits below. | Actual app/package verification remains pending. Native Leave was visible/hittable but unexercised; the route used Standard returns and final shared confirmed Leave. Offscreen reachability, continuous privacy and performance remain separate. |
| [iOS production follow-up — #46 / 34622875502](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34622875502), `069b4d9a` | The renderer producer passed, but the focused production CI job **failed at step 17**. | Original testcase counts, failure cause and timing results remain unknown. Terminal CI metadata supplies no native, timing or package acceptance. |
| [JVM TLS and measurements — 34547302716](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34547302716), `5341ffe8` | All three real TLS integration cases pass, including six-seat winner, rematch and same-controller rehost. Both measured suites complete two warmups and five samples; independent raw-data interpretation and accounting pass. The planned JVM integration and meaningful profiling work is complete. | These are JVM and local TLS measurements. Physical LAN and mobile hardware measurements remain separate. |

Runs **#8 and #9 exercise different scenarios**. #8 covers broad adaptive checks;
#9 adds the focused real public-claim and body-scroll route. Debug stopped while
staging the claim, and optimized failed its scrollbar-driven input sweep. #12's
continuous-touch run now passes the focused checks in both variants. The earlier
failures remain part of the record.

The nine #45 screenshots show lower 2D seat content, right-side 3D seat text and
part of the 3D Return to lobby control clipped at scroll-area edges. Current
source investigation explains these as intentional scrolling areas; actual
reachability after scrolling and historical source/package equality remain
unverified. The visible-scope approval does not establish full access to every
offscreen control.

The current full-iOS collection contains **five original ZIPs and 713 members**.
Its canonical metadata freeze binds all eight final review outcomes. Bulk
originals remain in the registered temporary evidence root and must be preserved.
Direct visual review records initial 3D Return to lobby clipping, with full
controls visible after the actual scroll, and a partially visible 2D hand strip.
The immediate 2D NEXT_ROUND capture still shows the prior result panel; accepted
round-2 state and later ROUND 2 pixels are separate evidence. These bounded
approvals do not establish every offscreen control's reachability, continuous
privacy or shipping screenshots. Observation geometry does not substitute for
viewing screenshots.

The actual Simulator timing audit records completed 3D draw and iteration maxima
of **18.764 s** and **18.735 s**, already present at the first retained native 3D
observation. This is a measured Simulator latency concern within a passing case.
The cumulative counters do not identify an exact frame, a CPU/GPU cause, or the
cause of the older focused failure; unchanged maxima do not rule out later
stalls. Performance acceptance remains open.

The strict timing validator retains its **52 passing host-test methods** and
independently reviewed staging correction. #44's originals are collected and its
collection review is closed; the timing audit and interpretation remain pending.
Host checks and CI success do not qualify native performance.

The current locally verified renderer pack is **1,553,628 bytes / 138 entries**,
SHA-256 `e516e6b8e1bd6c82b8779fa18a9a15503e39f66b2029427a6babb53848747cad`,
from the reviewed `b2566f53` source integration. The earlier accepted full-iOS
packages and the accepted #41 shipping package contain the preceding **1,551,096 bytes / 136 entries** pack, SHA-256
`83b79592cb1542f2b0f7ad18222f686f9bc23cd7810b8072662bf502b9d605b1`.
The updated native PCK pin requires fresh Simulator/device engine builds and
matching module, staged-input, link and actual-package evidence for the new pack.
Old engine receipts and accepted packages do not qualify this later source.
Test-signed Android packages and unsigned iOS device packages are qualification
artifacts; publisher signing remains open.

## Recovery and current evidence

The **04:57 UTC** runtime restart erased earlier `/tmp` and `/dev/shm` workspaces,
including some originals, private candidates and review receipts. Repository
files, durable evidence and the published gallery survived. Recovered historical
records retain their attribution; an old path alone does not establish current
availability. [RESTART.md](RESTART.md) remains the historical checkpoint.

Published gallery totals remain **4,764 originals / 203 collections / 26,261
checksum paths**. Nine newly reviewed #45 screenshots are staged for publication;
independent stage review and publication are still pending at this cutoff, so
they are not included in those totals. Retained reviews preserve each run's
original outcome and separate package, visual and performance limits.

## Work remaining

1. **Investigate measured iOS timing.** Complete #44's original timing audit and
   independent interpretation. Collect and review #46's original failure,
   testcase and timing evidence. Resolve the long completed 3D timing scopes
   before accepting Simulator performance; no exact frame or CPU/GPU cause is
   established.
2. **Finish Android native acceptance.** Close #12 collection finalization,
   helper/package bindings and the 52 planned screenshot reviews. Collect and
   independently review #13's original outcomes, packages and pixels; #10
   canonical collection also remains open. Verify full public claim text,
   guidance and Challenge reachability at 200% text in short views. Passing
   focused checks and closed #9/#11 metadata do not complete these separate gates.
3. **Complete native delivery work.** Verify #45's actual app/package and bind
   rebuilt iOS engines and apps to the new pack. Check offscreen scrolling and
   native Leave behavior beyond the accepted Standard-return route. Finish
   review and publication of the nine #45 screenshots. Android shipping
   activation remains conditional on its remaining native and delivery checks.
   Standard remains the accessible route; both real Godot implementations stay
   available for comparison.
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

## Earlier recorded qualification

These rows retain their original execution and review scope. They do not assert
that every historical temporary evidence path remains available after restart.

| Work and source | Recorded result | Remaining limit |
| --- | --- | --- |
| [Full Android — 34538972728](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34538972728), `dd6df8a5` | 264 JUnit tests and 259 Python checks pass; lint has zero errors and 11 warnings. Godot debug has 30 passes; optimized has 28 passes and two explicit renderer-death skips. Native Reveal, selection, Play and Standard return pass in both modes. Package, PCK, signature and alignment audits are sealed; the additional content/fixture/R8 screen passes. | The overall workflow failed on iOS. Optimized renderer-death cases were skipped; these results do not establish physical-device behavior. |
| [Adaptive Android — 34540229407](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34540229407), `4ee4563d` | All 96 adaptive scopes and four installations pass; 16 held proofs are accepted. All six original archives, producer/source/four-consumer package bindings and the inclusion audit are complete and frozen. Review receipts cover all 2,476 frame identities from the 32 recordings, directly or by verified identical bytes. | This run captured 3D latest-claim truncation in short split-screen views at 200% text. The correction is now integrated and reviewed on desktop; affected native presentation acceptance is open. Full review coverage does not establish offscreen privacy or interaction reachability. |
| [Retained native iOS — 34540908385](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34540908385), `65e4d86e` | All three lifecycle, concealment and re-entry cases pass; source, artifact and package binding is frozen. | This retained-host result does not complete production-session or hardware performance acceptance. |
| [Full iOS retry — 34545222517](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34545222517), `3d73b343` | Shared Native 156/156 and ordinary Simulator 9/9 pass. The separate UIKit execution passes 3/3; those case identities also occur in the ordinary nine. Three actual Simulator app packages and the unsigned device package pass inspection. Collection and final preservation are frozen. | Production Godot is **0/2**: both cases fail their initial Home observation decoding before Practice. The rejected value was not retained, so the failing field is still unknown. |
| [Focused iOS — 34554200601](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34554200601), `253e9656` | **3D passes; 2D fails: one passed, one failed, zero skipped.** Collection and source/package bindings are frozen; final preservation is independently approved. | The combined two-case gate failed. The 2D failure is “Observe fresh, current production renderer diagnostics,” before gameplay iteration; its actual cause is unproven. This run predates the corrected 3D pack. |

The earlier [iOS diagnostic, 34550903117](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34550903117),
at `ac2200ae`, failed both cases with `data_corrupted` at `$` and 512 bytes.
Its originals and final preservation are independently reviewed; the decoder
cause remains unproven. The [previous diagnostic, 34547924733](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34547924733)
stopped before XCTest and remains frozen.

The [cancelled full iOS run, 34556241013](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34556241013),
at `f4832799`, stopped after device staging failed on a stale retained-engine PCK
pin; production tests did not run. That pin is corrected in `fd3c8366`, and startup
timing diagnostics are integrated in `39405bb0`. The current successful cases do
not establish a cause or causal fix for the older focused 2D failure.

The reviewed 3D correction is integrated in `aa10e0bd`: public rank, turn and
claim text moves into the body when the short layout cannot keep it readable.
All eight final desktop runs pass, and the independently reviewed regression
is committed in `456d40e1`. Native public-claim scrolling acceptance remains open.

## Included deliverables and earlier evidence

- [Run the app](../README.md), [compare 2D and 3D](../godot/comparison/README.md),
  and [build or qualify iOS](../iosApp/README.md).
- [Review gallery](screenshots/README.md): **4,764 original images + 2,806
  supplements + four asset proofs**, with **26,261 checksum paths** across
  **203 collections**, are published.
  The four reviewed Android #8 stills were pushed in
  [`0c646e1b`](https://github.com/Apdelrahman1911/PartyDeck/commit/0c646e1ba0657beda36d82e28ede509209b2462a);
  the 51 full-iOS originals in
  [`00e8c4ac`](https://github.com/Apdelrahman1911/PartyDeck/commit/00e8c4ac9968bb50f35e0acc38a820ac9c17db8d);
  and four Android #10 diagnostic images in
  [`695cd5eb`](https://github.com/Apdelrahman1911/PartyDeck/commit/695cd5eb79b926260d0486581ee62ea3acbf4edc).
  Six further original diagnostics from failed Android/iOS runs are published in
  [`6cc9266b`](https://github.com/Apdelrahman1911/PartyDeck/commit/6cc9266b053f1f750fc7465b0bca74dae545bff9),
  after independent source and destination review.
  Each collection retains its actual result and viewing scope; publication does
  not imply every original was viewed or add native reachability acceptance.
- [Verified JVM baseline](measurements/jvm-20260911/README.md) and
  [measurement method](jvm-rule-network-measurements.md): the independently
  verified eight-file report and raw-data bundle remains included.
- [Prior detailed status](https://github.com/Apdelrahman1911/PartyDeck/blob/6e7ef324c93fcde3f033947c42b2ec114442ab6e/docs/STATUS.md),
  [historical pause checkpoint](RESTART.md), and [historical release evidence](release-qualification.md)
  retain the earlier investigations and results.
