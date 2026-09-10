# Independent Godot environment review

Reviewed through 2026-09-10. Installation, isolated builds, bridge JVM tests,
real renderer import/export, matched desktop input, Android packaging, and
iOS engine-only compilation pass the checks below. After saving scene IDs and
ordering explicit export inputs, two independent ordered-v5 native exports
are byte-identical. The later reflection/lifetime replacement also passes its
source/content audit and matched desktop comparison. The separate release
review accepts ordered-v5 Android integration with all 19 notices. Refreshed
Compose Android/iOS baseline evidence and the corrected Rules capture are
qualified below; native Godot execution and KMP embedding remain incomplete.

## Independent checks and artifact inspection

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
| Refreshed Compose Android baseline | Independently inspected run `34428798269`: 118 actual passing tests, both executed APK hashes, 60 stage captures, 132 input records and four actual Rules/game/confirmed-leave/Home routes. A subsequent bounded audit of `34432935952` closes the remaining Rules capture clipping. |
| Refreshed Compose iOS baseline | Independently inspected run `34428798269`: 83 actual shared native cases, six passing XCTest cases, eight screenshots, both Swift/Java host directions, Simulator bundle and optimized unsigned ARM64 device bundle. This reviewer did not rerun the native suites. |

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

The subsequent v5 matched run, `matched-packed-v5-20260910`, also passes an
independent artifact audit. It ran at `02:01:32–02:02:03 UTC` using the v5
canonical PCK `0b3de6b276d15972708cfc7919d7f2f5bf2aefe8a05afb8859357e7139057d37`.
Its report hashes to
`30f7f87a212757dc1284a4ed9105212315d07a3226148240848ff1dde75191af` and records
commit `19501a23606c44ffd94eba3b24855a239e703a74`, a dirty working tree, and
source fingerprint
`642422de487b33a6dc2951d8a9a178c5a40737bf0e80bb6831fa197116cda515`.
Both presentations retain the same scenario counts and identical 42-row trace
digest above. All 22 new PNGs, individual receipts, CRCs, decoded dimensions,
and input rectangles were independently checked; the rectangles fit without
an epsilon. Both processes exited 0, logs retain only the VSync/root warnings,
and no renderer using this run's exact output argument remained. This run
records that exact PCK hash and normal text scale.

The final ordered-pack comparison, `matched-packed-ordered-20260910`, ran at
`02:38:21–02:38:52 UTC` and passes the same independent audit. Report SHA-256
is `5d138cf9535d1c7e63a94fe3bcb7bf7889119a5e16e5805b1cb4dfd6e1a3102b`;
the exact PCK is the reproducible `26bfbb72…ff890` artifact below. It records
commit `ce98579b5972b24c077df42d7af1ab278043e5b5`, a dirty tree and the same
renderer/comparison source fingerprint as raw v5. Every one of its 22 PNGs is
byte-identical to the corresponding raw-v5 capture. Both 42-row traces,
scenario counts, geometry, clean exit logs and absence of a renderer with the
exact output argument were independently verified again from the new evidence.
No duplicate gameplay execution was performed by this reviewer.

The replacement-pack comparison, `matched-packed-native-fixes-20260910`, ran
at `03:26:29–03:27:01 UTC` and also passes the independent artifact audit.
Report SHA-256 is
`1848d7484acb3ade7e352d56606452fe6b635830939b2ee6925be7ed20e9c7a4`;
it records commit `8d8d429186bfa3fc895b943101a24c7aeb992163`, a dirty tree,
and PCK `6599f825…55938`. The recorded renderer/comparison fingerprint
`fcdb2756623c46da345d3ffeaa081cff2e6555610c91788adeb6e47cf58b3928`
was independently recomputed from all 108 included files. All 22 PNGs and
individual receipts verify; their bytes equal the prior ordered-run images.
Both 42-row traces equal each other and the prior trace, all input rectangles
fit, both exits are 0, and both logs retain only VSync/root warnings. No renderer
with the run's output argument remained. This was an artifact inspection,
without another graphical run or a native-runtime acceptance claim.

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
the three canonical IDs in the source headers. The initial artifacts are
unchanged.

The v5 canonical export and one independent export both pass all four real
engine commands and the independent binary/receipt audit. They each contain
136 entries and 1,542,328 bytes. Their 132 source files and four tooling files
were independently hashed and preserved, with the identical fingerprint
`6f3f1bf69490f15df0ff547f8746282eaafd8bd4266ce08edc00bda393662ce7`.

| V5 artifact before export-order correction | SHA-256 |
| --- | --- |
| Canonical PCK | `0b3de6b276d15972708cfc7919d7f2f5bf2aefe8a05afb8859357e7139057d37` |
| Independent PCK | `74e179ac649ac5b57008293da6508ee875a7cfd4ac72f72bfaa335e5d92ba251` |

All 136 resource hashes now match, including the three generated scenes. Whole
PCK bytes still differ: nine unchanged `.txt` notice payloads have different
physical ordering and directory offsets. Header bytes and directory ordering
match. The exact upstream exporter reads include-filter files through unsorted
`DirAccessUnix::get_next`/`readdir`, writes payloads as it iterates the collected
paths, and sorts directory records only afterward. Byte reproducibility is not
claimed for this pair. Both raw packs, their logs/receipts and the frozen input files
are preserved separately from future promotions. An independent in-memory
reconstruction reproduces every byte of the second pack solely by relocating
the unchanged payloads and updating their offsets. All inter-file padding is
zero; no normalized pack was written.

The correction derives a staged preset containing 72 sorted explicit resource
paths and no wildcard inclusion/exclusion. It omits 60 source sidecar/config
inputs already handled by import/export while retaining every runtime resource
and notice. The actual engine still writes the pack. The source preset and
other option values are preserved, and the receipt records both preset hashes,
the selected paths and metadata omissions. `check-pack` recomputes that plan.
The reviewed `renderer.py` hashes to
`706b3a62e8d6ab7089a7be0ac79c2ec2e96d2fccbdc80bf08910d3605ed8fb59`.
Eleven independent host checks pass, including reversed source enumeration,
other-preset preservation, and missing/duplicate/malformed preset rejection.

One new independent export after that concrete correction is byte-for-byte
identical to the canonical export. Both contain 136 entries and 1,542,328 bytes,
with PCK SHA-256
`26bfbb72efa55b63bef2e0ab989c82356c75b3bb3ca40bcf1c5e70e931bff890` and exact
source/tool fingerprint
`b5d55f2a51f629191629a4f6f2fb5abcc44424a778a0e0435e34a4c668db3f79`.
All four real engine stages pass. Independent binary/MD5/SHA-256, receipt,
source/tool inventory, exclusion and notice checks pass for both. The logged
derived presets also match independently generated bytes. The real
`check-pack` CLI accepts this pack and rejects five separately altered receipt
plans. This establishes byte reproducibility for the recorded inputs, engine
and host, without upgrading the earlier failed pairs.

All 132 renderer source files remain unchanged from raw v5. Of its packed
entries, 135 remain byte-identical; only `.godot/uid_cache.bin` changes. An
independent reader using the exact upstream cache format confirms all 58
UID-to-path mappings are identical, with record order as the sole difference.
The separate Android `--xr-mode off` change does not alter the PCK inputs.

Both owner-executed graphical startup previews of this corrected PCK were
also independently audited. They retain actual Ready events, exit 0, matching
pack/source/launch hashes and clean Mesa llvmpipe/OpenGL 4.5 logs with only
VSync/root warnings. `headless=false` and `audio_driver=Dummy` are recorded.
These bounded previews establish graphical startup, not additional gameplay,
native lifecycle, or audible sound.

The subsequent preview-tool change was independently exercised using the
immutable initial source reconstruction and exact current tools copied to
scratch. Real source import, scene checking and an Xvfb/OpenGL preview with
`--audio-driver Dummy` all pass; Ready is observed and engine errors are absent.
The receipt records the actual audio mode, source fingerprint and source/PCK
choice. A real stale-pack preview then fails and removes the previous success
receipt before replacement logs can be mistaken for a successful run.
This checks fixture presentation startup, not authority gameplay or audible sound.

## Replacement PCK after native fixes

The later replacement PCK is 1,542,296 bytes with SHA-256
`6599f825a418f9d2a7049b3ba9325e8e0dcb474685262899079231b7ec955938`;
its raw receipt hashes to
`d6feb1a1b14ac526f1497d98a9e4a4209b02db39c92071b98dafcc2ec6308b13`.
Independent binary parsing verifies every directory entry, payload hash/MD5,
bounds and nonoverlap. All 136 paths remain identical to ordered v5. Only
`scripts/main.gdc` and `presentations/three_d/table.gdc` change; the other
134 payloads, including all notice/provenance entries, are unchanged.

All 132 source hashes and the four tool hashes were independently verified.
The corresponding two source files are the only changed export inputs, with
fingerprint
`a50c9521194011e7f83d30efe9df2d0f761ede952e6eebf4269ae21cab0fe94f`.
The engine identity and explicit 72-resource export plan remain unchanged;
the new native-bridge test source is excluded from the pack. All four owner
engine-command logs verify and contain no engine-error diagnostics. An actual
read-only `check-pack` invocation independently passes. The raw PCK/receipt,
logs, and all source/tool inputs are preserved in scratch evidence.

This audit inspects the owner's fresh export and its completed desktop run.
It does not claim a second export of the changed runtime scripts; the earlier
two-export byte-reproducibility result remains tied to `26bfbb72…ff890`.

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
source inventory to 19. The subsequent v5 package build completed in 48 seconds
with successful PCK staging, both APK assemblies, release bundle generation,
R8 and release lint. Its independently inspected release lint report retains
zero errors and the same eight warnings. The debug lint and four queue-test
reports remain the earlier executed evidence; this package command did not
rerun them.

The separate release reviewer verified all 19 notice files (537,959 bytes),
all eight native library hashes, signatures/alignment and bundle validation
in those v5 packages. Each contains the raw v5 PCK `0b3de6b2…57d37`, stored
uncompressed in both APKs. The release APK and AAB remain unsigned. That
raw-v5 evidence remains historical. The separate release reviewer subsequently
accepted the ordered-v5 integration in debug `c1b6d6bd…512fb`, unsigned release
`856bf2a4…6f483`, and AAB `51bc9cba…e3a13`. Its mounted PCK equals the independent
`26bfbb72…ff890` export; all 19 notices and eight native files remain intact,
and both APKs pass 16 KB alignment. Its differential limits package changes
to PCK, DEX, profile and R8 metadata. This environment review reuses that
completed package audit. The earlier 15 generated splits remain tied to their
older AAB; they are not a new split build for these packages. Dependency/ELF/
license interpretation remains in the separate release review. No Android
runtime success is inferred from packaging or JVM unit tests.

The new Android runtime checker also has independent source-only acceptance for
its first scheduled execution. Its native lifetime, request/sequence, real
authority round-trip, full-rectangle/density, HOME/Overview/resume, PID absence,
chooser survival and failure-preserving cleanup contracts were checked against
the actual host and pinned upstream source. Two independently reproduced gaps
were corrected: normal Godot error lines and a prematurely stopped log collector
could previously escape rejection. The checker now rejects both and retains a
bounded final owned-PID log dump before stopping its live reader, including the
upstream renderer-exit timeout check.

All 46 checker tests were independently executed after those changes. Six
additional direct log probes passed, including real child-process cleanup and
failure of the final log dump. Its PNG decoder also read actual retained Android
and Godot images. Reviewed `run.py` SHA-256 is
`ebc30f7887d60bee3ec16c92e477f2eb81a62d8c8081d6b0f7145abb78085031`;
`evidence.py` is
`fa6fdcc4c23597aa4a5f546cb88b3c1a26da023ca2e655eb8c280b551a27ecd9`.
These are host-only checks. Actual native execution and independent inspection
of the Recents thumbnail remain required; the checker does not claim a generic
pixel classifier proves thumbnail privacy.

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

The baseline's Rules evidence has a narrower limit. It checked Rules and Back
but never tapped the practice CTA. In both optimized captures the fallback
label is a clipped sliver, and its clickable parent extends below the
ScrollView bottom at y=1516 (to y=1565 normally and y=1546 at 200% text).
Recorded input containment therefore does not establish this unclicked action
was fully readable or usable. The bounded action/route follow-up is reviewed
separately; the original CI evidence is preserved without upgrading its Rules
coverage.

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

## Refreshed Compose Android baseline and Rules capture

The independent audit of
[run 34428798269](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34428798269),
Android job `102719639490`, verifies the exact checkout
`15ab6408d16c04941d133214b03d4e8c6c42ced9`. The executed checker hashes to
`77b16a74b220a7509f74e335bb663aba52d469d30c0078b5fbfeffb20718194e`.
All 118 actual XML cases pass without failures/errors/skips: Android QR 4,
shared app 48, core 14, games 7, session 27 and transport 18. This includes
`rulesPracticeOpensTheTablePreservesLiveRulesAndLeavesCleanly[jvm]`.

All four downloaded package hashes verify. The optimized disposable signature
verifies independently, and its nonsignature ZIP payload equals the unsigned
release APK. The actual debug APK is
`fb5ab7ffc54d5f01cd7a93761c03f10743f4b5d3e6f8019f0486fddee0079d0b`;
the executed optimized test-signed APK is
`a0adb50939b13eb83b21e37bd0d0604aba309e3d106d1f0c38dd0746a7115724`.
Both run on the same API 35, 720-by-1600, 280-dpi emulator boot. All 60 stage
PNGs/XML and 132 input records verify, with reported tap rectangles and swipe
points inside app viewports. Normal and 200% Join captures show the real soft
IME. Preparation and both variant logcat/event files contain no matched fatal
crash or ANR; all three last-ANR reports say none has occurred since boot.

All four Rules CTA/game/confirmed-leave/Home routes are independently verified
against the executed source, chronological job steps, inputs and game/Home
XML. Three of the original four CTA captures show the complete button. In
optimized normal text, the clickable parent is itself clamped to
`[42,1428][678,1516]`, so inclusive containment accepts it even though its
rounded bottom is visibly cut flat. Its reported 88-pixel height is below the
98-pixel minimum implied by the actual 56-dp button at this density. The
label is readable and the route succeeds; this historical capture is not
described as a complete button.

The later checker requires a gap of 8 display pixels inside the effective clip
edges. Its bounded executed follow-up,
[run 34432935952](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34432935952),
job `102732063048` at `8d8d429186bfa3fc895b943101a24c7aeb992163`, closes that
capture finding. The exact executed helper SHA-256 is
`7d6cef007b3d4fb64c6aaaf2e55c3039dc02853332607ccba4a239bc8cd1e5f3`.
All four new original PNGs were independently viewed and checked with their
XML, CRCs and decoded row lengths. All labels and rounded borders are complete;
every action ends at y=1453, with 63 pixels before the viewport bottom y=1516.
All four actual CTA/game/confirmed-leave/Home routes again match the source,
input records, chronological job steps and game/Home XML. The new helper also
rejects the unchanged old clamped-parent tree when replayed without adb.

The new executed APK hashes were independently checked: debug
`6d5d798aa3ebc4a63442c2766ecc4974d1b34b2301db7eceb0341cd4a151c8c0`
and optimized test-signed
`28b4322baa4548a5ac565f05bb7f6dd0de56980c493797b2abc422a7e1fa0f88`.
This bounded follow-up did not repeat the full package/signature audit or count
the unchanged test suites. The original run's clipping evidence is preserved;
the passing capture is attributed only to the new run.

## Refreshed Compose iOS baseline

Run `34428798269`, iOS job `102719639796`, completes successfully at
`03:07:55 UTC` on the same `15ab6408d16c04941d133214b03d4e8c6c42ced9`
checkout. Independent XML inspection counts 83 actual native cases in 13
suites, with no failures/errors/skips: shared app 25, core 14, games 7,
session 27 and transport 10. Actual native test tasks are present in the job
log. The new Rules controller regression executes on `iosSimulatorArm64`;
it verifies new practice entry, preservation of Rules during an existing
session update, and confirmed return to a clean Home state.

The shared-test and application selection receipts identify the same iPhone 17
Simulator `6762BD8F-E960-4E21-B8DB-9D43947B47AF`, SDK 26.4 and runtime
26.4.1/build `23E254a`. Actual Xcode is 26.4.1/build `17E202`. The application
log records six individual passing XCTest start/end pairs: three native TLS
tests and three UI tests, with both suites reporting zero failures and
`TEST SUCCEEDED`. The Java/Swift fixture and native test exchange 65,536- and
20,000-byte payloads in both host directions, record both terminal states as
`Closed`, and finish with Java and Xcode exits 0.

All eight original 1206-by-2622 screenshots were independently hashed and
checked for valid PNG CRCs, decoded rows, manifest/test identifiers and capture
times. Every image was viewed. Concealed hands show no private faces; the tests require
zero private-card accessibility elements and disabled Play after hiding.
The revealed selection and subsequent four-card hand match accepted play.
Hosting captures show the actual named host and closed invitation dialog,
without retaining its live QR or URI. The UI tests exercise Home-to-practice,
settings controls/Back, hosting/invitation and confirmed leave. They do not
execute the direct Rules CTA, preference persistence, physical LAN/camera,
share-sheet delivery or app-switcher privacy.

Both app archives were independently read and every member file hashed. The
Simulator archive is 27,711,430 bytes, SHA-256
`2012605361f9f6f81e5e86eb3ed45812f0c2f2391575a6cbed10fc5116ae9657`.
It contains ARM64 Simulator code and Apple XCTest support signature entries;
these are not publisher-signing evidence. The optimized unsigned device
archive is 15,624,845 bytes, SHA-256
`d77f59a8272803879a31ed6b56fb32db7d1ab4ae8deae940f7874e871e10b89f`.
Its 50,360,472-byte executable hashes to
`611a9d4669fd07e07ae6314fdd99ca719fbe02544534700fd3d9053eace38b75`.
Mach-O headers/load commands verify ARM64/iPhoneOS, SDK 26.4 and minimum 15.0;
the bundle identifier is `dev.partydeck.app`. It has no signature/provisioning
entries or Mach-O code-signature command. Actual
`:composeApp:linkReleaseFrameworkIosArm64`, Release/iphoneos build success,
`CODE_SIGNING_ALLOWED=NO`, and the ARM64 application link map are verified.
Minimum-OS metadata is not execution on iOS 15; this archive was not installed
on hardware or signed by a publisher.

The retained logs contain 25 Simulator build warnings and four device build
warnings. These include the Swift non-Sendable captures and `@preconcurrency`
suggestion, Simulator ICU object built for 18.5 versus the app's 15.0 minimum,
thread count, signed XCTest support stripping and absent AppIntents metadata.
Simulator network/debugger/measurement and duplicate accessibility-class
diagnostics are retained as well. All three TLS error records occur between
the start and passing end of the deliberate wrong-pin test. None is hidden
or converted into a broader hardware/runtime claim. The xcresult bundle is
retained; this Linux audit parses its Info.plist and exported attachments,
and uses the actual xcodebuild log for individual test outcomes.

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
Preview follow-up evidence is `preview-followup/inspection.json`; Android
checker source/test evidence is `android-checker-review/inspection.json`.
The v5 export comparison and ordering diagnosis are retained under
`final-fixed-v5/inspection.json` and `final-fixed-v5/archive-difference.json`;
`final-fixed-v5/archive-order-inspection.json` proves the complete difference
is payload relocation and directory offsets.
`preservation-and-input-audit.json` in that directory records independently
hashed copies of the raw canonical pack, receipt/logs and all frozen inputs.
The final v5 matched desktop audit is
`final-fixed-v5/matched-desktop-inspection.json`.
The coordinator's raw-v5 build/report audit is
`final-fixed-v5/android-build-inspection/inspection.json`; the separate package
review is `/tmp/partydeck-godot-release-review/final-v5/android/summary.json`.
Corrected final export evidence is under `final-ordered-v5/`: `inspection.json`,
`content-transition-inspection.json`, `receipt-plan-inspection.json`,
`packed-previews-inspection.json` and `matched-desktop-inspection.json`.
The eleven independent helper checks are in
`explicit-export-review/inspection.json`.
The baseline CI audit is separately retained at
`/tmp/partydeck-toolchain-review/baseline-34421746656-independent/inspection.json`.
The refreshed baseline audits are
`/tmp/partydeck-toolchain-review/baseline-34428798269-independent/inspection.json`
and `/tmp/partydeck-toolchain-review/ios-34428798269-independent/inspection.json`;
the iOS directory also retains exact reviewed sources, both archive inventories
and `diagnostics.json`. The bounded Rules recapture audit is
`/tmp/partydeck-toolchain-review/rules-34432935952-independent/inspection.json`.
Replacement PCK and desktop evidence are in
`reflection-lifetime-replacement/pack-inspection.json` and
`reflection-lifetime-replacement/matched-desktop-inspection.json`, with the
raw pack/receipt, four export logs, source/tool copies and comparison source
inventory. The separately accepted ordered-v5 package audit is
`/tmp/partydeck-godot-release-review/ordered-xr/android/summary.json` and its
adjacent `differential-review.json`.

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
- [Pinned include-filter directory traversal](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/export/editor_export_platform.cpp#L689)
- [Pinned Unix directory enumeration](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/unix/dir_access_unix.cpp#L148)
