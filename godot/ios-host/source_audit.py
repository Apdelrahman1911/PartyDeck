#!/usr/bin/env python3
"""Inspect the pinned engine source; this does not run an iOS renderer."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


TAG = "4.7.2-stable"
COMMIT = "ed1daf0bf001b61586d9930840f2f1394092c079"
REPOSITORY = "https://github.com/godotengine/godot.git"

SOURCES = {
    "SConstruct": ["Library builds unsupported", 'env.Append(CPPDEFINES=["LIBGODOT_ENABLED"])'],
    "platform/ios/detect.py": ['"supported": ["metal", "mono"]', 'env["metal"] = False', 'env["vulkan"] = False'],
    "platform/ios/SCsub": ['"main_ios.mm"', "combine_libs_apple_embedded"],
    "platform/ios/main_ios.mm": ["int apple_embedded_main(int argc, char **argv)", "void apple_embedded_finish()", "delete os;"],
    "core/extension/libgodot.h": ["libgodot_create_godot_instance", "libgodot_destroy_godot_instance"],
    "drivers/apple_embedded/app.swift": ["UIViewControllerRepresentable", "@main", "GDTAppDelegateService.viewController = viewController"],
    "drivers/apple_embedded/godot_view_controller.h": ["@interface GDTViewController : UIViewController", "propagateUIPreferencesToRootViewController"],
    "drivers/apple_embedded/godot_view_controller.mm": ["method_setImplementation", "[self.godotView startRendering]", "[self.godotView stopRendering]"],
    "drivers/apple_embedded/godot_view_apple_embedded.mm": ["CFRunLoopRunInMode", "[self.renderer renderOnView:self]"],
    "drivers/apple_embedded/display_server_apple_embedded.mm": ["GDTAppDelegateService.viewController.godotView", "initializeRenderingForDriver"],
    "drivers/apple_embedded/godot_view_renderer.mm": ["Main::setup2()", "OS_AppleEmbedded::get_singleton()->start()", "OS_AppleEmbedded::get_singleton()->iterate()"],
    "platform/macos/libgodot_macos.mm": ["Only one Godot Instance may be created.", "When Godot Engine supports reinitialization"],
}


def inspect(source: Path) -> dict:
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != COMMIT:
        raise RuntimeError(f"Expected Godot {COMMIT}; found {revision}.")
    subprocess.run(["git", "-C", str(source), "diff", "--exit-code", "HEAD", "--"], check=True, stdout=subprocess.DEVNULL)
    findings = []
    for relative, required in SOURCES.items():
        path = source / relative
        contents = path.read_text()
        missing = [marker for marker in required if marker not in contents]
        if missing:
            raise RuntimeError(f"Pinned source assumption changed in {relative}: {missing}")
        findings.append({
            "path": relative,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "url": f"https://github.com/godotengine/godot/blob/{COMMIT}/{relative}",
            "lines": {marker: contents[:contents.index(marker)].count("\n") + 1 for marker in required},
        })
    return {
        "tag": TAG,
        "commit": revision,
        "source_audit": "passed",
        "ios_libgodot_library_mode": "unsupported_by_upstream_build",
        "ios_native_surface": "internal_GDTView_source_candidate",
        "ios_runtime_executed": False,
        "kmp_factory_qualified": False,
        "upstream_patches": [],
        "sources": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pin", choices=("tag", "commit", "repository"))
    args = parser.parse_args()
    if args.pin:
        print({"tag": TAG, "commit": COMMIT, "repository": REPOSITORY}[args.pin])
        return
    if args.source is None or args.output is None:
        parser.error("--source and --output are required for an audit")
    result = inspect(args.source.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Pinned source audit passed: {args.output}")


if __name__ == "__main__":
    main()
