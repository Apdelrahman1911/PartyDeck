#!/usr/bin/env bash
set -euo pipefail

PARTYDECK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARTYDECK_ROOT"
if (( $# > 2 )); then
  printf '%s\n' 'Usage: prepare-android-runtime-apk.sh [unsigned-release.apk] [output-directory]' >&2
  exit 1
fi
PARTYDECK_UNSIGNED_APK="${1:-androidApp/build/outputs/apk/release/androidApp-release-unsigned.apk}"
PARTYDECK_RUNTIME_OUTPUT="${2:-$PARTYDECK_ROOT/build/ci/android/packages}"
PARTYDECK_BUILD_TOOLS="${ANDROID_HOME:?Set ANDROID_HOME to the installed Android SDK.}/build-tools/36.0.0"
PARTYDECK_RUNTIME_APK="$PARTYDECK_RUNTIME_OUTPUT/PartyDeck-release-ci-test-signed.apk"

# This helper never consumes a publisher's signing configuration or identity.
for PARTYDECK_SIGNING_VARIABLE in PARTYDECK_KEYSTORE_PATH PARTYDECK_KEYSTORE_PASSWORD PARTYDECK_KEY_ALIAS PARTYDECK_KEY_PASSWORD; do
  if [[ -v "$PARTYDECK_SIGNING_VARIABLE" ]]; then
    printf '%s\n' 'CI runtime signing requires all production signing variables to be absent.' >&2
    exit 1
  fi
done
test -f "$PARTYDECK_UNSIGNED_APK"
test -x "$PARTYDECK_BUILD_TOOLS/apksigner"
test -x "$PARTYDECK_BUILD_TOOLS/zipalign"
python3 - "$PARTYDECK_UNSIGNED_APK" "$PARTYDECK_RUNTIME_APK" <<'PY'
from pathlib import Path
import sys

source, destination = map(Path, sys.argv[1:3])
if source.resolve() == destination.resolve() or (destination.exists() and source.samefile(destination)):
    raise RuntimeError("The unsigned input and CI runtime output must be different files.")
PY
mkdir -p "$PARTYDECK_RUNTIME_OUTPUT"

if "$PARTYDECK_BUILD_TOOLS/apksigner" verify "$PARTYDECK_UNSIGNED_APK" \
  > "$PARTYDECK_RUNTIME_OUTPUT/input-signature.log" 2>&1; then
  printf '%s\n' 'Expected an unsigned release APK; refusing to replace an existing valid signing identity.' >&2
  exit 1
fi
PARTYDECK_UNSIGNED_SHA="$(sha256sum "$PARTYDECK_UNSIGNED_APK")"
PARTYDECK_UNSIGNED_SHA="${PARTYDECK_UNSIGNED_SHA%% *}"

umask 077
PARTYDECK_KEY_DIRECTORY="$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/partydeck-runtime-key.XXXXXX")"
cleanup() {
  rm -rf -- "$PARTYDECK_KEY_DIRECTORY"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# A newly generated, short-lived test identity is deleted at script exit. Its
# keystore is outside the artifact tree; it is never a release/upload identity.
export PARTYDECK_CI_TEST_KEY_PASSWORD='partydeck-ci-runtime-only'
keytool -genkeypair \
  -keystore "$PARTYDECK_KEY_DIRECTORY/runtime-test.p12" \
  -storetype PKCS12 \
  -storepass:env PARTYDECK_CI_TEST_KEY_PASSWORD \
  -keypass:env PARTYDECK_CI_TEST_KEY_PASSWORD \
  -alias partydeck-ci-runtime \
  -keyalg RSA -keysize 2048 -validity 2 \
  -dname 'CN=PartyDeck CI runtime test only' \
  > "$PARTYDECK_RUNTIME_OUTPUT/key-generation.log" 2>&1

# zipalign must precede signing. Keep the original optimized APK byte-for-byte.
"$PARTYDECK_BUILD_TOOLS/zipalign" -P 16 -f 4 \
  "$PARTYDECK_UNSIGNED_APK" "$PARTYDECK_KEY_DIRECTORY/aligned.apk"
"$PARTYDECK_BUILD_TOOLS/apksigner" sign \
  --ks "$PARTYDECK_KEY_DIRECTORY/runtime-test.p12" \
  --ks-key-alias partydeck-ci-runtime \
  --ks-pass env:PARTYDECK_CI_TEST_KEY_PASSWORD \
  --key-pass env:PARTYDECK_CI_TEST_KEY_PASSWORD \
  --debuggable-apk-permitted false \
  --alignment-preserved true \
  --v4-signing-enabled false \
  --out "$PARTYDECK_RUNTIME_APK" \
  "$PARTYDECK_KEY_DIRECTORY/aligned.apk" \
  > "$PARTYDECK_RUNTIME_OUTPUT/apk-signing.log" 2>&1
"$PARTYDECK_BUILD_TOOLS/apksigner" verify --verbose --print-certs \
  "$PARTYDECK_RUNTIME_APK" > "$PARTYDECK_RUNTIME_OUTPUT/signature-verification.log" 2>&1
"$PARTYDECK_BUILD_TOOLS/zipalign" -c -P 16 -v 4 \
  "$PARTYDECK_RUNTIME_APK" > "$PARTYDECK_RUNTIME_OUTPUT/alignment-check.log" 2>&1

python3 - "$PARTYDECK_UNSIGNED_APK" "$PARTYDECK_RUNTIME_APK" \
  "$PARTYDECK_UNSIGNED_SHA" "$PARTYDECK_RUNTIME_OUTPUT" <<'PY'
import hashlib
import json
from pathlib import Path
import re
import sys

unsigned, signed = map(Path, sys.argv[1:3])
before_sha, output = sys.argv[3], Path(sys.argv[4])
unsigned_sha = hashlib.sha256(unsigned.read_bytes()).hexdigest()
if unsigned_sha != before_sha:
    raise RuntimeError("The original unsigned release APK changed during CI signing.")
verification = (output / "signature-verification.log").read_text()
match = re.search(r"Signer #1 certificate SHA-256 digest: ([0-9a-fA-F]{64})", verification)
if match is None:
    raise RuntimeError("Verified runtime APK did not report its signing certificate fingerprint.")
(output / "runtime-package.json").write_text(json.dumps({
    "variant": "optimized-test-signed",
    "signingIdentity": "disposable-ci-test-key",
    "distributionSigned": False,
    "originalUnsignedApk": str(unsigned),
    "originalUnsignedSha256": unsigned_sha,
    "runtimeApk": str(signed),
    "runtimeApkSha256": hashlib.sha256(signed.read_bytes()).hexdigest(),
    "certificateSha256": match.group(1).lower(),
    "alignmentKiB": 16,
}, indent=2) + "\n")
PY
printf 'Prepared CI test-signed optimized APK: %s\n' "$PARTYDECK_RUNTIME_APK"
