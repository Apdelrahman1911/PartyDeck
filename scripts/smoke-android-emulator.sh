#!/usr/bin/env bash
set -euo pipefail

PARTYDECK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARTYDECK_ROOT"
PARTYDECK_ANDROID_OUTPUT="$PARTYDECK_ROOT/build/ci/android"
PARTYDECK_ANDROID_SDK="${ANDROID_HOME:?Set ANDROID_HOME to the installed Android SDK.}"
PARTYDECK_EMULATOR_PORT="${PARTYDECK_EMULATOR_PORT:-5554}"
PARTYDECK_EMULATOR_SERIAL="emulator-$PARTYDECK_EMULATOR_PORT"
PARTYDECK_EMULATOR_PID=''
mkdir -p "$PARTYDECK_ANDROID_OUTPUT/debug" "$PARTYDECK_ANDROID_OUTPUT/optimized-test-signed"

if [[ ! "$PARTYDECK_EMULATOR_PORT" =~ ^5[0-9]{3}$ ]] || (( PARTYDECK_EMULATOR_PORT < 5554 || PARTYDECK_EMULATOR_PORT > 5682 || PARTYDECK_EMULATOR_PORT % 2 != 0 )); then
  printf '%s\n' 'PARTYDECK_EMULATOR_PORT must be an even port from 5554 through 5682.' >&2
  exit 1
fi

"$PARTYDECK_ANDROID_SDK/emulator/emulator" -accel-check | tee "$PARTYDECK_ANDROID_OUTPUT/acceleration.log"
if [[ "$(uname -s)" != Linux || ! -r /dev/kvm || ! -w /dev/kvm ]]; then
  printf '%s\n' 'This bounded CI smoke requires Linux with accessible KVM acceleration.' >&2
  exit 1
fi
PARTYDECK_EMULATOR_CORES="$(nproc)"
if (( PARTYDECK_EMULATOR_CORES > 4 )); then
  PARTYDECK_EMULATOR_CORES=4
fi
free -m > "$PARTYDECK_ANDROID_OUTPUT/host-memory-before-emulator.log"
lscpu > "$PARTYDECK_ANDROID_OUTPUT/host-cpu.log"
ps -eo pid,ppid,comm,rss,pcpu --sort=-rss > "$PARTYDECK_ANDROID_OUTPUT/host-process-memory.log"
PARTYDECK_ADB_DEVICES="$(adb devices)"
while IFS= read -r PARTYDECK_DEVICE_LINE; do
  if [[ "${PARTYDECK_DEVICE_LINE%%[[:space:]]*}" == "$PARTYDECK_EMULATOR_SERIAL" ]]; then
    printf 'The selected emulator serial is already registered (including offline): %s\n' "$PARTYDECK_EMULATOR_SERIAL" >&2
    exit 1
  fi
done <<< "$PARTYDECK_ADB_DEVICES"

cleanup() {
  PARTYDECK_SMOKE_STATUS=$?
  trap - EXIT
  if [[ -n "$PARTYDECK_EMULATOR_PID" ]]; then
    # Per-variant Python diagnostics retain redacted logcat and UI evidence.
    # Do not also save a raw dump that could contain a test invitation URI.
    free -m > "$PARTYDECK_ANDROID_OUTPUT/host-memory-after-smoke.log" || true
    # The emulator has its own process group. Never send an emu-kill command to
    # a serial that could belong to another process after a startup failure.
    kill -TERM -- "-$PARTYDECK_EMULATOR_PID" 2>/dev/null || true
    sleep 2
    kill -KILL -- "-$PARTYDECK_EMULATOR_PID" 2>/dev/null || true
    wait "$PARTYDECK_EMULATOR_PID" 2>/dev/null || true
  fi
  exit "$PARTYDECK_SMOKE_STATUS"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

export ANDROID_AVD_HOME="$PARTYDECK_ANDROID_OUTPUT/avd"
mkdir -p "$ANDROID_AVD_HOME"
printf 'no\n' | avdmanager create avd \
  --name partydeck_ci_api36 \
  --package 'system-images;android-36;default;x86_64' \
  --device pixel_7 \
  --path "$ANDROID_AVD_HOME/partydeck_ci_api36.avd" \
  --force

setsid "$PARTYDECK_ANDROID_SDK/emulator/emulator" \
  -avd partydeck_ci_api36 \
  -port "$PARTYDECK_EMULATOR_PORT" \
  -accel on -gpu swiftshader -memory 3072 -cores "$PARTYDECK_EMULATOR_CORES" \
  -no-window -no-audio -no-snapshot -no-boot-anim \
  -camera-back none -camera-front none \
  > "$PARTYDECK_ANDROID_OUTPUT/emulator.log" 2>&1 &
PARTYDECK_EMULATOR_PID=$!

# Keep first-boot OS initialization outside app acceptance. The helper preserves
# an observed System UI ANR and permits only one empty-AVD reboot for that cause.
# Every other preparation failure stops both APK runs; neither APK is retried.
python3 scripts/prepare-android-emulator.py \
  --serial "$PARTYDECK_EMULATOR_SERIAL" \
  --output "$PARTYDECK_ANDROID_OUTPUT/preparation"

PARTYDECK_DEBUG_STATUS=0
python3 scripts/smoke-android-ui.py \
  --serial "$PARTYDECK_EMULATOR_SERIAL" \
  --apk androidApp/build/outputs/apk/debug/androidApp-debug.apk \
  --variant debug \
  --output "$PARTYDECK_ANDROID_OUTPUT/debug" || PARTYDECK_DEBUG_STATUS=$?

PARTYDECK_OPTIMIZED_STATUS=0
if ./scripts/prepare-android-runtime-apk.sh; then
  # The optimized copy has its own disposable certificate. Remove any debug
  # install first; Python's install/clear/launch assertions verify replacement.
  timeout 30s adb -s "$PARTYDECK_EMULATOR_SERIAL" uninstall dev.partydeck.app \
    > "$PARTYDECK_ANDROID_OUTPUT/optimized-test-signed/remove-debug.log" 2>&1 || true
  python3 scripts/smoke-android-ui.py \
    --serial "$PARTYDECK_EMULATOR_SERIAL" \
    --apk "$PARTYDECK_ANDROID_OUTPUT/packages/PartyDeck-release-ci-test-signed.apk" \
    --variant optimized-test-signed \
    --output "$PARTYDECK_ANDROID_OUTPUT/optimized-test-signed" || PARTYDECK_OPTIMIZED_STATUS=$?
else
  PARTYDECK_OPTIMIZED_STATUS=$?
fi

python3 - "$PARTYDECK_ANDROID_OUTPUT" "$PARTYDECK_DEBUG_STATUS" "$PARTYDECK_OPTIMIZED_STATUS" <<'PY'
import json
from pathlib import Path
import sys

output = Path(sys.argv[1])
debug_status, optimized_status = map(int, sys.argv[2:4])
(output / "runtime-variants.json").write_text(json.dumps({
    "sameEmulatorBoot": True,
    "debugExitCode": debug_status,
    "optimizedTestSignedExitCode": optimized_status,
    "passed": debug_status == 0 and optimized_status == 0,
}, indent=2) + "\n")
PY
if (( PARTYDECK_DEBUG_STATUS != 0 || PARTYDECK_OPTIMIZED_STATUS != 0 )); then
  printf 'Android runtime validation failed: debug=%s optimized-test-signed=%s\n' \
    "$PARTYDECK_DEBUG_STATUS" "$PARTYDECK_OPTIMIZED_STATUS" >&2
  exit 1
fi
