#!/usr/bin/env bash
set -euo pipefail

PARTYDECK_AUTHORITY_HOST_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PARTYDECK_AUTHORITY_HOST_REPO="$(cd -- "$PARTYDECK_AUTHORITY_HOST_ROOT/../.." && pwd)"
PARTYDECK_AUTHORITY_HOST_BUILD="$PARTYDECK_AUTHORITY_HOST_ROOT/build"
PARTYDECK_AUTHORITY_HOST_EVIDENCE="$PARTYDECK_AUTHORITY_HOST_BUILD/evidence"
PARTYDECK_AUTHORITY_HOST_ARTIFACTS="$PARTYDECK_AUTHORITY_HOST_BUILD/artifacts"
PARTYDECK_AUTHORITY_HOST_DERIVED="$PARTYDECK_AUTHORITY_HOST_BUILD/AuthorityDerivedData"
PARTYDECK_AUTHORITY_HOST_APP="$PARTYDECK_AUTHORITY_HOST_DERIVED/Build/Products/Debug-iphonesimulator/AuthorityHost.app"
PARTYDECK_AUTHORITY_HOST_RESULT="$PARTYDECK_AUTHORITY_HOST_ARTIFACTS/AuthorityHost.xcresult"
PARTYDECK_AUTHORITY_HOST_STAGE="${1:-test}"
PARTYDECK_AUTHORITY_HOST_FRAMEWORK="${PARTYDECK_GODOT_AUTHORITY_FRAMEWORK:-$PARTYDECK_AUTHORITY_HOST_REPO/godot/qualification/build/modules/bridge/bin/iosSimulatorArm64/debugFramework/PartyDeckGodotBridge.framework}"
PARTYDECK_AUTHORITY_HOST_RECEIPT="${PARTYDECK_GODOT_AUTHORITY_RECEIPT:-$PARTYDECK_AUTHORITY_HOST_EVIDENCE/authority-framework-result.json}"
PARTYDECK_AUTHORITY_HOST_PACK="${PARTYDECK_GODOT_AUTHORITY_PCK:-$PARTYDECK_AUTHORITY_HOST_REPO/godot/qualification/build/renderer/partydeck-last-light.pck}"

if [[ "$PARTYDECK_AUTHORITY_HOST_STAGE" != build && "$PARTYDECK_AUTHORITY_HOST_STAGE" != test ]]; then
  printf '%s\n' 'Usage: test-authority-host.sh [build|test]' >&2
  exit 1
fi
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  printf '%s\n' 'The authority host requires the selected ARM64 macOS/Xcode runner.' >&2
  exit 1
fi
if [[ -e "$PARTYDECK_AUTHORITY_HOST_RESULT" ]]; then
  printf '%s\n' 'Retain the existing AuthorityHost.xcresult before another execution.' >&2
  exit 1
fi
mkdir -p "$PARTYDECK_AUTHORITY_HOST_EVIDENCE" "$PARTYDECK_AUTHORITY_HOST_ARTIFACTS"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode_26.4.1.app/Contents/Developer}"
xcodebuild -version > "$PARTYDECK_AUTHORITY_HOST_EVIDENCE/authority-host-xcode-version.log"
python3 - "$PARTYDECK_AUTHORITY_HOST_EVIDENCE/authority-host-xcode-version.log" <<'PY'
from pathlib import Path
import sys
if Path(sys.argv[1]).read_text().splitlines()[0] != "Xcode 26.4.1":
    raise SystemExit("The authority host is pinned to Xcode 26.4.1.")
PY
test -s "$PARTYDECK_AUTHORITY_HOST_ARTIFACTS/libpartydeck_godot_ios_probe.a"
test -s "$PARTYDECK_AUTHORITY_HOST_ARTIFACTS/libpartydeck_godot_camera.a"
python3 "$PARTYDECK_AUTHORITY_HOST_ROOT/prepare-authority-host.py" \
  --framework "$PARTYDECK_AUTHORITY_HOST_FRAMEWORK" \
  --framework-receipt "$PARTYDECK_AUTHORITY_HOST_RECEIPT" \
  --pack "$PARTYDECK_AUTHORITY_HOST_PACK"
plutil -lint "$PARTYDECK_AUTHORITY_HOST_ROOT/AuthorityHost/Info.plist" \
  "$PARTYDECK_AUTHORITY_HOST_ROOT/AuthorityHost.xcodeproj/project.pbxproj"

preserve_authority_outputs() {
  local authority_exit=$?
  trap - EXIT
  if [[ -d "$PARTYDECK_AUTHORITY_HOST_RESULT" ]]; then
    xcrun xcresulttool export attachments \
      --path "$PARTYDECK_AUTHORITY_HOST_RESULT" \
      --output-path "$PARTYDECK_AUTHORITY_HOST_ARTIFACTS/authority-attachments" || authority_exit=1
  fi
  if [[ -d "$PARTYDECK_AUTHORITY_HOST_APP" ]]; then
    tar -czf "$PARTYDECK_AUTHORITY_HOST_ARTIFACTS/AuthorityHost-simulator.app.tar.gz" \
      -C "$(dirname -- "$PARTYDECK_AUTHORITY_HOST_APP")" AuthorityHost.app || authority_exit=1
  fi
  exit "$authority_exit"
}
trap preserve_authority_outputs EXIT

# A linked Swift caller is a distinct milestone even if a later UI test fails.
xcodebuild build \
  -project "$PARTYDECK_AUTHORITY_HOST_ROOT/AuthorityHost.xcodeproj" \
  -scheme AuthorityHost -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath "$PARTYDECK_AUTHORITY_HOST_DERIVED" \
  CODE_SIGNING_ALLOWED=NO \
  2>&1 | tee "$PARTYDECK_AUTHORITY_HOST_EVIDENCE/authority-host-build.log"
xcrun nm "$PARTYDECK_AUTHORITY_HOST_APP/AuthorityHost" \
  > "$PARTYDECK_AUTHORITY_HOST_EVIDENCE/authority-host-symbols.log"
python3 "$PARTYDECK_AUTHORITY_HOST_ROOT/record-authority-result.py" \
  build "$PARTYDECK_AUTHORITY_HOST_EVIDENCE" "$PARTYDECK_AUTHORITY_HOST_APP/AuthorityHost"
if [[ "$PARTYDECK_AUTHORITY_HOST_STAGE" == build ]]; then
  exit 0
fi

PARTYDECK_AUTHORITY_HOST_SIMULATOR="$(python3 "$PARTYDECK_AUTHORITY_HOST_REPO/scripts/select-ios-simulator.py" "$PARTYDECK_AUTHORITY_HOST_EVIDENCE/authority-simulator.json")"
xcrun simctl bootstatus "$PARTYDECK_AUTHORITY_HOST_SIMULATOR" -b
xcodebuild test \
  -project "$PARTYDECK_AUTHORITY_HOST_ROOT/AuthorityHost.xcodeproj" \
  -scheme AuthorityHost -configuration Debug \
  -destination "platform=iOS Simulator,id=$PARTYDECK_AUTHORITY_HOST_SIMULATOR" \
  -derivedDataPath "$PARTYDECK_AUTHORITY_HOST_DERIVED" \
  -resultBundlePath "$PARTYDECK_AUTHORITY_HOST_RESULT" \
  -parallel-testing-enabled NO CODE_SIGNING_ALLOWED=NO \
  2>&1 | tee "$PARTYDECK_AUTHORITY_HOST_EVIDENCE/authority-host-test.log"
xcrun xcresulttool get test-results summary --path "$PARTYDECK_AUTHORITY_HOST_RESULT" \
  > "$PARTYDECK_AUTHORITY_HOST_EVIDENCE/authority-test-summary.json" \
  2> "$PARTYDECK_AUTHORITY_HOST_EVIDENCE/authority-test-summary-error.log" || true
python3 "$PARTYDECK_AUTHORITY_HOST_ROOT/record-authority-result.py" \
  test "$PARTYDECK_AUTHORITY_HOST_EVIDENCE" "$PARTYDECK_AUTHORITY_HOST_APP/AuthorityHost"
