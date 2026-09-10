"""Host-only adversarial traces for the actual Android acceptance driver."""

import copy
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import run as runner
from evidence import (
    CheckFailure, HostTrace, accepted_intent, active, completed_teardown, concealed,
    healthy, local_transition, validate_host,
)
from test_evidence import hidden, png_fixture


IDENTITY = "a517cdd0-90ad-4c75-8c6a-73174d30fe39"


def host():
    diagnostic = hidden()
    diagnostic.update(presentationId=IDENTITY, revision="0", requestId="1", sequence="0")
    return {
        "schemaVersion": 1, "evidenceRevision": "8", "presentationId": IDENTITY, "mode": "2d",
        "randomness": "reference_seed_2", "displayDensity": 1.75, "enginePid": 1234, "taskId": 19,
        "startedElapsedRealtimeMs": "15000", "lifecycle": "active", "setupCompleted": True,
        "mainLoopStarted": True, "readyAccepted": True, "foreground": True, "coverVisible": False,
        "foregroundFrameReady": True, "bridgeClosed": False, "nativeDestroyRequested": False,
        "nativeDestroyReturned": False, "nativeTerminating": False, "nativeForceQuitCallback": False,
        "processExitRequested": False, "diagnosticsRequested": "1", "diagnosticsTimedOut": False,
        "capturePolicy": "recents_disabled", "revision": "0", "receivedEvents": "1",
        "receivedIntents": "0", "acceptedIntents": "0", "rejectedEvents": "0", "authorityRejections": "0",
        "botActions": "0", "submittedCommands": "2",
        "publicState": {"phase": "PLAYING", "roundNumber": 1, "viewerHandCount": 5,
                        "canPlay": True, "canChallenge": False, "canAdvanceRound": False, "winnerPresent": False},
        "engineSurface": {"x": 0, "y": 200, "width": 720, "height": 1200}, "diagnostics": diagnostic,
    }


def refreshed(value=None):
    value = copy.deepcopy(value or host())
    value["evidenceRevision"] = str(int(value["evidenceRevision"]) + 1)
    value["diagnosticsRequested"] = str(int(value["diagnosticsRequested"]) + 1)
    value["diagnostics"]["requestId"] = value["diagnosticsRequested"]
    value["diagnostics"]["sequence"] = str(int(value["diagnostics"]["sequence"]) + 1)
    return value


def final_host():
    value = refreshed()
    value.update(lifecycle="process_exit_requested", foreground=False, coverVisible=True,
                 foregroundFrameReady=False, bridgeClosed=True, nativeDestroyRequested=True,
                 nativeDestroyReturned=True, nativeTerminating=True, processExitRequested=True,
                 closeSignalAcknowledged=True, closeReason="native_close", nativeDestroyElapsedMs="45")
    return value


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class ReplayDevice:
    """Supplies observed documents only; it cannot manufacture a driver success."""
    def __init__(self, clock, after, crash=False):
        self.clock, self.after, self.crash = clock, copy.deepcopy(after), crash
        self.deadline, self.stage = 60, "host-only replay"
        self.display_size = (720, 1600)
        self.taps, self.dump_count = [], 0
        self.engine_alive, self.chooser_pid = False, 999
        self.final_only = False

    def check_ui(self, deadline=None):
        self.clock.sleep(0.1)
        self.dump_count += 1
        if self.crash:
            raise CheckFailure("Actual Android crash/ANR dialog blocks acceptance.")
        return ET.Element("hierarchy")

    def read_host(self, allow_missing=False):
        return copy.deepcopy(self.after if self.taps or self.final_only else host())

    def native_tap(self, tag, **_):
        self.taps.append(tag)

    def pids(self, name):
        return ({1234} if self.engine_alive else set()) if name.endswith(":godot") else {self.chooser_pid}

    def pid_exists(self, pid):
        return self.engine_alive

    def wait_for_tag(self, tag, **_):
        return ET.Element("node", {"resource-id": tag, "enabled": "true", "package": runner.PACKAGE})

    def record(self, message):
        pass


class HostSchemaTest(unittest.TestCase):
    def test_current_ready_evidence_requires_actual_plugin_and_frame_facts(self):
        self.assertTrue(active(validate_host(host())))
        for field in ("readyAccepted", "mainLoopStarted", "setupCompleted", "foregroundFrameReady"):
            value = host()
            value[field] = False
            with self.subTest(field=field):
                self.assertFalse(active(validate_host(value)))
        value = host()
        value["submittedCommands"] = "0"
        self.assertFalse(active(validate_host(value)))

    def test_host_cannot_accept_future_or_wrong_lifetime_diagnostics(self):
        for field, replacement in (("presentationId", "another-entry"), ("revision", "1"), ("requestId", "2")):
            value = host()
            value["diagnostics"][field] = replacement
            with self.subTest(field=field), self.assertRaises(CheckFailure):
                validate_host(value)

    def test_private_or_unknown_host_fields_are_rejected_before_persistence(self):
        value = host()
        value["privateHand"] = ["secret"]
        with self.assertRaises(CheckFailure):
            validate_host(value)
        value = host()
        value["diagnostics"]["controls"][0]["privateCardId"] = "secret"
        with self.assertRaises(CheckFailure):
            validate_host(value)

    def test_failure_rejection_and_diagnostic_timeout_cannot_pass(self):
        for field, replacement in (("failureCode", "renderer_ready_timeout"), ("rejectedEvents", "1"),
                                   ("authorityRejections", "1"), ("diagnosticsTimedOut", True)):
            value = host()
            value[field] = replacement
            with self.subTest(field=field), self.assertRaises(CheckFailure):
                healthy(validate_host(value))

    def test_lifetime_trace_rejects_rollback_and_changed_same_revision(self):
        for change in ({"evidenceRevision": "7"}, {"submittedCommands": "1"}, {"taskId": 20},
                       {"enginePid": 1235}, {"mode": "3d"}):
            trace = HostTrace(IDENTITY, "2d", 1234)
            trace.accept(host())
            value = host()
            value.update(change)
            with self.subTest(change=change), self.assertRaises(CheckFailure):
                trace.accept(value)

    def test_exact_intent_roundtrip_requires_new_real_authority_view(self):
        before = host()
        good = refreshed()
        good.update(receivedEvents="2", receivedIntents="1", acceptedIntents="1", lastIntentType="play",
                    revision="1", submittedCommands="3")
        good["diagnostics"]["revision"] = "1"
        accepted_intent(before, good, "play")
        for change in ({"acceptedIntents": "0"}, {"receivedIntents": "2"}, {"lastIntentType": "challenge"},
                       {"revision": "0"}, {"submittedCommands": "2"}):
            value = copy.deepcopy(good)
            value.update(change)
            with self.subTest(change=change), self.assertRaises(CheckFailure):
                accepted_intent(before, value, "play")

    def test_local_reveal_or_selection_must_not_emit_an_authority_event(self):
        local_transition(host(), refreshed())
        for field in ("revision", "receivedEvents", "receivedIntents", "acceptedIntents"):
            value = refreshed()
            value[field] = str(int(value[field]) + 1)
            with self.subTest(field=field), self.assertRaises(CheckFailure):
                local_transition(host(), value)

    def test_teardown_requires_all_native_markers(self):
        completed_teardown(validate_host(final_host()), "native_close")
        for field in ("bridgeClosed", "nativeDestroyRequested", "nativeDestroyReturned", "nativeTerminating",
                      "processExitRequested", "closeSignalAcknowledged", "coverVisible"):
            value = final_host()
            value[field] = False
            with self.subTest(field=field), self.assertRaises(CheckFailure):
                completed_teardown(value, "native_close")


class DriverReplayTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = pathlib.Path(self.directory.name)
        self.clock = Clock()
        self.time_patch = mock.patch.object(runner, "time", self.clock)
        self.time_patch.start()
        self.addCleanup(self.time_patch.stop)

    def qualification(self, after, crash=False):
        device = ReplayDevice(self.clock, after, crash)
        value = runner.Qualification(device, self.output)
        value.entry_output = self.output
        value.trace = HostTrace(IDENTITY, "2d", 1234)
        value.chooser_pid = 999
        return value

    def test_fresh_correlated_response_follows_one_visible_native_request(self):
        qualification = self.qualification(refreshed())
        value = qualification.refresh("fresh response")
        self.assertEqual(value["diagnostics"]["requestId"], "2")
        self.assertEqual(qualification.device.taps, ["refresh_diagnostics"])
        self.assertGreaterEqual(qualification.device.dump_count, 2)

    def test_stale_file_times_out_without_repeated_native_taps(self):
        qualification = self.qualification(host())
        with self.assertRaisesRegex(CheckFailure, "within 30 seconds"):
            qualification.refresh("fresh response")
        self.assertEqual(qualification.device.taps, ["refresh_diagnostics"])
        self.assertLessEqual(self.clock.now, 30.3)

    def test_wrong_identity_after_request_is_rejected(self):
        value = refreshed()
        value["presentationId"] = "8a8b4714-0f99-4d77-bcdf-ce78f978d6ca"
        value["diagnostics"]["presentationId"] = value["presentationId"]
        qualification = self.qualification(value)
        with self.assertRaisesRegex(CheckFailure, "another native lifetime"):
            qualification.refresh("fresh response")

    def test_new_request_with_old_view_cannot_pass(self):
        value = refreshed()
        value["revision"] = "1"  # Renderer still reports revision zero.
        qualification = self.qualification(value)
        with self.assertRaisesRegex(CheckFailure, "within 30 seconds"):
            qualification.refresh("fresh response")

    def test_crash_rejection_precedes_even_valid_host_evidence(self):
        qualification = self.qualification(refreshed(), crash=True)
        with self.assertRaisesRegex(CheckFailure, "crash/ANR"):
            qualification.refresh("fresh response")
        self.assertEqual(qualification.device.taps, [])
        self.assertIsNone(qualification.snapshot)

    def test_hidden_but_retained_private_binding_cannot_satisfy_response(self):
        value = refreshed()
        value["diagnostics"]["privateFaceCount"] = 1
        qualification = self.qualification(value)
        with self.assertRaisesRegex(CheckFailure, "within 30 seconds"):
            qualification.refresh("concealed response", lambda item: concealed(item["diagnostics"]))

    def test_documented_native_close_without_pid_death_still_fails(self):
        qualification = self.qualification(final_host())
        qualification.device.final_only = True
        qualification.device.engine_alive = True
        with self.assertRaisesRegex(CheckFailure, "actual old engine PID remains alive"):
            qualification.exit_entry("native_close")
        self.assertLessEqual(self.clock.now, 25.3)

    def test_missing_native_marker_fails_even_when_process_is_absent(self):
        value = final_host()
        value["nativeTerminating"] = False
        qualification = self.qualification(value)
        qualification.device.final_only = True
        with self.assertRaisesRegex(CheckFailure, "Missing actual native teardown marker"):
            qualification.exit_entry("native_close")

    def test_replaced_chooser_does_not_pass_engine_teardown(self):
        qualification = self.qualification(final_host())
        qualification.device.final_only = True
        qualification.device.chooser_pid = 1000
        with self.assertRaisesRegex(CheckFailure, "killed or replaced the native chooser"):
            qualification.exit_entry("native_close")

    def test_clean_teardown_records_process_absence_and_surviving_chooser(self):
        qualification = self.qualification(final_host())
        qualification.device.final_only = True
        log = mock.Mock()
        qualification.engine_log = log
        qualification.capture_native = mock.Mock()
        qualification.exit_entry("native_close")
        log.close.assert_called_once()
        value = json.loads((self.output / "teardown.json").read_text())
        self.assertTrue(value["old_pid_absent"])
        self.assertEqual(value["surviving_chooser_pid"], 999)

    def test_scene_geometry_changed_before_touch_is_not_used(self):
        qualification = self.qualification(refreshed())
        qualification.device.final_only = True
        root = ET.Element("hierarchy")
        ET.SubElement(root, "node", {"package": runner.PACKAGE,
                                      "resource-id": runner.PACKAGE + ":id/host_status"})
        qualification.device.check_ui = mock.Mock(return_value=root)
        before = host()
        with self.assertRaisesRegex(CheckFailure, "refusing stale coordinates"):
            qualification.scene_input(before, before["diagnostics"]["controls"][0], "tap", {"x": 70, "y": 600})
        self.assertFalse((self.output / "scene-input-geometry.log").exists())

    def test_clipped_stationary_control_stops_without_a_tap(self):
        value = host()
        value["diagnostics"]["controls"][0].update(rect=[20, 1150, 100, 200], enabled=True)
        qualification = self.qualification(value)
        qualification.refresh = mock.Mock(return_value=value)
        qualification.scene_input = mock.Mock()
        qualification.device.adb = mock.Mock()
        with self.assertRaisesRegex(CheckFailure, "scroll did not move"):
            qualification.control("card", 0)
        self.assertEqual(qualification.device.adb.call_count, 2)
        for call in qualification.device.adb.call_args_list:
            self.assertEqual(call.args[:3], ("shell", "input", "swipe"))


class ProcessAndCleanupTest(unittest.TestCase):
    def test_final_diagnostic_errors_and_crash_cannot_be_silently_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            for name in ("logcat.log", "events.log", "last-anr.log"):
                (output / name).write_text("retained\n")
            (output / "last-ui.xml").write_text("<hierarchy />")
            (output / "final-screen.png").write_bytes(png_fixture(1, 1, b"\0\0\0"))
            device = runner.Device("no-device", output, "run-as")
            with mock.patch.object(runner.baseline.AndroidSmoke, "diagnostics"):
                device.diagnostics()
                error_file = output / "events.log.error.log"
                error_file.write_text("adb failed")
                with self.assertRaisesRegex(CheckFailure, "diagnostic collection was incomplete"):
                    device.diagnostics()
                error_file.unlink()
                (output / "last-ui.xml").write_text('<hierarchy><node resource-id="android:id/aerr_wait" /></hierarchy>')
                with self.assertRaisesRegex(RuntimeError, "crash/ANR"):
                    device.diagnostics()

    def test_privileged_observation_requires_existing_root_and_does_not_enable_it(self):
        with tempfile.TemporaryDirectory() as directory:
            device = runner.Device("no-device", pathlib.Path(directory), "root")
            device.adb = mock.Mock(side_effect=("0", "userdebug", "1", "0"))
            self.assertEqual(device.assert_access()["method"], "privileged_userdebug_private_file")
            self.assertTrue(all(call.args[0] == "shell" for call in device.adb.call_args_list))
            device.adb = mock.Mock(side_effect=("0", "userdebug", "1", "2000"))
            with self.assertRaisesRegex(CheckFailure, "already-rooted adbd"):
                device.assert_access()
            self.assertTrue(all(call.args[0] == "shell" for call in device.adb.call_args_list))

    def test_pidof_absence_is_distinct_from_adb_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            device = runner.Device("no-device", pathlib.Path(directory), "run-as")
            device.command = mock.Mock(return_value=subprocess.CompletedProcess([], 1, "", ""))
            self.assertEqual(device.pids(runner.PACKAGE + ":godot"), set())
            for result in (subprocess.CompletedProcess([], 1, "", "error: device offline"),
                           subprocess.CompletedProcess([], 0, "", ""),
                           subprocess.CompletedProcess([], 0, "not a PID", "")):
                device.command.return_value = result
                with self.subTest(result=result), self.assertRaises(CheckFailure):
                    device.pids(runner.PACKAGE + ":godot")

    def test_upstream_timeout_is_not_successful_native_termination(self):
        runner.EngineLog.inspect("Godot: OnGodotTerminating\n")
        for message in ("Unable to exit the renderer within 1500 ms... Force quitting the process.",
                        "AndroidRuntime: FATAL EXCEPTION: main", "godot: SCRIPT ERROR: Invalid call",
                        "09-10 07:11:12.345 1234 1452 E godot : ERROR: Failed loading resource: res://missing.png."):
            with self.subTest(message=message), self.assertRaises(CheckFailure):
                runner.EngineLog.inspect(message)

    def test_early_successful_logcat_exit_is_a_missing_evidence_interval(self):
        with tempfile.TemporaryDirectory() as directory:
            log = object.__new__(runner.EngineLog)
            log.path, log.errors = pathlib.Path(directory) / "log", pathlib.Path(directory) / "errors"
            log.output, log.error_output = log.path.open("wb"), log.errors.open("wb")
            log.process = mock.Mock()
            log.process.poll.return_value = 0
            with self.assertRaisesRegex(CheckFailure, "stopped before the final teardown"):
                log.close()
            log.process.terminate.assert_not_called()
            self.assertTrue(log.output.closed and log.error_output.closed)

    def test_final_device_dump_detects_a_late_renderer_timeout_not_yet_streamed(self):
        with tempfile.TemporaryDirectory() as directory:
            log = object.__new__(runner.EngineLog)
            log.path, log.errors = pathlib.Path(directory) / "log", pathlib.Path(directory) / "errors"
            log.output, log.error_output = log.path.open("wb"), log.errors.open("wb")
            log.process, log.device, log.pid = mock.Mock(), mock.Mock(), 1234
            log.process.poll.return_value = None
            log.device.adb.return_value = "Godot: Unable to exit the renderer within 1500 ms... Force quitting the process."
            with self.assertRaisesRegex(CheckFailure, "timed out exiting its renderer"):
                log.close()
            log.device.adb.assert_called_once_with("logcat", "-d", "-v", "threadtime", "-b", "main", "-b", "system",
                                                   "-b", "crash", "--pid", "1234", timeout=20)
            log.process.terminate.assert_called_once()
            self.assertTrue(log.output.closed and log.error_output.closed)
            self.assertTrue(log.path.with_name("final-process-logcat.log").is_file())

    def test_final_device_dump_failure_still_stops_collector_and_closes_files(self):
        with tempfile.TemporaryDirectory() as directory:
            log = object.__new__(runner.EngineLog)
            log.path, log.errors = pathlib.Path(directory) / "log", pathlib.Path(directory) / "errors"
            log.output, log.error_output = log.path.open("wb"), log.errors.open("wb")
            log.process, log.device, log.pid = mock.Mock(), mock.Mock(), 1234
            log.process.poll.return_value = None
            log.device.adb.side_effect = subprocess.TimeoutExpired("final owned PID log", 20)
            with self.assertRaises(subprocess.TimeoutExpired):
                log.close()
            log.process.terminate.assert_called_once()
            self.assertTrue(log.output.closed and log.error_output.closed)

    def test_original_failure_survives_diagnostic_error_and_settings_restore_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "result"
            device = mock.Mock(stage="actual scene input", steps=[])
            device.diagnostics.side_effect = RuntimeError("diagnostic collection failed")
            device.restore_environment.return_value = []
            engine_log = mock.Mock()
            engine_log.close.side_effect = CheckFailure("log collector stopped early")
            qualification = mock.Mock(engine_log=engine_log, mode_result={"mode": "2d", "passed": False})
            qualification.setup.return_value = {}
            qualification.run_mode.side_effect = CheckFailure("original missing native round trip")
            with mock.patch.object(runner, "Device", return_value=device), \
                    mock.patch.object(runner, "Qualification", return_value=qualification), \
                    mock.patch.object(runner, "apk_facts", return_value={}), \
                    mock.patch.object(runner.sys, "argv", ["run.py", "--serial", "no-device", "--apk", "none.apk",
                                                         "--output", str(output), "--mode", "2d"]):
                self.assertEqual(runner.main(), 1)
            device.restore_environment.assert_called_once()
            value = json.loads((output / "result.json").read_text())
            self.assertFalse(value["passed"])
            self.assertEqual(value["error"], "original missing native round trip")
            self.assertTrue(any("diagnostic collection failed" in error for error in value["cleanup_errors"]))
            self.assertTrue(any("log collector stopped early" in error for error in value["cleanup_errors"]))

    def test_invalid_apk_never_contacts_a_device(self):
        with tempfile.TemporaryDirectory() as directory:
            device = mock.Mock(steps=[], stage="initialization")
            with mock.patch.object(runner, "Device", return_value=device), \
                    mock.patch.object(runner.sys, "argv", ["run.py", "--serial", "no-device", "--apk", "absent.apk",
                                                         "--output", str(pathlib.Path(directory) / "out")]):
                self.assertEqual(runner.main(), 1)
            device.adb.assert_not_called()
            device.diagnostics.assert_not_called()
            device.restore_environment.assert_not_called()


if __name__ == "__main__":
    unittest.main()
