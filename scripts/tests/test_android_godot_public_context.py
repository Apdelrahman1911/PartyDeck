"""Host-only focused collector regressions; fixture XML/bytes never qualify a device.

Provenance and observation doubles exist only in these tests. The native runner
has no fixture, authority-injection, pin-override or fake activation option.
"""

from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import smoke_android_godot_public_context as focused

engine = focused.engine
session = focused.adaptive.load_session(SCRIPTS / "smoke-android-godot-session.py")


def node(parent, *, tag="", text="", bounds="[20,40][340,80]", package=session.PACKAGE, **attributes):
    return ET.SubElement(parent, "node", {"package": package, "resource-id": tag, "text": text,
        "bounds": bounds, "enabled": "true", "clickable": "false", **attributes})


def table_tree(*texts):
    root = ET.Element("hierarchy", rotation="0")
    table = node(root, tag="game-table", bounds="[0,0][400,600]", scrollable="true")
    for text in texts:
        node(table, text=text)
    return root, table


def visible_reader(root):
    reader = session.ui.AndroidSmoke.__new__(session.ui.AndroidSmoke)
    reader.ui_root, reader.ui_sequence, reader.display_size = None, 0, [400, 600]
    reader.bind_ui(root)
    return reader.visible


def snapshot(y=240, stamp=0):
    clip, target = [12, 30, 365, 170], [20, y, 300, 44]
    return dict(schemaVersion=1, mode="3d", request="1", sequence="1", generation=str(3 + stamp),
        command="2", input=str(stamp), projectionRevision="7", requestedUptimeMs=1000,
        capturedUptimeMs=1050, expiresUptimeMs=13050, surface=[136, 343, 681, 377],
        viewport=list(focused.EXPECTED_VIEWPORT), sceneStateApplied=True, handConcealed=True,
        selectedCount=0, privateFaceCount=0, privateLabelCount=0,
        controls=[dict(role="play", slot=-1, rect=target, clip=clip, enabled=False, selected=False,
                       visible=y < clip[1] + clip[3] and y + target[3] > clip[1])])


HELPER_MANIFEST = (
    '<manifest package="dev.partydeck.qualification.input" xmlns:android="http://schemas.android.com/apk/res/android">'
    '<uses-sdk android:minSdkVersion="36" android:targetSdkVersion="36"/>'
    '<application android:testOnly="true" android:allowBackup="false"/>'
    '<instrumentation android:name="dev.partydeck.qualification.input.ContinuousTouchInstrumentation" '
    'android:targetPackage="dev.partydeck.qualification.input"/></manifest>').encode()


def continuous_output(arguments, down_time=1001):
    """Host-only framework receipt fixture; it never injects Android input."""
    supplied = {arguments[index + 1]: arguments[index + 2] for index, value in enumerate(arguments) if value == "-e"}
    start = [int(supplied["x0"]), int(supplied["y0"])]
    end = [int(supplied["x1"]), int(supplied["y1"])]
    move = int(supplied["move_ms"])
    endpoint, tail_end = down_time + move, down_time + move + 200
    receipt = dict(schemaVersion=1, requestId=supplied["request_id"], ok=True, phase="completed",
        failureClass="", releaseFailureClass="", start=start, end=end, moveDurationMs=move, tailDurationMs=200,
        startDeadlineUptimeMs=int(supplied["start_deadline"]), stopDeadlineUptimeMs=int(supplied["stop_deadline"]),
        downTimeUptimeMs=down_time, downAckUptimeMs=down_time + 1, endpointAckUptimeMs=endpoint,
        tailStartUptimeMs=endpoint, tailEndUptimeMs=tail_end, upEventUptimeMs=tail_end, upAckUptimeMs=tail_end + 1,
        eventsAttempted=6, eventsAcknowledged=6, stationaryMoveEvents=2, downAttempted=True, upAttempted=True,
        tailCompleted=True, inputUncertain=False, automationFlags=3, pointerCount=1, pointerId=0, inputSource=4098)
    return focused.continuous_touch.RESULT_PREFIX + json.dumps(receipt) + "\nINSTRUMENTATION_CODE: -1\n"


def owner():
    return {"configuration": {"windowing_mode": "multi-window", "font_scale": 2.0,
                               "bounds": [0, 0, 817, 720]},
            "display_size": [1600, 720], "task": 4, "renderer": {"pid": 123, "uid": 10001}}


class StandardClaimTests(unittest.TestCase):
    def claim(self, root):
        return focused.standard_claim(root, session, visible_reader(root))

    def test_reads_one_visible_app_owned_current_claim_with_its_actual_words(self):
        for count in (1, 2, 3):
            with self.subTest(count=count):
                sentence = f"Orbit claims {count} Moon{'' if count == 1 else 's'}."
                root, _ = table_tree("THE LAST CLAIM", sentence, "Only a challenge reveals the cards.")
                self.assertEqual({"kind": "claim", "claimant": "Orbit", "card_count": count,
                                  "table_rank": "Moon", "standard_sentence": sentence}, self.claim(root))

    def test_opening_is_explicit_and_never_inferred_from_an_absent_claim(self):
        self.assertEqual({"kind": "opening"}, self.claim(table_tree("Set the tone.")[0]))
        for texts in ((), ("THE LAST CLAIM",), ("Orbit claims 2 Moons.",)):
            with self.subTest(texts=texts):
                self.assertIsNone(self.claim(table_tree(*texts)[0]))

    def test_current_result_problem_and_expanded_history_are_rejected_even_offscreen(self):
        for tag in ("problem-panel", "game-round-result", "game-winner", "game-next-round"):
            root, table = table_tree("THE LAST CLAIM", "Orbit claims 2 Moons.")
            node(table, tag=tag, bounds="[20,650][340,690]")
            with self.subTest(tag=tag), self.assertRaisesRegex(Exception, "problem/result"):
                self.claim(root)
        root, table = table_tree("THE LAST CLAIM", "Orbit claims 2 Moons.")
        node(table, text="Hide round 1 reveal", bounds="[20,650][340,690]")
        with self.assertRaisesRegex(engine.ObservationFailure, "history"):
            self.claim(root)

    def test_duplicate_and_contradictory_current_semantics_fail(self):
        cases = (("THE LAST CLAIM", "THE LAST CLAIM", "Orbit claims 2 Moons."),
                 ("THE LAST CLAIM", "Orbit claims 2 Moons.", "Pip claims 1 Moon."),
                 ("THE LAST CLAIM", "Orbit claims 2 Moons.", "Set the tone."),
                 ("Set the tone.", "Set the tone."))
        for texts in cases:
            with self.subTest(texts=texts), self.assertRaisesRegex(engine.ObservationFailure, "ambiguous"):
                self.claim(table_tree(*texts)[0])
        root, _ = table_tree("THE LAST CLAIM", "Orbit claims 2 Moons.")
        node(root, tag="game-table")
        with self.assertRaisesRegex(Exception, "Duplicate"):
            self.claim(root)

    def test_foreign_outside_and_clipped_text_cannot_supply_a_claim(self):
        for location in ("foreign", "outside", "clipped"):
            root, table = table_tree("THE LAST CLAIM")
            node(root if location == "outside" else table, text="Orbit claims 2 Moons.",
                 package="other.application" if location == "foreign" else session.PACKAGE,
                 bounds="[20,590][340,630]" if location == "clipped" else "[20,80][340,120]")
            with self.subTest(location=location):
                self.assertIsNone(self.claim(root))

    def test_count_wording_is_exact_and_out_of_scope_count_is_not_staged(self):
        for text in ("Orbit claims 1 Moons.", "Orbit claims 2 Moon."):
            with self.subTest(text=text), self.assertRaisesRegex(engine.ObservationFailure, "wording"):
                self.claim(table_tree("THE LAST CLAIM", text)[0])
        for text in ("Orbit claims 4 Moons.", "Orbit claimed 2 Moons.", "Orbit claims 2 Moons. Extra"):
            with self.subTest(text=text):
                self.assertIsNone(self.claim(table_tree("THE LAST CLAIM", text)[0]))


class GeometryTests(unittest.TestCase):
    def test_admits_directly_measured_short_viewport_with_real_window_and_font(self):
        value = engine.parse(json.dumps(snapshot()), "3d", [1600, 720])
        focused.admit_native_geometry(owner(), value)
        for field, changed in (("windowing_mode", "fullscreen"), ("font_scale", 1.0)):
            changed_owner = owner()
            changed_owner["configuration"][field] = changed
            with self.subTest(field=field), self.assertRaisesRegex(engine.ObservationFailure, "multi-window"):
                focused.admit_native_geometry(changed_owner, value)
        for width, height in ((400, 600), (500, 215), (389, 240)):
            with self.subTest(viewport=(width, height)), self.assertRaisesRegex(engine.ObservationFailure, "viewport"):
                focused.admit_native_geometry(owner(), value | {"viewport": [width, height]})

    def test_disabled_play_supplies_scroll_geometry_but_remains_untappable(self):
        value = snapshot()
        original = copy.deepcopy(value)
        swipe = focused.body_swipe(value)
        self.assertEqual(original, value)
        self.assertEqual(swipe["start"][0], swipe["end"][0])
        self.assertGreater(swipe["start"][1], swipe["end"][1])
        self.assertGreaterEqual(swipe["duration_ms"], 600)
        surface, clip = value["surface"], value["controls"][0]["clip"]
        for point in (swipe["start"], swipe["end"]):
            logical = [(point[index] - surface[index]) / 1.75 for index in (0, 1)]
            self.assertTrue(clip[0] < logical[0] < clip[0] + clip[2])
            self.assertTrue(clip[1] < logical[1] < clip[1] + clip[3])
        for action in (engine.scroll_gesture, engine.touch_point):
            with self.assertRaisesRegex(engine.ObservationFailure, "disabled|Disabled"):
                action(value, value["controls"][0])

    def test_scroll_rejects_private_selection_enabled_play_and_unusable_clips(self):
        cases = []
        for field, changed in (("handConcealed", False), ("selectedCount", 1),
                               ("privateFaceCount", 1), ("privateLabelCount", 1)):
            cases.append(snapshot() | {field: changed})
        for change in ({"enabled": True}, {"selected": True}, {"clip": [12, 30, 365, 0]},
                       {"rect": [20, 240, 300, 171]}, {"rect": [0, 240, 300, 44]}):
            value = snapshot()
            value["controls"][0].update(change)
            cases.append(value)
        value = snapshot()
        value["controls"].append(dict(value["controls"][0], role="select", slot=0))
        cases.append(value)
        for value in cases:
            for upper in (False, True):
                with self.subTest(value=value, upper_origin=upper), self.assertRaises(engine.ObservationFailure):
                    focused.body_swipe(value, upper_origin=upper)

    def test_alternate_origin_preserves_the_recorded_drag_length_in_another_body_strip(self):
        # Measured run 34568971032 position-07 geometry. The alternate coordinates
        # are a host calculation, not an executed native recovery result.
        value = snapshot(524)
        value["controls"][0].update(clip=[16, 96, 357, 103], rect=[16, 524, 349, 68], visible=False)
        original = copy.deepcopy(value)
        centred = focused.body_swipe(value)
        upper = focused.body_swipe(value, upper_origin=True)
        self.assertEqual({"start": [476, 637], "end": [476, 565], "duration_ms": 1646}, centred)
        self.assertEqual({"start": [476, 601], "end": [476, 529], "duration_ms": 1646}, upper)
        self.assertEqual(centred["start"][1] - centred["end"][1], upper["start"][1] - upper["end"][1])
        self.assertEqual(original, value)
        for gesture in (centred, upper):
            for point in (gesture["start"], gesture["end"]):
                logical = [(point[index] - value["surface"][index]) / 1.75 for index in (0, 1)]
                self.assertTrue(16 < logical[0] < 373)
                self.assertTrue(96 < logical[1] < 199)

    def test_body_swipe_limits_requested_speed_without_extending_short_drags(self):
        # Preserve the existing movement speed and short-stroke floor near full
        # Play enclosure. The helper supplies a separate stationary endpoint tail.
        # This host geometry check does not predict or accept native displacement.
        for y in (160, 240, 900):
            for upper in (False, True):
                value = snapshot(y)
                swipe = focused.body_swipe(value, upper_origin=upper)
                distance = (swipe["start"][1] - swipe["end"][1]) / 1.75
                with self.subTest(y=y, upper_origin=upper):
                    self.assertLessEqual(distance / (swipe["duration_ms"] / 1000), 25)
                    self.assertGreaterEqual(swipe["duration_ms"], 600)
        # A 32-unit clip yields the smallest admitted 12.8-unit requested stroke.
        value = snapshot(200)
        value["controls"][0].update(clip=[16, 96, 357, 32], rect=[16, 200, 349, 24], visible=False)
        for upper in (False, True):
            swipe = focused.body_swipe(value, upper_origin=upper)
            self.assertEqual(600, swipe["duration_ms"])

    def test_near_play_drag_aims_inside_the_full_enclosure_interval(self):
        value = snapshot(160)
        for upper in (False, True):
            swipe = focused.body_swipe(value, upper_origin=upper)
            distance = (swipe["start"][1] - swipe["end"][1]) / 1.75
            target = value["controls"][0]["rect"].copy()
            target[1] -= distance
            self.assertTrue(engine.encloses(value["controls"][0]["clip"], target))
            self.assertLess(distance, value["controls"][0]["clip"][3] * 0.4)

    def test_overlap_depends_on_measured_motion_and_not_the_requested_swipe(self):
        before = snapshot(300)
        self.assertLess((focused.body_swipe(before)["start"][1]
                        - focused.body_swipe(before)["end"][1]) / 1.75, 85)
        self.assertEqual(80, focused.measured_displacement(before, snapshot(220, 5)))
        with self.assertRaisesRegex(engine.ObservationFailure, "overlap"):
            focused.measured_displacement(before, snapshot(200, 5))
        with self.assertRaisesRegex(engine.ObservationFailure, "opposite"):
            focused.measured_displacement(before, snapshot(310, 5))

    def test_input_generation_may_advance_but_fixed_projection_and_geometry_cannot(self):
        before = snapshot()
        focused.same_context(before, snapshot(200, 20))
        for field, changed in (("mode", "2d"), ("command", "3"), ("projectionRevision", "8"),
                               ("surface", [137, 343, 680, 377]), ("viewport", [390, 215])):
            with self.subTest(field=field), self.assertRaises(engine.ObservationFailure):
                focused.same_context(before, snapshot(200, 20) | {field: changed})
        for field, changed in (("clip", [12, 31, 365, 169]), ("rect", [21, 200, 300, 44]),
                               ("rect", [20, 200, 299, 44]), ("rect", [20, 200, 300, 43])):
            value = snapshot(200, 20)
            value["controls"][0][field] = changed
            with self.subTest(field=field, changed=changed), self.assertRaises(engine.ObservationFailure):
                focused.same_context(before, value)


class HostTransport:
    def __init__(self, values, transport_error=None):
        self.values, self.value = copy.deepcopy(values), copy.deepcopy(values[0])
        self.index, self.calls, self.captures, self.receipts = 0, [], [], []
        self.owner, self.input_incomplete = owner(), False
        self.session, self.stage, self.last_error = session, "host-test", ""
        self.transport_error, self.capture_mutation = transport_error, None

    def adb(self, *arguments, **kwargs):
        self.calls.append(arguments)
        if self.transport_error:
            raise self.transport_error
        down_time = self.value["capturedUptimeMs"] + 1
        self.index += 1
        self.value = copy.deepcopy(self.values[min(self.index, len(self.values) - 1)])
        return continuous_output(arguments, down_time) if arguments[:3] == ("shell", "am", "instrument") else ""

    def dump_ui(self, deadline=None):
        root = ET.Element("hierarchy")
        node(root, tag=engine.RESOURCE, text="Table ready.", clickable="true",
             **{"class": "android.widget.TextView", "content-desc": json.dumps(self.value)})
        return root

    def native_controls(self, root):
        return {"status": "Table ready."}

    def visible(self, node):
        return True

    def retain_standard_ui(self, name, value):
        receipt = {"file": name + ".xml", "observation": copy.deepcopy(value)}
        self.receipts.append(receipt)
        return receipt

    def capture_evidence(self, name, component, pid, ui_assertion):
        capture = {"name": name, "screenshot": {"file": name + ".png"}, "host_double": True}
        self.captures.append(capture)
        ui_assertion(self.dump_ui())
        if self.capture_mutation:
            self.capture_mutation(self.value)
        return capture

    def reject_crash_dialog(self, root):
        pass

    def swipe(self, *args, **kwargs):
        return self.adb("shell", "input", "swipe", "1", "2", "1", "1", "600")


class HostSmoke(focused.PublicContextScenarios, HostTransport):
    pass


class HostProbe(engine.EngineObservationProbe):
    """Only settlement/owner acquisition use doubles; parsing and pre-input checks are real."""
    def __init__(self, smoke):
        self.smoke, self.owner, self.mode, self.pid = smoke, copy.deepcopy(smoke.owner), "3d", 123
        self.prefix, self.serial, self.refresh_count, self.settled_count = "host-observation", 0, 0, 0

    def _owner(self):
        engine.require(self.owner == self.smoke.owner, "Native owner changed in host fixture.")
        return self.owner

    def refresh(self, deadline):
        engine.require(focused.time.monotonic() < deadline, "Host refresh deadline expired.")
        self._owner()
        self.refresh_count += 1
        self.smoke.value.update(request=str(self.refresh_count), sequence=str(self.refresh_count),
            requestedUptimeMs=1000 + self.refresh_count * 250, capturedUptimeMs=1050 + self.refresh_count * 250,
            expiresUptimeMs=13050 + self.refresh_count * 250)
        value = self._parse(json.dumps(self.smoke.value))
        return {"value": value, "owner": self.owner, "requested_host_time": focused.time.monotonic(),
                "receipt": self.smoke.retain_standard_ui(self._name("refresh"), value)}

    def settled(self, predicate, seconds=60):
        self.settled_count += 1
        result = self.refresh(focused.time.monotonic() + seconds)
        engine.require(predicate(result["value"]), "Host fixture does not satisfy settlement predicate.")
        return result


class SweepTests(unittest.TestCase):
    def setUp(self):
        timer = patch.object(focused.time, "monotonic", return_value=100.0)
        timer.start()
        self.addCleanup(timer.stop)

    def sweep(self, ys, *, values=None, transport_error=None):
        values = values if values is not None else [snapshot(y, index * 8) for index, y in enumerate(ys)]
        smoke = HostSmoke(values, transport_error)
        probe = HostProbe(smoke)
        return focused.ContextSweep(smoke, probe), smoke, probe

    def test_motion_full_play_and_terminal_no_progress_leave_pixel_review_pending(self):
        sweep, smoke, probe = self.sweep([240, 180, 120, 120, 120])
        result = sweep.run()
        self.assertEqual("passed", result["automated_geometry"])
        self.assertEqual(120, result["body_displacement"])
        self.assertEqual("pending-independent-review", result["public_context_pixel_acceptance"])
        self.assertIn("bottom is not established", result["termination"])
        self.assertEqual([False, False, True, True, True], [p["play_fully_enclosed"] for p in result["positions"]])
        self.assertEqual(4, len(smoke.calls))
        self.assertEqual(5, len(smoke.captures))
        self.assertEqual(["centred-body", "upper-body"], [s["origin"] for s in sweep.swipes[-2:]])
        self.assertTrue(all(s["status"] == "observed" and s["input"] and s["after"] for s in sweep.swipes))
        self.assertTrue(all(not p["after"]["observation"]["controls"][0]["enabled"] for p in sweep.positions))

    def test_small_clip_long_traversal_uses_its_own_budget_beyond_eight_action_swipes(self):
        # 103 is the prior desktop body height; these internal rectangles are host fixtures,
        # not native measurements. Live qualification must observe its own actual geometry.
        ys = list(range(958, 27, -30)) + [28, 28]
        values = []
        for index, y in enumerate(ys):
            value = snapshot(y, index * 8)
            value["controls"][0].update(clip=[16, 96, 357, 103], rect=[16, y, 349, 68],
                                         visible=y < 199 and y + 68 > 96)
            values.append(value)
        sweep, smoke, _ = self.sweep([], values=values)
        result = sweep.run()
        self.assertEqual(33, len(smoke.calls))
        self.assertEqual(930, result["body_displacement"])
        self.assertTrue(result["play_fully_enclosed"])
        self.assertEqual("pending-independent-review", result["public_context_pixel_acceptance"])
        self.assertTrue(all(s["content_displacement"] <= 103 / 2 for s in sweep.swipes))

    def test_input_stamps_without_motion_or_without_full_play_cannot_pass(self):
        for ys in ([240, 240, 240], [100, 100, 100], [350, 300, 300, 300]):
            sweep, smoke, _ = self.sweep(ys)
            with self.subTest(ys=ys), self.assertRaisesRegex(engine.ObservationFailure, "before meaningful"):
                sweep.run()
            self.assertEqual(len(ys), len(smoke.captures))

    def test_subunit_plateaus_cannot_add_up_to_new_meaningful_movement(self):
        sweep, smoke, _ = self.sweep([100, 99.4, 98.8])
        with self.assertRaisesRegex(engine.ObservationFailure, "before meaningful"):
            sweep.run()
        self.assertEqual(2, len(smoke.calls))
        self.assertTrue(all(p["play_fully_enclosed"] for p in sweep.positions))
        self.assertTrue(all(0 < s["content_displacement"] < 1 for s in sweep.swipes))
        self.assertGreater(sum(s["content_displacement"] for s in sweep.swipes), 1)

    def test_recorded_no_progress_uses_upper_origin_then_resumes_centred_collection(self):
        # The first nine positions reproduce recorded geometry. All remaining
        # responses are explicit host fixtures; no native recovery is asserted.
        ys = [842, 800, 754, 709, 665, 617, 569, 524, 524]
        ys += [480, 436, 392, 348, 304, 260, 216, 172, 128, 84, 40, 40, 40]
        values = []
        for index, y in enumerate(ys):
            value = snapshot(y, index * 8)
            value["controls"][0].update(clip=[16, 96, 357, 103], rect=[16, y, 349, 68],
                                         visible=y < 199 and y + 68 > 96)
            values.append(value)
        sweep, smoke, _ = self.sweep([], values=values)
        result = sweep.run()
        self.assertEqual("passed", result["automated_geometry"])
        self.assertEqual(len(ys) - 1, len(smoke.calls))
        self.assertEqual(0, sweep.swipes[7]["content_displacement"])
        self.assertFalse(sweep.positions[8]["play_fully_enclosed"])
        self.assertEqual("centred-body", sweep.swipes[7]["origin"])
        self.assertEqual([476, 637], sweep.swipes[7]["gesture"]["start"])
        self.assertEqual("upper-body", sweep.swipes[8]["origin"])
        self.assertEqual([476, 601], sweep.swipes[8]["gesture"]["start"])
        self.assertEqual(44, sweep.swipes[8]["content_displacement"])
        self.assertEqual("centred-body", sweep.swipes[9]["origin"])
        self.assertTrue(result["play_fully_enclosed"])
        self.assertEqual("pending-independent-review", result["public_context_pixel_acceptance"])
        self.assertTrue(all(s["status"] == "observed" and s["content_displacement"] <= 103 / 2 for s in sweep.swipes))

    def test_observed_gap_and_reverse_motion_keep_the_reached_image_and_receipts(self):
        for ys, message in (([300, 200], "overlap"), ([200, 210], "opposite")):
            sweep, smoke, _ = self.sweep(ys)
            with self.subTest(ys=ys), self.assertRaisesRegex(engine.ObservationFailure, message):
                sweep.run()
            self.assertEqual(2, len(smoke.captures))
            self.assertEqual(2, len(sweep.positions))
            self.assertEqual("sampled", sweep.swipes[0]["status"])
            self.assertEqual(ys[0] - ys[1], sweep.swipes[0]["content_displacement"])
            self.assertIn("after", sweep.swipes[0])

    def test_run10_recorded_displacements_still_fail_the_half_clip_overlap_gate(self):
        # Selected run 34575134242 geometry is replayed under host doubles only.
        # Neither the slower requested gesture nor the renderer correction may
        # relabel these already observed 52/86-unit jumps as acceptable evidence.
        for before_y, after_y in ((682, 630), (550, 464)):
            values = []
            for index, y in enumerate((before_y, after_y)):
                value = snapshot(y, index * 8)
                value["projectionRevision"] = "5"
                value["controls"][0].update(clip=[16, 96, 357, 103], rect=[16, y, 349, 68], visible=False)
                values.append(value)
            sweep, smoke, _ = self.sweep([], values=values)
            with self.subTest(displacement=before_y - after_y), \
                    self.assertRaisesRegex(engine.ObservationFailure, "half-page capture overlap"):
                sweep.run()
            self.assertEqual(1, len(smoke.calls))
            self.assertEqual(2, len(smoke.captures))
            self.assertEqual("centred-body", sweep.swipes[0]["origin"])
            self.assertEqual(1646, sweep.swipes[0]["gesture"]["duration_ms"])
            self.assertEqual("sampled", sweep.swipes[0]["status"])
            self.assertEqual(before_y - after_y, sweep.swipes[0]["content_displacement"])
            self.assertEqual(103 / 2, sweep.positions[-1]["clip"][3] / 2)
            self.assertIn("after", sweep.swipes[0])

    def test_missing_input_or_inconsistent_generation_stamp_fails_after_one_swipe(self):
        for change in ({"input": "0"}, {"generation": "3"}, {"generation": "0"}, {"generation": "10"}):
            values = [snapshot(), snapshot(180, 8) | change]
            sweep, smoke, _ = self.sweep([], values=values)
            with self.subTest(change=change), self.assertRaisesRegex(engine.ObservationFailure, "stamps"):
                sweep.run()
            self.assertEqual(1, len(smoke.calls))
        values = [snapshot(), snapshot(180, 8) | {"generation": "12"}, snapshot(120, 16), snapshot(120, 24), snapshot(120, 32)]
        # One expiry invalidation is legal in addition to the delivered input events.
        for value in values[2:]:
            value["generation"] = str(int(value["generation"]) + 1)
        self.assertEqual("passed", self.sweep([], values=values)[0].run()["automated_geometry"])

    def test_alternate_origin_cannot_continue_after_an_observation_or_overlap_failure(self):
        cases = (
            (snapshot(180, 16) | {"input": "8"}, "stamps"),
            (snapshot(180, 16) | {"projectionRevision": "8"}, "projectionRevision"),
            (snapshot(180, 16) | {"handConcealed": False}, "settlement predicate"),
            (snapshot(120, 16), "overlap"),
            (snapshot(250, 16), "opposite"),
        )
        for after, message in cases:
            sweep, smoke, _ = self.sweep([], values=[snapshot(240, 0), snapshot(240, 8), after])
            with self.subTest(message=message), self.assertRaisesRegex(engine.ObservationFailure, message):
                sweep.run()
            self.assertEqual(2, len(smoke.calls))
            self.assertEqual("upper-body", sweep.swipes[-1]["origin"])

    def test_changed_projection_fails_before_a_second_swipe(self):
        values = [snapshot(), snapshot(180, 8) | {"projectionRevision": "8"}]
        sweep, smoke, _ = self.sweep([], values=values)
        with self.assertRaisesRegex(engine.ObservationFailure, "projectionRevision"):
            sweep.run()
        self.assertEqual(1, len(smoke.calls))

    def test_real_pre_input_freshness_rejects_expiry_owner_and_changed_publication(self):
        for kind in ("expired", "owner", "publication"):
            sweep, smoke, probe = self.sweep([240, 180])
            current = probe.settled(focused.concealed)
            if kind == "expired":
                current["requested_host_time"] = 91.0
            elif kind == "owner":
                smoke.owner["renderer"]["pid"] = 124
            else:
                smoke.value["projectionRevision"] = "8"
            with self.subTest(kind=kind), self.assertRaises(engine.ObservationFailure):
                probe._before_input(current, "play", -1, focused.body_swipe(current["value"]), "context-swipe")
            self.assertEqual([], smoke.calls)

    def test_screenshot_bracket_rejects_changed_state_without_losing_the_capture(self):
        for field, value in (("generation", "4"), ("input", "1"), ("projectionRevision", "8")):
            sweep, smoke, _ = self.sweep([240])
            smoke.capture_mutation = lambda current: current.update({field: value})
            with self.subTest(field=field), self.assertRaisesRegex(engine.ObservationFailure, "around the sequential"):
                sweep.run()
            self.assertEqual(1, len(smoke.captures))
            self.assertEqual([], sweep.positions)
            self.assertEqual([], smoke.calls)

    def test_finite_count_and_time_budgets_fail_incomplete_collection(self):
        sweep, smoke, _ = self.sweep([400, 350, 300, 250, 200])
        with patch.object(focused, "MAX_SWIPES", 3), self.assertRaisesRegex(engine.ObservationFailure, "finite swipe budget"):
            sweep.run()
        self.assertEqual(3, len(smoke.calls))
        sweep, smoke, _ = self.sweep([240])
        with patch.object(focused, "SWEEP_SECONDS", 0), self.assertRaisesRegex(engine.ObservationFailure, "deadline"):
            sweep.run()
        self.assertEqual([], smoke.calls)

    def test_alternate_origin_cannot_escape_the_existing_count_or_time_budget(self):
        sweep, smoke, _ = self.sweep([240, 240, 240])
        with patch.object(focused, "MAX_SWIPES", 1), self.assertRaisesRegex(engine.ObservationFailure, "finite swipe budget"):
            sweep.run()
        self.assertEqual(1, len(smoke.calls))
        self.assertEqual("centred-body", sweep.swipes[-1]["origin"])

        sweep, smoke, _ = self.sweep([240, 240, 240])
        measure = focused.measured_displacement
        with patch.object(focused.time, "monotonic", return_value=100.0) as clock:
            def expire_after_measurement(before, after):
                displacement = measure(before, after)
                clock.return_value = 100.0 + focused.SWEEP_SECONDS + 1
                return displacement
            with patch.object(focused, "measured_displacement", side_effect=expire_after_measurement), \
                    self.assertRaisesRegex(engine.ObservationFailure, "finite time budget"):
                sweep.run()
        self.assertEqual(1, len(smoke.calls))
        self.assertEqual(2, len(smoke.captures))

    def test_uncertain_alternate_input_is_preserved_and_never_repeated(self):
        sweep, smoke, _ = self.sweep([240, 240, 180])
        send = smoke.adb
        def second_input_fails(*arguments, **kwargs):
            if len(smoke.calls) == 1:
                smoke.transport_error = subprocess.TimeoutExpired(["adb", "shell", "input", "swipe"], 10)
            return send(*arguments, **kwargs)
        smoke.adb = second_input_fails
        with self.assertRaisesRegex(engine.ObservationFailure, "transport did not complete"):
            sweep.run()
        self.assertEqual(2, len(smoke.calls))
        self.assertTrue(smoke.input_incomplete)
        self.assertEqual("upper-body", sweep.swipes[-1]["origin"])
        self.assertEqual("requested", sweep.swipes[-1]["status"])
        with self.assertRaisesRegex(engine.ObservationFailure, "prior input"):
            smoke.adb("shell", "input", "tap", "1", "1")
        self.assertEqual(2, len(smoke.calls))

    def test_uncertain_swipe_is_retained_once_and_all_further_input_is_forbidden(self):
        error = subprocess.TimeoutExpired(["adb", "shell", "input", "swipe"], 10)
        sweep, smoke, probe = self.sweep([240, 180], transport_error=error)
        with self.assertRaisesRegex(engine.ObservationFailure, "transport did not complete"):
            sweep.run()
        self.assertTrue(smoke.input_incomplete)
        self.assertEqual(1, len(smoke.calls))
        self.assertEqual(1, probe.settled_count)
        self.assertEqual("requested", sweep.swipes[0]["status"])
        self.assertIn("input", sweep.swipes[0])
        with self.assertRaisesRegex(engine.ObservationFailure, "prior input"):
            smoke.adb("shell", "input", "tap", "1", "1")
        self.assertEqual(1, len(smoke.calls))

    def test_inherited_ui_wait_cannot_retry_an_uncertain_transport_error(self):
        for error in (subprocess.TimeoutExpired(["adb"], 10), OSError("transport lost")):
            _, smoke, _ = self.sweep([240], transport_error=error)
            with self.subTest(error=type(error).__name__), self.assertRaisesRegex(engine.ObservationFailure, "transport did not complete"):
                session.ui.AndroidSmoke.wait_until(smoke, "missing control", lambda root: None, seconds=1, scroll="down")
            self.assertEqual(1, len(smoke.calls))

    def test_keyboard_interrupt_during_input_marks_transport_incomplete(self):
        sweep, smoke, _ = self.sweep([240], transport_error=KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            sweep.run()
        self.assertTrue(smoke.input_incomplete)
        self.assertEqual(1, len(smoke.calls))


class StagingTests(unittest.TestCase):
    def stage(self, *, opening=False, play_error=None, play_error_at=1, still_opening=False,
              contexts=None, expire_after_play=False):
        class Stage(focused.PublicContextScenarios):
            def __init__(self):
                self.session, self.actions, self.plays, self.turn_waits = session, [], 0, 0
                self.reads, self.input_incomplete = 0, False
                self.public = {"round": 1, "table_rank": "Moon", "turn": "Your turn"}
            def tap_action(self, tag, **kwargs):
                self.actions.append(tag)
            def wait_for_tag(self, tag):
                return table_tree()[1]
            def wait_for_human_turn(self):
                self.turn_waits += 1
            def observe_context(self, prefix, allow_opening=False):
                self.reads += 1
                if contexts is None:
                    kind = "opening" if (opening and self.reads == 1) or still_opening else "claim"
                    round_number = 1 + 4 * (self.reads - 1)
                else:
                    kind, round_number = contexts[self.reads - 1]
                engine.require(kind != "opening" or allow_opening, "An explicit opening was not allowed.")
                self.public = dict(self.public, round=round_number)
                return {"public": self.public.copy(), "claim": {"kind": kind}}
            def observe_match(self, prefix):
                return {"host_only_baseline": True, "public": self.public.copy()}
            def play_standard_card(self, baseline, prefix):
                self.plays += 1
                # This test double explicitly models transport acknowledgement; no native action runs.
                self.context_staging_action["status"] = "input-acknowledged"
                if play_error and self.plays == play_error_at:
                    raise play_error
                if expire_after_play:
                    self.context_staging_deadline = focused.time.monotonic() - 1
                return {"host_only_outcome": True}
            def conceal_after_staging_play(self, prefix):
                # This class tests the staging driver; real hand UI behavior is exercised below.
                self.actions.append("conceal-after-confirmed-play")
            def dump_ui(self):
                return table_tree()[0]
            def retain_standard_ui(self, name, observation):
                return {"file": name + ".xml", "host_only": True, "observation": observation}
        return Stage()

    def test_existing_claim_needs_no_staging_action(self):
        smoke = self.stage()
        result, staging = smoke.stage_context()
        self.assertEqual("claim", result["claim"]["kind"])
        self.assertEqual([], staging)
        self.assertEqual(0, smoke.plays)
        self.assertEqual(["home-practice"], smoke.actions)

    def test_explicit_opening_uses_one_standard_action_and_bounded_progression(self):
        smoke = self.stage(opening=True)
        smoke.stage_context()
        self.assertEqual(1, smoke.plays)
        self.assertEqual(2, smoke.turn_waits)
        self.assertEqual(1, smoke.actions.count("conceal-after-confirmed-play"))
        self.assertTrue(smoke.context_practice_active)

    def test_acknowledged_practice_launch_is_owned_even_if_first_table_wait_fails(self):
        smoke = self.stage()
        with patch.object(smoke, "wait_for_tag", side_effect=TimeoutError("No table sample")), self.assertRaises(TimeoutError):
            smoke.stage_context()
        self.assertEqual(["home-practice"], smoke.actions)
        self.assertTrue(smoke.context_practice_active)
        self.assertEqual(0, smoke.plays)

    def test_fresh_later_openings_permit_new_actions_after_each_confirmed_outcome(self):
        smoke = self.stage(contexts=[("opening", 1), ("opening", 5), ("opening", 9), ("claim", 11)])
        records = []
        current, plays = smoke.stage_context(records)
        self.assertEqual("claim", current["claim"]["kind"])
        self.assertEqual(3, smoke.plays)
        self.assertEqual(3, smoke.actions.count("conceal-after-confirmed-play"))
        self.assertEqual([1, 5, 9], [play["before"]["public"]["round"] for play in plays])
        self.assertTrue(all(play["status"] == "confirmed" and "outcome" in play for play in plays))
        self.assertEqual(3, len({play["prefix"] for play in plays}))
        self.assertEqual(4, len([item for item in records if item["kind"] == "observed-context"]))
        self.assertIsNone(smoke.context_staging_deadline)

    def test_four_confirmed_plays_at_fresh_openings_exhaust_staging_as_unsupported(self):
        smoke = self.stage(still_opening=True)
        records = []
        with self.assertRaisesRegex(focused.adaptive.Unavailable, "Four confirmed"):
            smoke.stage_context(records)
        self.assertEqual(4, smoke.plays)
        self.assertEqual(5, smoke.turn_waits)
        plays = [item for item in records if item["kind"] == "standard-staging-play"]
        self.assertEqual(4, len(plays))
        self.assertTrue(all(play["status"] == "confirmed" for play in plays))
        self.assertIsNone(smoke.context_staging_deadline)

    def test_uncertain_oracle_preserves_the_prepared_attempt_and_never_retries(self):
        smoke = self.stage(opening=True, play_error=engine.ObservationFailure("Uncertain outcome"))
        records = []
        with self.assertRaisesRegex(engine.ObservationFailure, "Uncertain outcome"):
            smoke.stage_context(records)
        self.assertEqual(1, smoke.plays)
        self.assertEqual(1, smoke.turn_waits)
        attempt = [item for item in records if item["kind"] == "standard-staging-play"][0]
        self.assertEqual("input-acknowledged", attempt["status"])
        self.assertNotIn("outcome", attempt)
        self.assertIsNone(smoke.context_staging_deadline)

    def test_an_opening_in_the_same_round_does_not_authorize_a_second_play(self):
        smoke = self.stage(contexts=[("opening", 1), ("opening", 1)])
        with self.assertRaisesRegex(engine.ObservationFailure, "without a new observed round"):
            smoke.stage_context()
        self.assertEqual(1, smoke.plays)

    def test_second_oracle_failure_keeps_the_first_confirmation_and_stops_before_a_third_play(self):
        smoke = self.stage(contexts=[("opening", 1), ("opening", 5), ("claim", 9)],
            play_error=engine.ObservationFailure("Second outcome unconfirmed"), play_error_at=2)
        records = []
        with self.assertRaisesRegex(engine.ObservationFailure, "Second outcome unconfirmed"):
            smoke.stage_context(records)
        attempts = [event for event in records if event["kind"] == "standard-staging-play"]
        self.assertEqual(2, smoke.plays)
        self.assertEqual(2, smoke.turn_waits)
        self.assertEqual(1, smoke.actions.count("conceal-after-confirmed-play"))
        self.assertEqual(["confirmed", "input-acknowledged"], [event["status"] for event in attempts])
        self.assertIn("outcome", attempts[0])
        self.assertNotIn("outcome", attempts[1])
        self.assertIsNone(smoke.context_staging_deadline)

    def test_deadline_before_or_after_a_confirmed_transaction_is_honest_exhaustion(self):
        smoke = self.stage(opening=True)
        with patch.object(focused, "STAGING_SECONDS", 0), self.assertRaises(focused.adaptive.Unavailable):
            smoke.stage_context()
        self.assertEqual(0, smoke.plays)
        smoke = self.stage(opening=True, expire_after_play=True)
        records = []
        with self.assertRaises(focused.adaptive.Unavailable):
            smoke.stage_context(records)
        self.assertEqual(1, smoke.plays)
        self.assertEqual(1, len([item for item in records if item.get("status") == "confirmed"]))

    def test_deadline_while_play_outcome_is_unconfirmed_remains_failure(self):
        for status in ("input-requested", "input-acknowledged"):
            smoke = self.stage()
            smoke.context_staging_deadline = focused.time.monotonic() - 1
            smoke.context_staging_action = {"status": status}
            with self.subTest(status=status), self.assertRaisesRegex(engine.ObservationFailure, "outcome was confirmed"):
                smoke.staging_time()

    def test_cleanup_does_not_repeat_an_incomplete_attempt_or_run_after_uncertain_input(self):
        for attributes, message in (({"input_incomplete": True}, "Uncertain input"),
                                    ({"input_incomplete": False, "context_cleanup_attempted": True}, "cannot repeat")):
            smoke = self.stage()
            smoke.__dict__.update(attributes)
            with self.subTest(attributes=attributes), self.assertRaisesRegex(engine.ObservationFailure, message):
                smoke.end_context_practice()
            self.assertEqual([], smoke.actions)


class StagingUiTransport:
    """Only acquisition/transport use fixtures; inherited UI decisions and receipts run."""
    def adb(self, *arguments, **kwargs):
        self.transport_calls.append(arguments)
        actions = [event for event in self.context_staging_records
                   if event["kind"] in ("standard-staging-play", "round-advance")]
        self.input_states.append([
            {"status": event["status"], "xml_exists": (self.output / event["input_xml"]["file"]).is_file()}
            for event in actions if "input_xml" in event])
        if self.transport_error is not None:
            raise self.transport_error
        if arguments[:2] == ("shell", "input"):
            self.frame_index = min(self.frame_index + 1, len(self.frames) - 1)
        return ""


class StagingUiHost(focused.PublicContextScenarios, StagingUiTransport, session.GodotSessionSmoke):
    def __init__(self, output, frames):
        session.GodotSessionSmoke.__init__(self, "host-only", output)
        self.session, self.stage, self.display_size = session, "host-only-staging", [400, 600]
        self.frames = [ET.tostring(frame, encoding="utf-8") for frame in frames]
        self.frame_index, self.input_incomplete, self.transport_error = 0, False, None
        self.transport_calls, self.input_states, self.events = [], [], []
        self.context_staging_deadline = focused.time.monotonic() + focused.STAGING_SECONDS
        self.context_staging_action, self.context_staging_records = None, []

    def dump_ui(self, deadline=None):
        self.events.append(("dump", self.frame_index))
        self.last_xml_bytes = self.frames[self.frame_index]
        self.last_xml_time = "host-only-fixture-acquisition"
        root = ET.fromstring(self.last_xml_bytes)
        self.bind_ui(root)
        return root

    def wait_activity(self, component, *, child_absent=False):
        self.events.append(("activity", component, child_absent))

    def record(self, message):
        self.steps.append(message)


class StagingEvidenceTests(unittest.TestCase):
    def host(self, frames):
        directory = tempfile.TemporaryDirectory(prefix="partydeck-context-staging-host-")
        self.addCleanup(directory.cleanup)
        return StagingUiHost(Path(directory.name), frames)

    @staticmethod
    def winner():
        root, table = table_tree()
        node(table, tag="game-winner", text="Host-only match result")
        return root

    @staticmethod
    def elimination():
        return table_tree("Stay for the showdown.",
            "You’re out of this match. Keep watching to see who keeps their last light.")[0]

    def test_exact_exhaustion_requires_fresh_app_owned_end_or_elimination(self):
        for message in sorted(focused.TURN_EXHAUSTION):
            for root, reason in ((self.winner(), "observed match end"),
                                 (self.elimination(), "observed human elimination")):
                smoke = self.host([root])
                with self.subTest(message=message, reason=reason), \
                     patch.object(smoke, "wait_for_human_turn", side_effect=RuntimeError(message)), \
                     self.assertRaisesRegex(focused.adaptive.Unavailable, reason):
                    smoke.wait_context_turn("host-exhaustion")
                self.assertEqual([("activity", session.MAIN_COMPONENT, True), ("dump", 0)], smoke.events)
                event = smoke.context_staging_records[0]
                self.assertEqual("observed-staging-exhaustion", event["status"])
                self.assertEqual(reason, event["reason"])
                receipt = event["final_ui"]
                raw = (smoke.output / receipt["file"]).read_bytes()
                self.assertEqual(smoke.frames[0], raw)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), receipt["sha256"])

    def test_unknown_foreign_partial_or_stale_spectator_evidence_does_not_downgrade_failure(self):
        unknown = table_tree("Stay for the showdown.", "Watch the claims. See who holds their nerve.")[0]
        foreign_winner, table = table_tree()
        node(table, tag="game-winner", package="foreign.app")
        foreign_elimination = self.elimination()
        for item in foreign_elimination.iter("node"):
            if item.get("text"):
                item.set("package", "foreign.app")
        outside, _ = table_tree()
        node(outside, tag="game-winner")
        contradictory = self.winner()
        node(session.tagged_node(contradictory, "game-table"), tag="game-play")
        roots = (unknown, foreign_winner, foreign_elimination, outside, contradictory,
                 table_tree("Stay for the showdown.")[0], ET.Element("hierarchy"))
        for index, root in enumerate(roots):
            smoke = self.host([root])
            # Old positive bytes must not survive a new, nonqualifying acquisition.
            smoke.last_xml_bytes = ET.tostring(self.winner())
            error = RuntimeError("Practice did not offer a human play within 120 seconds.")
            with self.subTest(index=index), patch.object(smoke, "wait_for_human_turn", side_effect=error), \
                 self.assertRaises(RuntimeError) as raised:
                smoke.wait_context_turn("host-unqualified")
            self.assertIs(error, raised.exception)
            self.assertEqual(smoke.frames[0], smoke.last_xml_bytes)
            self.assertEqual("unconfirmed", smoke.context_staging_records[0]["status"])
            self.assertNotIn("final_ui", smoke.context_staging_records[0])

    def test_problem_crash_or_wrong_activity_cannot_be_reclassified_as_exhaustion(self):
        for kind in ("problem", "crash", "wrong-activity"):
            root = self.winner()
            if kind == "problem":
                node(root, tag="problem-panel")
            elif kind == "crash":
                node(root, tag="android:id/aerr_close", package="android")
            smoke = self.host([root])
            if kind == "wrong-activity":
                def wrong_activity(*args, **kwargs):
                    raise RuntimeError("The current Activity is not the owned Main Activity.")
                smoke.wait_activity = wrong_activity
            with self.subTest(kind=kind), patch.object(smoke, "wait_for_human_turn", side_effect=
                    RuntimeError("Practice ended before the human play could be exercised.")), \
                 self.assertRaises((RuntimeError, engine.ObservationFailure)) as raised:
                smoke.wait_context_turn("host-invalid-end")
            self.assertNotIsInstance(raised.exception, focused.adaptive.Unavailable)
            self.assertEqual("unconfirmed", smoke.context_staging_records[0]["status"])
            self.assertNotIn("final_ui", smoke.context_staging_records[0])

    def test_generic_helper_errors_and_uncertain_input_keep_the_original_failure(self):
        class OtherRuntimeError(RuntimeError):
            pass
        known = "Practice ended before the human play could be exercised."
        cases = ((RuntimeError("Unrelated helper failure"), False), (RuntimeError(known + " altered"), False),
                 (OtherRuntimeError(known), False), (TimeoutError(known), False), (RuntimeError(known), True))
        for error, incomplete in cases:
            smoke = self.host([self.winner()])
            smoke.input_incomplete = incomplete
            with self.subTest(error=repr(error), incomplete=incomplete), \
                 patch.object(smoke, "wait_for_human_turn", side_effect=error), \
                 self.assertRaises(type(error)) as raised:
                smoke.wait_context_turn("host-other-failure")
            self.assertIs(error, raised.exception)
            self.assertEqual([], smoke.events)

    def test_inherited_turn_wait_retains_each_next_round_before_acknowledged_input(self):
        frames = []
        for round_number in range(1, 5):
            root, table = table_tree(f"Round {round_number}")
            node(table, tag="game-next-round", text="Next round", clickable="true")
            frames.append(root)
        root, table = table_tree("Round 5", "Set the tone.")
        node(table, tag="game-play", text="Play cards", enabled="false")
        smoke = self.host(frames + [root])
        with patch.object(session.ui.time, "sleep", return_value=None):
            smoke.wait_context_turn("host-rounds")
        advances = [event for event in smoke.context_staging_records if event["kind"] == "round-advance"]
        self.assertEqual(4, len(advances))
        self.assertEqual(4, len(smoke.transport_calls))
        self.assertTrue(all(call[:3] == ("shell", "input", "tap") for call in smoke.transport_calls))
        self.assertEqual("human-play-observed", smoke.context_staging_records[0]["status"])
        for index, event in enumerate(advances):
            self.assertEqual("input-acknowledged", event["status"])
            self.assertEqual({"status": "input-requested", "xml_exists": True}, smoke.input_states[index][-1])
            receipt = event["input_xml"]
            raw = (smoke.output / receipt["file"]).read_bytes()
            self.assertEqual(smoke.frames[index], raw)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), receipt["sha256"])
        self.assertEqual(4, len({event["input_xml"]["file"] for event in advances}))

    def prepare_play(self):
        root, table = table_tree()
        node(table, tag="game-play", text="Play 1 card", clickable="true")
        smoke = self.host([root])
        root = smoke.dump_ui()
        receipt = smoke.retain_standard_ui("host-play-input", {"label": "Play 1 card"})
        event = {"kind": "standard-staging-play", "prefix": "host-play", "status": "preparing"}
        smoke.context_staging_action = event
        smoke.context_staging_records.append(event)
        return smoke, smoke.find_action(root, "game-play"), event, receipt

    def test_scoped_play_receipt_precedes_transport_and_acknowledgement_cannot_repeat(self):
        smoke, action, event, receipt = self.prepare_play()
        smoke.tap_node(action, "game-play")
        self.assertIs(receipt, event["input_xml"])
        self.assertEqual("input-acknowledged", event["status"])
        self.assertEqual([[{"status": "input-requested", "xml_exists": True}]], smoke.input_states)
        with self.assertRaisesRegex(engine.ObservationFailure, "never be repeated"):
            smoke.tap_node(action, "game-play")
        self.assertEqual(1, len(smoke.transport_calls))
        smoke, action, event, _ = self.prepare_play()
        smoke.observations["standard_ui"].clear()
        with self.assertRaises(KeyError):
            smoke.tap_node(action, "game-play")
        self.assertEqual([], smoke.transport_calls)
        self.assertEqual("preparing", event["status"])

    def test_deadline_before_shell_input_stops_transport_and_uncertain_input_stays_failure(self):
        for incomplete, status, expected in ((False, None, focused.adaptive.Unavailable),
                (False, "input-requested", engine.ObservationFailure),
                (False, "input-acknowledged", engine.ObservationFailure),
                (True, None, engine.ObservationFailure)):
            smoke = self.host([table_tree()[0]])
            smoke.input_incomplete, smoke.context_staging_deadline = incomplete, 0
            smoke.context_staging_action = None if status is None else {"status": status}
            with self.subTest(incomplete=incomplete, status=status), self.assertRaises(expected):
                smoke.adb("shell", "input", "tap", "40", "60")
            self.assertEqual([], smoke.transport_calls)
            self.assertEqual(incomplete, smoke.input_incomplete)

    def test_uncertain_staged_play_keeps_its_requested_receipt_and_forbids_further_input(self):
        smoke, action, event, receipt = self.prepare_play()
        smoke.transport_error = subprocess.TimeoutExpired(["adb", "shell", "input"], 20)
        with self.assertRaisesRegex(engine.ObservationFailure, "transport did not complete"):
            smoke.tap_node(action, "game-play")
        self.assertTrue(smoke.input_incomplete)
        self.assertEqual("input-requested", event["status"])
        self.assertIs(receipt, event["input_xml"])
        with self.assertRaisesRegex(engine.ObservationFailure, "Uncertain prior input"):
            smoke.adb("shell", "input", "keyevent", "KEYCODE_BACK")
        self.assertEqual(1, len(smoke.transport_calls))


class StagingHandTests(unittest.TestCase):
    """Original run-9 starting XML plus explicit host-only later scroll/tap responses."""
    @staticmethod
    def hand_frame(*, shown, clipped=False):
        root = ET.Element("hierarchy", rotation="1")
        table = node(root, tag="game-table", bounds="[136,271][1516,720]")
        pane = node(table, bounds="[136,271][1516,720]", scrollable="true")
        hand = node(pane, tag="game-hand", bounds="[136,271][1516,610]")
        node(hand, tag="game-hide-hand" if shown else "game-reveal-hand",
             text="Hide hand" if shown else "Show hand", clickable="true",
             bounds="[171,150][600,250]" if clipped else "[171,350][600,450]")
        if shown:
            node(hand, tag="game-card-0", bounds="[171,470][1481,550]",
                 **{"content-desc": "Star. Card 1 of 5."})
        return root

    def host(self, frames, *, original_first=False):
        directory = tempfile.TemporaryDirectory(prefix="partydeck-staging-hand-host-")
        self.addCleanup(directory.cleanup)
        smoke = StagingUiHost(Path(directory.name), frames)
        smoke.display_size = [720, 1600]
        if original_first:
            path = SCRIPTS / "tests/fixtures/android-focused-34568971032/debug-post-progression.xml"
            raw = path.read_bytes()
            self.assertEqual("ea61b13aaa764e0529224ea90c5b480c93e2376643c2e6431e1288feb6de44b7",
                             hashlib.sha256(raw).hexdigest())
            smoke.frames.insert(0, raw)
        return smoke

    def virtual_wait_clock(self):
        elapsed = [0.0]
        def advance(seconds):
            elapsed[0] += seconds
        for mock in (patch.object(session.ui.time, "monotonic", side_effect=lambda: elapsed[0]),
                     patch.object(session.ui.time, "sleep", side_effect=advance)):
            mock.start()
            self.addCleanup(mock.stop)

    def test_run9_private_hand_without_toggles_discovers_hide_once_and_then_proves_concealment(self):
        smoke = self.host([self.hand_frame(shown=True), self.hand_frame(shown=False)], original_first=True)
        original = smoke.dump_ui()
        self.assertIsNotNone(session.tagged_node(original, "game-card-4"))
        self.assertIsNone(session.tagged_node(original, "game-hide-hand"))
        self.assertIsNone(session.tagged_node(original, "game-reveal-hand"))
        self.assertIsNotNone(smoke.find(original, "game-play", enabled=False))
        with patch.object(session.ui.time, "sleep", return_value=None):
            smoke.conceal_after_staging_play("host-run9")
            smoke.assert_concealed()
        self.assertEqual(["swipe", "tap"], [call[2] for call in smoke.transport_calls])
        event = smoke.context_staging_records[0]
        self.assertEqual("game-hide-hand", event["control"])
        self.assertEqual("input-acknowledged", event["status"])
        receipt = event["control_xml"]
        self.assertEqual(smoke.frames[1], (smoke.output / receipt["file"]).read_bytes())
        self.assertIsNotNone(session.tagged_node(smoke.ui_root, "game-reveal-hand"))
        self.assertIsNone(session.tagged_node(smoke.ui_root, "game-card-0"))

    def test_already_concealed_hand_needs_no_input(self):
        smoke = self.host([self.hand_frame(shown=False)])
        smoke.conceal_after_staging_play("host-concealed")
        smoke.assert_concealed()
        self.assertEqual([], smoke.transport_calls)
        self.assertEqual("game-reveal-hand", smoke.context_staging_records[0]["control"])
        self.assertEqual("control-observed", smoke.context_staging_records[0]["status"])

    def test_clipped_hide_requires_new_visible_geometry_before_input(self):
        smoke = self.host([self.hand_frame(shown=True, clipped=True),
                           self.hand_frame(shown=True), self.hand_frame(shown=False)])
        with patch.object(session.ui.time, "sleep", return_value=None):
            smoke.conceal_after_staging_play("host-clipped")
        self.assertEqual(["swipe", "tap"], [call[2] for call in smoke.transport_calls])
        geometry = [json.loads(line) for line in (smoke.output / "input-geometry.log").read_text().splitlines()]
        self.assertEqual([171, 350, 600, 450], geometry[-1]["bounds"])
        self.assertEqual("game-hide-hand", geometry[-1]["label"])

    def test_invalid_current_table_or_contradictory_controls_fail_before_input(self):
        for kind in ("both-controls", "outside-table", "problem", "result", "foreign-table"):
            root = self.hand_frame(shown=True)
            if kind == "both-controls":
                node(session.tagged_node(root, "game-hand"), tag="game-reveal-hand")
            elif kind == "outside-table":
                hand = session.tagged_node(root, "game-hand")
                hide = session.tagged_node(root, "game-hide-hand")
                hand.remove(hide)
                root.append(hide)
            elif kind == "problem":
                node(root, tag="problem-panel")
            elif kind == "result":
                node(root, tag="game-round-result")
            else:
                session.tagged_node(root, "game-table").set("package", "foreign.app")
            smoke = self.host([root])
            with self.subTest(kind=kind), self.assertRaises(engine.ObservationFailure):
                smoke.conceal_after_staging_play("host-invalid")
            self.assertEqual([], smoke.transport_calls)

    def test_uncertain_discovery_swipe_or_hide_tap_stops_all_further_input(self):
        for during_discovery in (True, False):
            smoke = self.host([self.hand_frame(shown=True)], original_first=during_discovery)
            smoke.transport_error = subprocess.TimeoutExpired(["adb", "shell", "input"], 20)
            with self.subTest(during_discovery=during_discovery), \
                 self.assertRaisesRegex(engine.ObservationFailure, "transport did not complete"):
                smoke.conceal_after_staging_play("host-uncertain-hand")
            self.assertTrue(smoke.input_incomplete)
            self.assertEqual(1, len(smoke.transport_calls))
            if not during_discovery:
                self.assertEqual("input-requested", smoke.context_staging_records[0]["status"])
            with self.assertRaisesRegex(engine.ObservationFailure, "Uncertain prior input"):
                smoke.adb("shell", "input", "keyevent", "KEYCODE_BACK")
            self.assertEqual(1, len(smoke.transport_calls))

    def test_acknowledged_but_ineffective_hide_cannot_bypass_strict_context_assertion(self):
        smoke = self.host([self.hand_frame(shown=True)])
        self.virtual_wait_clock()
        smoke.conceal_after_staging_play("host-ineffective")
        with self.assertRaisesRegex(RuntimeError, "game-reveal-hand.*45 seconds"):
            smoke.observe_context("host-after-ineffective", allow_opening=True)
        self.assertEqual(1, sum(call[2] == "tap" for call in smoke.transport_calls))
        self.assertEqual("input-acknowledged", smoke.context_staging_records[0]["status"])

    def test_initial_or_returned_context_never_automatically_hides_an_exposed_hand(self):
        for prefix in ("3d-context-initial", "3d-context-return"):
            smoke = self.host([self.hand_frame(shown=True)])
            self.virtual_wait_clock()
            with self.subTest(prefix=prefix), self.assertRaisesRegex(RuntimeError, "game-reveal-hand.*45 seconds"):
                smoke.observe_context(prefix, allow_opening=True)
            self.assertFalse(any(call[2] == "tap" for call in smoke.transport_calls))
            self.assertEqual([], smoke.context_staging_records)


class CleanupHarness(focused.PublicContextScenarios):
    def __init__(self):
        self.session, self.shell_task = session, 4
        self.input_incomplete = self.split_owned = self.fail_next_state = False
        self.context_practice_active = self.shell_owned = True
        self.foreground, self.actions, self.on_home, self.dialog = "Main", [], False, False

    def command(self, *args):
        return SimpleNamespace(returncode=0, stdout="host-capability-double", stderr="")

    def save_observation(self, *args, **kwargs):
        pass

    def adb(self, *args):
        if args[:4] == ("shell", "cmd", "package", "resolve-activity"):
            return "com.android.settings/.DisplaySettings\n"
        if args[:3] == ("shell", "am", "start"):
            self.foreground, self.fail_next_state = "Settings", True
            self.actions.append("acknowledged-settings-launch")
            return ""
        raise AssertionError("Unexpected host cleanup command")

    def state(self):
        if self.fail_next_state:
            self.fail_next_state = False
            raise TimeoutError("First state read after acknowledged companion launch failed")
        return {"host_owned_shell": self.shell_owned, "foreground": self.foreground}

    def require_shell(self, state):
        engine.require(state["host_owned_shell"], "Owned shell changed")
        self.actions.append("verify-owned-shell")

    def focus_shell_task(self):
        self.actions.append("focus-owned-shell")
        self.foreground = "Main"

    def wait_activity(self, component, **kwargs):
        engine.require(self.foreground == "Main", "Cleanup cannot observe Main while Settings owns foreground")

    def dismiss_split_picker(self, name):
        self.actions.append("dismiss-current-picker-if-present")

    def dump_ui(self):
        if not self.on_home:
            return table_tree()[0]
        root = ET.Element("hierarchy")
        node(root, tag="home-practice")
        return root

    def assert_no_private_semantics(self, root):
        session.GodotSessionSmoke.assert_no_private_semantics(root)

    def find_action(self, root, tag):
        return session.tagged_node(root, tag)

    def back(self):
        engine.require(self.foreground == "Main" and not self.on_home, "Back is outside the owned practice")
        self.dialog = True
        self.actions.append("practice-back")

    def leave_dialog(self, name):
        engine.require(self.dialog, "No current practice confirmation")

    def tap_action(self, tag, text):
        engine.require(tag == "leave-confirm" and text == "Leave table" and self.dialog,
                       "Unexpected cleanup action")
        self.on_home, self.dialog = True, False
        self.actions.append("confirmed-practice-leave")

    def wait_for_action(self, tag, **kwargs):
        engine.require(self.on_home and tag == "home-practice", "Home was not reached")

    def capture_evidence(self, name, component):
        engine.require(self.on_home, "Cleanup capture is not Home")
        self.actions.append("home-capture")


class CleanupTests(unittest.TestCase):
    def test_early_companion_observation_failure_refocuses_the_verified_owned_practice(self):
        smoke = CleanupHarness()
        with patch.object(focused.adaptive, "split_capability"), self.assertRaises(TimeoutError):
            smoke.enter_context_split()
        self.assertEqual("Settings", smoke.foreground)
        self.assertFalse(smoke.split_owned)
        smoke.end_context_practice()
        self.assertEqual(["acknowledged-settings-launch", "verify-owned-shell", "focus-owned-shell",
            "dismiss-current-picker-if-present", "practice-back", "confirmed-practice-leave", "home-capture"], smoke.actions)
        self.assertFalse(smoke.context_practice_active)

    def test_changed_shell_identity_prevents_task_refocus_or_leave_input(self):
        smoke = CleanupHarness()
        smoke.shell_owned = False
        with self.assertRaisesRegex(engine.ObservationFailure, "Owned shell changed"):
            smoke.end_context_practice()
        self.assertEqual([], smoke.actions)
        self.assertTrue(smoke.context_practice_active)


class InputAdmissionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="partydeck-context-host-inputs-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.bundle, self.package = self.root / "bundle", self.root / "package-inputs"
        self.bundle.mkdir()
        self.package.mkdir()
        self.current = dict(sourceRevision="a" * 40, runId="42", runAttempt="1", repository="owner/project")
        env = dict(GITHUB_SHA=self.current["sourceRevision"], GITHUB_RUN_ID="42", GITHUB_RUN_ATTEMPT="1",
                   GITHUB_REPOSITORY="owner/project")
        (self.root / "scripts").mkdir()
        runner = self.root / focused.RUNNER_PATH
        runner.write_bytes(Path(focused.__file__).read_bytes())
        self.helper = self.root / "scripts/host-helper.py"
        self.helper.write_bytes(b"host-only pin fixture\n")
        pins = {focused.RUNNER_PATH: focused.adaptive.sha256(runner),
                "scripts/host-helper.py": focused.adaptive.sha256(self.helper)}
        for mock in (patch.dict(os.environ, env, clear=True), patch.object(focused.bound_inputs, "ROOT", self.root),
                     patch.object(focused.bound_inputs, "PINS", pins)):
            mock.start()
            self.addCleanup(mock.stop)
        for name in focused.bound_inputs.FILES:
            (self.bundle / name).write_bytes(b"non-runtime provenance fixture: " + name.encode())
        expectation = {"schemaVersion": 1, "profile": "qualification", "modesCsv": "2d,3d"}
        expectation_raw = json.dumps(expectation).encode()
        (self.bundle / "godot-activation-build.json").write_bytes(expectation_raw)
        (self.package / "activation-build-expectation.json").write_bytes(expectation_raw)
        self.manifest = dict(schemaVersion=1, **self.current, androidApi=36, modesCsv="2d,3d",
            qualificationProfile="qualification", checkerSha256=pins, files=focused.bound_inputs.file_records(self.bundle))
        self.args = SimpleNamespace(source_revision=self.current["sourceRevision"], bundle=self.bundle,
            variant="debug", apk=self.bundle / "androidApp-debug.apk", package_inputs=self.package / "package-inputs.json")
        self.report = dict(command="verify", verified=True, consumerContext=self.current.copy(),
            inputs=self.manifest, activationExpectation={"profile": "qualification", "modesCsv": "2d,3d", "modes": ["2d", "3d"]},
            packages={})
        packaged = ('<manifest package="dev.partydeck.app" xmlns:android="http://schemas.android.com/apk/res/android">'
            '<application><meta-data android:name="dev.partydeck.GODOT_ACTIVATION_PROFILE" android:value="qualification"/>'
            '<meta-data android:name="dev.partydeck.GODOT_PRESENTATION_MODES" android:value="2d,3d"/></application></manifest>').encode()
        for variant, name in (("debug", "androidApp-debug.apk"), ("optimized-test-signed", "PartyDeck-release-ci-test-signed.apk")):
            (self.package / (variant + "-packaged-manifest.xml")).write_bytes(packaged)
            self.report["packages"][variant] = dict(verified=True, apkSha256=focused.adaptive.sha256(self.bundle / name),
                packSha256=self.manifest["files"]["partydeck-last-light.pck"]["sha256"],
                embeddedPackSha256=self.manifest["files"]["partydeck-last-light.pck"]["sha256"], manifestExitCode=0,
                manifestSha256=hashlib.sha256(packaged).hexdigest(), packagedActivation=self.report["activationExpectation"])
        helper_manifest = self.package / "continuous-input-packaged-manifest.xml"
        helper_manifest.write_bytes(HELPER_MANIFEST)
        self.report["continuousInput"] = dict(verified=True,
            apkSha256=focused.adaptive.sha256(self.bundle / focused.continuous_touch.APK_NAME),
            manifestSha256=hashlib.sha256(HELPER_MANIFEST).hexdigest(), certificateSha256="c" * 64,
            metadata=focused.continuous_touch.inspect_manifest(HELPER_MANIFEST))
        self.write_manifest()

    def write_manifest(self):
        raw = json.dumps(self.manifest, sort_keys=True).encode()
        (self.bundle / "inputs.json").write_bytes(raw)
        self.args.manifest_sha256 = hashlib.sha256(raw).hexdigest()
        self.report["producerManifestSha256"] = self.args.manifest_sha256
        self.write_report()

    def write_report(self, value=None):
        self.args.package_inputs.write_text(json.dumps(self.report if value is None else value))

    def test_each_exact_variant_and_same_run_later_attempt_are_admitted(self):
        for variant, name in (("debug", "androidApp-debug.apk"), ("optimized-test-signed", "PartyDeck-release-ci-test-signed.apk")):
            self.args.variant, self.args.apk = variant, self.bundle / name
            with self.subTest(variant=variant):
                receipt = focused.admit_inputs(self.args)
                self.assertTrue(receipt["verified"])
                self.assertEqual(self.report["packages"][variant]["apkSha256"], receipt["apk_sha256"])
        os.environ["GITHUB_RUN_ATTEMPT"] = "2"
        self.report["consumerContext"]["runAttempt"] = "2"
        self.write_report()
        self.assertEqual("2", focused.admit_inputs(self.args)["source"]["runAttempt"])

    def test_missing_focused_pin_and_changed_executed_helper_fail(self):
        with patch.dict(focused.bound_inputs.PINS, {}, clear=True), self.assertRaisesRegex(engine.ObservationFailure, "not registered"):
            focused.admit_inputs(self.args)
        self.helper.write_bytes(b"changed host-only helper\n")
        with self.assertRaisesRegex(engine.ObservationFailure, "executed helper|An executed helper"):
            focused.admit_inputs(self.args)

    def test_exact_producer_hash_and_every_apk_pack_receipt_are_rechecked(self):
        original_hash = self.args.manifest_sha256
        self.args.manifest_sha256 = "0" * 64
        with self.assertRaisesRegex(ValueError, "producer output"):
            focused.admit_inputs(self.args)
        self.args.manifest_sha256 = original_hash
        for name in focused.bound_inputs.FILES:
            path = self.bundle / name
            original = path.read_bytes()
            path.write_bytes(original + b" changed")
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "bytes differ"):
                focused.admit_inputs(self.args)
            path.write_bytes(original)

    def test_foreign_revision_run_repository_and_manifest_scope_fail(self):
        for key, changed in (("GITHUB_SHA", "b" * 40), ("GITHUB_RUN_ID", "43"), ("GITHUB_REPOSITORY", "other/project")):
            with self.subTest(key=key), patch.dict(os.environ, {key: changed}), self.assertRaises((ValueError, engine.ObservationFailure)):
                focused.admit_inputs(self.args)
        original = copy.deepcopy(self.manifest)
        for change in ({"androidApi": 35}, {"qualificationProfile": "shipping"}, {"modesCsv": "3d"}, {"checkerSha256": {}}):
            self.manifest = original | change
            self.report["inputs"] = self.manifest
            self.write_manifest()
            with self.subTest(change=change), self.assertRaises(ValueError):
                focused.admit_inputs(self.args)

    def test_unverified_wrong_consumer_or_wrong_manifest_report_fails(self):
        for change in ({"verified": False}, {"verified": 1}, {"command": "record"}, {"consumerContext": {}},
                       {"inputs": {}}, {"producerManifestSha256": "0" * 64}):
            self.write_report(self.report | change)
            with self.subTest(change=change), self.assertRaisesRegex(engine.ObservationFailure, "not the verified manifest"):
                focused.admit_inputs(self.args)

    def test_package_hash_activation_and_success_fields_cannot_be_substituted(self):
        original = copy.deepcopy(self.report)
        for change in ({"verified": False}, {"apkSha256": "0" * 64}, {"packSha256": "0" * 64},
                       {"embeddedPackSha256": "0" * 64}, {"manifestExitCode": 1}, {"manifestExitCode": False},
                       {"manifestSha256": "0" * 64}, {"packagedActivation": {}}):
            modified = copy.deepcopy(original)
            modified["packages"]["debug"].update(change)
            self.write_report(modified)
            with self.subTest(change=change), self.assertRaises(engine.ObservationFailure):
                focused.admit_inputs(self.args)

    def test_original_activation_documents_are_hashed_and_parsed_again(self):
        for filename in ("activation-build-expectation.json", "debug-packaged-manifest.xml"):
            path = self.package / filename
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with self.subTest(filename=filename), self.assertRaisesRegex(engine.ObservationFailure, "bytes"):
                focused.admit_inputs(self.args)
            path.write_bytes(original)
        path = self.package / "debug-packaged-manifest.xml"
        path.write_bytes(path.read_bytes().replace(b'android:value="qualification"', b'android:value="shipping"'))
        self.report["packages"]["debug"]["manifestSha256"] = focused.adaptive.sha256(path)
        self.write_report()
        with self.assertRaisesRegex(ValueError, "actual APK activation"):
            focused.admit_inputs(self.args)

    def test_wrong_variant_path_and_indirect_or_duplicate_report_are_rejected(self):
        self.args.apk = self.bundle / "PartyDeck-release-ci-test-signed.apk"
        with self.assertRaisesRegex(engine.ObservationFailure, "variant input"):
            focused.admit_inputs(self.args)
        self.args.apk = self.bundle / "androidApp-debug.apk"
        raw = self.args.package_inputs.read_text()
        self.args.package_inputs.write_text(raw[:-1] + ', "verified": true}')
        with self.assertRaisesRegex(engine.ObservationFailure, "Duplicate"):
            focused.admit_inputs(self.args)
        self.args.package_inputs.unlink()
        target = self.package / "indirect-report.json"
        target.write_text(raw)
        self.args.package_inputs.symlink_to(target)
        with self.assertRaisesRegex(engine.ObservationFailure, "original verified"):
            focused.admit_inputs(self.args)


class MainStatusTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="partydeck-context-host-main-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.apk = self.root / "host-only.apk"
        self.apk.write_bytes(b"host-only-main-test; never installed")
        self.argv = ["--session-checker", str(SCRIPTS / "smoke-android-godot-session.py"), "--serial", "host-double",
            "--apk", str(self.apk), "--source-revision", "a" * 40, "--variant", "debug", "--bundle", str(self.root),
            "--package-inputs", str(self.root / "package-inputs.json"), "--manifest-sha256", "b" * 64,
            "--output", str(self.root / "output")]

    def main(self, *, run_error=None, missing=False, unsupported=False, admission_error=None, cleanup_error=False,
             helper_error=None):
        instances = []
        class MainBase:
            pass
        class MainAdaptive:
            def __init__(self, session, serial, output, variant, font_scale, hold_ms):
                self.output, self.session = output, session
                self.identity, self.checks, self.captures, self.adaptive_observations, self.steps = {}, {}, [], [], []
                self.stage, self.logcat_started, self.input_incomplete = "initialization", False, False
                self.calls, self.setup_called = [], False
                self.helper_installed, self.run_called = False, False
                instances.append(self)
            def adb(self, *args, **kwargs):
                self.calls.append(args)
                return "free"
            def save_observation(self, *args, **kwargs):
                pass
            def setup_session(self, apk):
                self.setup_called = True
                self.checks["installation"] = {"status": "passed"}
            def restore_adaptive(self):
                return ["Host restore failure"] if cleanup_error else []
            def write_json(self, name, value):
                (self.output / name).write_text(json.dumps(value))
        fake_session = SimpleNamespace(GodotSessionSmoke=MainBase, ui=SimpleNamespace(redacted=lambda value: value),
            utc_now=lambda: "host-only-time", fresh_output=lambda path: path.mkdir(), UnsupportedCheck=session.UnsupportedCheck)
        def install(smoke, bundle, identity):
            engine.require(smoke.setup_called, "The owned app must be set up before helper installation.")
            if helper_error:
                raise helper_error
            smoke.helper_installed = True
        def run(smoke):
            engine.require(smoke.helper_installed, "The same-run helper must be installed before practice.")
            smoke.run_called = True
            if run_error:
                raise run_error
            smoke.checks.update({name: {"status": "passed"} for name in focused.REQUIRED_CHECKS})
            if missing:
                del smoke.checks[focused.REQUIRED_CHECKS[-1]]
            if unsupported:
                smoke.checks["3d.context-short-split"] = {"status": "unsupported"}
        with patch.object(focused.adaptive, "load_session", return_value=fake_session), \
             patch.object(focused.adaptive, "AdaptiveScenarios", MainAdaptive), \
             patch.object(focused.PublicContextScenarios, "run_public_context", run), \
             patch.object(focused, "admit_inputs", side_effect=admission_error,
                          return_value={"host_double": True, "continuous_input_helper": {"host_double": True}}), \
             patch.object(focused.continuous_touch, "install_helper", side_effect=install), \
             redirect_stdout(io.StringIO()):
            try:
                status = focused.main(self.argv)
            finally:
                self.instances = instances
        return status, json.loads((self.root / "output/godot-public-context-result.json").read_text())

    def test_success_requires_all_checks_and_still_leaves_pixel_acceptance_pending(self):
        status, result = self.main()
        self.assertEqual(0, status)
        self.assertEqual("passed-automated-geometry-awaiting-pixel-review", result["status"])
        self.assertEqual("pending-independent-review", result["public_context_pixel_acceptance"])
        self.assertEqual(["3d"], result["modes"])
        self.assertEqual("2.0", result["font_scale"])

    def test_incomplete_required_checks_and_failed_cleanup_cannot_report_success(self):
        status, result = self.main(missing=True)
        self.assertEqual(1, status)
        self.assertEqual("failed", result["status"])
        self.assertIn("did not all complete", result["error"])

    def test_failed_environment_restore_makes_the_run_fail(self):
        status, result = self.main(cleanup_error=True)
        self.assertEqual(1, status)
        self.assertEqual("failed", result["status"])

    def test_unsupported_geometry_is_never_reported_as_passed(self):
        status, result = self.main(unsupported=True)
        self.assertEqual(2, status)
        self.assertEqual("unsupported", result["status"])

    def test_rejected_input_binding_performs_no_adb_or_installation(self):
        status, result = self.main(admission_error=ValueError("Host binding rejected"))
        self.assertEqual(1, status)
        self.assertEqual("failed", result["status"])
        self.assertEqual([], self.instances[0].calls)
        self.assertFalse(self.instances[0].setup_called)

    def test_failed_helper_installation_cannot_start_practice(self):
        status, result = self.main(helper_error=engine.ObservationFailure("Host helper install failure"))
        self.assertEqual(1, status)
        self.assertEqual("failed", result["status"])
        self.assertTrue(self.instances[0].setup_called)
        self.assertFalse(self.instances[0].helper_installed)
        self.assertFalse(self.instances[0].run_called)

    def test_interrupt_propagates_but_writes_a_failed_receipt(self):
        with self.assertRaises(KeyboardInterrupt):
            self.main(run_error=KeyboardInterrupt())
        result = json.loads((self.root / "output/godot-public-context-result.json").read_text())
        self.assertEqual("failed", result["status"])
        self.assertEqual("KeyboardInterrupt", result["error"])

    def test_cli_cannot_expand_modes_font_scale_or_omit_variant_binding(self):
        parser = focused.argument_parser()
        for extra in (("--modes", "2d"), ("--font-scale", "1.0"), ("--variant", "release")):
            with self.subTest(extra=extra), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser.parse_args(self.argv + list(extra))
        without_variant = self.argv.copy()
        index = without_variant.index("--variant")
        del without_variant[index:index + 2]
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(without_variant)


if __name__ == "__main__":
    unittest.main(verbosity=2)
