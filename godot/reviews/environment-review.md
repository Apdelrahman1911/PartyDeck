# Independent Godot environment review

Reviewed through 2026-09-10. Installation, isolated builds, bridge JVM tests,
real renderer import/export, matched desktop input, initial Android packaging,
and iOS engine-only compilation pass the checks below. The first two exports
are not byte-reproducible: three generated scene node IDs differ. The identified
source correction awaits a fresh export comparison. Updated Android notices,
native Godot execution, and KMP embedding remain separate open gates.

## Independently executed checks

| Check | Result and evidence |
| --- | --- |
| Official Linux engine | Release `4.7.2-stable`, published `2026-08-18T15:56:46Z`, checked against the official release API and published checksums. The installed binary matches the verified archive member. |
| Actual CLI | `/opt/partydeck-godot/godot --version` returned `4.7.2.stable.official.ed1daf0bf`. `--help` and the versioned command-line documentation agree on import and pack semantics. |
| Repository installer | Executed `renderer.py install` from `/tmp` using the verified local ZIP and a separate scratch destination. The installed binary/version/receipt match the official pin. An invalid archive was rejected without creating an executable or success receipt. |
| Gradle configuration/output isolation | A scratch init script inspected the configured build directories of all six projects. `help` completed successfully in 19 seconds. Root outputs are under `godot/qualification/build`; `androidHost`, `bridge`, `comparison`, `core`, and `games` each use `build/modules/<name>`. |
| Actual bridge JVM tests | The unfiltered `:bridge:jvmTest` executed all 12 tests: six owner tests and six independent adversarial review tests, with zero failures, errors, or skips. Source/test hashes remained unchanged during the run. |
| Independent authority fixtures | `:bridge:generateFixtures` produced 15 documents plus a manifest in a separate scratch directory. Seed 2 exercised two viewer plays, two viewer challenges, and a winner in round 14. All manifest file hashes verify, and all 16 files are byte-for-byte identical to the owner's separate regeneration. |
| Desktop distribution | `:comparison:test :comparison:installDist` completed in 18 seconds. `test` was `NO-SOURCE`; the existing distribution was up-to-date. Its nine JARs/main class were inspected and the installed launcher executed `--help` successfully from `/tmp`. |
| Real renderer import/export | Independently ran all four real Godot stages: resource import, source scene instantiation, PCK export, and scene instantiation using only the PCK from an empty directory. All passed with exit 0 and no engine-error diagnostics. |
| Matched desktop artifacts | Independently verified both mode reports, all 22 PNGs and individual receipts, exact PCK provenance, matching 42-row authority traces, recorded exit 0, and clean engine logs. This is an audit of the owner's actual run, not a duplicate gameplay execution. |
| Official Android AAR | The actual `org.godotengine:godot:4.7.2.stable` AAR is 103,251,267 bytes and matches the SHA-256 in the published Gradle module metadata. |
| Initial Android packages | Inspected the coordinator's successful debug/release APK, release AAB and release lint build. Both APKs contain the verified PCK uncompressed; generated staging contains only that PCK. Four native queue unit tests pass. Debug and release lint each report zero errors and eight unsuppressed warnings. |
| iOS upstream pin | The official GitHub tag independently resolves to `ed1daf0bf001b61586d9930840f2f1394092c079`. The source audit was rerun against that checkout with clean tracked sources and passed. |
| iOS build dependency | The actual `scons-4.11.1-py3-none-any.whl` was downloaded and its 4,123,659 bytes independently hashed against PyPI metadata and `requirements.txt`. |
| iOS cache action | Official `actions/cache` tag `v6.1.0` resolves to the pinned commit `55cc8345863c7cc4c66a329aec7e433d2d1c52a9`; its action definition supports the configured path/key/restore-key inputs. |
| Actual iOS engine build | [Run 34415851126](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34415851126), repository commit `02364e5f3a4dd7742b43f8595269ff610acd2e4e`, completed `stage=engine` successfully. The downloaded native archive and symbol definitions were independently inspected. |

The exact Gradle command was:

```sh
flock -w 120 /tmp/partydeck-gradle.lock ./gradlew \
  -p godot/qualification --no-daemon --console=plain \
  --init-script /tmp/partydeck-godot-environment-review/output-layout.init.gradle help
```

The existing `core`/`games` warnings about disabled Android host tests were
reported without suppression. The later JVM run reports the same warning for
the new bridge. These checks do not qualify Android host tests or native tests.

The independent JVM suite and fixture generation completed in 16 seconds:

```sh
flock -w 120 /tmp/partydeck-gradle.lock ./gradlew \
  -p godot/qualification --no-daemon --console=plain \
  :bridge:jvmTest :bridge:generateFixtures \
  -Ppartydeck.fixtures.dir=/tmp/partydeck-godot-environment-review/bridge-fixtures
```

Both XML suites were copied to scratch evidence before another build could
replace them. `BridgeAdversarialReviewTest` and `LastLightBridgeTest` each contain
six executed test cases. Fixture generation uses the real Kotlin authority and
does not establish renderer behavior or multiplayer operation.

### Verified hashes

| Artifact | SHA-256 |
| --- | --- |
| Official Linux ZIP | `cadd3204e728a35d3f13adb7fd0d7902636b79f6b95c40c265eb73b6c35329e4` |
| Official `SHA512-SUMS.txt` | `b8bdff6704f833e7a021df16ec08e1478edd5a285c1f894929b91a7f74a5c7c0` |
| Installed Linux executable | `8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e` |
| Official Android AAR | `8791eecfe7c96a4de2d188a0bccfe9b83b92589a5a6825847473416a990e8629` |
| SCons wheel | `454cef364348053422696e3d2ecb4fa593c96a624f955842eaaea64f95c8d11d` |
| Built iOS Simulator archive | `aa97ac8ab7be8f1d0ea9947ee58bfc791e31ae64640b969ea55110a22910936e` |

The Linux ZIP also matches the published SHA-512:
`9aa00f7a605200940bce3027a567b782f49bd8e940dd06ae9e987bd65aee1b1467edd56ed84fcdcbdd44354bf613bdbb4e5d2913e925850368e150c59ed54c65`.

## Source/configuration review

The isolated settings import the shipping version catalog without changing it.
The extra Kotlin JVM plugin alias uses that catalog's existing Kotlin version.
Referenced domain projects have ordinary KMP outputs covered by the independently
verified build-directory redirection.

`StageGodotAssets` connects its generated asset directory to the Android variant
source API, invokes the pack verifier before staging, and synchronizes only the
canonical PCK. Its up-to-date shortcut is disabled so the verifier can check the
current renderer sources each time. The verifier now has a source review:
paths derive from the script location; inputs are copied to a temporary project;
source/tool fingerprints are rechecked before promotion; the PCK and receipt
must agree; and source/packed scene checks and license/provenance contents are
required. The completed initial Android build exercised this staging task and
recorded the same PCK digest found independently inside its outputs. Workflow
configuration itself remains separate from executed desktop or native evidence.

Five independent subprocess-wrapper checks also passed: normal completion,
zero-exit script-error diagnostics, ANSI-colored zero-exit error diagnostics,
nonzero exit, and timeout. Failure logs were retained and rejected; the timeout
was recorded as exit 124. These are deliberate host-level diagnostic fixtures,
separate from actual scene validation.

The pinned AAR declares Kotlin stdlib 2.1.21 and runtime Fragment 1.8.6 /
DocumentFile 1.1.0. These are published dependency declarations, not a claim
about the final resolved application graph. The Android host explicitly adds
Fragment to its compile dependencies because Godot's host API exposes those
types. Package/license/ELF findings belong to the separate release review.

For iOS, the exact upstream `SConstruct`, platform flags, `SCsub`, bootstrap
implementation, and controller header were independently inspected. They
support the probe's use of the ordinary Simulator ARM64 export-template static
archive and the declared `GDTViewController` override. Upstream rejects iOS
`library_type` modes and disables Metal/Vulkan for the Simulator; the probe
requests OpenGL Compatibility accordingly. The script verifies its exact
checkout and Xcode selection, uses hash-checked SCons, preserves compiler
failure through `pipefail`, and records runtime/KMP qualification as false.

The engine stage subsequently passed in CI using Xcode 26.4.1 (17E202), iOS
Simulator SDK 26.4, Apple clang 21.0.0, and SCons 4.11.1. The downloaded
`libpartydeck_godot_ios_probe.a` is 191,336,704 bytes and matches its receipt.
An independent archive parser inspected all 2,293 object headers as ARM64
Mach-O objects. It also read the actual symbol tables and Simulator build
commands in `main_ios` and `engine_surface_probe`: bootstrap/finish and the
probe controller class/metaclass are defined in sections, not merely referenced.
The build completed with 357 `ranlib`/`libtool` warnings about empty archive
members and no other compiler warnings or errors in the retained build log.

A static archive does not establish that a native application links or renders.
The original `nm` guard matched symbol substrings, including undefined
references. Its source now requires exact defined symbols; the independent
archive inspection already verified the required definitions for the retained
engine-only run. The new host/test stage requires five individually passed
XCTest cases and the linked host/runtime definitions before writing a native
success receipt. That stage has not yet supplied execution evidence here.

## Desktop execution evidence follow-up

The owner's first real 2D input run retained 21 bridge events, 42 authority
revisions, and 11 PNG captures. This reviewer independently matched all 11
capture hashes, individual receipts, and PNG dimensions of 430 by 932. Its
report records a dirty working tree and source fingerprint
`264752032a7425fcfa4995eb03e8a8abb807b337c9a744eda66989d0efd97935`;
only 2D ran, so it does not establish matching 2D/3D traces.

The retained `godot.log` ends with
`ERROR: Comparison loopback connection closed`, despite the report's success
status. The owner confirmed a cleanup race: the JVM closes the socket after the
quit reply while the probe still waits before marking itself closed. The
scenario/capture evidence remains useful, but clean-exit qualification is
withheld for this iteration. The first report and images remain preserved.

The corrected matched packed run completed at `2026-09-10T00:48:15Z`, after
starting at `00:47:44Z`. Its report is
`qualification/build/comparison/matched-packed-20260910/report.json`, SHA-256
`e668179d24ce75b0fd472715abdf405be726764f69d6152485aff43c1adf8d46`.
The report records commit `e1ee4fb7d498449035181515dd7f40899b2b6c2f`, a dirty
working tree, and source fingerprint
`26426170ab4341d7ff72b3b387b3f70f5938376d0285f216d102fb27689f9637`.

Both modes used the initial canonical PCK below, seed 2, reduced motion, and a
430-by-932 viewport. Each retained 21 bridge events, 21 input records, two
viewer plays, two viewer challenges, 13 round advances, 129 probe requests,
and 11 captures. The two actual 42-row traces are equal, including every view
digest, and independently hash to
`79b5b2a6415a365d531da3488b7b87f1b2309f2b1208899ee5b4618da16be674`.
All PNG hashes, dimensions, chunk CRCs and decoded row lengths match their
individual receipts and report entries. The recorded touch rectangles and
centers fit their recorded clip viewports.

The probe now drains its quit reply within a bounded shutdown state; the JVM
keeps the socket open until process exit, requires exit 0, and rejects engine
error diagnostics before writing success. Both retained logs contain only the
Xvfb VSync and superuser warnings, with OpenGL 4.5/Mesa llvmpipe. No renderer
with this run's output argument remained during independent process inspection.
This proves the retained desktop comparison scope; it does not establish native
device performance, sound, accessibility, or multiplayer behavior.

## Renderer import/export and reproducibility

The initial canonical PCK is preserved under
`qualification/build/renderer/milestone-6457270/partydeck-last-light.pck`.
An independent second export ran from `/tmp` and used a separate temporary
project and output. Both artifacts contain 136 entries and are 1,532,712 bytes.
Their exact source/tool inventories are identical, with fingerprint
`1615fd93aaf5055baca9ea76a6abdf30bc3cbe01409cff27a38a15226c546594`.

| Initial artifact | SHA-256 |
| --- | --- |
| Canonical milestone PCK | `2c840bb8a20177aaed657cf5ae6f0bcee74964bc591d269ed741cd9e58365e35` |
| Independent second PCK | `01cb813a1a3136b753c0b5a92fa3b05c9d3dbf590b652166c0a16fcab7389361` |

An independent binary reader verified directory bounds, offsets, flags, entry
MD5 checksums and receipt SHA-256 values for both packs. All 11 license/provenance
inputs are retained unchanged. Tests, checks, fixtures, development proofs and
source artwork are excluded. All three source and PCK-only scene checks pass.
The original verifier also independently rejects a corrupt PCK entry and stale
renderer input, while accepting an exact scratch reconstruction of the original
source/tool inventory. These checks preserve the initial snapshot despite
subsequent renderer work.

Byte reproducibility fails for this initial snapshot. Exactly four bytes differ
in each of three generated `.scn` files; the other 133 entries are identical.
Actual Godot reads of `PackedScene._bundled.node_ids` match those uint32 fields:
main `2052510987` versus `73853442`, 2D `1922329495` versus `699304503`, and
3D `1409826314` versus `1744682930`. Exact upstream source shows that scene
repacking generates a crypto-random ID when a saved node has no `unique_id`.
Each source scene originally lacked that root-node field. The owners persisted
the three canonical IDs in the source headers; a fresh independent export
comparison will verify the correction. The initial artifacts are unchanged.

## Initial Android packaging

The coordinator's real package build completed in 34 seconds. Its retained log
records debug and release APK assembly, release bundle generation, R8/resource
shrinking, release lint, and successful PCK staging. Independent ZIP inspection
found the exact initial PCK in all three artifacts. Both APK PCK entries use
ZIP method 0; the AAB stores its asset with deflate, which is not an installed
APK compression claim. All generated and packaged outputs remain inside the
isolated qualification build.

| Initial Android artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Debug APK | 314,327,223 | `3cb4352778854da8e782b25fb8960498816973a4a322a22b2e9e61dbae96b42b` |
| Unsigned release APK | 311,412,493 | `209167831ff681bbde07814a6890e4e94097af58dcbd45acaa287303b0c7dc41` |
| Unsigned release AAB | 104,783,958 | `04b7ce58606aaf29a422b7a1775893bc823b854c1cf016f26e723ef9d4fc9c16` |

`apksigner` independently accepts the debug APK and rejects the unsigned release
APK as expected. The inspected queue-test XML has four actual passing cases,
with no failures, errors or skips. Both lint reports contain zero errors and
eight warnings: target API age, the pinned Fragment version, portrait/resizing
constraints, their Android 16 compatibility implications, and two isolated
dependency declarations outside the shipping catalog. They are not suppressed.

These initial packages contain ten native notice files, each matching its
source. Nine additional runtime notices were added afterward, bringing the
source inventory to 19. Their inclusion awaits the coordinator's planned
repackage with the updated renderer. Dependency/ELF/license interpretation
remains in the separate release review. No Android runtime success is inferred
from packaging or JVM unit tests.

## Existing Android baseline follow-up

The separately assigned review of baseline CI run
[34421746656](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34421746656)
accepts its single API 35 emulator gate. The exact executed script at commit
`d3418f150e908667560767e4b825f8968b337df3` hashes to the previously independently
reviewed viewport-containment correction. All 117 XML test cases pass without
failures/errors/skips. The four downloaded package hashes match their receipts;
the optimized test signature verifies, and its nonsignature ZIP payload is
identical to the unsigned release APK.

Both APK flows passed on the same 720-by-1600, 280-dpi emulator boot. All 52
stage PNGs/CRCs/XML files and all 115 input-geometry records were independently
checked. Every recorded tap rectangle and swipe endpoint fits its app-owned
viewport. The normal and 200% Join submit targets now fit wholly inside the
scroll viewport. Both real soft-IME captures identify the correctly focused
app field and visible input method.

The cumulative logs retain one Launcher3 ANR at `00:45:38–00:45:39 UTC`, with
Android's disposition `expired, only dump ANR app`. It already appears in the
empty-AVD preparation evidence, whose installed-app query is empty. Launcher
readiness succeeds at `00:45:54.565` and again at `00:46:06.058`; the first
named PartyDeck package-added record is `00:46:06.321`, followed by its first
process at `00:46:06.540`. Both runtime buffers contain the same historical
event and no new ANR or fatal crash. No reboot or crash-dialog dismissal was
used. This is accepted as a retained pre-install infrastructure event; it is
not described as an entirely ANR-free emulator boot. Physical LAN, physical
camera frames, publisher signing and the separate Godot host remain open.

## Export and execution boundaries

No export templates are installed in the verified local toolchain. Godot's
`--export-pack` exports data only and implies resource import; a successful PCK
export would not establish standalone/mobile export or launch. In the exact
upstream `EditorNode`, the pack-only branch calls `export_pack` before the
normal export/template checks. The local PCK reader's format version, flags,
offsets, directory entries and MD5 fields were checked against the pinned
engine reader/writer. SHA-256 provides the separate artifact digest.
`--headless` selects the headless display and Dummy audio drivers.
`--quit-after` counts iterations, so execution deadlines use a process timeout.

No redundant local emulator or full desktop scenario run was performed. The
independent import/export uses scratch outputs, and Android/desktop runtime
conclusions above come from inspecting their owners' completed artifacts.
Upcoming renderer revisions require their own fresh PCK and execution evidence.

## Evidence and authoritative sources

Scratch evidence is under `/tmp/partydeck-godot-environment-review/`:
`toolchain-verification.json`, `godot-version.log`, `godot-help.log`,
`gradle-output-layout.json`, `ios-upstream-audit.json`,
`ios-upstream-tag-verification.json`, `ios-scons-verification.json`, and
`ios-engine-34415851126-verification.json`. The last receipt was generated by
`audit-ios-archive.py` against the shared download under
`/tmp/partydeck-engine-ci/34415851126/godot-ios-probe-engine/`.
The repository installer receipt is under `tooling-install/`; source hashes are
in `reviewed-tooling.json` and `reviewed-scaffolding.json`.
Bridge evidence is in `bridge-build-verification.json`, `bridge-test-results/`,
`bridge-fixtures/`, and `bridge-jvm-tests-and-fixtures.log`. Subprocess guard
evidence is in `command-guards/review-results.json`.
Desktop build evidence is in `comparison-build-verification.json` and
`comparison-installed-help.log`; the first 2D artifact inspection is in
`first-real-2d-input-inspection.json`.
Import/export evidence is in `renderer-export/`, `renderer-pack-verification.json`,
`renderer-pack-reproducibility-difference.json`, and
`packed-node-id-inspection/inspection.json`. The completed matched desktop
artifact audit is `matched-packed-desktop-inspection.json`; initial Android
packages, lint, tests and signing evidence are in
`android-initial-package-inspection/inspection.json` and adjacent logs/XML.
The baseline CI audit is separately retained at
`/tmp/partydeck-toolchain-review/baseline-34421746656-independent/inspection.json`.

- [Official engine release](https://github.com/godotengine/godot-builds/releases/tag/4.7.2-stable)
- [Versioned command-line reference](https://docs.godotengine.org/en/4.7/tutorials/editor/command_line_tutorial.html)
- [Exact Android module metadata](https://repo.maven.apache.org/maven2/org/godotengine/godot/4.7.2.stable/godot-4.7.2.stable.module)
- [Exact Android POM](https://repo.maven.apache.org/maven2/org/godotengine/godot/4.7.2.stable/godot-4.7.2.stable.pom)
- [Pinned upstream iOS source](https://github.com/godotengine/godot/tree/ed1daf0bf001b61586d9930840f2f1394092c079/platform/ios)
- [Pinned upstream controller declaration](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/apple_embedded/godot_view_controller.h)
- [SCons wheel metadata](https://pypi.org/pypi/scons/4.11.1/json)
- [Pinned cache action](https://github.com/actions/cache/blob/55cc8345863c7cc4c66a329aec7e433d2d1c52a9/action.yml)
- [Pinned pack-only export branch](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.cpp#L1377)
- [Pinned PCK reader](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/io/file_access_pack.cpp)
- [Pinned PCK writer](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/export/editor_export_platform.cpp#L2177)
- [Pinned scene-node ID generation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/resources/packed_scene.cpp#L1099)
- [Pinned random resource-ID generator](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/io/resource_uid.cpp#L113)
