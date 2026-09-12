"""Focused host regressions for the native preview gate; no device qualification."""

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile


SPEC = importlib.util.spec_from_file_location(
    "partydeck_preview_3d", Path(__file__).resolve().parents[1] / "smoke-android-preview-3d.py")
preview = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preview)

REVISION = "a" * 40
MANIFEST = b'''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="dev.partydeck.app">
<application android:debuggable="true">
<meta-data android:name="dev.partydeck.GODOT_ACTIVATION_PROFILE" android:value="qualification"/>
<meta-data android:name="dev.partydeck.GODOT_PRESENTATION_MODES" android:value="2d,3d"/>
</application></manifest>'''


class Replay(preview.Preview3dSmoke):
    """Only exercise coordinator failure handling; never a substitute for runtime evidence."""

    diagnostic_errors = []
    restore_errors = []
    setup_calls = 0
    requested_modes = []

    def setup_session(self, apk):
        type(self).setup_calls += 1
        with self.check("installation"):
            self.display_size = (1080, 2400)
            self.write_text("display-density.log", "Physical density: 420\n")

    def adb(self, *args, **kwargs):
        if args == ("shell", "settings", "get", "system", "font_scale"):
            return "1.0\n"
        raise AssertionError("Host regression unexpectedly attempted adb: " + str(args))

    def run_engine_gameplay(self, mode):
        type(self).requested_modes.append(mode)
        for name in sorted(preview.EXPECTED_CHECKS - {"package-inputs", "installation", "display"}):
            with self.check(name):
                pass
        self.captures.extend({"name": name, "status": "captured", "previewDisplay": {"verified": True}}
                             for name in preview.REQUIRED_NATIVE_CAPTURES)

    def diagnostics(self):
        return self.diagnostic_errors.copy()

    def restore_environment(self):
        return self.restore_errors.copy()


class PreviewGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="preview-3d-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.apk = self.root / "preview.apk"
        self.apk.write_bytes(b"host-only APK input")
        self.apk_sha = hashlib.sha256(self.apk.read_bytes()).hexdigest()
        Replay.setup_calls = 0
        Replay.requested_modes = []
        Replay.diagnostic_errors = []
        Replay.restore_errors = []

    def args(self, name="run"):
        return ["--serial", "host-only", "--apk", str(self.apk), "--source-revision", REVISION,
                "--output", str(self.root / name)]

    def complete_smoke(self):
        output = self.root / "runtime"
        output.mkdir()
        smoke = preview.Preview3dSmoke("host-only", output, (1080, 2400), 420)
        smoke.checks.update({name: {"status": "passed"} for name in preview.EXPECTED_CHECKS})
        smoke.captures.extend({"name": name, "status": "captured", "previewDisplay": {"verified": True}}
                             for name in preview.REQUIRED_NATIVE_CAPTURES)
        return smoke

    def test_nonpass_missing_extra_checks_and_unverified_native_pixels_fail(self):
        smoke = self.complete_smoke()
        self.assertEqual([], preview.completed_errors(smoke))
        for status in ("failed", "unsupported", "running", "skipped", "unknown", None):
            with self.subTest(status=status):
                smoke.checks["3d.engine-reveal-selection"]["status"] = status
                self.assertTrue(preview.completed_errors(smoke))
        smoke.checks["3d.engine-reveal-selection"]["status"] = "passed"
        prior = smoke.checks.pop("3d.engine-leave-end")
        self.assertTrue(preview.completed_errors(smoke))
        smoke.checks["3d.engine-leave-end"] = prior
        smoke.checks["2d.unrequested"] = {"status": "passed"}
        self.assertTrue(preview.completed_errors(smoke))
        del smoke.checks["2d.unrequested"]
        smoke.captures[0]["previewDisplay"]["verified"] = False
        self.assertTrue(preview.completed_errors(smoke))

    def test_required_entry_capture_matches_the_real_session_helper_name(self):
        smoke = self.complete_smoke()
        smoke.shell_identity = {"pid": 601, "uid": 10234, "name": preview.session.PACKAGE}
        native_state = {
            "renderer_pids": [602],
            "processes": [{"pid": 602, "uid": 10234, "name": preview.session.RENDERER_PROCESS}],
            "foreground": {"component": preview.session.NATIVE_COMPONENT, "task_id": 19},
        }
        # Execute the actual inherited enter_native body. Device interactions are
        # isolated, but the producer's capture-name construction is never mocked.
        with ExitStack() as stack:
            for name, value in (("wait_activity", native_state), ("state", native_state),
                                ("tap_action", None), ("wait_until", object()),
                                ("wait_for_presentation_choice", object()), ("tap_node", None),
                                ("require_shell", None)):
                stack.enter_context(patch.object(smoke, name, return_value=value))
            capture = stack.enter_context(patch.object(smoke, "capture_evidence"))
            smoke.enter_native("3d", "3d-engine-entry")
        actual_native_names = {call.args[0] for call in capture.call_args_list
                               if call.args[1] == preview.session.NATIVE_COMPONENT}
        self.assertEqual(preview.REQUIRED_NATIVE_CAPTURES - {"3d-engine-selected"}, actual_native_names)

    def test_actual_density_override_and_size_must_match(self):
        smoke = self.complete_smoke()
        smoke.display_size = (1080, 2400)
        path = smoke.output / "display-density.log"
        with patch.object(smoke, "adb", return_value="1.0\n"):
            path.write_text("Physical density: 420\n")
            self.assertEqual(420, preview.display_receipt(smoke)["densityDpi"])
            for raw in ("Physical density: 420\nOverride density: 280\n", "Physical density: 420\nPhysical density: 420\n", ""):
                with self.subTest(raw=raw), self.assertRaises(preview.session.CheckFailure):
                    path.write_text(raw)
                    preview.display_receipt(smoke)
            path.write_text("Physical density: 420\n")
            smoke.display_size = (720, 1600)
            with self.assertRaises(preview.session.CheckFailure):
                preview.display_receipt(smoke)

    def test_native_capture_checks_activity_density_and_original_png_dimensions(self):
        smoke = self.complete_smoke()
        (smoke.output / "logs/last-activity.log").write_text("host-only Activity fixture")
        baseline = {"status": "captured", "screenshot": {"width": 1080, "height": 2400}}
        focus = {"component": preview.session.NATIVE_COMPONENT,
                 "configuration": {"density_dpi": 420, "font_scale": 1.0}}
        cases = (("matched", 420, 1080, 0), ("density", 280, 1080, 0),
                 ("pixels", 420, 720, 0), ("rotation", 420, 1080, 1))
        for name, density, width, rotation in cases:
            entry = copy.deepcopy(baseline)
            entry["screenshot"]["width"] = width
            owner = copy.deepcopy(focus)
            owner["configuration"]["density_dpi"] = density
            with patch.object(preview.session.GodotSessionSmoke, "capture_evidence", return_value=entry), \
                    patch.object(smoke, "adb", return_value="host-only window fixture"), \
                    patch.object(preview.session.platform_observation, "activity_records", return_value=([], [])), \
                    patch.object(preview.session.platform_observation, "window_display", return_value={"size": [1080, 2400], "rotation": rotation}), \
                    patch.object(preview.session.platform_observation, "attributed_focus", return_value=owner):
                if name == "matched":
                    result = smoke.capture_evidence(name, preview.session.NATIVE_COMPONENT, 602)
                    self.assertIs(result["previewDisplay"]["verified"], True)
                else:
                    with self.assertRaises(preview.session.CheckFailure):
                        smoke.capture_evidence(name, preview.session.NATIVE_COMPONENT, 602)
                    saved = json.loads((smoke.output / f"captures/{name}.json").read_text())
                    self.assertEqual("failed", saved["status"])
                    self.assertIn("error", saved)

    def run_replay(self, name="run", preflight_error=None):
        receipt = self.root / "package-inputs.json"
        engine = {"verified": True, "apk_sha256": self.apk_sha,
                  "packaged_activation": {"profile": "qualification", "modes": ["2d", "3d"]}}
        with patch.object(preview, "Preview3dSmoke", Replay), \
                patch.object(preview, "record_package_inputs", return_value=receipt, side_effect=preflight_error), \
                patch.object(preview.session, "verify_engine_package_inputs", return_value=engine), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = preview.main(self.args(name))
        return code, json.loads((self.root / name / "smoke-result.json").read_text())

    def test_package_failure_prevents_any_device_operation(self):
        code, report = self.run_replay(preflight_error=ValueError("wrong APK/source"))
        self.assertEqual(1, code)
        self.assertIs(report["passed"], False)
        self.assertEqual("failed", report["checks"]["package-inputs"]["status"])
        self.assertEqual(0, Replay.setup_calls)
        self.assertEqual([], Replay.requested_modes)

    def test_one_3d_route_and_both_cleanup_failures_remain_fatal(self):
        code, report = self.run_replay("complete")
        self.assertEqual(0, code)
        self.assertEqual(["3d"], Replay.requested_modes)
        self.assertEqual(self.apk_sha, report["apkSha256"])
        self.assertEqual(REVISION, report["sourceRevision"])
        for kind in ("diagnostic_errors", "restore_errors"):
            setattr(Replay, kind, ["host-injected cleanup failure"])
            code, report = self.run_replay(kind)
            self.assertEqual(1, code)
            self.assertIs(report["passed"], False)
            self.assertTrue(report["diagnosticOrRestoreErrors"])
            setattr(Replay, kind, [])

    def package_fixture(self):
        pack = self.root / "godot/qualification/build/renderer/partydeck-last-light.pck"
        pack.parent.mkdir(parents=True)
        pack.write_bytes(b"host-only pack")
        pack.with_suffix(".receipt.json").write_text('{"hostOnly": true}\n')
        expectation = self.root / "build/ci/android/godot-activation-build.json"
        expectation.parent.mkdir(parents=True)
        expectation.write_text('{"schemaVersion":1,"profile":"qualification","modesCsv":"2d,3d"}')
        with zipfile.ZipFile(self.apk, "w") as archive:
            archive.writestr("assets/partydeck-last-light.pck", pack.read_bytes())
        return preview.arguments(self.args())

    def test_receipt_uses_actual_manifest_and_exact_embedded_pack(self):
        args = self.package_fixture()
        context = {"sourceRevision": REVISION, "runId": "123", "runAttempt": "1"}
        for name, manifest in (("qualification", MANIFEST),
                               ("shipping", MANIFEST.replace(b'android:value="qualification"', b'android:value="shipping"')),
                               ("nondebug", MANIFEST.replace(b'android:debuggable="true"', b'android:debuggable="false"'))):
            output = self.root / name
            output.mkdir()
            with patch.object(preview, "ROOT", self.root), patch.object(preview.shipping, "build_context", return_value=context), \
                    patch.dict(preview.os.environ, {"ANDROID_HOME": "/host-only-sdk"}), \
                    patch.object(preview.shipping, "checked_command", side_effect=[b"host-only source check", manifest]):
                if name == "qualification":
                    receipt = preview.record_package_inputs(args, output)
                    value = json.loads(receipt.read_text())
                    self.assertIs(value["verified"], True)
                    self.assertEqual(value["embeddedPackSha256"], value["packSha256"])
                    self.assertEqual(hashlib.sha256(manifest).hexdigest(), value["activation"]["manifestSha256"])
                    runtime = self.root / "compatibility-runtime"
                    runtime.mkdir()
                    smoke = preview.Preview3dSmoke("host-only", runtime, (1080, 2400), 420)
                    with patch.object(preview.session.subprocess, "run", return_value=subprocess.CompletedProcess(
                            ["host-only-manifest"], 0, MANIFEST, b"")):
                        admission = preview.session.verify_engine_package_inputs(smoke, self.apk, receipt, REVISION)
                    self.assertIs(admission["verified"], True)
                    self.assertEqual(value["apkSha256"], admission["apk_sha256"])
                else:
                    with self.assertRaises((ValueError, preview.session.CheckFailure)):
                        preview.record_package_inputs(args, output)
                    self.assertIs(json.loads((output / "package-inputs.json").read_text())["verified"], False)
        with zipfile.ZipFile(self.apk, "w") as archive:
            archive.writestr("assets/partydeck-last-light.pck", b"different pack")
        output = self.root / "changed-pack"
        output.mkdir()
        with patch.object(preview, "ROOT", self.root), patch.object(preview.shipping, "build_context", return_value=context), \
                patch.object(preview.shipping, "checked_command", return_value=b"host-only source check") as command:
            with self.assertRaises(preview.session.CheckFailure):
                preview.record_package_inputs(args, output)
            self.assertEqual(1, command.call_count, "Mismatched PCK must fail before Android SDK/device tools.")

    def test_fresh_output_is_required(self):
        destination = self.root / "existing"
        destination.mkdir()
        sentinel = destination / "prior-evidence"
        sentinel.write_text("preserve")
        with self.assertRaises(FileExistsError):
            preview.main(self.args("existing"))
        self.assertEqual("preserve", sentinel.read_text())


if __name__ == "__main__":
    unittest.main()
