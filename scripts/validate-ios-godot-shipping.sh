#!/usr/bin/env bash
# Private handoff runner. Root owns copying the reviewed test/project changes and CI integration.
set -euo pipefail

if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  printf '%s\n' 'Shipping UI smoke requires the ARM64 macOS/Xcode runner.' >&2
  exit 2
fi
shipping_repo="$(cd -- "${1:?Supply the integrated repository root.}" && pwd)"
shipping_output="${2:?Supply a new absolute evidence directory.}"
shipping_tools="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Keep the historical picker run separate from the two-case native Leave run.
shipping_scope="${3:-picker}"
case "$shipping_scope" in
  picker)
    shipping_checker="$shipping_tools/check-ios-godot-shipping-smoke.py"
    shipping_selections=(
      -only-testing:PartyDeckUITests/PartyDeckGodotShippingUITests/testShippingPickerOpensBothNativeTablesAndReturnsToStandard
    )
    ;;
  native-leave)
    shipping_checker="$shipping_tools/check-ios-godot-native-leave-smoke.py"
    shipping_selections=(
      -only-testing:PartyDeckUITests/PartyDeckGodotNativeLeaveShippingUITests/testShipping2DNativeLeaveCancelAndConfirm
      -only-testing:PartyDeckUITests/PartyDeckGodotNativeLeaveShippingUITests/testShipping3DNativeLeaveCancelAndConfirm
    )
    ;;
  *)
    printf '%s\n' 'Shipping scope must be picker or native-leave.' >&2
    exit 2
    ;;
esac
shipping_engine="${PARTYDECK_IOS_SIMULATOR_GODOT_ENGINE_ROOT:?Supply the existing receipt-checked Simulator engine.}"
shipping_pack="${PARTYDECK_IOS_GODOT_PACK:-$shipping_repo/godot/qualification/build/renderer/partydeck-last-light.pck}"
if [[ "$shipping_output" != /* || -e "$shipping_output" ]]; then
  printf '%s\n' 'Use a new absolute directory; preserve all previous shipping evidence.' >&2
  exit 2
fi
mkdir -p "$shipping_output"
shipping_derived="$shipping_output/DerivedData"
shipping_result="$shipping_output/PartyDeckShipping.xcresult"
shipping_app="$shipping_derived/Build/Products/Debug-iphonesimulator/PartyDeck.app"
shipping_link_map="$shipping_output/PartyDeck-Shipping-Debug-LinkMap-arm64.txt"
shipping_preflight_exit='' shipping_build_settings_exit='' shipping_settings_check_exit=''
shipping_test_exit='' shipping_tee_exit='' shipping_attachments_exit='' shipping_summary_exit=''
shipping_package_exit='' shipping_archive_exit=''

shipping_preserve() {
  shipping_primary_exit=$?
  trap - EXIT
  set +e
  if [[ -d "$shipping_result" ]]; then
    xcrun xcresulttool export attachments --path "$shipping_result" --output-path "$shipping_output/attachments" \
      > "$shipping_output/attachments-export.log" 2>&1
    shipping_attachments_exit=$?
    xcrun xcresulttool get test-results summary --path "$shipping_result" \
      > "$shipping_output/test-summary.json" 2> "$shipping_output/summary-export.log"
    shipping_summary_exit=$?
  fi
  if [[ -d "$shipping_app" ]]; then
    python3 -B "$shipping_repo/scripts/prepare-ios-godot.py" verify-app --app "$shipping_app" \
      --inputs "$shipping_derived/Build/Products/Debug-iphonesimulator/PartyDeckGodotInputs/inputs.json" \
      --link-map "$shipping_link_map" --output "$shipping_output/godot-shipping-link.json" \
      > "$shipping_output/package-verification.log" 2>&1
    shipping_package_exit=$?
    tar -czf "$shipping_output/PartyDeck-shipping-simulator.app.tar.gz" -C "$(dirname -- "$shipping_app")" PartyDeck.app \
      > "$shipping_output/package-archive.log" 2>&1
    shipping_archive_exit=$?
  fi
  python3 - "$shipping_output/stage-exits.json" "$shipping_primary_exit" "$shipping_preflight_exit" \
    "$shipping_build_settings_exit" "$shipping_settings_check_exit" "$shipping_test_exit" "$shipping_tee_exit" \
    "$shipping_attachments_exit" "$shipping_summary_exit" "$shipping_package_exit" "$shipping_archive_exit" <<'PY'
from pathlib import Path
import json, sys
names = ['primary_exit', 'preflight', 'build_settings', 'settings_check', 'xcodebuild', 'tee',
         'attachments_export', 'summary_export', 'package_verify', 'package_archive']
assert len(sys.argv[2:]) == len(names)
with Path(sys.argv[1]).open('x') as output:
    json.dump({key: int(value) if value else None for key, value in zip(names, sys.argv[2:])}, output, indent=2)
    output.write('\n')
PY
  shipping_receipt_exit=$?
  python3 -B "$shipping_checker" result --directory "$shipping_output" \
    > "$shipping_output/result-check.log" 2>&1
  shipping_check_exit=$?
  if [[ "$shipping_primary_exit" != 0 ]]; then exit "$shipping_primary_exit"; fi
  if [[ "$shipping_receipt_exit" != 0 || "$shipping_check_exit" != 0 ]]; then exit 1; fi
  exit 0
}
trap shipping_preserve EXIT
cd "$shipping_repo"

if python3 -B "$shipping_checker" preflight --repo "$shipping_repo" --directory "$shipping_output" \
    > "$shipping_output/preflight.log" 2>&1; then
  shipping_preflight_exit=0
else
  shipping_preflight_exit=$?
  exit "$shipping_preflight_exit"
fi

shipping_settings=(
  PARTYDECK_SESSION_QUALIFICATION_CONDITION=
  PARTYDECK_SHIPPING_SMOKE_CONDITION=PARTYDECK_GODOT_SHIPPING_SMOKE
  "PARTYDECK_APP_INFO_PLIST=$shipping_repo/iosApp/PartyDeck/Info.plist"
  PARTYDECK_GODOT_ACTIVATION_EXPECTATION=
  "PARTYDECK_GODOT_ENGINE_ROOT=$shipping_engine"
  "PARTYDECK_GODOT_PACK=$shipping_pack"
  "PARTYDECK_GODOT_LINK_MAP=$shipping_link_map"
  CODE_SIGNING_ALLOWED=NO LD_GENERATE_MAP_FILE=YES
)
if xcodebuild -project iosApp/PartyDeck.xcodeproj -target PartyDeck -target PartyDeckUITests \
    -configuration Debug -sdk iphonesimulator -showBuildSettings -json "${shipping_settings[@]}" \
    > "$shipping_output/build-settings.json" 2> "$shipping_output/build-settings-error.log"; then
  shipping_build_settings_exit=0
else
  shipping_build_settings_exit=$?
  exit "$shipping_build_settings_exit"
fi
if python3 -B "$shipping_checker" settings --repo "$shipping_repo" --directory "$shipping_output" \
    > "$shipping_output/settings-check.log" 2>&1; then
  shipping_settings_check_exit=0
else
  shipping_settings_check_exit=$?
  exit "$shipping_settings_check_exit"
fi

shipping_simulator="$(python3 "$shipping_repo/scripts/select-ios-simulator.py" "$shipping_output/simulator.json")"
xcrun simctl bootstatus "$shipping_simulator" -b
set +e
xcodebuild test -project iosApp/PartyDeck.xcodeproj -scheme PartyDeck -configuration Debug -sdk iphonesimulator \
  -destination "platform=iOS Simulator,id=$shipping_simulator" \
  -derivedDataPath "$shipping_derived" -clonedSourcePackagesDirPath "$shipping_repo/build/ci/ios/SourcePackages" \
  -resultBundlePath "$shipping_result" -parallel-testing-enabled NO \
  "${shipping_selections[@]}" \
  "${shipping_settings[@]}" 2>&1 | tee "$shipping_output/test.log"
shipping_pipeline_exits=("${PIPESTATUS[@]}")
set -e
shipping_test_exit="${shipping_pipeline_exits[0]}"
shipping_tee_exit="${shipping_pipeline_exits[1]}"
if [[ "$shipping_test_exit" != 0 ]]; then exit "$shipping_test_exit"; fi
if [[ "$shipping_tee_exit" != 0 ]]; then exit "$shipping_tee_exit"; fi
