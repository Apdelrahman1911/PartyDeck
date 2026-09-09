#!/usr/bin/env bash
set -euo pipefail

PARTYDECK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARTYDECK_ROOT"
PARTYDECK_ANDROID_OUTPUT="$PARTYDECK_ROOT/build/ci/android"
PARTYDECK_ANDROID_SDK="${ANDROID_HOME:?Set ANDROID_HOME to the installed Android SDK.}"
PARTYDECK_EMULATOR_PORT="${PARTYDECK_EMULATOR_PORT:-5554}"
PARTYDECK_EMULATOR_SERIAL="emulator-$PARTYDECK_EMULATOR_PORT"
PARTYDECK_EMULATOR_PID=''
mkdir -p "$PARTYDECK_ANDROID_OUTPUT"

if [[ ! "$PARTYDECK_EMULATOR_PORT" =~ ^5[0-9]{3}$ ]] || (( PARTYDECK_EMULATOR_PORT < 5554 || PARTYDECK_EMULATOR_PORT > 5682 || PARTYDECK_EMULATOR_PORT % 2 != 0 )); then
  printf '%s\n' 'PARTYDECK_EMULATOR_PORT must be an even port from 5554 through 5682.' >&2
  exit 1
fi

"$PARTYDECK_ANDROID_SDK/emulator/emulator" -accel-check | tee "$PARTYDECK_ANDROID_OUTPUT/acceleration.log"
if [[ "$(uname -s)" != Linux || ! -r /dev/kvm || ! -w /dev/kvm ]]; then
  printf '%s\n' 'This bounded CI smoke requires Linux with accessible KVM acceleration.' >&2
  exit 1
fi
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
    timeout 15s adb -s "$PARTYDECK_EMULATOR_SERIAL" logcat -d -t 2000 > "$PARTYDECK_ANDROID_OUTPUT/emulator-final-logcat.log" 2>&1 || true
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
  -accel on -gpu swiftshader -memory 2048 -cores 2 \
  -no-window -no-audio -no-snapshot -no-boot-anim \
  -camera-back none -camera-front none \
  > "$PARTYDECK_ANDROID_OUTPUT/emulator.log" 2>&1 &
PARTYDECK_EMULATOR_PID=$!

python3 scripts/smoke-android-ui.py \
  --serial "$PARTYDECK_EMULATOR_SERIAL" \
  --apk androidApp/build/outputs/apk/debug/androidApp-debug.apk \
  --output "$PARTYDECK_ANDROID_OUTPUT"
