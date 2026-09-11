"""Host-only shipping gates; synthetic package/status fixtures never run adb."""

import argparse
from contextlib import redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "smoke-android-godot-shipping.py"
SPEC = importlib.util.spec_from_file_location("shipping_gate_test_subject", SCRIPT)
shipping = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shipping)
ANDROID = shipping.activation.ANDROID
CONTEXT = {"sourceRevision": "a" * 40, "attribution": "Build-step receipt; not an embedded APK attestation.",
           "runId": "123", "runAttempt": "1", "repository": "example/PartyDeck"}
CERTIFICATE = "b" * 64


def manifest(profile="shipping", modes="2d,3d", debuggable="true"):
    root = ET.Element("manifest", {"package": "dev.partydeck.app"})
    app = ET.SubElement(root, "application", {ANDROID + "debuggable": debuggable})
    for key, value in ((shipping.activation.PROFILE_KEY, profile), (shipping.activation.MODES_KEY, modes)):
        ET.SubElement(app, "meta-data", {ANDROID + "name": key, ANDROID + "value": value})
    ET.SubElement(app, "activity", {ANDROID + "name": "dev.partydeck.app.godot.SessionGodotActivity",
                                    ANDROID + "exported": "false", ANDROID + "process": ":godot"})
    ET.SubElement(app, "service", {ANDROID + "name": "dev.partydeck.app.godot.GodotSessionBrokerService",
                                   ANDROID + "exported": "false"})
    return root


class InputsFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="partydeck-shipping-host-only-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.pack = self.root / "renderer.pck"
        self.pack.write_bytes(b"synthetic host-only bytes; not an executable renderer")
        self.pack.with_suffix(".receipt.json").write_text('{"syntheticHostOnly":true}\n')
        self.apk = self.root / "synthetic-input.apk"
        with zipfile.ZipFile(self.apk, "w") as archive:
            archive.writestr("assets/partydeck-last-light.pck", self.pack.read_bytes())
        self.expected = self.root / "build.json"
        self.expected.write_text('{"schemaVersion":1,"profile":"shipping","modesCsv":"2d,3d"}\n')
        self.sdk = self.root / "sdk"
        self.sdk.mkdir()
        self.environment = mock.patch.dict(shipping.os.environ, {"ANDROID_HOME": str(self.sdk)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.context = mock.patch.object(shipping, "build_context", return_value=CONTEXT)
        self.context.start()
        self.addCleanup(self.context.stop)
        self.args = argparse.Namespace(apk=self.apk, variant="debug", source_revision="a" * 40,
                                       build_expectation=self.expected, renderer_pack=self.pack,
                                       signing_receipt=None, unsigned_apk=None, inputs=self.root / "inputs.json")
        self.record_inputs()

    def record_inputs(self):
        self.record = shipping.input_record(self.args)
        self.args.inputs.write_text(json.dumps(self.record))

    def run_arguments(self):
        return ["run", "--apk", str(self.apk), "--variant", "debug", "--source-revision", "a" * 40,
                "--build-expectation", str(self.expected), "--renderer-pack", str(self.pack),
                "--inputs", str(self.args.inputs), "--serial", "synthetic-no-adb-device",
                "--output", str(self.root / "runtime-result")]

    def verify(self, *, xml=None, certificate=CERTIFICATE):
        output = self.root / "package-output"
        output.mkdir()
        calls = []

        def host_tool(argv, output, name, timeout=60):
            calls.append(name)
            if name == "packaged-manifest":
                return ET.tostring(xml if xml is not None else manifest(debuggable="false" if self.args.variant == "optimized-test-signed" else "true"))
            if name == "signature":
                return ("Signer #1 certificate SHA-256 digest: " + certificate + "\n").encode()
            return b"host-only stand-in; no SDK or renderer execution\n"

        with mock.patch.object(shipping, "checked_command", side_effect=host_tool):
            result = shipping.verify_inputs(self.args, output)
        return result, calls


class ShippingPackageGateTest(InputsFixture):
    def test_matching_shipping_gate_records_actual_debuggable_and_test_signing_scope(self):
        result, calls = self.verify()
        self.assertTrue(result["verified"])
        self.assertEqual(["source-pack-check", "packaged-manifest", "signature", "alignment"], calls)
        self.assertTrue(result["packaged"]["debuggable"])
        self.assertEqual("shipping", result["packaged"]["activation"]["profile"])
        self.assertEqual("debuggable-test-package", result["signingCategory"])
        self.assertFalse(result["publisherSigningQualified"])
        self.assertEqual(self.record["files"]["rendererPack"]["sha256"], result["embeddedPackSha256"])

    def test_changed_apk_or_source_run_is_rejected_before_sdk_or_device_tools(self):
        for key in ("apk", "run"):
            with self.subTest(change=key):
                changed = json.loads(json.dumps(self.record))
                if key == "apk":
                    changed["files"]["apk"]["sha256"] = "0" * 64
                else:
                    changed["context"]["runId"] = "456"
                self.args.inputs.write_text(json.dumps(changed))
                with mock.patch.object(shipping, "checked_command") as command:
                    with self.assertRaises(shipping.session.CheckFailure):
                        shipping.verify_inputs(self.args, self.root)
                    command.assert_not_called()

    def test_actual_qualification_apk_cannot_pass_a_shipping_build_expectation(self):
        with self.assertRaises(shipping.session.CheckFailure):
            self.verify(xml=manifest(profile="qualification"))

    def test_signed_apk_must_embed_the_exact_bound_pack(self):
        with zipfile.ZipFile(self.apk, "w") as archive:
            archive.writestr("assets/partydeck-last-light.pck", b"different synthetic pack")
        self.record_inputs()
        with self.assertRaises(shipping.session.CheckFailure):
            self.verify()

    def test_optimized_receipt_must_match_fresh_certificate_and_unsigned_input(self):
        unsigned = self.root / "unsigned.apk"
        unsigned.write_bytes(b"synthetic unsigned input")
        signing = self.root / "signing.json"
        self.args.variant = "optimized-test-signed"
        self.args.unsigned_apk = unsigned
        self.args.signing_receipt = signing
        signing.write_text(json.dumps({"variant": "optimized-test-signed", "signingIdentity": "disposable-ci-test-key",
                                       "distributionSigned": False, "alignmentKiB": 16, "certificateSha256": "c" * 64,
                                       "runtimeApkSha256": shipping.session.sha256_file(self.apk),
                                       "originalUnsignedSha256": shipping.session.sha256_file(unsigned)}))
        self.record_inputs()
        with self.assertRaises(shipping.session.CheckFailure):
            self.verify(certificate=CERTIFICATE)

    def test_failed_package_gate_cannot_construct_a_native_driver(self):
        self.args.inputs.write_text('{}')
        with mock.patch.object(shipping, "ShippingSmoke") as native, redirect_stderr(io.StringIO()):
            status = shipping.main(self.run_arguments())
        self.assertEqual(1, status)
        native.assert_not_called()
        result = json.loads((self.root / "runtime-result/shipping-activation-result.json").read_text())
        self.assertEqual("failed", result["status"])
        self.assertNotIn("identity", result)

class ManifestAndObservationTest(unittest.TestCase):
    def test_subset_empty_and_exposed_components_are_rejected(self):
        samples = [manifest(modes=""), manifest(modes="2d"), manifest(debuggable="false")]
        for tag, key, value in (("activity", "exported", "true"), ("activity", "process", "dev.partydeck.app"),
                                ("service", "exported", "true"), ("service", "process", ":godot")):
            altered = manifest()
            altered.find("application/" + tag).set(ANDROID + key, value)
            samples.append(altered)
        for root in samples:
            with self.subTest(xml=ET.tostring(root)), self.assertRaises(shipping.session.CheckFailure):
                shipping.packaged_boundary(ET.tostring(root), "debug")

    def test_observer_node_is_rejected_without_reading_or_requesting_its_document(self):
        root = ET.fromstring('<hierarchy><node resource-id="" text="Table ready."/></hierarchy>')
        shipping.reject_observer(root)
        for value in ("godot_qualification_observation", "dev.partydeck.app:id/godot_qualification_observation"):
            root[0].set("resource-id", value)
            with self.assertRaises(shipping.session.CheckFailure):
                shipping.reject_observer(root)

    def test_engine_gameplay_and_mode_subset_have_no_shipping_cli_option(self):
        base = ["run", "--apk", "a", "--variant", "debug", "--source-revision", "a" * 40,
                "--build-expectation", "b", "--renderer-pack", "c", "--inputs", "d", "--serial", "e", "--output", "f"]
        for extra in (["--engine-gameplay"], ["--engine-package-inputs", "receipt"], ["--modes", "2d"], ["--engine"]):
            with self.subTest(extra=extra), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
                shipping.parser().parse_args(base + extra)
            self.assertEqual(2, failure.exception.code)


class SourceContextTest(unittest.TestCase):
    def test_exact_clean_head_and_complete_ci_context_are_bound(self):
        replies = [mock.Mock(stdout=("a" * 40 + "\n").encode(), returncode=0),
                   mock.Mock(stdout=b"", returncode=0)]
        environment = {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
                       "GITHUB_REPOSITORY": "example/PartyDeck"}
        with mock.patch.object(shipping.subprocess, "run", side_effect=replies), \
                mock.patch.dict(shipping.os.environ, environment, clear=True):
            self.assertEqual(CONTEXT, shipping.build_context("a" * 40))

    def test_untracked_source_or_partial_ci_context_cannot_be_recorded(self):
        for dirty, environment in ((b"?? core/src/untracked.kt\n", {}), (b"", {"GITHUB_SHA": "a" * 40})):
            replies = [mock.Mock(stdout=("a" * 40 + "\n").encode(), returncode=0),
                       mock.Mock(stdout=dirty, returncode=0)]
            with self.subTest(dirty=bool(dirty), partial_ci=bool(environment)), \
                    mock.patch.object(shipping.subprocess, "run", side_effect=replies), \
                    mock.patch.dict(shipping.os.environ, environment, clear=True), \
                    self.assertRaises(shipping.session.CheckFailure):
                shipping.build_context("a" * 40)


class CompletionGateTest(InputsFixture):
    # The stand-in below can only exercise report accounting. It has no adb/SDK
    # implementation and never produces a native qualification artifact.
    def run_status(self, required_status="passed", diagnostics=None, restore=None):
        seen = []
        class AccountingOnly:
            def __init__(self, serial, output, variant, scale):
                self.identity, self.checks, self.observations = {}, {}, {}
                self.steps, self.captures = [], []
                self.stage = "synthetic-accounting"
            def setup_session(self, apk): self.checks["installation"] = {"status": "passed"}
            def run_shipping_mode(self, mode):
                seen.append(mode)
                for suffix in ("practice-baseline", "native-entry", "standard-return", "reentry-leave"):
                    if required_status != "missing" or (mode, suffix) != ("3d", "native-entry"):
                        self.checks[f"{mode}.{suffix}"] = {"status": required_status if (mode, suffix) == ("3d", "native-entry") else "passed"}
            def diagnostics(self): return diagnostics or []
            def restore_environment(self): return restore or []
        package = {"verified": True, "inputs": self.record}
        arguments = self.run_arguments()
        output = self.root / ("runtime-result-" + str(len(list(self.root.iterdir()))))
        arguments[-1] = str(output)
        with mock.patch.object(shipping, "verify_inputs", return_value=package), \
                mock.patch.object(shipping, "ShippingSmoke", AccountingOnly):
            status = shipping.main(arguments)
        result = json.loads((output / "shipping-activation-result.json").read_text())
        self.assertEqual(["2d", "3d"], seen)
        return status, result

    def test_both_modes_with_every_check_are_required_for_completion(self):
        status, result = self.run_status()
        self.assertEqual(0, status)
        self.assertTrue(result["passed"])
        self.assertFalse(result["engineGameplayRequested"] or result["qualificationObservationRequested"])

    def test_any_nonpass_required_check_prevents_success(self):
        for required_status in ("running", "failed", "skipped", "unsupported"):
            with self.subTest(required_status=required_status):
                status, result = self.run_status(required_status)
                self.assertEqual(1, status)
                self.assertFalse(result["passed"])

    def test_missing_required_entry_cannot_be_reported_as_passed(self):
        status, result = self.run_status("missing")
        self.assertEqual(1, status)
        self.assertFalse(result["passed"])

    def test_cleanup_failure_fails_the_completed_route(self):
        status, result = self.run_status(restore=["synthetic settings restore failure"])
        self.assertEqual(1, status)
        self.assertIn("synthetic settings restore failure", result["diagnosticOrRestoreErrors"])

    def test_diagnostic_failure_fails_the_completed_route(self):
        status, result = self.run_status(diagnostics=["synthetic crash evidence"])
        self.assertEqual(1, status)
        self.assertFalse(result["passed"])

    def test_failed_native_entry_never_reaches_standard_return(self):
        native_output = self.root / "driver-flow"
        native_output.mkdir()
        native = shipping.ShippingSmoke("synthetic-no-adb-device", native_output)
        with mock.patch.object(native, "tap_action") as tap, \
                mock.patch.object(native, "wait_for_human_turn"), \
                mock.patch.object(native, "assert_concealed"), \
                mock.patch.object(native, "observe_match", return_value={"synthetic": True}), \
                mock.patch.object(native, "select_first_card"), \
                mock.patch.object(native, "enter_native", side_effect=shipping.session.CheckFailure("No native Ready")), \
                mock.patch.object(native, "require_concealed_return") as standard:
            with self.assertRaises(shipping.session.CheckFailure):
                native.run_shipping_mode("2d")
            standard.assert_not_called()
            self.assertEqual([mock.call("home-practice")], tap.call_args_list)
            self.assertEqual("failed", native.checks["2d.native-entry"]["status"])


if __name__ == "__main__":
    unittest.main()
