#!/usr/bin/env bash
set -euo pipefail

PARTYDECK_RETAINED_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PARTYDECK_RETAINED_REPO="$(cd -- "$PARTYDECK_RETAINED_ROOT/../.." && pwd)"
PARTYDECK_RETAINED_STAGE="${1:-test}"
if [[ "$PARTYDECK_RETAINED_STAGE" != build && "$PARTYDECK_RETAINED_STAGE" != test ]]; then
  printf '%s\n' 'Usage: test-retained-host.sh [build|test]' >&2
  exit 1
fi
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  printf '%s\n' 'Retained engine execution requires the pinned ARM64 macOS/Xcode runner.' >&2
  exit 1
fi
PARTYDECK_RETAINED_OUTPUT="$PARTYDECK_RETAINED_ROOT/build/retained-host-$PARTYDECK_RETAINED_STAGE"
if [[ -e "$PARTYDECK_RETAINED_OUTPUT" ]]; then
  printf '%s\n' 'Preserve the existing retained-host stage directory before another run.' >&2
  exit 1
fi
PARTYDECK_RETAINED_EVIDENCE="$PARTYDECK_RETAINED_OUTPUT/evidence"
PARTYDECK_RETAINED_ARTIFACTS="$PARTYDECK_RETAINED_OUTPUT/artifacts"
PARTYDECK_RETAINED_DERIVED="$PARTYDECK_RETAINED_OUTPUT/DerivedData"
PARTYDECK_RETAINED_APP="$PARTYDECK_RETAINED_DERIVED/Build/Products/Debug-iphonesimulator/RetainedHost.app"
PARTYDECK_RETAINED_RESULT="$PARTYDECK_RETAINED_ARTIFACTS/RetainedHost.xcresult"
PARTYDECK_RETAINED_FRAMEWORK="${PARTYDECK_GODOT_RETAINED_FRAMEWORK:-$PARTYDECK_RETAINED_REPO/godot/qualification/build/modules/bridge/bin/iosSimulatorArm64/debugFramework/PartyDeckGodotBridge.framework}"
PARTYDECK_RETAINED_FRAMEWORK_RECEIPT="${PARTYDECK_GODOT_RETAINED_FRAMEWORK_RECEIPT:-$PARTYDECK_RETAINED_ROOT/build/evidence/authority-framework-result.json}"
PARTYDECK_RETAINED_PACK="${PARTYDECK_GODOT_RETAINED_PCK:-$PARTYDECK_RETAINED_REPO/godot/qualification/build/renderer/partydeck-last-light.pck}"
PARTYDECK_RETAINED_SIMULATOR=""
mkdir -p "$PARTYDECK_RETAINED_EVIDENCE" "$PARTYDECK_RETAINED_ARTIFACTS"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode_26.4.1.app/Contents/Developer}"

preserve_retained_outputs() {
  local retained_exit=$?
  trap - EXIT
  if [[ "$PARTYDECK_RETAINED_STAGE" == test ]]; then
    local retained_attachment_exit="" retained_summary_exit=""
    if [[ -d "$PARTYDECK_RETAINED_RESULT" ]]; then
      if xcrun xcresulttool export attachments --path "$PARTYDECK_RETAINED_RESULT" \
        --output-path "$PARTYDECK_RETAINED_ARTIFACTS/attachments" \
        > "$PARTYDECK_RETAINED_EVIDENCE/attachments-export.log" 2>&1; then
        retained_attachment_exit=0
      else
        retained_attachment_exit=$?
        retained_exit=1
      fi
      if xcrun xcresulttool get test-results summary --path "$PARTYDECK_RETAINED_RESULT" \
        > "$PARTYDECK_RETAINED_EVIDENCE/test-summary.json" \
        2> "$PARTYDECK_RETAINED_EVIDENCE/test-summary-error.log"; then
        retained_summary_exit=0
      else
        retained_summary_exit=$?
        retained_exit=1
      fi
    else
      retained_exit=1
    fi
    python3 - "$PARTYDECK_RETAINED_EVIDENCE/test-evidence-export.json" \
      "$retained_attachment_exit" "$retained_summary_exit" <<'PY'
from pathlib import Path
import json, sys
Path(sys.argv[1]).write_text(json.dumps({
    "attachments_export_exit_code": int(sys.argv[2]) if sys.argv[2] else None,
    "summary_export_exit_code": int(sys.argv[3]) if sys.argv[3] else None,
}, indent=2) + "\n")
PY
  fi
  if [[ -d "$PARTYDECK_RETAINED_APP" ]]; then
    tar -czf "$PARTYDECK_RETAINED_ARTIFACTS/RetainedHost-simulator.app.tar.gz" \
      -C "$(dirname -- "$PARTYDECK_RETAINED_APP")" RetainedHost.app || retained_exit=1
  fi
  if [[ -n "$PARTYDECK_RETAINED_SIMULATOR" ]]; then
    local retained_container
    retained_container="$(xcrun simctl get_app_container "$PARTYDECK_RETAINED_SIMULATOR" dev.partydeck.godot.iosretained data 2>/dev/null || true)"
    if [[ -n "$retained_container" && -d "$retained_container/Documents" ]]; then
      mkdir -p "$PARTYDECK_RETAINED_EVIDENCE/application-observations"
      for retained_document in "$retained_container"/Documents/retained-runtime-*.json; do
        [[ -f "$retained_document" ]] || continue
        cp "$retained_document" "$PARTYDECK_RETAINED_EVIDENCE/application-observations/" || retained_exit=1
      done
    fi
  fi
  python3 "$PARTYDECK_RETAINED_ROOT/record-retained-result.py" \
    "$PARTYDECK_RETAINED_STAGE" "$PARTYDECK_RETAINED_EVIDENCE" "$PARTYDECK_RETAINED_APP/RetainedHost" "$retained_exit" || retained_exit=1
  exit "$retained_exit"
}
trap preserve_retained_outputs EXIT

xcodebuild -version > "$PARTYDECK_RETAINED_EVIDENCE/xcode-version.log"
python3 - "$PARTYDECK_RETAINED_EVIDENCE/xcode-version.log" <<'PY'
from pathlib import Path
import sys
if Path(sys.argv[1]).read_text().splitlines()[0] != "Xcode 26.4.1":
    raise SystemExit("The retained harness is pinned to Xcode 26.4.1.")
PY

# This reuses the established receipt verification and fixed pack staging.
# It performs no Gradle or engine build and exports no replacement PCK.
# Retained entry also requires the exact pack pinned by the verified native module.
python3 "$PARTYDECK_RETAINED_ROOT/prepare-authority-host.py" \
  --framework "$PARTYDECK_RETAINED_FRAMEWORK" \
  --framework-receipt "$PARTYDECK_RETAINED_FRAMEWORK_RECEIPT" \
  --pack "$PARTYDECK_RETAINED_PACK" \
  --retained
python3 - "$PARTYDECK_RETAINED_ROOT" "$PARTYDECK_RETAINED_EVIDENCE" <<'PY'
from pathlib import Path
import datetime, hashlib, json, sys
root, evidence = map(Path, sys.argv[1:])
paths = [file for folder in ("RetainedHost", "RetainedHostUITests", "RetainedHost.xcodeproj")
         for file in sorted((root / folder).rglob("*")) if file.is_file()]
paths += [root / "test-retained-host.sh", root / "record-retained-result.py",
          root / "modules/partydeck_ios_probe/PDGodotEngineOwner.h"]
hashes = {file.relative_to(root).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest() for file in paths}
inputs = {"started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "sources": hashes,
          "verified_engine_framework_pack": json.loads((root / "build/evidence/authority-host-inputs.json").read_text())}
(evidence / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
PY
plutil -lint "$PARTYDECK_RETAINED_ROOT/RetainedHost/Info.plist" \
  "$PARTYDECK_RETAINED_ROOT/RetainedHost.xcodeproj/project.pbxproj"
xcodebuild build -project "$PARTYDECK_RETAINED_ROOT/RetainedHost.xcodeproj" \
  -scheme RetainedHost -configuration Debug -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath "$PARTYDECK_RETAINED_DERIVED" CODE_SIGNING_ALLOWED=NO \
  LD_MAP_FILE_PATH="$PARTYDECK_RETAINED_EVIDENCE/RetainedHost-LinkMap.txt" \
  2>&1 | tee "$PARTYDECK_RETAINED_EVIDENCE/build.log"
xcrun nm "$PARTYDECK_RETAINED_APP/RetainedHost" > "$PARTYDECK_RETAINED_EVIDENCE/symbols.log"
if [[ "$PARTYDECK_RETAINED_STAGE" == build ]]; then exit 0; fi

PARTYDECK_RETAINED_SIMULATOR="$(python3 "$PARTYDECK_RETAINED_REPO/scripts/select-ios-simulator.py" "$PARTYDECK_RETAINED_EVIDENCE/simulator.json")"
xcrun simctl bootstatus "$PARTYDECK_RETAINED_SIMULATOR" -b
xcodebuild test -project "$PARTYDECK_RETAINED_ROOT/RetainedHost.xcodeproj" \
  -scheme RetainedHost -configuration Debug -destination "platform=iOS Simulator,id=$PARTYDECK_RETAINED_SIMULATOR" \
  -derivedDataPath "$PARTYDECK_RETAINED_DERIVED" -resultBundlePath "$PARTYDECK_RETAINED_RESULT" \
  -parallel-testing-enabled NO CODE_SIGNING_ALLOWED=NO \
  LD_MAP_FILE_PATH="$PARTYDECK_RETAINED_EVIDENCE/RetainedHost-LinkMap.txt" \
  2>&1 | tee "$PARTYDECK_RETAINED_EVIDENCE/test.log"
