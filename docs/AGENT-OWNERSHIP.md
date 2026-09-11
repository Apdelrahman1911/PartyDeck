# Current agent ownership

**Resumed work, 2026-09-11 01:46 UTC.** The coordinator uses **30 delegated
agents, all gpt-6-astra with max reasoning**, plus the root coordinator. This
supersedes the original ten-implementation/five-reviewer allocation for the
current work batch. The original module boundaries remain documented in
[IMPLEMENTATION.md](IMPLEMENTATION.md).

This ledger records original assignments and confirmed follow-up work through
the timestamp above. Completion results are tracked in STATUS.

Root owns shared Gradle configuration, CI dispatch, Git integration and
publication. Activation candidates remain private until the applicable native
acceptance is supported. Collectors retain originals; reviewers independently
inspect their assigned evidence and write separate receipts. Previously
completed reviews keep their original attribution and are not reassigned.

For adaptive pixels, Debug/Optimized identifies the package, 1.0/2.0 identifies
font scale, and landscape/seascape/split identifies the recorded transition.
Coverage, visible findings and native qualification are separate claims.

| Agent | Owned work and boundary | Deliverable |
| --- | --- | --- |
| `activation_android` | Private Android Gradle activation and shipping-smoke candidates; root owns shared Gradle/CI edits. | Reviewed allowlist patch and shipping-profile checks; activation waits for native acceptance. |
| `activation_ios` | Private iOS Info.plist activation and shipping UI-smoke candidates. | Reviewed plist and smoke changes; shared shipping lists remain under root integration. |
| `adaptive_decode` | The sole decoder for the 32 adaptive Android recordings; independent resource-policy review after decoding. | Frozen frame inventory and integrity audit; preserve completed sets and interrupted attempts. |
| `android_collect` | Adaptive run 34540229407 artifact metadata, original ZIP collection and final collection binding. | Complete producer/consumer originals, receipts and collection freeze. |
| `android_package` | Actual adaptive APK/PCK/native-library/signature and producer/consumer package inspection. | Independent package report and final binding after producer collection. |
| `delivery_review` | README, build/download/comparison and iOS instructions against actual scripts and workflows. | Private Markdown corrections with verified paths and explicit shipping/qualification behavior. |
| `gallery_frames` | Later adaptive-frame and full-iOS image publication candidates. | Manifest, provenance and per-image viewing labels; reuse existing originals and recordings. |
| `gallery_review` | Independent authored-gallery and resumed-document review. | Verify counts, links, original bindings and claims; private approval receipt. |
| `ios_evidence` | Full and canceled iOS evidence preservation; sole collector for diagnostic 34550903117. | Frozen originals, exact test results and package/source bindings; no inferred native passes. |
| `ios_fix` | Initial Home-observation decoding investigation and any evidence-supported Swift correction. | Actual diagnostic explanation, bounded patch and focused validation; no speculative schema relaxation. |
| `ios_review` | Independent iOS outcome/provenance, diagnostic and activation-candidate review. | Source and executed-evidence findings that keep package, simulator and hardware claims distinct. |
| `measurement_publish` | JVM baseline documentation completed; now independent delivery-document and shipping-candidate reviews. | Preserve the verified eight-file report and raw CSVs; review new source/document candidates without repeating the workload. |
| `package_inclusion` | Additional full-Android content/fixture/DEX/R8 screen and the adaptive package delta. | Bounded inclusion report tied to actual package inventory and source. |
| `release_status` | Private STATUS, AGENT-OWNERSHIP, IMPLEMENTATION introduction and RESTART pointer candidates. | Concise current outcomes, unchanged scope accounting and exact 30-agent ownership; root integrates. |
| `resource_cleanup` | Approved duplicate gallery stages and three reproducible iOS engine checkouts. | Verified reclamation and preservation receipts; retain original evidence and maintained sources. |
| `resource_policy` | Private resource-cap, registration and admission-policy revisions. | Reviewed revisions preserving resource floors, common locking and existing frozen evidence; root activates. |
| `pixel_d1_land` | Debug 1.0: 3D landscape review completed; now the 12 full-iOS retry stills. | Per-image review receipts preserving the original Android scope and separate iOS evidence. |
| `pixel_d1_sea` | Debug 1.0: 3D seascape review completed; now independent authored review of the next gallery batch. | Preserve the frozen pixel receipt and independently verify new gallery counts, labels and links. |
| `pixel_d1_split` | Debug 1.0: 3D split entry and exit only. | Separate per-clip pixel receipts and remaining findings. |
| `pixel_d2_sea` | Debug 2.0: 3D seascape rotation only. | Frozen per-frame coverage and captured clipping/reachability limits. |
| `pixel_d2_split` | Debug 2.0: 3D split entry and exit only. | Separate per-clip pixel receipts and remaining findings. |
| `pixel_o2_saved` | Optimized 2.0: 2D split-entry/exit reviews completed; now independent joined-image identity review. | Preserve saved-view attribution and verify the combined source identities and review bindings. |
| `pixel_o2_land` | Optimized 2.0: 3D landscape rotation only. | Frozen per-frame coverage and captured clipping/reachability limits. |
| `pixel_o2_sea` | Optimized 2.0: 3D seascape rotation only. | Frozen per-frame coverage and bounded visual findings. |
| `pixel_o2_split` | Optimized 2.0: 3D split entry and exit only. | Separate per-clip pixel receipts and remaining findings. |
| `pixel_o1_land2` | Optimized 1.0: remaining 2D landscape views completed; now bounded font-2.0 clipping triage. | Joined review with prior coverage preserved, followed by a separate source/evidence finding. |
| `pixel_o1_2d` | Optimized 1.0: 2D seascape, split entry and split exit only. | Three per-clip coverage and visual-review receipts. |
| `pixel_o1_land3` | Optimized 1.0: 3D landscape rotation only. | Frozen per-frame coverage and bounded visual findings. |
| `pixel_o1_sea3` | Optimized 1.0: 3D seascape rotation only. | Frozen per-frame coverage and bounded visual findings. |
| `pixel_o1_split3` | Optimized 1.0: 3D split entry and exit only. | Separate per-clip pixel receipts and remaining findings. |

Current verified completion and open work are in [STATUS.md](STATUS.md). The
[paused-session checkpoint](RESTART.md) remains historical evidence.
