#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -gt 1 ]]; then
  printf '%s\n' 'Usage: validate-ios-godot-session.sh [production|qualification-scroll]' >&2
  exit 2
fi
PARTYDECK_SESSION_SCOPE="${1-production}"
case "$PARTYDECK_SESSION_SCOPE" in
  production)
    PARTYDECK_SESSION_OUTPUT_NAME=godot-session
    PARTYDECK_SESSION_TESTS=(
      -only-testing:PartyDeckUITests/PartyDeckGodotSessionUITests/testProduction2DPracticeSession
      -only-testing:PartyDeckUITests/PartyDeckGodotSessionUITests/testProduction3DPracticeSession
    )
    ;;
  qualification-scroll)
    PARTYDECK_SESSION_OUTPUT_NAME=godot-session-scroll
    PARTYDECK_SESSION_TESTS=(
      -only-testing:PartyDeckUITests/PartyDeckGodotSessionUITests/testProduction2DConcealedLobbyScrollAndCancel
      -only-testing:PartyDeckUITests/PartyDeckGodotSessionUITests/testProduction3DConcealedLobbyScrollAndCancel
    )
    ;;
  *)
    printf '%s\n' 'Select production or qualification-scroll; evidence scopes cannot be combined.' >&2
    exit 2
    ;;
esac

if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  printf '%s\n' 'Godot session qualification requires the ARM64 macOS/Xcode runner.' >&2
  exit 1
fi
if [[ "${PARTYDECK_IOS_GODOT_SESSION_SMOKE:-0}" != 1 ]]; then
  printf '%s\n' 'Select the explicit Godot session qualification input before running this script.' >&2
  exit 1
fi

PARTYDECK_SESSION_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARTYDECK_SESSION_ROOT"
PARTYDECK_SESSION_OUTPUT="$PARTYDECK_SESSION_ROOT/build/ci/ios/$PARTYDECK_SESSION_OUTPUT_NAME"
if [[ -e "$PARTYDECK_SESSION_OUTPUT" ]]; then
  printf '%s\n' 'Preserve the existing selected session evidence before another execution.' >&2
  exit 1
fi
if [[ "$PARTYDECK_SESSION_SCOPE" == qualification-scroll ]]; then
  # Fail before building or launching if the reviewed route or its cleanup changed.
  python3 -B - "$PARTYDECK_SESSION_ROOT/scripts/check-ios-production-session-smoke.py" \
    "$PARTYDECK_SESSION_ROOT/iosApp/PartyDeckUITests/PartyDeckGodotSessionUITests.swift" <<'PY'
from pathlib import Path
import runpy, sys
runpy.run_path(sys.argv[1])["check_scroll_source"](Path(sys.argv[2]))
PY
fi
PARTYDECK_SESSION_PACK="${PARTYDECK_IOS_GODOT_PACK:-$PARTYDECK_SESSION_ROOT/godot/qualification/build/renderer/partydeck-last-light.pck}"
PARTYDECK_SESSION_ENGINE="${PARTYDECK_IOS_SIMULATOR_GODOT_ENGINE_ROOT:?Supply the receipt-checked Simulator engine from this run.}"
PARTYDECK_SESSION_DERIVED="$PARTYDECK_SESSION_OUTPUT/DerivedData"
PARTYDECK_SESSION_RESULT="$PARTYDECK_SESSION_OUTPUT/PartyDeckGodotSessions.xcresult"
PARTYDECK_SESSION_APP="$PARTYDECK_SESSION_DERIVED/Build/Products/Debug-iphonesimulator/PartyDeck.app"
PARTYDECK_SESSION_LINK_MAP="$PARTYDECK_SESSION_OUTPUT/PartyDeck-Session-Debug-LinkMap-arm64.txt"
mkdir -p "$PARTYDECK_SESSION_OUTPUT"

preserve_session_outputs() {
  local session_exit=$?
  trap - EXIT
  local session_attachment_exit="" session_summary_exit=""
  if [[ -d "$PARTYDECK_SESSION_RESULT" ]]; then
    if xcrun xcresulttool export attachments --path "$PARTYDECK_SESSION_RESULT" \
      --output-path "$PARTYDECK_SESSION_OUTPUT/attachments" \
      > "$PARTYDECK_SESSION_OUTPUT/attachments-export.log" 2>&1; then
      session_attachment_exit=0
    else
      session_attachment_exit=$?
      session_exit=1
    fi
    if xcrun xcresulttool get test-results summary --path "$PARTYDECK_SESSION_RESULT" \
      > "$PARTYDECK_SESSION_OUTPUT/test-summary.json" \
      2> "$PARTYDECK_SESSION_OUTPUT/test-summary-error.log"; then
      session_summary_exit=0
    else
      session_summary_exit=$?
      session_exit=1
    fi
  else
    session_exit=1
  fi
  python3 - "$PARTYDECK_SESSION_OUTPUT/test-evidence-export.json" \
    "$session_attachment_exit" "$session_summary_exit" <<'PY' || session_exit=1
from pathlib import Path
import json, sys
Path(sys.argv[1]).write_text(json.dumps({
    "attachments_export_exit_code": int(sys.argv[2]) if sys.argv[2] else None,
    "summary_export_exit_code": int(sys.argv[3]) if sys.argv[3] else None,
}, indent=2) + "\n")
PY
  if [[ -d "$PARTYDECK_SESSION_APP" ]]; then
    python3 scripts/prepare-ios-godot.py verify-app \
      --app "$PARTYDECK_SESSION_APP" \
      --inputs "$PARTYDECK_SESSION_DERIVED/Build/Products/Debug-iphonesimulator/PartyDeckGodotInputs/inputs.json" \
      --link-map "$PARTYDECK_SESSION_LINK_MAP" \
      --output "$PARTYDECK_SESSION_OUTPUT/godot-production-session-link.json" \
      > "$PARTYDECK_SESSION_OUTPUT/app-verification.log" 2>&1 || session_exit=1
    tar -czf "$PARTYDECK_SESSION_OUTPUT/PartyDeck-session-simulator.app.tar.gz" \
      -C "$(dirname -- "$PARTYDECK_SESSION_APP")" PartyDeck.app || session_exit=1
  else
    session_exit=1
  fi
  python3 scripts/check-ios-production-session-smoke.py \
    --scope "$PARTYDECK_SESSION_SCOPE" \
    --test-source "$PARTYDECK_SESSION_ROOT/iosApp/PartyDeckUITests/PartyDeckGodotSessionUITests.swift" \
    --test-log "$PARTYDECK_SESSION_OUTPUT/test.log" \
    --xcresult "$PARTYDECK_SESSION_RESULT" \
    --attachments "$PARTYDECK_SESSION_OUTPUT/attachments" \
    --summary "$PARTYDECK_SESSION_OUTPUT/test-summary.json" \
    --command-exit "$session_exit" \
    --output "$PARTYDECK_SESSION_OUTPUT/result.json" || session_exit=1
  exit "$session_exit"
}
trap preserve_session_outputs EXIT

python3 -B godot/tools/renderer.py check-pack --pack "$PARTYDECK_SESSION_PACK"
python3 -B scripts/prepare-ios-godot-activation.py --modes 2d,3d \
  --output-plist "$PARTYDECK_SESSION_OUTPUT/activation/Info.plist" \
  --expectation "$PARTYDECK_SESSION_OUTPUT/activation/expectation.json"
PARTYDECK_SESSION_SIMULATOR="$(python3 scripts/select-ios-simulator.py "$PARTYDECK_SESSION_OUTPUT/simulator.json")"
xcrun simctl bootstatus "$PARTYDECK_SESSION_SIMULATOR" -b

PARTYDECK_SESSION_SETTINGS=(
  PARTYDECK_SESSION_QUALIFICATION_CONDITION=PARTYDECK_GODOT_SESSION_QUALIFICATION
  "PARTYDECK_APP_INFO_PLIST=$PARTYDECK_SESSION_OUTPUT/activation/Info.plist"
  "PARTYDECK_GODOT_ACTIVATION_EXPECTATION=$PARTYDECK_SESSION_OUTPUT/activation/expectation.json"
  "PARTYDECK_GODOT_ENGINE_ROOT=$PARTYDECK_SESSION_ENGINE"
  "PARTYDECK_GODOT_PACK=$PARTYDECK_SESSION_PACK"
  "PARTYDECK_GODOT_LINK_MAP=$PARTYDECK_SESSION_LINK_MAP"
  CODE_SIGNING_ALLOWED=NO LD_GENERATE_MAP_FILE=YES
)
# The pinned Xcode help supports multiple explicit -target selectors. Query
# both targets because the app's effective conditions do not prove the tests'.
xcodebuild -project iosApp/PartyDeck.xcodeproj \
  -target PartyDeck -target PartyDeckUITests -configuration Debug -sdk iphonesimulator \
  -showBuildSettings -json "${PARTYDECK_SESSION_SETTINGS[@]}" \
  > "$PARTYDECK_SESSION_OUTPUT/build-settings.json" \
  2> "$PARTYDECK_SESSION_OUTPUT/build-settings-error.log"
python3 - "$PARTYDECK_SESSION_OUTPUT/build-settings.json" \
  "$PARTYDECK_SESSION_OUTPUT/activation/Info.plist" <<'PY'
from pathlib import Path
import json, shlex, sys

def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate effective build setting.")
        result[key] = value
    return result

documents = json.loads(Path(sys.argv[1]).read_text(), object_pairs_hook=unique)
if not isinstance(documents, list):
    raise SystemExit("Expected an array of effective Xcode target settings.")
targets = {}
for value in documents:
    if not isinstance(value, dict) or value.get("target") not in {"PartyDeck", "PartyDeckUITests"}:
        raise SystemExit("Unexpected target in qualification build settings.")
    target = value["target"]
    if target in targets or not isinstance(value.get("buildSettings"), dict):
        raise SystemExit("Missing or duplicate qualification target settings.")
    settings = value["buildSettings"]
    conditions = settings.get("SWIFT_ACTIVE_COMPILATION_CONDITIONS", "")
    if (not isinstance(conditions, str)
            or not {"DEBUG", "PARTYDECK_GODOT_SESSION_QUALIFICATION"} <= set(shlex.split(conditions))
            or settings.get("CONFIGURATION") != "Debug"
            or settings.get("PLATFORM_NAME") != "iphonesimulator"):
        raise SystemExit("Both Simulator targets must inherit DEBUG and the explicit observation condition.")
    targets[target] = settings
if set(targets) != {"PartyDeck", "PartyDeckUITests"}:
    raise SystemExit("Both app and UI-test target settings are required.")
app, tests = targets["PartyDeck"], targets["PartyDeckUITests"]
if app.get("INFOPLIST_FILE") != sys.argv[2] or app.get("GENERATE_INFOPLIST_FILE") != "NO":
    raise SystemExit("The app must consume the exact generated qualification plist.")
if tests.get("GENERATE_INFOPLIST_FILE") != "YES" or tests.get("INFOPLIST_FILE") not in (None, ""):
    raise SystemExit("The UI-test bundle must keep its own generated plist.")
PY

# Use a separate build/result directory so the ordinary app's receipts and
# original package remain intact. Only the selected scope's two named cases run here.
xcodebuild test \
  -project iosApp/PartyDeck.xcodeproj -scheme PartyDeck -configuration Debug -sdk iphonesimulator \
  -destination "platform=iOS Simulator,id=$PARTYDECK_SESSION_SIMULATOR" \
  -derivedDataPath "$PARTYDECK_SESSION_DERIVED" \
  -clonedSourcePackagesDirPath "$PARTYDECK_SESSION_ROOT/build/ci/ios/SourcePackages" \
  -resultBundlePath "$PARTYDECK_SESSION_RESULT" \
  -parallel-testing-enabled NO \
  "${PARTYDECK_SESSION_TESTS[@]}" \
  "${PARTYDECK_SESSION_SETTINGS[@]}" \
  2>&1 | tee "$PARTYDECK_SESSION_OUTPUT/test.log"
