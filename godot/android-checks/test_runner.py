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
CACHE_WARNING = (
    "09-10 03:34:52.733  3074  3111 E godot   : WARNING: Failed to load cached shader, recompiling.\n"
    "09-10 03:34:52.733  3074  3111 E godot   :    at: _load_from_cache (drivers/gles3/shader_gles3.cpp:615)\n"
)


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


def final_host(value=None):
    value = refreshed(value)
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

    def test_pending_scene_is_preserved_but_cannot_authorize_scene_input(self):
        value = host()
        value["diagnostics"]["sceneStateApplied"] = False
        observed = validate_host(value)
        self.assertIs(observed["diagnostics"]["sceneStateApplied"], False)
        self.assertFalse(active(observed))
        value["diagnostics"]["sceneStateApplied"] = True
        self.assertTrue(active(validate_host(value)))

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

    def response_trace(self, initial, responses):
        qualification = self.qualification(initial)
        observations = [initial] + responses

        def read_host(allow_missing=False):
            value = observations[min(len(qualification.device.taps), len(observations) - 1)]
            if isinstance(value, Exception):
                raise value
            return copy.deepcopy(value)

        qualification.device.read_host = read_host
        return qualification

    def entry_trace(self, initial, response):
        qualification = self.qualification(initial)
        qualification.mode_result = {}
        native_tap = qualification.device.native_tap

        def launch_or_refresh(tag, **kwargs):
            if tag.startswith("launch_"):
                qualification.device.engine_alive = True
            native_tap(tag, **kwargs)

        qualification.device.native_tap = launch_or_refresh
        qualification.device.read_host = lambda allow_missing=False: copy.deepcopy(
            response if "refresh_diagnostics" in qualification.device.taps else initial)
        return qualification

    def test_entry_pending_response_can_be_observed_without_relaxing_ready_or_scene_gates(self):
        pending = host()
        pending["diagnostics"]["sceneStateApplied"] = False
        applied = refreshed()
        qualification = self.entry_trace(pending, applied)
        with mock.patch.object(runner, "EngineLog"):
            value = qualification.enter("2d", "pending-entry")
        self.assertEqual(value, applied)
        self.assertTrue(active(value))
        self.assertEqual(qualification.device.taps, ["launch_2d", "refresh_diagnostics"])
        self.assertEqual(qualification.device.deadline, 60)
        local_transition(pending, value)

    def test_entry_pending_followup_preserves_the_original_entry_deadline(self):
        pending = host()
        pending["diagnostics"]["sceneStateApplied"] = False
        qualification = self.entry_trace(pending, refreshed())
        read_host = qualification.device.read_host
        observations = 0

        def delayed_entry(allow_missing=False):
            nonlocal observations
            observations += 1
            if observations == 2:
                self.clock.sleep(44.7)
            return read_host(allow_missing)

        qualification.device.read_host = delayed_entry
        with mock.patch.object(runner, "EngineLog"), self.assertRaisesRegex(CheckFailure, "within 44.9 seconds"):
            qualification.enter("2d", "pending-entry")
        self.assertEqual(qualification.device.taps, ["launch_2d", "refresh_diagnostics"])
        self.assertLessEqual(self.clock.now, 45.3)
        self.assertEqual(qualification.device.deadline, 60)

    def test_saved_pending_response_can_request_one_fresh_applied_observation(self):
        initial = host()
        initial["diagnostics"]["sceneStateApplied"] = False
        qualification = self.response_trace(initial, [refreshed()])
        value = qualification.refresh("applied scene")
        self.assertTrue(active(value))
        self.assertEqual(qualification.device.taps, ["refresh_diagnostics"])
        self.assertEqual(qualification.device.deadline, 60)
        local_transition(initial, value)

    def test_matching_pending_response_permits_only_an_observation_followup(self):
        initial = host()
        pending = refreshed(initial)
        pending["diagnostics"]["sceneStateApplied"] = False
        applied = refreshed(pending)
        applied["diagnostics"]["sceneStateApplied"] = True
        qualification = self.response_trace(initial, [pending, applied])
        value = qualification.refresh("applied scene")
        self.assertEqual(value, applied)
        self.assertEqual(qualification.device.taps, ["refresh_diagnostics"] * 2)
        self.assertEqual(qualification.device.deadline, 60)
        local_transition(initial, value)
        observed = [json.loads(line) for line in (self.output / "host-observations.log").read_text().splitlines()]
        self.assertIn(pending, observed)
        self.assertEqual(observed[-1], applied)

    def test_replayed_pending_response_cannot_trigger_another_followup(self):
        pending = refreshed()
        pending["diagnostics"]["sceneStateApplied"] = False
        qualification = self.response_trace(host(), [pending, pending])
        with self.assertRaisesRegex(CheckFailure, "within 30 seconds"):
            qualification.refresh("applied scene")
        self.assertEqual(qualification.device.taps, ["refresh_diagnostics"] * 2)
        self.assertLessEqual(self.clock.now, 30.3)
        self.assertEqual(qualification.device.deadline, 60)

    def test_missing_stale_or_unready_pending_evidence_never_permits_a_followup(self):
        for defect in ("missing_diagnostic", "request", "sequence", "revision", "cover", "foreground_frame"):
            with self.subTest(defect=defect):
                self.clock.now = 0
                pending = refreshed()
                pending["diagnostics"]["sceneStateApplied"] = False
                if defect == "missing_diagnostic":
                    del pending["diagnostics"]
                elif defect == "request":
                    pending["diagnostics"]["requestId"] = "1"
                elif defect == "sequence":
                    pending["diagnostics"]["sequence"] = "0"
                elif defect == "revision":
                    pending["revision"] = "1"
                elif defect == "cover":
                    pending["coverVisible"] = True
                else:
                    pending["foregroundFrameReady"] = False
                qualification = self.response_trace(host(), [pending])
                with self.assertRaisesRegex(CheckFailure, "within 30 seconds"):
                    qualification.refresh("applied scene")
                self.assertEqual(qualification.device.taps, ["refresh_diagnostics"])
                self.assertLessEqual(self.clock.now, 30.3)
                self.assertEqual(qualification.device.deadline, 60)

    def test_missing_saved_response_does_not_start_diagnostic_tapping(self):
        initial = host()
        del initial["diagnostics"]
        qualification = self.response_trace(initial, [])
        with self.assertRaisesRegex(CheckFailure, "within 30 seconds"):
            qualification.refresh("applied scene")
        self.assertEqual(qualification.device.taps, [])

    def test_native_timeout_wrong_lifetime_or_missing_file_is_not_retried(self):
        for defect in ("timeout", "lifetime", "file"):
            with self.subTest(defect=defect):
                pending = refreshed()
                pending["diagnostics"]["sceneStateApplied"] = False
                if defect == "timeout":
                    pending["diagnosticsTimedOut"] = True
                    error = "diagnostic request timed out"
                elif defect == "lifetime":
                    pending["enginePid"] = 4321
                    error = "another native lifetime"
                else:
                    pending = CheckFailure("Could not read the real app-private host evidence")
                    error = "Could not read"
                qualification = self.response_trace(host(), [pending])
                with self.assertRaisesRegex(CheckFailure, error):
                    qualification.refresh("applied scene")
                self.assertEqual(qualification.device.taps, ["refresh_diagnostics"])
                self.assertEqual(qualification.device.deadline, 60)

    def test_applied_response_must_still_satisfy_the_original_observation_predicate(self):
        pending = refreshed()
        pending["diagnostics"]["sceneStateApplied"] = False
        applied = refreshed(pending)
        applied["diagnostics"].update(sceneStateApplied=True, privateFaceCount=1)
        qualification = self.response_trace(host(), [pending, applied])
        with self.assertRaisesRegex(CheckFailure, "within 30 seconds"):
            qualification.refresh("concealed scene", lambda item: concealed(item["diagnostics"]))
        self.assertEqual(qualification.device.taps, ["refresh_diagnostics"] * 2)
        self.assertLessEqual(self.clock.now, 30.3)

    def test_distinct_pending_responses_have_a_finite_request_bound(self):
        observations = []
        value = host()
        for _ in range(runner.MAX_PENDING_DIAGNOSTIC_REFRESHES + 1):
            value = refreshed(value)
            value["diagnostics"]["sceneStateApplied"] = False
            observations.append(value)
        qualification = self.response_trace(host(), observations)
        with self.assertRaisesRegex(CheckFailure, "bounded diagnostic responses"):
            qualification.refresh("applied scene")
        self.assertEqual(qualification.device.taps,
                         ["refresh_diagnostics"] * (runner.MAX_PENDING_DIAGNOSTIC_REFRESHES + 1))
        self.assertLess(self.clock.now, 30)
        self.assertEqual(qualification.device.deadline, 60)

    def test_followup_cannot_reset_the_original_response_deadline(self):
        pending = refreshed()
        pending["diagnostics"]["sceneStateApplied"] = False
        applied = refreshed(pending)
        applied["diagnostics"]["sceneStateApplied"] = True
        qualification = self.response_trace(host(), [pending, applied])
        read_host = qualification.device.read_host

        def delayed_response(allow_missing=False):
            if len(qualification.device.taps) == 1:
                self.clock.sleep(29.8)
            return read_host(allow_missing)

        qualification.device.read_host = delayed_response
        budgets = []
        native_tap = qualification.device.native_tap

        def record_budget(tag, **kwargs):
            budgets.append((qualification.device.deadline, kwargs.get("seconds")))
            native_tap(tag, **kwargs)

        qualification.device.native_tap = record_budget
        with self.assertRaisesRegex(CheckFailure, "within 30 seconds"):
            qualification.refresh("applied scene")
        self.assertEqual(qualification.device.taps, ["refresh_diagnostics"] * 2)
        self.assertAlmostEqual(budgets[1][0], 30.1)
        self.assertLessEqual(budgets[1][1], 0.11)
        self.assertLessEqual(self.clock.now, 30.3)
        self.assertEqual(qualification.device.deadline, 60)

    def test_pending_response_at_expired_deadline_cannot_trigger_a_followup(self):
        pending = refreshed()
        pending["diagnostics"]["sceneStateApplied"] = False
        qualification = self.response_trace(host(), [pending])
        read_host = qualification.device.read_host

        def late_response(allow_missing=False):
            if qualification.device.taps:
                self.clock.sleep(30)
            return read_host(allow_missing)

        qualification.device.read_host = late_response
        with self.assertRaisesRegex(CheckFailure, "within 30 seconds"):
            qualification.refresh("applied scene")
        self.assertEqual(qualification.device.taps, ["refresh_diagnostics"])
        self.assertLessEqual(self.clock.now, 30.3)
        self.assertEqual(qualification.device.deadline, 60)

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

    def test_incomplete_live_warning_does_not_accept_host_state_until_context_arrives(self):
        qualification = self.qualification(host())
        qualification.engine_log = mock.Mock()
        qualification.engine_log.check.side_effect = (False, True)
        predicate = mock.Mock(return_value=True)
        qualification.wait_host("complete engine log", predicate)
        self.assertEqual(qualification.engine_log.check.call_count, 2)
        self.assertEqual(qualification.device.dump_count, 2)
        predicate.assert_called_once()
        self.assertEqual(qualification.device.taps, [])

    def test_missing_live_warning_context_cannot_extend_host_deadline(self):
        qualification = self.qualification(host())
        qualification.engine_log = mock.Mock()
        qualification.engine_log.check.return_value = False
        predicate = mock.Mock(return_value=True)
        with self.assertRaisesRegex(CheckFailure, "within 1 seconds"):
            qualification.wait_host("complete engine log", predicate, seconds=1)
        self.assertLessEqual(self.clock.now, 1.3)
        predicate.assert_not_called()
        self.assertEqual(qualification.device.taps, [])

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

    def lobby_exit(self, before, confirmation=None):
        last = confirmation or before
        final = final_host(last)
        final.update(closeReason="return_to_chooser", lastIntentType="return_to_lobby")
        for name in ("receivedEvents", "receivedIntents", "acceptedIntents"):
            final[name] = str(int(last[name]) + 1)
        qualification = self.qualification(final)
        qualification.device.final_only = True
        qualification.engine_log = mock.Mock()
        qualification.capture_native = mock.Mock()
        qualification.capture_scene = mock.Mock()
        qualification.tap_scene = mock.Mock(side_effect=[before] + ([confirmation] if confirmation else []))
        qualification.refresh = mock.Mock(return_value=confirmation)
        return qualification

    def test_finished_lobby_route_uses_pre_tap_phase_and_verifies_real_teardown(self):
        before = host()
        before["publicState"].update(phase="FINISHED", canPlay=False, winnerPresent=True,
                                     outcomeRoundNumber=1, truthful=False, burnedOut=True)
        qualification = self.lobby_exit(before)
        qualification.snapshot = host()  # Older cached phase cannot decide the route.
        qualification.return_to_chooser("2d")
        qualification.tap_scene.assert_called_once_with("lobby")
        qualification.refresh.assert_not_called()
        qualification.capture_scene.assert_not_called()
        receipt = json.loads((self.output / "teardown.json").read_text())
        self.assertEqual(receipt["host"]["closeReason"], "return_to_chooser")
        self.assertTrue(receipt["old_pid_absent"])

    def test_finished_lobby_cannot_pass_missing_intent_or_teardown_marker(self):
        before = host()
        before["publicState"].update(phase="FINISHED", canPlay=False, winnerPresent=True,
                                     outcomeRoundNumber=1, truthful=False, burnedOut=True)
        for field, wrong, error in (("acceptedIntents", "0", "exactly one accepted native intent"),
                                    ("nativeDestroyReturned", False, "Missing actual native teardown marker")):
            with self.subTest(field=field):
                qualification = self.lobby_exit(before)
                qualification.device.after[field] = wrong
                with self.assertRaisesRegex(CheckFailure, error):
                    qualification.return_to_chooser("2d")

    def test_unfinished_lobby_preserves_confirmation_before_authority_exit(self):
        before = host()
        confirmation = refreshed(before)
        confirmation["diagnostics"]["controls"].append({
            "group": "partydeck_action_lobby_confirm", "cardIndex": -1,
            "rect": [100, 300, 300, 100], "clipRect": [0, 0, 720, 1200],
            "visible": True, "enabled": True, "selected": False,
        })
        qualification = self.lobby_exit(before, confirmation)
        qualification.snapshot = copy.deepcopy(before)
        qualification.snapshot["publicState"]["phase"] = "FINISHED"
        qualification.return_to_chooser("2d")
        self.assertEqual(qualification.tap_scene.call_args_list, [mock.call("lobby"), mock.call("lobby_confirm")])
        qualification.capture_scene.assert_called_once_with("13-lobby-confirmation", confirmation)
        predicate = qualification.refresh.call_args.args[1]
        self.assertTrue(predicate(confirmation))
        self.assertFalse(predicate(before))
        confirmation["diagnostics"]["controls"][-1]["visible"] = False
        self.assertFalse(predicate(confirmation))

    def test_unfinished_lobby_rejects_a_gameplay_event_while_opening_dialog(self):
        before = host()
        confirmation = refreshed(before)
        confirmation["receivedEvents"] = "2"
        qualification = self.lobby_exit(before, confirmation)
        with self.assertRaisesRegex(CheckFailure, "local hand interaction emitted an authority event"):
            qualification.return_to_chooser("2d")
        qualification.tap_scene.assert_called_once_with("lobby")
        qualification.capture_scene.assert_not_called()
        self.assertFalse((self.output / "teardown.json").exists())

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

    def test_oscillating_control_still_stops_at_the_original_scroll_bound(self):
        observations = []
        for attempt in range(runner.MAX_SCROLLS + 1):
            value = refreshed(observations[-1] if observations else host())
            value["diagnostics"]["controls"][0].update(
                rect=[20, 1150 if attempt % 2 == 0 else -150, 100, 200], enabled=True)
            observations.append(value)
        qualification = self.qualification(observations[0])
        qualification.refresh = mock.Mock(side_effect=observations)
        qualification.scene_input = mock.Mock()
        qualification.device.adb = mock.Mock()
        with self.assertRaisesRegex(CheckFailure, "remained clipped after the bounded real scroll sequence"):
            qualification.control("card", 0)
        self.assertEqual(qualification.device.adb.call_count, 16)
        for call in qualification.device.adb.call_args_list:
            self.assertEqual(call.args[:3], ("shell", "input", "swipe"))
            self.assertTrue(350 <= int(call.args[-1]) <= 1000)


class UiAcquisitionTest(unittest.TestCase):
    """Replay subprocess results through the real fresh rm/dump/read helpers."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = pathlib.Path(temporary.name)
        self.clock = Clock()
        self.enterContext(mock.patch.object(runner, "time", self.clock))
        self.enterContext(mock.patch.object(runner.baseline, "time", self.clock))
        self.device = runner.Device("no-device", self.output, "run-as")
        self.device.display_size = (720, 1600)
        self.device.deadline = 50
        self.device.stage = "2d match entry"
        old = ET.fromstring('<hierarchy><node resource-id="old" bounds="[0,0][100,100]" /></hierarchy>')
        self.old_node = old.find("node")
        self.device.bind_ui(old)
        self.device_xml = ET.tostring(old, encoding="unicode")
        self.fresh = '<hierarchy><node resource-id="fresh" bounds="[0,0][100,100]" /></hierarchy>'
        self.events, self.commands = ["missing", self.fresh], []
        self.enterContext(mock.patch.object(runner.subprocess, "run", self.process))

    def process(self, command, **options):
        arguments = tuple(command[3:])
        timeout = options["timeout"]
        error_output = ""
        self.commands.append((arguments, self.clock.now, timeout))
        self.clock.sleep(min(0.02, timeout))
        if timeout < 0.02:
            raise subprocess.TimeoutExpired(command, timeout)
        if arguments == ("shell", "rm", "-f", "/sdcard/partydeck-ci-ui.xml"):
            self.device_xml, value = None, ""
        elif arguments == ("shell", "uiautomator", "dump", "/sdcard/partydeck-ci-ui.xml"):
            self.assertIsNone(self.device_xml, "A previous device XML must be deleted before every attempt")
            event = self.events.pop(0) if len(self.events) > 1 else self.events[0]
            if isinstance(event, Exception):
                raise event
            if isinstance(event, subprocess.CompletedProcess):
                return event
            self.device_xml = None if event == "missing" else event
            value = "" if event == "missing" else "UI hierchary dumped to: /sdcard/partydeck-ci-ui.xml\n"
            if event == "missing":
                error_output = "Synthetic transient UI dump returned no XML.\n"
        elif arguments == ("shell", "cat", "/sdcard/partydeck-ci-ui.xml"):
            if self.device_xml is None:
                raise subprocess.CalledProcessError(1, command, output="", stderr="cat: /sdcard/partydeck-ci-ui.xml: No such file or directory\n")
            value = self.device_xml
        else:
            self.fail("Unexpected device command: " + str(arguments))
        return subprocess.CompletedProcess(command, 0, value, error_output)

    def test_missing_dump_retries_fresh_and_retains_failure_after_later_success(self):
        root = self.device.check_ui(deadline=10)
        self.assertIsNotNone(self.device.find(root, "fresh"))
        self.assertFalse(self.device.visible(self.old_node))
        path = self.output / "ui-dump-failures.log"
        failures = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["returncode"], 1)
        self.assertIn("No such file", failures[0]["stderr"])
        self.assertEqual(failures[0]["dump_returncode"], 0)
        self.assertEqual(failures[0]["dump_stdout"], "")
        self.assertEqual(failures[0]["dump_stderr"], "Synthetic transient UI dump returned no XML.\n")
        self.device.dump_ui(deadline=10)  # Later final diagnostics must not erase the failed attempt.
        self.assertEqual(failures, [json.loads(line) for line in path.read_text().splitlines()])
        self.assertIn("UI hierchary dumped", (self.output / "last-ui-dump.log").read_text())
        self.assertEqual(3, sum(args[:2] == ("shell", "rm") for args, _, _ in self.commands))

    def test_unavailable_ui_expires_at_enclosing_deadline_without_using_old_tree(self):
        self.events = ["missing"]
        self.device.deadline = 0.65
        with self.assertRaisesRegex(CheckFailure, "fresh crash-checked Android UI.*existing deadline"):
            self.device.check_ui(deadline=10)
        self.assertLessEqual(self.clock.now, 0.65)
        self.assertGreaterEqual(self.device.ui_dump_attempts, 2)
        self.assertIsNone(self.device.ui_root)
        self.assertFalse(self.device.visible(self.old_node))
        for _, started, timeout in self.commands:
            self.assertLessEqual(started + timeout, 0.650000001)
        self.assertFalse((self.output / "last-ui.xml").exists())

    def test_crash_after_transient_failure_is_rejected_without_another_retry(self):
        crash = '<hierarchy><node resource-id="android:id/aerr_wait" /></hierarchy>'
        self.events = ["missing", crash, self.fresh]
        with self.assertRaisesRegex(RuntimeError, "crash/ANR"):
            self.device.check_ui(deadline=10)
        self.assertEqual(self.device.ui_dump_attempts, 2)
        self.assertEqual(self.events, [self.fresh])

    def test_malformed_dump_does_not_bind_or_reuse_previous_geometry(self):
        self.events = ["<hierarchy>", self.fresh]
        root = self.device.check_ui(deadline=10)
        self.assertIsNotNone(self.device.find(root, "fresh"))
        failure = json.loads((self.output / "ui-dump-failures.log").read_text())
        self.assertEqual(failure["error_type"], "ParseError")
        self.assertFalse(self.device.visible(self.old_node))

    def test_timeout_output_is_retained_and_does_not_reuse_prior_dump_stdout(self):
        (self.output / "last-ui-dump.log").write_text("Earlier successful dump")
        self.events = [subprocess.TimeoutExpired("uiautomator", 1, output=b"partial stdout", stderr=b"partial stderr"), self.fresh]
        self.device.check_ui(deadline=10)
        failure = json.loads((self.output / "ui-dump-failures.log").read_text())
        self.assertEqual(failure["error_type"], "TimeoutExpired")
        self.assertEqual(failure["stdout"], "partial stdout")
        self.assertEqual(failure["stderr"], "partial stderr")
        self.assertIsNone(failure["dump_stdout"])

    def test_nonzero_dump_preserves_both_streams_before_a_fresh_retry(self):
        self.events = [subprocess.CompletedProcess("uiautomator", 1, "partial dump", "dump failed"), self.fresh]
        root = self.device.check_ui(deadline=10)
        self.assertIsNotNone(self.device.find(root, "fresh"))
        failure = json.loads((self.output / "ui-dump-failures.log").read_text())
        self.assertEqual(failure["returncode"], 1)
        self.assertEqual(failure["dump_returncode"], 1)
        self.assertEqual(failure["dump_stdout"], "partial dump")
        self.assertEqual(failure["dump_stderr"], "dump failed")
        self.assertEqual(1, sum(args[:2] == ("shell", "cat") for args, _, _ in self.commands))


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

    def test_verified_cache_warning_remains_in_live_and_final_log_evidence(self):
        header, location = CACHE_WARNING.splitlines(keepends=True)
        interleaved = header + "09-10 03:34:52.733  3074  3102 I Godot   : Frame delivery\n" + location
        self.assertTrue(runner.EngineLog.inspect(interleaved))
        with tempfile.TemporaryDirectory() as directory:
            log = object.__new__(runner.EngineLog)
            log.path, log.errors = pathlib.Path(directory) / "log", pathlib.Path(directory) / "errors"
            log.output, log.error_output = log.path.open("wb"), log.errors.open("wb")
            log.output.write(CACHE_WARNING.encode())
            log.output.flush()
            log.process, log.device, log.pid = mock.Mock(), mock.Mock(), 3074
            log.process.poll.return_value = None
            log.device.adb.return_value = CACHE_WARNING
            self.assertTrue(log.check())
            log.close()
            self.assertEqual(log.path.read_text(), CACHE_WARNING)
            self.assertEqual(log.path.with_name("final-process-logcat.log").read_text(), CACHE_WARNING)

    def test_cache_warning_does_not_hide_compilation_unknown_error_crash_or_timeout(self):
        header, location = CACHE_WARNING.splitlines(keepends=True)
        for error in (
            "09-10 03:34:52.733  3074  3111 E godot : ERROR: Fragment shader compilation failed.\n",
            "09-10 03:34:52.733  3074  3111 E godot : ERROR: Program linking failed.\n",
            "godot: SHADER ERROR: Invalid shader source\n",
            "09-10 03:34:52.733  3074  3111 E godot : WARNING: An unverified warning.\n",
            "09-10 03:34:52.733  3074  3111 E godot : Unknown engine failure\n",
            "09-10 03:34:52.733  3074  3111 E Godot : Unknown native failure\n",
            "AndroidRuntime: FATAL EXCEPTION: main\n",
            "libc: Fatal signal 11\n",
            "godot: SCRIPT ERROR: Invalid call\n",
            "Godot: Unable to exit the renderer within 1500 ms... Force quitting the process.\n",
        ):
            with self.subTest(error=error), self.assertRaises(CheckFailure):
                runner.EngineLog.inspect(header + error + location)

    def test_cache_warning_exception_requires_exact_paired_thread_and_source(self):
        header, location = CACHE_WARNING.splitlines(keepends=True)
        for invalid in (
            header, location, header + header + location,
            header + location.replace("  3074 ", "  3075 "),
            header + location.replace("  3111 ", "  3112 "),
            header + location.replace(".cpp:615", ".cpp:616"),
            header + location.replace("_load_from_cache", "_compile_specialization"),
            header.replace("recompiling.", "recompiling. Unexpected failure") + location,
            CACHE_WARNING.replace("E godot", "E Godot"),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(CheckFailure):
                runner.EngineLog.inspect(invalid)

    def test_partial_live_warning_waits_but_final_inspection_requires_complete_context(self):
        header, location = CACHE_WARNING.splitlines(keepends=True)
        for prefix in (header[:60], header, header + location[:80]):
            with self.subTest(prefix=prefix):
                self.assertFalse(runner.EngineLog.inspect(prefix, complete=False))
        self.assertTrue(runner.EngineLog.inspect(CACHE_WARNING, complete=False))
        with self.assertRaisesRegex(CheckFailure, "Incomplete shader-cache warning source context"):
            runner.EngineLog.inspect(header)
        with self.assertRaises(CheckFailure):
            runner.EngineLog.inspect(header + location[:80])
        with self.assertRaises(CheckFailure):
            runner.EngineLog.inspect(header + "09-10 03:34:52.733  3074  3111 E godot : Unknown error\n", complete=False)

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
            qualification.collect_failure_state.return_value = []
            qualification.collect_failure_logs.return_value = []
            order = []
            qualification.collect_failure_state.side_effect = lambda phase: order.append(phase) or []
            qualification.collect_failure_logs.side_effect = lambda: order.append("late_pid_logs") or []
            def failed_diagnostics():
                order.append("final_diagnostics")
                raise RuntimeError("diagnostic collection failed")
            device.diagnostics.side_effect = failed_diagnostics
            device.restore_environment.side_effect = lambda: order.append("restore") or []
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
            self.assertEqual(order, ["before_final_diagnostics", "final_diagnostics", "after_final_diagnostics", "late_pid_logs", "restore"])

    def test_entry_failure_retains_validated_host_and_late_log_after_observed_pid_dies(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            device = runner.Device("no-device", output, "run-as")
            failed = final_host()
            failed["failureCode"] = "renderer_ready_timeout"
            device.command = mock.Mock(side_effect=(
                subprocess.CompletedProcess([], 0, "1234\n", ""),
                subprocess.CompletedProcess([], 0, json.dumps(host()), ""),
                subprocess.CompletedProcess([], 1, "", ""),
                subprocess.CompletedProcess([], 0, json.dumps(failed), ""),
            ))
            device.adb = mock.Mock(return_value="Godot: Unable to exit the renderer within 1500 ms... Force quitting the process.")
            qualification = runner.Qualification(device, output)
            self.assertIsNone(qualification.trace)
            self.assertEqual(qualification.collect_failure_state("before_final_diagnostics"), [])
            self.assertEqual(qualification.collect_failure_state("after_final_diagnostics"), [])
            errors = qualification.collect_failure_logs()
            self.assertTrue(any("timed out exiting its renderer" in error for error in errors))
            observations = [json.loads(line) for line in (output / "failure-host-observations.log").read_text().splitlines()]
            self.assertEqual(observations[0]["engine_pids"], [1234])
            self.assertEqual(observations[1]["engine_pids"], [])
            self.assertEqual(observations[1]["host"]["failureCode"], "renderer_ready_timeout")
            self.assertIn("Unable to exit", (output / "failure-process-1234-logcat.log").read_text())
            device.adb.assert_called_once_with("logcat", "-d", "-v", "threadtime", "-b", "main", "-b", "system",
                                               "-b", "crash", "--pid", "1234", timeout=20)

    def test_failure_collection_rejects_private_fields_before_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            device = runner.Device("no-device", output, "run-as")
            private = host()
            private["privateHand"] = ["sentinel-card-secret"]
            device.command = mock.Mock(side_effect=(
                subprocess.CompletedProcess([], 0, "1234\n", ""),
                subprocess.CompletedProcess([], 0, json.dumps(private), ""),
            ))
            qualification = runner.Qualification(device, output)
            self.assertTrue(qualification.collect_failure_state("after_final_diagnostics"))
            retained = (output / "failure-host-observations.log").read_text()
            self.assertNotIn("sentinel-card-secret", retained)
            self.assertNotIn("host", json.loads(retained))
            self.assertIn("host_error", json.loads(retained))

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
