#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  printf '%s\n' 'Native UIKit layout qualification requires the ARM64 macOS/Xcode runner.' >&2
  exit 1
fi
if [[ "${PARTYDECK_IOS_GODOT_SESSION_SMOKE:-0}" != 1 ]]; then
  printf '%s\n' 'Select the explicit iOS Godot session qualification input before running its UIKit layout gate.' >&2
  exit 1
fi

PARTYDECK_LAYOUT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARTYDECK_LAYOUT_ROOT"
PARTYDECK_LAYOUT_OUTPUT="$PARTYDECK_LAYOUT_ROOT/build/ci/ios/godot-layout"
if [[ -e "$PARTYDECK_LAYOUT_OUTPUT" ]]; then
  printf '%s\n' 'Preserve the existing native layout evidence before another execution.' >&2
  exit 1
fi
PARTYDECK_LAYOUT_ENGINE="${PARTYDECK_IOS_SIMULATOR_GODOT_ENGINE_ROOT:?Supply the receipt-checked Simulator engine from this run.}"
PARTYDECK_LAYOUT_PACK="${PARTYDECK_IOS_GODOT_PACK:-$PARTYDECK_LAYOUT_ROOT/godot/qualification/build/renderer/partydeck-last-light.pck}"
PARTYDECK_LAYOUT_DERIVED="$PARTYDECK_LAYOUT_OUTPUT/DerivedData"
PARTYDECK_LAYOUT_RESULT="$PARTYDECK_LAYOUT_OUTPUT/PartyDeckGodotLayout.xcresult"
PARTYDECK_LAYOUT_APP="$PARTYDECK_LAYOUT_DERIVED/Build/Products/Debug-iphonesimulator/PartyDeck.app"
PARTYDECK_LAYOUT_PLIST="$PARTYDECK_LAYOUT_ROOT/iosApp/PartyDeck/Info.plist"
PARTYDECK_LAYOUT_LINK_MAP="$PARTYDECK_LAYOUT_OUTPUT/PartyDeck-Layout-Debug-LinkMap-arm64.txt"
PARTYDECK_LAYOUT_TEST_EXIT=""
PARTYDECK_LAYOUT_LOG_EXIT=""
mkdir -p "$PARTYDECK_LAYOUT_OUTPUT"

preserve_layout_outputs() {
  local layout_exit=$?
  trap - EXIT
  local layout_attachments="" layout_summary="" layout_verify="" layout_archive=""
  if [[ -d "$PARTYDECK_LAYOUT_RESULT" ]]; then
    if xcrun xcresulttool export attachments --path "$PARTYDECK_LAYOUT_RESULT" \
      --output-path "$PARTYDECK_LAYOUT_OUTPUT/attachments" \
      > "$PARTYDECK_LAYOUT_OUTPUT/attachments-export.log" 2>&1; then
      layout_attachments=0
    else
      layout_attachments=$?
      layout_exit=1
    fi
    if xcrun xcresulttool get test-results summary --path "$PARTYDECK_LAYOUT_RESULT" \
      > "$PARTYDECK_LAYOUT_OUTPUT/test-summary.json" 2> "$PARTYDECK_LAYOUT_OUTPUT/test-summary-error.log"; then
      layout_summary=0
    else
      layout_summary=$?
      layout_exit=1
    fi
  else
    layout_exit=1
  fi
  if [[ -d "$PARTYDECK_LAYOUT_APP" ]]; then
    if python3 scripts/prepare-ios-godot.py verify-app \
      --app "$PARTYDECK_LAYOUT_APP" \
      --inputs "$PARTYDECK_LAYOUT_DERIVED/Build/Products/Debug-iphonesimulator/PartyDeckGodotInputs/inputs.json" \
      --link-map "$PARTYDECK_LAYOUT_LINK_MAP" \
      --output "$PARTYDECK_LAYOUT_OUTPUT/godot-layout-app-link.json" \
      > "$PARTYDECK_LAYOUT_OUTPUT/app-verification.log" 2>&1; then
      layout_verify=0
    else
      layout_verify=$?
      layout_exit=1
    fi
    if tar -czf "$PARTYDECK_LAYOUT_OUTPUT/PartyDeck-layout-simulator.app.tar.gz" \
      -C "$(dirname -- "$PARTYDECK_LAYOUT_APP")" PartyDeck.app; then
      layout_archive=0
    else
      layout_archive=$?
      layout_exit=1
    fi
  else
    layout_exit=1
  fi
  python3 - "$PARTYDECK_LAYOUT_OUTPUT/command-status.json" "$PARTYDECK_LAYOUT_TEST_EXIT" \
    "$PARTYDECK_LAYOUT_LOG_EXIT" "$layout_attachments" "$layout_summary" "$layout_verify" "$layout_archive" <<'PY' || layout_exit=1
from pathlib import Path
import json, sys
keys = ("native_test_exit_code", "test_log_exit_code", "attachments_export_exit_code",
        "summary_export_exit_code", "app_verification_exit_code", "app_archive_exit_code")
Path(sys.argv[1]).write_text(json.dumps({key: int(value) if value else None for key, value in zip(keys, sys.argv[2:])}, indent=2) + "\n")
PY
  python3 scripts/check-ios-godot-layout.py result \
    --build-settings "$PARTYDECK_LAYOUT_OUTPUT/build-settings.json" --app-plist "$PARTYDECK_LAYOUT_PLIST" \
    --test-log "$PARTYDECK_LAYOUT_OUTPUT/test.log" --xcresult "$PARTYDECK_LAYOUT_RESULT" \
    --attachments "$PARTYDECK_LAYOUT_OUTPUT/attachments" --summary "$PARTYDECK_LAYOUT_OUTPUT/test-summary.json" \
    --command-status "$PARTYDECK_LAYOUT_OUTPUT/command-status.json" --command-exit "$layout_exit" \
    --source-root "$PARTYDECK_LAYOUT_ROOT" --output "$PARTYDECK_LAYOUT_OUTPUT/result.json" || layout_exit=1
  exit "$layout_exit"
}
trap preserve_layout_outputs EXIT

python3 -B godot/tools/renderer.py check-pack --pack "$PARTYDECK_LAYOUT_PACK"
PARTYDECK_LAYOUT_SIMULATOR="$(python3 scripts/select-ios-simulator.py "$PARTYDECK_LAYOUT_OUTPUT/simulator.json")"
xcrun simctl bootstatus "$PARTYDECK_LAYOUT_SIMULATOR" -b
PARTYDECK_LAYOUT_SETTINGS=(
  PARTYDECK_SESSION_QUALIFICATION_CONDITION=PARTYDECK_GODOT_SESSION_QUALIFICATION
  "PARTYDECK_APP_INFO_PLIST=$PARTYDECK_LAYOUT_PLIST"
  PARTYDECK_GODOT_ACTIVATION_EXPECTATION=
  "PARTYDECK_GODOT_ENGINE_ROOT=$PARTYDECK_LAYOUT_ENGINE"
  "PARTYDECK_GODOT_PACK=$PARTYDECK_LAYOUT_PACK"
  "PARTYDECK_GODOT_LINK_MAP=$PARTYDECK_LAYOUT_LINK_MAP"
  CODE_SIGNING_ALLOWED=NO LD_GENERATE_MAP_FILE=YES
)
xcodebuild -project iosApp/PartyDeck.xcodeproj -target PartyDeck -target PartyDeckTests \
  -configuration Debug -sdk iphonesimulator -showBuildSettings -json "${PARTYDECK_LAYOUT_SETTINGS[@]}" \
  > "$PARTYDECK_LAYOUT_OUTPUT/build-settings.json" 2> "$PARTYDECK_LAYOUT_OUTPUT/build-settings-error.log"
python3 scripts/check-ios-godot-layout.py settings \
  --build-settings "$PARTYDECK_LAYOUT_OUTPUT/build-settings.json" --app-plist "$PARTYDECK_LAYOUT_PLIST"

# Keep this UIKit result separate from the unchanged exact-two production engine receipt.
set +e
xcodebuild test -project iosApp/PartyDeck.xcodeproj -scheme PartyDeck -configuration Debug -sdk iphonesimulator \
  -destination "platform=iOS Simulator,id=$PARTYDECK_LAYOUT_SIMULATOR" \
  -derivedDataPath "$PARTYDECK_LAYOUT_DERIVED" \
  -clonedSourcePackagesDirPath "$PARTYDECK_LAYOUT_ROOT/build/ci/ios/SourcePackages" \
  -resultBundlePath "$PARTYDECK_LAYOUT_RESULT" -parallel-testing-enabled NO \
  -only-testing:PartyDeckTests/GodotPresentationViewControllerTests/testPortraitStageUsesAvailableHeightWithStandardText \
  -only-testing:PartyDeckTests/GodotPresentationViewControllerTests/testPortraitStageUsesAvailableHeightWithAccessibilityText \
  -only-testing:PartyDeckTests/GodotPresentationViewControllerTests/testNativeChildRemainsInsideTheHiddenAccessibilityContainer \
  "${PARTYDECK_LAYOUT_SETTINGS[@]}" 2>&1 | tee "$PARTYDECK_LAYOUT_OUTPUT/test.log"
PARTYDECK_LAYOUT_PIPE_STATUS=("${PIPESTATUS[@]}")
set -e
PARTYDECK_LAYOUT_TEST_EXIT="${PARTYDECK_LAYOUT_PIPE_STATUS[0]}"
PARTYDECK_LAYOUT_LOG_EXIT="${PARTYDECK_LAYOUT_PIPE_STATUS[1]}"
if [[ "$PARTYDECK_LAYOUT_TEST_EXIT" != 0 || "$PARTYDECK_LAYOUT_LOG_EXIT" != 0 ]]; then
  exit 1
fi
