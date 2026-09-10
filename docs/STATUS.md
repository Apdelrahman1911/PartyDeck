# PartyDeck status report

**Snapshot: 2026-09-10, 14:58 UTC.** Published source is through `0258150`.
Estimated completion of the original app release scope is **81%**. The added
Godot scope has **3 of 6 acceptance groups complete (50%)**. These are different
scopes and must not be averaged. **The app is not yet ready for production.**

The Standard app is implemented and its baseline automated checks pass. Both
real Godot presentations, **2D and 3D**, exist and remain until the user chooses.
Desktop scenarios and all four Android comparison cases pass. Production-shell
integration still has Android and iOS failures being fixed. These are project
work, not external blockers.

## Completion calculation

| Original release workstream | Weight | Complete | Evidence and remaining limit |
| --- | ---: | ---: | --- |
| Core features and architecture | 30% | 100% implemented | Rules, authority, protocol, transport, practice and app flows exist; physical multiplayer qualification is separate |
| UI, assets and accessibility implementation | 15% | 100% implemented | Screens, original assets, preferences and native accessible Standard controls exist; actual assistive-technology qualification remains |
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
| Android production, [34485028785](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34485028785), `fc431ee` | 228 current JUnit cases in 39 suites and 98 Python checks pass; zero lint errors/eleven warnings. Ordinary debug/optimized flows pass. Both Godot variants tap the real 2D choice, then fail waiting for a native Activity; no renderer process is observed |
| Android adaptive, [34485033488](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34485033488), `fc431ee` | Producer and all four installations pass. All four first landscape checks fail; 92 of 96 scopes unexecuted. Normal text fails Standard preparation; 200% text reaches the 2D picker but no native Activity. No transition videos |
| Android comparison, [34478725424](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34478725424), `c6ea1dd` | All four normal/200% 2D/3D cases and twelve exits pass. Independently verified current pack/source, 445 host observations, 430 applied diagnostics, 112 taps, 42 swipes and 48 captures |
| iOS production, [34480503751](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34480503751), `7012ba0` | Both engine builds, staging, 139 shared native tests and six baseline native/UI cases pass. Three packages and their actual link maps verify. Both production Godot cases reach ACTIVE/Ready but fail the live-observation predicate; originals show a roughly 26-point-high native surface |
| iOS native hosts, [34478720554](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34478720554), `c6ea1dd` | Authority 2/5: normal 2D and secure Exit pass. 2D/200% launch and both 3D action observations fail. Retained 1/3: repeated entries pass; background/stale re-entry fail subsequent 3D warmup |
| Packed renderer, `4d8bd92` / `c6ea1dd` | 677 real-render assertions pass: 155 boundary, 216 terminal-return and 306 redraw |

Historical screenshot reports are excluded from current test totals. A pushed
workflow correction also excludes those historical files from future report
uploads; actual updated upload verification is pending. Disposable CI signing is
not publisher signing. Comparison acceptance does not qualify the production
shell, physical LAN or hardware GPUs.

## Fixes and parallel work

| Work | Done | What remains |
| --- | --- | --- |
| iOS linkage and test headers | Corrected archive extraction and native header search paths. Actual Simulator/device links, sole framework ownership, unit compilation and baseline XCTest pass | Closed for the tested packages; retain regression checks |
| Android picker and observations | Corrected absent picker-ID handling, padded process output and adaptive activity parsing; 98 integrated checker tests pass; real runs now reach the intended choice | New failures below remain |
| Android presentation selection | Original taps/focus transitions reviewed. Source shows selection can be rejected while the dialog owns focus, before renderer creation | Implement/review bounded pending selection consumed only after valid actual foreground/focus recovery; rerun both variants and modes |
| Android landscape checker | Original right-hand action pane is clipped while generic swipes target the equally sized left pane | Target the current ancestor pane, preserve visibility/clearance/deadlines, then rerun four API 36 consumers |
| iOS production layout and accessibility observation | Independently reviewed four-file correction integrated locally: content-hugging fixes, actual child/hidden-container measurement and UIKit regressions | Wire/run three UIKit cases, then both real production sessions. Raw child-local flag and other privacy/currentness/input guards remain |
| iOS native responsiveness | Prior originals prove delayed main-run-loop entry but do not identify the blocking stage. Fixed-size numeric stage timing reviewed and pushed | [Run 34488350932](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34488350932), `4f69429`: producers and all five Authority cases pass with original evidence verified. Retained background/resume and repeated entries pass; stale-callback re-entry fails, 2/3 passed. Diagnose the remaining failure; instrumentation alone is not a performance fix |
| Android Standard accessibility | Independently approved extension integrated locally: all five cards, checked state, fifth-card reachability, deselection, three-card limit, Hide privacy and real Standard Play after Godot return | Compose landscape fix, run integrated host/native checks; hardware TalkBack separate |
| iOS Standard accessibility | Separate test extension prepared for five-card semantics, a real legal Standard action after Godot return and unfiltered supported accessibility audits | Finish source review/uniqueness correction, compose production fix, execute XCTest |
| Android native gameplay evidence | Qualification-only bounded observation design approved; actual hook candidate frozen for security review | Review/compile/test hooks and checker, then actual native Reveal/card/Play with current geometry |
| Screenshots | 1,913 originals plus nine labeled supplemental video frames pushed at `0258150` | Publish newer Android comparison/production/adaptive and iOS production captures |

Agents use **gpt-6-astra with max reasoning**. Android, iOS, checker,
accessibility and rendering work proceeds concurrently with independent review.
Root owns shared builds, integration and Git. Security review remains source-only.

The current PCK remains **1,549,656 bytes / 136 entries**, SHA-256
`d6adbba1b5cbd6a1ac3a5754e4294363eae70ae9540af4ba12040cd4cfff44e0`.
The v7 native module adds numeric stage timings only. Reviewed CoreAudio dormancy
and main-loop access patches remain; the optional mouse patch remains unapplied.
No cover, lifecycle, input-currentness or timeout gate is relaxed for a pass.

## What still needs to be done to finish

1. **Complete implementation and automated native qualification.** Fix Android
   selection and iOS layout/responsiveness, complete production 2D/3D gameplay
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

- Source milestones pushed through `0258150`.
- [Screenshot gallery](screenshots/README.md): **1,913 original PNGs plus nine supplemental video frames**,
  with 6,661 evidence files and 8,579 checksum entries. Recent captures are being
  prepared with their actual run/failure context.
- [Verified Android 2D/3D preview download](../godot/comparison/README.md),
  [main instructions](../README.md), [validation commands](../scripts/README.md)
  and [iOS setup](../iosApp/README.md).
- [Release qualification](release-qualification.md),
  [CI research](research/engine-ci.md) and [Godot reviews](../godot/reviews/).
  New successes do not rewrite earlier failed results.
