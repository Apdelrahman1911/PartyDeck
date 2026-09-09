# Toolchain evidence and independent environment review

Research date: 2026-09-09. Sources below were fetched directly from the official
documentation, release APIs, and artifact repositories. This document distinguishes
documented compatibility from builds actually executed by the independent reviewer.

## Selected versions

| Component | PartyDeck selection | Evidence and reason |
| --- | --- | --- |
| Kotlin Multiplatform, serialization compiler plugin, Compose compiler plugin | **2.4.20** | Kotlin's latest stable release, published 2026-09-07. The Compose compiler plugin must match Kotlin. [1][2][3] |
| Compose Multiplatform | **1.12.0** | Latest stable release, published 2026-08-25. Official documentation says latest stable Compose supports latest stable Kotlin. [3][4] |
| Gradle wrapper | **9.7.0** | Within Kotlin 2.4.20's documented 7.6.3–9.7.0 range and above AGP 9.3's 9.5.0 minimum. The current Gradle release is 9.7.1; selecting 9.7.0 preserves the explicitly documented intersection. [1][5][6] |
| Android Gradle Plugin | **9.3.1** | Kotlin 2.4.20 documents AGP 8.5.2–9.3.1 compatibility. Google's Maven metadata confirms 9.3.1 is published. Newer stable 9.3.2 and 9.4.0 exist but exceed that table's tested ceiling. [1][5][7] |
| Gradle runtime JDK | **21**; installed Ubuntu **21.0.12+8-1-24.04** | Gradle 9.7.0 supports Java 17–26; AGP 9.3 requires at least 17. AGP 9.3.2 notes a JDK 17 lint crash fixed after 9.3.1, making JDK 21 the sensible runtime for this pin. [5][8] |
| Android compileSdk / targetSdk | **36 / 36** | Stable SDK 36 is published. Google Play requires new phone apps and updates to target at least 36 from 2026-08-31. SDK 37 exists, but this first release deliberately targets 36 while its networking behavior is qualified. [9][10] |
| Android SDK Build Tools | **36.0.0** | AGP 9.3's documented minimum and default; published in the stable SDK channel. [5][9] |
| Android command-line tools | Installed **19.0**, archive **13114758** | Official repository confirms this stable archive. Latest stable is 23.0 / 16111833, but updating a working SDK 36 bootstrap is unnecessary. [9] |
| Xcode for iOS CI | **26.4.1**, iOS SDK **26.4** | Kotlin documents Xcode 26.4 compatibility. GitHub's macOS 26 ARM64 image supplies Xcode 26.4.1 and its 26.4 SDK. Apple requires macOS 26.2 or later for this Xcode. [1][11][12] |
| iOS deployment target | **15.0 minimum** | Current Kotlin/Native defaults to iOS 15; Xcode 26.4.1 supports deployment targets 15–26.4. Compose alone lists iOS 14, which is not the complete toolchain floor. [3][11][13] |

The current Temurin 21 distribution is **21.0.12.1+1** according to Adoptium's API.
PartyDeck uses the already installed supported Ubuntu OpenJDK 21 distribution;
these are separate vendor build numbers, not an assertion that Ubuntu's patch
number equals Temurin's. [14]

The official Gradle 9.7.0 binary distribution SHA-256 is:

```text
84fbba45c7f4c64abc77460e1c00f541e9f960e3c7ed2538f1ede19eacd873ae
```

Source: [Gradle distribution checksum][15]. Pin this in the wrapper properties.

## Configuration constraints that affect implementation

- Use `org.jetbrains.kotlin.multiplatform` with Google's
  `com.android.kotlin.multiplatform.library` in shared modules. Google directs
  Android applications into a separate `com.android.application` module. The old
  KMP + `com.android.library` integration depends on deprecated AGP APIs. [16]
- The Android KMP plugin configures its Android target inside `kotlin { android { ... } }`.
  It has one variant, and host/device tests are disabled until explicitly enabled.
  Its minimum versions are AGP 8.10.0 and Kotlin 2.0.0. [16]
- Apply `org.jetbrains.kotlin.plugin.compose` at version 2.4.20 anywhere Compose
  compilation is needed. Do not infer the compiler version from Compose's 1.12.0
  runtime version. [3]
- Compose 1.12.0's release table includes **Material3 1.12.0-alpha03** and
  **Navigation 2.10.0-alpha02**. The core framework's stable status does not make
  these components stable. UI/navigation owners must verify and pin stable
  component releases independently. [4]
- Use `iosArm64()` and `iosSimulatorArm64()`: both are Kotlin/Native Tier 1.
  Apple targets require a macOS host. `iosX64()` is Tier 3 and is unnecessary for
  the selected ARM64 CI runner. [13]
- GitHub documents **`macos-26` as ARM64**, with `macos-26-intel` as the separate
  Intel label. Select `DEVELOPER_DIR=/Applications/Xcode_26.4.1.app/Contents/Developer`;
  the image's default Xcode is currently 26.6. The runner inventory is evidence
  of tool availability, not proof that PartyDeck's iOS build has passed. [12][17]
- A Compose/KMP Android application does not need a separately installed Kotlin
  CLI for its Gradle compilation. A project NDK/native build is only warranted
  if an actual native integration requires it; AGP lists its NDK minimum as N/A. [5]

## Bootstrap and verification status

- Independently executed `java -version`: **passed**, reporting OpenJDK
  `21.0.12+8-1-24.04-Ubuntu` on Linux.
- Coordinator reports that the initial JDK apt installation failed because
  `/usr/share/man/man1` was missing; creating that directory and rerunning dpkg
  configuration resolved it. This installation incident is reported history,
  not an independently reproduced failure.
- Android SDK installation and project bootstrap were still in progress when
  this research record was written. Independent Kotlin/KMP, Compose, Android,
  and selected networking smoke tests will be recorded after the coordinator
  makes that milestone available.
- iOS compilation and simulator execution require the macOS workflow. Physical
  device behavior, signing, and distribution must be qualified separately from
  a successful unsigned simulator build.

## Authoritative sources

[1]: https://kotlinlang.org/docs/multiplatform/multiplatform-compatibility-guide.html
[2]: https://github.com/JetBrains/kotlin/releases/tag/v2.4.20
[3]: https://kotlinlang.org/docs/multiplatform/compose-compatibility-and-versioning.html
[4]: https://github.com/JetBrains/compose-multiplatform/releases/tag/v1.12.0
[5]: https://developer.android.com/build/releases/agp-9-3-0-release-notes
[6]: https://services.gradle.org/versions/current
[7]: https://dl.google.com/dl/android/maven2/com/android/tools/build/gradle/maven-metadata.xml
[8]: https://docs.gradle.org/9.7.0/userguide/compatibility.html
[9]: https://dl.google.com/android/repository/repository2-3.xml
[10]: https://support.google.com/googleplay/android-developer/answer/11926878?hl=en
[11]: https://developer.apple.com/xcode/system-requirements
[12]: https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md
[13]: https://kotlinlang.org/docs/native-target-support.html
[14]: https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture=x64&image_type=jdk&os=linux&vendor=eclipse
[15]: https://services.gradle.org/distributions/gradle-9.7.0-bin.zip.sha256
[16]: https://developer.android.com/kotlin/multiplatform/plugin
[17]: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
