#!/usr/bin/env python3
"""Inspect the pinned engine source; this does not run an iOS renderer."""

import argparse
import hashlib
import json
from pathlib import Path
import stat
import subprocess


TAG = "4.7.2-stable"
COMMIT = "ed1daf0bf001b61586d9930840f2f1394092c079"
REPOSITORY = "https://github.com/godotengine/godot.git"
ROOT = Path(__file__).resolve().parent
PATCH_FILES_BY_NAME = {
    "coreaudio-dormancy": {
        "drivers/coreaudio/audio_driver_coreaudio.h",
        "drivers/coreaudio/audio_driver_coreaudio.mm",
        "servers/audio/audio_server.h",
        "servers/audio/audio_server.cpp",
    },
    "iteration-phases": {"core/os/os.h", "core/os/os.cpp", "main/main.cpp"},
    "main-loop-access": {
        "drivers/apple_embedded/os_apple_embedded.h",
    },
}
PATCH_FILES = set().union(*PATCH_FILES_BY_NAME.values())

SOURCES = {
    "SConstruct": ["Library builds unsupported", 'env.Append(CPPDEFINES=["LIBGODOT_ENABLED"])', '"disable_path_overrides"', 'env.Append(CPPDEFINES=["OVERRIDE_PATH_ENABLED"])', 'BoolVariable("sdl", "Enable the SDL3 input driver", True)'],
    "platform/ios/detect.py": ['"supported": ["metal", "mono"]', 'env["metal"] = False', 'env["vulkan"] = False', 'if env["sdl"]:', 'env.Append(CPPDEFINES=["SDL_ENABLED"])'],
    "platform/ios/SCsub": ['"main_ios.mm"', "combine_libs_apple_embedded"],
    "platform/ios/main_ios.mm": ["int apple_embedded_main(int argc, char **argv)", "void apple_embedded_finish()", "delete os;"],
    "platform/ios/api/api.cpp": ["godot_apple_embedded_plugins_initialize()", "godot_apple_embedded_plugins_deinitialize()"],
    "editor/export/editor_export_platform_apple_embedded.cpp": ["String plugin_initialization_cpp_code;", "void godot_apple_embedded_plugins_initialize()", "void godot_apple_embedded_plugins_deinitialize()"],
    "drivers/SCsub": ['if env["sdl"] and env["platform"] in ["linuxbsd", "macos", "windows", "ios", "visionos"]:'],
    "drivers/sdl/joypad_sdl.cpp": ['SDL_SetHint(SDL_HINT_JOYSTICK_THREAD, "1")', "SDL_Init(SDL_INIT_JOYSTICK | SDL_INIT_GAMEPAD)"],
    "drivers/apple_embedded/main_utilities.mm": ["char path[512]", "r_args[p_argc] = nullptr", "godot_cmdline"],
    "main/main.cpp": ["Error Main::setup2", "_start_success = true", "ERR_FAIL_COND(!_start_success)", "int Main::start()", "without support for path overrides", "disable_path_overrides=no"],
    "core/extension/libgodot.h": ["libgodot_create_godot_instance", "libgodot_destroy_godot_instance"],
    "drivers/apple_embedded/app.swift": ["UIViewControllerRepresentable", "@main", "GDTAppDelegateService.viewController = viewController"],
    "drivers/apple_embedded/godot_view_controller.h": ["@interface GDTViewController : UIViewController", "propagateUIPreferencesToRootViewController"],
    "drivers/apple_embedded/godot_view_controller.mm": ["method_setImplementation", "[self.godotView startRendering]", "[self.godotView stopRendering]"],
    "drivers/apple_embedded/godot_view_apple_embedded.mm": ["CFRunLoopRunInMode", "[self.renderer renderOnView:self]"],
    "drivers/apple_embedded/display_server_apple_embedded.mm": ["GDTAppDelegateService.viewController.godotView", "initializeRenderingForDriver", "screen_set_keep_on(keep_screen_on)", "[UIApplication sharedApplication].idleTimerDisabled = p_enable;", "* screen_get_max_scale()", "return screen_get_scale(DisplayServerEnums::SCREEN_OF_MAIN_WINDOW);"],
    "platform/ios/display_server_ios.mm": ["float DisplayServerIOS::screen_get_scale(int p_screen) const", "return [UIScreen mainScreen].scale;"],
    "drivers/apple_embedded/godot_view_renderer.mm": ["Main::setup2()", "OS_AppleEmbedded::get_singleton()->start()", "OS_AppleEmbedded::get_singleton()->iterate()"],
    "core/os/os.h": ["friend class Main;", "virtual void set_main_loop(MainLoop *p_main_loop) = 0;", "virtual void delete_main_loop() = 0;"],
    "drivers/apple_embedded/os_apple_embedded.h": ["virtual void set_main_loop(MainLoop *p_main_loop) override;", "virtual void delete_main_loop() override;", "static OS_AppleEmbedded *get_singleton();"],
    "drivers/apple_embedded/os_apple_embedded.mm": ["main_loop->initialize()", "audio_driver.stop()", "audio_driver.start()", "handle_application_pause", "void OS_AppleEmbedded::delete_main_loop()", "main_loop = nullptr;", "#ifdef SDL_ENABLED"],
    "scene/main/scene_tree.cpp": ["void SceneTree::initialize()", "void SceneTree::finalize()", "SceneTree::~SceneTree()", "timers.clear();", "tweens.clear();"],
    "scene/main/window.cpp": ["MAIN_WINDOW_ID", "window_set_input_event_callback"],
    "core/object/message_queue.cpp": ["Error CallQueue::flush()", "has_messages() const", "is_flushing() const"],
    "core/input/input.cpp": ["void Input::flush_buffered_events()", "void Input::release_pressed_events()"],
    "modules/gdscript/gdscript.cpp": ["GDScriptInstance::~GDScriptInstance()", "pending_func_states"],
    "drivers/coreaudio/audio_driver_coreaudio.h": ["AudioDriverCoreAudio", "void stop()"],
    "drivers/coreaudio/audio_driver_coreaudio.mm": ["AudioOutputUnitStop", "AudioOutputUnitStart", "output_callback"],
    "servers/audio/audio_server.h": ["SafeList", "AudioServer"],
    "servers/audio/audio_server.cpp": ["_delete_stream_playback", "_cleanup_lists()"],
    "platform/ios/godot_view_ios.mm": ["@implementation GDTViewIOS", "GDTOpenGLLayer layer", "initializeDisplayLayer"],
    "platform/ios/display_layer_ios.mm": ["@implementation GDTOpenGLLayer", "presentRenderbuffer", "setCurrentContext:nil"],
    "platform/macos/libgodot_macos.mm": ["Only one Godot Instance may be created.", "When Godot Engine supports reinitialization"],
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regular_file(path: Path) -> bytes:
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode) or mode & 0o111:
        raise RuntimeError(f"Expected an ordinary non-executable file, not a symlink/type change: {path}")
    return path.read_bytes()


def patch_inventory(source: Path, apply_patches: bool) -> list:
    changed = set(subprocess.check_output(["git", "-c", "core.filemode=true", "-C", str(source), "diff", "--name-only", "HEAD", "--"], text=True).splitlines())
    if changed - PATCH_FILES:
        raise RuntimeError(f"Unexpected tracked upstream modifications: {sorted(changed - PATCH_FILES)}")
    inventories = []
    for name, expected_files in PATCH_FILES_BY_NAME.items():
        manifest_path = ROOT / "patches" / f"{name}.json"
        manifest_bytes = regular_file(manifest_path)
        manifest = json.loads(manifest_bytes)
        if (manifest.get("schemaVersion") != 1 or manifest.get("baseCommit") != COMMIT
                or manifest.get("baseVersion") != TAG or manifest.get("patchFile") != f"{name}.patch"
                or manifest.get("platformGuard") != "IOS_ENABLED"):
            raise RuntimeError(f"The maintained {name} patch does not identify this pinned iOS engine.")
        patch_path = manifest_path.parent / manifest["patchFile"]
        if sha256(regular_file(patch_path)) != manifest.get("patchSha256"):
            raise RuntimeError(f"The maintained {name} patch differs from its provenance.")
        files = manifest.get("files", [])
        if len(files) != len(expected_files) or {item.get("path") for item in files} != expected_files:
            raise RuntimeError(f"Only the reviewed {name} files may be patched.")
        for item in files:
            original = subprocess.check_output(["git", "-C", str(source), "show", f"HEAD:{item['path']}"])
            if sha256(original) != item.get("originalSha256"):
                raise RuntimeError(f"The patch's pristine source differs: {item['path']}")
        current = {item["path"]: sha256(regular_file(source / item["path"])) for item in files}
        pristine = all(current[item["path"]] == item["originalSha256"] for item in files)
        patched = all(current[item["path"]] == item["patchedSha256"] for item in files)
        if not pristine and not patched:
            raise RuntimeError(f"The {name} source is neither pristine nor the complete reviewed patch.")
        inventories.append(({
            "name": name, "base_commit": COMMIT,
            "patch_sha256": manifest["patchSha256"], "manifest_sha256": sha256(manifest_bytes),
            "applied": patched, "files": files,
        }, patch_path, pristine))
    if apply_patches and any(pristine for _, _, pristine in inventories):
        if source == (ROOT / "build/upstream").resolve():
            raise RuntimeError("The shared build/upstream checkout is a read-only reference; patch an isolated engine checkout.")
        # Validate every requested patch before changing the isolated checkout.
        for _, patch_path, pristine in inventories:
            if pristine:
                subprocess.run(["git", "-C", str(source), "apply", "--check", "--whitespace=error", str(patch_path)], check=True)
        for receipt, patch_path, pristine in inventories:
            if pristine:
                subprocess.run(["git", "-C", str(source), "apply", "--whitespace=error", str(patch_path)], check=True)
                receipt["applied"] = all(sha256(regular_file(source / item["path"])) == item["patchedSha256"] for item in receipt["files"])
                if not receipt["applied"]:
                    raise RuntimeError(f"Applying the reviewed {receipt['name']} patch did not produce the exact recorded bytes.")
    return [receipt for receipt, _, _ in inventories]


def inspect(source: Path, apply_patches: bool = False, require_pristine: bool = False, require_no_untracked: bool = False) -> dict:
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != COMMIT:
        raise RuntimeError(f"Expected Godot {COMMIT}; found {revision}.")
    # SConstruct reads ignored custom.py, and native globs can include ignored
    # *.gen.mm. Fresh build checkouts reject all untracked inputs before SCons.
    untracked_args = ["git", "-C", str(source), "ls-files", "--others", "-z"]
    if not require_no_untracked:
        untracked_args.append("--exclude-standard")
    untracked = subprocess.check_output(untracked_args).decode().rstrip("\0").split("\0")
    if untracked != [""]:
        raise RuntimeError(f"Unexpected untracked upstream inputs: {untracked[:20]}")
    patches = patch_inventory(source, apply_patches)
    if require_pristine and any(patch["applied"] for patch in patches):
        raise RuntimeError("The shared engine reference must remain pristine.")
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
        "no_untracked_inputs_required": require_no_untracked,
        "ios_libgodot_library_mode": "unsupported_by_upstream_build",
        "ios_native_surface": "internal_GDTView_source_candidate",
        "ios_runtime_executed": False,
        "kmp_factory_qualified": False,
        "upstream_patches": patches,
        "required_template_option": "disable_path_overrides=no",
        "exported_apple_plugins": [],
        "required_input_option": "sdl=no",
        "native_input_scope": "touch_and_hardware_keyboard",
        "sdl_device_query_glue": "removed_with_disabled_sdl_driver",
        "sources": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pin", choices=("tag", "commit", "repository"))
    parser.add_argument("--apply-patches", action="store_true")
    parser.add_argument("--require-pristine", action="store_true")
    parser.add_argument("--require-no-untracked", action="store_true")
    args = parser.parse_args()
    if args.pin:
        print({"tag": TAG, "commit": COMMIT, "repository": REPOSITORY}[args.pin])
        return
    if args.source is None or args.output is None:
        parser.error("--source and --output are required for an audit")
    if args.apply_patches and args.require_pristine:
        parser.error("--apply-patches and --require-pristine are mutually exclusive")
    result = inspect(args.source.resolve(), args.apply_patches, args.require_pristine, args.require_no_untracked)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Pinned source audit passed: {args.output}")


if __name__ == "__main__":
    main()
