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
    "SConstruct": ["Library builds unsupported", 'env.Append(CPPDEFINES=["LIBGODOT_ENABLED"])', '"disable_path_overrides"', 'env.Append(CPPDEFINES=["OVERRIDE_PATH_ENABLED"])'],
    "platform/ios/detect.py": ['"supported": ["metal", "mono"]', 'env["metal"] = False', 'env["vulkan"] = False'],
    "platform/ios/SCsub": ['"main_ios.mm"', "combine_libs_apple_embedded"],
    "platform/ios/main_ios.mm": ["int apple_embedded_main(int argc, char **argv)", "void apple_embedded_finish()", "delete os;"],
    "platform/ios/api/api.cpp": ["godot_apple_embedded_plugins_initialize()", "godot_apple_embedded_plugins_deinitialize()"],
    "editor/export/editor_export_platform_apple_embedded.cpp": ["String plugin_initialization_cpp_code;", "void godot_apple_embedded_plugins_initialize()", "void godot_apple_embedded_plugins_deinitialize()"],
    "thirdparty/README.md": ["3.2.28 (7f3ae3d57459e59943a4ecfefc8f6277ec6bf540"],
    "thirdparty/sdl/SDL.c": ["extern bool SDL_IsIPad(void)", "extern bool SDL_IsAppleTV(void)"],
    "drivers/sdl/SCsub": ['elif env["platform"] in ["ios", "visionos"]', '"joystick/apple/SDL_mfijoystick.m"'],
    "drivers/apple_embedded/main_utilities.mm": ["char path[512]", "r_args[p_argc] = nullptr", "godot_cmdline"],
    "main/main.cpp": ["Error Main::setup2", "_start_success = true", "ERR_FAIL_COND(!_start_success)", "int Main::start()", "without support for path overrides", "disable_path_overrides=no"],
    "core/extension/libgodot.h": ["libgodot_create_godot_instance", "libgodot_destroy_godot_instance"],
    "drivers/apple_embedded/app.swift": ["UIViewControllerRepresentable", "@main", "GDTAppDelegateService.viewController = viewController"],
    "drivers/apple_embedded/godot_view_controller.h": ["@interface GDTViewController : UIViewController", "propagateUIPreferencesToRootViewController"],
    "drivers/apple_embedded/godot_view_controller.mm": ["method_setImplementation", "[self.godotView startRendering]", "[self.godotView stopRendering]"],
    "drivers/apple_embedded/godot_view_apple_embedded.mm": ["CFRunLoopRunInMode", "[self.renderer renderOnView:self]"],
    "drivers/apple_embedded/display_server_apple_embedded.mm": ["GDTAppDelegateService.viewController.godotView", "initializeRenderingForDriver", "screen_set_keep_on(keep_screen_on)", "[UIApplication sharedApplication].idleTimerDisabled = p_enable;"],
    "drivers/apple_embedded/godot_view_renderer.mm": ["Main::setup2()", "OS_AppleEmbedded::get_singleton()->start()", "OS_AppleEmbedded::get_singleton()->iterate()"],
    "drivers/apple_embedded/os_apple_embedded.mm": ["main_loop->initialize()", "audio_driver.stop()", "audio_driver.start()", "handle_application_pause"],
    "platform/ios/godot_view_ios.mm": ["@implementation GDTViewIOS", "GDTOpenGLLayer layer", "initializeDisplayLayer"],
    "platform/ios/display_layer_ios.mm": ["@implementation GDTOpenGLLayer", "presentRenderbuffer", "setCurrentContext:nil"],
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
        "required_template_option": "disable_path_overrides=no",
        "exported_apple_plugins": [],
        "extracted_sdl_device_queries": {
            "upstream_url": "https://github.com/libsdl-org/SDL/blob/7f3ae3d57459e59943a4ecfefc8f6277ec6bf540/src/video/uikit/SDL_uikitvideo.m",
            "upstream_file_sha256": "e42cc222f7c551fe2100ff98ce1035db6c2d6c164bb585bc5b2d3d8456d2ef31",
            "functions": ["SDL_IsIPad", "SDL_IsAppleTV"],
            "behavior": "unchanged_UIDevice_userInterfaceIdiom_queries",
        },
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
