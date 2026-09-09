#!/usr/bin/env bash
set -euo pipefail

PARTYDECK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARTYDECK_ROOT"

# On a headless Linux host, invoke this script through xvfb-run for Compose UI tests.
# CI deliberately supplies no release signing credentials; its release AAB is unsigned.
./gradlew --continue --stacktrace --console=plain \
  :core:jvmTest \
  :session:jvmTest \
  :transport:jvmTest \
  :games:jvmTest \
  :composeApp:jvmTest \
  :composeApp:compileKotlinJvm \
  :androidApp:testDebugUnitTest \
  :androidApp:lintDebug \
  :androidApp:assembleDebug \
  :androidApp:assembleRelease \
  :androidApp:bundleRelease
