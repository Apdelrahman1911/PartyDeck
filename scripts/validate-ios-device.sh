#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != Darwin ]]; then
  printf '%s\n' 'Optimized iOS device compilation requires macOS with Xcode.' >&2
  exit 1
fi

PARTYDECK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARTYDECK_ROOT"
PARTYDECK_IOS_OUTPUT="$PARTYDECK_ROOT/build/ci/ios"
mkdir -p "$PARTYDECK_IOS_OUTPUT"

# Reuse explicitly supplied, receipt-checked native artifacts, or build this variant.
# The PCK must already be exported from the current shared renderer sources.
PARTYDECK_IOS_GODOT_PACK="${PARTYDECK_IOS_GODOT_PACK:-$PARTYDECK_ROOT/godot/qualification/build/renderer/partydeck-last-light.pck}"
python3 godot/tools/renderer.py check-pack --pack "$PARTYDECK_IOS_GODOT_PACK"
if [[ -z "${PARTYDECK_IOS_DEVICE_GODOT_ENGINE_ROOT:-}" ]]; then
  bash godot/ios-host/build-probe.sh engine device-release
  PARTYDECK_IOS_DEVICE_GODOT_ENGINE_ROOT="$PARTYDECK_ROOT/godot/ios-host/build/device-release"
fi
PARTYDECK_IOS_GODOT_LINK_MAP="$PARTYDECK_IOS_OUTPUT/PartyDeck-Release-iphoneos-LinkMap-arm64.txt"
PARTYDECK_IOS_ACTIVATION_ARGUMENTS=("PARTYDECK_APP_INFO_PLIST=$PARTYDECK_ROOT/iosApp/PartyDeck/Info.plist")
case "${PARTYDECK_IOS_GODOT_SESSION_SMOKE:-0}" in
  0) ;;
  1)
    python3 -B scripts/prepare-ios-godot-activation.py --modes 2d,3d \
      --output-plist "$PARTYDECK_IOS_OUTPUT/device-activation/Info.plist" \
      --expectation "$PARTYDECK_IOS_OUTPUT/device-activation/expectation.json"
    PARTYDECK_IOS_ACTIVATION_ARGUMENTS=(
      "PARTYDECK_APP_INFO_PLIST=$PARTYDECK_IOS_OUTPUT/device-activation/Info.plist"
      "PARTYDECK_GODOT_ACTIVATION_EXPECTATION=$PARTYDECK_IOS_OUTPUT/device-activation/expectation.json"
    )
    ;;
  *) printf '%s\n' 'PARTYDECK_IOS_GODOT_SESSION_SMOKE must be 0 or 1.' >&2; exit 1 ;;
esac

# CI runs this in parallel with Simulator validation after the shared pack is ready.
# Release includes optimized Kotlin/Swift and device-only scanner/native code.
xcodebuild build \
  -project iosApp/PartyDeck.xcodeproj \
  -scheme PartyDeck \
  -configuration Release \
  -sdk iphoneos \
  -destination 'generic/platform=iOS' \
  -derivedDataPath "$PARTYDECK_IOS_OUTPUT/DeviceDerivedData" \
  -clonedSourcePackagesDirPath "$PARTYDECK_IOS_OUTPUT/SourcePackages" \
  PARTYDECK_GODOT_ENGINE_ROOT="$PARTYDECK_IOS_DEVICE_GODOT_ENGINE_ROOT" \
  PARTYDECK_GODOT_PACK="$PARTYDECK_IOS_GODOT_PACK" \
  PARTYDECK_GODOT_LINK_MAP="$PARTYDECK_IOS_GODOT_LINK_MAP" \
  "${PARTYDECK_IOS_ACTIVATION_ARGUMENTS[@]}" \
  CODE_SIGNING_ALLOWED=NO \
  LD_GENERATE_MAP_FILE=YES \
  2>&1 | tee "$PARTYDECK_IOS_OUTPUT/xcodebuild-device.log"

python3 - "$PARTYDECK_IOS_OUTPUT/xcodebuild-device.log" <<'PY'
from pathlib import Path
import sys
if ":composeApp:linkReleaseFrameworkIosArm64" not in Path(sys.argv[1]).read_text():
    raise RuntimeError("The Release device app build did not report its optimized Kotlin framework task.")
PY
PARTYDECK_DEVICE_APP="$PARTYDECK_IOS_OUTPUT/DeviceDerivedData/Build/Products/Release-iphoneos/PartyDeck.app"
test -d "$PARTYDECK_DEVICE_APP"
python3 scripts/prepare-ios-godot.py verify-app \
  --app "$PARTYDECK_DEVICE_APP" \
  --inputs "$PARTYDECK_IOS_OUTPUT/DeviceDerivedData/Build/Products/Release-iphoneos/PartyDeckGodotInputs/inputs.json" \
  --link-map "$PARTYDECK_IOS_GODOT_LINK_MAP" \
  --output "$PARTYDECK_IOS_OUTPUT/godot-production-link-Release-iphoneos.json"
tar -czf "$PARTYDECK_IOS_OUTPUT/PartyDeck-device-unsigned.app.tar.gz" \
  -C "$(dirname -- "$PARTYDECK_DEVICE_APP")" PartyDeck.app
