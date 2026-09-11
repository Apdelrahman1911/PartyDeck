#!/usr/bin/env python3
"""Bind one CI build's qualification APKs/PCK to all adaptive emulator jobs."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "androidApp-debug.apk": "androidApp/build/outputs/apk/debug/androidApp-debug.apk",
    "androidApp-release-unsigned.apk": "androidApp/build/outputs/apk/release/androidApp-release-unsigned.apk",
    "PartyDeck-release-ci-test-signed.apk": "build/ci/android/packages/PartyDeck-release-ci-test-signed.apk",
    "runtime-package.json": "build/ci/android/packages/runtime-package.json",
    "godot-activation-build.json": "build/ci/android/godot-activation-build.json",
    "partydeck-last-light.pck": "godot/qualification/build/renderer/partydeck-last-light.pck",
    "partydeck-last-light.receipt.json": "godot/qualification/build/renderer/partydeck-last-light.receipt.json",
}
PINS = {
    "scripts/android_godot_activation.py": "5f5650fbabd934f904ceaf9e5b7705f5c91bfde999fb2bb03ad28062e91e61f9",
    "scripts/smoke-android-godot-session.py": "610971b22dc8ee60d62fa4e213224833cdd43fb0fa533c0fdd5fa39227a39fc4",
    "scripts/smoke-android-ui.py": "831b57634a0cee99a466e6820059bb55209a26db3723b2ffff703b2ee0f60836",
    "scripts/tests/test_android_godot_session.py": "77aa9c7dee4147141c61d95266d7bb6cdab0e3287fc3e41b9ed23a207bbf756e",
    "scripts/adaptive_observations.py": "8b636b7f2687d6ddc0bca37624e678c3f1779a2df9537062088fd1e203a481c5",
    "scripts/smoke_android_godot_adaptive.py": "9ed771c96e7f16a8c669e4db5c11904836c0e3937341ad3513a76f037401b918",
    "scripts/android_godot_session_observation.py": "4a9340d49e69d596d2d6ed3cfd12b69eb567ab0fb49fed0fa49a643dfc877a8f",
    "scripts/tests/test_android_engine_gameplay.py": "d4cdec6444f4b7dd8240e5b8ae5b1f1ee26717ebac61efc68f92944ae7eb9f83",
    "scripts/smoke_android_godot_public_context.py": "86555cd27b7342fec48af00df07fab07883e3e5de88bcabf3e61e3a3ec3f112c",
    "scripts/tests/test_android_godot_public_context.py": "3e02a6f8e9bc9b036e0661a234095cd56f16d5dbbbdd6cbe4054bc9ee4dc8324",
    "scripts/tests/fixtures/android-focused-34568971032/debug-post-progression.xml": "ea61b13aaa764e0529224ea90c5b480c93e2376643c2e6431e1288feb6de44b7",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate key in input receipt.")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def context():
    revision, run_id, attempt, repository = (os.environ.get(key, "") for key in
        ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_REPOSITORY"))
    require(re.fullmatch(r"[0-9a-f]{40}", revision), "A full workflow source revision is required.")
    require(run_id.isdigit() and attempt.isdigit() and repository.count("/") == 1,
            "Workflow run, attempt and repository provenance are required.")
    return dict(sourceRevision=revision, runId=run_id, runAttempt=attempt, repository=repository)


def file_records(bundle):
    result = {}
    for name in FILES:
        path = bundle / name
        require(path.is_file() and not path.is_symlink(), "Missing or indirect input: " + name)
        result[name] = dict(sha256=digest(path), bytes=path.stat().st_size)
    return result


def verify_manifest(raw, expected_hash, bundle, current):
    require(re.fullmatch(r"[0-9a-f]{64}", expected_hash or ""), "The producer manifest SHA-256 is required.")
    require(hashlib.sha256(raw).hexdigest() == expected_hash, "Downloaded manifest differs from the producer output.")
    value = read_json(raw)
    require(type(value) is dict and type(value.get("schemaVersion")) is int
            and value["schemaVersion"] == 1, "Unrecognized adaptive input manifest.")
    for key in ("sourceRevision", "runId", "repository"):
        require(value.get(key) == current[key], "Input provenance differs from this workflow: " + key)
    # A later consumer attempt may reuse this immutable producer artifact in the same run.
    require(str(value.get("runAttempt", "")).isdigit(), "Missing producer attempt provenance.")
    require(value.get("androidApi") == 36 and value.get("modesCsv") == "2d,3d"
            and value.get("qualificationProfile") == "qualification", "Wrong adaptive execution scope.")
    require(value.get("checkerSha256") == PINS, "Producer checker pins differ from the accepted input contract.")
    require(value.get("files") == file_records(bundle), "Downloaded APK/PCK/receipt bytes differ from the producer.")
    return value


def checked_command(argv, output, stem):
    try:
        result = subprocess.run([str(part) for part in argv], cwd=ROOT, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired as error:
        (output / (stem + ".stdout.log")).write_bytes(error.stdout or b"")
        (output / (stem + ".stderr.log")).write_bytes(error.stderr or b"")
        raise
    (output / (stem + ".stdout.log")).write_bytes(result.stdout)
    (output / (stem + ".stderr.log")).write_bytes(result.stderr)
    require(result.returncode == 0, "Input check failed: " + stem)
    return result.stdout


def inspect_inputs(bundle, output, report):
    for name, expected in PINS.items():
        require(digest(ROOT / name) == expected, "Frozen checker changed: " + name)
    spec = importlib.util.spec_from_file_location("adaptive_activation_check", ROOT / "scripts/android_godot_activation.py")
    activation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(activation)
    expectation = (bundle / "godot-activation-build.json").read_bytes()
    (output / "activation-build-expectation.json").write_bytes(expectation)
    expected = activation.parse_build_expectation(expectation)
    checked_command([sys.executable, "-B", ROOT / "godot/tools/renderer.py", "check-pack", "--pack",
                     bundle / "partydeck-last-light.pck"], output, "source-pack-check")
    analyzer = shutil.which("apkanalyzer")
    require(analyzer, "The SDK command-line tools must expose apkanalyzer on PATH.")
    sdk = Path(os.environ["ANDROID_HOME"])
    signer = sdk / "build-tools/36.0.0/apksigner"
    aligner = sdk / "build-tools/36.0.0/zipalign"
    signing = read_json((bundle / "runtime-package.json").read_bytes())
    require(signing.get("variant") == "optimized-test-signed"
            and signing.get("signingIdentity") == "disposable-ci-test-key"
            and signing.get("distributionSigned") is False and signing.get("alignmentKiB") == 16,
            "The optimized input lacks the disposable CI signing contract.")
    for receipt_key, name in (("originalUnsignedSha256", "androidApp-release-unsigned.apk"),
                              ("runtimeApkSha256", "PartyDeck-release-ci-test-signed.apk")):
        require(signing.get(receipt_key) == digest(bundle / name), "Signing receipt differs from the exact APK bytes.")
    report.update(activationExpectation=expected, signingReceipt=signing, packages={})
    pack_hash = digest(bundle / "partydeck-last-light.pck")
    for variant, name in (("debug", "androidApp-debug.apk"),
                          ("optimized-test-signed", "PartyDeck-release-ci-test-signed.apk")):
        apk = bundle / name
        item = dict(apkSha256=digest(apk), packSha256=pack_hash, verified=False)
        report["packages"][variant] = item
        with zipfile.ZipFile(apk) as archive:
            entry = "assets/partydeck-last-light.pck"
            require(archive.namelist().count(entry) == 1, "APK must contain exactly one renderer PCK.")
            with archive.open(entry) as stream:
                item["embeddedPackSha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        require(item["embeddedPackSha256"] == pack_hash, "APK embeds a different renderer PCK.")
        command = [analyzer, "manifest", "print", str(apk)]
        item["manifestCommand"] = command
        try:
            decoded = subprocess.run(command, capture_output=True, timeout=120)
        except subprocess.TimeoutExpired as error:
            (output / (variant + "-packaged-manifest.xml")).write_bytes(error.stdout or b"")
            (output / (variant + "-manifest.stderr.log")).write_bytes(error.stderr or b"")
            item["manifestTimedOut"] = True
            raise
        (output / (variant + "-packaged-manifest.xml")).write_bytes(decoded.stdout)
        (output / (variant + "-manifest.stderr.log")).write_bytes(decoded.stderr)
        item.update(manifestCommand=command, manifestExitCode=decoded.returncode,
                    manifestSha256=hashlib.sha256(decoded.stdout).hexdigest())
        require(decoded.returncode == 0, "Cannot decode the supplied APK manifest.")
        item["packagedActivation"] = activation.parse_packaged_manifest(decoded.stdout)
        activation.require_qualification_match(expected, item["packagedActivation"], "2d,3d")
        application = ET.fromstring(decoded.stdout).find("application")
        debuggable = application.get("{http://schemas.android.com/apk/res/android}debuggable", "false")
        require(debuggable == ("true" if variant == "debug" else "false"), "APK debuggability differs from its variant.")
        certificates = checked_command([signer, "verify", "--verbose", "--print-certs", apk], output,
                                       variant + "-signature").decode("utf-8")
        fingerprints = re.findall(r"^Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]{64})$", certificates, re.M)
        require(len(fingerprints) == 1, "Expected one verified APK signer.")
        item["certificateSha256"] = fingerprints[0].lower()
        if variant == "optimized-test-signed":
            require(item["certificateSha256"] == signing.get("certificateSha256"), "Optimized signer differs from its receipt.")
            checked_command([aligner, "-c", "-P", "16", "-v", "4", apk], output, variant + "-alignment")
        item["verified"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("record", "verify"))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Fresh input-evidence directory.")
    parser.add_argument("--manifest-sha256", help="Exact producer output required by verify.")
    args = parser.parse_args()
    bundle, output = args.bundle.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = dict(command=args.command, verified=False, nativeExecution=False)
    status = 1
    try:
        current = context()
        report["consumerContext" if args.command == "verify" else "producerContext"] = current
        if args.command == "record":
            bundle.mkdir(parents=True, exist_ok=False)
            for name, source in FILES.items():
                shutil.copyfile(ROOT / source, bundle / name)
            manifest = dict(schemaVersion=1, **current, androidApi=36, modesCsv="2d,3d",
                            qualificationProfile="qualification", checkerSha256=PINS, files=file_records(bundle))
        else:
            raw = (bundle / "inputs.json").read_bytes()
            (output / "received-inputs.json").write_bytes(raw)
            manifest = verify_manifest(raw, args.manifest_sha256, bundle, current)
            report["producerManifestSha256"] = args.manifest_sha256
            report["producerArtifactId"] = os.environ.get("PARTYDECK_ADAPTIVE_ARTIFACT_ID")
        report["inputs"] = manifest
        inspect_inputs(bundle, output, report)
        if args.command == "record":
            (bundle / "inputs.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        report["verified"] = True
        status = 0
    except Exception as error:
        report["error"] = str(error)
        print(str(error), file=sys.stderr)
    finally:
        (output / "package-inputs.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
