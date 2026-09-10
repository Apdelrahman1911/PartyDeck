# Godot release and artifact review

Independent review by `review_release`, 2026-09-09; updated 2026-09-10. Both Last Light presentations are reviewed as renderers of the same authority bridge. Neither renderer is selected for shipping by this review.

**Status:** engine/AAR provenance, shared asset inventory, the first actual renderer PCK, and the resolved Android runtime dependency/notice sources are independently verified. All 19 host notice source files match the reviewed originals. Preliminary APKs pass the static package checks below but predate nine runtime notice additions and the final UI changes. The final PCK/APK/AAB rebuild and native runtime results remain pending. Existing Compose/KMP Android and iOS qualification does not qualify the new Godot host.

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

Two Android native items were identified and are now covered in the canonical notice directory. Their exact notice/source bytes are present in the first independently mounted PCK and preliminary APKs; the final rebuild still needs verification:

1. **MPL certificate source is actually retained.** The same 130,566-byte zlib stream exists in all four `libgodot_android.so` files. Decompression yields the exact 225,076-byte pinned `thirdparty/certs/ca-bundle.crt`, SHA-256 `33a22c7286f7752131636a11fb9feb3fb12ecd02f1a9b3e54e5901349d37362e`. Godot's notice includes Mozilla attribution and MPL-2.0. The new `GODOT_CA_BUNDLE_SOURCE.txt` is an exact offline source copy; `GODOT_CA_CERTIFICATES_SOURCE.txt` identifies it and links to the [unchanged source at the full pinned commit](https://raw.githubusercontent.com/godotengine/godot/ed1daf0bf001b61586d9930840f2f1394092c079/thirdparty/certs/ca-bundle.crt), addressing source availability under MPL section 3.2. Evidence: `aar-certificate-deflate-review.json` and `renderer-notice-review.json`. This establishes retention, not a runtime network operation by PartyDeck.
2. **The C++ runtime has verified NDK provenance and separate notice coverage.** Each ABI includes `libc++_shared.so`; neither the AAR nor its `classes.jar` contains standalone license/notice files, and Godot's `COPYRIGHT.txt` has no LLVM/libc++ section. All four runtimes match NDK r29's prebuilt build IDs and every ELF LOAD byte except section-table header fields changed by stripping. The official NDK r29 Linux ZIP's 783,549,481-byte size and SHA-1 `87e2bb7e9be5d6a1c6cdf5ec40dd4e0c6d07c30b` match Google's SDK repository metadata; its independently computed SHA-256 is `4abbbcdc842f3d4879206e9695d52709603e52dd68d3c1fff04b3b5e7a308ecf`. The new `ANDROID_NDK_LLVM_NOTICE.txt` equals its complete 130,424-byte `toolchains/llvm/prebuilt/linux-x86_64/NOTICE`, SHA-256 `f96f763beb66a7ba7a667647fc64c0226ace875e590c831fdd9579ec1c1d91e1`, including LLVM Apache-2.0 exceptions and libc++/libc++abi notices. Evidence: `aar-libcxx-ndk-comparison.json`, `renderer-notice-review.json`, and `upstream/android-ndk/ndk-r29-package-review.json`.

The C++ runtime retains an ELF note saying NDK `r28` build `13004108`; it is nevertheless the prebuilt runtime shipped in the verified NDK r29 distribution. Godot's DSO records `r29` build `14206865`. The embedded note alone must not be used to assign a different distribution or infer incompatibility.

The seven canonical files in `renderer/licenses/` include these four exact upstream files, the source-availability note, `README.txt`, and `NOTICE_PROVENANCE.json`. The latter records accurate artifact sizes/hashes, all four C++ build IDs, original filenames and source commits. Both new full-commit source URLs were independently fetched and matched the canonical bytes (`recipient-source-url-review.json`). The final source-availability note is 1,241 bytes, SHA-256 `c68edd43fa15b39be0aa724eaf28cdfa9df22a83eb74f66614b93993bdcde1f7`. Android's native notice index is implemented and reads each document separately. Its source files are verified below; the final packaged index and an executed screen are not yet verified.

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

An independent source-copy check confirms the complete expected set of **19 files, 537,959 bytes**: the nine additions, seven canonical engine/native files, and three font files all match their reviewed originals. Evidence: `android-host-final-notice-sources.json`. Durable source URLs, extraction records, and notice hashes are in `android-host/docs/runtime-notices-provenance.json` (5,918 bytes; SHA-256 `2984f4738d9cdf83b83fa849f2cf42fa16b589895c9151efab039885bdbe8715`), without temporary-directory or Gradle-cache references. All 19 expected names and hashes must be checked again in the final APK/AAB.

After notice-specific Git attributes were applied, a further independent check at commit `c80a5fc1c95ae5a7e26c1bb49e4f885b15d84352` confirmed that all 29 canonical/font/host notice Git blobs equal their working-tree bytes. The 19 host copies also still match the reviewed source hashes. Evidence: `notice-git-blob-review.json`.

For the desktop comparison delivered with this source tree, `renderer/README.md` links the full readable notice files. A separate renderer credits UI is not required for that delivery. Any later desktop binary/PCK distribution without the tree must retain a recipient-readable notice directory and documentation or provide a viewer; the Android-only screen does not establish that desktop path.

## First actual renderer PCK

The first canonical `partydeck-last-light.pck` is **1,532,712 bytes**, SHA-256 **`2c840bb8a20177aaed657cf5ae6f0bcee74964bc591d269ed741cd9e58365e35`**. Its input fingerprint is `1615fd93aaf5055baca9ea76a6abdf30bc3cbe01409cff27a38a15226c546594`.

Independent inspection mounted a stable copy with the verified Godot executable using `ProjectSettings.load_resource_pack()` from an isolated empty directory. It enumerated and read every file through the engine's `DirAccess`/`FileAccess` APIs, without instantiating the app. All **136 mounted paths, lengths, and SHA-256 values** match the receipt: no missing, extra, changed, or unreadable entries. All ten notice/provenance files and `assets/manifest.json` match their source bytes exactly.

The mounted pack contains both presentations and shared scripts, including 37 imported textures, six audio samples, four fontdata resources, three packed scenes, and 11 compiled GDScripts. No test/check/fixture/proof/editable-source/build entries were found. The engine exited successfully; its only stderr output was the root-user warning. Evidence and the stable PCK/receipt are retained under `pack-inspection/`, including `inspect_pack.gd`, `mounted-inventory.json`, and `mounted-pack-review.json`.

This accepts that specific first pack. It does not transfer acceptance to the upcoming combined UI v5 pack or establish native runtime behavior.

## Preliminary Android artifacts

These APKs were independently inspected on 2026-09-10 around 00:54 UTC and remained stable during inspection. They contain only the original ten notices, before the nine managed-runtime additions, and are **provisional artifacts, not the final release milestone**.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Debug APK | 314,327,223 | `3cb4352778854da8e782b25fb8960498816973a4a322a22b2e9e61dbae96b42b` |
| Unsigned release APK | 311,412,493 | `209167831ff681bbde07814a6890e4e94097af58dcbd45acaa287303b0c7dc41` |

Both contain the exact first PCK above, uncompressed, and all eight native libraries match the verified official AAR hashes. Every native ZIP data offset is a multiple of 16 KB, and Android Build Tools 36 `zipalign -c -P 16 -v 4` passes. No test/check/fixture/proof paths were found. The debug APK has a valid APK v2 signature from an Android Debug certificate, SHA-256 `82c66f9e40e46b5ecb44e6f24315cc35cc11eec4b99ac3dc18079cc82e2147be`. The release APK is unsigned; signature verification fails as expected. Inventories explicitly record the nine missing runtime notices rather than checking only the files that happen to be present.

The actual release merged manifest identifies `dev.partydeck.godot.compare`, version `0.1.0`/1, minimum SDK 26, target 36, and compile SDK 37, with GLES 3 required. Backups, cleartext traffic, and native-library extraction are disabled. The only uses-permission is the app's signature-level `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`. The launcher is exported; game, notice, ProcessPhoenix, FileProvider, and AndroidX startup components are nonexported. The Godot activity runs in `:godot`, portrait and non-resizable; ProcessPhoenix runs in `:phoenix`. The exported ProfileInstaller receiver is guarded by `android.permission.DUMP`. No exposure is inferred merely from its exported flag or the FileProvider path inventory.

The preliminary AAB's BundleConfig enables uncompressed native libraries with `PAGE_ALIGNMENT_16K` and an uncompressed PCK glob. This configuration alone does not verify generated split APK alignment. Full final AAB contents, signing state, and generated splits remain open. Evidence for all preliminary checks is under `android-preliminary/`.

## Remaining artifact gates

- Independently mount the final combined UI v5 PCK and compare all actual entries to its receipt and current source notices. Preserve the accepted first-pack evidence separately.
- Inspect the rebuilt host APK/AAB: package identity, merged manifest, ABI contents, native and final PCK hashes, every one of the 19 expected notice filenames and hashes, signing/debug state, package size and final APK/split ZIP alignment. An unsigned or debug qualification artifact must retain that label.
- Confirm the final recipient notice index exposes the retained MPL source, NDK/LLVM runtime coverage, font notices, and managed-runtime notices. Source and package retention do not establish an executed screen or native accessibility.
- Keep Android/iOS native embedding, foreground/background concealment, teardown/re-entry, input, sound, native accessibility, physical LAN and device performance gates separate from source, headless, PCK, and ELF evidence. Refer to the other independent Godot reviews for their acceptance criteria and observed results.

## Authoritative sources

- [Official Godot 4.7.2 release artifacts](https://github.com/godotengine/godot-builds/releases/tag/4.7.2-stable), [source tag](https://github.com/godotengine/godot/tree/4.7.2-stable), [Maven module](https://repo.maven.apache.org/maven2/org/godotengine/godot/4.7.2.stable/godot-4.7.2.stable.module), and [POM](https://repo.maven.apache.org/maven2/org/godotengine/godot/4.7.2.stable/godot-4.7.2.stable.pom).
- Pinned engine [MIT license](https://github.com/godotengine/godot/blob/4.7.2-stable/LICENSE.txt), [third-party copyrights/licenses](https://github.com/godotengine/godot/blob/4.7.2-stable/COPYRIGHT.txt), and [Engine license-query API](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Engine.xml).
- [Godot license-compliance guidance](https://docs.godotengine.org/en/stable/about/complying_with_licenses.html), retrieved 2026-09-09; retained HTML SHA-256 `3f27b275844371b82f2c4fdd8265ff59b815d33dfadc124eb0c8490a5508e11c`.
- Pinned [certificate generation](https://github.com/godotengine/godot/blob/4.7.2-stable/core/core_builders.py), [compression helper](https://github.com/godotengine/godot/blob/4.7.2-stable/methods.py), [certificate loading](https://github.com/godotengine/godot/blob/4.7.2-stable/modules/mbedtls/crypto_mbedtls.cpp), and [Android toolchain configuration](https://github.com/godotengine/godot/blob/4.7.2-stable/platform/android/detect.py).
- [Official Android NDK r29 Linux archive](https://dl.google.com/android/repository/android-ndk-r29-linux.zip) and [Google SDK repository metadata](https://dl.google.com/android/repository/repository2-3.xml); archive and metadata records retained under `upstream/android-ndk/`. The archive's LLVM notice also exactly matches the Android prebuilts [pinned r29 toolchain notice](https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/+/568b941cf0c249b9c2a1f853e94a29f0e6291c59/clang-r563880c/NOTICE).
