#!/usr/bin/env bash
# A bounded preview gate using the existing device-preparation and app helpers.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."

PARTYDECK_PREVIEW_OUTPUT="$PWD/build/ci/android-preview"
PARTYDECK_PREVIEW_SDK="${ANDROID_HOME:?Android SDK is required}"
PARTYDECK_PREVIEW_SERIAL=emulator-5554
PARTYDECK_PREVIEW_PID=''
export ANDROID_AVD_HOME="$PARTYDECK_PREVIEW_OUTPUT/avd"
mkdir -p "$ANDROID_AVD_HOME"
test -f androidApp/build/outputs/apk/debug/androidApp-debug.apk
test -r /dev/kvm
test -w /dev/kvm
if adb devices | awk 'NR > 1 { print $1 }' | grep -Fxq "$PARTYDECK_PREVIEW_SERIAL"; then
  printf '%s\n' 'The preview emulator serial is already in use.' >&2
  exit 1
fi

cleanup() {
  PARTYDECK_PREVIEW_STATUS=$?
  trap - EXIT
  if [[ -n "$PARTYDECK_PREVIEW_PID" ]]; then
    kill -TERM -- "-$PARTYDECK_PREVIEW_PID" 2>/dev/null || true
    sleep 2
    kill -KILL -- "-$PARTYDECK_PREVIEW_PID" 2>/dev/null || true
    wait "$PARTYDECK_PREVIEW_PID" 2>/dev/null || true
  fi
  exit "$PARTYDECK_PREVIEW_STATUS"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf 'no\n' | avdmanager create avd --name partydeck_preview_api36 \
  --package 'system-images;android-36;default;x86_64' --device pixel_7 \
  --path "$ANDROID_AVD_HOME/partydeck_preview_api36.avd" --force
python3 -B - "$ANDROID_AVD_HOME/partydeck_preview_api36.avd/config.ini" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
values = {'hw.lcd.width': '720', 'hw.lcd.height': '1600', 'hw.lcd.density': '280',
          'skin.name': '720x1600', 'skin.path': '720x1600'}
lines = [line for line in path.read_text().splitlines() if line.partition('=')[0].strip() not in values]
path.write_text('\n'.join(lines + [f'{key}={value}' for key, value in values.items()]) + '\n')
PY

PARTYDECK_PREVIEW_CORES="$(nproc)"
if (( PARTYDECK_PREVIEW_CORES > 4 )); then PARTYDECK_PREVIEW_CORES=4; fi
setsid "$PARTYDECK_PREVIEW_SDK/emulator/emulator" \
  -avd partydeck_preview_api36 -port 5554 -accel on -gpu swangle \
  -memory 3072 -cores "$PARTYDECK_PREVIEW_CORES" \
  -no-window -no-audio -no-snapshot -no-boot-anim \
  -camera-back none -camera-front none \
  > "$PARTYDECK_PREVIEW_OUTPUT/emulator.log" 2>&1 &
PARTYDECK_PREVIEW_PID=$!
python3 -B scripts/prepare-android-emulator.py \
  --serial "$PARTYDECK_PREVIEW_SERIAL" --output "$PARTYDECK_PREVIEW_OUTPUT/preparation"
python3 -B scripts/smoke-android-preview.py \
  --serial "$PARTYDECK_PREVIEW_SERIAL" \
  --apk androidApp/build/outputs/apk/debug/androidApp-debug.apk \
  --output "$PARTYDECK_PREVIEW_OUTPUT/runtime"
