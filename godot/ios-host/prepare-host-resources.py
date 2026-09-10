#!/usr/bin/env python3
"""Prepare the diagnostic's real scene and authority-generated launch fixture."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, help="Optional independently verified shared 2D/3D pack.")
    args = parser.parse_args()
    fixture_dir = ROOT.parent / "bridge" / "fixtures"
    fixture = fixture_dir / "launch-2d.json"
    manifest_path = fixture_dir / "fixture-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if sha256(fixture) != manifest["sha256"][fixture.name]:
        raise SystemExit("Authority fixture does not match its generated manifest.")
    if fixture.stat().st_size > 65536:
        raise SystemExit("Authority launch fixture exceeds the native envelope bound.")
    output = ROOT / "build" / "host-resources"
    if output.is_symlink():
        raise SystemExit("Generated resource output must not be a symlink.")
    if output.exists():
        shutil.rmtree(output)
    scene = output / "ProbeScene"
    resources = output / "ProbeResources"
    scene.mkdir(parents=True)
    resources.mkdir()
    source_hashes = {}
    for filename in ("project.godot", "main.tscn", "main.gd"):
        source = ROOT / "ProbeScene" / filename
        shutil.copy2(source, scene / filename)
        source_hashes[f"ProbeScene/{filename}"] = sha256(source)
    shutil.copy2(fixture, resources / "Launch.json")
    shutil.copy2(manifest_path, resources / "fixture-manifest.json")
    license_root = ROOT.parent / "renderer" / "licenses"
    license_hashes = {}
    for source in sorted(license_root.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(license_root)
        destination = resources / "Licenses" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        license_hashes[relative.as_posix()] = sha256(destination)
    for required in ("GODOT_LICENSE.txt", "GODOT_COPYRIGHT.txt", "GODOT_CA_BUNDLE_SOURCE.txt",
                     "GODOT_CA_CERTIFICATES_SOURCE.txt", "NOTICE_PROVENANCE.json"):
        if required not in license_hashes:
            raise SystemExit(f"The canonical Godot license/source bundle is incomplete: {required}")
    pack_receipt = None
    if args.pack is not None:
        pack = args.pack.resolve()
        subprocess.run([
            sys.executable, str(ROOT.parent / "tools" / "renderer.py"),
            "check-pack", "--pack", str(pack),
        ], check=True)
        shutil.copy2(pack, resources / "partydeck-last-light.pck")
        companion = pack.with_suffix(".receipt.json")
        if not companion.is_file():
            raise SystemExit("The shared pack's verified companion receipt is required.")
        shutil.copy2(companion, resources / "partydeck-last-light.receipt.json")
        pack_receipt = {"sha256": sha256(pack), "bytes": pack.stat().st_size}
    receipt = {
        "stage": "host_resources_only",
        "fixture_sha256": sha256(fixture),
        "fixture_manifest_sha256": sha256(manifest_path),
        "fixture_authority": manifest["authority"],
        "diagnostic_sources": source_hashes,
        "license_bundle_sha256": license_hashes,
        "optional_shared_pack": pack_receipt,
        "ios_runtime_executed": False,
        "kmp_factory_qualified": False,
    }
    evidence = ROOT / "build" / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "host-resources.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("Prepared the real diagnostic scene and verified authority fixture.")


if __name__ == "__main__":
    main()
