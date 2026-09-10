"""Host-only activation/parser gates; synthetic APK bytes are never installed."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile


SCRIPTS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("android_godot_activation", SCRIPTS / "android_godot_activation.py")
activation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(activation)


def manifest(profile="qualification", modes="2d,3d"):
    root = ET.Element("manifest", {"package": "dev.partydeck.app"})
    app = ET.SubElement(root, "application")
    for key, value in [(activation.PROFILE_KEY, profile), (activation.MODES_KEY, modes)]:
        ET.SubElement(app, "meta-data", {activation.ANDROID + "name": key, activation.ANDROID + "value": value})
    return root


def expectation(profile="qualification", modes="2d,3d"):
    return json.dumps({"schemaVersion": 1, "profile": profile, "modesCsv": modes}).encode()


class ActivationParsingTest(unittest.TestCase):
    def test_packaged_subset_and_shipping_empty_are_exact(self):
        for profile, modes in [("shipping", ""), ("qualification", "2d"), ("qualification", "3d"), ("qualification", "2d,3d")]:
            with self.subTest(profile=profile, modes=modes):
                self.assertEqual(activation.parse_build_expectation(expectation(profile, modes)),
                                 activation.parse_packaged_manifest(ET.tostring(manifest(profile, modes))))

    def test_invalid_profiles_types_and_lists_fail_closed(self):
        for profile, modes in [(None, "2d"), (True, "2d"), ("debug", "2d"), ("Qualification", "2d"),
                               ("qualification", None), ("qualification", []), ("qualification", ""),
                               *[("qualification", value) for value in [",", "2d,", ",3d", "2d,,3d", "2d,2d", "3d,2d", "2d,4d", "2D", " 2d", "2d, 3d"]]]:
            with self.subTest(profile=profile, modes=modes), self.assertRaises(ValueError):
                activation.activation_values(profile, modes)

    def test_build_expectation_rejects_ambiguous_or_wrong_schema(self):
        for raw in [b'{', b'[]', b'{}', b'{"schemaVersion":true,"profile":"qualification","modesCsv":"2d"}',
                    b'{"schemaVersion":1,"profile":"shipping","profile":"qualification","modesCsv":"2d"}',
                    b'{"schemaVersion":1,"profile":"qualification","modesCsv":"2d","extra":true}']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                activation.parse_build_expectation(raw)

    def test_packaged_metadata_requires_single_literal_application_values(self):
        roots = []
        missing = manifest(); missing.find("application").remove(missing.find("application/meta-data")); roots.append(missing)
        duplicate = manifest(); duplicate.find("application").append(duplicate.find("application/meta-data")); roots.append(duplicate)
        resource = manifest(); resource.find("application/meta-data").set(activation.ANDROID + "resource", "@string/profile"); roots.append(resource)
        absent_value = manifest(); del absent_value.find("application/meta-data").attrib[activation.ANDROID + "value"]; roots.append(absent_value)
        wrong_package = manifest(); wrong_package.set("package", "dev.example.fake"); roots.append(wrong_package)
        two_apps = manifest(); two_apps.append(two_apps.find("application")); roots.append(two_apps)
        nested = manifest(); app = nested.find("application"); item = app.find("meta-data"); app.remove(item); ET.SubElement(app, "activity").append(item); roots.append(nested)
        for root in roots:
            with self.subTest(xml=ET.tostring(root)), self.assertRaises(ValueError):
                activation.parse_packaged_manifest(ET.tostring(root))

    def test_expected_and_packaged_values_must_match_the_requested_qualification(self):
        both = activation.activation_values("qualification", "2d,3d")
        shipping = activation.activation_values("shipping", "")
        one = activation.activation_values("qualification", "2d")
        activation.require_qualification_match(both, both, "2d,3d")
        for expected, packaged in [(shipping, shipping), (both, shipping), (both, one), (one, both)]:
            with self.subTest(expected=expected, packaged=packaged), self.assertRaises(ValueError):
                activation.require_qualification_match(expected, packaged, "2d,3d")


class ActivationWrapperTest(unittest.TestCase):
    def run_wrapper(self, profile, modes, *, analyzer_exit=0):
        with tempfile.TemporaryDirectory(prefix="partydeck-activation-host-") as temporary:
            root = Path(temporary)
            (root / "scripts").mkdir()
            (root / "scripts/android_godot_activation.py").write_bytes((SCRIPTS / "android_godot_activation.py").read_bytes())
            # This host-only stub records invocation; it cannot launch an app or a renderer.
            (root / "scripts/smoke-android-godot-session.py").write_text(
                "from pathlib import Path\nPath('checker-invoked').write_text('synthetic host gate check\\n')\n")
            pack = root / "godot/qualification/build/renderer/partydeck-last-light.pck"
            pack.parent.mkdir(parents=True); pack.write_bytes(b"synthetic host pack bytes, not a PCK")
            apk = root / "synthetic-input.apk"
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("assets/partydeck-last-light.pck", pack.read_bytes())
            expected = root / "build/ci/android/godot-activation-build.json"
            expected.parent.mkdir(parents=True); expected.write_bytes(expectation())
            tool = root / "sdk/cmdline-tools/latest/bin/apkanalyzer"
            tool.parent.mkdir(parents=True)
            raw = ET.tostring(manifest(profile, modes))
            tool.write_text("#!/usr/bin/env python3\nimport sys\nsys.stdout.buffer.write(" + repr(raw) + ")\nsys.exit(" + str(analyzer_exit) + ")\n")
            tool.chmod(0o700)
            source = (SCRIPTS / "smoke-android-emulator.sh").read_text()
            start = source.index("run_godot_session_smoke() {\n")
            end = source.index("\n}\n\nPARTYDECK_DEBUG_STATUS=", start) + 3
            script = root / "wrapper.sh"
            script.write_text("set -euo pipefail\nPARTYDECK_SOURCE_REVISION=" + "a" * 40 +
                              "\nPARTYDECK_EMULATOR_SERIAL=synthetic-host-only\n" + source[start:end] +
                              "\nrun_godot_session_smoke debug synthetic-input.apk evidence\n")
            environment = dict(os.environ, ANDROID_HOME=str(root / "sdk"), PYTHONDONTWRITEBYTECODE="1")
            process = subprocess.run(["bash", str(script)], cwd=root, env=environment, capture_output=True, timeout=20)
            receipt = json.loads((root / "evidence/package-inputs.json").read_text())
            return process.returncode, (root / "checker-invoked").exists(), receipt, hashlib.sha256(apk.read_bytes()).hexdigest()

    def test_matching_apk_metadata_reaches_the_unchanged_checker_with_hashes(self):
        status, invoked, receipt, apk_hash = self.run_wrapper("qualification", "2d,3d")
        self.assertEqual(0, status)
        self.assertTrue(invoked)
        self.assertTrue(receipt["verified"])
        self.assertTrue(receipt["activation"]["verified"])
        self.assertEqual(apk_hash, receipt["apkSha256"])
        self.assertEqual(receipt["packSha256"], receipt["embeddedPackSha256"])
        self.assertEqual("a" * 40, receipt["sourceRevision"])
        self.assertEqual("2d,3d", receipt["activation"]["packaged"]["modesCsv"])

    def test_shipping_or_wrong_subset_stops_before_checker_invocation(self):
        for profile, modes in [("shipping", ""), ("qualification", "2d")]:
            with self.subTest(profile=profile, modes=modes):
                status, invoked, receipt, _ = self.run_wrapper(profile, modes)
                self.assertNotEqual(0, status)
                self.assertFalse(invoked)
                self.assertFalse(receipt["verified"])
                self.assertFalse(receipt["activation"]["verified"])
                self.assertEqual(profile, receipt["activation"]["packaged"]["profile"])
                self.assertIn("error", receipt)

    def test_failed_manifest_extraction_stops_before_checker_invocation(self):
        status, invoked, receipt, _ = self.run_wrapper("qualification", "2d,3d", analyzer_exit=7)
        self.assertNotEqual(0, status)
        self.assertFalse(invoked)
        self.assertFalse(receipt["verified"])
        self.assertEqual(7, receipt["activation"]["manifestCommandExitCode"])


class BuildOptInScriptTest(unittest.TestCase):
    def invoke(self, flag):
        with tempfile.TemporaryDirectory(prefix="partydeck-build-opt-in-host-") as temporary:
            root = Path(temporary)
            (root / "scripts").mkdir()
            script = root / "scripts/validate-android.sh"
            script.write_bytes((SCRIPTS / "validate-android.sh").read_bytes())
            (root / "scripts/prepare-godot-renderer.sh").write_text("printf 'host-only stub' > preparation-invoked\n")
            # Record arguments only. This file never invokes Gradle or builds source.
            wrapper = root / "gradlew"
            wrapper.write_text("#!/usr/bin/env python3\nimport json, sys\nfrom pathlib import Path\nPath('arguments.json').write_text(json.dumps(sys.argv[1:]))\n")
            wrapper.chmod(0o700)
            environment = dict(os.environ)
            environment.pop("PARTYDECK_ANDROID_GODOT_SESSION_SMOKE", None)
            if flag is not None:
                environment["PARTYDECK_ANDROID_GODOT_SESSION_SMOKE"] = flag
            process = subprocess.run(["bash", str(script)], cwd=root, env=environment, capture_output=True, timeout=10)
            arguments = json.loads((root / "arguments.json").read_text()) if (root / "arguments.json").exists() else None
            return process.returncode, arguments, (root / "preparation-invoked").exists()

    def test_only_explicit_session_input_adds_build_property_for_both_variants(self):
        for flag in (None, "0", "1"):
            with self.subTest(flag=flag):
                status, arguments, prepared = self.invoke(flag)
                self.assertEqual(0, status)
                self.assertTrue(prepared)
                self.assertEqual(["-PpartydeckGodotQualificationModes=2d,3d"] if flag == "1" else [],
                                 [value for value in arguments if value.startswith("-PpartydeckGodotQualificationModes")])
                for task in (":androidApp:recordGodotPresentationActivation", ":androidApp:assembleDebug", ":androidApp:assembleRelease", ":androidApp:bundleRelease"):
                    self.assertIn(task, arguments)

    def test_invalid_session_input_stops_before_build_preparation(self):
        status, arguments, prepared = self.invoke("true")
        self.assertNotEqual(0, status)
        self.assertIsNone(arguments)
        self.assertFalse(prepared)


if __name__ == "__main__":
    unittest.main()
