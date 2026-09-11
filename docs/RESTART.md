# PartyDeck paused-session checkpoint

> **Resumed on 2026-09-11 at the user's request.** This checkpoint preserves the
> historical stopping state. Use [STATUS.md](STATUS.md) for current verified
> results and [AGENT-OWNERSHIP.md](AGENT-OWNERSHIP.md) for the 30-agent allocation.

## Historical pause instruction — superseded by the resume above

**Paused at the user's request on 2026-09-11, approximately 01:05 UTC.**
The instruction at that stopping point was:

> Do not resume agents, collectors, builds, decoders, or CI until the user asks to resume.

The [original checkpoint](https://github.com/Apdelrahman1911/PartyDeck/blob/085a07338b3f79c0fa6d167bf07ebe62dc6a99d1/docs/RESTART.md)
preserves its exact wording. The remaining sections record that historical state.

The working branch is `checkpoint/pause-20260911`. Its application source is based on
the already-pushed main commit `ac2200aed8d170e55009257a9ab5b48ef0b02081`.
The checkpoint preserves unfinished gallery publication and review work; it is not a
release or a claim of production readiness. The earlier `docs/STATUS.md` is stale;
use the verified state below when restarting.

## Safe stopping state

- All 15 agents stopped after preserving their progress. No automatic resume callback is scheduled.
- The local iOS collector (session 37496, process group 5216) stopped with exit 143.
  Its recorded lease was released. No owned collector or audit process remained.
- The sole Android video decoder (session 89189) had already stopped with exit 75.
  No decoder, recovery controller, SDK child, Gradle build, or Godot build remained running.
- Root checked that the Gradle and Godot lock files were available.
- GitHub diagnostic run **34547924733** was canceled by root. GitHub subsequently
  reported `status=completed`, `conclusion=cancelled`; native job 103104648986
  ended at **01:02:19 UTC**. Its upload step succeeded, but its reports/log have not
  been collected or interpreted. Do not count it as a completed qualification.
- The engine agent's earlier pause JSON says cancellation was unverified. The
  subsequent root observation above supersedes only that cancellation field.
- No evidence originals or interrupted decoder attempts were deleted.

## Instructions that persist

Read `AGENTS.md`, `plan.md`, `docs/IMPLEMENTATION.md`, and `godot/README.md`.
The user requires agents to use **gpt-6-astra with max reasoning**, independent work
in parallel, both real Godot 2D and 3D retained until they choose, and review images
pushed. Root owns shared build configuration, Git integration, and dispatches.
Research authoritative APIs rather than guessing. `review_security` is source-only:
send it source/diffs in messages; it must not execute code or tools.

Use `followup_task` to restart a completed agent after user authorization; merely
sending it a message does not start its turn. Do not redo completed reviews/tests
or duplicate artifact downloads and video decoding.

Gradle execution uses `ANDROID_HOME=/opt/android-sdk` and
`flock /tmp/partydeck-gradle.lock`. Godot uses `/tmp/partydeck-godot.lock`.
CI collectors/decoders share the resource gate and bulk lock described below.

## Verified progress

The original release milestone estimate remains **81%**. The additional Godot
acceptance scope remains **3 of 6 groups, 50%**. These scopes are separate and must
not be averaged. **The app is not yet production-ready.**

| Work | Verified outcome |
| --- | --- |
| Rules, host authority, hidden-information protocol, TLS transport, practice, app UI | Implemented; original baseline automated checks passed. Real-device release checks remain separate. |
| Both Godot presentations | Real 2D and 3D scenes and native hosts exist; canonical PCK remains unchanged. |
| Full Android, run 34538972728 / dd6df8a5 | Android succeeds: 264 JUnit tests, 259 Python checks, zero lint errors/11 warnings. Godot debug 30 passes; optimized 28 passes with two explicitly skipped renderer-death checks. Native Reveal/select/Play and Standard return pass in both modes. Actual package/PCK/signature/alignment audits are complete and sealed. The overall workflow failed on iOS. |
| Android adaptive, run 34540229407 / 4ee4563d | 96/96 adaptive scopes plus 4/4 installations pass; 16 held proofs accepted. Final producer package audit and transition pixel review remain incomplete. |
| Retained iOS, run 34540908385 / 65e4d86e | All 3 lifecycle/concealment/reentry cases pass; artifacts/source/package binding frozen. This is not a hardware performance result. |
| Full iOS retry, run 34545222517 / 3d73b343 | Shared 156/156, ordinary 9/9, UIKit 3/3, Simulator packages and unsigned device package pass. Both production Godot cases fail initial Home observation decoding. Originals and package/source audits are collected; final preservation audit/handoff/freeze remain unfinished. |
| Focused iOS, run 34544241421 / aa1d1df8 | Both production cases fail initial Home observation decoding; complete original collection frozen. No rejected JSON was retained, so the failing field remains unknown. |
| JVM TLS/measurements, run 34547302716 / 5341ffe8 | All three real TLS integration tests pass, including six-seat winner/rematch/same-controller rehost. Both measurement suites completed 2 warmups and 5 samples. Independent raw-data interpretation and accounting pass. |
| Diagnostic iOS, run 34547924733 / ac2200ae | Canceled at user pause. Collect its available log/report first after resuming; it may contain useful diagnostics, but no result has been assessed. |

The current pack is `godot/qualification/build/renderer/partydeck-last-light.pck`:
1,550,440 bytes / 136 entries, SHA-256
`541ded4c5074b56a9e320882a23f357ff8162520fac099e32567ac3a678f2751`.

Recent pushed main changes:

- `e2ffacbb`: run independent iOS suites even after unrelated ordinary/layout failures.
- `aa1d1df8`: native 3D passive-scroll assertions and required `canChallenge` observation.
- `3d73b343`: wait for the entered host name before its unchanged assertion; the full retry passes it.
- `5341ffe8`: six-seat TLS test, opt-in rule/network measurements, and hosted measurement workflow.
- `ac2200ae`: privacy-safe iOS decoder category/path/byte-count diagnostic only; no schema defect is claimed fixed.

## First tasks after explicit resume

1. Read this checkpoint, inspect Git state and available resources, and restore only
   missing private working files if necessary. Do not overwrite newer work.
2. Reclaim verified disposable staging copies if needed, then collect the canceled
   diagnostic's native log/report. Use any actual category/path/byte-count evidence
   to fix the initial iOS decode failure; keep required fields, privacy predicates,
   lifecycle guards, and timeouts strict. Independently review and rerun the focused
   production suite. Dispatch another run only if the retained canceled run is insufficient.
3. In parallel, finish Android producer package verification, the 12 remaining video
   decodes, four reviewers' remaining pixel work, and the package inclusion screen.
4. Finish the independent authored-gallery review and publish its completed batch.
   Publish the reviewed measurement candidate and remaining viewed-frame images.
5. Regenerate the detailed STATUS report from current results, finish native
   qualification and accepted shipping-mode integration, and perform appropriate
   final checks. Only then address the genuine external gates.

The shipping mode lists are still deliberately empty in Android Gradle configuration
and iOS Info.plist. Promoting accepted modes is pending native qualification.
Do not mistake qualification-profile APKs/apps for a publisher-signed release.

## Owners and exact restart locations

Paths below are under `/root/projects/PartyDeck` unless they begin with `/tmp`.

| Owner | Saved work and next action |
| --- | --- |
| engine_ci | `artifacts/evidence-storage/engine-ci-pause-checkpoint-20260911-v1.json` describes all stopped processes, frozen focused evidence, completed full-run collection and unfinished final audit. New diagnostic root: `artifacts/evidence-storage/34547924733`; collector config is frozen, but the collector must not restart automatically. |
| ios_platform | `/tmp/partydeck-ios-observation-decode-diagnostic-v1-I5O1Lf`. Diagnostic patch SHA `c940cf86ee1046451ca97ef3a0e4f4004ef95c92dc4fce8304ba5c5c354dd97e`; integrated Swift SHA `68cc85317757d2efc3b654f7906cf214cba8ce75f5394212843da1364b5af4fe`. Both independent source reviews pass. Needs actual decoder evidence. |
| game_domain | JVM collection frozen at `artifacts/evidence-storage/34547302716/FROZEN.json`. The ac2200a source derivation was inspected but **not created**: derive 852 files from `source-3d73b34` using 845 unchanged hardlinks plus seven local Git blobs. No source download/build is needed. |
| app_controller | `/tmp/partydeck-jvm-baseline-publication-app-controller-v1/COPYLIST.json`, SHA `1e4c0b67f4bf5a5c910108a65ddf3807018da7c4f3546db5fd80a2d15078dd92`: complete eight-file publication candidate, 477,360 bytes, not integrated. Raw interpretation is frozen in `/tmp/partydeck-jvm-measurement-review-app-controller-v1`. |
| android_platform | `artifacts/evidence-storage/34540229407/receipts/collection-checkpoint-v1.json`. Five ZIPs collected; producer artifact **10177161142** has not started. `audit-scripts/direct-hold-v1.py` and `finalize-collection-v2.py` are prepared, never executed. |
| network_transport | `artifacts/evidence-storage/android-adaptive-producer-34540229407-network-review-v1`. `direct-package-audit.py` SHA `05a11ed319cf159613bf4e39a3a2a560d0e6d9e0dd4a307267b04265c62c672b`; resource contract SHA `f77a58066ffde6c414b4fdfacceca057ee5543aca1f48b9a9c466bcd3c646077`. Direct SDK/package/PCK/JNI/alignment inspection, final producer/consumer bindings and freeze remain pending. No SDK child or full APK scratch copy started. |
| ui_game | `/tmp/partydeck-android-adaptive-decode-ui-game-34540229407-v1`. Exactly **20/32 recordings** decoded/frozen: all 16 2D and four 3D landscape. Both interrupted attempts (five and seven frames) are preserved and incomplete. `run-decoder-windows-v4.py` is prepared but never run; it skips completed sets. Final audit `/tmp/partydeck-adaptive-final-audit-ui-game-34540229407-v1.py` is unrun. |
| session_protocol | Debug 1.0 pixels: `/tmp/partydeck-adaptive-debug-pixel-review-session-protocol-34540229407-v1/PAUSED-v1.json`. Four 2D clips complete; 379/641 frames covered overall. Resume partial 3D landscape without reopening already reviewed frames. |
| review_game | Debug 2.0 pixels: `/tmp/partydeck-android-adaptive-debug2-pixels-review-game-v1/PAUSED-RESTART-CHECKPOINT-v1.json`. Five clips/413 frames covered; remaining three 3D clips/233 frames wholly unviewed. |
| ui_shell | Optimized 2.0 pixels: `/tmp/partydeck-adaptive-optimized-2.0-pixel-review-ui-shell-34540229407-v1/PAUSED-BY-USER-20260911-v1.json`. Two rotation reviews frozen; all split-entry frames covered, final receipt pending; 120 direct views saved. |
| review_design | Optimized 1.0 pixels: `/tmp/partydeck-adaptive-optimized-1.0-pixel-review-design-34540229407-v1/PAUSED-BY-USER-20260911-v1.json`. First clip has 41/51 distinct representatives saved; resume at 41. Gallery candidate below is unchanged. |
| assets | Independent payload review passed; **25 authored gallery files and baseline review remain unfinished**. Reconcile two historical manifest references against the preserved baseline. Verified staging-copy reclamation list exists; no aliases were applied. |
| review_environment | Full Android collection sealed. Additional package inclusion screen remains incomplete: preliminary expected resource comparison passed, but content/secret, DEX fixture, R8 and adaptive delta screens have not run. No new audit report/freeze exists. |
| review_release | `/tmp/partydeck-status-plan-update-6fda8a2-review-release-v3/PAUSED.json`. Private builder has newer JVM conclusions than its generated `STATUS.candidate.md`; collect/build/validate sequentially before integrating. Do not blindly apply the stale candidate. |
| review_security | Completed source-only approvals for the JVM changes and exact iOS diagnostic. Resume only for a new concrete source-review task after user authorization. |

## Gallery and backup

Main last published **3,677 original images + 246 supplements** in `6fda8a2d`.
This checkpoint branch also preserves the next batch: **4,586 originals + 330
supplements** in total. Root copied and hash/size/mtime-verified all 3,241 retained
payload files (203,371,493 bytes) and all 25 authored files (49,401,602 bytes).
They are saved work awaiting the remaining independent authored-file review.

Candidate: `/tmp/partydeck-gallery-after-3677-candidate-v1/candidate-files.json`,
SHA `5965f033d210ddb22bb6fef05d2f0dbc85a953d4f35bfcd457bf34870e5988e4`.
The 909 additions comprise 31 directly viewed originals, 18 reviewed byte matches
and 860 unviewed originals. The 84 added host-name video frames have five direct
views, seven attributed peer identities and 72 unviewed frames. Later adaptive
derivatives/reviews and new full/diagnostic iOS captures are outside this batch.

[Pending-work backup](checkpoints/20260911/pending-work.tar.gz) and its
[inventory](checkpoints/20260911/backup.json) preserve the in-progress decoder
outputs, reviewer notes, publication candidates and selected pause receipts.
The redundant gallery `stage` was excluded because its files are already in this
branch. Archive members retain their original `tmp/...` or `root/...` locations;
restore only missing work after checking hashes, not blindly over existing files.
The archive does not replace the historical CI evidence roots. Original artifacts
remain in the workspace or GitHub Actions; remote retention is normally 14 days.

## Resource constraints to resolve before restarting bulk work

At pause, overlay free space was about 1.1 GiB before checkpoint packing,
`/tmp` used about 6.9 GiB, and `/dev/shm` about 6.8 GiB. Recheck actual values.
The arena policy retains a 7 GiB cap, 3 GiB MemAvailable floor, 1 GiB destination
floor and common bulk lock. V8 is frozen in
`artifacts/evidence-storage/shm-evidence-arena-20260910` (configuration freeze SHA
`be066e0cc39fcd184de7f2a65be5c9fd9861c227e880e077938619f535a5393c`).
Older collectors intentionally retain their own frozen policy versions.

The direct Android audit needs at least 3,632,267,264 bytes MemAvailable;
the remaining producer ZIP initially needs 3,650,011,136 bytes. Also recheck arena
headroom: the final observed remaining cap was only about 280 MB, smaller than
the pending producer ZIP. Do not start work on memory headroom alone.

Root already reclaimed reproducible npm/Node/pip/Linux Kotlin Native downloads
and the installed Gradle/Android installer ZIPs. The Linux Native compiler would
need redownloading for future local Native work; the JVM work already ran on CI.

Prepared but **not applied**: `/tmp/partydeck-assets-stage-reclaim-candidates-v1.json`,
SHA `f2f835230dbb5d5d97965131d148151be69ddb1147a41a3eda131d577039be1f`.
It lists 5,373 already-published staging duplicates (537.25 MiB before alias overhead)
with matching bytes/modes/mtimes. Revalidate before replacing duplicate staging
copies with aliases; preserve the source originals and excluded metadata files.
Do not delete `/tmp/partydeck-engine-ci`: it contains original evidence.

## Remaining external release gates

Physical Android/iPhone and mixed-platform LAN sessions (2–6 players), actual
TalkBack/VoiceOver use, device privacy/process-loss behavior, hardware performance
and battery checks; publisher/support/privacy identities and public policy URL;
signing/store accounts and submissions; publisher assessment of Adobe DNG SDK
commercial terms. The Standard table remains the accessible route. Do not invent
a new full Godot accessibility-overlay requirement or a separate two-seat benchmark gate.

Suggested next-session instruction: **“Resume PartyDeck from docs/RESTART.md using
Astra max agents, and continue the unfinished work in parallel.”**
