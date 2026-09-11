#!/usr/bin/env bash
set -euo pipefail

PARTYDECK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARTYDECK_ROOT"
PARTYDECK_ANDROID_OUTPUT="$PARTYDECK_ROOT/build/ci/android"
PARTYDECK_ANDROID_SDK="${ANDROID_HOME:?Set ANDROID_HOME to the installed Android SDK.}"
PARTYDECK_ANDROID_API="${PARTYDECK_ANDROID_API:-35}"
PARTYDECK_ANDROID_GODOT_SESSION_SMOKE="${PARTYDECK_ANDROID_GODOT_SESSION_SMOKE:-0}"
PARTYDECK_ANDROID_GODOT_ADAPTIVE_SMOKE="${PARTYDECK_ANDROID_GODOT_ADAPTIVE_SMOKE:-0}"
PARTYDECK_SOURCE_REVISION="${PARTYDECK_SOURCE_REVISION:-${GITHUB_SHA:-}}"
if [[ "$PARTYDECK_ANDROID_API" != 35 && "$PARTYDECK_ANDROID_API" != 36 ]]; then
  printf '%s\n' 'PARTYDECK_ANDROID_API must be 35 or 36.' >&2
  exit 1
fi
if [[ "$PARTYDECK_ANDROID_GODOT_SESSION_SMOKE" != 0 && "$PARTYDECK_ANDROID_GODOT_SESSION_SMOKE" != 1 ]]; then
  printf '%s\n' 'PARTYDECK_ANDROID_GODOT_SESSION_SMOKE must be 0 or 1.' >&2
  exit 1
fi
if [[ "$PARTYDECK_ANDROID_GODOT_ADAPTIVE_SMOKE" != 0 && "$PARTYDECK_ANDROID_GODOT_ADAPTIVE_SMOKE" != 1 ]]; then
  printf '%s\n' 'PARTYDECK_ANDROID_GODOT_ADAPTIVE_SMOKE must be 0 or 1.' >&2
  exit 1
fi

select_godot_shipping_smoke() {
  python3 -B - <<'PY'
from pathlib import Path
import sys

sys.path.insert(0, str(Path("scripts").resolve()))
from android_godot_activation import parse_build_expectation

with Path('build/ci/android/godot-activation-build.json').open('rb') as stream:
    raw = stream.read(4097)
if len(raw) > 4096:
    raise ValueError('The activation build receipt is oversized.')
expected = parse_build_expectation(raw)
if expected['profile'] != 'shipping':
    raise ValueError('Ordinary Android smoke requires a shipping activation build receipt.')
if expected['modes'] not in ([], ['2d', '3d']):
    raise ValueError('Shipping smoke requires both modes or the empty shipping baseline.')
print('1' if expected['modes'] else '0')
PY
}

PARTYDECK_ANDROID_GODOT_SHIPPING_SMOKE=0
if [[ "$PARTYDECK_ANDROID_GODOT_SESSION_SMOKE" == 0 && "$PARTYDECK_ANDROID_GODOT_ADAPTIVE_SMOKE" == 0 ]]; then
  # Select from the actual build receipt; qualification and adaptive keep their own routes.
  PARTYDECK_ANDROID_GODOT_SHIPPING_SMOKE="$(select_godot_shipping_smoke)"
  if [[ "$PARTYDECK_ANDROID_GODOT_SHIPPING_SMOKE" == 1 ]]; then
    if [[ ! "$PARTYDECK_SOURCE_REVISION" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]]; then
      printf '%s\n' 'Shipping smoke requires the full source revision used to build these APKs.' >&2
      exit 1
    fi
    test -f scripts/smoke-android-godot-shipping.py
  fi
fi

if [[ "$PARTYDECK_ANDROID_GODOT_ADAPTIVE_SMOKE" == 1 ]]; then
  if [[ "$PARTYDECK_ANDROID_API" != 36 || "$PARTYDECK_ANDROID_GODOT_SESSION_SMOKE" != 0 || \
        "$PARTYDECK_SOURCE_REVISION" != "${GITHUB_SHA:-}" ]]; then
    printf '%s\n' 'Adaptive CI requires API36, the workflow source revision and its own execution path.' >&2
    exit 1
  fi
  PARTYDECK_ADAPTIVE_VARIANT="${PARTYDECK_ADAPTIVE_VARIANT:?Set the exact adaptive APK variant.}"
  PARTYDECK_ADAPTIVE_FONT_SCALE="${PARTYDECK_ADAPTIVE_FONT_SCALE:?Set the adaptive font scale.}"
  if [[ "$PARTYDECK_ADAPTIVE_VARIANT" != debug && "$PARTYDECK_ADAPTIVE_VARIANT" != optimized-test-signed ]] || \
     [[ "$PARTYDECK_ADAPTIVE_FONT_SCALE" != 1.0 && "$PARTYDECK_ADAPTIVE_FONT_SCALE" != 2.0 ]]; then
    printf '%s\n' 'Adaptive CI requires debug/optimized-test-signed and 1.0/2.0 text.' >&2
    exit 1
  fi
  PARTYDECK_ADAPTIVE_BUNDLE="$PARTYDECK_ANDROID_OUTPUT/adaptive-inputs"
  PARTYDECK_ADAPTIVE_OUTPUT="$PARTYDECK_ANDROID_OUTPUT/godot-adaptive"
  # Check the producer's exact same-run inputs before starting an emulator.
  python3 -B scripts/android_godot_adaptive_inputs.py verify \
    --bundle "$PARTYDECK_ADAPTIVE_BUNDLE" \
    --output "$PARTYDECK_ADAPTIVE_OUTPUT/package-inputs" \
    --manifest-sha256 "${PARTYDECK_ADAPTIVE_MANIFEST_SHA256:?Set the producer input manifest SHA-256.}"
fi
if [[ "$PARTYDECK_ANDROID_GODOT_SESSION_SMOKE" == 1 ]]; then
  if [[ ! "$PARTYDECK_SOURCE_REVISION" =~ ^[0-9a-f]{40}$ ]]; then
    printf '%s\n' 'Godot session smoke requires the full source revision used to build these APKs.' >&2
    exit 1
  fi
  test -f scripts/smoke-android-godot-session.py
  mkdir -p "$PARTYDECK_ANDROID_OUTPUT/godot-session"
  # Verify the existing build's pack without starting or rebuilding the engine.
  python3 -B godot/tools/renderer.py check-pack \
    --pack godot/qualification/build/renderer/partydeck-last-light.pck \
    > "$PARTYDECK_ANDROID_OUTPUT/godot-session/source-pack-check.log" 2>&1
fi
PARTYDECK_AVD_NAME="partydeck_ci_api$PARTYDECK_ANDROID_API"
PARTYDECK_EMULATOR_PORT="${PARTYDECK_EMULATOR_PORT:-5554}"
PARTYDECK_EMULATOR_SERIAL="emulator-$PARTYDECK_EMULATOR_PORT"
PARTYDECK_EMULATOR_PID=''
mkdir -p "$PARTYDECK_ANDROID_OUTPUT/debug" "$PARTYDECK_ANDROID_OUTPUT/optimized-test-signed"

if [[ ! "$PARTYDECK_EMULATOR_PORT" =~ ^5[0-9]{3}$ ]] || (( PARTYDECK_EMULATOR_PORT < 5554 || PARTYDECK_EMULATOR_PORT > 5682 || PARTYDECK_EMULATOR_PORT % 2 != 0 )); then
  printf '%s\n' 'PARTYDECK_EMULATOR_PORT must be an even port from 5554 through 5682.' >&2
  exit 1
fi

"$PARTYDECK_ANDROID_SDK/emulator/emulator" -accel-check | tee "$PARTYDECK_ANDROID_OUTPUT/acceleration.log"
"$PARTYDECK_ANDROID_SDK/emulator/emulator" -help-gpu > "$PARTYDECK_ANDROID_OUTPUT/graphics-options.log"
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
cp "$PARTYDECK_ANDROID_SDK/system-images/android-$PARTYDECK_ANDROID_API/default/x86_64/source.properties" \
  "$PARTYDECK_ANDROID_OUTPUT/system-image-source.log"
printf 'no\n' | avdmanager create avd \
  --name "$PARTYDECK_AVD_NAME" \
  --package "system-images;android-$PARTYDECK_ANDROID_API;default;x86_64" \
  --device pixel_7 \
  --path "$ANDROID_AVD_HOME/$PARTYDECK_AVD_NAME.avd" \
  --force

# Reduce software-rendered pixels while retaining the Pixel 7 logical viewport.
# Numeric skin.path takes precedence over skin.name, so keep both in agreement.
python3 - "$ANDROID_AVD_HOME/$PARTYDECK_AVD_NAME.avd/config.ini" "$PARTYDECK_ANDROID_OUTPUT" "$PARTYDECK_ANDROID_API" <<'PY'
import json
from pathlib import Path
import sys

config, output = map(Path, sys.argv[1:3])
values = {
    "hw.lcd.width": "720", "hw.lcd.height": "1600", "hw.lcd.density": "280",
    "skin.name": "720x1600", "skin.path": "720x1600",
}
lines = [line for line in config.read_text().splitlines() if line.partition("=")[0].strip() not in values]
lines.extend(f"{key}={value}" for key, value in values.items())
config.write_text("\n".join(lines) + "\n")
(output / "avd-config.log").write_text(config.read_text())
(output / "display-configuration.json").write_text(json.dumps({
    "expectedPhysicalSize": [720, 1600], "expectedDensityDpi": 280,
    "logicalSizeDp": [720 * 160 / 280, 1600 * 160 / 280],
    "expectedAndroidApi": int(sys.argv[3]), "guestApiVerified": False, "displayVerified": False,
}, indent=2) + "\n")
PY

setsid "$PARTYDECK_ANDROID_SDK/emulator/emulator" \
  -avd "$PARTYDECK_AVD_NAME" \
  -port "$PARTYDECK_EMULATOR_PORT" \
  -accel on -gpu swangle -memory 3072 -cores "$PARTYDECK_EMULATOR_CORES" \
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

# Prove the booted display matches the configuration before either APK starts.
python3 - "$PARTYDECK_EMULATOR_SERIAL" "$PARTYDECK_ANDROID_OUTPUT" <<'PY'
import json
from pathlib import Path
import re
import subprocess
import sys

serial, output = sys.argv[1], Path(sys.argv[2])
report = output / "display-configuration.json"
result = json.loads(report.read_text())
try:
    api = subprocess.run(["adb", "-s", serial, "shell", "getprop", "ro.build.version.sdk"],
                         capture_output=True, text=True, check=True, timeout=20).stdout
    (output / "android-api.log").write_text(api)
    result["actualAndroidApi"] = int(api.strip())
    result["guestApiVerified"] = result["actualAndroidApi"] == result["expectedAndroidApi"]
    for command in ("size", "density"):
        value = subprocess.run(["adb", "-s", serial, "shell", "wm", command],
                               capture_output=True, text=True, check=True, timeout=20).stdout
        (output / f"display-{command}.log").write_text(value)
        result[f"actual{command.title()}Output"] = value.strip()
    sizes = [list(map(int, pair)) for pair in re.findall(
        r"(?:Physical|Override) size:\s*(\d+)x(\d+)", result["actualSizeOutput"])]
    densities = list(map(int, re.findall(r"(?:Physical|Override) density:\s*(\d+)", result["actualDensityOutput"])))
    physical_size = re.search(r"^Physical size:\s*\d+x\d+\s*$", result["actualSizeOutput"], re.MULTILINE)
    physical_density = re.search(r"^Physical density:\s*\d+\s*$", result["actualDensityOutput"], re.MULTILINE)
    result["displayVerified"] = bool(physical_size and physical_density and sizes and densities) and all(
        size == result["expectedPhysicalSize"] for size in sizes
    ) and all(density == result["expectedDensityDpi"] for density in densities)
finally:
    report.write_text(json.dumps(result, indent=2) + "\n")
if not result["displayVerified"] or not result["guestApiVerified"]:
    raise SystemExit("Android guest API or display does not match the expected configuration; APK checks cannot start.")
PY

if [[ "$PARTYDECK_ANDROID_GODOT_ADAPTIVE_SMOKE" == 1 ]]; then
  # Preserve the exact installed SDK image files and the observed guest identity.
  python3 - "$PARTYDECK_EMULATOR_SERIAL" "$PARTYDECK_ANDROID_SDK" "$PARTYDECK_ADAPTIVE_OUTPUT" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys

serial, sdk, output = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
image = sdk / 'system-images/android-36/default/x86_64'
files = []
for path in sorted(image.rglob('*')):
    if path.is_file():
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        files.append({'path': str(path.relative_to(image)), 'bytes': path.stat().st_size, 'sha256': digest})
guest = {}
for key in ('ro.build.fingerprint', 'ro.build.version.sdk', 'ro.build.version.release',
            'ro.build.version.incremental', 'ro.build.type', 'ro.debuggable', 'ro.product.cpu.abi'):
    value = subprocess.run(['adb', '-s', serial, 'shell', 'getprop', key],
                           capture_output=True, text=True, check=True, timeout=20)
    guest[key] = value.stdout.strip()
for name in ('source.properties', 'package.xml'):
    path = sdk / 'emulator' / name
    if path.is_file():
        (output / ('emulator-' + name)).write_bytes(path.read_bytes())
(output / 'device-provenance.json').write_text(json.dumps({
    'requestedSystemImage': 'system-images;android-36;default;x86_64',
    'sdkImageFiles': files, 'guestProperties': guest, 'serial': serial,
    'api35AdaptiveScope': 'Separate; no compatibility or qualification claim.',
}, indent=2) + '\n')
if not files or guest['ro.build.version.sdk'] != '36' or not guest['ro.build.fingerprint']:
    raise SystemExit('Cannot attribute the actual API36 emulator image and guest.')
PY
  PARTYDECK_ADAPTIVE_APK="$PARTYDECK_ADAPTIVE_BUNDLE/androidApp-debug.apk"
  if [[ "$PARTYDECK_ADAPTIVE_VARIANT" == optimized-test-signed ]]; then
    PARTYDECK_ADAPTIVE_APK="$PARTYDECK_ADAPTIVE_BUNDLE/PartyDeck-release-ci-test-signed.apk"
  fi
  PARTYDECK_ADAPTIVE_STATUS=0
  python3 -B scripts/smoke_android_godot_adaptive.py \
    --session-checker scripts/smoke-android-godot-session.py \
    --serial "$PARTYDECK_EMULATOR_SERIAL" --apk "$PARTYDECK_ADAPTIVE_APK" \
    --source-revision "$PARTYDECK_SOURCE_REVISION" --variant "$PARTYDECK_ADAPTIVE_VARIANT" \
    --font-scale "$PARTYDECK_ADAPTIVE_FONT_SCALE" --modes 2d 3d \
    --output "$PARTYDECK_ADAPTIVE_OUTPUT/runtime" || PARTYDECK_ADAPTIVE_STATUS=$?
  python3 - "$PARTYDECK_ADAPTIVE_OUTPUT" "$PARTYDECK_ADAPTIVE_STATUS" \
    "$PARTYDECK_ADAPTIVE_VARIANT" "$PARTYDECK_ADAPTIVE_FONT_SCALE" <<'PY'
import json
from pathlib import Path
import sys

output, status, variant, font = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4]
(output / 'execution.json').write_text(json.dumps({
    'runnerExitCode': status, 'variant': variant, 'fontScale': font, 'modes': ['2d', '3d'],
    'androidApi': 36, 'unsupported': status == 2,
    'scope': 'Adaptive automated scope only; original pixel privacy review remains required.',
}, indent=2) + '\n')
PY
  # Exit 2 remains unsupported and fails the job; ordinary baseline flows do not run here.
  exit "$PARTYDECK_ADAPTIVE_STATUS"
fi

run_godot_shipping_phase() {
  local phase="$1" variant="$2" apk="$3" output="$4"
  local arguments=(--apk "$apk" --variant "$variant" --source-revision "$PARTYDECK_SOURCE_REVISION"
    --build-expectation build/ci/android/godot-activation-build.json
    --renderer-pack godot/qualification/build/renderer/partydeck-last-light.pck
    --inputs "$output/build-inputs.json")
  if [[ "$variant" == optimized-test-signed ]]; then
    arguments+=(--signing-receipt "$PARTYDECK_ANDROID_OUTPUT/packages/runtime-package.json"
      --unsigned-apk androidApp/build/outputs/apk/release/androidApp-release-unsigned.apk)
  fi
  mkdir -p "$output" || return "$?"
  case "$phase" in
    record-inputs)
      timeout --signal=TERM --kill-after=15s 3m \
        python3 -B scripts/smoke-android-godot-shipping.py record-inputs "${arguments[@]}" \
        2>&1 | tee "$output/record-inputs-command.log"
      ;;
    run)
      timeout --signal=TERM --kill-after=15s 20m \
        python3 -B scripts/smoke-android-godot-shipping.py run "${arguments[@]}" \
          --serial "$PARTYDECK_EMULATOR_SERIAL" --output "$output/run" --font-scale 1.0 \
        2>&1 | tee "$output/command.log"
      ;;
    *) return 2 ;;
  esac
}

run_godot_session_smoke() {
  local variant="$1" apk="$2" output="$3"
  shift 3
  mkdir -p "$output" || return "$?"
  python3 - "$variant" "$apk" "$output" "$PARTYDECK_SOURCE_REVISION" <<'PY' || return "$?"
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import os
import subprocess

sys.path.insert(0, str(Path("scripts").resolve()))
from android_godot_activation import parse_build_expectation, parse_packaged_manifest, require_qualification_match

variant, apk_name, output_name, revision = sys.argv[1:]
apk, output = Path(apk_name), Path(output_name)
pack = Path('godot/qualification/build/renderer/partydeck-last-light.pck')

def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    return value.hexdigest()

record = {'variant': variant, 'apk': str(apk), 'sourceRevision': revision,
          'sourceRevisionProvenance': 'caller-supplied build revision', 'verified': False}
try:
    record['apkSha256'] = digest(apk)
    record['packSha256'] = digest(pack)
    with zipfile.ZipFile(apk) as archive:
        entry = 'assets/partydeck-last-light.pck'
        if archive.namelist().count(entry) != 1:
            raise RuntimeError('The production APK must contain exactly one renderer PCK.')
        record['embeddedPackSha256'] = hashlib.sha256(archive.read(entry)).hexdigest()
    if record['embeddedPackSha256'] != record['packSha256']:
        raise RuntimeError('The production APK differs from the source-checked renderer pack.')
    # The Gradle receipt is intent; decode and compare the actual APK before native execution.
    expectation = Path('build/ci/android/godot-activation-build.json')
    expected_bytes = expectation.read_bytes()
    (output / 'activation-build-expectation.json').write_bytes(expected_bytes)
    record['activation'] = {'verified': False, 'expectationSha256': hashlib.sha256(expected_bytes).hexdigest()}
    record['activation']['expected'] = parse_build_expectation(expected_bytes)
    analyzer = Path(os.environ['ANDROID_HOME']) / 'cmdline-tools/latest/bin/apkanalyzer'
    command = [str(analyzer), 'manifest', 'print', str(apk)]
    manifest = subprocess.run(command, capture_output=True, timeout=60)
    (output / 'packaged-manifest.xml').write_bytes(manifest.stdout)
    (output / 'packaged-manifest-error.log').write_bytes(manifest.stderr)
    record['activation']['manifestCommand'] = command
    record['activation']['manifestCommandExitCode'] = manifest.returncode
    record['activation']['manifestSha256'] = hashlib.sha256(manifest.stdout).hexdigest()
    if manifest.returncode != 0:
        raise RuntimeError('Cannot decode the actual production APK manifest.')
    record['activation']['packaged'] = parse_packaged_manifest(manifest.stdout)
    require_qualification_match(record['activation']['expected'], record['activation']['packaged'], '2d,3d')
    if digest(apk) != record['apkSha256']:
        raise RuntimeError('The APK changed during packaged activation verification.')
    record['activation']['verified'] = True
    if variant == 'optimized-test-signed':
        unsigned = Path('androidApp/build/outputs/apk/release/androidApp-release-unsigned.apk')
        signing = json.loads(Path('build/ci/android/packages/runtime-package.json').read_text())
        record['originalUnsignedSha256'] = digest(unsigned)
        if (Path(signing['runtimeApk']).resolve() != apk.resolve()
                or Path(signing['originalUnsignedApk']).resolve() != unsigned.resolve()
                or signing['runtimeApkSha256'] != record['apkSha256']
                or signing['originalUnsignedSha256'] != record['originalUnsignedSha256']
                or signing['signingIdentity'] != 'disposable-ci-test-key'
                or signing['distributionSigned'] is not False):
            raise RuntimeError('The optimized APK does not match its CI signing receipt.')
        record['certificateSha256'] = signing['certificateSha256']
    record['verified'] = True
except Exception as error:
    record['error'] = f'{type(error).__name__}: {error}'
    raise
finally:
    (output / 'package-inputs.json').write_text(json.dumps(record, indent=2) + '\n')
PY
  # Both modes now include the full Standard-hand and lifecycle sequence.
  # Bound the cumulative run separately from each unchanged scenario deadline.
  local engine_arguments=() runtime_timeout=20m
  if [[ "$PARTYDECK_ANDROID_API" == 36 ]]; then
    # The qualified API36 path owns the original package/PCK/activation receipt.
    # Invoke the separate real-engine practice scenario for both APK variants.
    engine_arguments=(--engine-gameplay --engine-package-inputs "$output/package-inputs.json")
  fi
  timeout --signal=TERM --kill-after=15s "$runtime_timeout" \
    python3 -B scripts/smoke-android-godot-session.py \
      --serial "$PARTYDECK_EMULATOR_SERIAL" --apk "$apk" --output "$output/runtime" \
      --source-revision "$PARTYDECK_SOURCE_REVISION" --variant "$variant" \
      --modes 2d 3d --font-scale 1.0 "${engine_arguments[@]}" "$@" 2>&1 | tee "$output/command.log"
}

PARTYDECK_DEBUG_STATUS=0
PARTYDECK_SHIPPING_DEBUG_INPUT_STATUS=''
PARTYDECK_SHIPPING_DEBUG_STATUS=''
PARTYDECK_SHIPPING_OPTIMIZED_INPUT_STATUS=''
PARTYDECK_SHIPPING_OPTIMIZED_STATUS=''
if [[ "$PARTYDECK_ANDROID_GODOT_SHIPPING_SMOKE" == 1 ]]; then
  # Bind debug build outputs before any variant UI smoke can run.
  PARTYDECK_SHIPPING_DEBUG_INPUT_STATUS=0
  run_godot_shipping_phase record-inputs debug androidApp/build/outputs/apk/debug/androidApp-debug.apk \
    "$PARTYDECK_ANDROID_OUTPUT/godot-shipping/debug" || PARTYDECK_SHIPPING_DEBUG_INPUT_STATUS=$?
fi
python3 scripts/smoke-android-ui.py \
  --serial "$PARTYDECK_EMULATOR_SERIAL" \
  --apk androidApp/build/outputs/apk/debug/androidApp-debug.apk \
  --variant debug \
  --output "$PARTYDECK_ANDROID_OUTPUT/debug" || PARTYDECK_DEBUG_STATUS=$?

PARTYDECK_GODOT_DEBUG_STATUS=''
PARTYDECK_GODOT_OPTIMIZED_STATUS=''
if [[ "$PARTYDECK_ANDROID_GODOT_SESSION_SMOKE" == 1 ]]; then
  PARTYDECK_GODOT_DEBUG_STATUS=0
  run_godot_session_smoke debug androidApp/build/outputs/apk/debug/androidApp-debug.apk \
    "$PARTYDECK_ANDROID_OUTPUT/godot-session/debug" || PARTYDECK_GODOT_DEBUG_STATUS=$?
fi
if [[ "$PARTYDECK_ANDROID_GODOT_SHIPPING_SMOKE" == 1 && "$PARTYDECK_SHIPPING_DEBUG_INPUT_STATUS" == 0 ]]; then
  PARTYDECK_SHIPPING_DEBUG_STATUS=0
  run_godot_shipping_phase run debug androidApp/build/outputs/apk/debug/androidApp-debug.apk \
    "$PARTYDECK_ANDROID_OUTPUT/godot-shipping/debug" || PARTYDECK_SHIPPING_DEBUG_STATUS=$?
fi

PARTYDECK_OPTIMIZED_STATUS=0
if ./scripts/prepare-android-runtime-apk.sh; then
  if [[ "$PARTYDECK_ANDROID_GODOT_SHIPPING_SMOKE" == 1 ]]; then
    # Only the newly signed optimized copy can produce this variant's input receipt.
    PARTYDECK_SHIPPING_OPTIMIZED_INPUT_STATUS=0
    run_godot_shipping_phase record-inputs optimized-test-signed \
      "$PARTYDECK_ANDROID_OUTPUT/packages/PartyDeck-release-ci-test-signed.apk" \
      "$PARTYDECK_ANDROID_OUTPUT/godot-shipping/optimized-test-signed" || PARTYDECK_SHIPPING_OPTIMIZED_INPUT_STATUS=$?
  fi
  # The optimized copy has its own disposable certificate. Remove any debug
  # install first; Python's install/clear/launch assertions verify replacement.
  timeout 30s adb -s "$PARTYDECK_EMULATOR_SERIAL" uninstall dev.partydeck.app \
    > "$PARTYDECK_ANDROID_OUTPUT/optimized-test-signed/remove-debug.log" 2>&1 || true
  python3 scripts/smoke-android-ui.py \
    --serial "$PARTYDECK_EMULATOR_SERIAL" \
    --apk "$PARTYDECK_ANDROID_OUTPUT/packages/PartyDeck-release-ci-test-signed.apk" \
    --variant optimized-test-signed \
    --output "$PARTYDECK_ANDROID_OUTPUT/optimized-test-signed" || PARTYDECK_OPTIMIZED_STATUS=$?
  if [[ "$PARTYDECK_ANDROID_GODOT_SESSION_SMOKE" == 1 ]]; then
    PARTYDECK_GODOT_OPTIMIZED_STATUS=0
    # This APK is not debuggable. Omitting its same-UID kill case is explicit;
    # the debug invocation must prove that case or return its nonzero status.
    run_godot_session_smoke optimized-test-signed \
      "$PARTYDECK_ANDROID_OUTPUT/packages/PartyDeck-release-ci-test-signed.apk" \
      "$PARTYDECK_ANDROID_OUTPUT/godot-session/optimized-test-signed" \
      --skip-renderer-death || PARTYDECK_GODOT_OPTIMIZED_STATUS=$?
  fi
  if [[ "$PARTYDECK_ANDROID_GODOT_SHIPPING_SMOKE" == 1 && "$PARTYDECK_SHIPPING_OPTIMIZED_INPUT_STATUS" == 0 ]]; then
    PARTYDECK_SHIPPING_OPTIMIZED_STATUS=0
    run_godot_shipping_phase run optimized-test-signed \
      "$PARTYDECK_ANDROID_OUTPUT/packages/PartyDeck-release-ci-test-signed.apk" \
      "$PARTYDECK_ANDROID_OUTPUT/godot-shipping/optimized-test-signed" || PARTYDECK_SHIPPING_OPTIMIZED_STATUS=$?
  fi
else
  PARTYDECK_OPTIMIZED_STATUS=$?
fi

python3 - "$PARTYDECK_ANDROID_OUTPUT" "$PARTYDECK_DEBUG_STATUS" "$PARTYDECK_OPTIMIZED_STATUS" \
  "$PARTYDECK_ANDROID_GODOT_SESSION_SMOKE" "$PARTYDECK_GODOT_DEBUG_STATUS" "$PARTYDECK_GODOT_OPTIMIZED_STATUS" \
  "$PARTYDECK_ANDROID_GODOT_SHIPPING_SMOKE" "$PARTYDECK_SHIPPING_DEBUG_INPUT_STATUS" "$PARTYDECK_SHIPPING_DEBUG_STATUS" \
  "$PARTYDECK_SHIPPING_OPTIMIZED_INPUT_STATUS" "$PARTYDECK_SHIPPING_OPTIMIZED_STATUS" <<'PY'
import json
from pathlib import Path
import sys

output = Path(sys.argv[1])
debug_status, optimized_status = map(int, sys.argv[2:4])
godot_requested = sys.argv[4] == '1'
godot_debug, godot_optimized = (int(value) if value else None for value in sys.argv[5:7])
godot_passed = not godot_requested or (godot_debug == 0 and godot_optimized == 0)
shipping_requested = sys.argv[7] == '1'
shipping_debug_inputs, shipping_debug, shipping_optimized_inputs, shipping_optimized = (
    int(value) if value else None for value in sys.argv[8:12])
shipping_passed = not shipping_requested or all(value == 0 for value in (
    shipping_debug_inputs, shipping_debug, shipping_optimized_inputs, shipping_optimized))
(output / "runtime-variants.json").write_text(json.dumps({
    "sameEmulatorBoot": True,
    "debugExitCode": debug_status,
    "optimizedTestSignedExitCode": optimized_status,
    "godotSessionSmoke": {
        "requested": godot_requested,
        "debugPhaseExitCode": godot_debug,
        "optimizedTestSignedPhaseExitCode": godot_optimized,
        "debugRendererDeathRequested": godot_requested,
        "optimizedRendererDeathRequested": False,
        "optimizedRendererDeathScope": "Explicitly omitted for the non-debuggable APK.",
        "allRequestedPhasesPassed": godot_passed if godot_requested else None,
        "fontScale": 1.0,
        "scope": "Real selector and native session lifecycle at normal text; renderer gameplay and pixel privacy require separate evidence.",
    },
    "godotShippingSmoke": {
        "requested": shipping_requested,
        "debugInputExitCode": shipping_debug_inputs,
        "debugPhaseExitCode": shipping_debug,
        "optimizedTestSignedInputExitCode": shipping_optimized_inputs,
        "optimizedTestSignedPhaseExitCode": shipping_optimized,
        "allRequestedPhasesPassed": shipping_passed if shipping_requested else None,
        "modes": ['2d', '3d'] if shipping_requested else [],
        "fontScale": 1.0,
        "qualificationObservationRequested": False,
        "engineGameplayRequested": False,
        "scope": "Shipping picker, real native entry and Standard return; renderer gameplay and pixel privacy retain separate evidence.",
    },
    "passed": debug_status == 0 and optimized_status == 0 and godot_passed and shipping_passed,
}, indent=2) + "\n")
PY
if (( PARTYDECK_DEBUG_STATUS != 0 || PARTYDECK_OPTIMIZED_STATUS != 0 )) || \
  [[ "$PARTYDECK_ANDROID_GODOT_SESSION_SMOKE" == 1 && ( "$PARTYDECK_GODOT_DEBUG_STATUS" != 0 || "$PARTYDECK_GODOT_OPTIMIZED_STATUS" != 0 ) ]] || \
  [[ "$PARTYDECK_ANDROID_GODOT_SHIPPING_SMOKE" == 1 && ( "$PARTYDECK_SHIPPING_DEBUG_INPUT_STATUS" != 0 || \
     "$PARTYDECK_SHIPPING_DEBUG_STATUS" != 0 || "$PARTYDECK_SHIPPING_OPTIMIZED_INPUT_STATUS" != 0 || "$PARTYDECK_SHIPPING_OPTIMIZED_STATUS" != 0 ) ]]; then
  printf 'Android runtime validation failed: debug=%s optimized-test-signed=%s godot-debug=%s godot-optimized=%s shipping-debug-input=%s shipping-debug=%s shipping-optimized-input=%s shipping-optimized=%s\n' \
    "$PARTYDECK_DEBUG_STATUS" "$PARTYDECK_OPTIMIZED_STATUS" \
    "${PARTYDECK_GODOT_DEBUG_STATUS:-not-run}" "${PARTYDECK_GODOT_OPTIMIZED_STATUS:-not-run}" \
    "${PARTYDECK_SHIPPING_DEBUG_INPUT_STATUS:-not-run}" "${PARTYDECK_SHIPPING_DEBUG_STATUS:-not-run}" \
    "${PARTYDECK_SHIPPING_OPTIMIZED_INPUT_STATUS:-not-run}" "${PARTYDECK_SHIPPING_OPTIMIZED_STATUS:-not-run}" >&2
  exit 1
fi
