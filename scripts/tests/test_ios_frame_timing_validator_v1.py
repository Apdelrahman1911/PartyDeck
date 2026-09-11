"""Host-only behavior tests using independently constructed synthetic values."""
from copy import deepcopy
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ios_frame_timing_validator_v1 as validator
import ios_timing_fixtures as fixtures


class TimingValidationTests(unittest.TestCase):
    def validate(self, value, **kwargs):
        return validator.validate_attachment(fixtures.encoded(value), "2d", fixtures.source_name(), **kwargs)

    def rejected(self, value, code=None):
        with self.assertRaises(validator.ValidationError) as caught:
            self.validate(value)
        self.assertIn(caught.exception.code, validator.CODES)
        self.assertEqual(str(caught.exception), caught.exception.code)
        if code is not None:
            self.assertEqual(caught.exception.code, code)

    def test_full_wrapper_and_release_association(self):
        value = fixtures.baseline()
        before = deepcopy(value)
        report = self.validate(value)
        self.assertTrue(report["timingStructureValidated"])
        self.assertTrue(report["completedReleaseDrawRecorded"])
        self.assertTrue(report["releaseAssociatedIterationRecorded"])
        self.assertTrue(report["attachmentContext"]["liveAttachmentPredicatesSatisfied"])
        self.assertTrue(report["attachmentContext"]["concealedRendererPredicateSatisfied"])
        self.assertTrue(report["attachmentContext"]["attachmentGeometryAgrees"])
        self.assertEqual(value, before)

    def test_3d_wrapper(self):
        report = validator.validate_attachment(fixtures.encoded(fixtures.baseline("3d")), "3d", fixtures.source_name("3d"))
        self.assertEqual(report["mode"], "3d")

    def test_equal_slow_recurrence_overwrites_without_new_maximum(self):
        report = self.validate(fixtures.recurrence(), previous_payload=fixtures.encoded(fixtures.baseline()),
                               previous_source_name=fixtures.source_name())
        self.assertEqual(report["stages"]["draw"]["slowCompletedCount"], "5")
        self.assertEqual(report["stages"]["draw"]["overwrittenCount"], "1")
        self.assertEqual(report["stages"]["draw"]["maximumSeconds"], 1)
        self.assertEqual(len(report["stages"]["draw"]["retainedSlowSampleContexts"]), 4)
        self.assertEqual(report["comparison"], "same_process_monotonic")
        self.assertTrue(report["observationSequenceAdvanced"])

    def test_nested_start_ordinals_can_reverse_at_completion(self):
        value = fixtures.nested()
        self.assertEqual([s["scopeOrdinal"] for s in fixtures.timing(value)["draw"]["slowSamples"]], ["8", "7"])
        self.validate(value)

    def test_ring_cannot_be_sorted_by_scope_start_ordinal(self):
        value = fixtures.nested()
        fixtures.timing(value)["draw"]["slowSamples"].reverse()
        self.rejected(value, "TIMING_ORDER")

    def test_old_and_mixed_generations_stay_historical(self):
        report = self.validate(fixtures.mixed_generation())
        self.assertEqual(report["stages"]["draw"]["maximumContext"], "historical_or_mixed_generations")
        self.assertEqual(report["stages"]["iterate"]["lastContext"], "historical_or_mixed_generations")
        self.assertFalse(report["stableActivityIntervalQualified"])

    def test_in_flight_durations_are_unknown(self):
        report = self.validate(fixtures.in_flight())
        for stage in report["stages"].values():
            self.assertIsNone(stage["lastSeconds"])
            self.assertIsNone(stage["maximumSeconds"])
        self.assertFalse(report["completedReleaseDrawRecorded"])

    def test_missing_required_nullable_fields(self):
        for key in ("readyConfirmed", "firstNativeCoverRelease", "firstNativeReleaseDraw", "lastIterationInReleaseDraw"):
            value = fixtures.baseline()
            del fixtures.timing(value)[key]
            with self.subTest(key=key):
                self.rejected(value, "TIMING_SHAPE")
        for key in ("last", "maximum"):
            value = fixtures.in_flight()
            del fixtures.timing(value)["draw"][key]
            with self.subTest(key=key):
                self.rejected(value, "TIMING_SHAPE")

    def test_missing_added_wrapper_fields(self):
        for key in ("frameTiming", "frameTimingStatus", "jointVisibility"):
            value = fixtures.baseline()
            owner = value["port"] if key == "jointVisibility" else value["port"]["native"]
            del owner[key]
            with self.subTest(key=key):
                self.rejected(value, "TIMING_REQUIRED")

    def test_null_associations_are_not_absent_work(self):
        value = fixtures.baseline()
        fixtures.timing(value)["firstNativeReleaseDraw"] = None
        fixtures.timing(value)["lastIterationInReleaseDraw"] = None
        report = self.validate(value)
        self.assertFalse(report["completedReleaseDrawRecorded"])
        self.assertFalse(report["releaseAssociatedIterationRecorded"])
        self.assertEqual(report["firstNativeCoverReleaseUptime"], 101)

    def test_release_iteration_can_precede_later_global_iterations(self):
        value = fixtures.recurrence()
        self.assertNotEqual(fixtures.timing(value)["lastIterationInReleaseDraw"], fixtures.timing(value)["iterate"]["last"])
        self.assertTrue(self.validate(value)["releaseAssociatedIterationRecorded"])

    def test_omitted_and_invalid_traces_rejected(self):
        for status in ("payload_budget", "invalid", "available"):
            value = fixtures.baseline()
            value["port"]["native"].update(frameTimingStatus=status, frameTiming=None)
            if status == "invalid":
                value["port"]["jointVisibility"] = None
            with self.subTest(status=status):
                self.rejected(value, "TIMING_SHAPE" if status == "available" else "TIMING_UNAVAILABLE")
        value = fixtures.baseline()
        value["port"]["native"] = None
        value["port"]["jointVisibility"] = None
        self.rejected(value, "TIMING_UNAVAILABLE")

    def test_status_payload_pairing(self):
        value = fixtures.baseline()
        value["port"]["native"]["frameTimingStatus"] = "payload_budget"
        self.rejected(value, "TIMING_SHAPE")
        value["port"]["native"].update(frameTimingStatus="invalid", frameTiming=None)
        self.rejected(value, "TIMING_SHAPE")

    def test_byte_budget_applies_to_original_bytes(self):
        data = fixtures.encoded(fixtures.baseline())
        bounded = data + b" " * (validator.MAX_BYTES - len(data))
        validator.validate_attachment(bounded, "2d", fixtures.source_name())
        with self.assertRaises(validator.ValidationError) as error:
            validator.validate_attachment(bounded + b" ", "2d", fixtures.source_name())
        self.assertEqual(error.exception.code, "INPUT_BYTES")

    def test_utf8_duplicate_keys_and_non_json_numbers_fail_safely(self):
        payloads = [b"\xff", b'{"private sentinel":1,"private sentinel":2}', b'{"private sentinel":NaN}',
                    b"[" * 1000 + b"]" * 1000, b"null", b"true", b""]
        for data in payloads:
            with self.subTest(payload_length=len(data)):
                with self.assertRaises(validator.ValidationError) as error:
                    validator.validate_attachment(data, "2d", fixtures.source_name())
                self.assertNotIn("private sentinel", str(error.exception))

    def test_unnamed_or_wrong_kind_or_mode_is_not_decoded(self):
        for name in ("opaque snapshot", "2d production concealed entry", "3d production concealed entry latest sanitized observation",
                     "3d round 1 actual body scroll coverage"):
            with self.subTest(name=name):
                with self.assertRaises(validator.ValidationError) as error:
                    validator.validate_attachment(b"not JSON", "2d", name)
                self.assertEqual(error.exception.code, "SOURCE_LABEL")

    def test_extra_private_field_cannot_be_projected_away(self):
        for location in ("wrapper", "controller", "native", "frame", "sample"):
            value = fixtures.baseline()
            targets = {"wrapper": value, "controller": value["controller"], "native": value["port"]["native"],
                       "frame": fixtures.timing(value), "sample": fixtures.timing(value)["draw"]["last"]}
            targets[location]["PRIVATE_SENTINEL"] = "sensitive rejected content"
            with self.subTest(location=location):
                self.rejected(value)

    def test_existing_authority_health_checks_remain(self):
        cases = (("controller", "supported", False), ("controller", "exhausted", True),
                 ("port", "activationValid", False), ("native", "nativeFailedPresentations", 1),
                 ("native", "rejectedEvents", 1), ("native", "quarantined", True))
        for location, key, setting in cases:
            value = fixtures.baseline()
            target = value["port"]["native"] if location == "native" else value[location]
            target[key] = setting
            with self.subTest(field=key):
                self.rejected(value, "BASE_SCHEMA")

    def test_live_context_requires_controller_and_renderer_revisions(self):
        for location, field, setting in (("controller", "foreground", False), ("controller", "sessionRevision", None),
                                         ("renderer", "revision", "8"), ("renderer", "sceneStateApplied", False)):
            value = fixtures.baseline()
            target = value["controller"] if location == "controller" else value["port"]["renderer"]
            target[field] = setting
            with self.subTest(field=field):
                self.assertFalse(self.validate(value)["attachmentContext"]["liveAttachmentPredicatesSatisfied"])

    def test_geometry_and_privacy_predicates_are_preserved_separately(self):
        value = fixtures.baseline()
        value["port"]["geometry"]["bounds"][2] = 300
        self.assertFalse(self.validate(value)["attachmentContext"]["attachmentGeometryAgrees"])
        value["port"]["renderer"]["privateFaceCount"] = 1
        self.assertFalse(self.validate(value)["attachmentContext"]["concealedRendererPredicateSatisfied"])

    def test_booleans_cannot_be_numbers(self):
        for key in ("schemaVersion", "sampleCapacity", "snapshotUptime", "slowThresholdSeconds"):
            value = fixtures.baseline()
            fixtures.timing(value)[key] = True
            with self.subTest(key=key):
                self.rejected(value)
        value = fixtures.baseline()
        fixtures.timing(value)["draw"]["last"]["seconds"] = True
        self.rejected(value, "TIMING_NUMBER")
        value = fixtures.baseline()
        fixtures.timing(value)["draw"]["last"]["begin"][7] = True
        self.rejected(value, "TIMING_FLAGS")

    def test_flags_and_context_shape_are_bounded(self):
        for flags in (-1, 512, 399.0, "399"):
            value = fixtures.baseline()
            fixtures.timing(value)["draw"]["last"]["begin"][7] = flags
            with self.subTest(flags=flags):
                self.rejected(value, "TIMING_FLAGS")
        value = fixtures.baseline()
        fixtures.timing(value)["draw"]["last"]["begin"].append("0")
        self.rejected(value, "TIMING_SHAPE")

    def test_boolean_fields_must_be_actual_booleans(self):
        for location in ("counterExhausted", "bothCoversClear", "outerCoverVisible"):
            value = fixtures.baseline()
            target = fixtures.timing(value)["draw"] if location == "counterExhausted" else value["port"]["jointVisibility"]
            if location == "outerCoverVisible":
                target = target["shell"]
            target[location] = 0
            with self.subTest(location=location):
                self.rejected(value, "TIMING_SHAPE")

    def test_uint64_canonical_counter_grammar(self):
        for counter in (True, 1, "", "01", "+1", "-1", "1.0", "1e1", " 1", "1\n", "\u0661", "18446744073709551616"):
            value = fixtures.baseline()
            fixtures.timing(value)["draw"]["startedCount"] = counter
            with self.subTest(counter=repr(counter)):
                self.rejected(value, "TIMING_COUNTER")

    def test_uint64_exact_upper_bound_is_accepted_without_overflow(self):
        value = fixtures.in_flight()
        fixtures.timing(value)["draw"]["startedCount"] = "18446744073709551615"
        self.assertEqual(self.validate(value)["stages"]["draw"]["startedCount"], "18446744073709551615")

    def test_counter_arithmetic_invalid_clocks_and_exhaustion(self):
        for key, bad in (("startedCount", "7"), ("completedCount", "9"), ("slowCompletedCount", "9"),
                         ("overwrittenCount", "1"), ("invalidCompletedCount", "1"), ("counterExhausted", True)):
            value = fixtures.baseline()
            fixtures.timing(value)["draw"][key] = bad
            with self.subTest(key=key):
                self.rejected(value, "TIMING_COUNTERS")

    def test_ring_capacity_and_retained_count(self):
        value = fixtures.recurrence()
        fixtures.timing(value)["draw"]["slowSamples"].append(fixtures.timing(value)["draw"]["last"])
        self.rejected(value, "TIMING_SHAPE")
        value = fixtures.recurrence()
        fixtures.timing(value)["draw"]["slowSamples"].pop()
        self.rejected(value, "TIMING_COUNTERS")

    def test_completion_identity_and_chronology(self):
        for key, bad in (("completedOrdinal", "7"), ("scopeOrdinal", "7"), ("completedUptime", 99)):
            value = fixtures.baseline()
            fixtures.timing(value)["draw"]["last"][key] = bad
            with self.subTest(key=key):
                self.rejected(value)
        value = fixtures.recurrence()
        fixtures.timing(value)["draw"]["slowSamples"][1]["completedOrdinal"] = "9"
        self.rejected(value, "TIMING_ORDER")

    def test_equal_maximum_keeps_its_earliest_completion(self):
        value = fixtures.recurrence()
        fixtures.timing(value)["draw"]["maximum"] = deepcopy(fixtures.timing(value)["draw"]["last"])
        self.rejected(value, "TIMING_ORDER")

    def test_absolute_duration_tolerance_not_relative(self):
        value = fixtures.in_flight()
        fixtures.timing(value)["snapshotUptime"] = 1e12
        draw = fixtures.sample(1, 1, 0, 1e12, fixtures.context(1, 0, 0), fixtures.context(1, 0, 0), seconds=1e12 - 1)
        fixtures.timing(value)["draw"] = fixtures.stage(1, 1, draw, draw, 1, [draw])
        self.rejected(value, "TIMING_SAMPLE")
        for entry in (fixtures.timing(value)["draw"]["last"], fixtures.timing(value)["draw"]["maximum"],
                      *fixtures.timing(value)["draw"]["slowSamples"]):
            entry["seconds"] = 1e12
        self.validate(value)

    def test_nonfinite_negative_and_overflow_numbers(self):
        for raw in (b"1e400", b"-1", b"true"):
            data = fixtures.encoded(fixtures.baseline()).replace(b'"snapshotUptime":102', b'"snapshotUptime":' + raw, 1)
            with self.subTest(raw=raw):
                with self.assertRaises(validator.ValidationError) as error:
                    validator.validate_attachment(data, "2d", fixtures.source_name())
                self.assertEqual(error.exception.code, "TIMING_NUMBER")

    def test_future_context_and_frame_generations_rejected(self):
        value = fixtures.baseline()
        fixtures.timing(value)["presentationGeneration"] = "2"
        self.rejected(value, "TIMING_GENERATION")
        for index in (0, 1, 2, 3, 4, 5):
            value = fixtures.baseline()
            fixtures.timing(value)["draw"]["last"]["end"][index] = "999"
            with self.subTest(index=index):
                self.rejected(value, "TIMING_GENERATION")

    def test_old_markers_cannot_be_relabelled_current(self):
        value = fixtures.baseline()
        fixtures.timing(value)["readyConfirmed"]["context"][0] = "2"
        self.rejected(value, "TIMING_MARKER")

    def test_release_requires_ready_eligibility_and_progress(self):
        for key, bad in (("readyConfirmed", None),):
            value = fixtures.baseline()
            fixtures.timing(value)[key] = bad
            self.rejected(value, "TIMING_MARKER")
        for index, bad in ((7, 415), (3, "0"), (4, "0")):
            value = fixtures.baseline()
            fixtures.timing(value)["firstNativeCoverRelease"]["context"][index] = bad
            with self.subTest(index=index):
                self.rejected(value, "TIMING_MARKER")
        value = fixtures.baseline()
        fixtures.timing(value)["firstNativeCoverRelease"]["uptime"] = 98
        self.rejected(value, "TIMING_MARKER")

    def test_release_draw_must_own_and_enclose_release(self):
        value = fixtures.baseline()
        fixtures.timing(value)["firstNativeCoverRelease"]["context"][3] = "7"
        self.rejected(value, "TIMING_ASSOCIATION")
        value = fixtures.baseline()
        fixtures.timing(value)["firstNativeCoverRelease"]["uptime"] = 101.1
        self.rejected(value, "TIMING_ASSOCIATION")

    def test_iteration_context_precedes_runtime_increment(self):
        value = fixtures.baseline()
        fixtures.timing(value)["firstNativeCoverRelease"]["context"][5] = "19"
        self.rejected(value, "TIMING_ASSOCIATION")

    def test_joint_samples_match_current_generations_and_flags(self):
        for key, bad in (("presentationGeneration", "2"), ("lifecycleGeneration", "3"), ("inputGeneration", "4"),
                         ("nativeSnapshotUptime", 101), ("nativeCoverVisible", True), ("bothCoversClear", False)):
            value = fixtures.baseline()
            value["port"]["jointVisibility"][key] = bad
            with self.subTest(key=key):
                self.rejected(value, "TIMING_JOINT")

    def test_joint_requires_attached_foreground_ready_native(self):
        for key, bad in (("surfaceAttached", False), ("nativeForeground", False), ("authorityReadyConfirmed", False),
                         ("applicationBackgrounded", True), ("dormant", True), ("emptyTree", True)):
            value = fixtures.baseline()
            value["port"]["native"][key] = bad
            with self.subTest(key=key):
                self.rejected(value, "TIMING_JOINT")

    def test_shell_transitions_and_sequential_clocks(self):
        for key, bad in (("snapshotUptime", 101), ("coverTransitions", "2"), ("counterExhausted", True),
                         ("firstReleaseUptime", None), ("lastTransitionUptime", 100)):
            value = fixtures.baseline()
            value["port"]["jointVisibility"]["shell"][key] = bad
            with self.subTest(key=key):
                self.rejected(value, "TIMING_JOINT")
        value = fixtures.baseline()
        shell = value["port"]["jointVisibility"]["shell"]
        shell.update(coverTransitions="0", outerCoverVisible=True, firstReleaseUptime=None, lastTransitionUptime=None)
        value["port"]["geometry"]["outerCoverVisible"] = True
        value["port"]["jointVisibility"]["bothCoversClear"] = False
        self.assertFalse(self.validate(value)["jointCoversClear"])

    def test_repeat_observation_is_not_fresh_progress(self):
        value = fixtures.baseline()
        report = self.validate(value, previous_payload=fixtures.encoded(value), previous_source_name=fixtures.source_name())
        self.assertFalse(report["observationSequenceAdvanced"])
        self.assertFalse(report["stableActivityIntervalQualified"])

    def test_history_rejects_counter_regression_and_rewritten_marker(self):
        before = fixtures.baseline()
        value = fixtures.baseline()
        fixtures.timing(value)["readyConfirmed"]["uptime"] = 98
        with self.assertRaises(validator.ValidationError) as error:
            self.validate(value, previous_payload=fixtures.encoded(before), previous_source_name=fixtures.source_name())
        self.assertEqual(error.exception.code, "TIMING_HISTORY")
        # Keep sequence and clock advancing so only lifetime counters regress.
        before["observationSequence"] = "55"
        fixtures.timing(before)["snapshotUptime"] = 112
        before["port"]["jointVisibility"]["nativeSnapshotUptime"] = 112
        before["port"]["jointVisibility"]["shell"]["snapshotUptime"] = 112.01
        with self.assertRaises(validator.ValidationError) as error:
            self.validate(before, previous_payload=fixtures.encoded(fixtures.recurrence()), previous_source_name=fixtures.source_name())
        self.assertEqual(error.exception.code, "TIMING_HISTORY")

    def test_history_permits_current_generation_reset_but_keeps_old_samples(self):
        report = self.validate(fixtures.mixed_generation())
        self.assertFalse(report["stableActivityIntervalQualified"])
        value = fixtures.recurrence()
        value["port"]["native"]["presentationGeneration"] = "4"
        fixtures.timing(value)["presentationGeneration"] = "4"
        fixtures.forget_markers(value)
        self.validate(value, previous_payload=fixtures.encoded(fixtures.baseline()), previous_source_name=fixtures.source_name())

    def test_history_native_lifetime_regression_even_with_older_retained_context(self):
        for key, high, low in (("lifecycleGeneration", "5", "4"), ("inputGeneration", "6", "5"),
                               ("nativePresentedFrames", 11, 10), ("iterations", 21, 20), ("drawCalls", 9, 8)):
            before = fixtures.baseline()
            before["port"]["native"][key] = high
            if key in ("lifecycleGeneration", "inputGeneration"):
                before["port"]["jointVisibility"][key] = high
            after = deepcopy(before)
            after["observationSequence"] = "51"
            after["port"]["native"][key] = low
            if key in ("lifecycleGeneration", "inputGeneration"):
                after["port"]["jointVisibility"][key] = low
            with self.subTest(counter=key):
                self.validate(before)
                self.validate(after)
                with self.assertRaises(validator.ValidationError) as error:
                    self.validate(after, previous_payload=fixtures.encoded(before), previous_source_name=fixtures.source_name())
                self.assertEqual(error.exception.code, "TIMING_HISTORY")

    def test_history_slow_count_cannot_grow_without_a_completion(self):
        before = fixtures.recurrence()
        frame = fixtures.timing(before)
        tail = fixtures.sample(16, 16, 116, 116.2, fixtures.context(16, 14, 24), fixtures.context(16, 14, 24))
        frame["draw"].update(startedCount="16", completedCount="16", last=tail)
        frame["snapshotUptime"] = 117
        before["port"]["native"].update(drawCalls=16)
        before["port"]["jointVisibility"] = None
        after = deepcopy(before)
        after["observationSequence"] = "55"
        forged = fixtures.sample(13, 13, 110, 111, fixtures.context(13, 14, 24), fixtures.context(13, 14, 24))
        stage = fixtures.timing(after)["draw"]
        stage.update(slowCompletedCount="6", overwrittenCount="2", slowSamples=stage["slowSamples"][1:] + [forged])
        self.validate(before)
        self.validate(after)
        with self.assertRaises(validator.ValidationError) as error:
            self.validate(after, previous_payload=fixtures.encoded(before), previous_source_name=fixtures.source_name())
        self.assertEqual(error.exception.code, "TIMING_HISTORY")

    def test_history_ring_surviving_suffix_and_legitimate_advance(self):
        before = fixtures.recurrence()
        after = deepcopy(before)
        after["observationSequence"] = "55"
        after["port"]["jointVisibility"] = None
        after["port"]["native"].update(nativePresentedFrames=15, iterations=25, drawCalls=13)
        frame = fixtures.timing(after)
        frame["snapshotUptime"] = 112
        new_draw = fixtures.sample(13, 13, 110, 111, fixtures.context(13, 14, 24), fixtures.context(13, 15, 25))
        old_stage = frame["draw"]
        frame["draw"] = fixtures.stage(13, 13, new_draw, old_stage["maximum"], 6, old_stage["slowSamples"][1:] + [new_draw])
        new_iteration = fixtures.sample(25, 25, 110.2, 110.8, fixtures.context(13, 14, 24), fixtures.context(13, 14, 24), seconds=0.6)
        frame["iterate"] = fixtures.stage(25, 25, new_iteration, frame["iterate"]["maximum"])
        self.validate(after, previous_payload=fixtures.encoded(before), previous_source_name=fixtures.source_name())
        # Both rings are individually chronological, but an older survivor
        # cannot replace the actual oldest surviving sample after one append.
        frame["draw"]["slowSamples"][0] = deepcopy(fixtures.timing(before)["draw"]["slowSamples"][0])
        self.validate(after)
        with self.assertRaises(validator.ValidationError) as error:
            self.validate(after, previous_payload=fixtures.encoded(before), previous_source_name=fixtures.source_name())
        self.assertEqual(error.exception.code, "TIMING_HISTORY")

    def test_history_shell_snapshot_and_transition_stability(self):
        before = fixtures.baseline()
        for key, bad in (("snapshotUptime", 102.005), ("lastTransitionUptime", 101.3)):
            after = deepcopy(before)
            after["observationSequence"] = "51"
            after["port"]["jointVisibility"]["shell"][key] = bad
            with self.subTest(field=key):
                self.validate(after)
                with self.assertRaises(validator.ValidationError) as error:
                    self.validate(after, previous_payload=fixtures.encoded(before), previous_source_name=fixtures.source_name())
                self.assertEqual(error.exception.code, "TIMING_HISTORY")

    def test_history_shell_can_transition_twice_between_clear_samples(self):
        before = fixtures.baseline()
        after = deepcopy(before)
        after["observationSequence"] = "51"
        fixtures.timing(after)["snapshotUptime"] = 104
        joint = after["port"]["jointVisibility"]
        joint["nativeSnapshotUptime"] = 104
        joint["shell"].update(snapshotUptime=104.01, coverTransitions="3", lastTransitionUptime=103)
        report = self.validate(after, previous_payload=fixtures.encoded(before), previous_source_name=fixtures.source_name())
        self.assertTrue(report["jointCoversClear"])
        self.assertFalse(report["stableActivityIntervalQualified"])

    def test_history_newly_recorded_work_cannot_predate_previous_snapshot(self):
        for snapshot in (102.5, 103.5):
            before = fixtures.baseline()
            fixtures.timing(before)["snapshotUptime"] = snapshot
            before["port"]["jointVisibility"] = None
            after = fixtures.recurrence()
            # The first new scope starts at 102 and ends at 103. A previous
            # snapshot after either boundary cannot still have count eight.
            self.validate(before)
            self.validate(after)
            with self.subTest(snapshot=snapshot):
                with self.assertRaises(validator.ValidationError) as error:
                    self.validate(after, previous_payload=fixtures.encoded(before), previous_source_name=fixtures.source_name())
                self.assertEqual(error.exception.code, "TIMING_HISTORY")

    def test_history_an_already_started_outer_scope_can_complete_later(self):
        after = fixtures.nested()
        before = deepcopy(after)
        inner = deepcopy(fixtures.timing(before)["draw"]["slowSamples"][0])
        fixtures.timing(before)["draw"] = fixtures.stage(8, 7, inner, inner, 1, [inner])
        fixtures.timing(before)["snapshotUptime"] = 102.5
        after["observationSequence"] = "51"
        self.validate(before)
        report = self.validate(after, previous_payload=fixtures.encoded(before), previous_source_name=fixtures.source_name())
        self.assertEqual(report["stages"]["draw"]["completedCount"], "8")
        self.assertEqual(report["comparison"], "same_process_monotonic")

    def test_previous_attachment_requires_its_own_named_source(self):
        with self.assertRaises(validator.ValidationError) as error:
            self.validate(fixtures.baseline(), previous_payload=fixtures.encoded(fixtures.baseline()))
        self.assertEqual(error.exception.code, "SOURCE_LABEL")

    def test_cli_errors_are_fixed_and_do_not_echo_bad_paths_or_options(self):
        for args in (["PRIVATE_SENTINEL", "--mode", "2d", "--source-name", fixtures.source_name()],
                     ["--PRIVATE_SENTINEL"]):
            output = io.StringIO()
            with redirect_stdout(output):
                result = validator.main(args)
            self.assertEqual(result, 2)
            data = json.loads(output.getvalue())
            self.assertFalse(data["ok"])
            self.assertNotIn("PRIVATE_SENTINEL", output.getvalue())

    def test_every_valid_fixture_keeps_acceptance_limits(self):
        for name, factory in fixtures.FIXTURES.items():
            with self.subTest(name=name):
                report = self.validate(factory())
                for key in ("performanceAccepted", "firstDisplayEstablished", "nativeAcceptance", "stableActivityIntervalQualified"):
                    self.assertFalse(report[key])
                self.assertFalse(report["attachmentContext"]["externalApplicationFrameVerified"])


class PhaseValidationTests(unittest.TestCase):
    def validate(self, value, previous=None):
        return validator.validate_attachment(fixtures.encoded(value), "2d", fixtures.source_name(),
            previous_payload=None if previous is None else fixtures.encoded(previous),
            previous_source_name=None if previous is None else fixtures.source_name())

    def rejected(self, value, code=None):
        with self.assertRaises(validator.ValidationError) as caught:
            self.validate(value)
        self.assertIn(caught.exception.code, validator.CODES)
        self.assertEqual(str(caught.exception), caught.exception.code)
        if code is not None:
            self.assertEqual(caught.exception.code, code)

    def record(self, value, name="iterate"):
        return value["port"]["native"]["framePhases"][name][0]

    def test_exact_join_keeps_context_timestamps_and_false_acceptance(self):
        value = fixtures.with_phases(fixtures.nested())
        before = deepcopy(value)
        report = self.validate(value)
        for name, records in report["joinedPhases"].items():
            for joined in records:
                sample, phases = joined["sample"], joined["phases"]
                self.assertEqual(sample["scopeOrdinal"], phases["scopeOrdinal"])
                self.assertEqual(sample["completedOrdinal"], phases["completedOrdinal"])
                self.assertIn("begin", sample); self.assertIn("end", sample)
                self.assertIn("startedUptime", sample); self.assertIn("completedUptime", sample)
        for key in ("stableActivityIntervalQualified", "performanceAccepted", "firstDisplayEstablished", "nativeAcceptance"):
            self.assertFalse(report[key])
        self.assertEqual(value, before)

    def test_absent_unavailable_and_budget_preserve_v1(self):
        baseline = fixtures.baseline()
        self.assertEqual(self.validate(baseline)["phaseStatus"], "absent")
        for status in ("unavailable", "invalid", "payload_budget"):
            value = deepcopy(baseline)
            value["port"]["native"].update(framePhasesStatus=status, framePhases=None)
            report = self.validate(value)
            self.assertEqual(report["phaseStatus"], status)
            self.assertIsNone(report["joinedPhases"])
            self.assertEqual(report["stages"], self.validate(baseline)["stages"])

    def test_zero_calls_skipped_pacing_and_exact_uint32_request(self):
        for mask in (1, 191, 255):
            value = fixtures.with_phases()
            record = self.record(value)
            record.update(seenMask=mask, seconds=[fixtures.timing(value)["iterate"]["last"]["seconds"]] + [0] * 7,
                          sleeps=[[0, "0", 0], [0, "0", 0]])
            self.validate(value)
        value = fixtures.with_phases()
        record = self.record(value)
        record["sleeps"] = [[1, str(2**32 - 1), 0], [1, "0", 0]]
        self.validate(value)  # requested vs actual must not be conflated

    def test_null_records_are_canonical_unknowns(self):
        for status in ("invalid", "unavailable"):
            value = fixtures.with_phases()
            self.record(value).update(status=status, seenMask=None, seconds=None, sleeps=None)
            self.validate(value)
            self.record(value)["seconds"] = [0] * 8
            self.rejected(value, "PHASE_SHAPE")

    def test_missing_duplicate_colliding_and_extra_joins(self):
        for change in ("missing", "duplicate", "scope", "completion", "extra"):
            value = fixtures.with_phases(fixtures.nested())
            records = value["port"]["native"]["framePhases"]["draw"]
            if change == "missing": records.pop()
            elif change == "duplicate": records.append(deepcopy(records[0]))
            elif change == "scope": records[0]["scopeOrdinal"] = "999"
            elif change == "completion": records[0]["completedOrdinal"] = records[1]["completedOrdinal"]
            else:
                records.append({**records[0], "scopeOrdinal": "999", "completedOrdinal": "999"})
            with self.subTest(change=change):
                self.rejected(value, "PHASE_JOIN")

    def test_vector_mask_sleep_bounds_and_types(self):
        mutations = [
            ("seenMask", 0), ("seenMask", 256), ("seenMask", True), ("seenMask", 127),
            ("seconds", [0] * 7), ("seconds", [1e308] * 8), ("seconds", [-1] + [0] * 7),
            ("seconds", [True] + [0] * 7), ("sleeps", [[2, "1", 0], [0, "0", 0]]),
            ("sleeps", [[True, "1", 0], [0, "0", 0]]),
            ("sleeps", [[1, str(2**32), 0], [0, "0", 0]]),
            ("sleeps", [[1, "01", 0], [0, "0", 0]]),
            ("sleeps", [[1, 1, 0], [0, "0", 0]]),
            ("sleeps", [[0, "1", 0], [0, "0", 0]]),
            ("sleeps", [[0, "0", 1], [0, "0", 0]]),
            ("sleeps", [[1, "1", 1], [0, "0", 0]]),
            ("sleeps", [[1, "1", -1], [0, "0", 0]]),
        ]
        for key, new in mutations:
            value = fixtures.with_phases()
            self.record(value)[key] = new
            with self.subTest(key=key, new=new):
                self.rejected(value)

    def test_unseen_phase_and_sleep_are_rejected(self):
        value = fixtures.with_phases()
        record = self.record(value)
        record["seenMask"] = 191
        self.rejected(value, "PHASE_BOUNDS")
        record["seconds"][2] += record["seconds"][6]; record["seconds"][6] = 0
        self.rejected(value, "PHASE_BOUNDS")  # remaining observed sleep without pacing
        value = fixtures.with_phases()
        self.record(value, "draw")["sleeps"] = [[0, "0", 0], [0, "0", 0]]
        self.rejected(value, "PHASE_SHAPE")

    def test_envelope_pair_and_unknown_private_fields_fail_before_projection(self):
        for key in ("framePhases", "framePhasesStatus"):
            value = fixtures.with_phases()
            del value["port"]["native"][key]
            self.rejected(value, "PHASE_SHAPE")
        for where in ("root", "record"):
            value = fixtures.with_phases()
            target = value["port"]["native"]["framePhases"] if where == "root" else self.record(value)
            target["unapproved"] = "synthetic private canary"
            self.rejected(value, "PHASE_SHAPE")
        for status in ("available", None, True, "other"):
            value = fixtures.with_phases()
            value["port"]["native"].update(framePhases=None, framePhasesStatus=status)
            self.rejected(value, "PHASE_SHAPE")

    def test_phase_history_survives_ring_and_marker_retention(self):
        before, after = fixtures.with_phases(), fixtures.with_phases(fixtures.recurrence())
        self.validate(after, before)
        old = fixtures.with_phases()
        changed = deepcopy(old)
        record = self.record(changed)
        record["seconds"][2] -= 0.01; record["seconds"][5] += 0.01
        self.validate(changed)
        with self.assertRaises(validator.ValidationError) as caught:
            self.validate(changed, old)
        self.assertEqual(caught.exception.code, "PHASE_HISTORY")
        changed["port"]["native"]["processIdentifier"] += 1
        self.assertEqual(self.validate(changed, old)["comparison"], "different_process")

    def test_phase_shape_does_not_reclassify_mixed_generations(self):
        value = fixtures.with_phases(fixtures.mixed_generation())
        report = self.validate(value)
        self.assertEqual(report["stages"]["draw"]["maximumContext"], "historical_or_mixed_generations")
        self.assertFalse(report["performanceAccepted"])

    def test_raw_nonfinite_duplicate_and_overbudget_inputs_fail(self):
        payload = fixtures.encoded(fixtures.with_phases())
        variants = [payload.replace(b'"seenMask":255', b'"seenMask":255,"seenMask":255', 1),
                    payload.replace(b'"seconds":[0,0,', b'"seconds":[NaN,0,', 1),
                    payload + b" " * validator.MAX_BYTES]
        for raw in variants:
            with self.assertRaises(validator.ValidationError):
                validator.validate_attachment(raw, "2d", fixtures.source_name())

    def test_bounded_maximum_companion_and_empty_completed_history(self):
        value = fixtures.with_phases(fixtures.recurrence())
        self.assertLessEqual(len(fixtures.encoded(value)), validator.MAX_BYTES)
        self.validate(value)
        value = fixtures.with_phases(fixtures.in_flight())
        self.validate(value)
        for records in value["port"]["native"]["framePhases"].values():
            if isinstance(records, list): self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
