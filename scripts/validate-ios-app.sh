#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != Darwin ]]; then
  printf '%s\n' 'iOS application validation requires macOS with Xcode; use the Validate GitHub Actions workflow from Linux.' >&2
  exit 1
fi

PARTYDECK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARTYDECK_ROOT"
PARTYDECK_IOS_OUTPUT="$PARTYDECK_ROOT/build/ci/ios"
mkdir -p "$PARTYDECK_IOS_OUTPUT"

if [[ -e "$PARTYDECK_IOS_OUTPUT/PartyDeck.xcresult" ]]; then
  printf '%s\n' 'build/ci/ios/PartyDeck.xcresult already exists. Move or remove the previous result before another run.' >&2
  exit 1
fi

PARTYDECK_SIMULATOR_ID="$(python3 scripts/select-ios-simulator.py "$PARTYDECK_IOS_OUTPUT/simulator.json")"
xcrun simctl bootstatus "$PARTYDECK_SIMULATOR_ID" -b

# Keep installed command documentation as evidence. The required native test and
# Java exchange result below prove forwarding even if manual packaging changes.
xcodebuild -help > "$PARTYDECK_IOS_OUTPUT/xcodebuild-help.log" 2>&1 || true
MANPAGER='cat' man xcodebuild 2>&1 | col -b > "$PARTYDECK_IOS_OUTPUT/xcodebuild-man.log" || true

# Export a compiled test-only JVM peer, then launch Java outside Gradle so the
# Xcode Kotlin build phase can use Gradle independently. No fixture ships in apps.
./gradlew --stacktrace --console=plain :transport:exportInteropFixtureClasspath
python3 scripts/run-ios-interop-tests.py \
  --classpath transport/build/interop/jvm-test-classpath.txt \
  --output "$PARTYDECK_IOS_OUTPUT" \
  -- xcodebuild test \
  -project iosApp/PartyDeck.xcodeproj \
  -scheme PartyDeck \
  -configuration Debug \
  -destination "platform=iOS Simulator,id=$PARTYDECK_SIMULATOR_ID" \
  -derivedDataPath "$PARTYDECK_IOS_OUTPUT/DerivedData" \
  -clonedSourcePackagesDirPath "$PARTYDECK_IOS_OUTPUT/SourcePackages" \
  -resultBundlePath "$PARTYDECK_IOS_OUTPUT/PartyDeck.xcresult" \
  CODE_SIGNING_ALLOWED=NO \
  LD_GENERATE_MAP_FILE=YES

PARTYDECK_SIMULATOR_APP="$PARTYDECK_IOS_OUTPUT/DerivedData/Build/Products/Debug-iphonesimulator/PartyDeck.app"
test -d "$PARTYDECK_SIMULATOR_APP"
tar -czf "$PARTYDECK_IOS_OUTPUT/PartyDeck-simulator.app.tar.gz" \
  -C "$(dirname -- "$PARTYDECK_SIMULATOR_APP")" PartyDeck.app

# The UI tests attach screenshots only after their readiness assertions. Record
# the installed Xcode command help before exporting those verified test images.
xcrun xcresulttool export attachments --help > "$PARTYDECK_IOS_OUTPUT/xcresulttool-attachments-help.log"
xcrun xcresulttool export attachments \
  --path "$PARTYDECK_IOS_OUTPUT/PartyDeck.xcresult" \
  --output-path "$PARTYDECK_IOS_OUTPUT/attachments"

# After Debug XCTest passes, compile the optimized Swift/Kotlin device app too.
# This includes device-only scanner code and records final linker-map evidence.
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
