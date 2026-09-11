#!/usr/bin/env python3
"""Freeze and verify the exact native module inputs before the engine build."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


MODULE_FILES = {
    f"partydeck_ios_probe/{name}" for name in (
        "AppleExportPlugins.mm", "PDGodotEngineOwner.h", "PDGodotRuntime.h",
        "PDGodotRuntime.mm", "SCsub", "config.py", "engine_surface_probe.mm",
        "frame_timing.h", "register_types.h", "strict_json.h",
    )
}


def capture(root: Path) -> dict[str, bytes]:
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError(f"Expected an ordinary module directory: {root}")
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode) and relative == "partydeck_ios_probe":
            continue
        if not stat.S_ISREG(mode) or relative not in MODULE_FILES:
            raise RuntimeError(f"Unexpected module input or file type: {relative}")
        result[relative] = path.read_bytes()
    if set(result) != MODULE_FILES:
        raise RuntimeError(f"Missing module inputs: {sorted(MODULE_FILES - set(result))}")
    return result


def inventory(contents: dict[str, bytes]) -> dict[str, str]:
    return {name: hashlib.sha256(data).hexdigest() for name, data in sorted(contents.items())}


def inventory_digest(files: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify(receipt: dict) -> None:
    observed = inventory(capture(Path(receipt["module_snapshot_path"])))
    if observed != receipt["native_module_sources"] or inventory_digest(observed) != receipt["module_snapshot_sha256"]:
        raise RuntimeError("The frozen native module inputs changed after capture.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modules", type=Path)
    parser.add_argument("--snapshots", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        verify(json.loads(args.verify.read_text()))
        print(f"Frozen module inputs verified: {args.verify}")
        return
    if args.modules is None or args.snapshots is None or args.output is None:
        parser.error("--modules, --snapshots and --output are required to capture inputs")
    contents = capture(args.modules)
    files = inventory(contents)
    digest = inventory_digest(files)
    args.snapshots.mkdir(parents=True, exist_ok=True)
    destination = args.snapshots.resolve() / digest
    if not destination.exists():
        temporary = Path(tempfile.mkdtemp(prefix="capture-", dir=args.snapshots))
        modules = temporary / "modules"
        (modules / "partydeck_ios_probe").mkdir(parents=True)
        for relative, data in contents.items():
            path = modules / relative
            path.write_bytes(data)
            path.chmod(0o444)
        if inventory(capture(modules)) != files or inventory(capture(args.modules)) != files:
            raise RuntimeError("Native module files changed while capturing the build inputs.")
        (modules / "partydeck_ios_probe").chmod(0o555)
        modules.chmod(0o555)
        temporary.chmod(0o555)
        os.rename(temporary, destination)
    elif inventory(capture(args.modules)) != files:
        raise RuntimeError("Native module files changed while selecting their frozen snapshot.")
    receipt = {
        "schema_version": 1,
        "module_snapshot_path": str(destination / "modules"),
        "module_snapshot_sha256": digest,
        "native_module_sources": files,
        "capture_phase": "before_scons",
    }
    verify(receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(receipt["module_snapshot_path"])


if __name__ == "__main__":
    main()
