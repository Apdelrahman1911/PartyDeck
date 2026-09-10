"""Host replay regressions for split ownership/recovery; no device qualification."""

import copy
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import smoke_android_godot_adaptive as runner

session = runner.load_session(Path(runner.__file__).with_name("smoke-android-godot-session.py"))
MAIN = session.MAIN_COMPONENT
NATIVE = session.NATIVE_COMPONENT
SETTINGS = "com.android.settings/com.android.settings.Settings$DisplaySettingsActivity"
HELP = (
    "  Window Manager Shell commands:\n"
    "    splitscreen\n"
    "      moveToSideStage <taskId> <SideStagePosition>\n"
    "      exitSplitScreen <taskId>\n"
    "    help\n"
)


class SplitReplay(runner.AdaptiveScenarios, session.GodotSessionSmoke):
    """Real scenario/check/recovery methods over a small synthetic device boundary."""

    def __init__(self, output):
        super().__init__(session, "host-replay-only", output, "debug", "1.0", 30000)
        self.shell_identity = {"pid": 601, "uid": 10234, "name": session.PACKAGE}
        self.shell_task = 19
        self.focus = MAIN
        self.screen = "home"
        self.actual_split = False
        self.child_pid = None
        self.next_child_pid = 700
        self.revealed = False
        self.selected = False
        self.rotation = 1
        self.display_size = (720, 1600)
        self.events = []
        self.commands = []
        self.recorder_active = False
        self.picker_open = False
        self.fail_picker_done = False
        self.unavailable_recording = None
        self.failed_recording = None
        self.resolver_available = True
        self.move_failure = None
        self.ignore_exit = False
        self.fail_standard = False
        self.baseline = {"public": "fixed public anchor", "first_card": "fixed private sample"}

    def dump_ui(self, deadline=None):
        root = ET.Element("hierarchy", rotation=str(self.rotation))
        if self.focus == NATIVE:
            ET.SubElement(root, "node", {"package": session.PACKAGE,
                "resource-id": "native-standard-table", "text": "Standard table",
                "class": "android.widget.Button", "enabled": "true", "clickable": "true",
                "bounds": "[100,100][600,180]"})
        elif self.picker_open:
            def node(parent, kind, bounds, **attrs):
                return ET.SubElement(parent, "node", {"package": session.PACKAGE, "class": kind,
                    "bounds": bounds, "enabled": "true", "clickable": "false", **attrs})
            panel = node(root, "android.view.View", "[50,40][730,680]")
            node(panel, "android.widget.TextView", "[80,60][320,100]", text="Table style")
            node(panel, "android.widget.ScrollView", "[70,120][710,560]", scrollable="true")
            done = node(panel, "android.widget.Button", "[520,600][680,650]", clickable="true",
                        **{"resource-id": "presentation-picker-done"})
            node(done, "android.widget.TextView", "[560,610][630,640]", text="Done")
        self.bind_ui(root)
        return root

    def record(self, message):
        self.steps.append(message)

    def state(self):
        def activity(target, task, pid, bounds, mode, visible):
            cfg = {
                "orientation": "land", "width_dp": (bounds[2] - bounds[0]) // 2,
                "height_dp": 360, "density_dpi": 280, "font_scale": 1.0,
                "layout_direction": "ldltr", "window_size": [bounds[2] - bounds[0], bounds[3] - bounds[1]],
                "bounds": bounds, "windowing_mode": mode, "display_rotation": self.rotation,
            }
            return {
                "component": target, "task_id": task, "app_pid": pid, "record_id": target,
                "display_id": 0, "configuration": cfg, "visible": visible,
                "client_visible": visible, "window": {"component": target, "window_id": target},
            }
        app_mode = "multi-window" if self.actual_split else "fullscreen"
        app_bounds = [0, 0, 780, 720] if self.actual_split else [0, 0, 1600, 720]
        app_target = NATIVE if self.child_pid is not None else MAIN
        records = [activity(app_target, self.shell_task, self.child_pid or 601, app_bounds, app_mode, True)]
        if self.child_pid is not None:
            records.append(activity(MAIN, self.shell_task, 601, app_bounds, app_mode, False))
        if self.companion_task is not None:
            records.append(activity(SETTINGS, self.companion_task, 800,
                                    [820, 0, 1600, 720] if self.actual_split else [0, 0, 1600, 720],
                                    app_mode, self.actual_split or self.focus == SETTINGS))
        focus = next((row for row in records if row["component"] == self.focus), None)
        processes = [self.shell_identity]
        if self.child_pid is not None:
            processes.append({"pid": self.child_pid, "uid": 10234, "name": session.RENDERER_PROCESS})
        return copy.deepcopy({
            "foreground": focus, "activities": records, "processes": processes,
            "shell_pids": [601], "renderer_pids": [] if self.child_pid is None else [self.child_pid],
            "display": {"size": [1600, 720], "rotation": self.rotation,
                        "landscape": 1, "seascape": 3, "portrait": 0},
        })

    def command(self, *args, **kwargs):
        if args in (("shell", "am", "supports-multiwindow"),
                    ("shell", "am", "supports-split-screen-multi-window")):
            output = "true\n"
        elif args == ("shell", "wm", "shell", "help"):
            output = HELP
        else:
            raise AssertionError(("Unexpected host replay command", args))
        self.commands.append(args)
        return subprocess.CompletedProcess(args, 0, output, "")

    def adb(self, *args, **kwargs):
        self.commands.append(args)
        if args[:3] == ("shell", "input", "tap"):
            self.tap_action("presentation-picker-done" if self.picker_open else "native-standard-table", scroll=None)
            return ""
        if args[:4] == ("shell", "wm", "user-rotation", "-d"):
            if len(args) == 7:
                self.rotation = int(args[-1])
            return "lock " + str(self.rotation)
        if args[:5] == ("shell", "cmd", "package", "resolve-activity", "--brief"):
            return SETTINGS + "\n" if self.resolver_available else "No activity found\n"
        if args[:4] == ("shell", "am", "start", "-W"):
            self.companion_task, self.focus = 21, SETTINGS
            return ""
        if args[:4] == ("shell", "am", "task", "focus"):
            self.focus = NATIVE if self.child_pid is not None else MAIN
            return ""
        if args[:4] == ("shell", "wm", "shell", "splitscreen"):
            self.events.append(("split-command", args[4], self.split_owned, self.recorder_active))
            if args[4] == "moveToSideStage":
                if self.move_failure == "before":
                    raise runner.ObservationFailure("Injected move transport failure before effect")
                self.actual_split = True
                self.child_pid, self.focus, self.revealed, self.selected = None, MAIN, False, False
                if self.move_failure == "after":
                    raise runner.ObservationFailure("Injected move transport failure after possible effect")
            elif args[4] == "exitSplitScreen":
                # Android source: inactive split returns without changing the app Activity.
                if self.actual_split and not self.ignore_exit:
                    self.actual_split = False
                    self.child_pid, self.focus, self.revealed, self.selected = None, MAIN, False, False
            else:
                raise AssertionError(args)
            return ""
        raise AssertionError(("Unexpected host replay adb call", args))

    def tap_action(self, tag, fallback=None, scroll="up"):
        if self.recorder_active:
            raise AssertionError("Recovery UI ran before the recorder context completed")
        self.events.append(("tap", tag))
        if tag == "home-practice":
            self._require(self.focus == MAIN and self.screen == "home", "Practice requires the real home state")
            self.screen, self.revealed, self.selected = "match", False, False
        elif tag == "presentation-picker-done":
            if self.fail_picker_done:
                raise runner.ObservationFailure("Injected picker dismissal failure")
            self._require(self.focus == MAIN and self.picker_open, "Done requires the actual picker")
            self.picker_open = False
        elif tag == "native-standard-table":
            if self.fail_standard:
                raise runner.ObservationFailure("Injected ordinary Standard return failure")
            self._require(self.focus == NATIVE, "Standard requires native foreground")
            self.focus, self.child_pid, self.revealed, self.selected = MAIN, None, False, False
        elif tag == "native-leave-table":
            self._require(self.focus == NATIVE, "Leave requires native foreground")
            self.focus, self.child_pid, self.screen, self.revealed = MAIN, None, "leave-dialog", False
        elif tag == "leave-confirm":
            self._require(self.focus == MAIN and self.screen == "leave-dialog", "Leave requires its real confirmation")
            self.screen, self.revealed, self.selected = "home", False, False
        else:
            raise AssertionError(tag)

    @staticmethod
    def _require(value, message):
        if not value:
            raise runner.ObservationFailure(message)

    def wait_for_human_turn(self):
        self._require(self.focus == MAIN and self.screen == "match", "No human-turn match")

    def assert_concealed(self):
        self._require(not self.revealed and not self.selected, "Hand is not concealed/cleared")

    def observe_match(self, prefix):
        self.wait_for_human_turn()
        self.revealed = True
        return copy.deepcopy(self.baseline)

    def select_first_card(self, prefix):
        self._require(self.focus == MAIN and self.screen == "match" and self.revealed, "No revealed selectable card")
        self.selected = True

    def enter_native(self, mode, prefix, ready=True, *, before_choice=None):
        self._require(self.focus == MAIN and self.screen == "match" and self.selected, "Native entry lacks a fresh selection")
        self.picker_open = True
        self.events.append(("picker", mode, prefix))
        if before_choice is not None:
            before_choice()
        self.events.append(("native-choice", mode, prefix))
        self.picker_open = False
        self.next_child_pid += 1
        self.child_pid, self.focus, self.revealed, self.selected = self.next_child_pid, NATIVE, False, False
        self.events.append(("native-entry", mode, prefix))
        return self.child_pid, self.shell_task, None

    def require_concealed_return(self, baseline, prefix):
        self.wait_activity(MAIN, child_absent=True)
        self.assert_concealed()
        self._require(baseline == self.baseline, "Recovery changed the practice anchor")
        self.events.append(("concealed-return", prefix))
        self.revealed = True
        return {"synthetic_host_continuity": True}

    def leave_dialog(self, prefix):
        self.wait_activity(MAIN, child_absent=True)
        self._require(self.screen == "leave-dialog", "No real leave confirmation state")
        self.assert_concealed()

    def wait_for_action(self, tag, *args, **kwargs):
        self._require(tag == "home-practice" and self.focus == MAIN and self.screen == "home", "Home action is not ready")
        return object()

    def capture_evidence(self, name, target, *args, **kwargs):
        self._require(self.focus == target, "Capture target does not own foreground")
        self.captures.append({"name": name, "host_replay_only": True, "stage": self.stage})

    @contextmanager
    def recording(self, name, state, *, defer_start=False):
        recording = types.SimpleNamespace(width=state["display"]["size"][0], height=state["display"]["size"][1],
                                          finished=False)
        self.events.append(("recorder-created", name, defer_start))
        def start():
            self._require(not self.recorder_active, "Duplicate recorder startup")
            self.recorder_active = True
            self.events.append(("recorder-start", name, self.split_owned))
            if name == self.failed_recording:
                raise runner.ObservationFailure("Injected genuine recorder failure")
        def await_started():
            self._require(self.recorder_active, "Startup must precede admission")
            self.events.append(("recorder-joined", name))
            if name == self.unavailable_recording:
                raise runner.Unavailable("Injected recorder startup unavailable")
        recording.start_before_choice = start
        recording.await_started = await_started
        recording.checkpoint = lambda label: self.events.append(("checkpoint", label))
        try:
            if not defer_start:
                start()
                await_started()
            yield recording
        finally:
            recording.finished = True
            self.recorder_active = False
            self.events.append(("recorder-finished", name))


class SplitRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="partydeck-split-recovery-host-test-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        self.clock = 0.0

        def tick():
            self.clock += 0.25
            return self.clock

        self.addCleanup(patch.stopall)
        patch.object(runner.time, "monotonic", side_effect=tick).start()
        patch.object(runner.time, "sleep", return_value=None).start()
        self.smoke = SplitReplay(self.output)

    def split_commands(self):
        return [event[1] for event in self.smoke.events if event[0] == "split-command"]

    def assert_home(self):
        self.assertEqual((MAIN, "home", None, False, False),
                         (self.smoke.focus, self.smoke.screen, self.smoke.child_pid,
                          self.smoke.actual_split, self.smoke.split_owned))

    def test_unavailable_entry_recovers_home_without_split_mutation(self):
        self.smoke.unavailable_recording = "2d-split-entry"
        self.smoke.split_scenario("2d")
        self.assert_home()
        self.assertEqual([], self.split_commands())
        self.assertEqual("unsupported", self.smoke.checks["2d-split.entry-after-ready"]["status"])
        self.assertNotIn("2d-split.stable-split-launch-exit", self.smoke.checks)
        self.assertNotIn("2d-split.fullscreen-reentry-leave-home", self.smoke.checks)
        self.assertEqual([], self.smoke.restore_adaptive())
        # Exercise the next mode's actual preconditions, which failed in the retained run.
        self.smoke.set_rotation(1, MAIN, "land")
        self.smoke.begin_practice("next-baseline")
        self.smoke.enter_native("3d", "next-native")
        self.assertEqual(("native-entry", "3d", "next-native"), self.smoke.events[-1])

    def test_early_unsupported_companion_resolution_does_not_invent_a_match(self):
        self.smoke.resolver_available = False
        self.smoke.split_scenario("2d")
        self.assert_home()
        self.assertEqual("unsupported", self.smoke.checks["2d-split.entry-after-ready"]["status"])
        self.assertFalse(any(event[0] in ("native-entry", "tap", "recorder-start") for event in self.smoke.events))

    def test_genuine_recorder_failure_stays_failed_without_claiming_split_ownership(self):
        self.smoke.failed_recording = "2d-split-entry"
        with self.assertRaisesRegex(runner.ObservationFailure, "genuine recorder failure"):
            self.smoke.split_scenario("2d")
        self.assertEqual("failed", self.smoke.checks["2d-split.entry-after-ready"]["status"])
        self.assertFalse(self.smoke.split_owned)
        self.assertEqual([], self.split_commands())

    def test_ownership_starts_at_the_request_and_survives_ambiguous_command_failure(self):
        for effect in ("before", "after"):
            with self.subTest(effect=effect):
                output = self.output / effect
                output.mkdir()
                self.smoke = SplitReplay(output)
                self.smoke.move_failure = effect
                with self.assertRaisesRegex(runner.ObservationFailure, "move transport failure"):
                    self.smoke.split_scenario("2d")
                self.assertTrue(self.smoke.split_owned)
                start = next(event for event in self.smoke.events if event[0] == "recorder-start")
                self.assertFalse(start[2], "Recorder startup itself does not own split")
                move = next(event for event in self.smoke.events if event[0] == "split-command")
                self.assertEqual(("moveToSideStage", True, True), move[1:])
                self.assertEqual("failed", self.smoke.checks["2d-split.entry-after-ready"]["status"])
                self.assertEqual([], self.smoke.restore_adaptive())
                self.assertFalse(self.smoke.split_owned)
                self.assertIsNone(self.smoke.child_pid)
                self.assertEqual("failed", self.smoke.checks["2d-split.entry-after-ready"]["status"])

    def test_unavailable_exit_recovers_owned_split_and_keeps_downstream_scope_unreached(self):
        self.smoke.unavailable_recording = "2d-split-exit"
        self.smoke.split_scenario("2d")
        self.assert_home()
        self.assertEqual(["moveToSideStage", "exitSplitScreen"], self.split_commands())
        self.assertEqual("passed", self.smoke.checks["2d-split.entry-after-ready"]["status"])
        self.assertEqual("unsupported", self.smoke.checks["2d-split.stable-split-launch-exit"]["status"])
        self.assertNotIn("2d-split.fullscreen-reentry-leave-home", self.smoke.checks)
        self.assertTrue(any("exit-unsupported" in capture["name"] for capture in self.smoke.captures))

    def test_ordinary_recovery_failure_does_not_relabel_the_unsupported_check(self):
        self.smoke.unavailable_recording = "2d-split-entry"
        self.smoke.fail_standard = True
        with self.assertRaisesRegex(runner.ObservationFailure, "ordinary Standard return failure"):
            self.smoke.split_scenario("2d")
        self.assertEqual("unsupported", self.smoke.checks["2d-split.entry-after-ready"]["status"])
        self.assertNotIn("2d-split.stable-split-launch-exit", self.smoke.checks)
        self.assertNotEqual("home", self.smoke.screen)

    def test_noop_owned_exit_uses_standard_without_pretending_to_finish_the_practice(self):
        self.smoke.begin_practice("setup")
        self.smoke.enter_native("2d", "setup")
        self.smoke.split_owned = True
        self.smoke.cleanup_errors.append("Retained prior recorder diagnostic")
        self.assertEqual(["Retained prior recorder diagnostic"], self.smoke.restore_adaptive())
        self.assertEqual(["exitSplitScreen"], self.split_commands())
        self.assertIn(("tap", "native-standard-table"), self.smoke.events)
        self.assertEqual((MAIN, "match", None, False),
                         (self.smoke.focus, self.smoke.screen, self.smoke.child_pid, self.smoke.split_owned))

    def test_failed_fullscreen_observation_keeps_cleanup_owned_and_reported(self):
        self.smoke.actual_split = True
        self.smoke.split_owned = True
        self.smoke.ignore_exit = True
        self.smoke.companion_task = 21
        errors = self.smoke.restore_adaptive()
        self.assertTrue(self.smoke.split_owned)
        self.assertEqual(1, len(errors))
        self.assertIn("Owned split cleanup", errors[0])
        self.assertIn("configuration/window mode did not stabilize", errors[0])

    def test_native_in_a_different_task_is_not_tapped_by_recovery(self):
        self.smoke.begin_practice("setup")
        self.smoke.enter_native("2d", "setup")
        wrong = self.smoke.state()
        wrong["foreground"]["task_id"] = 99
        with patch.object(self.smoke, "state", return_value=wrong):
            with self.assertRaisesRegex(runner.ObservationFailure, "different task"):
                self.smoke.restore_split_window()
        self.assertNotIn(("tap", "native-standard-table"), self.smoke.events)

    def test_final_geometry_cannot_clear_ownership_with_a_wrong_task_or_live_child(self):
        for wrong_task, children in ((99, []), (19, [702])):
            with self.subTest(task=wrong_task, children=children):
                self.smoke.split_owned = True
                final = self.smoke.state()
                final["foreground"]["task_id"] = wrong_task
                final["renderer_pids"] = children
                with patch.object(self.smoke, "stable_activity", return_value=final):
                    with self.assertRaisesRegex(runner.ObservationFailure, "renderer retired"):
                        self.smoke.restore_split_window()
                self.assertTrue(self.smoke.split_owned)

    def test_incomplete_input_prevents_any_split_or_recovery_ui_mutation(self):
        self.smoke.input_incomplete = True
        self.smoke.split_owned = True
        with self.assertRaisesRegex(runner.ObservationFailure, "Incomplete input"):
            self.smoke.restore_split_window()
        self.assertEqual([], self.smoke.commands)
        self.assertEqual([], self.smoke.events)
        self.assertIn("no further UI mutations", self.smoke.restore_adaptive()[0])

    def test_successful_split_path_keeps_all_original_named_checks(self):
        self.smoke.split_scenario("2d")
        self.assert_home()
        self.assertEqual({
            "2d-split.support", "2d-split.entry-after-ready",
            "2d-split.stable-split-launch-exit", "2d-split.fullscreen-reentry-leave-home",
        }, set(self.smoke.checks))
        self.assertTrue(all(check["status"] == "passed" for check in self.smoke.checks.values()))
        self.assertFalse(any("unsupported-recovery" in row["name"] for row in self.smoke.adaptive_observations))

    def native_cleanup_setup(self):
        self.smoke.begin_practice("setup")
        self.smoke.enter_native("2d", "setup")
        self.smoke.events.clear()
        self.smoke.commands.clear()

    def retire_native(self):
        self.smoke.focus, self.smoke.child_pid = MAIN, None
        self.smoke.revealed, self.smoke.selected = False, False

    def test_native_retirement_during_ui_dump_accepts_main_without_standard_tap(self):
        self.native_cleanup_setup()
        dump = self.smoke.dump_ui

        def retiring_dump(deadline=None):
            self.retire_native()
            return dump(deadline)

        with patch.object(self.smoke, "dump_ui", side_effect=retiring_dump):
            self.smoke.restore_split_window()
        self.assertNotIn(("tap", "native-standard-table"), self.smoke.events)
        self.assertEqual(MAIN, self.smoke.focus)

    def test_native_retirement_after_ui_dump_never_uses_old_coordinates(self):
        self.native_cleanup_setup()
        dump = self.smoke.dump_ui

        def retiring_dump(deadline=None):
            root = dump(deadline)
            self.retire_native()
            return root

        with patch.object(self.smoke, "dump_ui", side_effect=retiring_dump):
            self.smoke.restore_split_window()
        self.assertFalse(any(call[:3] == ("shell", "input", "tap") for call in self.smoke.commands))
        self.assertEqual(MAIN, self.smoke.focus)

    def test_disabled_standard_waits_for_actual_retirement_without_input(self):
        self.native_cleanup_setup()
        dump = self.smoke.dump_ui
        reads = 0

        def closing_dump(deadline=None):
            nonlocal reads
            reads += 1
            root = dump(deadline)
            for node in root.iter("node"):
                node.set("enabled", "false")
            if reads == 3:
                self.retire_native()
            return root

        with patch.object(self.smoke, "dump_ui", side_effect=closing_dump):
            self.smoke.restore_split_window()
        self.assertEqual(3, reads)
        self.assertNotIn(("tap", "native-standard-table"), self.smoke.events)

    def test_expired_observation_budget_cannot_admit_a_native_tap(self):
        self.native_cleanup_setup()
        self.smoke.split_owned = True
        dump = self.smoke.dump_ui

        def late_dump(deadline=None):
            root = dump(deadline)
            self.clock = deadline + 1
            return root

        with patch.object(self.smoke, "dump_ui", side_effect=late_dump):
            with self.assertRaisesRegex(runner.ObservationFailure, "current Standard control"):
                self.smoke.restore_split_window()
        self.assertTrue(self.smoke.split_owned)
        self.assertNotIn(("tap", "native-standard-table"), self.smoke.events)

    def test_target_task_change_after_dump_blocks_native_input(self):
        self.native_cleanup_setup()
        dump = self.smoke.dump_ui
        state = self.smoke.state
        changed = False

        def changing_dump(deadline=None):
            nonlocal changed
            root = dump(deadline)
            changed = True
            return root

        def changing_state():
            result = state()
            if changed:
                result["foreground"]["task_id"] = 99
            return result

        with patch.object(self.smoke, "dump_ui", side_effect=changing_dump), \
                patch.object(self.smoke, "state", side_effect=changing_state):
            with self.assertRaisesRegex(runner.ObservationFailure, "different task"):
                self.smoke.restore_split_window()
        self.assertNotIn(("tap", "native-standard-table"), self.smoke.events)

    def test_old_xml_control_is_rejected_by_the_pinned_viewport_guard(self):
        self.native_cleanup_setup()
        old_root = self.smoke.dump_ui()
        old_control = self.smoke.find_action(old_root, "native-standard-table", "Standard table")
        self.smoke.dump_ui()
        with patch.object(self.smoke, "find_action", return_value=old_control):
            with self.assertRaisesRegex(RuntimeError, "current visible viewport"):
                self.smoke.restore_split_window()
        self.assertNotIn(("tap", "native-standard-table"), self.smoke.events)


if __name__ == "__main__":
    unittest.main()
