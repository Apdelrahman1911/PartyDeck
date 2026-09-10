"""Focused host regressions using source-shaped synthetic dumps, not captures."""

import copy
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adaptive_observations as obs
import smoke_android_godot_adaptive as runner


PACKAGE = "dev.partydeck.app"
MAIN = PACKAGE + "/" + PACKAGE + ".MainActivity"
NATIVE = PACKAGE + "/" + PACKAGE + ".godot.SessionGodotActivity"
SETTINGS = "com.android.settings/.Settings$DisplaySettingsActivity"
INPUT_NAME = "ff12 " + NATIVE


def cfg(bounds=(0, 0, 1920, 1080), orientation="land", rotation="ROTATION_90", mode="fullscreen"):
    return ("{1.0 ?mcc ?mnc [en_US] ldltr sw360dp w640dp h360dp 480dpi nrml long "
            + orientation + " finger -keyb/v/h -nav/h winConfig={ mBounds=Rect("
            + f"{bounds[0]}, {bounds[1]} - {bounds[2]}, {bounds[3]})"
            + " mAppBounds=Rect(0, 0 - 1920, 1080) mMaxBounds=Rect(0, 0 - 1920, 1080)"
            + f" mDisplayRotation={rotation} mWindowingMode={mode} mActivityType=standard"
            + f" mAlwaysOnTop=undefined mRotation={rotation}" + "} s.1 fontWeightAdjustment=0}")


def activity_block(record_id, target, task, pid, process, config=None, visible=True):
    visible = str(visible).lower()
    return (f"  * Hist  #0: ActivityRecord{{{record_id} u0 {target} t{task}}}\n"
            f"    packageName={process.split(':')[0]} processName={process}\n"
            f"    app=ProcessRecord{{ab {pid}:{process}/u0a234}}\n"
            f"    CurrentConfiguration={config or cfg()}\n"
            "    state=RESUMED delayedResume=false finishing=false\n"
            f"    mVisibleRequested={visible} mVisible={visible} mClientVisible={visible} reportedDrawn=true reportedVisible=true\n")


def activities(extra_resumed=True):
    return ("ACTIVITY MANAGER ACTIVITIES (dumpsys activity activities)\n"
            "Display #0 (activities from top to bottom):\n"
            + activity_block("aaaa", NATIVE, 19, 602, PACKAGE + ":godot")
            + activity_block("bbbb", SETTINGS, 21, 800, "com.android.settings")
            + activity_block("cccc", MAIN, 19, 601, PACKAGE, visible=False)
            + (f"    Resumed: ActivityRecord{{bbbb u0 {SETTINGS} t21}}\n" if extra_resumed else "")
            + f"    Resumed: ActivityRecord{{aaaa u0 {NATIVE} t19}}\n")


def windows(target=NATIVE, token="aaaa", task=19):
    return ("WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)\n"
            "  Display: mDisplayId=0 (organized)\n"
            "    init=1080x1920 480dpi cur=1920x1080 app=1920x1080\n"
            f"  mCurrentFocus=Window{{ff12 u0 {target}}}\n"
            f"  mFocusedApp=ActivityRecord{{{token} u0 {target} t{task}}}\n"
            "  DisplayRotation\n"
            "    mRotation=1 mDeferredRotationPauseCount=0\n"
            "    mLandscapeRotation=ROTATION_90 mSeascapeRotation=ROTATION_270\n"
            "    mPortraitRotation=ROTATION_0 mUpsideDownRotation=ROTATION_180\n")


def input_dump(active=True, down=1_000_000_000):
    touch = ("  TouchStatesByDisplay:\n"
             "    0 :     Windows:\n"
             f"        0 : name='{INPUT_NAME}', targetFlags=FOREGROUND, forwardingWindowToken=0x0, "
             f"mDeviceStates=-1:[touchingPointers=[Pointer(id=0, FINGER)], downTimeInTarget={down}, "
             "hoveringPointers=[], pilferingPointerIds=<none>]\n") if active else "  TouchStatesByDisplay: <no displays touched>\n"
    return ("Input Dispatcher State:\n" + touch
            + "  CursorStatesByDisplay: <no displays touched by cursor>\n"
            + "  Display: 0\n"
            + "    Windows:\n"
            + f"      0: name={INPUT_NAME}, id=15, displayId=0, inputConfig=0x0, alpha=1, "
            + "frame=[0,0][1920,1080], globalScale=1, ownerPid=602, ownerUid=10234, token=0x123\n"
            + "  Connections:\n"
            + f"    27: channelName='{INPUT_NAME}', status=NORMAL, monitor=false, responsive=true\n"
            + (f"      InputState: mMotionMementos: {{deviceId=-1, hovering=0, downTime={down}}}, \n" if active else "")
            + "  RecentQueue: length=2\n"
            + "    MotionEvent(deviceId=-1, eventTime=1500000000, source=TOUCHSCREEN, displayId=0, action=MOVE), policyFlags=0, age=100ms\n"
            + "    KeyEvent(deviceId=-1, eventTime=1500200000, source=KEYBOARD, displayId=0, action=DOWN), age=100ms\n"
            + "  PendingEvent: <none>\n")


class ObservationTests(unittest.TestCase):
    def test_history_spacing_keeps_full_record_and_focus_attribution(self):
        # Android 16 dumpActivity adds " #" to TaskFragment's "Hist " label.
        # The four API 36 consumers in run 34475052568 retained this spacing.
        for spacing in (" ", "  ", "\t", " \t "):
            with self.subTest(spacing=spacing):
                records, resumed = obs.activity_records(activities().replace("Hist  #", "Hist" + spacing + "#"))
                self.assertEqual(3, len(records))
                focus = obs.attributed_focus(records, resumed, obs.window_display(windows()))
                self.assertEqual((NATIVE, 602, PACKAGE + ":godot", "RESUMED"),
                                 (focus["component"], focus["app_pid"], focus["process_name"], focus["lifecycle_state"]))
                self.assertEqual([1920, 1080], focus["configuration"]["window_size"])

    def test_non_history_or_malformed_headers_cannot_supply_focused_records(self):
        for header in ("Hist#", "Hist X#", "Hist\u00a0#", "Fin  #", "Stop #", "History #"):
            with self.subTest(header=header):
                records, resumed = obs.activity_records(activities().replace("Hist  #", header))
                self.assertEqual([], records)
                self.assertIsNone(obs.attributed_focus(records, resumed, obs.window_display(windows())))

    def test_history_spacing_does_not_relax_record_or_configuration_guards(self):
        duplicate = activity_block("aaaa", NATIVE, 19, 602, PACKAGE + ":godot")
        with self.assertRaisesRegex(obs.ObservationFailure, "Duplicate full Activity record"):
            obs.activity_records(activities() + duplicate)
        raw = activities().replace("    CurrentConfiguration=" + cfg() + "\n", "")
        # A separate non-history list cannot restore missing full-record geometry.
        raw += (f"  * Fin #0: ActivityRecord{{aaaa u0 {NATIVE} t19}}\n"
                "    CurrentConfiguration=" + cfg() + "\n")
        records, resumed = obs.activity_records(raw)
        self.assertTrue(all("configuration" not in record for record in records))
        self.assertIsNone(obs.attributed_focus(records, resumed, obs.window_display(windows())))

    def test_focus_uses_wm_identity_with_all_resumed_records_retained(self):
        records, resumed = obs.activity_records(activities())
        self.assertEqual(2, len(resumed))
        focus = obs.attributed_focus(records, resumed, obs.window_display(windows()))
        self.assertEqual(NATIVE, focus["component"])
        self.assertEqual(602, focus["app_pid"])
        self.assertEqual([1920, 1080], focus["configuration"]["window_size"])
        settings_focus = obs.attributed_focus(records, resumed, obs.window_display(windows(SETTINGS, "bbbb", 21)))
        self.assertEqual(obs.component(SETTINGS), settings_focus["component"])

    def test_focus_requires_agreement_on_window_record_task_and_user(self):
        records, resumed = obs.activity_records(activities())
        correct = obs.window_display(windows())
        for change in ({"component": MAIN}, {"record_id": "dead"}, {"task_id": 99}, {"user_id": 10}):
            display = copy.deepcopy(correct)
            display["focused_app"].update(change)
            with self.subTest(change=change):
                self.assertIsNone(obs.attributed_focus(records, resumed, display))
        self.assertIsNone(obs.attributed_focus(records, [], correct))

    def test_default_display_is_not_confused_by_other_displays(self):
        raw = activities() + "Display #2 (activities from top to bottom):\n" + activity_block("dddd", NATIVE, 33, 603, PACKAGE + ":godot")
        raw += f"    Resumed: ActivityRecord{{dddd u0 {NATIVE} t33}}\n"
        records, resumed = obs.activity_records(raw)
        other = windows().replace("mDisplayId=0", "mDisplayId=2").replace("mRotation=1 ", "mRotation=3 ")
        focus = obs.attributed_focus(records, resumed, obs.window_display(other + windows()))
        self.assertEqual(19, focus["task_id"])

    def test_current_configuration_excludes_requested_override_and_history(self):
        raw = activities().replace("    state=RESUMED", f"    RequestedOverrideConfiguration={cfg(mode='freeform')}\n    state=RESUMED", 1)
        record = obs.activity_records(raw)[0][0]
        self.assertEqual("fullscreen", record["configuration"]["windowing_mode"])
        with self.assertRaises(obs.ObservationFailure):
            obs.activity_records(raw.replace("    state=RESUMED", "    CurrentConfiguration=" + cfg() + "\n    state=RESUMED", 1))
        with self.assertRaises(obs.ObservationFailure):
            obs.window_display(windows() + windows())

    def test_missing_or_undefined_configuration_cannot_prove_geometry(self):
        for raw in (cfg().replace("640dp", "0dp"), cfg().replace("land finger", "?orien finger"),
                    cfg().replace("480dpi", "?density"), cfg().replace("ldltr", "?layoutDir"),
                    cfg().replace("Rect(0, 0 - 1920, 1080)", "Rect(0, 0 - 0, 1080)", 1)):
            with self.subTest(raw=raw), self.assertRaises(obs.ObservationFailure):
                obs.configuration(raw)

    def test_half_turn_translation_and_mode_label_alone_are_not_size_changes(self):
        before = obs.configuration(cfg())
        translated = obs.configuration(cfg(bounds=(25, 40, 1945, 1120), rotation="ROTATION_270", mode="multi-window"))
        self.assertEqual({}, obs.tracked_changes(before, translated))
        resized = obs.configuration(cfg(bounds=(0, 0, 960, 1080), mode="multi-window"))
        self.assertEqual({"window_size"}, set(obs.tracked_changes(before, resized)))
        actual = copy.deepcopy(before)
        actual.update(orientation="port", width_dp=360, height_dp=640)
        self.assertEqual({"orientation", "width_dp", "height_dp"}, set(obs.tracked_changes(before, actual)))

    def test_held_touch_requires_actual_target_ownership_and_matching_memento(self):
        window = obs.window_display(windows())["window"]
        held = obs.held_touch(input_dump(), window, 602, 10234, [100, 200])
        self.assertEqual(-1, held["device_id"])
        self.assertEqual(1_000_000_000, held["down_time_ns"])
        for old, new in (("ownerPid=602", "ownerPid=601"), ("ownerUid=10234", "ownerUid=9999"),
                         ("downTime=1000000000", "downTime=999000000"),
                         ("hovering=0", "hovering=1"), ("deviceId=-1, hovering", "deviceId=1, hovering"),
                         ("monitor=false", "monitor=true"), ("targetFlags=FOREGROUND", "targetFlags=AS_IS"),
                         ("    0 :     Windows:", "    2 :     Windows:"),
                         ("InputState: mMotionMementos:", "WaitQueue: mMotionMementos:")):
            with self.subTest(change=(old, new)), self.assertRaises(obs.ObservationFailure):
                obs.held_touch(input_dump().replace(old, new), window, 602, 10234, [100, 200])
        with self.assertRaises(obs.ObservationFailure):
            obs.held_touch(input_dump(), window, 602, 10234, [2000, 200])

    def test_pending_outbound_input_cannot_prove_target_window_dispatch(self):
        pending = ("      OutboundQueue: length=1\n"
                   "        MotionEvent(deviceId=-1, action=DOWN), age=2ms, wait=1ms\n")
        raw = input_dump().replace("      InputState:", pending + "      InputState:")
        with self.assertRaisesRegex(obs.ObservationFailure, "outbound input"):
            obs.held_touch(raw, obs.window_display(windows())["window"], 602, 10234, [100, 200])

    def test_recent_key_history_or_connection_liveness_cannot_prove_held_input(self):
        raw = input_dump(active=False)
        self.assertTrue(obs.no_active_touch(raw))
        self.assertFalse(obs.no_active_touch(input_dump()))
        with self.assertRaises(obs.ObservationFailure):
            obs.held_touch(raw, obs.window_display(windows())["window"], 602, 10234, [100, 200])
        with self.assertRaises(obs.ObservationFailure):
            obs.no_active_touch("  TouchStatesByDisplay: unknown-format\n  Connections: <none>\n")

    def test_unparsed_named_device_state_cannot_prove_pre_injection_absence(self):
        raw = input_dump().replace(
            "mDeviceStates=-1:[touchingPointers=[Pointer(id=0, FINGER)], downTimeInTarget=1000000000, hoveringPointers=[], pilferingPointerIds=<none>]",
            "mDeviceStates=<unknown>")
        with self.assertRaises(obs.ObservationFailure):
            obs.no_active_touch(raw)

    def test_additional_device_continuation_is_rejected_in_complete_touch_section(self):
        continuation = "    4:[touchingPointers=[Pointer(id=1, FINGER)], downTimeInTarget=1000000000, hoveringPointers=[], pilferingPointerIds=<none>]\n"
        raw = input_dump().replace("  CursorStatesByDisplay:", continuation + "  CursorStatesByDisplay:")
        with self.assertRaises(obs.ObservationFailure):
            obs.held_touch(raw, obs.window_display(windows())["window"], 602, 10234, [100, 200])
        with self.assertRaises(obs.ObservationFailure):
            obs.no_active_touch(raw)

    def test_unrecognized_extra_memento_or_continuation_is_never_ignored(self):
        for extra in ("{deviceId=unknown, hovering=0, downTime=1000000000}, ",
                      "{unexpected=extra}, ", "\n      unparsed motion state"):
            raw = input_dump().replace("downTime=1000000000}, ", "downTime=1000000000}, " + extra)
            with self.subTest(extra=extra), self.assertRaises(obs.ObservationFailure):
                obs.held_touch(raw, obs.window_display(windows())["window"], 602, 10234, [100, 200])

    def test_input_clock_intersects_precision_intervals_and_proves_deadline(self):
        clock = obs.input_clock(input_dump())
        self.assertEqual(1_600_200_000, clock["lower_ns"])
        self.assertEqual(1_601_000_000, clock["upper_exclusive_ns"])
        result = obs.before_up(clock, {"down_time_ns": 1_000_000_000}, 10_000)
        self.assertEqual(11_000_000_000, result["earliest_up_ns"])
        with self.assertRaises(obs.ObservationFailure):
            obs.before_up(dict(lower_ns=10_999_500_000, upper_exclusive_ns=11_000_100_000), {"down_time_ns": 1_000_000_000}, 10_000)
        with self.assertRaises(obs.ObservationFailure):
            obs.before_up(clock, {"down_time_ns": 2_000_000_000}, 10_000)

    def test_clock_rejects_negative_ages_empty_intersection_and_missing_precision(self):
        for raw in (input_dump().replace("age=100ms", "age=-100ms", 1),
                    input_dump().replace("eventTime=1500200000", "eventTime=1503000000")):
            with self.subTest(raw=raw), self.assertRaises(obs.ObservationFailure):
                obs.input_clock(raw)
        for raw in (input_dump().replace("eventTime=1500000000", "eventTime=1.5"),
                    "  RecentQueue: length=1\n    MotionEvent, age=10ms\n  PendingEvent: <none>\n",
                    "  RecentQueue: <empty>\n  PendingEvent: <none>\n"):
            with self.subTest(raw=raw), self.assertRaises(obs.Unavailable):
                obs.input_clock(raw)

    def test_split_support_requires_both_platform_and_advertised_route(self):
        help_text = "Window Manager Shell commands:\n  splitscreen\n    moveToSideStage <taskId> <SideStagePosition>\n    exitSplitScreen <taskId>\n  help\n"
        self.assertTrue(obs.split_capability("true\n", "true\n", help_text)["platform_support"])
        for args in (("false", "true", help_text), ("true", "false", help_text), ("true", "true", "Unknown command")):
            with self.subTest(args=args), self.assertRaises(obs.Unavailable):
                obs.split_capability(*args)
        with self.assertRaises(obs.ObservationFailure):
            obs.split_capability("Error true", "true", help_text)

    def test_command_success_or_overlapping_hidden_panes_cannot_prove_split(self):
        first = obs.activity_records(activities())[0][0]
        second = obs.activity_records(activities())[0][1]
        first["configuration"] = obs.configuration(cfg(bounds=(0, 0, 950, 1080), mode="multi-window"))
        second["configuration"] = obs.configuration(cfg(bounds=(970, 0, 1920, 1080), mode="multi-window"))
        self.assertEqual(2, len(obs.split_pair([first, second], 19, 21, [1920, 1080])))
        for change in (dict(visible=False), dict(configuration=obs.configuration(cfg())),
                       dict(configuration=obs.configuration(cfg(bounds=(900, 0, 1920, 1080), mode="multi-window")))):
            with self.subTest(change=change), self.assertRaises(obs.ObservationFailure):
                obs.split_pair([first, second | change], 19, 21, [1920, 1080])


class RecordingSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="partydeck-adaptive-host-test-")
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.argv = ["/system/bin/screenrecord", "--time-limit", "60", "--size", "1920x1080",
                     "/sdcard/partydeck-adaptive-" + "a" * 32 + ".mp4"]
        self.identity = dict(pid=777, uid=2000, start_ticks=1234, name=self.argv[0])

    def test_recorder_stop_guard_is_bound_to_exact_pid_uid_start_time_and_command(self):
        script = runner.recorder_signal_script(self.identity, self.argv)
        self.assertIn("/proc/777/cmdline", script)
        self.assertIn("/proc/777/stat", script)
        self.assertIn("/proc/777/status", script)
        self.assertEqual(["kill -2 777"], [line for line in script.splitlines() if line.startswith("kill ")])
        self.assertLess(script.index("/proc/777/status"), script.index("kill -2 777"))
        for change in (dict(pid="777; kill -9 1"), dict(start_ticks=0), dict(uid=-1), dict(name="other")):
            with self.subTest(change=change), self.assertRaises(obs.ObservationFailure):
                runner.recorder_signal_script(self.identity | change, self.argv)
        with self.assertRaises(obs.ObservationFailure):
            runner.recorder_signal_script(self.identity, self.argv[:-1] + ["/sdcard/unrelated.mp4"])

    def test_original_video_survives_probe_and_decode_failures(self):
        path = self.output / "transition.mp4"
        original = b"synthetic incomplete video bytes retained for host-only failure test"
        path.write_bytes(original)
        failed = subprocess.CompletedProcess([], 1, "", "invalid media")
        with patch.object(runner.subprocess, "run", return_value=failed), self.assertRaises(obs.ObservationFailure):
            runner.verify_video(path, 1920, 1080, path.with_suffix(""))
        self.assertEqual(original, path.read_bytes())
        valid = subprocess.CompletedProcess([], 0, json.dumps(dict(streams=[dict(codec_type="video", width=1920, height=1080, nb_read_frames="30")], format=dict(duration="1.0"))), "")
        with patch.object(runner.subprocess, "run", side_effect=[valid, failed]), self.assertRaises(obs.ObservationFailure):
            runner.verify_video(path, 1920, 1080, path.with_suffix(""))
        self.assertEqual(original, path.read_bytes())
        self.assertIn("invalid media", (self.output / "transition.decode.log").read_text())

    def test_recording_with_sensitive_surface_is_not_pulled_and_only_own_path_is_removed(self):
        calls = []
        smoke = types.SimpleNamespace(
            output=self.output, serial="host-only", videos=[], sensitive_surface=True,
            session=types.SimpleNamespace(utc_now=lambda: "host-only-time", ui=types.SimpleNamespace(redacted=str)),
            dump_ui=lambda: None,
            adb=lambda *args, **kwargs: calls.append(args) or "",
            write_json=lambda name, value: (self.output / name).write_text(json.dumps(value)),
        )
        (self.output / "videos").mkdir()
        recording = runner.OriginalRecording(smoke, "sensitive", [1920, 1080])
        recording.path_available = True
        recording.finish()
        self.assertEqual("withheld-sensitive-surface", recording.entry["status"])
        self.assertEqual([("shell", "rm", "-f", recording.remote)], calls)
        self.assertFalse(any(self.output.rglob("*.mp4")))

    def test_failed_path_ownership_does_not_delete_preexisting_remote_file(self):
        calls = []
        smoke = types.SimpleNamespace(
            output=self.output, serial="host-only", videos=[], sensitive_surface=False,
            session=types.SimpleNamespace(utc_now=lambda: "host-only-time", ui=types.SimpleNamespace(redacted=str)),
            dump_ui=lambda: None, adb=lambda *args, **kwargs: calls.append(args) or "",
            write_json=lambda name, value: (self.output / name).write_text(json.dumps(value)),
        )
        (self.output / "videos").mkdir()
        recording = runner.OriginalRecording(smoke, "preexisting", [1920, 1080])
        recording.finish()
        self.assertEqual([], calls)

    def test_incomplete_input_prevents_all_cleanup_ui_mutations(self):
        class StopAfterIncompleteInput(runner.AdaptiveScenarios):
            input_incomplete = True
            cleanup_errors = []
            def adb(self, *args, **kwargs):
                self.fail("No adb mutation should run")
        errors = StopAfterIncompleteInput.restore_adaptive(StopAfterIncompleteInput.__new__(StopAfterIncompleteInput))
        self.assertEqual(1, len(errors))
        self.assertIn("no further UI mutations", errors[0])

    def test_actual_held_method_keeps_nonzero_or_timed_out_transport_incomplete(self):
        @contextmanager
        def no_video(*args):
            yield None
        def stop_before_transition():
            raise obs.ObservationFailure("Controlled host-only target-observation stop")
        for outcome in (1, subprocess.TimeoutExpired("host-only-adb", 30)):
            with self.subTest(outcome=outcome):
                case = self.output / ("nonzero" if outcome == 1 else "timeout")
                (case / "observations").mkdir(parents=True)
                ui = types.SimpleNamespace(node_bounds=lambda node: [0, 0, 200, 200],
                                           intersect_bounds=lambda first, second: first)
                smoke = types.SimpleNamespace(
                    output=case, serial="host-only", hold_ms=10000, last_xml_bytes=b"<host-only-fixture />",
                    session=types.SimpleNamespace(ui=ui, utc_now=lambda: "host-only-time"),
                    cleanup_errors=[], input_incomplete=False,
                    dump_ui=lambda: object(), native_controls=lambda root: {},
                    find_action=lambda *args: object(), viewport=lambda node: [0, 0, 200, 200],
                    save_observation=lambda name, **fields: dict(name=name, **fields),
                    input_observation=lambda name: (input_dump(active=False), {}), recording=no_video,
                    state=stop_before_transition,
                    write_json=lambda name, value: (case / name).write_text(json.dumps(value)),
                )
                process = types.SimpleNamespace(poll=lambda: None)
                if isinstance(outcome, Exception):
                    def wait(**kwargs):
                        raise outcome
                    process.wait = wait
                else:
                    process.wait = lambda **kwargs: outcome
                with patch.object(runner.subprocess, "Popen", return_value=process), self.assertRaises(obs.ObservationFailure):
                    runner.AdaptiveScenarios.rotate_while_held(smoke, 602, {}, 0, "host-only")
                self.assertTrue(smoke.input_incomplete)
                errors = runner.AdaptiveScenarios.restore_adaptive(smoke)
                self.assertEqual(1, len(errors))
                self.assertIn("no further UI mutations", errors[0])


class PinnedCheckerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session = runner.load_session(Path(__file__).resolve().parents[1] / "smoke-android-godot-session.py")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="partydeck-adaptive-state-host-test-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)

    def replay(self, output):
        session = self.session

        class Replay(runner.AdaptiveScenarios, session.GodotSessionSmoke):
            def __init__(self):
                output.mkdir(exist_ok=True)
                super().__init__(session, "synthetic-host-only", output, "debug", "1.0", 30000)
                self.activity = activities()
                self.pidof = {PACKAGE: [601], PACKAGE + ":godot": [602]}
                self.commands = []
                raw = (f"  PID   UID NAME                       \r\n601 10234 {PACKAGE}\r\n"
                       f"602 10234 {PACKAGE}:godot\r\n800 1000 com.android.settings\r\n").encode()
                self.process_result = subprocess.CompletedProcess([], 0, raw, b"")

            def adb(self, *args, **kwargs):
                return {("shell", "dumpsys", "activity", "activities"): self.activity,
                        ("shell", "dumpsys", "window", "displays"): windows()}[args]

            def pids(self, name):
                return self.pidof[name]

            def command(self, *args, **kwargs):
                self.commands.append((args, kwargs))
                if args != ("shell", "ps", "-A", "-n", "-w", "-o", "PID,UID,NAME") or kwargs != {"binary": True}:
                    raise AssertionError("Unexpected synthetic process-table command")
                if isinstance(self.process_result, Exception):
                    raise self.process_result
                return self.process_result

        return Replay()

    def test_observer_does_not_mutate_the_accepted_single_window_parser(self):
        with self.assertRaises(self.session.CheckFailure):
            self.session.parse_focused_activity(activities())

    def test_state_keeps_raw_samples_and_attributes_exact_native_focus(self):
        replay = self.replay(self.output)
        original_parser = self.session.parse_focused_activity
        process_parser = self.session.parse_process_table
        raw = replay.process_result.stdout

        def parse_saved_sample(value):
            receipt = json.loads((self.output / "logs/process-table-0001.json").read_text())
            self.assertEqual(raw, (self.output / receipt["stdout"]["file"]).read_bytes())
            self.assertEqual(b"", (self.output / receipt["stderr"]["file"]).read_bytes())
            self.assertEqual(runner.sha256(self.output / receipt["stdout"]["file"]), receipt["stdout"]["sha256"])
            self.assertEqual(["adb", "-s", "synthetic-host-only", "shell", "ps", "-A", "-n", "-w", "-o", "PID,UID,NAME"],
                             receipt["argv"])
            self.assertEqual(0, receipt["returncode"])
            return process_parser(value)

        with patch.object(self.session, "parse_process_table", side_effect=parse_saved_sample):
            state = replay.state()
        self.assertEqual(1, len(replay.commands))
        self.assertEqual(NATIVE, state["foreground"]["component"])
        self.assertEqual(2, len(state["resumed"]))
        self.assertEqual(activities(), (self.output / "states/00001-activity.log").read_text())
        self.assertEqual(windows(), (self.output / "states/00001-window.log").read_text())
        self.assertEqual(raw, (self.output / "states/00001-processes.log").read_bytes())
        self.assertIs(original_parser, self.session.parse_focused_activity)

    def test_state_rejects_inconsistent_process_identity_and_preserves_each_sample(self):
        for change in ("similar-name", "padded-name", "extra-exact-process", "multiple-pidof", "wrong-app-pid", "wrong-app-name"):
            with self.subTest(change=change):
                output = self.output / change
                replay = self.replay(output)
                raw = replay.process_result.stdout
                if change == "similar-name":
                    raw = raw.replace((PACKAGE + ":godot\r\n").encode(), (PACKAGE + ":godot-other\r\n").encode())
                elif change == "padded-name":
                    raw = raw.replace((PACKAGE + ":godot\r\n").encode(), (PACKAGE + ":godot \r\n").encode())
                elif change in ("extra-exact-process", "multiple-pidof"):
                    raw += f"603 10234 {PACKAGE}:godot\r\n".encode()
                    if change == "multiple-pidof":
                        replay.pidof[PACKAGE + ":godot"] = [602, 603]
                elif change == "wrong-app-pid":
                    replay.activity = replay.activity.replace("ab 602:", "ab 999:")
                elif change == "wrong-app-name":
                    replay.activity = replay.activity.replace("ab 602:" + PACKAGE + ":godot/", "ab 602:unrelated/")
                replay.process_result.stdout = raw
                with patch.object(runner.time, "sleep"), self.assertRaises(obs.ObservationFailure):
                    replay.state()
                samples = 1 if change == "multiple-pidof" else 3
                self.assertEqual(samples, len(replay.commands))
                for sequence in range(1, samples + 1):
                    receipt = json.loads((output / f"logs/process-table-{sequence:04d}.json").read_text())
                    self.assertEqual(raw, (output / receipt["stdout"]["file"]).read_bytes())

    def test_state_process_transport_and_schema_failures_keep_the_available_receipts(self):
        partial = b"PID UID NAME\r\n601 10234 "
        outcomes = (
            subprocess.CompletedProcess([], 2, partial, b"ps failed\xff\r\n"),
            subprocess.CompletedProcess([], 0, partial, b"ps diagnostic\r\n"),
            subprocess.CompletedProcess([], 0, b"PID USER NAME\r\n", b""),
            subprocess.CompletedProcess([], 0, partial + b"\xff\r\n", b""),
            subprocess.TimeoutExpired("synthetic-host-only", 20, output=partial, stderr=None),
        )
        for index, outcome in enumerate(outcomes):
            with self.subTest(index=index):
                output = self.output / str(index)
                replay = self.replay(output)
                replay.process_result = outcome
                with self.assertRaises((self.session.CheckFailure, UnicodeDecodeError, subprocess.TimeoutExpired)):
                    replay.state()
                self.assertEqual(1, len(replay.commands))
                receipt = json.loads((output / "logs/process-table-0001.json").read_text())
                self.assertEqual(outcome.stdout, (output / receipt["stdout"]["file"]).read_bytes())
                if isinstance(outcome, subprocess.TimeoutExpired):
                    self.assertIsNone(receipt["returncode"])
                    self.assertEqual({"available": False}, receipt["stderr"])
                    self.assertEqual("timeout", receipt["error"])
                else:
                    self.assertEqual(outcome.returncode, receipt["returncode"])
                    self.assertEqual(outcome.stderr, (output / receipt["stderr"]["file"]).read_bytes())
                self.assertFalse((output / "states/00001.json").exists())


if __name__ == "__main__":
    unittest.main()
