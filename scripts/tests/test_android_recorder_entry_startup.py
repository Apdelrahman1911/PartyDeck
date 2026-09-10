"""Host-only recorder threading/deadline/ownership regressions; no device I/O."""

from contextlib import ExitStack, contextmanager
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import smoke_android_godot_adaptive as runner
from test_android_godot_adaptive import input_dump

session = runner.load_session(Path(__file__).resolve().parents[1] / "smoke-android-godot-session.py")
REAL_SLEEP, REAL_THREAD = time.sleep, threading.Thread


class Clock:
    def __init__(self):
        self.value, self.lock = 0.0, threading.Lock()

    def now(self):
        with self.lock:
            return self.value

    def set(self, value):
        with self.lock:
            if value < self.value:
                raise AssertionError("Synthetic clock must not move backward")
            self.value = value

    def sleep(self, duration):
        with self.lock:
            self.value += duration
        REAL_SLEEP(0)


class Platform:
    """Real identity parsers and host thread; all transport/media work is fake."""
    def __init__(self, output):
        self.output, self.session, self.serial = output, session, "host-only-recorder"
        for name in ("videos", "observations"):
            (output / name).mkdir()
        self.videos, self.cleanup_errors, self.events, self.reads = [], [], [], []
        self.clock, self.owner = Clock(), threading.current_thread()
        self.input_incomplete = self.sensitive_surface = self.remote_exists = False
        self.identity = dict(pid=777, uid=2000, start_ticks=12345)
        self.sample, self.last_size, self.returncode = 0, 0, None
        self.recorder, self.on_size, self.on_pids = None, None, None
        self.bad_cmdline_samples, self.unrelated_pid = set(), False
        self.hold_ms, self.last_xml_bytes = 30000, b"<host-only-recording-control />"

    def event(self, name, **fields):
        worker = threading.current_thread() is not self.owner
        if worker and name not in {"pidof", "cmdline", "status", "proc-stat", "file-size", "poll"}:
            raise AssertionError("Observer performed a non-recorder-read action: " + name)
        self.events.append(dict(name=name, worker=worker, **fields))

    def read(self, name, kwargs):
        self.event(name)
        self.reads.append(dict(name=name, started=self.clock.now(), timeout=kwargs.get("timeout")))

    def popen(self, argv, **kwargs):
        self.event("popen", argv=argv)
        if argv[4] != "/system/bin/screenrecord":
            raise AssertionError("No held-input process is expected in this fixture")
        self.remote_exists = True
        return types.SimpleNamespace(poll=self.poll, wait=self.wait)

    def poll(self):
        self.event("poll")
        return self.returncode

    def wait(self, **kwargs):
        self.event("wait")
        self.returncode = 0
        return 0

    def pids(self, name, **kwargs):
        self.read("pidof", kwargs)
        self.sample += 1
        if self.on_pids:
            self.on_pids(self)
        return ([999] if self.unrelated_pid else []) + [self.identity["pid"]]

    def command(self, *args, **kwargs):
        if args[:3] == ("shell", "test", "-e"):
            self.event("test-path")
            return subprocess.CompletedProcess(args, 0 if self.remote_exists else 1, "", "")
        if args[:2] == ("exec-out", "cat"):
            self.read("cmdline", kwargs)
            raw = b"\0".join(value.encode() for value in self.recorder.argv) + b"\0"
            if args[2] == "/proc/999/cmdline" or self.sample in self.bad_cmdline_samples:
                raw = b"/system/bin/screenrecord\0--unrelated\0"
            return subprocess.CompletedProcess(args, 0, raw, b"")
        if args[:3] == ("shell", "stat", "-c"):
            self.read("file-size", kwargs)
            self.last_size = self.on_size(self) if self.on_size else 3232
            return subprocess.CompletedProcess(args, 0, str(self.last_size), "")
        if args[:3] == ("shell", "sh", "-c"):
            self.assert_joined()
            self.event("signal", script=args[3])
            return subprocess.CompletedProcess(args, 0, "PARTYDECK_SCREENRECORD_SIGINT\n", "")
        raise AssertionError("Unrecognized fake command: " + repr(args))

    def adb(self, *args, **kwargs):
        if args == ("shell", "id", "-u"):
            self.event("uid")
            return "2000"
        if args[:2] == ("exec-out", "cat"):
            return self.command(*args, **kwargs).stdout
        if args[:2] == ("shell", "cat"):
            if args[2].endswith("/status"):
                self.read("status", kwargs)
                return "Uid:\t" + "\t".join([str(self.identity["uid"])] * 4) + "\n"
            self.read("proc-stat", kwargs)
            fields = ["S"] + ["0"] * 18 + [str(self.identity["start_ticks"])]
            return f'{self.identity["pid"]} (screenrecord) ' + " ".join(fields)
        if args[:3] == ("shell", "stat", "-c"):
            self.event("checkpoint-size")
            return str(self.last_size)
        if args[0] == "pull":
            self.assert_joined()
            self.event("pull")
            Path(args[2]).write_bytes(b"original host-only retention fixture; not a video")
            return "host-only pull"
        if args[:3] == ("shell", "rm", "-f"):
            self.assert_joined()
            self.event("remove", path=args[3])
            self.remote_exists = False
            return ""
        raise AssertionError("Unrecognized fake adb call: " + repr(args))

    def assert_joined(self):
        if self.recorder.observer is not None:
            assert self.recorder.observer_joined and not self.recorder.observer.is_alive()

    def dump_ui(self):
        self.assert_joined()
        self.event("dump-ui")
        return object()

    def write_json(self, name, value):
        self.event("write-json", path=name)

    def write_text(self, name, value):
        self.event("write-text", path=name)


class RecorderEntryStartupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="partydeck-recorder-entry-host-")
        self.addCleanup(self.temporary.cleanup)
        self.platform = Platform(Path(self.temporary.name))
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(runner.subprocess, "Popen", side_effect=self.platform.popen))
        self.stack.enter_context(patch.object(runner.time, "monotonic", side_effect=self.platform.clock.now))
        self.stack.enter_context(patch.object(runner.time, "sleep", side_effect=self.platform.clock.sleep))
        self.stack.enter_context(patch.object(runner, "verify_video", return_value={"host_only": True}))

    def recorder(self):
        result = runner.OriginalRecording(self.platform, "entry", [1600, 720])
        self.platform.recorder = result
        self.addCleanup(lambda: [handle.close() for handle in result.handles])
        return result

    def successful_start(self):
        self.platform.on_size = lambda platform: 3232 if platform.sample == 1 else 42664
        recorder = self.recorder()
        recorder.start()
        return recorder

    def test_baseline_releases_choice_while_passive_observer_waits_for_growth(self):
        permit_growth = threading.Event()
        self.addCleanup(permit_growth.set)
        def size(platform):
            if platform.sample == 1:
                return 3232
            self.assertTrue(permit_growth.wait(2), "Foreground choice did not release the host fixture")
            platform.clock.set(7.846)
            return 42664
        self.platform.on_size = size
        recorder = self.recorder()
        recorder.start_before_choice()
        self.assertFalse(recorder.started_successfully)
        self.assertFalse(recorder.startup_done.is_set())
        self.assertTrue(recorder.observer.is_alive())
        self.platform.event("existing-choice")
        permit_growth.set()
        self.assertTrue(recorder.startup_done.wait(2))
        self.platform.clock.set(11.7)  # Native Ready may finish after admission.
        recorder.await_started()
        self.assertEqual(8, recorder.startup_deadline)
        self.assertEqual(7.846, recorder.entry["growth_observed_seconds"])
        self.assertTrue(recorder.observer_joined)
        recorder.checkpoint("before-held-input")
        recorder.finish()
        self.assertEqual(1, sum(event["name"] == "popen" for event in self.platform.events))
        self.assertTrue(any(event["worker"] for event in self.platform.events))
        for read in self.platform.reads:
            if read["timeout"] is not None:
                self.assertLessEqual(read["timeout"], 8 - read["started"])

    def test_header_only_observer_finishes_at_original_deadline_and_never_admits(self):
        recorder = self.recorder()
        recorder.start_before_choice()
        with self.assertRaises(runner.Unavailable):
            recorder.await_started()
        self.assertEqual(8, self.platform.clock.now())
        self.assertFalse(recorder.started_successfully)
        self.assertTrue(recorder.observer_joined)
        recorder.finish()
        self.assertEqual("startup-unavailable-original-retained", recorder.entry["status"])

    def test_growth_at_or_after_deadline_is_rejected_even_when_read_started_earlier(self):
        for end in (8.0, 8.25):
            with self.subTest(end=end):
                self.platform.clock.value = 0
                self.platform.sample = 0
                self.platform.remote_exists = False
                self.platform.on_size = lambda platform: 3232 if platform.sample == 1 else (platform.clock.set(end) or 42664)
                recorder = runner.OriginalRecording(self.platform, "late-" + str(end), [1600, 720])
                self.platform.recorder = recorder
                self.addCleanup(lambda recorder=recorder: [handle.close() for handle in recorder.handles])
                with self.assertRaises(runner.Unavailable):
                    recorder.start()
                self.assertFalse(recorder.started_successfully)
                self.assertEqual(end, recorder.entry["startup_observations"][-1]["size_query_ended_seconds"])

    def test_bound_command_cannot_change_then_restore_and_admit_later_growth(self):
        self.platform.bad_cmdline_samples = {2}
        self.platform.on_size = lambda platform: 3232 if platform.sample == 1 else 42664
        recorder = self.recorder()
        with self.assertRaisesRegex(runner.ObservationFailure, "command changed"):
            recorder.start()
        self.assertEqual(2, self.platform.sample)
        self.assertFalse(recorder.started_successfully)

    def test_unbound_unrelated_command_is_ignored_without_weakening_ownership(self):
        self.platform.unrelated_pid = True
        recorder = self.successful_start()
        self.assertEqual(777, recorder.identity["pid"])
        self.assertEqual([3232, 42664], recorder.entry["initial_file_sizes"])

    def test_deadline_timeout_is_retained_and_rethrown_after_join(self):
        def size(platform):
            if platform.sample == 1:
                return 3232
            raise subprocess.TimeoutExpired("host-only size query", 7.75)
        self.platform.on_size = size
        recorder = self.recorder()
        recorder.start_before_choice()
        with self.assertRaisesRegex(runner.Unavailable, "remaining eight-second budget"):
            recorder.await_started()
        self.assertTrue(recorder.observer_joined)
        self.assertTrue(recorder.entry["startup_command_timeout"])
        recorder.finish()

    def test_entry_exception_cancels_joins_and_retains_original_exactly_once(self):
        def size(platform):
            if platform.sample > 1:
                self.assertTrue(platform.recorder.cancel_startup.wait(2))
            return 3232
        self.platform.on_size = size
        error = runner.ObservationFailure("controlled failure before Native Ready")
        with self.assertRaises(runner.ObservationFailure) as caught:
            with runner.AdaptiveScenarios.recording(self.platform, "entry", {"display": {"size": [1600, 720]}}, defer_start=True) as recorder:
                self.platform.recorder = recorder
                recorder.start_before_choice()
                raise error
        self.assertIs(error, caught.exception)
        recorder.finish()
        self.assertTrue(recorder.observer_joined)
        self.assertTrue(all(handle.closed for handle in recorder.handles))
        self.assertEqual(1, sum(event["name"] == "signal" for event in self.platform.events))
        self.assertEqual(1, sum(event["name"] == "pull" for event in self.platform.events))
        self.assertEqual("startup-unavailable-original-retained", recorder.entry["status"])

    def test_interrupted_thread_start_keeps_worker_owned_and_creates_no_recorder(self):
        def thread(**kwargs):
            actual = REAL_THREAD(**kwargs)
            def start():
                actual.start()
                raise KeyboardInterrupt("controlled interruption after actual thread launch")
            return types.SimpleNamespace(start=start, join=actual.join, is_alive=actual.is_alive)
        with patch.object(runner.threading, "Thread", side_effect=thread), self.assertRaises(KeyboardInterrupt):
            with runner.AdaptiveScenarios.recording(self.platform, "entry", {"display": {"size": [1600, 720]}}, defer_start=True) as recorder:
                self.platform.recorder = recorder
                recorder.start_before_choice()
        self.assertTrue(recorder.startup_done.is_set())
        self.assertTrue(recorder.observer_joined)
        self.assertFalse(recorder.observer.is_alive())
        self.assertIsNone(recorder.process)
        self.assertEqual([], recorder.handles)
        self.assertFalse(any(event["name"] in {"popen", "pidof", "signal", "pull"} for event in self.platform.events))

    def test_unproved_start_failure_is_not_treated_as_absent_worker(self):
        observer = types.SimpleNamespace(start=lambda: (_ for _ in ()).throw(RuntimeError("controlled start failure")),
                                         join=lambda **kwargs: self.fail("Unproved worker cannot be joined as if started"),
                                         is_alive=lambda: False)
        with patch.object(runner.threading, "Thread", return_value=observer), self.assertRaisesRegex(RuntimeError, "controlled start failure"):
            with runner.AdaptiveScenarios.recording(self.platform, "entry", {"display": {"size": [1600, 720]}}, defer_start=True) as recorder:
                self.platform.recorder = recorder
                # Simulate no worker acknowledgement without spending a real second.
                recorder.startup_done.wait = lambda **kwargs: False
                recorder.start_before_choice()
        self.assertIs(recorder.observer, observer)
        self.assertFalse(recorder.observer_joined)
        self.assertTrue(any("start completion is unproved" in error for error in self.platform.cleanup_errors))
        self.assertFalse(any(event["name"] in {"popen", "dump-ui", "signal", "pull"} for event in self.platform.events))

    def test_launch_failure_after_thread_start_joins_before_closing_handles(self):
        with patch.object(runner.subprocess, "Popen", side_effect=OSError("controlled recorder launch failure")), self.assertRaisesRegex(OSError, "controlled recorder launch failure"):
            with runner.AdaptiveScenarios.recording(self.platform, "entry", {"display": {"size": [1600, 720]}}, defer_start=True) as recorder:
                self.platform.recorder = recorder
                recorder.start_before_choice()
        self.assertTrue(recorder.observer_joined)
        self.assertTrue(all(handle.closed for handle in recorder.handles))
        self.assertFalse(any(event["worker"] for event in self.platform.events))

    def test_foreground_failure_survives_unreported_observer_base_exception(self):
        primary = runner.ObservationFailure("controlled foreground error")
        with self.assertRaises(runner.ObservationFailure) as caught:
            with runner.AdaptiveScenarios.recording(self.platform, "entry", {"display": {"size": [1600, 720]}}, defer_start=True) as recorder:
                self.platform.recorder = recorder
                recorder.launch()
                recorder.startup_error = KeyboardInterrupt("controlled observer interruption; no signal")
                raise primary
        self.assertIs(primary, caught.exception)
        self.assertTrue(all(handle.closed for handle in recorder.handles))
        self.assertTrue(any("controlled observer interruption" in error for error in self.platform.cleanup_errors))

    def test_expired_transport_and_changed_identity_both_fail_preheld_checkpoint(self):
        recorder = self.successful_start()
        self.platform.returncode = 0
        with self.assertRaisesRegex(runner.ObservationFailure, "not live"):
            recorder.checkpoint("before-held-input")
        self.platform.returncode = None
        self.platform.identity["start_ticks"] += 1
        with self.assertRaisesRegex(runner.ObservationFailure, "lifetime changed"):
            recorder.checkpoint("before-held-input")

    def test_preheld_checkpoint_cannot_accept_shrink_after_entry_checkpoint(self):
        recorder = self.successful_start()
        self.platform.last_size = 100000
        recorder.checkpoint("native-entry-completed")
        self.platform.last_size = 50000
        with self.assertRaisesRegex(runner.ObservationFailure, "shrank"):
            recorder.checkpoint("before-held-input")

    def test_recorder_is_revalidated_after_ui_and_clock_before_down(self):
        recorder = self.successful_start()
        control = ET.Element("node", bounds="[0,0][200,200]")
        self.platform.native_controls = lambda root: {}
        self.platform.find_action = lambda *args: control
        self.platform.viewport = lambda node: [0, 0, 200, 200]
        self.platform.save_observation = lambda name, **fields: dict(name=name, **fields)
        def before_touch(name):
            self.platform.returncode = 0
            return input_dump(active=False), {}
        self.platform.input_observation = before_touch
        with self.assertRaisesRegex(runner.ObservationFailure, "not live"):
            runner.AdaptiveScenarios.rotate_while_held(self.platform, 602, {"display": {"size": [1600, 720]}}, 0, "entry", recording=recorder)
        self.assertEqual(["native-entry-completed"], [item["label"] for item in recorder.entry["checkpoints"]])
        self.assertEqual(1, sum(event["name"] == "popen" for event in self.platform.events))
        self.assertFalse(self.platform.input_incomplete)

    def test_sensitive_original_is_withheld_after_join(self):
        recorder = self.successful_start()
        self.platform.sensitive_surface = True
        recorder.finish()
        self.assertEqual("withheld-sensitive-surface", recorder.entry["status"])
        self.assertFalse(any(event["name"] == "pull" for event in self.platform.events))


class NativeChoiceHookTests(unittest.TestCase):
    def test_hook_preserves_fresh_choice_tap_and_all_native_ownership_checks(self):
        events = []
        old, fresh = object(), object()
        calls = iter((old, fresh))
        class Replay:
            shell_identity = dict(pid=601, uid=10150)
            native_pids = []
            def wait_activity(self, component, **kwargs):
                events.append(("activity", component))
                return dict(renderer_pids=[602], processes=[dict(name=session.RENDERER_PROCESS, pid=602, uid=10150)], foreground=dict(task_id=8))
            def tap_action(self, *args, **kwargs): events.append(("picker", args))
            def wait_until(self, *args, **kwargs): events.append(("wait", args[0])); return {}
            def presentation_picker(self, root): return {}
            def wait_for_presentation_choice(self, mode):
                value = next(calls); events.append(("choice", value)); return value
            def capture_evidence(self, name, *args, **kwargs): events.append(("capture", name))
            def tap_node(self, node, label): events.append(("tap", node))
            def state(self): events.append(("state",)); return dict(renderer_pids=[602])
            def require_shell(self, state): events.append(("shell",))
            def matches_activity(self, state, component): events.append(("ownership",)); return True
            def native_controls(self, root, ready=True): return {}
        replay = Replay()
        result = session.GodotSessionSmoke.enter_native(replay, "2d", "initial", before_choice=lambda: events.append(("hook",)))
        self.assertEqual((602, 8, {}), result)
        self.assertEqual([("tap", fresh)], [event for event in events if event[0] == "tap"])
        self.assertLess(events.index(("capture", "initial-selector")), events.index(("hook",)))
        self.assertLess(events.index(("hook",)), events.index(("choice", fresh)))
        self.assertLess(events.index(("tap", fresh)), events.index(("activity", session.NATIVE_COMPONENT)))
        for name in ("Expected native Ready/chrome",):
            self.assertIn(("wait", name), events)
        self.assertIn(("shell",), events)
        self.assertIn(("ownership",), events)
        self.assertIn(("capture", "initial-native-ready"), events)
        self.assertEqual([602], replay.native_pids)


class RecorderScenarioLifetimeTests(unittest.TestCase):
    def exercise(self, entry_error=None, cleanup_error=None):
        events, clips = [], []
        smoke = types.SimpleNamespace(session=session, cleanup_errors=[], checks={})

        @contextmanager
        def check(name):
            result = smoke.checks[name] = dict(status="running")
            try:
                yield result
            except BaseException:
                result["status"] = "failed"
                raise
            else:
                result["status"] = "passed"

        class Clip:
            def __init__(self, *args):
                clips.append(self)
                self.finishes = 0
            def start(self):
                raise AssertionError("Deferred lifetime must not launch before the choice hook")
            def start_before_choice(self):
                events.append("choice-setup")
            def finish(self):
                self.finishes += 1
                events.append("finish")
                if cleanup_error:
                    raise cleanup_error

        def enter(mode, prefix, *, before_choice):
            before_choice()
            events.append("fresh-choice-and-entry")
            if entry_error:
                raise entry_error
            return 602, 8, None

        def rotate(*args, recording):
            self.assertIs(clips[0], recording)
            events.append("held-body")
            return {}

        def continuity(*args):
            events.append("continuity")
            raise RuntimeError("controlled stop after recorded held scope")

        state = dict(display=dict(landscape=1, seascape=3, portrait=0, size=[1600, 720]))
        smoke.check = check
        smoke.state = lambda: state
        smoke.set_rotation = lambda *args: state
        smoke.begin_practice = lambda *args: {}
        smoke.enter_native = enter
        smoke.stable_activity = lambda *args: state
        smoke.rotate_while_held = rotate
        smoke.require_concealed_return = continuity
        smoke.recording = lambda *args, **kwargs: runner.AdaptiveScenarios.recording(smoke, *args, **kwargs)
        with patch.object(runner, "OriginalRecording", Clip):
            try:
                runner.AdaptiveScenarios.landscape_scenario(smoke, "2d", "landscape")
            except BaseException as error:
                return smoke, clips, events, error
        self.fail("Controlled scenario stop was not reached")

    def test_initial_entry_exception_keeps_one_cleanup_owner_and_primary_error(self):
        primary = runner.ObservationFailure("controlled native entry failure")
        smoke, clips, events, error = self.exercise(primary, KeyboardInterrupt("controlled observer cleanup error"))
        self.assertIs(primary, error)
        self.assertEqual(["choice-setup", "fresh-choice-and-entry", "finish"], events)
        self.assertEqual(1, clips[0].finishes)
        self.assertEqual("failed", smoke.checks["2d-landscape.initial-landscape"]["status"])
        self.assertNotIn("2d-landscape.held-rotation", smoke.checks)
        self.assertTrue(any("controlled observer cleanup error" in value for value in smoke.cleanup_errors))

    def test_held_scope_owns_cleanup_before_continuity_without_restarting_recorder(self):
        smoke, clips, events, error = self.exercise()
        self.assertEqual("controlled stop after recorded held scope", str(error))
        self.assertEqual(["choice-setup", "fresh-choice-and-entry", "held-body", "finish", "continuity"], events)
        self.assertEqual(1, len(clips))
        self.assertEqual(1, clips[0].finishes)
        self.assertEqual("passed", smoke.checks["2d-landscape.initial-landscape"]["status"])
        self.assertEqual([], smoke.cleanup_errors)


if __name__ == "__main__":
    unittest.main()
