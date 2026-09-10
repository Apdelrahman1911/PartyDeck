#!/usr/bin/env bash
set -euo pipefail

PARTYDECK_AUTHORITY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PARTYDECK_AUTHORITY_REPO="$(cd -- "$PARTYDECK_AUTHORITY_ROOT/../.." && pwd)"
PARTYDECK_AUTHORITY_EVIDENCE="$PARTYDECK_AUTHORITY_ROOT/build/evidence"
PARTYDECK_AUTHORITY_ARTIFACTS="$PARTYDECK_AUTHORITY_ROOT/build/artifacts"
PARTYDECK_AUTHORITY_FRAMEWORK="$PARTYDECK_AUTHORITY_REPO/godot/qualification/build/modules/bridge/bin/iosSimulatorArm64/debugFramework/PartyDeckGodotBridge.framework"
PARTYDECK_AUTHORITY_ARCHIVE="$PARTYDECK_AUTHORITY_ARTIFACTS/PartyDeckGodotBridge-simulator.framework.tar.gz"

if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  printf '%s\n' 'The authority framework requires the selected ARM64 macOS/Xcode runner.' >&2
  exit 1
fi
if [[ -e "$PARTYDECK_AUTHORITY_ARCHIVE" ]]; then
  printf '%s\n' 'Retain the existing authority framework artifact before another build.' >&2
  exit 1
fi
mkdir -p "$PARTYDECK_AUTHORITY_EVIDENCE" "$PARTYDECK_AUTHORITY_ARTIFACTS"

export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode_26.4.1.app/Contents/Developer}"
xcodebuild -version > "$PARTYDECK_AUTHORITY_EVIDENCE/authority-xcode-version.log"
java -version 2> "$PARTYDECK_AUTHORITY_EVIDENCE/authority-java-version.log"
python3 - "$PARTYDECK_AUTHORITY_EVIDENCE" <<'PY'
from pathlib import Path
import re
import sys

evidence = Path(sys.argv[1])
if (evidence / "authority-xcode-version.log").read_text().splitlines()[0] != "Xcode 26.4.1":
    raise SystemExit("The authority framework probe is pinned to Xcode 26.4.1.")
if not re.search(r'version "21(?:[.\"]|$)', (evidence / "authority-java-version.log").read_text()):
    raise SystemExit("Set up JDK 21 before building the authority framework.")
PY

# The isolated qualification build reuses the real core and bridge sources. Its
# output directory is set in qualification/build.gradle.kts, outside shipping.
"$PARTYDECK_AUTHORITY_REPO/gradlew" -p "$PARTYDECK_AUTHORITY_REPO/godot/qualification" \
  --no-daemon --console=plain --stacktrace --max-workers=2 \
  :bridge:linkDebugFrameworkIosSimulatorArm64 \
  2>&1 | tee "$PARTYDECK_AUTHORITY_EVIDENCE/authority-framework-build.log"

test -s "$PARTYDECK_AUTHORITY_FRAMEWORK/PartyDeckGodotBridge"
test -s "$PARTYDECK_AUTHORITY_FRAMEWORK/Headers/PartyDeckGodotBridge.h"
test -s "$PARTYDECK_AUTHORITY_FRAMEWORK/Modules/module.modulemap"
plutil -lint "$PARTYDECK_AUTHORITY_FRAMEWORK/Info.plist"
xcrun lipo -archs "$PARTYDECK_AUTHORITY_FRAMEWORK/PartyDeckGodotBridge" \
  > "$PARTYDECK_AUTHORITY_EVIDENCE/authority-framework-architectures.log"
xcrun nm -g "$PARTYDECK_AUTHORITY_FRAMEWORK/PartyDeckGodotBridge" \
  > "$PARTYDECK_AUTHORITY_EVIDENCE/authority-framework-symbols.log"
cp "$PARTYDECK_AUTHORITY_FRAMEWORK/Headers/PartyDeckGodotBridge.h" \
  "$PARTYDECK_AUTHORITY_EVIDENCE/PartyDeckGodotBridge.h"
cp "$PARTYDECK_AUTHORITY_FRAMEWORK/Modules/module.modulemap" \
  "$PARTYDECK_AUTHORITY_EVIDENCE/PartyDeckGodotBridge.modulemap"
python3 - "$PARTYDECK_AUTHORITY_EVIDENCE/PartyDeckGodotBridge.h" <<'PY' | tee "$PARTYDECK_AUTHORITY_EVIDENCE/authority-header-check.log"
from pathlib import Path
import re
import sys

header = Path(sys.argv[1]).read_text()
required = (
    "IosQualificationFactory", "IosQualificationAuthority", "IosQualificationResult",
    "IosQualificationStatus", "IosQualificationRandomness", "IosQualificationLifecycle",
    "IosQualificationPhase", "IosQualificationOutcome", "PresentationMode",
)
for name in required:
    if not re.search(r"@interface\s+\w*" + re.escape(name) + r"\s*:", header):
        raise SystemExit(f"The generated framework header lacks the expected facade declaration: {name}")
print("All nine required facade/mode declarations exist in the actual generated header.")
PY

# This verifies only that Swift can import the generated framework/module. The
# authority's exported method spelling and runtime behavior have later gates.
printf '%s\n' 'import PartyDeckGodotBridge' \
  > "$PARTYDECK_AUTHORITY_EVIDENCE/authority-module-import.swift"
xcrun --sdk iphonesimulator swiftc -typecheck -swift-version 6 \
  -target arm64-apple-ios15.0-simulator \
  -sdk "$(xcrun --sdk iphonesimulator --show-sdk-path)" \
  -F "$(dirname -- "$PARTYDECK_AUTHORITY_FRAMEWORK")" \
  -module-cache-path "$PARTYDECK_AUTHORITY_ROOT/build/authority-module-cache" \
  "$PARTYDECK_AUTHORITY_EVIDENCE/authority-module-import.swift" \
  2>&1 | tee "$PARTYDECK_AUTHORITY_EVIDENCE/authority-module-import.log"
tar -czf "$PARTYDECK_AUTHORITY_ARCHIVE" \
  -C "$(dirname -- "$PARTYDECK_AUTHORITY_FRAMEWORK")" PartyDeckGodotBridge.framework

python3 - "$PARTYDECK_AUTHORITY_EVIDENCE" "$PARTYDECK_AUTHORITY_FRAMEWORK" "$PARTYDECK_AUTHORITY_ARCHIVE" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

evidence, framework, archive = map(Path, sys.argv[1:])
if (evidence / "authority-framework-architectures.log").read_text().strip() != "arm64":
    raise SystemExit("The authority framework does not contain only the requested ARM64 architecture.")

def receipt(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"sha256": digest.hexdigest(), "bytes": path.stat().st_size}

files = ("PartyDeckGodotBridge", "Headers/PartyDeckGodotBridge.h", "Modules/module.modulemap", "Info.plist")
result = {
    "stage": "authority_framework_compilation",
    "target": "iosSimulatorArm64",
    "configuration": "debugFramework",
    "framework": {name: receipt(framework / name) for name in files},
    "archive": {"name": archive.name, **receipt(archive)},
    "framework_compiled": True,
    "expected_facade_declarations_present": True,
    "swift_module_import_typechecked": True,
    "swift_authority_host_compiled": False,
    "ios_authority_runtime_executed": False,
    "kmp_factory_qualified": False,
}
(evidence / "authority-framework-result.json").write_text(json.dumps(result, indent=2) + "\n")
print("Retained the compiled Kotlin framework and its actual Objective-C export header.")
PY
