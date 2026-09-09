# Runtime dependency licenses and notices

Audit date: 2026-09-09. This audit covers the resolved dependency inputs below, their published POM license declarations, embedded archive notices, and identified native source notices. It does not equate a dependency declaration with proof that every object survives final linking or Android shrinking.

The machine-readable Gradle evidence is [dependency_inventory.json](../assets/licenses/runtime/dependency_inventory.json). Every artifact entry records its coordinate, filename, SHA-256, size, configuration membership, published POM URL/hash/license declarations, and embedded license/notice entries. License inheritance is followed through parent POMs when the selected module omits its own declaration. [swift_package_resolution.json](../assets/licenses/runtime/swift_package_resolution.json) records the separately verified Xcode package lock and pinned source comparison. Build plugins, test-only dependencies, the operating system, and SDK/compiler distributions are outside the runtime inventory.

## Resolution evidence

Read-only Gradle 9.7.0 resolution was executed under the shared build lock, without building the application. The ordinary Android report and a temporary init-script report using Gradle's documented `Configuration.incoming`, `ArtifactView`, `ResolvedArtifactResult`, and `ModuleComponentIdentifier` APIs produced these inputs:

| Configuration | Resolved module components, including metadata/BOM nodes | Artifact files inspected |
|---|---:|---:|
| `:androidApp:releaseRuntimeClasspath` | 194 | 132 |
| `:composeApp:jvmRuntimeClasspath` | 118 | 61 |
| `:composeApp:iosArm64CompileKlibraries` | 102 | 52 |
| `:composeApp:iosSimulatorArm64CompileKlibraries` | 102 | 52 |

There are 279 distinct artifact files across the four reports; a shared file is recorded once with all applicable configurations. JAR, AAR, and KLIB contents were inspected, including JARs nested inside AARs. Source artifact coordinates are retained even where Android release shrinking could remove their classes. The iOS rows describe Kotlin/Native inputs resolved on Linux. The Xcode package graph is recorded separately below; neither resolution report establishes a completed Apple link.

Gradle API references: [Configuration](https://docs.gradle.org/9.7.0/javadoc/org/gradle/api/artifacts/Configuration.html), [ResolvedArtifactResult](https://docs.gradle.org/9.7.0/javadoc/org/gradle/api/artifacts/result/ResolvedArtifactResult.html), and [ModuleComponentIdentifier](https://docs.gradle.org/9.7.0/javadoc/org/gradle/api/artifacts/component/ModuleComponentIdentifier.html).

The read-only reporting task is preserved in [resolve_inventory.init.gradle](../assets/licenses/runtime/resolve_inventory.init.gradle). Reproduce the configuration reports with:

```sh
flock /tmp/partydeck-gradle.lock ./gradlew --no-configuration-cache \
  -I assets/licenses/runtime/resolve_inventory.init.gradle \
  :androidApp:partyDeckLicenseInventory :composeApp:partyDeckLicenseInventory
```

Each owning project resolves its own configurations, as required by Gradle's project locking. The `PARTYDECK_LICENSE_INVENTORY=` output contains local cache paths for inspection; keep raw reports outside version control. The committed inventory uses only artifact filenames, coordinates, public URLs, and hashes. Updating it also requires inspecting the selected archives and native source revisions; the reporting task does not infer their licenses.

## License declarations and source evidence

| Runtime family | Verified selected versions or scope | License evidence and required additional notices |
|---|---|---|
| Kotlin standard library | 2.4.20 | Published POM declares Apache-2.0. The [pinned repository license inventory](https://github.com/JetBrains/kotlin/blob/v2.4.20/license/README.md) additionally identifies runtime code derived from GWT, Guava, ThreeTenBP (BSD 3-Clause), and Boost (Boost Software License 1.0). Compiler-only third-party code is not treated as app runtime code. |
| Compose Multiplatform and AndroidX | All selected Android/JVM/iOS variants in the inventory, including Compose 1.12.0 and lifecycle 2.11.0 | Selected POMs declare Apache License 2.0. The common license text was extracted from the actual archives, not inferred from an unrelated component's name. Material/navigation/saved-state implementation variants have their own resolved versions in the inventory. |
| kotlinx.coroutines / kotlinx.serialization | 1.11.0 | Published POMs and pinned [coroutines LICENSE](https://github.com/Kotlin/kotlinx.coroutines/blob/1.11.0/LICENSE.txt) / [serialization LICENSE](https://github.com/Kotlin/kotlinx.serialization/blob/v1.11.0/LICENSE.txt) declare Apache-2.0. |
| Other resolved JetBrains libraries | atomicfu 0.28.0 JVM / 0.32.1 iOS, datetime 0.7.1, annotations 23.0.0, JBR API 1.9.0 | License declarations are recorded from the exact selected POMs. JBR API's POM declares Apache 2.0; this is not a claim about a bundled Java runtime distribution. |
| Bouncy Castle | `bcpkix-jdk18on:1.85`, `bcutil-jdk18on:1.85`, `bcprov-jdk18on:1.85.2` | The provider patch is verified in the resolved Android/JVM graph. All three actual JARs contain the same `META-INF/LICENSE.md`: MIT License, copyright 2000–2026 The Legion of the Bouncy Castle Inc. The exact text is preserved. |
| QRose | Android/JVM/iOS and core variants, 1.2.0 | POMs declare MIT. The existing asset audit preserves the [pinned upstream MIT license](https://github.com/alexzhirkevich/qrose/blob/1.2.0/LICENSE). The encoder's [QRMath](https://github.com/alexzhirkevich/qrose/blob/1.2.0/qrose/src/commonMain/kotlin/io/github/alexzhirkevich/qrose/qrcode/internals/QRMath.kt) and QRUtil headers identify code derived from Rafael Lins's qrcode-kotlin and Kazuhiko Arase's qrcode-generator. Both additional MIT copyright/permission notices are retained with pinned source snapshots; no separate dependency version or imported source revision is invented. |
| CameraX and other AndroidX camera components | CameraX 1.6.2, viewfinder 1.5.1 | POMs declare Apache 2.0; `camera-core:1.6.2` also declares BSD 3-Clause. Existing verified notices include LibYuv's license and patent grant. Native archive inventory must be kept when camera dependencies change. |
| ZXing | `com.google.zxing:core:3.5.4` | License inherited from `zxing-parent:3.5.4`; existing pinned [LICENSE](https://github.com/zxing/zxing/blob/zxing-3.5.4/LICENSE) and [NOTICE](https://github.com/zxing/zxing/blob/zxing-3.5.4/NOTICE) are preserved. |
| Guava, failureaccess, listenablefuture, Auto Value annotations | Exact selected coordinates in the inventory | Apache license inheritance was verified through their parent POMs, including the older `guava-parent:26.0-android` used by the small compatibility artifacts. |
| Dagger, J2ObjC, Error Prone, JSR-305, Javax Inject, JSpecify | Exact selected coordinates in the inventory | Published POM declarations are recorded. These are runtime configuration inputs even if optimizers later remove annotation-only classes. |
| Jakarta Dependency Injection | `jakarta.inject-api:2.0.1` | The actual JAR contains both Apache `META-INF/LICENSE.txt` and `META-INF/NOTICE.md`; both are preserved. The notice identifies the Eclipse Jakarta Dependency Injection project. |
| Checker Framework qualifiers | `checker-qual:3.43.0` | The actual JAR contains the MIT license with the Checker Framework developers' copyright. This is the qualifier library, not the Checker Framework compiler tool. |
| Skiko / Skia | Skiko 0.150.1; Skia `m150-1f14f1166a` | Skiko's POM/license is Apache 2.0, with a separate [NOTICE](https://github.com/JetBrains/skiko/blob/v0.150.1/NOTICE). Skia's BSD license and its bundled native components need their own notices; see below. |
| Swift Certificates | Resolved by Xcode to 1.20.0 | [LICENSE.txt](https://github.com/apple/swift-certificates/blob/c8aece90ea05f9866bd392a5bf13b5cae56c0e03/LICENSE.txt), [NOTICE.txt](https://github.com/apple/swift-certificates/blob/c8aece90ea05f9866bd392a5bf13b5cae56c0e03/NOTICE.txt), and the full musl MIT copyright/permission text embedded in [TimeCalculations.swift](https://github.com/apple/swift-certificates/blob/c8aece90ea05f9866bd392a5bf13b5cae56c0e03/Sources/X509/X509BaseTypes/TimeCalculations.swift), all verified against the locked commit. |
| Swift Crypto / Swift ASN.1 | Resolved by Xcode to 4.5.2 / 1.7.2 | Each package's Apache LICENSE and NOTICE bytes match its locked source commit. The audited BoringSSL source revision is also confirmed by the locked Swift Crypto package. |

## Embedded notices versus native code

The JAR/AAR/KLIB scan found five distinct embedded text contents: the shared AndroidX/Compose Apache license, Jakarta's Apache license and NOTICE, Bouncy Castle's MIT license, and Checker Framework qualifiers' MIT license. [embedded_notice_sources.json](../assets/licenses/runtime/embedded_notice_sources.json) maps each verbatim text back to every containing coordinate. Identical bytes may be presented once in the legal screen while all origins remain in the audit inventory.

An absent text file inside an archive does not mean there are no notice obligations. For example, the actual Skiko iOS KLIB includes 22 native/static archive members, including Skia, DNG SDK, Expat, HarfBuzz, ICU, libjpeg, piex, libpng, libwebp, and zlib. The shipped JVM `org/jetbrains/skiko/Version.class` contains `m150-1f14f1166a`, matching the [Skiko release configuration](https://github.com/JetBrains/skiko/blob/v0.150.1/skiko/gradle.properties). Its pinned [Skia DEPS](https://github.com/JetBrains/skia/blob/m150-1f14f1166a/DEPS), [build script](https://github.com/JetBrains/skia/blob/m150-1f14f1166a/tools/skia_release/build.py), and [release archive script](https://github.com/JetBrains/skia/blob/m150-1f14f1166a/tools/skia_release/archive.py) identify native dependency sources and license files separately from the Maven POM.

Kotlin's standard-library/runtime source inventory is also checked separately from the compiler's license list. The application does not distribute the Kotlin compiler, test fixtures, Xcode SDK, or Kotlin's Windows/Zephyr/sample-only components merely because those licenses exist in the upstream repository.

The [Skia source manifest](../assets/licenses/runtime/skia_notice_sources.json) pins each component to the commit in that release's `DEPS`. It preserves these terms separately:

| Native component | Preserved license/notice evidence |
|---|---|
| DNG SDK | Adobe DNG SDK License Agreement, `LICENSE.source_code`, technology acknowledgment, full `NOTICE`, and DNG patent license. This is a custom license, not BSD or MIT. |
| Expat / HarfBuzz / ICU | Expat MIT-style `COPYING`; HarfBuzz's "Old MIT" `COPYING`; full ICU `LICENSE`, including its additional notices. |
| libjpeg-turbo | Full `LICENSE.md` and `README.ijg`, covering the IJG and modified BSD terms and the required binary acknowledgment. |
| piex / libpng / libwebp / zlib | piex Apache license and `NOTICE`; complete PNG Reference Library license; libwebp BSD license and patent grant; zlib license. |
| FreeType / Brotli | FreeType's root license-selection document and `docs/FTL.TXT`, plus the separate BDF, PCF, hashing, and gzip notices it identifies; Brotli MIT license. The FreeType License route is used. These are desktop native source coverage; no separate FreeType or Brotli archive was observed in the inspected iOS KLIB. |

The [additional source manifest](../assets/licenses/runtime/source_notice_sources.json) also retains Kotlin native runtime notices for Apache Harmony, libbacktrace, Unicode data, UTF8-CPP headers, and Dmitry Vyukov's bounded queue. The runtime build/source files establish their scope. UTF8-CPP uses Boost-style permission terms; the queue has its own BSD-style redistribution notice. Kotlin's Breakpad build is restricted to macOS, so that compiler-distribution notice is not represented as an iOS runtime dependency. When a complete notice is embedded in a source comment, the manifest records the original file hash, extracted line range, and transformation.

## Required binary acknowledgments

[required_acknowledgments.txt](../assets/licenses/runtime/required_acknowledgments.txt) supplies the following credits prominently in the aggregate's runtime section:

> This software is based in part on the work of the Independent JPEG Group.

> This software is based in part on the work of the FreeType Team (https://freetype.org).

> This product includes DNG technology under license by Adobe Systems Incorporated.

These come from the pinned IJG, FreeType, and DNG patent terms linked in the manifest. FreeType's suggested year-specific credit is optional; no unverified year is invented.

DNG's [source-code agreement](../assets/licenses/runtime/skia_dng_sdk_LICENSE.source_code) grants redistribution rights, but section 5 addresses indemnification when distributing the software in a commercial product, and section 6 restricts trademark use. The release owner must account for those terms if DNG code remains in the distributed product. The notices are included conservatively while final-link retention is unverified. Absence of a standalone `libdng_sdk.a` file in an app bundle would not demonstrate exclusion of statically linked DNG code.

## Resolved Swift packages and native boundary

The [Xcode Package.resolved](../iosApp/PartyDeck.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved) retrieved from macOS CI run `34378549932` has SHA-256 `47eb4a3e1acc5072f207aaf2d4dc924544afeeda3e01800079c81d05322b08d3`. The workspace file matches the captured CI artifact byte-for-byte. It selects exactly these packages:

| Package | Selected version | Locked revision |
|---|---|---|
| Swift Certificates | 1.20.0 | `c8aece90ea05f9866bd392a5bf13b5cae56c0e03` |
| Swift Crypto | 4.5.2 | `da9d28d69ebe3894b18376c8f2395c2f37b8448f` |
| Swift ASN.1 | 1.7.2 | `d9a5b37470adc940d22c3bcd5ca6953a516b727f` |

All three audited upstream checkouts match those locked revisions. The six LICENSE/NOTICE files were compared directly with their pinned Git objects; their bytes already match the bundled texts. The Swift Certificates musl source hash and complete extracted permission block also match its locked commit. The [resolution record](../assets/licenses/runtime/swift_package_resolution.json) retains the package manifest and notice-source hashes. All recorded Swift notices are verified against the resolved sources.

Swift Crypto's locked [Package.swift](https://github.com/apple/swift-crypto/blob/da9d28d69ebe3894b18376c8f2395c2f37b8448f/Package.swift) and [vendored hash file](https://github.com/apple/swift-crypto/blob/da9d28d69ebe3894b18376c8f2395c2f37b8448f/Sources/CCryptoBoringSSL/hash.txt) both identify BoringSSL commit `0226f30467f540a3f62ef48d453f93927da199b6`, matching the audited BoringSSL license source. `_CryptoExtras` leads to `CryptoExtras`, whose declared target dependencies include BoringSSL on Apple platforms. This source dependency is recorded without inferring which objects the final app retains.

The completed iOS link and distributed bundle still need inspection before claiming complete native binary coverage, including the DNG terms and retention qualification above. Package resolution does not prove successful app compilation, linking, or code retention. System frameworks imported by the helper—Security, Network, CryptoKit, and Foundation—are not copied into the app as third-party source packages.

## Packaging and maintenance

Canonical runtime texts live under `assets/licenses/runtime/`; byte-identical app resources live under `composeApp/src/commonMain/composeResources/files/licenses/runtime/`. `assets/tools/bundle_notices.py` consumes the runtime manifest alongside the font and other software manifests. The legal screen reads the entire `files/licenses/third_party_notices.txt` resource and does not have a hardcoded component count, exposing the bundled notices offline through Settings.

The completed [runtime bundling manifest](../assets/licenses/runtime/software_notice_sources.json) has 56 records: five distinct embedded notice texts, 27 additional upstream/source notices, 23 Skia component notices, and one generated acknowledgment text. There are 49 distinct text hashes and 295,998 bytes across the 56 canonical files. All 56 app-resource copies were verified against their manifest SHA-256 and canonical bytes. Only listed text resources are copied; the inventory, manifests, and Gradle reporting helper are not app resources. Exact upstream bytes are retained, including upstream formatting; transformations of source comments are recorded explicitly.

The regenerated aggregate contains 64 total notice entries in 56 groups of identical text, retaining every component/title attribution. Its size is 258,067 bytes and SHA-256 is `d5c47822bd82a0f2b775b1f8c76863a4e5d5de7fbe6ca1aa1ad2713794a32066`. All 56 runtime texts and titles were independently checked against the aggregate after generation, with the required acknowledgments appearing first. The assets verifier also passes its 68 pinned source-file checks.

The release owner is independently inspecting the rebuilt APK/AAB/iOS legal resources. Final linked-product inventory and shipped-resource inclusion remain explicit qualification checks; the verified Swift lock closes dependency selection only. A source/POM review alone is not described as exhaustive binary compliance. After dependency upgrades, repeat Gradle and Xcode resolution, compare the locked source revisions, update native/source evidence and texts, run `python3 assets/tools/bundle_notices.py`, verify all hashes, and inspect the rebuilt packages before updating the release evidence.
