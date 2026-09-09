# Independent Godot environment review

Reviewed on 2026-09-09. Installation and isolated build configuration pass the
checks below. Renderer import/export, actual bridge/comparison compilation,
Android packaging, and native execution remain pending their owners' completed
artifacts. This review does not qualify a playable renderer or KMP embedding.

## Independently executed checks

| Check | Result and evidence |
| --- | --- |
| Official Linux engine | Release `4.7.2-stable`, published `2026-08-18T15:56:46Z`, checked against the official release API and published checksums. The installed binary matches the verified archive member. |
| Actual CLI | `/opt/partydeck-godot/godot --version` returned `4.7.2.stable.official.ed1daf0bf`. `--help` and the versioned command-line documentation agree on import and pack semantics. |
| Gradle configuration/output isolation | A scratch init script inspected the configured build directories of all six projects. `help` completed successfully in 19 seconds. Root outputs are under `godot/qualification/build`; `androidHost`, `bridge`, `comparison`, `core`, and `games` each use `build/modules/<name>`. |
| Official Android AAR | The actual `org.godotengine:godot:4.7.2.stable` AAR is 103,251,267 bytes and matches the SHA-256 in the published Gradle module metadata. |
| iOS upstream pin | The official GitHub tag independently resolves to `ed1daf0bf001b61586d9930840f2f1394092c079`. The source audit was rerun against that checkout with clean tracked sources and passed. |
| iOS build dependency | The actual `scons-4.11.1-py3-none-any.whl` was downloaded and its 4,123,659 bytes independently hashed against PyPI metadata and `requirements.txt`. |
| iOS cache action | Official `actions/cache` tag `v6.1.0` resolves to the pinned commit `55cc8345863c7cc4c66a329aec7e433d2d1c52a9`; its action definition supports the configured path/key/restore-key inputs. |

The exact Gradle command was:

```sh
flock -w 120 /tmp/partydeck-gradle.lock ./gradlew \
  -p godot/qualification --no-daemon --console=plain \
  --init-script /tmp/partydeck-godot-environment-review/output-layout.init.gradle help
```

The existing `core`/`games` warnings about disabled Android host tests were
reported without suppression. This configuration check does not establish that
their tests, the new bridge, or either host compiles.

### Verified hashes

| Artifact | SHA-256 |
| --- | --- |
| Official Linux ZIP | `cadd3204e728a35d3f13adb7fd0d7902636b79f6b95c40c265eb73b6c35329e4` |
| Official `SHA512-SUMS.txt` | `b8bdff6704f833e7a021df16ec08e1478edd5a285c1f894929b91a7f74a5c7c0` |
| Installed Linux executable | `8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e` |
| Official Android AAR | `8791eecfe7c96a4de2d188a0bccfe9b83b92589a5a6825847473416a990e8629` |
| SCons wheel | `454cef364348053422696e3d2ecb4fa593c96a624f955842eaaea64f95c8d11d` |

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
current renderer sources each time. The verifier implementation and actual
packaging have not been reviewed yet: `godot/tools/renderer.py` was not present
at this checkpoint. The manual comparison workflow is accepted as build/test/pack
scaffolding; it does not yet claim desktop or native runtime qualification.

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

The engine stage is accepted for CI compilation. A static archive does not
establish that a native application links or renders. The current `nm` guard
matches symbol substrings, including undefined references; checking definitions
was sent to the owner as a nonblocking improvement. No native link or execution
success is inferred from that guard.

## Export and execution boundaries

No export templates are installed in the verified local toolchain. Godot's
`--export-pack` exports data only and implies resource import; a successful PCK
export would not establish standalone/mobile export or launch. `--headless`
selects the headless display and Dummy audio drivers. `--quit-after` counts
iterations, so execution deadlines must use a process timeout.

The reviewer is waiting for source/import readiness notices before importing the
shared renderer or compiling owners' work. No redundant local emulator run was
performed. Actual import, PCK freshness/contents/size/hash, JVM tests,
Android packaging, and the macOS engine-stage result will be recorded after
execution.

## Evidence and authoritative sources

Scratch evidence is under `/tmp/partydeck-godot-environment-review/`:
`toolchain-verification.json`, `godot-version.log`, `godot-help.log`,
`gradle-output-layout.json`, `ios-upstream-audit.json`,
`ios-upstream-tag-verification.json`, and `ios-scons-verification.json`.

- [Official engine release](https://github.com/godotengine/godot-builds/releases/tag/4.7.2-stable)
- [Versioned command-line reference](https://docs.godotengine.org/en/4.7/tutorials/editor/command_line_tutorial.html)
- [Exact Android module metadata](https://repo.maven.apache.org/maven2/org/godotengine/godot/4.7.2.stable/godot-4.7.2.stable.module)
- [Exact Android POM](https://repo.maven.apache.org/maven2/org/godotengine/godot/4.7.2.stable/godot-4.7.2.stable.pom)
- [Pinned upstream iOS source](https://github.com/godotengine/godot/tree/ed1daf0bf001b61586d9930840f2f1394092c079/platform/ios)
- [Pinned upstream controller declaration](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/apple_embedded/godot_view_controller.h)
- [SCons wheel metadata](https://pypi.org/pypi/scons/4.11.1/json)
- [Pinned cache action](https://github.com/actions/cache/blob/55cc8345863c7cc4c66a329aec7e433d2d1c52a9/action.yml)
