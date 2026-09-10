#!/usr/bin/env bash
set -euo pipefail

PARTYDECK_PROBE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PARTYDECK_PROBE_BASE_BUILD="$PARTYDECK_PROBE_ROOT/build"
PARTYDECK_PROBE_REFERENCE="$PARTYDECK_PROBE_BASE_BUILD/upstream"
PARTYDECK_PROBE_STAGE="${1:-engine}"
PARTYDECK_PROBE_VARIANT="${2:-simulator-debug}"
case "$PARTYDECK_PROBE_VARIANT" in
  simulator-debug)
    PARTYDECK_PROBE_BUILD="$PARTYDECK_PROBE_BASE_BUILD"
    PARTYDECK_PROBE_SDK=iphonesimulator
    PARTYDECK_PROBE_CONFIGURATION=Debug
    PARTYDECK_PROBE_TARGET=template_debug
    PARTYDECK_PROBE_SIMULATOR=yes
    ;;
  device-release)
    PARTYDECK_PROBE_BUILD="$PARTYDECK_PROBE_BASE_BUILD/device-release"
    PARTYDECK_PROBE_SDK=iphoneos
    PARTYDECK_PROBE_CONFIGURATION=Release
    PARTYDECK_PROBE_TARGET=template_release
    PARTYDECK_PROBE_SIMULATOR=no
    ;;
  *) printf '%s\n' 'Expected simulator-debug or device-release native inputs.' >&2; exit 2 ;;
esac
PARTYDECK_PROBE_EVIDENCE="$PARTYDECK_PROBE_BUILD/evidence"
PARTYDECK_PROBE_ARTIFACTS="$PARTYDECK_PROBE_BUILD/artifacts"

case "$PARTYDECK_PROBE_STAGE" in
  source|engine|test) ;;
  *) printf '%s\n' 'Usage: build-probe.sh source|engine|test [simulator-debug|device-release]' >&2; exit 2 ;;
esac

if [[ "$PARTYDECK_PROBE_STAGE" == test && "$PARTYDECK_PROBE_VARIANT" != simulator-debug ]]; then
  printf '%s\n' 'The native probe XCTest targets currently execute on Simulator only.' >&2
  exit 2
fi

mkdir -p "$PARTYDECK_PROBE_EVIDENCE" "$PARTYDECK_PROBE_ARTIFACTS"
# Serialize invocations that share the upstream reference; parallel variants use
# separate checkouts/runners. Their artifacts, evidence and caches stay separate.
if ! mkdir "$PARTYDECK_PROBE_BASE_BUILD/.build-probe-lock"; then
  printf '%s\n' 'Another probe build owns the evidence/artifact paths, or its lock needs inspection.' >&2
  exit 1
fi
trap 'rmdir "$PARTYDECK_PROBE_BASE_BUILD/.build-probe-lock"' EXIT
PARTYDECK_GODOT_TAG="$(python3 "$PARTYDECK_PROBE_ROOT/source_audit.py" --pin tag)"
PARTYDECK_GODOT_COMMIT="$(python3 "$PARTYDECK_PROBE_ROOT/source_audit.py" --pin commit)"
PARTYDECK_GODOT_REPOSITORY="$(python3 "$PARTYDECK_PROBE_ROOT/source_audit.py" --pin repository)"

if [[ ! -d "$PARTYDECK_PROBE_REFERENCE/.git" ]]; then
  if [[ -e "$PARTYDECK_PROBE_REFERENCE" ]]; then
    printf '%s\n' 'The probe source path exists without its expected Git metadata.' >&2
    exit 1
  fi
  git clone --depth 1 --branch "$PARTYDECK_GODOT_TAG" \
    "$PARTYDECK_GODOT_REPOSITORY" "$PARTYDECK_PROBE_REFERENCE" \
    2>&1 | tee "$PARTYDECK_PROBE_EVIDENCE/source-download.log"
fi

python3 "$PARTYDECK_PROBE_ROOT/source_audit.py" \
  --source "$PARTYDECK_PROBE_REFERENCE" --require-pristine \
  --output "$PARTYDECK_PROBE_EVIDENCE/upstream-reference-audit.json"

# Keep the cached upstream reference read-only. Every invocation gets a fresh
# checkout, including source-only audits; ignored custom.py or *.gen.mm from an
# earlier compilation can never become an input to this build.
mkdir -p "$PARTYDECK_PROBE_BUILD/engine-checkouts"
PARTYDECK_PROBE_SOURCE="$(mktemp -d "$PARTYDECK_PROBE_BUILD/engine-checkouts/engine.XXXXXX")"
git clone --shared --no-checkout --quiet "$PARTYDECK_PROBE_REFERENCE" "$PARTYDECK_PROBE_SOURCE"
git -c core.autocrlf=false -C "$PARTYDECK_PROBE_SOURCE" checkout --quiet --detach "$PARTYDECK_GODOT_COMMIT"
python3 "$PARTYDECK_PROBE_ROOT/source_audit.py" \
  --source "$PARTYDECK_PROBE_SOURCE" \
  --apply-patches --require-no-untracked \
  --output "$PARTYDECK_PROBE_EVIDENCE/upstream-audit.json"

PARTYDECK_PROBE_MODULES="$(python3 "$PARTYDECK_PROBE_ROOT/stage-engine-inputs.py" \
  --modules "$PARTYDECK_PROBE_ROOT/modules" \
  --snapshots "$PARTYDECK_PROBE_BUILD/module-snapshots" \
  --output "$PARTYDECK_PROBE_EVIDENCE/native-module-inputs.json")"

if [[ "$PARTYDECK_PROBE_STAGE" == source ]]; then
  exit 0
fi

if [[ "$(uname -s)" != Darwin ]]; then
  printf '%s\n' 'The real iOS engine probe requires macOS and Xcode. The source audit can run on Linux.' >&2
  exit 1
fi

export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode_26.4.1.app/Contents/Developer}"
xcodebuild -version | tee "$PARTYDECK_PROBE_EVIDENCE/xcode-version.log"
python3 - "$PARTYDECK_PROBE_EVIDENCE/xcode-version.log" <<'PY'
from pathlib import Path
import sys
if Path(sys.argv[1]).read_text().splitlines()[0] != "Xcode 26.4.1":
    raise SystemExit("This probe is pinned to Xcode 26.4.1.")
PY
xcodebuild -showsdks > "$PARTYDECK_PROBE_EVIDENCE/xcode-sdks.log"
xcrun --sdk "$PARTYDECK_PROBE_SDK" clang --version > "$PARTYDECK_PROBE_EVIDENCE/clang-version.log"
xcrun --sdk "$PARTYDECK_PROBE_SDK" --show-sdk-version > "$PARTYDECK_PROBE_EVIDENCE/sdk-version.log"

if [[ ! -x "$PARTYDECK_PROBE_BUILD/venv/bin/python" ]]; then
  python3 -m venv "$PARTYDECK_PROBE_BUILD/venv"
fi
PARTYDECK_PROBE_PYTHON="$PARTYDECK_PROBE_BUILD/venv/bin/python"
"$PARTYDECK_PROBE_PYTHON" -m pip install --require-hashes --only-binary=:all: \
  -r "$PARTYDECK_PROBE_ROOT/requirements.txt"
"$PARTYDECK_PROBE_PYTHON" -m SCons --version > "$PARTYDECK_PROBE_EVIDENCE/scons-version.log"

# iOS's normal export-template build already produces a static archive.
# SConstruct explicitly rejects library_type=static_library/shared_library on iOS.
# Simulator drivers are limited to Compatibility by this exact upstream source.
# The owned host supplies its validated bundle paths through --path/--main-pack;
# export templates disable those arguments by default in this engine version.
(
  cd "$PARTYDECK_PROBE_SOURCE"
  PYTHONDONTWRITEBYTECODE=1 "$PARTYDECK_PROBE_PYTHON" -m SCons \
    platform=ios target="$PARTYDECK_PROBE_TARGET" arch=arm64 simulator="$PARTYDECK_PROBE_SIMULATOR" \
    vulkan=no metal=no opengl3=yes sdl=no lto=none generate_bundle=no disable_path_overrides=no \
    custom_modules="$PARTYDECK_PROBE_MODULES" redirect_build_objects=yes \
    cache_path="$PARTYDECK_PROBE_BUILD/scons-cache" \
    -j2
) 2>&1 | tee "$PARTYDECK_PROBE_EVIDENCE/engine-build.log"

python3 "$PARTYDECK_PROBE_ROOT/stage-engine-inputs.py" \
  --verify "$PARTYDECK_PROBE_EVIDENCE/native-module-inputs.json"
python3 "$PARTYDECK_PROBE_ROOT/source_audit.py" \
  --source "$PARTYDECK_PROBE_SOURCE" \
  --output "$PARTYDECK_PROBE_EVIDENCE/upstream-postbuild-audit.json"

"$PARTYDECK_PROBE_PYTHON" - "$PARTYDECK_PROBE_SOURCE" "$PARTYDECK_PROBE_ARTIFACTS" "$PARTYDECK_PROBE_EVIDENCE" "$PARTYDECK_GODOT_COMMIT" \
  "$PARTYDECK_PROBE_TARGET" "$PARTYDECK_PROBE_SIMULATOR" "$PARTYDECK_PROBE_SDK" "$PARTYDECK_PROBE_CONFIGURATION" <<'PY'
import hashlib
import json
from pathlib import Path
import shutil
import sys

source, artifacts, evidence = map(Path, sys.argv[1:4])
target, simulator_flag, sdk, configuration = sys.argv[5:9]
simulator = simulator_flag == "yes"
suffix = ".simulator" if simulator else ""
inputs = json.loads((evidence / "native-module-inputs.json").read_text())
before = json.loads((evidence / "upstream-audit.json").read_text())
after = json.loads((evidence / "upstream-postbuild-audit.json").read_text())
if before["sources"] != after["sources"] or before["upstream_patches"] != after["upstream_patches"]:
    raise SystemExit("The audited engine sources changed during compilation.")
archives = [p for p in (source / "bin").glob("libgodot.ios.*.a")
            if p.name == f"libgodot.ios.{target}.arm64{suffix}.a"]
if len(archives) != 1:
    raise SystemExit(f"Expected the {configuration}/{sdk} engine archive, found {[p.name for p in archives]}")
destination = artifacts / "libpartydeck_godot_ios_probe.a"
shutil.copy2(archives[0], destination)

def receipt(path):
    digest = hashlib.sha256()
    with path.open("rb") as archive:
        for block in iter(lambda: archive.read(1024 * 1024), b""):
            digest.update(block)
    return {"artifact": path.name, "sha256": digest.hexdigest(), "bytes": path.stat().st_size}

camera = [p for p in (source / "bin").glob("libgodot_camera.ios.*.a")
          if p.name == f"libgodot_camera.ios.{target}.arm64{suffix}.a"]
if len(camera) != 1:
    raise SystemExit(f"Expected one auxiliary camera archive, found {[p.name for p in camera]}")
camera_destination = artifacts / "libpartydeck_godot_camera.a"
shutil.copy2(camera[0], camera_destination)
result = {
    "engine_commit": sys.argv[4],
    "upstream_archive": archives[0].name,
    **receipt(destination),
    "auxiliary_archives": [{**receipt(camera_destination), "upstream_archive": camera[0].name}],
    "stage": "engine_compile_only",
    "platform": "ios",
    "target": target,
    "configuration": configuration,
    "simulator": simulator,
    "architecture": "arm64",
    "sdk": sdk,
    "sdk_version": (evidence / "sdk-version.log").read_text().strip(),
    "lto": "none",
    "xcode_version": "26.4.1",
    "rendering_drivers": ["opengl3"],
    "path_overrides_enabled": True,
    "bootstrap_arguments": "native_owned_bundle_paths",
    "sdl_enabled": False,
    "native_input_scope": "touch_and_hardware_keyboard",
    "upstream_patches": before["upstream_patches"],
    "native_module_sources": inputs["native_module_sources"],
    "module_snapshot_sha256": inputs["module_snapshot_sha256"],
    "native_module_capture_phase": inputs["capture_phase"],
    "engine_checkout_policy": "fresh_isolated_checkout",
    "ios_runtime_executed": False,
    "kmp_factory_qualified": False,
}
(evidence / "engine-artifact.json").write_text(json.dumps(result, indent=2) + "\n")
PY

xcrun nm -g "$PARTYDECK_PROBE_ARTIFACTS/libpartydeck_godot_ios_probe.a" \
  > "$PARTYDECK_PROBE_EVIDENCE/engine-symbols.log"
python3 - "$PARTYDECK_PROBE_EVIDENCE/engine-symbols.log" <<'PY'
from pathlib import Path
import sys
symbols = Path(sys.argv[1]).read_text()
defined = {
    fields[-1] for line in symbols.splitlines()
    if len(fields := line.split()) >= 3 and fields[-2] in {"T", "S", "D", "B", "R"}
}
for required in ("__Z19apple_embedded_mainiPPc", "__Z21apple_embedded_finishv",
                 "_OBJC_CLASS_$_PDGodotHostViewController", "_OBJC_CLASS_$_PDGodotRuntime",
                 "_OBJC_CLASS_$_PDGodotEngineOwner", "_OBJC_CLASS_$_PDGodotPresentation",
                 "__Z39godot_apple_embedded_plugins_initializev",
                 "__Z41godot_apple_embedded_plugins_deinitializev"):
    if required not in defined:
        raise SystemExit(f"The compiled archive is missing a defined native probe symbol: {required}")
PY

if [[ "$PARTYDECK_PROBE_STAGE" == test ]]; then
  bash "$PARTYDECK_PROBE_ROOT/test-probe.sh"
fi
