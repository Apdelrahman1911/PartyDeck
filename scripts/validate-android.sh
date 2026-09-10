#!/usr/bin/env bash
set -euo pipefail

PARTYDECK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARTYDECK_ROOT"

# Only the existing explicit CI session input opts the production APKs into qualification.
PARTYDECK_ANDROID_ACTIVATION_ARGS=()
case "${PARTYDECK_ANDROID_GODOT_SESSION_SMOKE:-0}" in
  0) ;;
  1) PARTYDECK_ANDROID_ACTIVATION_ARGS=(-PpartydeckGodotQualificationModes=2d,3d) ;;
  *) printf '%s\n' 'PARTYDECK_ANDROID_GODOT_SESSION_SMOKE must be 0 or 1.' >&2; exit 1 ;;
esac

# On a headless Linux host, invoke this script through xvfb-run for Compose UI tests.
# CI deliberately supplies no release signing credentials; its release AAB is unsigned.
bash scripts/prepare-godot-renderer.sh
./gradlew --continue --stacktrace --console=plain "${PARTYDECK_ANDROID_ACTIVATION_ARGS[@]}" \
  :androidApp:recordGodotPresentationActivation \
  :core:jvmTest \
  :session:jvmTest \
  :transport:jvmTest \
  :games:jvmTest \
  :bridge:jvmTest \
  :androidRenderer:testDebugUnitTest \
  :androidRenderer:lintDebug \
  :composeApp:jvmTest \
  :composeApp:compileKotlinJvm \
  :androidApp:testDebugUnitTest \
  :androidApp:lintDebug \
  :androidApp:assembleDebug \
  :androidApp:assembleRelease \
  :androidApp:bundleRelease
