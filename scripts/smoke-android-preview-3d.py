#!/usr/bin/env python3
"""Exercise one real 3D practice in the exact debug preview on an API36 emulator.

Reuse the session harness's real picker/Reveal/select/single-Play/Standard
outcome/Leave route. Original native PNGs support visual review; display geometry
and accepted input do not establish sharpness, animation quality or audible sound.
The dedicated emulator's PartyDeck data is cleared by the installation check.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import sys
import xml.etree.ElementTree as ET
import zipfile


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "partydeck_preview_shipping_helpers", Path(__file__).with_name("smoke-android-godot-shipping.py"))
shipping = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = shipping
SPEC.loader.exec_module(shipping)
session = shipping.session
require = session.require
EXPECTED_CHECKS = frozenset({
    "package-inputs", "installation", "display", "3d.engine-practice-baseline",
    "3d.engine-reveal-selection", "3d.engine-play-standard-outcome", "3d.engine-leave-end",
})
REQUIRED_NATIVE_CAPTURES = frozenset({"3d-engine-entry-native-ready", "3d-engine-selected"})


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def bounded_bytes(path, maximum):
    shipping.file_record(path)
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    require(len(raw) <= maximum, "Original package document exceeds its bound.")
    return raw


def record_package_inputs(args, output):
    """Produce the existing session wrapper's input contract, without a rebuild."""
    pack = ROOT / "godot/qualification/build/renderer/partydeck-last-light.pck"
    expectation = ROOT / "build/ci/android/godot-activation-build.json"
    record = {"variant": "debug", "apk": str(args.apk.resolve()),
              "sourceRevision": args.source_revision, "verified": False}
    try:
        record["context"] = shipping.build_context(args.source_revision)
        record["apkSha256"] = shipping.file_record(args.apk)["sha256"]
        record["packSha256"] = shipping.file_record(pack)["sha256"]
        shipping.checked_command(
            [sys.executable, "-B", ROOT / "godot/tools/renderer.py", "check-pack", "--pack", pack],
            output, "source-pack-check", timeout=180)
        renderer_receipt = bounded_bytes(pack.with_suffix(".receipt.json"), 8 * 1024 * 1024)
        (output / "renderer.receipt.json").write_bytes(renderer_receipt)
        record["rendererReceiptSha256"] = hashlib.sha256(renderer_receipt).hexdigest()
        with zipfile.ZipFile(args.apk) as archive:
            name = "assets/partydeck-last-light.pck"
            require(archive.namelist().count(name) == 1, "Expected one real embedded renderer pack.")
            with archive.open(name) as stream:
                record["embeddedPackSha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        require(record["embeddedPackSha256"] == record["packSha256"],
                "The exact preview APK differs from the source-checked renderer pack.")
        expected_raw = bounded_bytes(expectation, 4096)
        (output / "activation-build-expectation.json").write_bytes(expected_raw)
        expected = session.activation.parse_build_expectation(expected_raw)
        analyzer = Path(os.environ["ANDROID_HOME"]) / "cmdline-tools/latest/bin/apkanalyzer"
        command = [str(analyzer), "manifest", "print", str(args.apk)]
        manifest = shipping.checked_command(command, output, "packaged-manifest")
        (output / "packaged-manifest.xml").write_bytes(manifest)
        require(len(manifest) <= 2_097_152, "Decoded APK manifest exceeds its bound.")
        packaged = session.activation.parse_packaged_manifest(manifest)
        session.activation.require_qualification_match(expected, packaged, "2d,3d")
        application = ET.fromstring(manifest).find("application")
        require(application.get(session.activation.ANDROID + "debuggable") == "true",
                "The preview 3D check requires the actual debug APK.")
        record["activation"] = {
            "verified": True, "expected": expected, "packaged": packaged,
            "expectationSha256": hashlib.sha256(expected_raw).hexdigest(),
            "manifestSha256": hashlib.sha256(manifest).hexdigest(),
            "manifestCommand": command, "manifestCommandExitCode": 0,
        }
        require(session.sha256_file(args.apk) == record["apkSha256"]
                and session.sha256_file(pack) == record["packSha256"]
                and shipping.build_context(args.source_revision) == record["context"],
                "APK, pack or source context changed during preview preflight.")
        record["verified"] = True
    except Exception as error:
        record["error"] = session.ui.redacted(str(error))
        raise
    finally:
        write_json(output / "package-inputs.json", record)
    return output / "package-inputs.json"


def display_receipt(smoke):
    raw = (smoke.output / "display-density.log").read_text()
    values = re.findall(r"^(Physical|Override) density:\s*(\d+)\s*$", raw, re.M)
    require(values and len({label for label, _ in values}) == len(values),
            "Display density is absent or ambiguous.")
    densities = {label: int(value) for label, value in values}
    density = densities.get("Override", densities.get("Physical"))
    require(tuple(smoke.display_size) == smoke.expected_display_size
            and density == smoke.expected_density_dpi,
            "The actual emulator size/density differs from the required preview target.")
    require(smoke.adb("shell", "settings", "get", "system", "font_scale").strip() == "1.0",
            "The preview font scale changed.")
    return {"sizePx": list(smoke.display_size), "densityDpi": density, "fontScale": 1.0,
            "densitySource": "Original wm density output; each native capture also checks Activity configuration."}


class Preview3dSmoke(session.GodotSessionSmoke):
    def __init__(self, serial, output, display_size, density_dpi):
        super().__init__(serial, output, "debug", "1.0")
        self.expected_display_size = tuple(display_size)
        self.expected_density_dpi = density_dpi

    def prepare_device(self):
        require(self.adb("shell", "getprop", "ro.build.version.sdk").strip() == "36",
                "The preview 3D check requires API36.")
        super().prepare_device()

    def capture_evidence(self, name, component=None, renderer_pid=None, diagnostic=False, ui_assertion=None):
        entry = super().capture_evidence(name, component, renderer_pid, diagnostic, ui_assertion)
        if component != session.NATIVE_COMPONENT or diagnostic:
            return entry
        try:
            window = self.adb("shell", "dumpsys", "window", "displays")
            self.write_text(f"captures/{name}-display-window.log", window)
            records, resumed = session.platform_observation.activity_records(
                (self.output / "logs/last-activity.log").read_text())
            display = session.platform_observation.window_display(window)
            focus = session.platform_observation.attributed_focus(records, resumed, display)
            require(focus is not None and focus["component"] == session.NATIVE_COMPONENT,
                    "Native capture lost its focused Activity.")
            configuration = focus["configuration"]
            screenshot = entry["screenshot"]
            require(tuple(display["size"]) == self.expected_display_size and display["rotation"] == 0
                    and configuration["density_dpi"] == self.expected_density_dpi
                    and configuration["font_scale"] == 1.0
                    and (screenshot["width"], screenshot["height"]) == self.expected_display_size,
                    "Native capture does not prove the required portrait pixels/density/font scale.")
            entry["previewDisplay"] = {"sizePx": display["size"], "rotation": display["rotation"],
                                       "configuration": configuration, "verified": True}
        except Exception as error:
            entry.update(status="failed", error=session.ui.redacted(str(error)))
            raise
        finally:
            self.write_json(f"captures/{name}.json", entry)
        return entry


def completed_errors(smoke):
    errors = []
    if set(smoke.checks) != EXPECTED_CHECKS or any(check.get("status") != "passed" for check in smoke.checks.values()):
        errors.append("Every one of the seven required preview 3D checks must explicitly pass.")
    for name in REQUIRED_NATIVE_CAPTURES:
        matches = [capture for capture in smoke.captures if capture.get("name") == name]
        if (len(matches) != 1 or matches[0].get("status") != "captured"
                or matches[0].get("previewDisplay", {}).get("verified") is not True):
            errors.append("Missing successful native display capture: " + name)
    return errors


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                     allow_abbrev=False)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--output", type=Path, required=True, help="Fresh evidence directory; never overwritten.")
    parser.add_argument("--display-size", type=int, nargs=2, default=(1080, 2400), metavar=("WIDTH", "HEIGHT"))
    parser.add_argument("--density-dpi", type=int, default=420)
    args = parser.parse_args(argv)
    if not (320 <= args.display_size[0] <= 2160 and args.display_size[0] < args.display_size[1] <= 3840
            and 320 <= args.density_dpi <= 640):
        parser.error("Require bounded portrait display dimensions and a high-density target (320–640 dpi).")
    return args


def main(argv=None):
    args = arguments(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    package_output, runtime_output = args.output / "package", args.output / "runtime"
    package_output.mkdir()
    runtime_output.mkdir()
    smoke = Preview3dSmoke(args.serial, runtime_output, args.display_size, args.density_dpi)
    result = {"schemaVersion": 1, "passed": False, "status": "running", "startedUtc": session.utc_now(),
              "sourceRevision": args.source_revision, "apkSha256": None, "variant": "debug",
              "requestedModes": ["3d"], "qualificationObservationRequested": True,
              "scope": "Actual API36 preview APK: 3D picker, Reveal/select/single Play, Standard authority outcome and Leave.",
              "runtimeEvidenceRoot": "runtime", "checks": smoke.checks, "identity": smoke.identity,
              "captures": smoke.captures, "steps": smoke.steps, "observations": smoke.observations,
              "limits": ["Original native pixels require independent sharpness, table-clipping and privacy review.",
                         "No animation-quality, audible-sound, physical-phone, LAN or performance acceptance.",
                         "The accepted Play oracle is the existing action-specific Standard outcome; local counters alone never qualify Play."]}
    result_path = args.output / "smoke-result.json"
    write_json(result_path, result)  # A timeout must not leave an apparent successful result.
    device_started = False
    failed = True
    try:
        with smoke.check("package-inputs") as entry:
            receipt = record_package_inputs(args, package_output)
            smoke.engine_inputs = session.verify_engine_package_inputs(smoke, args.apk, receipt, args.source_revision)
            entry["inputs"] = smoke.engine_inputs
            result["package"] = smoke.engine_inputs
            result["apkSha256"] = smoke.engine_inputs["apk_sha256"]
            smoke.identity.update(input_apk=str(args.apk.resolve()), input_apk_sha256=result["apkSha256"],
                                  source_revision=args.source_revision,
                                  checker_sha256=session.sha256_file(Path(__file__)),
                                  session_helper_sha256=session.sha256_file(Path(session.__file__)),
                                  ui_helper_sha256=session.sha256_file(session.HELPER_PATH))
        device_started = True
        smoke.setup_session(args.apk)
        with smoke.check("display") as entry:
            result["display"] = display_receipt(smoke)
            entry.update(result["display"])
        smoke.run_engine_gameplay("3d")
        require(session.sha256_file(args.apk) == result["apkSha256"], "Preview APK changed during native execution.")
        failed = False
    except Exception as error:
        result.update(error=session.ui.redacted(str(error)), failedStage=smoke.stage)
        print("Preview 3D failed: " + session.ui.redacted(str(error)), file=sys.stderr)
    finally:
        errors = []
        if device_started:
            for label, operation in (("diagnostics", smoke.diagnostics), ("restore", smoke.restore_environment)):
                try:
                    errors.extend(label + ": " + message for message in operation())
                except Exception as error:
                    errors.append(label + ": " + session.ui.redacted(str(error)))
        errors.extend(completed_errors(smoke))
        if errors:
            failed = True
            result["diagnosticOrRestoreErrors"] = errors
        result.update(passed=not failed, status="failed" if failed else "passed", endedUtc=session.utc_now())
        write_json(result_path, result)
    return 1 if failed else 0


if __name__ == "__main__":
    def interrupted(signum, _frame):
        raise TimeoutError("Preview 3D interrupted by signal " + str(signum))

    signal.signal(signal.SIGTERM, interrupted)
    sys.exit(main())
