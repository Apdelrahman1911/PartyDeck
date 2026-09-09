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

# This builds the real SwiftUI app and runs PartyDeckUITests. Its Xcode build phase
# calls embedAndSignAppleFrameworkForXcode in the environment that task requires.
xcodebuild test \
  -project iosApp/PartyDeck.xcodeproj \
  -scheme PartyDeck \
  -configuration Debug \
  -destination "platform=iOS Simulator,id=$PARTYDECK_SIMULATOR_ID" \
  -derivedDataPath "$PARTYDECK_IOS_OUTPUT/DerivedData" \
  -clonedSourcePackagesDirPath "$PARTYDECK_IOS_OUTPUT/SourcePackages" \
  -resultBundlePath "$PARTYDECK_IOS_OUTPUT/PartyDeck.xcresult" \
  CODE_SIGNING_ALLOWED=NO \
  2>&1 | tee "$PARTYDECK_IOS_OUTPUT/xcodebuild.log"

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

# Compile the actual Swift application for a physical-device architecture too.
# This catches device-only camera/native bridge code without a signing identity.
xcodebuild build \
  -project iosApp/PartyDeck.xcodeproj \
  -scheme PartyDeck \
  -configuration Debug \
  -sdk iphoneos \
  -destination 'generic/platform=iOS' \
  -derivedDataPath "$PARTYDECK_IOS_OUTPUT/DeviceDerivedData" \
  -clonedSourcePackagesDirPath "$PARTYDECK_IOS_OUTPUT/SourcePackages" \
  CODE_SIGNING_ALLOWED=NO \
  2>&1 | tee "$PARTYDECK_IOS_OUTPUT/xcodebuild-device.log"

PARTYDECK_DEVICE_APP="$PARTYDECK_IOS_OUTPUT/DeviceDerivedData/Build/Products/Debug-iphoneos/PartyDeck.app"
test -d "$PARTYDECK_DEVICE_APP"
tar -czf "$PARTYDECK_IOS_OUTPUT/PartyDeck-device-unsigned.app.tar.gz" \
  -C "$(dirname -- "$PARTYDECK_DEVICE_APP")" PartyDeck.app
