# PartyDeck status report

**Snapshot: 2026-09-10, 17:00 UTC.** Published source is through `16d828e`.
Estimated completion of the original app release scope is **81%**. The added
Godot scope has **3 of 6 acceptance groups complete (50%)**. These are different
scopes and must not be averaged. **The app is not yet ready for production.**

The Standard app is implemented and its original baseline automated checks have passed. Both
real Godot presentations, **2D and 3D**, exist and remain until the user chooses.
Desktop scenarios and all four Android comparison cases passed. Expanded
production-app checks now reach both Android renderers in debug builds and have
found remaining Android and iOS defects. These are project work. Earlier passing
baselines do not make the current integrated release qualified.

## Completion calculation

| Original release workstream | Weight | Complete | Evidence and remaining limit |
| --- | ---: | ---: | --- |
| Core features and architecture | 30% | 100% implemented | Rules, authority, protocol, transport, practice and app flows exist; physical multiplayer qualification is separate |
| UI, assets and accessibility implementation | 15% | 100% baseline implemented | Screens, assets, preferences and Standard controls exist; an expanded iOS audit found a small feedback element, and actual assistive-technology qualification remains |
| Configured baseline automated qualification | 20% | 100% | Android/JVM, shared iOS, Swift TLS and ordinary native app flows pass, including separate Android API 36; added Godot regressions remain separate |
| Builds and unsigned packaging | 15% | 100% | Original Android APK/AAB and iOS Simulator/unsigned device packages build; latest Godot production iOS links also verify |
| Physical-device release validation | 15% | 0% | Physical Android/iPhone release matrix has not run here |
| Publisher, signing and store readiness | 5% | 10% | Configuration and instructions exist; identities, policies, signing, store setup and submission remain |

Weighted result: **80.5%, rounded to 81%**. This is a milestone estimate, not test
coverage, a reliability guarantee or an estimate of time remaining. Reviewed
source and partial native runs do not automatically increase it.

| Additional Godot acceptance group | Status |
| --- | --- |
| Verified engine, imports and real exported resources | Complete |
| Common authority bridge, privacy and message validation | Complete |
| Matched 2D/3D gameplay scenarios and desktop launch instructions | Complete |
| Native entry, lifecycle, concealment, exit/re-entry and teardown on both platforms | Partial |
| Mobile visual, interaction, responsive and accessibility acceptance | Partial |
| Both qualified, independently selectable native previews | Partial |

Exact definitions are in [the Godot plan](../godot/README.md).

## What is implemented

- **Last Light:** original two-to-six-player bluffing game, thirty-card deck,
  private five-card hands, one-to-three-card claims, challenges, six-light
  penalties, elimination, round advancement, winners and rematches.
- **Practice:** complete bot matches using the same authority as multiplayer.
- **Local multiplayer:** hosting, joining, lobby readiness, invitation sharing
  and pasting, QR display/native scanning, optional discovery, same-seat
  reconnection and recoverable errors. Real LAN qualification remains.
- **Transport and privacy:** native TLS, full host-certificate pinning,
  admission/reconnect credentials, bounded messages/queues, replay/revision
  rejection, recipient-specific views and cryptographic randomness.
- **App flows:** Home, Host, Join, Lobby, Rules, Settings, gameplay, round results
  and winner; hand reveal/concealment; persistent sound, haptic and reduced-motion
  preferences. Rules-to-Practice navigation is verified.
- **Assets and architecture:** original cards, symbols, launcher artwork and
  sound; licensed typography and offline notices; shared KMP modules and native
  services. The optional desktop launcher reuses the app.
- **Godot:** real 2D/3D scenes, recipient-safe event bridge, attachment to the
  existing session, Android process-separated host and retained iOS engine with
  Swift adapter. Production native qualification remains incomplete.

The Standard table supplies the agreed accessible native controls route on the
same session. A second complete Godot accessibility overlay is not required.
The canvas has no mobile accessibility adapter. Feasible native assertions are
being extended; actual TalkBack/VoiceOver speech, focus and traversal remain
unqualified. The winner heading now has polite live-region semantics, with seven
passing focused UI tests.

Default shipping configuration exposes no Godot modes. Explicit build-time
qualification profiles enable both for testing. Completing qualification and
shipping activation remain project work. Host migration and restoring matches
after host process death are outside the agreed first-release scope.

## Automated results

Each result belongs to its stated source/run. Repeated runs are not added as new
coverage, and earlier successes are not assigned to a new pack or host.

| Verification | Executed result |
| --- | --- |
| Original app, [34428798269](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34428798269), `15ab640` | 118 Android/JVM tests, 83 shared iOS tests, three Swift TLS tests and three native iOS UI tests pass; Android debug/optimized flows and iOS Simulator/unsigned device builds pass |
| Rules framing, [34432935952](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34432935952), `8d8d429` | 118 tests and both APK flows pass; Rules button borders and navigation verified at normal/200% text |
| API 36 ordinary app, [34457458638](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34457458638), `f11f92e` | Both APK flows pass, 86 steps/thirty stage captures per APK; Godot session smoke disabled |
| Android production API 35, [34496267571](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34496267571), `410c938` | 256 JUnit cases in 40 suites and 131 Python checks pass; zero lint errors/eleven warnings. Ordinary debug/optimized flows pass. Debug completes the 2D sequence and reaches 3D renderer-death preparation before the cumulative ten-minute wrapper cutoff; no final debug result exists. Optimized reaches native initialization, then aborts on missing JNI methods |
| Android adaptive API 36, [34496282263](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34496282263), `410c938` | Producer and all four installations pass. Both debug normal/200% cases pass initial native 2D landscape entry. Normal text then fails rotation-retirement observation and video stream validation; 200% held rotation is unsupported and portrait Standard re-entry fails. Both optimized variants abort during JNI initialization. Later scopes, including 3D acceptance, remain unexecuted |
| Android comparison, [34478725424](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34478725424), `c6ea1dd` | All four normal/200% 2D/3D cases and twelve exits pass. Independently verified current pack/source, 445 host observations, 430 applied diagnostics, 112 taps, 42 swipes and 48 captures |
| iOS production, [34496252392](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34496252392), `410c938` | Shared tests: 150 cases/23 suites, one failure in a deferred mode switch. Ordinary native unit tests: 6/6 pass, including all three UIKit layout cases' unguarded assertions. Qualification-only geometry assertions were not compiled in that ordinary bundle. Ordinary UI: 2/3 pass; expanded practice fails the unfiltered hit-area audit for selection-count feedback. The separate layout gate and both production session gates are skipped. Unsigned device artifact retained; ordinary failure prevents the Simulator app archive step |
| Earlier iOS production, [34480503751](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34480503751), `7012ba0` | Simulator/device packages and real link maps verify. Both sessions reach ACTIVE/Ready but fail observation with a roughly 26-point-high native surface; this is the original evidence for the subsequent layout correction |
| iOS native hosts, [34488350932](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34488350932), `4f69429` | Authority 5/5 pass. Retained 2/3 pass: background/resume and repeated entries pass; stale-callback re-entry fails. Both retained qualification flags remain false. Long engine/main-thread intervals are measured; their blocking work is not yet identified |
| Current iOS retry, [34503244345](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34503244345), `1cd34a3` | Still running. Shared native suite passes 156/156 cases in 24 suites, including the original deferred-close regression and six new common cases. Unsigned device job passes. App accessibility audit, separate layout gate and production sessions are not yet reported |
| Current Android API 35 retry, [34503251315](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34503251315), `1cd34a3` | Runtime in progress with the JNI retention fix, enlarged feedback bounds and cumulative twenty-minute variant budget. No final runtime outcome yet |
| Current retained diagnostic, [34505106959](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34505106959), `16d828e` | Optional stack sampling enabled around the unchanged retained tests. No native diagnostic or qualification result yet; sampling may affect timing |
| Packed renderer, `4d8bd92` / `c6ea1dd` | 677 real-render assertions pass: 155 boundary, 216 terminal-return and 306 redraw |

Historical screenshot reports are excluded from current test totals. The latest
API 35 report also verifies zero historical JUnit copies in its uploaded report.
Disposable CI signing is
not publisher signing. Comparison acceptance does not qualify the production
shell, physical LAN or hardware GPUs.

## Fixes and parallel work

| Work | Done | What remains |
| --- | --- | --- |
| iOS linkage and test headers | Corrected archive extraction and native header search paths. Actual Simulator/device links, sole framework ownership, unit compilation and baseline XCTest pass | Closed for the tested packages; retain regression checks |
| Android presentation selection | Bounded pending choice integrated; 73 focused controller/lifecycle/observation tests passed. Real debug runs now launch both modes; normal/200% initial 2D landscape entry passes | Complete subsequent lifecycle and gameplay acceptance; optimized crash is separate |
| Common deferred mode switch | Narrow correction integrated and pushed after two independent source reviews; 35 focused common tests pass. The original failing iOS regression and all six new common cases now pass in the 156-case native suite | Complete real production mode switching; factory, focus, binding, privacy and the original five-second deadline remain enforced |
| Optimized Android JNI | Independently reviewed retention rules pushed. Rebuilt optimized APK passes all 122 selected exact native-interface declarations, versus 69/122 in the original failed optimized APK | Confirm native Ready, gameplay and lifecycle on the running API 35 retry, then API 36. The static audit covers the exercised string/primitive boundary, not every optional Godot reflection feature |
| Android adaptive scenarios | Three corrections integrated and independently reviewed: poll actual Activity removal, verify/reveal after a real portrait rotation, and validate the two documented screenrecord metadata tracks while preserving decode timestamps. All 172 host tests pass, retaining every baseline test | Rerun the adaptive native matrix and the separate API 36 real-engine gameplay checks. Existing privacy, process-attribution, timing, recorder-growth and visibility gates remain |
| Android runtime budget | Expanded sequence now has a bounded twenty-minute cumulative budget on both API 35 and 36; independently reviewed and pushed | Running retry must reach an actual final result; every per-stage deadline stays unchanged |
| iOS production layout | Content sizing and hidden-ancestor observation integrated. All three UIKit cases executed and passed in the ordinary native unit bundle | Pass the separate layout receipt and both production sessions after the earlier failing checks are fixed |
| iOS native responsiveness | Authority 5/5 and retained 2/3 pass. Bounded optional stack sampler reviewed, integrated and pushed; 22 portable checks and eight owner workflow branch checks pass | Collect actual stacks from the running diagnostic, identify and fix the cause, then rerun retained acceptance. Missing or partial samples do not qualify behavior |
| Android Standard accessibility | Extended five-card, checked-state, selection-limit, Hide and authoritative Standard action checks integrated; API 35 debug progresses through the full 2D return/action sequence | Complete current full runs and adaptive return scenarios; hardware TalkBack remains separate |
| iOS Standard accessibility | Feedback semantic layout now has a 48-dp minimum height. Exact modifier/frame propagation independently reviewed; seven gameplay layout tests pass and the original JVM screenshot is retained | Running native retry must pass the unchanged unfiltered audit, Hide/fresh-Reveal checks and authoritative Standard action after Godot return |
| Android native gameplay evidence | Qualification-only geometry hook and separate real Reveal/card/Play checker independently reviewed, integrated and pushed; 155 host tests pass | Execute the new checker in actual API 36 production-app runs; renderer view revisions alone are not authority receipts |
| Screenshots | 2,013 originals plus 13 supplements pushed at `1b9c1a0`; 309 new/changed paths verified against the frozen handoff | Publish the next batch from newly completed runs and their original failure context |

Agents use **gpt-6-astra with max reasoning**. Android, iOS, checker,
accessibility and rendering work proceeds concurrently with independent review.
Root owns shared builds, integration and Git. Security review remains source-only.

The current PCK remains **1,549,656 bytes / 136 entries**, SHA-256
`d6adbba1b5cbd6a1ac3a5754e4294363eae70ae9540af4ba12040cd4cfff44e0`.
The v7 native module adds numeric stage timings only. Reviewed CoreAudio dormancy
and main-loop access patches remain; the optional mouse patch remains unapplied.
No cover, lifecycle, input-currentness or timeout gate is relaxed for a pass.

## What still needs to be done to finish

1. **Complete implementation and automated native qualification.** Qualify the
   integrated Android JNI, common switching and accessibility fixes, finish
   Android checker review and diagnose/fix iOS responsiveness. Complete production 2D/3D gameplay
   and lifecycle/return/process-loss checks, run all adaptive cases, finish
   supported accessibility assertions and visual review, rerun affected baselines,
   and enable shipping Godot modes only after their gates pass. This work
   continues without publisher or physical-hardware inputs.
2. **Execute physical-device release validation.** Android-to-iPhone and
   same-platform LAN with two-to-six players, rematches, QR/camera, permissions,
   sharing, network loss/reconnect, host loss, background/lock/privacy/process
   death; minimum/current devices, phones/tablets, orientation and large text;
   actual TalkBack/VoiceOver; startup, frame pacing, memory, battery, sound/haptics
   and network use. Required hardware is unavailable here.
3. **Complete publisher/store setup.** Publisher/support/privacy identities,
   public policy, Android signing and Apple team/provisioning, Play Console/App
   Store Connect listings/disclosures, signed test tracks/TestFlight and
   submission. Publisher assessment of Adobe DNG SDK commercial terms remains;
   notices alone do not settle it.

## Published deliverables

- Source milestones pushed through `16d828e`.
- [Screenshot gallery](screenshots/README.md): **2,013 original PNGs plus 13 supplemental images**,
  with 6,858 evidence files and 8,876 checksum entries. Recent captures are being
  prepared with their actual run/failure context.
- [Verified Android 2D/3D preview download](../godot/comparison/README.md),
  [main instructions](../README.md), [validation commands](../scripts/README.md)
  and [iOS setup](../iosApp/README.md).
- [Release qualification](release-qualification.md),
  [CI research](research/engine-ci.md) and [Godot reviews](../godot/reviews/).
  New successes do not rewrite earlier failed results.
