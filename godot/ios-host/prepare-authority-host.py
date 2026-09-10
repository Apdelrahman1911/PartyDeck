#!/usr/bin/env python3
"""Stage the real Kotlin framework and verified shared PCK for AuthorityHost."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from source_audit import COMMIT, PATCH_FILES_BY_NAME, TAG


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


def verify_retained_pack_pin(runtime: Path, pack: Path, verified_pack: dict) -> str:
    if (not isinstance(verified_pack, dict) or not pack.is_file()
            or file_receipt(pack) != verified_pack):
        raise SystemExit("The retained host requires the unchanged receipt-verified staged PCK.")
    source = runtime.read_text()
    # The maintained source uses no line splicing. Reject unsupported spelling
    # instead of mistaking a continued comment or string for a declaration.
    if re.search(r'\\[ \t]*\n', source):
        raise SystemExit("The retained native pin preflight does not support escaped source newlines.")
    # Keep comments and all quoted literals opaque, including C++ raw strings.
    tokens = [
        match[0] for match in re.finditer(
            r'//[^\n]*|/\*.*?\*/|(?:u8|u|U|L)?R"(?P<delimiter>[^ ()\\\t\r\n]{0,16})\(.*?\)(?P=delimiter)"'
            r'|@?"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_]\w*|==|\S',
            source, re.DOTALL,
        ) if not match[0].startswith(("//", "/*"))
    ]
    declarations = []
    for index, token in enumerate(tokens):
        if token != "PDQualifiedRetainedPackSHA256":
            continue
        previous = tokens[index - 1] if index else ""
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        # Recognize declarators independently of assignment/direct/brace/default
        # initialization, and reject additional assignments to this symbol.
        if ((re.fullmatch(r'[A-Za-z_]\w*|[*&]', previous)
             and previous not in {"return", "co_return", "throw", "case"})
                or following in {"=", "(", "{"}):
            declarations.append(index)
    pin = None
    if len(declarations) == 1:
        index = declarations[0]
        if (index >= 4 and tokens[index - 4:index] == ["static", "NSString", "*", "const"]
                and tokens[index + 1:index + 2] == ["="] and tokens[index + 3:index + 4] == [";"]):
            pin = re.fullmatch(r'@"([a-f0-9]{64})"', tokens[index + 2])
    if pin is None:
        raise SystemExit(
            "The retained host requires exactly one literal PDQualifiedRetainedPackSHA256 "
            "declaration in PDGodotRuntime.mm."
        )
    if pin[1] != verified_pack["sha256"]:
        raise SystemExit(
            f"The receipt-verified retained PCK SHA-256 {verified_pack['sha256']} does not match "
            f"PDQualifiedRetainedPackSHA256 {pin[1]}; native execution would reject it."
        )
    return pin[1]


def verify_engine_patch_receipt(engine: dict, patch_root: Path = ROOT / "patches") -> None:
    expected = []
    for name, expected_files in PATCH_FILES_BY_NAME.items():
        manifest_path = patch_root / f"{name}.json"
        manifest = json.loads(manifest_path.read_text())
        if (manifest.get("schemaVersion") != 1 or manifest.get("baseCommit") != COMMIT
                or manifest.get("baseVersion") != TAG or manifest.get("platformGuard") != "IOS_ENABLED"
                or manifest.get("patchFile") != f"{name}.patch"):
            raise SystemExit(f"The maintained {name} patch does not identify the pinned iOS engine.")
        files = manifest.get("files", [])
        if len(files) != len(expected_files) or {item.get("path") for item in files} != expected_files:
            raise SystemExit(f"The {name} patch must contain exactly its reviewed source files.")
        if file_receipt(patch_root / manifest["patchFile"])["sha256"] != manifest.get("patchSha256"):
            raise SystemExit(f"The maintained {name} patch differs from its provenance.")
        expected.append({
            "name": name, "base_commit": COMMIT,
            "patch_sha256": manifest["patchSha256"],
            "manifest_sha256": file_receipt(manifest_path)["sha256"],
            "applied": True, "files": files,
        })
    if engine.get("upstream_patches") != expected:
        raise SystemExit("Rebuild the native engine with every current reviewed iOS patch.")
    if engine.get("sdl_enabled") is not False or engine.get("native_input_scope") != "touch_and_hardware_keyboard":
        raise SystemExit("The native engine receipt must match the reviewed input-driver configuration.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", required=True, type=Path)
    parser.add_argument("--framework-receipt", required=True, type=Path)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--retained", action="store_true",
                        help="Require the staged PCK to match the native retained-engine literal.")
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
    if args.retained:
        result["native_pack_sha256"] = verify_retained_pack_pin(
            ROOT / "modules/partydeck_ios_probe/PDGodotRuntime.mm",
            ROOT / "build/host-resources/ProbeResources/partydeck-last-light.pck",
            resources.get("optional_shared_pack"),
        )
    (evidence / "authority-host-inputs.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Staged the receipt-matched Kotlin framework and verified shared renderer pack.")


if __name__ == "__main__":
    main()
