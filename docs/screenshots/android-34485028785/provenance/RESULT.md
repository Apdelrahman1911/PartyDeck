Run **34485028785 failed** at exact commit `fc431ee775990943dfe152f4f20fb9365db4e72d`. The corrected picker checker located the production Table style dialog and tapped the enabled 2D text target in both variants. Each then timed out waiting 45 seconds for `SessionGodotActivity`; the final diagnostic showed the concealed Compose table and the original shell process. This run does not qualify native session entry or lifecycle.

Run: https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34485028785

| Current-run evidence | Debug | Optimized test-signed |
|---|---|---|
| Ordinary app smoke | Passed: 88 steps, 30 named PNG/XML pairs | Passed: 86 steps, 30 named PNG/XML pairs |
| Installation and Compose practice baseline | Passed | Passed |
| Recorded 2D picker input | `(248, 931)`; fresh UI sequence 23 | `(248, 931)`; fresh UI sequence 24 |
| First failed check | `2d.native-entry`, 14:06:27.317 UTC | `2d.native-entry`, 14:15:30.738 UTC |
| Retained shell PID / UID / task | 7548 / 10148 / 11 | 14310 / 10149 / 15 |
| Numeric process-table samples | 136 successful, shell only | 136 successful, shell only |
| Original session PNG/XML pairs | 6 | 6 |
| Renderer-death scope | Requested, not reached | Explicit invocation omission; phase not reached |

The original selector XML has enabled, clickable, unchecked 2D/3D rows with empty resource IDs. Both recorded taps use the current 2D TextView bounds `[193, 911, 304, 952]`, centered inside its row with at least eight pixels of clearance. The tap uses a fresh dump after the retained selector capture. The command logs record `Tapped presentation-choice-godot_2d` before the activity wait fails. Both original selector and final PNGs were visually inspected: the dialog disappears, the final hand is concealed, and Select cards is disabled. No native surface is visible.

All 272 original process commands use `adb -s emulator-5554 shell ps -A -n -w -o PID,UID,NAME`; their numeric schema, raw stdout/stderr, exit status, hashes and capture attribution were independently checked. Each retained capture boundary has the same MainActivity task and shell identity. Retained logcat/events contain no `SessionGodot`, `GodotSession`, or exact renderer-process mention; both crash logs are empty. The diagnostic marker scan found no ANR/fatal marker in 674 retained logs. These are bounded observations of the retained samples and logs.

No 2D native Ready, 3D selection, native Home/Recents interruption, Standard return, Leave cancel/end, renderer death, native gameplay, or native pixel-privacy check ran. Both intentional-signal lists are empty. Public round/rank/turn still matches each Compose baseline in the final diagnostic, but no native round trip or final private-card comparison occurred.

Fresh test results are **228 JUnit cases in 39 canonical suites**, all inside this build step, with zero failures/errors/skips; the separately retained checker step has **98 tests, all OK**. Lint has **11 warnings, zero errors/fatal issues**. The recursive artifact upload also contains **76 historical documentation suites / 446 case occurrences**, which are preserved and explicitly excluded. Both ordinary smokes report a one-card hand decrease. Those ordinary Compose results are separate from the failed native-session attempts.

All four uploaded packages—debug APK, unsigned release APK, optimized test-signed APK and unsigned release AAB—contain literal activation values **qualification / 2d,3d** and the expected PCK `d6adbba1b5cbd6a1ac3a5754e4294363eae70ae9540af4ba12040cd4cfff44e0` (**1,549,656 bytes, 136 entries**). The 132 current renderer input files and four tools match the accepted comparison export fingerprint `125a5e807b1fff2132e837d173ce5df59fad4f08dc1a26204d73f1e64fddcac4`. That earlier receipt is used only for source/pack provenance. Every PCK entry checksum/hash was checked. Optimized signing preserves all **550** unsigned payload entries and adds three signature entries; its signing certificate matches the disposable CI-key receipt and its manifest is not debuggable. Source default shipping modes remain empty.

The retained package-manager logs independently match package `dev.partydeck.app`, the sampled UID, installed base path, version **1 / 1.0.0**, minimum SDK **26**, target SDK **36**, and each APK's debuggable flag. Device logs corroborate guest API **35**. The checker-recorded installed SHA-256/size matches each uploaded input APK. **Pulled `identity/installed-base.apk` bytes were excluded by workflow upload patterns**, and the retained pull stdout is empty, so those pulled bytes cannot be independently hashed. Their recorded identities remain preserved as declared missing artifacts.

The exact source suggests an earlier selection gate to investigate: the dialog row sets `expanded=false` and synchronously calls `onSelect`; `EmbeddedPresentationCoordinator.select` rejects `!state.isForeground`, fed by MainActivity focus. The ViewModel launch path has a further focused-shell gate. This modal-focus timing explanation is a source-grounded lead, **not executed branch telemetry or an accepted fix**.

Both original artifact ZIPs match GitHub's published SHA-256 and byte sizes. All **1,457 extracted artifact files** and **7,986 exact-commit source files** were independently rechecked against the retained archives. The full run-log ZIP has 21 entries; its job log exactly matches the separately downloaded job log. Collection completed without API/download errors. Three intentionally skipped iOS jobs were recorded as skipped, with no missing-log claim.

Use `runtime-evidence-audit-v2.json` as the authoritative runtime audit. Derived v1 remains preserved with a correction receipt for a predecessor-specific play-outcome sentence; current results say both hands decreased by one. The initial installed-identity parser's field-name mismatch is also preserved and corrected against the actual aapt2 output. Original CI evidence was not changed.

PNG/XML acquisitions are sequential, not atomic. No end-of-run guest boot ID is retained for an independent comparison with the initial ID. This collection supplies no physical-device, store-signing, LAN, accessibility, or performance qualification. Reviewer actions were limited to read-only collection, archive/package decoding, source inspection and evidence hashing; no build, test-suite rerun, native retry, Git operation, shared-source edit, or workflow dispatch was performed.
