# API 36 baseline runtime result

**Passed at `f11f92ed4ec4f91630396bf493ba2fd984f07bb9` in [Validate run 34457458638](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34457458638).** The independent retained-evidence audit passed all 23 checks.

The actual runner supplied four x86_64 CPUs, 15,989 MiB RAM and usable KVM. Android Emulator 37.1.11 ran the full default API 36 x86_64 revision 2 image with `swangle`, at 720 × 1600 / 280 dpi. The guest-reported API is 36. First-boot preparation passed with PartyDeck absent, without a reboot; the emulator reported boot completion in 36,473 ms.

Both debug and disposable-test-signed optimized APKs passed the existing smoke flows, with 86 recorded steps and 30 named stage captures each. They exercised rules, settings persistence, practice concealment/background/play, local hosting/share teardown, invalid-invitation recovery, real soft keyboards and 200% text. Both result receipts and wrapper exit codes agree. Neither receipt records diagnostic or settings-restoration errors.

The collected preparation and per-APK logs contain no matching `ANR in`, `am_anr`, `am_crash`, `FATAL EXCEPTION` or numbered fatal-signal markers. This is a result for the retained logs, not an exhaustive history or clean-driver-log claim. Generic seccomp-policy references to `crash_dump` remain ordinary retained warnings.

The downloaded `android-jvm-reports` ZIP matches GitHub's published SHA-256:

`b92ec1d1b6f546d8b9c4d1a5cf7b1f23f901306df820a84aef2c9795868e8bea`

The final receipt is `final-receipt.json`, SHA-256:

`90646e74f95150462306d51bafcff50dbbf389b70bf1776e7e07395aea19728a`

Original reports, job/run metadata, job log, screenshot identities and diagnostic scan are retained in this directory. The executed-input receipts report debug APK `017c91a09857886c1ed60030e35448b3f556ef5c4593732c62ae71f43486688a` and optimized APK `c515d8b0924d0a12e6e24ba4d6c1b8444b3ca6ba9deefc14d39c5723e11070be`; the optimized hash agrees with its disposable signing receipt. The separate 474 MB package artifact was not downloaded in this bounded audit.

This closes the previous **baseline API 36 runner/runtime gap at this checkpoint**. The earlier two-CPU preparation failures remain valid historical environment failures. This successful run used runner image `20260831.293.1`, the same image version recorded in the latest two-CPU failure. The larger allocation is proven; CPU count is not claimed as a uniquely isolated cause.

Native Godot session smoke was explicitly disabled, so API 36 native presentation gameplay and renderer lifecycle are outside this acceptance. Physical-device behavior, mixed-device LAN, camera frames and publisher/store signing remain separate. Root dispatched the run; this researcher only read sources and collected/audited evidence under `/tmp`.
