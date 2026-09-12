#!/usr/bin/env bash
# Exercise the exported renderer, including its real pixel buffers and input.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."

PARTYDECK_POLISH_ENGINE="${PARTYDECK_GODOT_EXECUTABLE:-$PWD/godot/qualification/build/toolchain/godot}"
PARTYDECK_POLISH_PACK="$PWD/godot/qualification/build/renderer/partydeck-last-light.pck"
PARTYDECK_POLISH_OUTPUT="${PARTYDECK_POLISH_OUTPUT:-$PWD/build/ci/android-preview/renderer}"
python3 -B godot/tools/renderer.py check-pack --pack "$PARTYDECK_POLISH_PACK"
mkdir -p "$(dirname -- "$PARTYDECK_POLISH_OUTPUT")"
mkdir "$PARTYDECK_POLISH_OUTPUT"

for PARTYDECK_POLISH_CASE in redraw play_effect quality_capture; do
  mkdir -p "$PARTYDECK_POLISH_OUTPUT/$PARTYDECK_POLISH_CASE/empty"
  PARTYDECK_POLISH_EXTRA=()
  PARTYDECK_POLISH_SCRIPT="$PWD/godot/renderer/tests/three_d_${PARTYDECK_POLISH_CASE}_check.gd"
  if [[ "$PARTYDECK_POLISH_CASE" == quality_capture ]]; then
    PARTYDECK_POLISH_SCRIPT="$PWD/godot/renderer/tests/three_d_quality_capture.gd"
    PARTYDECK_POLISH_EXTRA=(--check-width=1080 --check-height=2340 --check-density=3)
  fi
  timeout --signal=TERM --kill-after=10s 180s xvfb-run -a --server-args='-screen 0 2560x2560x24' \
    "$PARTYDECK_POLISH_ENGINE" \
    --path "$PARTYDECK_POLISH_OUTPUT/$PARTYDECK_POLISH_CASE/empty" \
    --main-pack "$PARTYDECK_POLISH_PACK" \
    --rendering-method gl_compatibility --rendering-driver opengl3 --audio-driver Dummy \
    --script "$PARTYDECK_POLISH_SCRIPT" -- \
    --manual-bridge \
    --check-output="$PARTYDECK_POLISH_OUTPUT/$PARTYDECK_POLISH_CASE/results" \
    --check-fixture="$PWD/godot/bridge/fixtures/launch-3d.json" \
    "${PARTYDECK_POLISH_EXTRA[@]}" \
    2>&1 | tee "$PARTYDECK_POLISH_OUTPUT/$PARTYDECK_POLISH_CASE/runtime.log"
done

python3 -B - "$PARTYDECK_POLISH_OUTPUT" "$PARTYDECK_POLISH_PACK" <<'PY'
import hashlib
import json
from pathlib import Path
import re
import sys

output, pack = map(Path, sys.argv[1:])
cases = []
quality_checks = {'nativeDensityConfigured', 'requestedWindowSize', 'physicalCaptureSize',
                  'nativeViewportPixels', 'tableRimContained', 'concealedHandHasNoPrivateNodes',
                  'ownHandRevealedByInput', 'cardsSelectedByInput', 'noGameplayIntent'}
for name in ('redraw', 'play_effect', 'quality_capture'):
    report = json.loads((output / name / 'results/report.json').read_text())
    checks = report.get('checks')
    if name == 'quality_capture':
        valid_checks = (isinstance(checks, dict) and set(checks) == quality_checks
                        and all(value is True for value in checks.values()))
    else:
        valid_checks = (isinstance(checks, list) and bool(checks)
                        and all(isinstance(check, dict) and check.get('passed') is True for check in checks))
    if report.get('result') != 'passed' or not valid_checks:
        raise SystemExit(f'{name}: the packed renderer check did not pass.')
    log = (output / name / 'runtime.log').read_text()
    if re.search(r'(?m)^\s*(?:SCRIPT ERROR|SHADER ERROR|USER ERROR|ERROR|Parse Error):', log):
        raise SystemExit(f'{name}: Godot reported an error despite its exit status.')
    cases.append({'name': name, 'passed': True, 'assertions': len(checks)})
with pack.open('rb') as stream:
    pack_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
summary = {'passed': True, 'rendererPackSha256': pack_hash, 'cases': cases,
           'scope': 'Godot 4.7.2 desktop OpenGL rendering, native-density layout, '
                    'public-play feedback, privacy and idle redraw; Dummy audio output.'}
(output / 'check-result.json').write_text(json.dumps(summary, indent=2) + '\n')
print(f"Packed 3D checks passed: {sum(case['assertions'] for case in cases)} assertions.")
PY
