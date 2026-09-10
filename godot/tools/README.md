# Godot renderer packaging tools

`renderer.py` packages the real shared project in `godot/renderer`. One
`partydeck-last-light.pck` contains both presentations; the Kotlin launch
document selects `presentationMode: "2d"` or `"3d"`. It creates no game rules,
authoritative state, accepted intents, or fabricated match outcomes.

`prepare_assets.py` is maintained by the asset owner. Its source verification
and the Kotlin bridge/comparison scenarios remain separate checks.

## Install and validate

The packaging scripts require Python 3.10 or later and the official standard
Godot **4.7.2-stable** editor. No Python packages are needed by `renderer.py`.
The automatic installer supports Linux x86_64. Other desktop hosts can provide
the matching official editor with `--godot`; those hosts are not asserted to
have been executed by the Linux tooling audit.

```sh
python3 godot/tools/renderer.py install
python3 godot/tools/renderer.py validate \
  --godot godot/qualification/build/toolchain/godot
python3 godot/tools/renderer.py pack \
  --godot godot/qualification/build/toolchain/godot
python3 godot/tools/renderer.py check-pack \
  --pack godot/qualification/build/renderer/partydeck-last-light.pck
```

Every default path is derived from the script location, so `check-pack` also
works when Gradle invokes it from the isolated Android host project. Overrides
include `--project`, `pack --output`, and `install --destination`. The export
preset is renderer-owned and defaults to `Renderer pack`.

`install` verifies the release ZIP's SHA-256, SHA-512, size, single executable
member, executable SHA-256, and version output. It writes `install.receipt.json`
and downloads **no export templates**. A previously downloaded official ZIP
can be reused without weakening verification:

```sh
python3 godot/tools/renderer.py install \
  --archive /opt/partydeck-godot/downloads/Godot_v4.7.2-stable_linux.x86_64.zip
```

The inspected Linux editor dynamically requires the system loader, libc,
libm, libdl, libpthread, and librt. Headless import/export does not need a
display server. An interactive preview needs a desktop display and a working
graphics driver; the renderer selects GL Compatibility. GPU performance,
input, audio, and mobile lifecycle require their own execution evidence.

The separate asset preparation tool needs the pinned development packages in
`assets/tools/requirements.txt`. After preparing assets, its independent check
is:

```sh
python3 godot/tools/prepare_assets.py --check \
  --godot godot/qualification/build/toolchain/godot
```

## Artifacts and checks

Canonical outputs are:

- `godot/qualification/build/renderer/partydeck-last-light.pck`
- `godot/qualification/build/renderer/partydeck-last-light.receipt.json`
- `godot/qualification/build/renderer/pack-logs/commands.json` and command logs

Android asset staging copies only the PCK to the assets root, where its host
uses `--main-pack res://partydeck-last-light.pck`. Keep the receipt as a build
artifact for verification. The standalone `check-pack` command requires only
Python, the PCK/receipt, and the matching source checkout; it does not invoke
Godot or Gradle.

Validation imports a temporary project copy and loads/instantiates
`main.tscn`, `presentations/two_d/table.tscn`, and
`presentations/three_d/table.tscn` in the real engine. It does not add these
nodes to the tree or pretend to validate their interactive behavior. Godot
`ERROR`, `SCRIPT ERROR`, and shader-error diagnostics fail the command even
when the engine exits zero. The actual Kotlin authority/comparison harness
owns behavior and acceptance checks.

Export repeats that validation and derives a staged copy of the named preset
with a sorted explicit list of runtime inputs. Godot's `resources` export mode
retains this order. The wildcard include/exclude filters are empty because
staging has already removed excluded files; their unsorted directory scans
otherwise change payload order. The source preset and its other options remain
unchanged. Raw `.import`/`.uid` sidecars and project/preset configuration are
omitted from the explicit list; Godot still generates the required imported
resources and exported project settings. The receipt records the selected
paths and original/derived preset hashes. The supplied preset is preserved at
`pack-logs/export_presets.cfg`.

The tool then runs the real `--export-pack`, verifies each PCK entry's embedded
checksum and SHA-256, and loads/instantiates the same scenes from the pack in
an empty project directory. Loose source files cannot mask a missing packed
scene in that check. Only after these steps and a second source fingerprint
check are the native pack bytes and successful receipt promoted.

Staging excludes generated caches/build directories, tests, checks, fixtures,
`assets/proofs/`, `assets/sources/`, `.gdignore` subtrees, signing/key files,
`.env` files, and export credentials. It retains resource `.uid` and `.import`
sidecars. The receipt lists exact included and excluded source paths. The PCK
must include both presentation scenes, project settings, `assets/manifest.json`,
all font/Godot notices, and every file under a `licenses/` directory with
unchanged bytes. Export-generated `.godot` resources inside the PCK are normal
runtime inputs; source `.godot` caches are never copied into staging.

The receipt records source/tool hashes, commands, log hashes, editor identity,
entry hashes, and PCK SHA-256. `check-pack` recomputes the explicit export plan
and rejects corruption, missing notices/scenes, missing successful scene
checks, a changed plan, or a source/tool fingerprint change. It is suitable for
Android's fail-fast generated-assets task. Receipts and logs contain local
command paths but no copied launch-document bodies.
All generated artifacts live in ignored `build/` directories.
See the [environment review](../reviews/environment-review.md) and
[release review](../reviews/release-review.md) for independent execution
evidence and the scope of each check.

On 2026-09-10, two isolated exports using the pinned Linux editor produced the
same native PCK bytes: 136 entries, 1,542,328 bytes, SHA-256
`26bfbb72efa55b63bef2e0ab989c82356c75b3bb3ca40bcf1c5e70e931bff890`.
Both packed desktop presentations reached Ready using Xvfb, Mesa llvmpipe,
and Dummy audio. The reviews retain the input fingerprint, receipt hashes,
binary inspection, and rejection-probe evidence.

Retain the existing scene node `unique_id` fields when editing scenes. Godot's
export repacking assigns randomized IDs to nodes without one, so exports from
otherwise identical inputs can differ in their binary scene contents. The
checked-in root IDs came from the first verified engine export.

## Separate desktop previews

Generate real fixtures through the existing Kotlin bridge task:

```sh
flock /tmp/partydeck-gradle.lock ./gradlew -p godot/qualification :bridge:generateFixtures
```

Then open either presentation, using the corresponding fixture unchanged:

```sh
python3 godot/tools/renderer.py preview \
  --godot godot/qualification/build/toolchain/godot \
  --pack godot/qualification/build/renderer/partydeck-last-light.pck \
  --presentation 2d --launch-file godot/bridge/fixtures/launch-2d.json

python3 godot/tools/renderer.py preview \
  --godot godot/qualification/build/toolchain/godot \
  --pack godot/qualification/build/renderer/partydeck-last-light.pck \
  --presentation 3d --launch-file godot/bridge/fixtures/launch-3d.json
```

Omit `--pack` to import and preview a temporary copy of current sources. Add
`--headless --quit-after 10 --timeout 30` for a bounded startup check; this does
not qualify rendered appearance or a complete match. A mode mismatch fails
before launch. The tool passes the renderer's actual `--presentation=...` and
`--launch-file=...` user arguments and records the fixture hash. It does not
rewrite the launch document. For interactive authoritative input and scenario
capture, use the [JVM comparison runner](../comparison/README.md) and its
`--manual-bridge` driver.

A successful preview receipt requires the renderer's actual standalone Ready
event and no Failed event. Ready confirms initialization only; it is never
recorded as accepted gameplay or a successful match.

For a bounded graphical startup check on a Linux host with Xvfb and no audio
device, select Godot's real `Dummy` audio driver explicitly:

```sh
xvfb-run -a python3 godot/tools/renderer.py preview \
  --godot godot/qualification/build/toolchain/godot \
  --pack godot/qualification/build/renderer/partydeck-last-light.pck \
  --presentation 3d --launch-file godot/bridge/fixtures/launch-3d.json \
  --audio-driver Dummy --quit-after 10 --timeout 45
```

This exercises the graphical renderer with physical audio output disabled.
The default audio backend remains appropriate on a desktop with audio hardware.
A backend error fails the preview even if Godot falls back and reaches Ready.
Preview receipts record the source fingerprint, optional PCK hash, launch hash,
headless/audio-driver options, and actual commands. A failed new preview clears
the previous success receipt before replacing its logs.

## Authoritative references

Checked against the pinned 4.7.2-stable release:

- [Official 4.7.2 release](https://github.com/godotengine/godot/releases/tag/4.7.2-stable)
  and its [SHA512-SUMS](https://github.com/godotengine/godot/releases/download/4.7.2-stable/SHA512-SUMS.txt).
  Exact archive/executable pins are in `godot-pins.json`. The Linux ZIP is
  77,860,424 bytes; the unneeded template archive is 1,281,349,702 bytes.
- [EditorNode export routing](https://github.com/godotengine/godot/blob/4.7.2-stable/editor/editor_node.cpp)
  selects `export_pack` for `pack_only` before the normal application's
  `can_export`/template checks.
- [EditorExportPlatform](https://github.com/godotengine/godot/blob/4.7.2-stable/editor/export/editor_export_platform.cpp)
  writes project data through `save_pack`, including its v4 header/directory.
- [EditorExport preset loading](https://github.com/godotengine/godot/blob/4.7.2-stable/editor/export/editor_export.cpp)
  maps `export_filter="resources"` to selected resources and loads explicit
  `export_files`.
  [EditorExportPreset](https://github.com/godotengine/godot/blob/4.7.2-stable/editor/export/editor_export_preset.cpp)
  and [HashSet](https://github.com/godotengine/godot/blob/4.7.2-stable/core/templates/hash_set.h)
  retain their insertion order. Wildcard filter scans use unsorted `DirAccess`
  iteration, and removals swap the last set entry; the staged preset avoids
  both sources of ordering variation.
- [Pack format constants](https://github.com/godotengine/godot/blob/4.7.2-stable/core/io/file_access_pack.h)
  and [pack reader](https://github.com/godotengine/godot/blob/4.7.2-stable/core/io/file_access_pack.cpp)
  establish the v4 layout checked by `partydeck_pck.py`. The inspector accepts
  standalone unencrypted, non-sparse, non-patch 4.7.2 exports only.
- [CLI implementation/help](https://github.com/godotengine/godot/blob/4.7.2-stable/main/main.cpp)
  documents `--import`, `--export-pack`, `--main-pack`, and `--quit-after`.
- [ResourceLoader](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/ResourceLoader.xml)
  and [PackedScene](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/PackedScene.xml)
  define the structural checks. Their success is not a substitute for running
  either presentation or validating native embedding.
- [Packed scene serialization](https://github.com/godotengine/godot/blob/4.7.2-stable/scene/resources/packed_scene.cpp)
  assigns missing node IDs in `SceneState::_parse_node` through
  [ResourceUID's random generator](https://github.com/godotengine/godot/blob/4.7.2-stable/core/io/resource_uid.cpp).
  Independent read-only inspection of both initial exports confirmed that only
  the three generated root node IDs differed before they were persisted.
