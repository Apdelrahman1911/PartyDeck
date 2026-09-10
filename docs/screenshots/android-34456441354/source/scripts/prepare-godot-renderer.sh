#!/usr/bin/env bash
set -euo pipefail

PARTYDECK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARTYDECK_ROOT"

# Reuse a source-current pack; never silently reuse one from different sources.
PARTYDECK_PACK="godot/qualification/build/renderer/partydeck-last-light.pck"
if [[ -f "$PARTYDECK_PACK" ]] && python3 -B godot/tools/renderer.py check-pack --pack "$PARTYDECK_PACK"; then
  exit 0
fi

# Linux installation checks the official archive and executable pins. Other
# platforms may provide their verified official Godot 4.7.2 executable explicitly.
PARTYDECK_ENGINE="${PARTYDECK_GODOT_EXECUTABLE:-}"
if [[ -z "$PARTYDECK_ENGINE" ]]; then
  python3 -B godot/tools/renderer.py install --destination godot/qualification/build/toolchain
  PARTYDECK_ENGINE="$PARTYDECK_ROOT/godot/qualification/build/toolchain/godot"
fi
python3 -B godot/tools/renderer.py pack --godot "$PARTYDECK_ENGINE"
