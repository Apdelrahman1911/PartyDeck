"""Host-only continuous-input contract tests; no fixture qualifies Android or Godot."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import android_continuous_touch as touch
import android_godot_adaptive_inputs as inputs
import smoke_android_godot_public_context as focused
import test_android_godot_public_context as fixtures

engine = touch.engine


def observation(*, requested=100.0, received=100.0):
    value = engine.parse(json.dumps(fixtures.snapshot()), "3d", [1600, 720])
    return {"value": value, "requested_host_time": requested, touch.HOST_RECEIPT_TIME: received,
            "receipt": {"host_only": True}}


def arguments(now=100.0, deadline=820.0):
    sample = observation()
    return touch.request_arguments(sample, focused.body_swipe(sample["value"]), deadline, now, "a" * 32)


def wire(args):
    vector = ["shell", "am", "instrument", "-w", "-r", "--no-test-api-access", "--always-check-signature"]
    for key, value in args.items():
        vector.extend(("-e", key, str(value)))
    return tuple(vector + [touch.COMPONENT])


def receipt_text(value):
    return touch.RESULT_PREFIX + json.dumps(value) + "\nINSTRUMENTATION_CODE: -1\n"


class Transport:
    def __init__(self, *, reply=None, error=None, completed=None):
        self.calls, self.command_calls, self.captures = [], [], []
        self.input_incomplete, self.identity = False, {}
        self.reply, self.error, self.completed = reply, error, completed

    def adb(self, *argv, **kwargs):
        self.calls.append((argv, kwargs))
        if self.error is not None:
            raise self.error
        output = fixtures.continuous_output(argv, 1051) if argv[:3] == ("shell", "am", "instrument") else "Success"
        if self.reply is not None:
            output = self.reply(output)
        if self.completed is not None:
            self.completed()
        return output

    def command(self, *argv, **kwargs):
        self.command_calls.append((argv, kwargs))
        if self.completed is not None:
            self.completed()
        return "host-only completion"

    def capture_evidence(self, *args, **kwargs):
        self.captures.append({"host_only": True})
        if self.completed is not None:
            self.completed()
        return self.captures[-1]


class Smoke(focused.PublicContextScenarios, Transport):
    pass


class RequestTests(unittest.TestCase):
    def test_real_numeric_native_times_are_accepted_without_counter_conversion(self):
        sample = observation()
        args, timeout = touch.request_arguments(sample, focused.body_swipe(sample["value"]), 820, 100, "a" * 32)
        self.assertEqual(10050, args["start_deadline"])
        self.assertEqual(11050, args["stop_deadline"])
        self.assertEqual(10.0, timeout)
        self.assertIsInstance(sample["value"]["capturedUptimeMs"], int)

    def test_receipt_anchor_yields_conservative_device_deadlines_across_delays(self):
        # This model knows capture's actual host instant. Production deliberately knows only
        # the later receipt, so neither deadline may extend that model's true deadline.
        for dispatch in (0.0, 0.2, 0.7):
            for receipt_delay in (0.0, 0.1, 0.8):
                for after_receipt in (0.0, 0.3, 1.0):
                    requested, captured_host = 100.0, 100.0 + dispatch
                    received = captured_host + receipt_delay
                    now = received + after_receipt
                    sample = observation(requested=requested, received=received)
                    args, timeout = touch.request_arguments(sample, focused.body_swipe(sample["value"]), 105.0, now, "a" * 32)
                    device_clock = lambda host: 1050 + (host - captured_host) * 1000
                    with self.subTest(dispatch=dispatch, receipt=receipt_delay, after=after_receipt):
                        self.assertLessEqual(args["start_deadline"], device_clock(requested + 9) + 0.001)
                        self.assertLessEqual(args["stop_deadline"], device_clock(105.0) + 0.001)
                        self.assertLessEqual(args["start_deadline"], sample["value"]["expiresUptimeMs"])
                        self.assertAlmostEqual(105.0 - now, timeout)

    def test_expired_missing_or_invalid_receipt_anchors_cannot_create_input(self):
        for received in (None, True, float("nan"), 99.9, 101.0):
            sample = observation(received=received)
            with self.subTest(received=received), self.assertRaises(engine.ObservationFailure):
                touch.request_arguments(sample, focused.body_swipe(sample["value"]), 820, 100, "a" * 32)
        for now, deadline in ((109.0, 820.0), (100.0, 100.0)):
            with self.subTest(now=now, deadline=deadline), self.assertRaises(engine.ObservationFailure):
                arguments(now, deadline)

    def test_geometry_and_request_types_are_rejected_before_transport(self):
        sample = observation()
        gesture = focused.body_swipe(sample["value"])
        for change in ({"start": [True, 300]}, {"end": [gesture["end"][0] + 1, gesture["end"][1]]},
                       {"duration_ms": True}, {"duration_ms": 9800}, {"tail_ms": 201}):
            with self.subTest(change=change), self.assertRaises(engine.ObservationFailure):
                touch.request_arguments(sample, gesture | change, 820, 100, "a" * 32)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.args, _ = arguments()
        self.raw = fixtures.continuous_output(wire(self.args), 1051)
        self.value = touch.completed_receipt(self.raw, self.args)

    def test_success_requires_complete_fresh_tail_release_and_exact_identity(self):
        mutations = (
            {"ok": False}, {"phase": "moving"}, {"failureClass": "IllegalStateException"},
            {"releaseFailureClass": "IllegalStateException"}, {"requestId": "b" * 32},
            {"inputUncertain": True}, {"downAttempted": False}, {"upAttempted": False}, {"tailCompleted": False},
            {"start": [True, self.value["start"][1]]}, {"pointerId": 1}, {"pointerCount": 2},
            {"automationFlags": 2}, {"inputSource": 0}, {"tailDurationMs": 199}, {"schemaVersion": True},
            {"downAckUptimeMs": self.args["start_deadline"]}, {"upAckUptimeMs": self.args["stop_deadline"]},
            {"endpointAckUptimeMs": self.value["downTimeUptimeMs"] + self.args["move_ms"] - 1},
            {"tailEndUptimeMs": self.value["tailStartUptimeMs"] + 199}, {"upEventUptimeMs": 1},
            {"eventsAcknowledged": 5}, {"stationaryMoveEvents": 1}, {"eventsAttempted": 1205},
            {"eventsAcknowledged": True}, {"extra": "unexpected"},
        )
        for change in mutations:
            with self.subTest(change=change), self.assertRaises(engine.ObservationFailure):
                touch.completed_receipt(receipt_text(self.value | change), self.args)

    def test_missing_duplicate_failed_and_oversized_completions_fail(self):
        invalid = ["", self.raw.replace("INSTRUMENTATION_CODE: -1", "INSTRUMENTATION_CODE: 0"),
            self.raw + "INSTRUMENTATION_CODE: -1\n", self.raw + self.raw,
            self.raw + "INSTRUMENTATION_FAILED: host fixture\n", "x" * 65537,
            self.raw.replace('"schemaVersion": 1', '"schemaVersion": 1, "schemaVersion": 1')]
        for index, raw in enumerate(invalid):
            with self.subTest(index=index), self.assertRaises(engine.ObservationFailure):
                touch.completed_receipt(raw, self.args)


class InjectionTests(unittest.TestCase):
    def setUp(self):
        timer = patch.object(touch.time, "monotonic", return_value=100.0)
        self.clock = timer.start()
        self.addCleanup(timer.stop)

    def inject(self, smoke, audit=None):
        sample = observation()
        return touch.inject_continuous_touch(smoke, sample, focused.body_swipe(sample["value"]), 820, audit=audit)

    def assert_stopped(self, smoke):
        count = len(smoke.calls)
        self.assertTrue(smoke.input_incomplete)
        with self.assertRaises(engine.ObservationFailure):
            self.inject(smoke)
        with self.assertRaises(engine.ObservationFailure):
            smoke.adb("shell", "input", "tap", "1", "1")
        with self.assertRaises(engine.ObservationFailure):
            smoke.end_context_practice()
        self.assertEqual(count, len(smoke.calls))

    def test_one_self_target_command_and_bounded_audit_on_success(self):
        smoke, audit = Smoke(), {}
        result = self.inject(smoke, audit)
        self.assertEqual(1, len(smoke.calls))
        argv, kwargs = smoke.calls[0]
        self.assertEqual(("shell", "am", "instrument", "-w", "-r", "--no-test-api-access", "--always-check-signature"), argv[:7])
        self.assertEqual(touch.COMPONENT, argv[-1])
        self.assertLessEqual(kwargs["timeout"], 10)
        self.assertTrue(result["ok"])
        self.assertEqual("completed", audit["status"])
        self.assertEqual(result, audit["receipt"])
        self.assertEqual(64, len(audit["completion_sha256"]))
        self.assertNotIn("stdout", audit)
        self.assertFalse(smoke.input_incomplete)

    def test_transport_errors_interrupts_and_bad_receipts_latch_without_retry(self):
        scenarios = [dict(error=subprocess.TimeoutExpired(["host-only-adb"], 10)),
                     dict(error=OSError("Host transport fixture")), dict(error=KeyboardInterrupt()),
                     dict(reply=lambda _: "malformed host completion")]
        for scenario in scenarios:
            smoke, audit = Smoke(**scenario), {}
            expected = KeyboardInterrupt if isinstance(scenario.get("error"), KeyboardInterrupt) else engine.ObservationFailure
            with self.subTest(scenario=scenario), self.assertRaises(expected):
                self.inject(smoke, audit)
            self.assertEqual(1, len(smoke.calls))
            self.assertEqual("failed-or-uncertain", audit["status"])
            self.assert_stopped(smoke)

    def test_valid_but_late_host_completion_cannot_authorize_following_input(self):
        smoke = Smoke(completed=lambda: setattr(self.clock, "return_value", 110.0))
        audit = {}
        with self.assertRaises(engine.ObservationFailure):
            self.inject(smoke, audit)
        self.assertIn("host deadline", audit["failure"])
        self.assertNotIn("receipt", audit)
        self.assert_stopped(smoke)

    def test_receipt_validation_must_also_finish_before_host_deadline(self):
        smoke, audit = Smoke(), {}
        parse = touch.completed_receipt
        def late_parse(output, args):
            value = parse(output, args)
            self.clock.return_value = 110.0
            return value
        with patch.object(touch, "completed_receipt", side_effect=late_parse), self.assertRaises(engine.ObservationFailure):
            self.inject(smoke, audit)
        self.assertIn("validation", audit["failure"])
        self.assert_stopped(smoke)


class SweepDeadlineTests(unittest.TestCase):
    def setUp(self):
        timer = patch.object(focused.time, "monotonic", return_value=100.0)
        self.clock = timer.start()
        self.addCleanup(timer.stop)

    def sweep(self):
        smoke = fixtures.HostSmoke([fixtures.snapshot(y, index * 8) for index, y in enumerate((240, 180, 120, 120, 120))])
        probe = fixtures.HostProbe(smoke)
        return focused.ContextSweep(smoke, probe), smoke, probe

    def test_terminal_capture_expiry_preserves_capture_without_new_refresh_or_success(self):
        sweep, smoke, probe = self.sweep()
        refresh_count = []
        def expire(value):
            if len(smoke.captures) == 5:
                refresh_count.append(probe.refresh_count)
                self.clock.return_value = 820.0
        smoke.capture_mutation = expire
        with self.assertRaisesRegex(engine.ObservationFailure, "deadline"):
            sweep.run()
        self.assertEqual([probe.refresh_count], refresh_count)
        self.assertEqual(5, len(smoke.captures))
        self.assertEqual(4, len(sweep.positions))
        self.assertTrue(smoke.input_incomplete)

    def test_terminal_measurement_expiry_cannot_return_pass(self):
        sweep, smoke, _ = self.sweep()
        measure = focused.measured_displacement
        def expire(before, after):
            result = measure(before, after)
            if len(smoke.calls) == 4:
                self.clock.return_value = 820.0
            return result
        with patch.object(focused, "measured_displacement", side_effect=expire), self.assertRaisesRegex(engine.ObservationFailure, "deadline"):
            sweep.run()
        self.assertEqual(4, len(smoke.calls))
        self.assertTrue(smoke.context_sweep_expired)
        with self.assertRaises(engine.ObservationFailure):
            smoke.end_context_practice()

    def test_initial_expiry_has_no_observation_capture_or_input(self):
        sweep, smoke, probe = self.sweep()
        with patch.object(focused, "SWEEP_SECONDS", 0), self.assertRaises(engine.ObservationFailure):
            sweep.run()
        self.assertEqual(0, probe.settled_count)
        self.assertEqual([], smoke.captures)
        self.assertEqual([], smoke.calls)

    def test_nested_transports_are_bounded_and_late_return_blocks_all_new_calls(self):
        for method in ("adb", "command"):
            self.clock.return_value = 100.0
            smoke = Smoke(completed=lambda: setattr(self.clock, "return_value", 101.0))
            smoke.context_sweep_deadline = 101.0
            with self.subTest(method=method), self.assertRaisesRegex(engine.ObservationFailure, "deadline"):
                getattr(smoke, method)("shell", "dumpsys", "window", timeout=20)
            calls = smoke.calls if method == "adb" else smoke.command_calls
            self.assertEqual(1.0, calls[0][1]["timeout"])
            with self.assertRaises(engine.ObservationFailure):
                smoke.capture_evidence("forbidden-new-capture")
            with self.assertRaises(engine.ObservationFailure):
                smoke.adb("shell", "input", "tap", "1", "1")
            self.assertEqual([], smoke.captures)
            self.assertEqual(1, len(calls))
            self.assertTrue(smoke.input_incomplete)

    def test_fast_uncertain_input_blocks_ui_dump_and_diagnostic_capture_before_deadline(self):
        smoke = Smoke()
        smoke.context_sweep_deadline, smoke.input_incomplete = 200.0, True
        with self.assertRaisesRegex(engine.ObservationFailure, "Uncertain input"):
            smoke.capture_evidence("final-diagnostic", diagnostic=True)
        with self.assertRaisesRegex(engine.ObservationFailure, "Uncertain input"):
            smoke.dump_ui()
        self.assertEqual([], smoke.captures)
        self.assertEqual([], smoke.calls)
        smoke.adb("logcat", "-d", "-b", "crash")
        self.assertEqual(1, len(smoke.calls))


class HelperAdmissionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="partydeck-helper-host-")
        self.addCleanup(directory.cleanup)
        self.bundle = Path(directory.name)
        self.apk = self.bundle / touch.APK_NAME
        self.apk.write_bytes(b"host-only helper fixture, never installed")
        self.packaged = self.bundle / "continuous-input-packaged-manifest.xml"
        self.packaged.write_bytes(fixtures.HELPER_MANIFEST)
        self.manifest = {"files": {touch.APK_NAME: {"sha256": inputs.digest(self.apk), "bytes": self.apk.stat().st_size}}}
        self.item = dict(verified=True, apkSha256=inputs.digest(self.apk), metadata=touch.inspect_manifest(fixtures.HELPER_MANIFEST),
                        manifestSha256=inputs.digest(self.packaged), certificateSha256="c" * 64)
        self.report = {"continuousInput": self.item}

    def admit(self):
        return touch.admit_helper(self.bundle, self.manifest, self.report, self.bundle)

    def test_same_run_helper_metadata_and_actual_manifest_are_both_bound(self):
        identity = self.admit()
        self.assertEqual(inputs.digest(self.apk), identity["apk_sha256"])
        self.assertEqual(inputs.digest(self.packaged), identity["manifest_sha256"])
        self.assertEqual("c" * 64, identity["certificate_sha256"])
        for field, value in (("verified", False), ("apkSha256", "0" * 64), ("metadata", {}),
                             ("manifestSha256", "0" * 64), ("certificateSha256", "")):
            original = self.item[field]
            self.item[field] = value
            with self.subTest(field=field), self.assertRaises(engine.ObservationFailure):
                self.admit()
            self.item[field] = original
        self.packaged.write_bytes(fixtures.HELPER_MANIFEST + b" ")
        with self.assertRaises(engine.ObservationFailure):
            self.admit()

    def test_manifest_rejects_app_target_permissions_components_and_non_test_build(self):
        original = fixtures.HELPER_MANIFEST
        invalid = [original.replace(b'android:targetPackage="dev.partydeck.qualification.input"', b'android:targetPackage="dev.partydeck.app"'),
                   original.replace(b'android:testOnly="true"', b'android:testOnly="false"'),
                   original.replace(b'android:allowBackup="false"', b'android:allowBackup="true"'),
                   original.replace(b'<uses-sdk ', b'<uses-permission android:name="android.permission.INTERNET"/><uses-sdk '),
                   original.replace(b'<application ', b'<application><activity android:name="Bad"/></application><application '),
                   original.replace(b'android:minSdkVersion="36"', b'android:minSdkVersion="35"'),
                   original.replace(b'<instrumentation ', b'<instrumentation android:targetProcesses="dev.partydeck.app" ')]
        for raw in invalid:
            self.packaged.write_bytes(raw)
            self.item["manifestSha256"] = inputs.digest(self.packaged)
            with self.subTest(raw=raw), self.assertRaises(engine.ObservationFailure):
                self.admit()

    def test_changed_or_indirect_helper_is_rejected_before_install(self):
        identity = self.admit()
        self.apk.write_bytes(self.apk.read_bytes() + b" changed")
        smoke = Smoke()
        with self.assertRaises(engine.ObservationFailure):
            touch.install_helper(smoke, self.bundle, identity)
        self.assertEqual([], smoke.calls)
        target = self.bundle / "moved.apk"
        self.apk.rename(target)
        self.apk.symlink_to(target)
        with self.assertRaises(engine.ObservationFailure):
            self.admit()

    def test_helper_install_is_one_test_only_install_and_success_is_required(self):
        identity, smoke = self.admit(), Smoke()
        touch.install_helper(smoke, self.bundle, identity)
        self.assertEqual([(("install", "-t", str(self.apk)), {"timeout": 60})], smoke.calls)
        self.assertEqual(identity, smoke.identity["continuous_input_helper"])
        failed = Smoke(reply=lambda _: "Failure [HOST_FIXTURE]")
        with self.assertRaises(engine.ObservationFailure):
            touch.install_helper(failed, self.bundle, identity)
        self.assertEqual(1, len(failed.calls))
        self.assertNotIn("continuous_input_helper", failed.identity)


class ProducerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="partydeck-helper-producer-host-")
        self.addCleanup(directory.cleanup)
        self.bundle, self.output = Path(directory.name) / "bundle", Path(directory.name) / "output"
        self.bundle.mkdir()
        self.output.mkdir()
        for name in inputs.FILES:
            (self.bundle / name).write_bytes(b"Host-only non-runtime fixture: " + name.encode())
        self.assertIn(touch.APK_NAME, inputs.FILES)
        for name in ("androidApp-debug.apk", "PartyDeck-release-ci-test-signed.apk"):
            with zipfile.ZipFile(self.bundle / name, "w") as archive:
                archive.writestr("assets/partydeck-last-light.pck", (self.bundle / "partydeck-last-light.pck").read_bytes())
        (self.bundle / "godot-activation-build.json").write_text(json.dumps(dict(schemaVersion=1, profile="qualification", modesCsv="2d,3d")))
        signing = dict(variant="optimized-test-signed", signingIdentity="disposable-ci-test-key", distributionSigned=False,
                       alignmentKiB=16, originalUnsignedSha256=inputs.digest(self.bundle / "androidApp-release-unsigned.apk"),
                       runtimeApkSha256=inputs.digest(self.bundle / "PartyDeck-release-ci-test-signed.apk"), certificateSha256="a" * 64)
        (self.bundle / "runtime-package.json").write_text(json.dumps(signing))
        self.helper_manifest, self.helper_signers, self.signature_error = fixtures.HELPER_MANIFEST, ["c" * 64], None
        self.stems = []

    def inspect(self, report):
        def checked(argv, output, stem):
            self.stems.append(stem)
            if stem == "continuous-input-manifest":
                return self.helper_manifest
            if stem.endswith("-signature"):
                if stem == "continuous-input-signature" and self.signature_error:
                    raise self.signature_error
                fingerprints = self.helper_signers if stem == "continuous-input-signature" else ["a" * 64]
                return "\n".join(f"Signer #{index + 1} certificate SHA-256 digest: {value}" for index, value in enumerate(fingerprints)).encode()
            return b"host-only checked-command result"
        def app_manifest(argv, **kwargs):
            debug = "true" if str(argv[-1]).endswith("androidApp-debug.apk") else "false"
            raw = ('<manifest package="dev.partydeck.app" xmlns:android="http://schemas.android.com/apk/res/android">'
                '<application android:debuggable="' + debug + '"><meta-data android:name="dev.partydeck.GODOT_ACTIVATION_PROFILE" android:value="qualification"/>'
                '<meta-data android:name="dev.partydeck.GODOT_PRESENTATION_MODES" android:value="2d,3d"/></application></manifest>').encode()
            return SimpleNamespace(stdout=raw, stderr=b"", returncode=0)
        with patch.object(inputs, "ROOT", fixtures.SCRIPTS.parent), patch.object(inputs, "PINS", {}), \
                patch.dict(os.environ, {"ANDROID_HOME": "/host-only-sdk-never-executed"}), \
                patch.object(inputs.shutil, "which", return_value="host-only-apkanalyzer"), \
                patch.object(inputs, "checked_command", side_effect=checked), \
                patch.object(inputs.subprocess, "run", side_effect=app_manifest):
            inputs.inspect_inputs(self.bundle, self.output, report)

    def test_producer_verifies_helper_and_both_original_app_packages(self):
        report = {}
        self.inspect(report)
        helper = report["continuousInput"]
        self.assertTrue(helper["verified"])
        self.assertEqual("c" * 64, helper["certificateSha256"])
        self.assertEqual(inputs.digest(self.bundle / touch.APK_NAME), helper["apkSha256"])
        self.assertEqual(fixtures.HELPER_MANIFEST, (self.output / "continuous-input-packaged-manifest.xml").read_bytes())
        self.assertTrue(all(item["verified"] for item in report["packages"].values()))
        self.assertEqual({"debug", "optimized-test-signed"}, set(report["packages"]))

    def test_missing_multiple_or_failed_helper_signatures_never_become_verified(self):
        for signatures, error in (([], None), (["b" * 64, "c" * 64], None), (["c" * 64], ValueError("Host signature failure"))):
            self.helper_signers, self.signature_error = signatures, error
            report = {}
            with self.subTest(signatures=signatures, error=error), self.assertRaises(ValueError):
                self.inspect(report)
            self.assertIs(False, report["continuousInput"]["verified"])
            self.assertNotIn("packages", report)

    def test_invalid_self_target_manifest_stops_before_signature_acceptance(self):
        self.helper_manifest = self.helper_manifest.replace(b'android:testOnly="true"', b'android:testOnly="false"')
        report = {}
        with self.assertRaises(engine.ObservationFailure):
            self.inspect(report)
        self.assertIs(False, report["continuousInput"]["verified"])
        self.assertNotIn("continuous-input-signature", self.stems)


if __name__ == "__main__":
    unittest.main(verbosity=2)
