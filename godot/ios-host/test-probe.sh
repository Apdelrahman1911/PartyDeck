#!/usr/bin/env bash
set -euo pipefail

PARTYDECK_PROBE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PARTYDECK_REPO_ROOT="$(cd -- "$PARTYDECK_PROBE_ROOT/../.." && pwd)"
PARTYDECK_PROBE_BUILD="$PARTYDECK_PROBE_ROOT/build"
PARTYDECK_PROBE_EVIDENCE="$PARTYDECK_PROBE_BUILD/evidence"
PARTYDECK_PROBE_ARTIFACTS="$PARTYDECK_PROBE_BUILD/artifacts"
PARTYDECK_PROBE_RESULT="$PARTYDECK_PROBE_ARTIFACTS/ProbeHost.xcresult"
PARTYDECK_PROBE_DERIVED="$PARTYDECK_PROBE_BUILD/DerivedData"
PARTYDECK_PROBE_APP="$PARTYDECK_PROBE_DERIVED/Build/Products/Debug-iphonesimulator/ProbeHost.app"

if [[ "$(uname -s)" != Darwin ]]; then
  printf '%s\n' 'Executable iOS validation requires the selected macOS/Xcode runner.' >&2
  exit 1
fi
if [[ -e "$PARTYDECK_PROBE_RESULT" ]]; then
  printf '%s\n' 'The previous ProbeHost.xcresult exists; retain it before starting another execution.' >&2
  exit 1
fi
mkdir -p "$PARTYDECK_PROBE_EVIDENCE" "$PARTYDECK_PROBE_ARTIFACTS"
test -f "$PARTYDECK_PROBE_ARTIFACTS/libpartydeck_godot_ios_probe.a"
test -f "$PARTYDECK_PROBE_ARTIFACTS/libpartydeck_godot_camera.a"

if [[ -n "${PARTYDECK_GODOT_PROBE_PCK:-}" ]]; then
  python3 "$PARTYDECK_PROBE_ROOT/prepare-host-resources.py" --pack "$PARTYDECK_GODOT_PROBE_PCK"
else
  python3 "$PARTYDECK_PROBE_ROOT/prepare-host-resources.py"
fi
xcrun clang++ -std=c++17 -Wall -Wextra -Werror \
  "$PARTYDECK_PROBE_ROOT/tests/strict_json_test.cpp" \
  -o "$PARTYDECK_PROBE_BUILD/strict-json-test"
"$PARTYDECK_PROBE_BUILD/strict-json-test" | tee "$PARTYDECK_PROBE_EVIDENCE/strict-json-test.log"
plutil -lint "$PARTYDECK_PROBE_ROOT/ProbeHost/Info.plist" \
  "$PARTYDECK_PROBE_ROOT/ProbeHost.xcodeproj/project.pbxproj"

PARTYDECK_SIMULATOR_ID="$(python3 "$PARTYDECK_REPO_ROOT/scripts/select-ios-simulator.py" "$PARTYDECK_PROBE_EVIDENCE/simulator.json")"
xcrun simctl bootstatus "$PARTYDECK_SIMULATOR_ID" -b
xcrun xcresulttool export attachments --help > "$PARTYDECK_PROBE_EVIDENCE/xcresulttool-attachments-help.log"

preserve_probe_outputs() {
  local probe_exit=$?
  trap - EXIT
  if [[ -d "$PARTYDECK_PROBE_RESULT" ]]; then
    xcrun xcresulttool export attachments \
      --path "$PARTYDECK_PROBE_RESULT" \
      --output-path "$PARTYDECK_PROBE_ARTIFACTS/attachments" || probe_exit=1
  fi
  if [[ -d "$PARTYDECK_PROBE_APP" ]]; then
    tar -czf "$PARTYDECK_PROBE_ARTIFACTS/ProbeHost-simulator.app.tar.gz" \
      -C "$(dirname -- "$PARTYDECK_PROBE_APP")" ProbeHost.app || probe_exit=1
  fi
  exit "$probe_exit"
}
trap preserve_probe_outputs EXIT

# Selective archive linking preserves the host's SwiftUI entry point. The
# complete Godot archive is not force-loaded; retain the actual link map.
xcodebuild test \
  -project "$PARTYDECK_PROBE_ROOT/ProbeHost.xcodeproj" \
  -scheme ProbeHost \
  -configuration Debug \
  -destination "platform=iOS Simulator,id=$PARTYDECK_SIMULATOR_ID" \
  -derivedDataPath "$PARTYDECK_PROBE_DERIVED" \
  -resultBundlePath "$PARTYDECK_PROBE_RESULT" \
  -parallel-testing-enabled NO \
  CODE_SIGNING_ALLOWED=NO \
  2>&1 | tee "$PARTYDECK_PROBE_EVIDENCE/host-test.log"

# Retain the installed tool's output as supplementary evidence. The result
# recorder gates on each actual XCTest case outcome, not an assumed JSON schema.
xcrun xcresulttool get test-results summary --path "$PARTYDECK_PROBE_RESULT" \
  > "$PARTYDECK_PROBE_EVIDENCE/native-test-summary.json" \
  2> "$PARTYDECK_PROBE_EVIDENCE/native-test-summary-error.log" || true
xcrun nm "$PARTYDECK_PROBE_APP/ProbeHost" > "$PARTYDECK_PROBE_EVIDENCE/host-symbols.log"
python3 "$PARTYDECK_PROBE_ROOT/record-native-result.py" \
  "$PARTYDECK_PROBE_EVIDENCE" "$PARTYDECK_PROBE_APP/ProbeHost"
