# Godot release and artifact review

Independent review by `review_release`, 2026-09-09; updated 2026-09-10. Both Last Light presentations are reviewed as renderers of the same authority bridge. Neither renderer is selected for shipping by this review.

**Status:** engine/AAR provenance, shared assets, resolved runtime notices, the deterministic PCK, and the exact CI 34433457249 Android artifacts below pass independent static inspection. The CI replacement PCK equals the local export byte for byte. All 19 notices survive exactly in both APKs and the unsigned AAB; direct APK alignment passes. The refreshed AAB's native payloads and output policy equal those used in the earlier successful 15-split audit. **The full native suite in that CI run failed.** Static package acceptance and existing Compose/KMP qualification do not qualify the Godot host's native runtime.

## Verified inputs

| Input | Independently verified result |
| --- | --- |
| Installed Linux executable | `4.7.2.stable.official.ed1daf0bf`; full source commit `ed1daf0bf001b61586d9930840f2f1394092c079`. The installed executable equals the ZIP member. |
| Official Linux ZIP | 77,860,424 bytes; SHA-256 `cadd3204e728a35d3f13adb7fd0d7902636b79f6b95c40c265eb73b6c35329e4`. Matched the official release API digest and published SHA-512 list; the list itself matched its release digest. |
| Installed executable bytes | 146,414,384 bytes; SHA-256 `8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e`. |
| Android runtime | `org.godotengine:godot:4.7.2.stable`, 103,251,267-byte AAR; SHA-256 `8791eecfe7c96a4de2d188a0bccfe9b83b92589a5a6825847473416a990e8629`. Maven bytes match the official GitHub `godot-lib.4.7.2.stable.template_release.aar` digest, Maven checksum, and both Gradle module variants' size/SHA-256/SHA-512 records. |
| Android source JAR | SHA-256 `aa9b8361b2ce9e60512cb02281171c25f2553ee45481065f09cac3e780508cc2`; matches the exact module metadata. This is the Android wrapper source, not the entire native engine source. |
| Shared asset manifest | SHA-256 `37480b580dd95d88e39605f40f6062fb30a96a6fe529b25eb1a593ef77d2280e`; all 54 mapped files, 114 recorded source references, and 47 import sidecars match their recorded bytes and hashes. |

The official release was published on 2026-08-18 and is neither draft nor prerelease. The export-template archive is not installed; no template or mobile export execution is inferred from its published metadata.

Evidence is under `/tmp/partydeck-godot-release-review/`: `cli-binary-review.json`, `cli-archive-provenance.json`, `aar-provenance-review.json`, `maven/download-record.json`, and `asset-source-review-final.json`. Downloaded official release/tag responses and pinned sources are retained under `upstream/`.

## Licenses and source availability

The core renderer notice files now match the exact `4.7.2-stable` upstream bytes:

| Renderer file | Bytes | SHA-256 |
| --- | ---: | --- |
| `licenses/GODOT_LICENSE.txt` | 1,149 | `b0435e3b3e4e55238f05f4b306f30524a1b2e20147810d436eaa554fa6855c80` |
| `licenses/GODOT_COPYRIGHT.txt` | 100,108 | `cb1980c88089573bcacd7221d777c689bb8bbd778799f24c27fca0fe5f774d6d` |

Godot's official licensing guidance requires making the MIT text available to recipients and recommends distributing its third-party `COPYRIGHT.txt`. That file explicitly summarizes main third-party licenses without enumerating every file/snippet exception. It must not be described as an exhaustive audit of every native dependency.

An isolated headless query of the installed engine executed successfully: `Engine.get_license_text()` equals the pinned MIT text; `get_license_info()` and `get_copyright_info()` return 19 license definitions and 102 components. This is a compiled source-component catalog, not proof that every listed component is retained in an Android binary. Evidence: `cli-license-query-review.json` and `cli-compiled-license-catalog.json`.

Two Android native items were identified and are now covered in the canonical notice directory. Their exact notice/source bytes are present in both independently mounted PCKs and the rebuilt v5 Android artifacts:

1. **MPL certificate source is actually retained.** The same 130,566-byte zlib stream exists in all four `libgodot_android.so` files. Decompression yields the exact 225,076-byte pinned `thirdparty/certs/ca-bundle.crt`, SHA-256 `33a22c7286f7752131636a11fb9feb3fb12ecd02f1a9b3e54e5901349d37362e`. Godot's notice includes Mozilla attribution and MPL-2.0. The new `GODOT_CA_BUNDLE_SOURCE.txt` is an exact offline source copy; `GODOT_CA_CERTIFICATES_SOURCE.txt` identifies it and links to the [unchanged source at the full pinned commit](https://raw.githubusercontent.com/godotengine/godot/ed1daf0bf001b61586d9930840f2f1394092c079/thirdparty/certs/ca-bundle.crt), addressing source availability under MPL section 3.2. Evidence: `aar-certificate-deflate-review.json` and `renderer-notice-review.json`. This establishes retention, not a runtime network operation by PartyDeck.
2. **The C++ runtime has verified NDK provenance and separate notice coverage.** Each ABI includes `libc++_shared.so`; neither the AAR nor its `classes.jar` contains standalone license/notice files, and Godot's `COPYRIGHT.txt` has no LLVM/libc++ section. All four runtimes match NDK r29's prebuilt build IDs and every ELF LOAD byte except section-table header fields changed by stripping. The official NDK r29 Linux ZIP's 783,549,481-byte size and SHA-1 `87e2bb7e9be5d6a1c6cdf5ec40dd4e0c6d07c30b` match Google's SDK repository metadata; its independently computed SHA-256 is `4abbbcdc842f3d4879206e9695d52709603e52dd68d3c1fff04b3b5e7a308ecf`. The new `ANDROID_NDK_LLVM_NOTICE.txt` equals its complete 130,424-byte `toolchains/llvm/prebuilt/linux-x86_64/NOTICE`, SHA-256 `f96f763beb66a7ba7a667647fc64c0226ace875e590c831fdd9579ec1c1d91e1`, including LLVM Apache-2.0 exceptions and libc++/libc++abi notices. Evidence: `aar-libcxx-ndk-comparison.json`, `renderer-notice-review.json`, and `upstream/android-ndk/ndk-r29-package-review.json`.

The C++ runtime retains an ELF note saying NDK `r28` build `13004108`; it is nevertheless the prebuilt runtime shipped in the verified NDK r29 distribution. Godot's DSO records `r29` build `14206865`. The embedded note alone must not be used to assign a different distribution or infer incompatibility.

The seven canonical files in `renderer/licenses/` include these four exact upstream files, the source-availability note, `README.txt`, and `NOTICE_PROVENANCE.json`. The latter records accurate artifact sizes/hashes, all four C++ build IDs, original filenames and source commits. Both new full-commit source URLs were independently fetched and matched the canonical bytes (`recipient-source-url-review.json`). The final source-availability note is 1,241 bytes, SHA-256 `c68edd43fa15b39be0aa724eaf28cdfa9df22a83eb74f66614b93993bdcde1f7`. Android's native notice index is implemented and reads each document separately. Its exact packaged document set is verified below; an executed screen and native accessibility remain unverified by this review.

The shared assets contain four original audited font binaries, 24 original PartyDeck vectors, eight derived rank textures, five wordless card textures, four editable card source files, six exact original WAVE cues, and three font license/credit files. Fraunces and Manrope retain their complete SIL OFL 1.1 texts and copyright credits. No new external art, model, or audio provenance obligation was found in the recorded asset set. Original PartyDeck provenance is not a public-domain or CC0 assertion.

All three `assets/licenses/*.txt` files must survive export. The asset owner's executed import evidence is in `assets/proofs/import_verification.json`; this review independently checked source and sidecar bytes, and does not relabel the owner's import run as an independently executed device or audible-playback test.

## Actual AAR contents

The archive contains four ABIs, each with the Godot engine and C++ runtime:

| ABI | `libgodot_android.so` bytes | `libc++_shared.so` bytes | ELF LOAD alignment |
| --- | ---: | ---: | --- |
| `arm64-v8a` | 71,114,944 | 1,374,336 | 16,384 bytes; every LOAD offset/address is congruent at 16 KB |
| `x86_64` | 74,061,272 | 1,337,488 | 16,384 bytes; every LOAD offset/address is congruent at 16 KB |
| `armeabi-v7a` | 74,938,344 | 963,028 | 4,096 bytes |
| `x86` | 84,312,052 | 1,255,932 | 4,096 bytes |

Individual SHA-256 values, build IDs, LOAD segments and native dependencies are recorded in `aar-native-review.json`; `elf/` retains the `readelf` output. The 64-bit ELF inspection passes. It does not establish final APK ZIP alignment, bundle-generated split alignment, or execution on a 16 KB device.

The AAR manifest declares minimum SDK 24 and library version `4.7.2.stable`, with no permissions or hardware features. It contributes a nonexported `ProcessPhoenix` activity and a nonexported AndroidX `FileProvider` with URI grants enabled. Provider paths cover app files, external storage, and external app files. The preliminary host merged manifest was inspected below; broad provider paths alone do not establish an exposed operation.

The POM declares Kotlin stdlib 2.1.21 in compile scope, AndroidX Fragment 1.8.6 and DocumentFile 1.1.0 in runtime scope. Host conflict resolution selects Kotlin 2.4.20, as independently checked below.

## Resolved Android runtime and recipient notices

The completed `releaseRuntimeClasspath` was inventoried in a read-only Gradle task under the shared build lock. It selects 47 components, including metadata/BOM entries, with 41 distinct runtime artifacts: 27 AARs and 14 JARs. The artifact view initially emitted 43 rows; duplicate Core and Lifecycle ViewModel rows were deduplicated by coordinate and hash. Every selected published POM was independently fetched from Maven Central or Google Maven and matched the cached POM exactly.

The resolved graph includes Godot 4.7.2.stable, Kotlin stdlib 2.4.20, coroutines and serialization 1.11.0, AndroidX Fragment/KTX 1.8.6, Activity/KTX 1.8.1, Core/KTX 1.9.0, Lifecycle 2.6.1, SavedState/KTX 1.2.1, DocumentFile 1.1.0, JetBrains annotations 23.0.0, JSpecify 1.0.0, and Guava listenablefuture 1.0. Exact coordinates, lengths, and SHA-256 values are retained in `android-runtime/resolved-artifacts-unique.json`; metadata verification is in `published-pom-review.json`.

All selected POM license declarations resolve to Apache-2.0 except Godot's MIT declaration. Guava listenablefuture inherits Apache-2.0 from the independently verified `guava-parent:26.0-android` POM. Archive and nested-JAR inspection found native libraries only in Godot's AAR. The one distinct embedded license text, in DocumentFile, equals the canonical 10,175-byte AndroidX Apache text, SHA-256 `809fa1ed21450f59827d1e9aec720bbc4b687434fa22283c6cb5dd82a47ab9c0`.

POM declarations were supplemented with exact upstream source archives. Kotlin's source license inventory and stdlib sources confirm borrowed GWT/Guava code, ThreeTenBP time code, and Boost JVM math code. The corresponding six checked classes exist in the resolved stdlib JAR. This establishes dependency-input retention, not retention of each class after R8. Exact leading copyright/permission blocks from JetBrains annotations, JSpecify, and Guava sources are preserved with extraction offsets and hashes in `android-runtime/runtime-notice-copy-plan.json`. No unrelated Kotlin compiler/Native or baseline Skia/DNG notices were added to this host subset.

The native owner integrated nine reviewed additions into `android-host/src/main/assets/notices/`: `ANDROIDX_APACHE_2.txt`, `KOTLIN_APACHE_2.txt`, `KOTLIN_COPYRIGHT.txt`, `KOTLIN_THREETENBP_BSD.txt`, `KOTLIN_BOOST_LICENSE.txt`, `KOTLINX_COROUTINES_LICENSE.txt`, `KOTLINX_SERIALIZATION_LICENSE.txt`, `ANDROID_HOST_EXTRA_NOTICES.txt`, and `ANDROID_HOST_DEPENDENCIES.txt`. These comprise seven exact existing audited texts and two reviewed dependency/credit mappings, totaling 55,638 bytes.

An independent source-copy check confirms the complete expected set of **19 files, 537,959 bytes**: the nine additions, seven canonical engine/native files, and three font files all match their reviewed originals. Evidence: `android-host-final-notice-sources.json`. Durable source URLs, extraction records, and notice hashes are in `android-host/docs/runtime-notices-provenance.json` (5,918 bytes; SHA-256 `2984f4738d9cdf83b83fa849f2cf42fa16b589895c9151efab039885bdbe8715`), without temporary-directory or Gradle-cache references. The v5 APK/AAB audit below also verifies the complete expected set of names and hashes.

After notice-specific Git attributes were applied, a further independent check at commit `c80a5fc1c95ae5a7e26c1bb49e4f885b15d84352` confirmed that all 29 canonical/font/host notice Git blobs equal their working-tree bytes. The 19 host copies also still match the reviewed source hashes. Evidence: `notice-git-blob-review.json`.

For the desktop comparison delivered with this source tree, `renderer/README.md` links the full readable notice files. A separate renderer credits UI is not required for that delivery. Any later desktop binary/PCK distribution without the tree must retain a recipient-readable notice directory and documentation or provide a viewer; the Android-only screen does not establish that desktop path.

## First actual renderer PCK

The first canonical `partydeck-last-light.pck` is **1,532,712 bytes**, SHA-256 **`2c840bb8a20177aaed657cf5ae6f0bcee74964bc591d269ed741cd9e58365e35`**. Its input fingerprint is `1615fd93aaf5055baca9ea76a6abdf30bc3cbe01409cff27a38a15226c546594`.

Independent inspection mounted a stable copy with the verified Godot executable using `ProjectSettings.load_resource_pack()` from an isolated empty directory. It enumerated and read every file through the engine's `DirAccess`/`FileAccess` APIs, without instantiating the app. All **136 mounted paths, lengths, and SHA-256 values** match the receipt: no missing, extra, changed, or unreadable entries. All ten notice/provenance files and `assets/manifest.json` match their source bytes exactly.

The mounted pack contains both presentations and shared scripts, including 37 imported textures, six audio samples, four fontdata resources, three packed scenes, and 11 compiled GDScripts. No test/check/fixture/proof/editable-source/build entries were found. The engine exited successfully; its only stderr output was the root-user warning. Evidence and the stable PCK/receipt are retained under `pack-inspection/`, including `inspect_pack.gd`, `mounted-inventory.json`, and `mounted-pack-review.json`.

This accepts that specific first pack. The later combined UI v5 pack is separately inspected below; neither check establishes native runtime behavior.

## Preliminary Android artifacts

These APKs were independently inspected on 2026-09-10 around 00:54 UTC and remained stable during inspection. They contain only the original ten notices, before the nine managed-runtime additions, and are **provisional artifacts, not the final release milestone**.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Debug APK | 314,327,223 | `3cb4352778854da8e782b25fb8960498816973a4a322a22b2e9e61dbae96b42b` |
| Unsigned release APK | 311,412,493 | `209167831ff681bbde07814a6890e4e94097af58dcbd45acaa287303b0c7dc41` |

Both contain the exact first PCK above, uncompressed, and all eight native libraries match the verified official AAR hashes. Every native ZIP data offset is a multiple of 16 KB, and Android Build Tools 36 `zipalign -c -P 16 -v 4` passes. No test/check/fixture/proof paths were found. The debug APK has a valid APK v2 signature from an Android Debug certificate, SHA-256 `82c66f9e40e46b5ecb44e6f24315cc35cc11eec4b99ac3dc18079cc82e2147be`. The release APK is unsigned; signature verification fails as expected. Inventories explicitly record the nine missing runtime notices rather than checking only the files that happen to be present.

The actual release merged manifest identifies `dev.partydeck.godot.compare`, version `0.1.0`/1, minimum SDK 26, target 36, and compile SDK 37, with GLES 3 required. Backups, cleartext traffic, and native-library extraction are disabled. The only uses-permission is the app's signature-level `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`. The launcher is exported; game, notice, ProcessPhoenix, FileProvider, and AndroidX startup components are nonexported. The Godot activity runs in `:godot`, portrait and non-resizable; ProcessPhoenix runs in `:phoenix`. The exported ProfileInstaller receiver is guarded by `android.permission.DUMP`. No exposure is inferred merely from its exported flag or the FileProvider path inventory.

The preliminary AAB's BundleConfig enables uncompressed native libraries with `PAGE_ALIGNMENT_16K` and an uncompressed PCK glob. This configuration alone does not verify generated split APK alignment. The subsequent v5 audit below inspects actual generated splits. Evidence for all preliminary checks is under `android-preliminary/`.

## UI v5 PCK and Android artifact audit

The separately preserved v5 PCK is **1,542,328 bytes**, SHA-256 **`0b3de6b276d15972708cfc7919d7f2f5bf2aefe8a05afb8859357e7139057d37`**. Its receipt SHA-256 is `4039944f7f269ac5be22a302f52247101e3dc07a7924faf3e2e042b7e14ef0bc`; its source/tool input fingerprint is `6f3f1bf69490f15df0ff547f8746282eaafd8bd4266ce08edc00bda393662ce7`.

The same independent engine-mounted inspection read all **136 entries** from an isolated empty directory. Every actual path, length, and SHA-256 matches the receipt. The ten renderer notice/provenance files and asset manifest exactly match current sources. There are no duplicate, missing, changed, extra, or unreadable files, and no repository fixture/proof/test/check/tool/editable-source paths. Evidence and stable copies: `final-v5/pack/mounted-pack-review.json`, `mounted-inventory.json`, the PCK, and its receipt.

The coordinator's successful rebuild is recorded in `/tmp/partydeck-godot-android-final-package-build.log`. Independent package inspection around 02:14 UTC checked the following exact, stable files from `godot/qualification/build/modules/androidHost/outputs/`:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Debug APK | 315,870,392 | `de1acf679cd8578f6ec57f53cb9ca0e01581fe96841e1116937e1caf74972f59` |
| Unsigned release APK | 311,443,357 | `a04add0d0892bc63ba4ee1f6b17e549134dbc939be79e71ca18cb03f92c13371` |
| Unsigned release AAB | 104,816,396 | `4d27609a137979b5c4794132549edae1b024eacf917a35d472412b0a0013f70b` |

All three contain exactly one PCK with the v5 hash above, all **19 expected notice filenames and 537,959 exact source bytes**, and all eight verified AAR native libraries across the four ABIs. Every archive entry was read and hashed, with no duplicate or encrypted entries. Both APKs retain the PCK uncompressed; native ZIP offsets are multiples of 16 KB, and Build Tools 36 `zipalign -c -P 16 -v 4` passes. Matching native hashes preserve the earlier ELF findings: 64-bit LOAD alignment is 16 KB; 32-bit LOAD alignment is 4 KB. ZIP alignment is not a 16 KB device execution result.

The actual debug and release manifest dumps are byte-identical to their independently reviewed preliminary dumps. Package ID/version, minimum/target/compile SDKs, GLES requirement, privacy settings, process ownership, component exposure and guarded ProfileInstaller receiver therefore remain as recorded above. Debug is debuggable and verifies under APK Signature Scheme v2 with the same Android Debug certificate. Release is non-debuggable and unsigned; `apksigner` reports no signature. The AAB has only the base module, validates successfully, contains no JAR signing entries, and `jarsigner` confirms it is unsigned.

No repository fixture/proof/test/check/tool or editable-source paths were found in these packages. The only path candidate containing a `build` directory is the exact 56-byte Android Gradle plugin metadata with its two version properties; the original candidate and its classification are retained. `DebugProbesKt.bin` is an exact 1,728-byte resource from the reviewed coroutines 1.11.0 dependency, not a PartyDeck test fixture. The optimized APK also has ordinary baseline profile assets. Evidence: `final-v5/android/summary.json`, the three complete `*-inventory.json` files, manifest/signature/alignment logs, and `dependency-resource-classification.json`.

The AAB's intermediate ZIP compresses its PCK and native contents, while BundleConfig requests an uncompressed PCK and `PAGE_ALIGNMENT_16K` native output. Actual APK generation used **bundletool 1.18.3**, whose 32,520,401-byte JAR matches the official release API's SHA-256 `a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29`. All **15 generated APKs** were independently inspected: the three base/master splits retain the exact PCK uncompressed and all 19 notices; all **24 native library copies** in the twelve ABI splits match the verified AAR, remain uncompressed, and have 16 KB ZIP offsets. Every generated APK passes `zipalign` and signature verification using a disposable local test certificate. The temporary private key was deleted. These generated signatures are solely for this static audit and do not qualify publisher signing or runtime behavior. Evidence: `bundletool-identity.json`, `bundle-generated-splits.json`, `generated-split-review.json`, and `split-checks/`, all under `final-v5/android/`.

This accepted the named v5 artifact bytes and closed their package-content/notice/alignment findings. At that point, whole-PCK byte reproducibility remained open: the independent environment review found identical entry payloads but a different ordering of nine unchanged notice texts between exports. The corrected PCK and replacement packages are separately inspected below. The earlier PCK, package, and generated-split evidence remains preserved.

## Deterministic PCK and Android command-line refresh

The ordered exporter produces **1,542,328-byte PCK `26bfbb72efa55b63bef2e0ab989c82356c75b3bb3ca40bcf1c5e70e931bff890`**, with 136 entries. Receipt SHA-256: `14ff07912b3b49b3b4a922b056f401778bae50377aa3597791be9bd5a7c7347a`; recorded source/tool fingerprint: `b5d55f2a51f629191629a4f6f2fb5abcc44424a778a0e0435e34a4c668db3f79`.

This review independently mounted the new PCK and verified every path, length, and hash against its receipt, including the ten renderer notice/provenance files and asset manifest against source. There are no missing, duplicate, extra, forbidden, or unreadable entries. Comparing the mounted inventories against the preserved v5 PCK finds **135 unchanged payloads** and only `.godot/uid_cache.bin` changed. The environment reviewer parsed that cache against pinned Godot source and confirmed the same 58 UID-to-path mappings in a different record order, with all 132 renderer source files unchanged.

The environment reviewer independently executed import, source-scene checks, native export, and packed-scene checks from the frozen inputs. All stages passed and both raw PCKs are byte-identical. This review also compared the two actual files directly and confirmed whole-file equality. **The identical-input PCK byte-reproducibility gate is closed for this exporter/input set.** This does not assert cross-toolchain or cross-version reproducibility. Evidence: `/tmp/partydeck-godot-environment-review/final-ordered-v5/inspection.json` and `content-transition-inspection.json`, plus this review's `ordered-xr/pack/mounted-pack-review.json` and stable PCK/receipt.

The native host now supplies `--xr-mode` and `off` as separate command-line arguments. The coordinator's replacement package build completed successfully in 33 seconds (`/tmp/partydeck-godot-android-ordered-package-build.log`). Independent static inspection around 02:47 UTC verified:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Debug APK | 315,819,480 | `c1b6d6bd1725edf28fdf416ff8a98fddf4149423dd0697b5b0c25caffce512fb` |
| Unsigned release APK | 311,443,357 | `856bf2a4676ad4d5466a3f90dfe02b11f7b1291dffc83af6d81306e5c086f483` |
| Unsigned release AAB | 104,818,580 | `51bc9cbaebc91aef783f35d8d5e6cd8d4b380747cf5a3d4ff63b44c496de3a13` |

All three contain the exact deterministic PCK, all **19 notice files/537,959 bytes**, and all **eight native library files** unchanged from the prior reviewed originals. No entry paths were added or removed. Both APKs keep the PCK and native libraries uncompressed and pass `zipalign -c -P 16 -v 4`; every native ZIP offset is 16 KB aligned. Debug remains debuggable with the same valid v2 Android Debug signer. Release APK and AAB remain unsigned. All three manifest dumps are unchanged, including package/SDK metadata and component exposure.

Payload differences are limited to the PCK, one DEX per package, and corresponding optimized profile/R8 metadata. The AAB validates successfully; both raw `BundleConfig.pb` and `base/native.pb`, the decoded bundle policy, and every native payload exactly match the prior AAB. Its output still requests `PAGE_ALIGNMENT_16K` and an uncompressed PCK. This bounded differential audit did **not** generate another 15 APKs: the earlier split result remains evidence for AAB `4d27609a…`, while the unchanged inputs relevant to that alignment result are verified here. No native execution or successful startup is inferred from these static checks.

Separate evidence is retained under `ordered-xr/android/`: the three complete inventories, exact manifest/signature/alignment/validation outputs, `summary.json`, and `differential-review.json`. The earlier `final-v5/` evidence was not overwritten.

## CI replacement package differential

[Run 34433457249](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34433457249)
built these exact artifacts from **`bf77ea73e8b3b2f3f4115fda3a95f598c8de1148`**.
The package-build job **102733605318** completed successfully at
**2026-09-10 03:33:00 UTC**; the overall run and native suite failed. The debug
APK came from CI artifact **10135407640**, `godot-comparison-runtime-apk`;
the release APK, AAB, and PCK came from **10135412361**,
`godot-comparison-builds`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Replacement PCK | 1,542,296 | `6599f825a418f9d2a7049b3ba9325e8e0dcb474685262899079231b7ec955938` |
| Debug APK | 314,309,880 | `2957db8d5bff4fa7c02b9a4bedbab9a2ee474bfc289c47380e9ac94499c96fa0` |
| Unsigned release APK | 311,443,325 | `2735b98ede773eba7f035b54398c460b7fd01ebc71548dd72321d6df52e031ef` |
| Unsigned release AAB | 104,819,497 | `864469cfc912fa1a681a3494646e8e1c3fb7621c243e480a003ffe5347770f40` |

Independent binary parsing against the pinned Godot pack-reader contract checks
all **136 PCK entries**, including their bounds, checksums, lengths, and SHA-256
values. Every entry matches the CI receipt, whose SHA-256 is
`517bf63b7fea902a69505238c9e786f7cfdace2336a87a658044028e300981c3`.
All **132 renderer source files and four tools** match the retained CI source
archive; the recomputed source/tool fingerprint is
`a50c9521194011e7f83d30efe9df2d0f761ede952e6eebf4269ae21cab0fe94f`.
Compared with the accepted ordered PCK, **134 payloads are unchanged**; only
`scripts/main.gdc` and `presentations/three_d/table.gdc` changed. The ten
renderer notice/provenance files and asset manifest remain exact. No forbidden
fixture, test, proof, tool, or editable-source entry was found. The actual CI
PCK equals the local replacement PCK byte for byte; this review did not rerun
the engine export or native application.

Every archive member was read and hashed. The debug APK, release APK, and AAB
retain their respective **146, 83, and 90 entry paths**, with no additions,
removals, duplicates, or encrypted entries. All **19 notices / 537,959 bytes**,
all **eight native libraries**, and all three manifests are unchanged from the
accepted `ordered-xr` packages. Member compression policies are unchanged;
both APKs retain the PCK and native libraries uncompressed and pass Build Tools
36 `zipalign -c -P 16 -v 4`. Every native ZIP offset is 16 KB aligned. The
unchanged native hashes preserve the earlier ELF findings.

The debug APK's changed `classes6.dex` contains the renderer-exit wait update:
normalized disassembly isolates the existing-class change to
`GodotGameActivity.destroyEngine`, with three added wait/helper classes. Its
other six DEX payloads are unchanged. Release APK and AAB contain identical
optimized DEX bytes; disassembly and the packaged R8 map confirm retention of
the **1,500 ms** exit wait and unconfirmed-exit failure path. These are static
code-inclusion findings. The other changed payloads are the PCK, optimization
profiles/R8 metadata, and AAB resource metadata. Parsing `base/resources.pb`
finds only **ten source-line annotations** changed; the complete decoded
resource names, configurations, and values are identical.

Debug remains debuggable and verifies with APK Signature Scheme v2 under an
Android Debug certificate, SHA-256
`6d37f6c77cf880c7de162180db14904b099f48d4bd59f8cf1252ee17da095ae8`.
This CI development signer differs from the earlier local debug signer.
Release remains non-debuggable and unsigned; the AAB is unsigned, has only the
base module, and passes bundletool validation. Both raw `BundleConfig.pb` and
`base/native.pb`, the decoded bundle policy, and native payloads are unchanged,
including `PAGE_ALIGNMENT_16K` and the uncompressed-PCK output glob. No split
regeneration was warranted by this differential. The earlier 15-split result
continues to apply only to AAB `4d27609a…`; it is not a new split-build result
for the CI AAB.

All **20 audit checks pass** in
`/tmp/partydeck-godot-release-review/ci-34433457249/audit-summary.json`.
That directory retains the exact package files, run/head and CI artifact
metadata, build log, complete inventories, disassembly, and separate PCK,
DEX, resource, manifest, signature, and alignment records. Service ZIP digests
are retained as GitHub metadata; this review independently hashed the extracted
package files. Acceptance covers these exact static artifacts. No runtime or
split tests were repeated, and native-suite, publisher-signing, store, and
physical-device qualification remain open. Native runtime evidence is recorded
separately in the [environment review](environment-review.md).

## Reusable Android plugin extraction

The frozen local comparison build after extraction into `godot/android-renderer`
passed a bounded reflection and resource review on **2026-09-10**:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Optimized release APK | 311,443,325 | `f5ae9db9b00574672811ed0288be06291919d582c25f8d2d34f726bfe0197b82` |
| Debug APK | 314,309,938 | `6fd3e9ce0d761bd675f301c791d47589f0fa5ba0423ef39fc9db37dc0633c889` |

The independently rechecked, pinned Godot 4.7.2 sources establish that registration
uses `getDeclaredMethods()`, runtime `UsedByGodot` annotations, and each Java
method's name and types. The optimized APK's R8 map identifies the relocated
`dev.partydeck.godot.android.PartyDeckBridgePlugin` as `jg` and the annotation
type as `wl`. Actual DEX inspection confirms that all four methods remain public,
with unchanged names/prototypes and runtime annotations:

- `get_launch_document(): String`
- `get_display_scale(): double`
- `renderer_event(String): void`
- `renderer_diagnostics(String): void`

The annotation type retains runtime retention. Optimized registration code still
reflects that same type and calls `nativeRegisterMethod`; the singleton name
remains `PartyDeckBridge`. The merged R8 configuration identifies
`androidRenderer` as the source of the relocated consumer rules. This verifies
the packaged reflection contract without executing native registration.

Both APKs contain exactly one uncompressed PCK, with the unchanged SHA-256
`6599f825a418f9d2a7049b3ba9325e8e0dcb474685262899079231b7ec955938`.
All **19 notices / 537,959 bytes** match the accepted CI package set. Neither
APK has duplicate ZIP entry names. The debug APK now has 147 entries, including
the added `classes8.dex` partition; the release APK has 83.

The receipt, source snapshots, actual DEX annotations/disassembly, R8 map and
consumer configuration are retained under
`/tmp/partydeck-godot-release-review/android-renderer-extraction-20260910/`.
Exact APK copies are under
`artifacts/evidence-storage/release-review/android-renderer-extraction-20260910/`.
This addendum verifies relocation, reflection, and resource retention for the
named local APKs. The earlier 20-check CI audit retains its exact artifact scope;
native runtime, input-gate behavior, generated splits, and distribution signing
were not qualified by this bounded review.

## Production Credits source completeness

The production Credits source change passed independent review on **2026-09-10**
against committed baseline `86ca7f5`. All **19 canonical notices / 537,959 bytes**
remain identical to that baseline and to the accepted comparison release APK
`f5ae9db9b00574672811ed0288be06291919d582c25f8d2d34f726bfe0197b82`, whose
identity was independently rechecked. Each new common resource under
`files/licenses/godot/` preserves its original filename and exact bytes.

The regenerated `files/licenses/third_party_notices.txt` is **743,782 bytes**,
SHA-256 `7e20d6f71fcc8fba56050280ea38d41305029194c585be59f070eaaf2ac71e06`.
All **83 complete notice bodies** retain their associated titles and component
attributions in **66 distinct text groups**. This includes the full Godot
MIT/copyright notices, NDK/LLVM notice, Mozilla CA source and source-availability
notice. The Android comparison dependency inventory and supplemental notices
remain explicitly labeled for the comparison host. Their inclusion does not
assert a new production dependency inventory.

The existing **64 individual common notice resources** are unchanged. An
independent isolated generator run reproduces all **84 resource files**, and
the focused `verify_assets.check_sources()` check passes **87 pinned files**.
The unchanged common Settings implementation reads this complete aggregate and
splits it into bounded text items without discarding characters. The retained
official Godot license guidance and pinned upstream license/copyright files
were also checked against the reviewed sources.

Reproducible review code, body/attribution checks, hashes, focused-check output
and generated copies are retained under
`/tmp/partydeck-godot-release-review/production-credits-20260910/`.
This closes the source completeness gap in production Credits. Final Android/iOS
package inclusion and native Credits-screen execution remain separate checks;
no app build or native run was performed for this addendum.

## Production Android merged-manifest checkpoint

The coordinator's actual debug/release merged manifests and successful
`releaseRuntimeClasspath` report were independently reviewed on **2026-09-10**.
The retained manifest identities are:

| Manifest | SHA-256 |
| --- | --- |
| Debug | `f3407ad13120a092189ede865c4726c76d4a9b2ac50e8f3591180a049e71e18f` |
| Release | `24a482e75253b05033457a687d6436636092f0299fd930c875a35f5a33047848` |

They differ only in debug's `debuggable=true`. All **10 components** match the
application declarations and expected transitive entries. `MainActivity` is the
only exported component without a declared permission; the exported
`ProfileInstallReceiver` declares `android.permission.DUMP`. The renderer,
broker, Godot `ProcessPhoenix`, and all providers remain nonexported. The
renderer uses `:godot`, and the broker remains in the shell process.

Permissions remain Internet, Camera, and AndroidX's app-owned signature
permission. Camera features and GLES 3 remain optional. The minimum/target SDKs
remain 26/36; backup and cleartext restrictions and the intended startup
initializers survive merging. Godot's provider attributes match its pinned AAR.

The resolved release graph includes Godot **4.7.2.stable**, Fragment and
Fragment KTX **1.8.6**, DocumentFile **1.1.0**, Kotlin standard library
**2.4.20**, Activity **1.13.0**, and Lifecycle runtime **2.11.0**.
The receipt and input hashes are retained in
`/tmp/partydeck-godot-release-review/production-manifest-20260910/audit-summary.json`;
the coordinator's manifest copies and dependency log remain under
`/tmp/partydeck-production-manifest-review/` and
`/tmp/partydeck-production-manifest-check.log`.
This checkpoint establishes merged configuration and dependency resolution.
It does not verify a production APK/AAB, PCK, optimized DEX, native libraries,
installation, or runtime behavior.

## Remaining artifact gates

- Retain the exact checked artifact identities and unsigned/debug labels. Any further replacement requires checking changed inputs and package contents against the accepted evidence.
- Execute the native recipient notice index and verify access to the retained MPL source, NDK/LLVM, font, and managed-runtime documents. The complete document set is now verified in the named packages; retention does not establish an executed screen or native accessibility.
- Keep Android/iOS native embedding, foreground/background concealment, teardown/re-entry, input, sound, native accessibility, physical LAN and device performance gates separate from source, headless, PCK, and ELF evidence. Refer to the other independent Godot reviews for their acceptance criteria and observed results.

## Authoritative sources

- [Official Godot 4.7.2 release artifacts](https://github.com/godotengine/godot-builds/releases/tag/4.7.2-stable), [source tag](https://github.com/godotengine/godot/tree/4.7.2-stable), [Maven module](https://repo.maven.apache.org/maven2/org/godotengine/godot/4.7.2.stable/godot-4.7.2.stable.module), and [POM](https://repo.maven.apache.org/maven2/org/godotengine/godot/4.7.2.stable/godot-4.7.2.stable.pom).
- Pinned engine [MIT license](https://github.com/godotengine/godot/blob/4.7.2-stable/LICENSE.txt), [third-party copyrights/licenses](https://github.com/godotengine/godot/blob/4.7.2-stable/COPYRIGHT.txt), and [Engine license-query API](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Engine.xml).
- [Godot license-compliance guidance](https://docs.godotengine.org/en/stable/about/complying_with_licenses.html), retrieved 2026-09-09; retained HTML SHA-256 `3f27b275844371b82f2c4fdd8265ff59b815d33dfadc124eb0c8490a5508e11c`.
- Pinned [certificate generation](https://github.com/godotengine/godot/blob/4.7.2-stable/core/core_builders.py), [compression helper](https://github.com/godotengine/godot/blob/4.7.2-stable/methods.py), [certificate loading](https://github.com/godotengine/godot/blob/4.7.2-stable/modules/mbedtls/crypto_mbedtls.cpp), and [Android toolchain configuration](https://github.com/godotengine/godot/blob/4.7.2-stable/platform/android/detect.py).
- [Official Android NDK r29 Linux archive](https://dl.google.com/android/repository/android-ndk-r29-linux.zip) and [Google SDK repository metadata](https://dl.google.com/android/repository/repository2-3.xml); archive and metadata records retained under `upstream/android-ndk/`. The archive's LLVM notice also exactly matches the Android prebuilts [pinned r29 toolchain notice](https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/+/568b941cf0c249b9c2a1f853e94a29f0e6291c59/clang-r563880c/NOTICE).
- [Official bundletool 1.18.3 release](https://github.com/google/bundletool/releases/tag/1.18.3), with the actual JAR checked against the release API digest. Installed `help build-apks` documents APK-set generation and explicit local signing inputs; generated output and signature/alignment tool results are retained separately from the unsigned source AAB.
- Pinned Godot [PCK flags and format constants](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/io/file_access_pack.h) and [pack reader](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/io/file_access_pack.cpp), independently fetched for the CI differential's binary parser. The verified bundletool JAR's actual `help dump` contract and `Resources.ResourceTable` parser were used for the resource/configuration comparison.
