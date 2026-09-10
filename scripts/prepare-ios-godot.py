#!/usr/bin/env python3
"""Verify and stage the real iOS engine/PCK; record production linking separately."""

import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import runpy
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "godot/ios-host"
ARCHIVES = ("libpartydeck_godot_ios_probe.a", "libpartydeck_godot_camera.a")
NATIVE_CLASSES = ("_OBJC_CLASS_$_PDGodotEngineOwner", "_OBJC_CLASS_$_PDGodotPresentation")
VARIANTS = {
    ("Debug", "iphonesimulator"): ("template_debug", True, "7"),
    ("Release", "iphoneos"): ("template_release", False, "2"),
}


def receipt(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def apple_platform(path: Path, expected: str) -> dict:
    # arm64 alone does not distinguish a Simulator archive from a device archive.
    # Apple's otool accepts archives; LC_BUILD_VERSION platform 2 is iOS, 7 is Simulator.
    architectures = subprocess.check_output(["xcrun", "lipo", "-archs", str(path)], text=True).split()
    if architectures != ["arm64"]:
        raise RuntimeError(f"Expected only arm64 in {path.name}: {architectures}")
    platforms = set()
    count = 0
    with tempfile.TemporaryFile(mode="w+") as output:
        subprocess.run(["xcrun", "otool", "-l", str(path)], stdout=output, check=True)
        output.seek(0)
        in_build_version = False
        for line in output:
            fields = line.split()
            if fields[:1] == ["cmd"]:
                in_build_version = fields == ["cmd", "LC_BUILD_VERSION"]
                if len(fields) == 2 and fields[1].startswith("LC_VERSION_MIN_"):
                    raise RuntimeError(f"Expected explicit platform load commands in {path.name}.")
            elif in_build_version and fields[:1] == ["platform"]:
                if len(fields) != 2:
                    raise RuntimeError("Unexpected otool platform record.")
                platforms.add({"IOS": "2", "IOSSIMULATOR": "7"}.get(fields[1], fields[1]))
                count += 1
    if platforms != {expected} or count == 0:
        raise RuntimeError(f"Wrong or missing Mach-O platform in {path.name}: {sorted(platforms)}")
    return {"architectures": architectures, "platform": expected, "build_version_commands": count}


def require_native_definitions(archive: Path) -> None:
    required = set(NATIVE_CLASSES) | {
        "__Z19apple_embedded_mainiPPc", "__Z21apple_embedded_finishv",
        "__Z39godot_apple_embedded_plugins_initializev",
        "__Z41godot_apple_embedded_plugins_deinitializev",
    }
    with tempfile.TemporaryFile(mode="w+") as output:
        subprocess.run(["xcrun", "nm", "-g", str(archive)], stdout=output, check=True)
        output.seek(0)
        for line in output:
            fields = line.split()
            if len(fields) >= 3 and fields[-2] in set("TtSsDdBbRr"):
                required.discard(fields[-1])
    if required:
        raise RuntimeError(f"Native archive lacks retained-engine definitions: {sorted(required)}")


def checked_inputs(args: argparse.Namespace) -> dict:
    key = (args.configuration, args.platform)
    if key not in VARIANTS:
        raise RuntimeError("Supported native inputs are Debug/iphonesimulator and Release/iphoneos.")
    target, simulator, platform_id = VARIANTS[key]
    engine_root = args.engine_root.resolve()
    engine_path = engine_root / "evidence/engine-artifact.json"
    engine = json.loads(engine_path.read_text())

    # Reuse the qualification host's pure patch validator, not its main() staging
    # routine. No qualification framework, authority, scene or fixture is copied.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(HOST))
    checks = runpy.run_path(str(HOST / "prepare-authority-host.py"))
    if (engine.get("engine_commit") != checks["COMMIT"]
            or engine.get("path_overrides_enabled") is not True
            or engine.get("bootstrap_arguments") != "native_owned_bundle_paths"):
        raise RuntimeError("The pinned native engine must permit its owned bundle path arguments.")
    checks["verify_engine_patch_receipt"](engine)

    modules = runpy.run_path(str(HOST / "stage-engine-inputs.py"))
    current = modules["inventory"](modules["capture"](HOST / "modules"))
    if (engine.get("native_module_sources") != current
            or engine.get("module_snapshot_sha256") != modules["inventory_digest"](current)
            or engine.get("native_module_capture_phase") != "before_scons"
            or engine.get("engine_checkout_policy") != "fresh_isolated_checkout"):
        raise RuntimeError("Rebuild the native engine from the current frozen module sources.")
    expected_build = {
        "platform": "ios", "sdk": args.platform, "architecture": "arm64",
        "target": target, "rendering_drivers": ["opengl3"], "xcode_version": "26.4.1",
    }
    if any(engine.get(k) != v for k, v in expected_build.items()):
        raise RuntimeError("Rebuild the selected native variant with its explicit target/SDK receipt.")
    # target + sdk also bind the existing Simulator checkpoint unambiguously.
    # The extended builder adds these fields for both variants; reject conflicts.
    for key, value in {"configuration": args.configuration, "simulator": simulator, "lto": "none"}.items():
        if key in engine and (type(engine[key]) is not type(value) or engine[key] != value):
            raise RuntimeError(f"Conflicting native build receipt field: {key}")
    xcode = subprocess.check_output(["xcodebuild", "-version"], text=True).splitlines()
    sdk = subprocess.check_output(["xcrun", "--sdk", args.platform, "--show-sdk-version"], text=True).strip()
    if (not xcode or xcode[0] != "Xcode 26.4.1"
            or ("sdk_version" in engine and engine["sdk_version"] != sdk)):
        raise RuntimeError("The native engine and production app must use the pinned Xcode and matching SDK.")
    items = [engine, *engine.get("auxiliary_archives", [])]
    if len(items) != 2 or {item.get("artifact") for item in items} != set(ARCHIVES):
        raise RuntimeError("Exactly the native engine and camera archives require build receipts.")
    suffix = ".simulator" if simulator else ""
    verified_archives = {}
    for item in items:
        name = item["artifact"]
        upstream = "libgodot" if name == ARCHIVES[0] else "libgodot_camera"
        if item.get("upstream_archive") != f"{upstream}.ios.{target}.arm64{suffix}.a":
            raise RuntimeError(f"Archive provenance does not match the selected variant: {name}")
        path = engine_root / "artifacts" / name
        actual = receipt(path)
        if any(item.get(k) != v for k, v in actual.items()):
            raise RuntimeError(f"Native archive differs from its receipt: {name}")
        verified_archives[name] = {**actual, "macho": apple_platform(path, platform_id)}
    require_native_definitions(engine_root / "artifacts" / ARCHIVES[0])

    pack = args.pack.resolve()
    subprocess.run([
        sys.executable, str(ROOT / "godot/tools/renderer.py"), "check-pack", "--pack", str(pack),
    ], check=True)
    pack_receipt = pack.with_suffix(".receipt.json")
    pack_info = receipt(pack)
    runtime = (HOST / "modules/partydeck_ios_probe/PDGodotRuntime.mm").read_text()
    pins = re.findall(r'^static NSString \*const PDQualifiedRetainedPackSHA256\s*=\s*@"([a-f0-9]{64})";', runtime, re.MULTILINE)
    if len(pins) != 1 or pins[0] != pack_info["sha256"]:
        raise RuntimeError("The shared PCK does not match the receipt-verified native retained-engine allowlist.")
    return {
        "schema_version": 1, "stage": "production_ios_inputs_only",
        "configuration": args.configuration, "platform": args.platform,
        "engine_root": str(engine_root), "engine_receipt": engine,
        "engine_receipt_file": receipt(engine_path), "archives": verified_archives,
        "pack_path": str(pack), "pack": pack_info, "pack_receipt": receipt(pack_receipt),
        "native_pack_sha256": pins[0], "ios_runtime_executed": False,
        "kmp_factory_qualified": False, "advertised_native_modes": [],
    }


def stage(args: argparse.Namespace, inputs: dict) -> None:
    destination = args.output.absolute()

    def path_kind(path: Path) -> str:
        if path.is_symlink():
            return "symlink"
        if path.is_dir():
            return "nonempty-directory" if any(path.iterdir()) else "empty-directory"
        if path.is_file():
            return "regular-file"
        return "other" if path.exists() else "missing"

    def check_destination() -> None:
        if destination.name != "PartyDeckGodotInputs" or destination.is_symlink():
            raise RuntimeError(
                "Use the ordinary generated PartyDeckGodotInputs directory. "
                f"Destination kind: {path_kind(destination)}."
            )
        if not destination.exists():
            return
        if destination.is_dir():
            marker = destination / "inputs.json"
            # Preserve ordinary receipt-marker ownership for generated refreshes.
            if not marker.is_symlink() and marker.is_file():
                return
            children = [(path.name, path_kind(path)) for path in sorted(destination.iterdir())]
            # Declared build outputs can have their parent directories created
            # before this phase. Accept only the empty directories we generate.
            if all(name in {"artifacts", "ProbeResources"} and kind == "empty-directory"
                   for name, kind in children):
                return
            details = ", ".join(f"{json.dumps(name[:80])}: {kind}" for name, kind in children[:8])
            if len(children) > 8:
                details += f", ... ({len(children) - 8} more entries)"
            details = f"directory children: [{details}]"
        else:
            details = f"destination kind: {path_kind(destination)}"
        raise RuntimeError(f"Refusing to replace an unrecognized native input directory; {details}.")

    check_destination()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".partydeck-godot-", dir=destination.parent) as temporary:
        prepared = Path(temporary) / "PartyDeckGodotInputs"
        libraries = prepared / "artifacts"
        resources = prepared / "ProbeResources"
        libraries.mkdir(parents=True)
        resources.mkdir()
        for name in ARCHIVES:
            target = libraries / name
            shutil.copy2(Path(inputs["engine_root"]) / "artifacts" / name, target)
            if receipt(target) != {k: inputs["archives"][name][k] for k in ("sha256", "bytes")}:
                raise RuntimeError("A native archive changed while staging.")
        source_pack = Path(inputs["pack_path"])
        for source, name, expected in (
            (source_pack, "partydeck-last-light.pck", inputs["pack"]),
            (source_pack.with_suffix(".receipt.json"), "partydeck-last-light.receipt.json", inputs["pack_receipt"]),
        ):
            shutil.copy2(source, resources / name)
            if receipt(resources / name) != expected:
                raise RuntimeError("The PCK or export receipt changed while staging.")
        licenses = ROOT / "godot/renderer/licenses"
        for name in ("GODOT_LICENSE.txt", "GODOT_COPYRIGHT.txt", "GODOT_CA_BUNDLE_SOURCE.txt",
                     "GODOT_CA_CERTIFICATES_SOURCE.txt", "NOTICE_PROVENANCE.json"):
            if not (licenses / name).is_file():
                raise RuntimeError(f"Missing canonical Godot notice: {name}")
        shutil.copytree(licenses, resources / "Licenses")
        inputs["resource_files"] = {
            path.relative_to(resources).as_posix(): receipt(path)
            for path in sorted(resources.rglob("*")) if path.is_file()
        }
        write_json(prepared / "inputs.json", inputs)
        check_destination()
        if destination.exists():
            shutil.rmtree(destination)
        prepared.rename(destination)


def verify_app(args: argparse.Namespace) -> None:
    inputs = json.loads(args.inputs.read_text())
    if inputs.get("schema_version") != 1 or inputs.get("stage") != "production_ios_inputs_only":
        raise RuntimeError("Expected the production native input receipt from this build.")
    if (inputs.get("resource_files", {}).get("partydeck-last-light.pck") != inputs.get("pack")
            or inputs.get("pack", {}).get("sha256") != inputs.get("native_pack_sha256")
            or "partydeck-last-light.receipt.json" not in inputs.get("resource_files", {})):
        raise RuntimeError("The production resource receipt must identify its native-pinned PCK and export receipt.")
    app = args.app.resolve()
    info = plistlib.loads((app / "Info.plist").read_bytes())
    if info.get("PartyDeckQualifiedGodotPresentations") not in (None, []):
        raise RuntimeError("Native presentations must remain unadvertised until separately qualified.")
    if (app / "PartyDeck.debug.dylib").exists() or (app / "Frameworks/PartyDeckGodotBridge.framework").exists():
        raise RuntimeError("Unexpected debug executor or qualification framework in the production app.")
    resources = app / "ProbeResources"
    actual = {
        path.relative_to(resources).as_posix(): receipt(path)
        for path in sorted(resources.rglob("*")) if path.is_file()
    }
    if actual != inputs.get("resource_files"):
        raise RuntimeError("The app must contain exactly the staged ProbeResources pack, receipt and notices.")

    objects = {}
    symbols = {}
    section = None
    with args.link_map.open(errors="replace") as source:
        for line in source:
            if "PartyDeckGodotBridge" in line or "PDGBIosQualification" in line:
                raise RuntimeError("A second Kotlin qualification graph entered the production link.")
            if "godot_swift_module10SwiftUIApp" in line:
                raise RuntimeError("Godot's exporter-owned SwiftUI application entered the production link.")
            if line.strip() in {"# Object files:", "# Sections:", "# Symbols:", "# Dead Stripped Symbols:"}:
                section = line.strip()
            elif section == "# Object files:":
                match = re.match(r"\[\s*(\d+)\]\s+(.+)", line)
                if match:
                    objects[match[1]] = match[2]
            elif section == "# Symbols:":
                match = re.match(r"0x[0-9A-Fa-f]+\s+0x[0-9A-Fa-f]+\s+\[\s*(\d+)\]\s+(.+)", line)
                if match:
                    symbols.setdefault(match[2], []).append(match[1])
    for symbol in ("_main", *NATIVE_CLASSES):
        if len(symbols.get(symbol, [])) != 1:
            raise RuntimeError(f"The production executable needs exactly one live definition of {symbol}.")
    kotlin_owners = {
        match[1] for value in objects.values()
        if (match := re.match(r"(.+PartyDeckKit\.framework/PartyDeckKit)\(", value))
    }
    if len(kotlin_owners) != 1:
        raise RuntimeError("Expected exactly one linked static PartyDeckKit framework.")
    loaded_archive_members = {}
    for name in ARCHIVES:
        archive_path = args.inputs.parent / "artifacts" / name
        if receipt(archive_path) != {k: inputs["archives"][name][k] for k in ("sha256", "bytes")}:
            raise RuntimeError(f"Staged archive changed before production link verification: {name}")
        owners = {
            match[1] for value in objects.values()
            if (match := re.match(r"(.+/" + re.escape(name) + r")\(", value))
        }
        expected = archive_path.resolve()
        # The camera archive is a required link input but can have no loaded
        # members when the retained presentation does not reference a camera.
        if ((name == ARCHIVES[0] and not owners)
                or (owners and {Path(path).resolve() for path in owners} != {expected})):
            raise RuntimeError(f"The production link used an unexpected native engine archive: {name}")
        loaded_archive_members[name] = sum(name + "(" in value for value in objects.values())
    main_owner = objects.get(symbols["_main"][0], "")
    if "libgodot" in main_owner or "libpartydeck_godot" in main_owner:
        raise RuntimeError("The application entry point must belong to PartyDeck.")
    executable = app / info["CFBundleExecutable"]
    _, _, platform_id = VARIANTS[(inputs["configuration"], inputs["platform"])]
    write_json(args.output, {
        "schema_version": 1, "stage": "production_ios_app_link_only", "inputs": inputs,
        "executable": receipt(executable), "macho": apple_platform(executable, platform_id),
        "link_map": receipt(args.link_map), "partydeck_kit_link_owners": sorted(kotlin_owners),
        "loaded_archive_members": loaded_archive_members,
        "linked_native_classes": list(NATIVE_CLASSES), "main_owner": main_owner,
        "ios_runtime_executed": False, "kmp_factory_qualified": False,
        "advertised_native_modes": [],
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "stage"):
        command = commands.add_parser(name)
        command.add_argument("--configuration", required=True)
        command.add_argument("--platform", required=True)
        command.add_argument("--engine-root", type=Path, required=True)
        command.add_argument("--pack", type=Path, required=True)
        if name == "stage":
            command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("verify-app")
    for name in ("app", "inputs", "link-map", "output"):
        command.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify-app":
        verify_app(args)
        print("Verified production iOS linkage and bundle resources; native modes remain unqualified.")
    else:
        inputs = checked_inputs(args)
        if args.command == "stage":
            stage(args, inputs)
        print(f"Verified {args.configuration}/{args.platform} native archives and the pinned renderer PCK.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
