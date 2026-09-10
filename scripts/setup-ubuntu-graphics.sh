#!/usr/bin/env bash
set -euo pipefail

PARTYDECK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARTYDECK_ROOT"
PARTYDECK_GRAPHICS_OUTPUT="$PARTYDECK_ROOT/build/ci/android"
mkdir -p "$PARTYDECK_GRAPHICS_OUTPUT"
PARTYDECK_GRAPHICS_PACKAGES=(xvfb xauth libgl1 libgl1-mesa-dri libegl1 libx11-6 libxi6 libxrender1 libxtst6)
PARTYDECK_MISSING_PACKAGES=()
for PARTYDECK_PACKAGE in "${PARTYDECK_GRAPHICS_PACKAGES[@]}"; do
  PARTYDECK_PACKAGE_STATUS="$(dpkg-query --show '--showformat=${Status}' "$PARTYDECK_PACKAGE" 2>/dev/null || true)"
  if [[ "$PARTYDECK_PACKAGE_STATUS" != 'install ok installed' ]]; then
    PARTYDECK_MISSING_PACKAGES+=("$PARTYDECK_PACKAGE")
  fi
done

if (( ${#PARTYDECK_MISSING_PACKAGES[@]} > 0 )); then
  # The hosted Ubuntu 24.04 image keeps its signed Ubuntu mirror configuration
  # here. Unrelated Chrome/Microsoft feeds must not gate these Ubuntu packages.
  PARTYDECK_UBUNTU_SOURCES='/etc/apt/sources.list.d/ubuntu.sources'
  if [[ ! -r "$PARTYDECK_UBUNTU_SOURCES" ]]; then
    printf '%s\n' 'Expected the Ubuntu 24.04 runner source file at /etc/apt/sources.list.d/ubuntu.sources.' >&2
    exit 1
  fi
  cp "$PARTYDECK_UBUNTU_SOURCES" "$PARTYDECK_GRAPHICS_OUTPUT/graphics-ubuntu-sources.log"
  PARTYDECK_EMPTY_SOURCE_PARTS="$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/partydeck-apt-sources.XXXXXX")"
  cleanup() {
    rmdir -- "$PARTYDECK_EMPTY_SOURCE_PARTS"
  }
  trap cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  PARTYDECK_APT_OPTIONS=(
    -o "Dir::Etc::sourcelist=$PARTYDECK_UBUNTU_SOURCES"
    -o "Dir::Etc::sourceparts=$PARTYDECK_EMPTY_SOURCE_PARTS"
    -o Acquire::Retries=3
  )
  PARTYDECK_APT_COMMAND=(apt-get)
  if (( EUID != 0 )); then
    PARTYDECK_APT_COMMAND=(sudo apt-get)
  fi
  "${PARTYDECK_APT_COMMAND[@]}" "${PARTYDECK_APT_OPTIONS[@]}" update \
    2>&1 | tee "$PARTYDECK_GRAPHICS_OUTPUT/graphics-apt-update.log"
  "${PARTYDECK_APT_COMMAND[@]}" "${PARTYDECK_APT_OPTIONS[@]}" install --yes --no-install-recommends \
    "${PARTYDECK_MISSING_PACKAGES[@]}" \
    2>&1 | tee "$PARTYDECK_GRAPHICS_OUTPUT/graphics-apt-install.log"
else
  printf '%s\n' 'Required Compose test graphics packages are already installed; no APT network request needed.'
fi

dpkg-query --show '--showformat=${Package}\t${Status}\t${Version}\n' \
  "${PARTYDECK_GRAPHICS_PACKAGES[@]}" | tee "$PARTYDECK_GRAPHICS_OUTPUT/graphics-packages.log"
command -v xvfb-run
command -v Xvfb
