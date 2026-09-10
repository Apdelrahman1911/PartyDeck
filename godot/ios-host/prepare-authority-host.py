#!/usr/bin/env python3
"""Stage the real Kotlin framework and verified shared PCK for AuthorityHost."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from source_audit import COMMIT, PATCH_FILES, TAG


ROOT = Path(__file__).resolve().parent
FRAMEWORK_FILES = (
    "PartyDeckGodotBridge", "Headers/PartyDeckGodotBridge.h",
    "Modules/module.modulemap", "Info.plist",
)


def file_receipt(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def verify_engine_patch_receipt(engine: dict, patch_root: Path = ROOT / "patches") -> None:
    manifest_path = patch_root / "coreaudio-dormancy.json"
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get("schemaVersion") != 1 or manifest.get("baseCommit") != COMMIT
            or manifest.get("baseVersion") != TAG or manifest.get("platformGuard") != "IOS_ENABLED"
            or manifest.get("patchFile") != "coreaudio-dormancy.patch"):
        raise SystemExit("The maintained audio patch does not identify the pinned iOS engine.")
    files = manifest.get("files", [])
    if len(files) != len(PATCH_FILES) or {item.get("path") for item in files} != PATCH_FILES:
        raise SystemExit("The audio patch must contain exactly the four reviewed source files.")
    if file_receipt(patch_root / manifest["patchFile"])["sha256"] != manifest.get("patchSha256"):
        raise SystemExit("The maintained audio patch differs from its provenance.")
    expected = [{
        "name": "coreaudio-dormancy", "base_commit": COMMIT,
        "patch_sha256": manifest["patchSha256"],
        "manifest_sha256": file_receipt(manifest_path)["sha256"],
        "applied": True, "files": files,
    }]
    if engine.get("upstream_patches") != expected:
        raise SystemExit("Rebuild the native engine with the current reviewed iOS audio patch.")
    if engine.get("sdl_enabled") is not False or engine.get("native_input_scope") != "touch_and_hardware_keyboard":
        raise SystemExit("The native engine receipt must match the reviewed input-driver configuration.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", required=True, type=Path)
    parser.add_argument("--framework-receipt", required=True, type=Path)
    parser.add_argument("--pack", required=True, type=Path)
    args = parser.parse_args()
    engine = json.loads((ROOT / "build/evidence/engine-artifact.json").read_text())
    if engine.get("engine_commit") != COMMIT or engine.get("path_overrides_enabled") is not True:
        raise SystemExit("The authority host requires the pinned engine with owned path overrides enabled.")
    verify_engine_patch_receipt(engine)
    engine_archives = [engine, *engine.get("auxiliary_archives", [])]
    if len(engine_archives) != 2 or {item.get("artifact") for item in engine_archives} != {
        "libpartydeck_godot_ios_probe.a", "libpartydeck_godot_camera.a",
    }:
        raise SystemExit("The two expected native engine archives need distinct build receipts.")
    for item in engine_archives:
        if item.get("artifact") not in {"libpartydeck_godot_ios_probe.a", "libpartydeck_godot_camera.a"}:
            raise SystemExit("The engine receipt names an unexpected native archive.")
        actual = file_receipt(ROOT / "build/artifacts" / item["artifact"])
        if any(actual[key] != item.get(key) for key in actual):
            raise SystemExit("The native engine archive differs from its build receipt.")
    modules = ROOT / "modules"
    module_hashes = {
        path.relative_to(modules).as_posix(): file_receipt(path)["sha256"]
        for path in sorted(modules.rglob("*"))
        if path.is_file() and (path.suffix in {".h", ".mm", ".py"} or path.name == "SCsub")
    }
    if engine.get("native_module_sources") != module_hashes:
        raise SystemExit("Rebuild the native engine archive with the current authority-host module sources.")
    module_digest = hashlib.sha256(json.dumps(
        module_hashes, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    if (engine.get("module_snapshot_sha256") != module_digest
            or engine.get("native_module_capture_phase") != "before_scons"
            or engine.get("engine_checkout_policy") != "fresh_isolated_checkout"):
        raise SystemExit("The native engine requires verified module inputs captured before its isolated build.")
    framework = args.framework.resolve()
    receipt = json.loads(args.framework_receipt.read_text())
    if receipt.get("target") != "iosSimulatorArm64" or not all(receipt.get(key) is True for key in (
        "framework_compiled", "expected_facade_declarations_present", "swift_module_import_typechecked",
    )):
        raise SystemExit("A successful ARM64 Simulator framework receipt is required.")
    for filename in FRAMEWORK_FILES:
        if file_receipt(framework / filename) != receipt["framework"].get(filename):
            raise SystemExit(f"The authority framework does not match its receipt: {filename}")
    destination = ROOT / "build/artifacts/PartyDeckGodotBridge.framework"
    if destination.is_symlink():
        raise SystemExit("Generated framework staging must not be a symlink.")
    if destination.resolve() != framework:
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(framework, destination)
    for filename in FRAMEWORK_FILES:
        if file_receipt(destination / filename) != receipt["framework"][filename]:
            raise SystemExit("The staged framework changed while copying.")
    subprocess.run([
        sys.executable, str(ROOT / "prepare-host-resources.py"), "--pack", str(args.pack.resolve()),
    ], check=True)
    evidence = ROOT / "build/evidence"
    resources = json.loads((evidence / "host-resources.json").read_text())
    result = {
        "stage": "authority_host_inputs_only",
        "framework_receipt": receipt,
        "engine_receipt": engine,
        "framework_receipt_file": file_receipt(args.framework_receipt),
        "resources": resources,
        "swift_authority_host_compiled": False,
        "ios_authority_runtime_executed": False,
        "kmp_factory_qualified": False,
    }
    (evidence / "authority-host-inputs.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Staged the receipt-matched Kotlin framework and verified shared renderer pack.")


if __name__ == "__main__":
    main()
