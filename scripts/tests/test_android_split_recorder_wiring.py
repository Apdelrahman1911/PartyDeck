"""Split orchestration over a synthetic device; real context/admission/checkpoint/finish.

Observer transport and positive-growth samples are supplied by this boundary.
The separate foundation suite exercises its actual host thread and deadlines.
No device command or media probe/decoder is executed here.
"""

from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import smoke_android_godot_adaptive as runner
import test_android_split_recovery as replay


class RecordingBoundary(runner.OriginalRecording):
    """Supply recorder observations without replacing its production guards."""

    def __init__(self, smoke, name, dimensions):
        super().__init__(smoke, name, dimensions)
        smoke.recorders.append(self)
        smoke.events.append(("recorder-created", name, tuple(dimensions)))
        self.current_checkpoint, self.returncode, self.dead = None, None, False
        if name in smoke.canvas_faults:
            self.width, self.height = smoke.canvas_faults[name]

    def start_before_choice(self):
        runner.require(not self.launch_attempted and not self.smoke.recorder_active, "Duplicate recording")
        runner.require(self.smoke.picker_open, "Recorder hook did not run inside the existing picker")
        self.launch_attempted = self.path_available = True
        self.smoke.recorder_active, self.smoke.active_recording = True, self
        self.observer = object()
        self.process = types.SimpleNamespace(poll=self.poll, wait=self.wait)
        self.uid = 2000
        self.identity = dict(pid=9000 + len(self.smoke.recorders), uid=self.uid,
                             name=self.argv[0], start_ticks=12345)
        self.entry.update(initial_file_sizes=[100, 200], status="recording")
        self.started_successfully = self.name not in self.smoke.missing_growth
        if self.name == self.smoke.unavailable_recording:
            self.started_successfully = False
            self.startup_error = runner.Unavailable("Injected recorder startup unavailable")
        self.startup_done.set()
        self.smoke.events.append(("recorder-start", self.name, self.smoke.split_owned))
        if self.name in self.smoke.setup_errors:
            raise self.smoke.setup_errors[self.name]

    def join_startup(self, cancel=False):
        self.smoke.events.append(("observer-join", self.name, cancel))
        if self.name in self.smoke.unjoined:
            raise runner.ObservationFailure("Injected observer did not join")
        self.observer_joined = True

    def poll(self):
        if self.dead or (self.current_checkpoint and self.smoke.checkpoint_faults.get(self.name) == "dead"):
            return 0
        return self.returncode

    def wait(self, **kwargs):
        self.returncode = 0
        return 0

    def checkpoint(self, label):
        self.current_checkpoint = label
        super().checkpoint(label)
        self.smoke.events.append(("checkpoint", label, self.name))

    def finish(self):
        self.smoke.events.append(("finish-called", self.name))
        try:
            super().finish()
        finally:
            if self.finished:
                self.smoke.recorder_active = False
            self.smoke.events.append(("recorder-finished", self.name, self.finished))


class WiringReplay(replay.SplitReplay):
    recording = runner.AdaptiveScenarios.recording

    def __init__(self, output):
        super().__init__(output)
        self.recorders, self.active_recording = [], None
        self.checkpoint_faults, self.canvas_faults, self.setup_errors = {}, {}, {}
        self.finish_errors, self.entry_errors = {}, {}
        self.missing_growth, self.unjoined = set(), set()

    def save_observation(self, name, **fields):
        self.events.append(("observation", name))
        return super().save_observation(name, **fields)

    def enter_native(self, mode, prefix, ready=True, *, before_choice=None):
        result = super().enter_native(mode, prefix, ready, before_choice=before_choice)
        if prefix in self.entry_errors:
            raise self.entry_errors[prefix]
        return result

    def command(self, *args, **kwargs):
        if args[:3] == ("shell", "test", "-e"):
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:3] == ("shell", "sh", "-c"):
            self.events.append(("recorder-signal", self.active_recording.name))
            runner.require(self.active_recording.observer_joined, "Signal preceded observer join")
            if self.active_recording.name in self.finish_errors:
                raise self.finish_errors[self.active_recording.name]
            return subprocess.CompletedProcess(args, 0, "PARTYDECK_SCREENRECORD_SIGINT\n", "")
        return super().command(*args, **kwargs)

    def adb(self, *args, **kwargs):
        clip = self.active_recording
        fault = self.checkpoint_faults.get(clip.name) if clip else None
        if args[:2] == ("exec-out", "cat"):
            values = clip.argv if fault != "argv" else ["/system/bin/screenrecord", "--other-path"]
            return b"\0".join(item.encode() for item in values) + b"\0"
        if args[:2] == ("shell", "cat") and args[2].startswith("/proc/"):
            if args[2].endswith("/status"):
                uid = clip.uid + (fault == "uid")
                return "Uid:\t" + "\t".join([str(uid)] * 4) + "\n"
            ticks = clip.identity["start_ticks"] + (fault == "lifetime")
            fields = ["S"] + ["0"] * 18 + [str(ticks)]
            return f'{clip.identity["pid"]} (screenrecord) ' + " ".join(fields)
        if args[:3] == ("shell", "stat", "-c"):
            if fault == "ended-during-checkpoint":
                clip.dead = True
            return "199" if fault == "shrunk" else "200"
        if args[0] == "pull":
            runner.require(clip.observer_joined, "Pull preceded observer join")
            Path(args[2]).write_bytes(b"Host fixture only; not a video.")
            return "Host fixture copied"
        if args[:3] == ("shell", "rm", "-f"):
            runner.require(clip.observer_joined, "Path cleanup preceded observer join")
            return ""
        return super().adb(*args, **kwargs)


class SplitRecorderWiringTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="partydeck-split-wiring-host-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        self.clock = 0.0
        self.addCleanup(patch.stopall)
        patch.object(runner, "OriginalRecording", RecordingBoundary).start()
        patch.object(runner, "verify_video", return_value={"synthetic_host_fixture": True}).start()
        patch.object(runner.time, "monotonic", side_effect=self.tick).start()
        patch.object(runner.time, "sleep", return_value=None).start()
        self.smoke = WiringReplay(self.output)

    def tick(self):
        self.clock += 0.01
        return self.clock

    def reset(self, name):
        output = self.output / name
        output.mkdir()
        self.smoke = WiringReplay(output)

    def commands(self):
        return [event for event in self.smoke.events if event[0] == "split-command"]

    def event_index(self, kind, value, start=0):
        return next(index for index, event in enumerate(self.smoke.events[start:], start)
                    if event[0] == kind and event[1] == value)

    def assert_finished_once(self):
        for recording in self.smoke.recorders:
            self.assertTrue(recording.finished)
            self.assertEqual(1, self.smoke.events.count(("finish-called", recording.name)))

    def test_two_transitions_each_use_one_prechoice_recorder_and_live_checkpoint(self):
        for mode in ("2d", "3d"):
            with self.subTest(mode=mode):
                self.reset(mode)
                self.smoke.split_scenario(mode)
                self.assertEqual([mode + "-split-entry", mode + "-split-exit"],
                                 [recording.name for recording in self.smoke.recorders])
                for suffix, command, native_suffix in (("entry", "moveToSideStage", "full"),
                                                        ("exit", "exitSplitScreen", "pane")):
                    name = mode + "-split-" + suffix
                    created = self.event_index("recorder-created", name)
                    started = self.event_index("recorder-start", name)
                    choices = [index for index, event in enumerate(self.smoke.events)
                               if event == ("native-choice", mode, mode + "-split-" + native_suffix)]
                    self.assertEqual(1, len(choices))
                    self.assertLess(created, started)
                    self.assertLess(started, choices[0])
                    joined = self.event_index("observer-join", name)
                    requested = self.event_index("split-command", command)
                    self.assertLess(choices[0], joined)
                    self.assertLess(joined, requested)
                    self.assertEqual(("checkpoint", "before-split-" + suffix + "-request", name),
                                     self.smoke.events[requested - 1])
                    post = self.event_index("checkpoint", "split-" + suffix + "-and-concealed-return-observed")
                    finished = self.event_index("recorder-finished", name)
                    continuity = self.event_index("concealed-return", mode + "-split-" + suffix + "-return")
                    self.assertLess(requested, post)
                    self.assertLess(post, finished)
                    self.assertLess(finished, continuity)
                self.assert_finished_once()
                self.assertTrue(all(recording.argv[1:5] == ["--time-limit", "60", "--size", "1600x720"]
                                    for recording in self.smoke.recorders))
                self.assertEqual("home", self.smoke.screen)
                self.assertTrue(all(item["status"] == "passed" for item in self.smoke.checks.values()))

    def test_real_checkpoint_rejects_dead_or_changed_recorder_before_either_command(self):
        for suffix in ("entry", "exit"):
            for fault in ("argv", "uid", "lifetime", "shrunk", "dead", "ended-during-checkpoint"):
                with self.subTest(transition=suffix, fault=fault):
                    self.reset(suffix + "-" + fault)
                    self.smoke.checkpoint_faults["2d-split-" + suffix] = fault
                    with self.assertRaises(RuntimeError):
                        self.smoke.split_scenario("2d")
                    self.assertEqual([] if suffix == "entry" else ["moveToSideStage"],
                                     [event[1] for event in self.commands()])
                    self.assertEqual(suffix == "exit", self.smoke.split_owned)
                    self.assert_finished_once()

    def test_missing_growth_proof_cannot_be_admitted_by_native_ready(self):
        self.smoke.missing_growth.add("2d-split-entry")
        with self.assertRaisesRegex(RuntimeError, "positive-growth startup proof"):
            self.smoke.split_scenario("2d")
        self.assertIn(("native-entry", "2d", "2d-split-full"), self.smoke.events)
        self.assertEqual([], self.commands())
        self.assertFalse(self.smoke.split_owned)
        self.assert_finished_once()

    def test_pane_sized_canvas_blocks_the_exit_without_clearing_owned_split(self):
        self.smoke.canvas_faults["2d-split-exit"] = [780, 720]
        with self.assertRaisesRegex(RuntimeError, "observed full display"):
            self.smoke.split_scenario("2d")
        self.assertEqual(["moveToSideStage"], [event[1] for event in self.commands()])
        self.assertTrue(self.smoke.split_owned)
        self.assert_finished_once()

    def test_unavailable_startup_preserves_one_ordinary_choice_then_recovers_home(self):
        for suffix, native_suffix, check in (("entry", "full", "entry-after-ready"),
                                             ("exit", "pane", "stable-split-launch-exit")):
            with self.subTest(transition=suffix):
                self.reset(suffix)
                self.smoke.unavailable_recording = "2d-split-" + suffix
                self.smoke.split_scenario("2d")
                self.assertEqual(1, self.smoke.events.count(("native-choice", "2d", "2d-split-" + native_suffix)))
                self.assertEqual("unsupported", self.smoke.checks["2d-split." + check]["status"])
                self.assertNotIn("2d-split.fullscreen-reentry-leave-home", self.smoke.checks)
                self.assertEqual("home", self.smoke.screen)
                self.assertFalse(self.smoke.split_owned)
                if suffix == "exit":
                    self.assertEqual(("exitSplitScreen", True, False), self.commands()[-1][1:])
                else:
                    self.assertEqual([], self.commands())
                self.assert_finished_once()

    def test_setup_failure_dismisses_only_the_picker_after_finish(self):
        primary = runner.ObservationFailure("Primary setup integrity failure")
        self.smoke.setup_errors["2d-split-entry"] = primary
        with self.assertRaises(RuntimeError) as caught:
            self.smoke.split_scenario("2d")
        self.assertIs(primary, caught.exception)
        self.assertFalse(self.smoke.picker_open)
        self.assertTrue(self.smoke.revealed and self.smoke.selected)
        self.assertNotIn(("native-choice", "2d", "2d-split-full"), self.smoke.events)
        self.assertLess(self.event_index("recorder-finished", "2d-split-entry"),
                        self.event_index("tap", "presentation-picker-done"))
        self.assertEqual("failed", self.smoke.checks["2d-split.entry-after-ready"]["status"])
        self.assertFalse(any(event[0] == "concealed-return" for event in self.smoke.events))
        self.assertEqual([], self.commands())
        self.assert_finished_once()

    def test_unjoined_observer_keeps_picker_ownership_and_blocks_all_later_cleanup(self):
        for suffix in ("entry", "exit"):
            with self.subTest(transition=suffix):
                self.reset(suffix)
                name = "2d-split-" + suffix
                primary = runner.ObservationFailure("Primary setup integrity failure")
                self.smoke.setup_errors[name] = primary
                self.smoke.unjoined.add(name)
                with self.assertRaises(RuntimeError) as caught:
                    self.smoke.split_scenario("2d")
                self.assertIs(primary, caught.exception)
                self.assertTrue(self.smoke.picker_open and self.smoke.split_recorder_unjoined)
                self.assertEqual(suffix == "exit", self.smoke.split_owned)
                self.assertNotIn(("tap", "presentation-picker-done"), self.smoke.events)
                before = list(self.smoke.events), list(self.smoke.commands)
                self.assertIn("no further UI mutations", self.smoke.restore_adaptive()[-1])
                with self.assertRaisesRegex(RuntimeError, "Unjoined recorder"):
                    self.smoke.restore_split_window()
                with self.assertRaisesRegex(RuntimeError, "earlier split recorder"):
                    with self.smoke.recorded_split_entry("3d", "later", "later"):
                        self.fail("A later recorder was admitted")
                self.assertEqual(before, (self.smoke.events, self.smoke.commands))
                self.assertTrue(self.smoke.split_recorder_unjoined)

    def test_prechoice_unsupported_error_cannot_continue_recovery_with_unjoined_observer(self):
        self.smoke.setup_errors["2d-split-entry"] = runner.Unavailable("Injected prechoice unsupported boundary")
        self.smoke.unjoined.add("2d-split-entry")
        with self.assertRaisesRegex(RuntimeError, "Unjoined recorder observation"):
            self.smoke.split_scenario("2d")
        self.assertEqual("unsupported", self.smoke.checks["2d-split.entry-after-ready"]["status"])
        self.assertTrue(self.smoke.picker_open)
        self.assertEqual([], self.commands())
        self.assertNotIn(("tap", "presentation-picker-done"), self.smoke.events)

    def test_picker_cleanup_base_exception_cannot_replace_primary_setup_error(self):
        primary = runner.ObservationFailure("Primary setup integrity failure")
        self.smoke.setup_errors["2d-split-entry"] = primary
        with patch.object(self.smoke, "tap_node", side_effect=KeyboardInterrupt("Secondary picker interrupt")):
            with self.assertRaises(RuntimeError) as caught:
                self.smoke.split_scenario("2d")
        self.assertIs(primary, caught.exception)
        self.assertTrue(any("Secondary picker interrupt" in error for error in self.smoke.cleanup_errors))
        self.assert_finished_once()

    def test_finish_base_exception_is_secondary_and_joined_picker_cleanup_remains_safe(self):
        primary = runner.ObservationFailure("Primary setup integrity failure")
        self.smoke.setup_errors["2d-split-entry"] = primary
        self.smoke.finish_errors["2d-split-entry"] = KeyboardInterrupt("Secondary finish interrupt")
        with self.assertRaises(RuntimeError) as caught:
            self.smoke.split_scenario("2d")
        self.assertIs(primary, caught.exception)
        self.assertTrue(any("Secondary finish interrupt" in error for error in self.smoke.cleanup_errors))
        self.assertFalse(self.smoke.picker_open or self.smoke.split_recorder_unjoined)
        self.assert_finished_once()

    def test_finish_failure_after_transition_blocks_continuity_ui(self):
        primary = runner.ObservationFailure("Recorder stop integrity failure")
        self.smoke.finish_errors["2d-split-entry"] = primary
        with self.assertRaises(RuntimeError) as caught:
            self.smoke.split_scenario("2d")
        self.assertIs(primary, caught.exception)
        self.assertFalse(any(event[0] == "concealed-return" for event in self.smoke.events))
        self.assertEqual("failed", self.smoke.checks["2d-split.entry-after-ready"]["status"])
        self.assert_finished_once()

    def test_native_ready_failure_before_yield_still_finishes_the_single_context(self):
        primary = runner.ObservationFailure("Native Ready failed after its one choice")
        self.smoke.entry_errors["2d-split-full"] = primary
        with self.assertRaises(RuntimeError) as caught:
            self.smoke.split_scenario("2d")
        self.assertIs(primary, caught.exception)
        self.assertEqual([], self.commands())
        self.assertNotIn(("tap", "presentation-picker-done"), self.smoke.events)
        self.assert_finished_once()

    def test_picker_cleanup_rejects_state_change_after_its_xml_dump(self):
        self.smoke.setup_errors["2d-split-entry"] = runner.ObservationFailure("Primary setup integrity failure")
        dump, state = self.smoke.dump_ui, self.smoke.state
        changed = False

        def changing_dump(deadline=None):
            nonlocal changed
            root = dump(deadline)
            if deadline is not None:
                changed = True
            return root

        def current_state():
            result = state()
            if changed:
                result["foreground"]["task_id"] = 99
            return result

        with patch.object(self.smoke, "dump_ui", side_effect=changing_dump), \
                patch.object(self.smoke, "state", side_effect=current_state):
            with self.assertRaisesRegex(RuntimeError, "Primary setup integrity failure"):
                self.smoke.split_scenario("2d")
        self.assertNotIn(("tap", "presentation-picker-done"), self.smoke.events)
        self.assertTrue(any("changed before the current picker" in error for error in self.smoke.cleanup_errors))

    def test_picker_done_fallback_uses_the_real_modal_when_tags_are_absent(self):
        self.smoke.setup_errors["2d-split-entry"] = runner.ObservationFailure("Primary setup integrity failure")
        dump = self.smoke.dump_ui

        def untagged_dump(deadline=None):
            root = dump(deadline)
            for node in root.iter("node"):
                node.attrib.pop("resource-id", None)
            return root

        with patch.object(self.smoke, "dump_ui", side_effect=untagged_dump):
            with self.assertRaisesRegex(RuntimeError, "Primary setup integrity failure"):
                self.smoke.split_scenario("2d")
        self.assertFalse(self.smoke.picker_open)
        self.assertEqual(1, self.smoke.events.count(("tap", "presentation-picker-done")))

    def test_unrelated_done_text_is_not_tapped_as_a_picker(self):
        self.smoke.begin_practice("setup")
        self.smoke.picker_open = True
        dump = self.smoke.dump_ui

        def unrelated_dialog(deadline=None):
            root = dump(deadline)
            for node in root.iter("node"):
                if node.get("text") == "Table style":
                    node.set("text", "An unrelated dialog")
            return root

        with patch.object(self.smoke, "dump_ui", side_effect=unrelated_dialog):
            self.smoke.dismiss_split_picker("setup")
        self.assertTrue(self.smoke.picker_open)
        self.assertNotIn(("tap", "presentation-picker-done"), self.smoke.events)

    def test_incomplete_input_rejects_deferred_setup_before_any_ui_or_recorder_creation(self):
        self.smoke.input_incomplete = True
        with self.assertRaisesRegex(RuntimeError, "Incomplete input forbids split recorder setup"):
            with self.smoke.recorded_split_entry("2d", "blocked", "blocked"):
                self.fail("Incomplete input admitted setup")
        self.assertEqual([], self.smoke.events)
        self.assertEqual([], self.smoke.recorders)


if __name__ == "__main__":
    unittest.main()
