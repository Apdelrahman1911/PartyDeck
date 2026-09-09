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

# CI runs this after Debug XCTest succeeds and its evidence upload is attempted.
# Release includes optimized Kotlin/Swift and device-only scanner/native code.
xcodebuild build \
  -project iosApp/PartyDeck.xcodeproj \
  -scheme PartyDeck \
  -configuration Release \
  -sdk iphoneos \
  -destination 'generic/platform=iOS' \
  -derivedDataPath "$PARTYDECK_IOS_OUTPUT/DeviceDerivedData" \
  -clonedSourcePackagesDirPath "$PARTYDECK_IOS_OUTPUT/SourcePackages" \
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
tar -czf "$PARTYDECK_IOS_OUTPUT/PartyDeck-device-unsigned.app.tar.gz" \
  -C "$(dirname -- "$PARTYDECK_DEVICE_APP")" PartyDeck.app
