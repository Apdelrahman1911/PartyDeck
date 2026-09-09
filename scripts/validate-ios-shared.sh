#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != Darwin ]]; then
  printf '%s\n' 'iOS validation requires macOS with Xcode; use the Validate GitHub Actions workflow from Linux.' >&2
  exit 1
fi

PARTYDECK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARTYDECK_ROOT"
PARTYDECK_SIMULATOR_ID="$(python3 scripts/select-ios-simulator.py "$PARTYDECK_ROOT/build/ci/ios/shared-simulator.json")"

# Keep native compilation within the memory available on the ARM64 hosted runner.
# Specify the matching runtime for every native test task; Kotlin's default can
# otherwise choose a newer installed iOS runtime than the selected Xcode SDK.
./gradlew --stacktrace --console=plain --max-workers=2 \
  :core:iosSimulatorArm64Test --device "$PARTYDECK_SIMULATOR_ID" \
  :session:iosSimulatorArm64Test --device "$PARTYDECK_SIMULATOR_ID" \
  :transport:iosSimulatorArm64Test --device "$PARTYDECK_SIMULATOR_ID" \
  :games:iosSimulatorArm64Test --device "$PARTYDECK_SIMULATOR_ID" \
  :composeApp:iosSimulatorArm64Test --device "$PARTYDECK_SIMULATOR_ID" \
  :composeApp:linkDebugFrameworkIosArm64
