"""Bounded diagnostic retention over host fixtures; no device or pixel proof."""

import copy
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import hashlib
import io
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import adaptive_observations as obs
import smoke_android_godot_adaptive as runner
from test_android_godot_adaptive import activities, input_dump, windows

session = runner.load_session(Path(__file__).resolve().parents[1] / "smoke-android-godot-session.py")
PACKAGE, MAIN, NATIVE = session.PACKAGE, session.MAIN_COMPONENT, session.NATIVE_COMPONENT


def ui_bytes(kind="missing", number=1):
    marker = ""
    if kind != "missing":
        bounds = "[63,1516][657,1600]" if kind == "outside" else "[63,1472][657,1556]"
        enabled = "false" if kind == "disabled" else "true"
        marker = (f'<node package="{PACKAGE}" resource-id="game-reveal-hand" '
                  f'bounds="{bounds}" enabled="{enabled}" clickable="true"/>')
    extra = ""
    if kind == "private":
        extra = f'<node package="{PACKAGE}" resource-id="game-card-0" bounds="[0,1700][100,1800]"/>'
    if kind == "dialog":
        extra = f'<node package="{PACKAGE}" text="Leave the table?" bounds="[40,400][680,480]"/>'
    # Declaration, CRLF, comments, entity spelling and attribute order must survive.
    return (f'<?xml version="1.0" encoding="UTF-8"?>\r\n<hierarchy rotation="0">\r\n'
            f'<!-- original fixture {number} -->\r\n'
            f'<node class="android.widget.ScrollView" package="{PACKAGE}" scrollable="true" '
            f'bounds="[0,358][720,1516]">'
            f'<node resource-id="game-hand" package="{PACKAGE}" bounds="[0,1069][720,1516]">'
            f'<node text="Public &amp; concealed" package="{PACKAGE}" bounds="[20,1200][700,1300]"/>'
            f'{marker}</node>{extra}</node>\r\n</hierarchy>\r\n').encode()


NATIVE_UI = (f'<hierarchy rotation="1"><node package="{PACKAGE}" bounds="[0,0][1920,1080]">'
             f'<node package="{PACKAGE}" text="Table ready." bounds="[20,10][220,60]"/>'
             f'<node package="{PACKAGE}" resource-id="native-standard-table" class="android.widget.Button" '
             f'bounds="[20,80][180,320]" enabled="true" clickable="true"/>'
             f'<node package="{PACKAGE}" resource-id="native-leave-table" class="android.widget.Button" '
             f'bounds="[240,80][420,160]" enabled="true" clickable="true"/>'
             '</node></hierarchy>').encode()


class HostOnly(runner.AdaptiveScenarios, session.GodotSessionSmoke):
    def __init__(self, output):
        super().__init__(session, "host-only-no-device", output, "debug", "2.0", 30000)
        self.shell_task = 19
        self.shell_identity = dict(pid=601, uid=10234, name=PACKAGE)
        self.display_size = (1080, 1920)

    def adb(self, *args, **kwargs):
        raise AssertionError("No device command is allowed")

    command = adb

    def load_ui(self, raw, number):
        root = session.ET.fromstring(raw)
        self.bind_ui(root)
        self.last_xml_bytes = raw
        self.last_xml_time = f"2026-09-10T00:00:{number % 60:02d}.500+00:00"
        return root

    def marker_state(self, number=1):
        return dict(foreground=dict(component=MAIN, task_id=self.shell_task), renderer_pids=[],
                    activities=[dict(component=MAIN)], original_log_prefix=f"states/{number:05d}",
                    started_utc=f"2026-09-10T00:00:{number % 60:02d}.000+00:00",
                    ended_utc=f"2026-09-10T00:00:{number % 60:02d}.100+00:00")


class LoopReplay(HostOnly):
    """Actual held loop, predicate and input proofs; synthetic transport/state/UI."""

    def __init__(self, output, kinds, *, state_fault=None, transport=0, expired_clock=False):
        super().__init__(output)
        self.events, self.kinds = [], iter(kinds)
        self.last_kind, self.dump_count = None, 0
        self.state_fault, self.transport, self.expired_clock = state_fault, transport, expired_clock
        self.wait_attempted = False
        self.recording_active = False
        self.process = types.SimpleNamespace(poll=self.poll, wait=self.wait)
        records, resumed = obs.activity_records(activities())
        display = obs.window_display(windows())
        self.before = dict(foreground=obs.attributed_focus(records, resumed, display), renderer_pids=[602],
                           shell_pids=[601], processes=[self.shell_identity, dict(pid=602, uid=10234, name=PACKAGE + ":godot")],
                           activities=records, display=display)
        self.main = copy.deepcopy(self.before)
        foreground = next(item for item in self.main["activities"] if item["component"] == MAIN)
        foreground.update(visible=True, visible_requested=True, client_visible=True)
        foreground["configuration"].update(orientation="port", display_rotation=0, bounds=[0, 0, 1080, 1920],
                                            window_size=[1080, 1920], width_dp=360, height_dp=640)
        foreground["window"] = dict(component=MAIN, input_name="ff12 " + MAIN, window_id="ff12")
        self.main.update(foreground=foreground, activities=[foreground], renderer_pids=[], processes=[self.shell_identity])
        self.main["display"].update(rotation=0, size=[1080, 1920])
        if state_fault == "native-record":
            self.main["activities"].append(dict(component=NATIVE, lifecycle_state="DESTROYED"))
        if state_fault == "task":
            foreground["task_id"] += 1

    def poll(self):
        self.events.append(("process-poll",))
        return None

    def wait(self, **kwargs):
        self.wait_attempted = True
        self.events.append(("input-wait", kwargs["timeout"]))
        if isinstance(self.transport, Exception):
            raise self.transport
        return self.transport

    def state(self):
        self.state_sequence += 1
        self.events.append(("state", self.state_sequence))
        state = copy.deepcopy(self.before if self.state_sequence <= 2 else self.main)
        state.update(original_log_prefix=f"states/{self.state_sequence:05d}",
                     started_utc=f"2026-09-10T00:00:{self.state_sequence:02d}.000+00:00",
                     ended_utc=f"2026-09-10T00:00:{self.state_sequence:02d}.100+00:00")
        self.write_json(state["original_log_prefix"] + ".json", state)
        return state

    def dump_ui(self, deadline=None):
        self.dump_count += 1
        self.events.append(("ui-dump", deadline))
        if self.dump_count == 1:
            raw = NATIVE_UI
        else:
            self.last_kind = next(self.kinds, self.last_kind or "visible")
            raw = ui_bytes(self.last_kind, self.dump_count)
        root = self.load_ui(raw, self.dump_count)
        (self.output / "last-ui.xml").write_bytes(raw)
        return root

    def input_observation(self, name):
        self.events.append(("input-observation", name))
        raw = input_dump()
        if name == "before-held-touch":
            raw = input_dump(active=False).replace("1500000000", "800000000").replace("1500200000", "800200000")
        elif name == "after-concealed-return-clock":
            clock = "32000000000" if self.expired_clock else "2000000000"
            raw = raw.replace("1500000000", clock).replace("1500200000", str(int(clock) + 200000))
        return raw, self.save_observation(name)

    def adb(self, *args, **kwargs):
        if args != ("shell", "wm", "user-rotation", "-d", "0", "lock", "0"):
            raise AssertionError(f"Unexpected device boundary: {args}")
        self.events.append(("rotation-request", args))
        return ""

    @contextmanager
    def recording(self, *args):
        self.recording_active = True
        self.events.append(("recording-start",))
        try:
            yield types.SimpleNamespace(checkpoint=lambda label: self.events.append(("checkpoint", label)))
        finally:
            self.recording_active = False
            self.events.append(("recording-finish",))

    def wait_activity(self, component, **kwargs):
        assert self.wait_attempted
        self.events.append(("wait-activity", component, kwargs))
        return self.state()

    def capture_evidence(self, name, *args):
        assert self.wait_attempted
        self.events.append(("capture", name))

    def save_observation(self, name, **fields):
        self.events.append(("observation", name))
        return super().save_observation(name, **fields)


def run_loop(output, kinds, *, method=None, diagnostic_write_fault=False, finalize=True, **kwargs):
    smoke = LoopReplay(output, kinds, **kwargs)
    clock_values = iter((0, 1, 2, 3, 4, 30))
    utc_counter = 0

    def tick():
        value = next(clock_values)
        smoke.events.append(("host-monotonic", value))
        return value

    def utc_now():
        nonlocal utc_counter
        utc_counter += 1
        smoke.events.append(("host-utc", utc_counter))
        return f"2026-09-10T00:01:{utc_counter:02d}.000+00:00"

    write_exact = runner.HeldReturnUiDiagnostics.write_exact

    def retained_write(path, data):
        assert smoke.wait_attempted, "Diagnostic I/O ran before the existing input wait exited"
        assert not smoke.recording_active, "Diagnostic I/O ran before the recorder context exited"
        if diagnostic_write_fault:
            raise OSError("Injected diagnostic storage failure")
        return write_exact(path, data)

    error, value = None, None
    with patch.object(runner.subprocess, "Popen", return_value=smoke.process), \
            patch.object(runner.time, "monotonic", side_effect=tick), \
            patch.object(runner.time, "sleep", side_effect=AssertionError("No extra sleep")), \
            patch.object(session, "utc_now", side_effect=utc_now), \
            patch.object(runner.HeldReturnUiDiagnostics, "write_exact", side_effect=retained_write):
        try:
            value = (method or runner.AdaptiveScenarios.rotate_while_held)(smoke, 602, smoke.before, 0, "host-held")
        except Exception as caught:
            error = caught
        # A standalone fixture has now unwound its local recorder owner. The
        # executable uses main's later finalization, after all caller cleanup.
        smoke.optional_diagnostics = runner.HeldReturnUiDiagnostics.flush_pending(smoke) if finalize else None
    return smoke, value, error


def run_main(output, *, scenario_error=None, cleanup_error=None, optional_fault=None, result_write_error=None):
    """Actual main/finally and persistence; synthetic scenario and owner cleanup.

    Real recorder lifetime coverage belongs to the separate recorder tests. This
    fixture checks that the executable's finalization reaches its original
    inventory/result write and preserves the original outcome under optional
    queue, summary, write, and fallback failures.
    """
    replay = types.SimpleNamespace(events=[], smoke=None, value=None, error=None)

    class MainReplay(runner.AdaptiveScenarios):
        load_ui = HostOnly.load_ui
        marker_state = HostOnly.marker_state

        def __init__(self, *args):
            super().__init__(*args)
            replay.smoke = self
            self.shell_task = 19
            self.shell_identity = dict(pid=601, uid=10234, name=PACKAGE)
            self.logcat_started = True

        def adb(self, *args, **kwargs):
            raise AssertionError("No device command is allowed")

        command = adb

        def prepare_capabilities(self):
            replay.events.append("prepare")

        def setup_session(self, apk):
            self.write_json("identity/host-fixture.json", dict(kind="synthetic-host-only"))

        def landscape_scenario(self, mode, direction):
            self.stage = mode + "-" + direction
            replay.events.append("scenario-owner-enter")
            try:
                collector = runner.HeldReturnUiDiagnostics.begin(self, self.stage)
                root = self.load_ui(ui_bytes(), 1)
                collector.remember(self, self.marker_state(), root)
                if scenario_error is not None:
                    raise scenario_error
            finally:
                replay.events.append("scenario-owner-cleanup-completed")

        def split_scenario(self, mode):
            replay.events.append("split-fixture-completed")

        def diagnostics(self):
            replay.events.append("original-diagnostics")
            return []

        def restore_adaptive(self):
            replay.events.append("original-restore")
            if cleanup_error is not None:
                raise cleanup_error
            return []

        def write_json(self, name, value):
            replay.events.append("write:" + name)
            if name == "godot-adaptive-result.json" and result_write_error is not None:
                raise result_write_error
            return super().write_json(name, value)

    original_flush = runner.HeldReturnUiDiagnostics.flush_pending
    original_finish = runner.HeldReturnUiDiagnostics.finish
    original_write = runner.HeldReturnUiDiagnostics.write_exact
    original_hash = runner.sha256

    def flush(smoke):
        replay.events.append("optional-flush")
        if optional_fault in ("flush", "fallback"):
            raise MemoryError("Optional queue finalization")
        return original_flush(smoke)

    def finish(collector, smoke, prefix):
        if optional_fault == "summary":
            raise MemoryError("Optional summary allocation")
        return original_finish(collector, smoke, prefix)

    def write_exact(path, raw):
        replay.events.append("optional-write")
        if optional_fault == "write":
            raise OSError("Optional storage failure")
        return original_write(path, raw)

    def make_dict(*args, **kwargs):
        if optional_fault == "fallback" and kwargs.get("status") == "diagnostic-finalization-failed":
            raise MemoryError("Optional fallback allocation")
        return dict(*args, **kwargs)

    def file_hash(path):
        if path.is_relative_to(output):
            replay.events.append("inventory:" + str(path.relative_to(output)))
        return original_hash(path)

    def utc_now():
        replay.events.append("original-utc")
        return "2026-09-10T00:00:00.000+00:00"

    apk = output.with_suffix(".synthetic.apk")
    apk.write_bytes(b"Synthetic host-only APK argument; never installed")
    argv = ["--session-checker", str(Path(__file__).resolve().parents[1] / "smoke-android-godot-session.py"),
            "--serial", "host-only-no-device", "--apk", str(apk), "--output", str(output),
            "--source-revision", "0" * 40, "--modes", "2d"]
    with patch.object(runner, "AdaptiveScenarios", MainReplay), patch.object(runner, "load_session", return_value=session), \
            patch.object(runner.HeldReturnUiDiagnostics, "flush_pending", side_effect=flush), \
            patch.object(runner.HeldReturnUiDiagnostics, "finish", autospec=True, side_effect=finish), \
            patch.object(runner.HeldReturnUiDiagnostics, "write_exact", side_effect=write_exact), \
            patch.object(runner, "dict", side_effect=make_dict, create=True), \
            patch.object(runner, "sha256", side_effect=file_hash), patch.object(session, "utc_now", side_effect=utc_now), \
            patch.object(runner.subprocess, "Popen", side_effect=AssertionError("No process execution")), \
            patch.object(runner.subprocess, "run", side_effect=AssertionError("No process execution")), \
            redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        try:
            replay.value = runner.main(argv)
        except Exception as error:
            replay.error = error
    result_path = output / "godot-adaptive-result.json"
    replay.result = json.loads(result_path.read_bytes()) if result_path.is_file() else None
    return replay


class HeldUiDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="partydeck-held-ui-diagnostics-host-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)

    def host(self, name="case"):
        output = self.output / name
        output.mkdir()
        return HostOnly(output)

    def index(self, smoke, summary):
        path = smoke.output / summary["index"]["file"]
        raw = path.read_bytes()
        self.assertEqual(summary["index"]["sha256"], hashlib.sha256(raw).hexdigest())
        return json.loads(raw)

    def stream(self, smoke):
        return smoke.optional_diagnostics["streams"][0]

    def test_original_bytes_state_and_ui_times_survive_overwrite_without_observation_io(self):
        smoke = self.host()
        raw = ui_bytes("missing")
        root = smoke.load_ui(raw, 1)
        state = smoke.marker_state()
        self.assertFalse(smoke.concealed_readonly(state, root))
        counters = smoke.state_sequence, smoke.observation_sequence, smoke.ui_sequence
        diagnostics = runner.HeldReturnUiDiagnostics()
        blocked = AssertionError("Retention during the held loop must only use existing memory")
        with patch.object(Path, "open", side_effect=blocked), patch.object(Path, "write_bytes", side_effect=blocked), \
                patch.object(smoke, "dump_ui", create=True, side_effect=blocked), \
                patch.object(smoke, "write_json", side_effect=blocked), \
                patch.object(runner.time, "monotonic", side_effect=blocked), \
                patch.object(session, "utc_now", side_effect=blocked):
            diagnostics.remember(smoke, state, root)
        self.assertEqual(counters, (smoke.state_sequence, smoke.observation_sequence, smoke.ui_sequence))
        root.set("derived-modification", "must not reach the original")
        smoke.load_ui(ui_bytes("visible", 2), 2)
        summary = diagnostics.finish(smoke, "original")
        sample = self.index(smoke, summary)["samples"][0]
        self.assertEqual("reveal-marker-absent", sample["reason"])
        self.assertEqual("retained-original", sample["status"])
        self.assertEqual(raw, (smoke.output / sample["xml"]["file"]).read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), sample["xml"]["sha256"])
        self.assertEqual(dict(file="states/00001.json", started_utc=state["started_utc"], ended_utc=state["ended_utc"]), sample["state"])
        self.assertEqual(dict(received_utc="2026-09-10T00:00:01.500+00:00", sequence=1), sample["ui"])
        self.assertEqual([], diagnostics.samples)

    def test_retention_keeps_first_and_latest_seven_and_bounds_files_bytes_and_counters(self):
        smoke = self.host()
        diagnostics = runner.HeldReturnUiDiagnostics()
        originals = {}
        for number in range(1, 41):
            raw = ui_bytes("missing", number)
            originals[number] = raw
            root = smoke.load_ui(raw, number)
            diagnostics.remember(smoke, smoke.marker_state(number), root)
            self.assertLessEqual(len(diagnostics.samples), 8)
            self.assertLessEqual(sum(len(value) for _, value in diagnostics.samples if value is not None), 8 * diagnostics.XML_BYTE_LIMIT)
        summary = diagnostics.finish(smoke, "bounded")
        index = self.index(smoke, summary)
        self.assertEqual([1, 34, 35, 36, 37, 38, 39, 40], [sample["observation"] for sample in index["samples"]])
        self.assertEqual(40, summary["observations_seen"])
        self.assertEqual(32, summary["evicted_observations"])
        self.assertEqual({"reveal-marker-absent": 40}, summary["reason_counts"])
        self.assertEqual({"buffered-original": 40}, summary["sampling_status_counts"])
        files = list((smoke.output / "observations").iterdir())
        self.assertEqual(9, len(files))
        self.assertLessEqual(sum(path.stat().st_size for path in files), 8 * diagnostics.XML_BYTE_LIMIT + diagnostics.INDEX_BYTE_LIMIT)
        for sample in index["samples"]:
            self.assertEqual(originals[sample["observation"]], (smoke.output / sample["xml"]["file"]).read_bytes())

    def test_oversized_xml_is_explicitly_omitted_without_truncating_a_boundary_sized_original(self):
        smoke = self.host()
        diagnostics = runner.HeldReturnUiDiagnostics()
        boundary = ui_bytes() + b" " * (diagnostics.XML_BYTE_LIMIT - len(ui_bytes()))
        for number, raw in enumerate((boundary + b" ", boundary), 1):
            root = smoke.load_ui(raw, number)
            diagnostics.remember(smoke, smoke.marker_state(number), root)
        summary = diagnostics.finish(smoke, "oversized")
        first, second = self.index(smoke, summary)["samples"]
        self.assertEqual("xml-byte-limit", first["status"])
        self.assertNotIn("xml", first)
        self.assertEqual(len(boundary) + 1, first["original_xml_bytes"])
        self.assertEqual(boundary, (smoke.output / second["xml"]["file"]).read_bytes())
        self.assertEqual(1, summary["original_xml_files"])
        self.assertEqual({"xml-byte-limit": 1, "buffered-original": 1}, summary["sampling_status_counts"])

    def test_stale_tree_or_missing_association_never_labels_other_dump_bytes_as_original(self):
        for missing in ("tree", "time", "state"):
            with self.subTest(missing=missing):
                smoke = self.host(missing)
                root = smoke.load_ui(ui_bytes(), 1)
                state = smoke.marker_state()
                if missing == "tree":
                    smoke.load_ui(ui_bytes("visible", 2), 2)
                elif missing == "time":
                    smoke.last_xml_time = None
                else:
                    state.pop("original_log_prefix")
                diagnostics = runner.HeldReturnUiDiagnostics()
                diagnostics.remember(smoke, state, root)
                summary = diagnostics.finish(smoke, "unavailable")
                sample = self.index(smoke, summary)["samples"][0]
                self.assertEqual("original-association-unavailable", sample["status"])
                self.assertEqual(0, summary["original_xml_files"])
                self.assertFalse(list((smoke.output / "observations").glob("*.xml")))

    def test_index_limit_omits_diagnostics_before_creating_original_files(self):
        smoke = self.host()
        diagnostics = runner.HeldReturnUiDiagnostics()
        root = smoke.load_ui(ui_bytes(), 1)
        diagnostics.remember(smoke, smoke.marker_state(), root)
        with patch.object(diagnostics, "INDEX_BYTE_LIMIT", 1):
            summary = diagnostics.finish(smoke, "index-limit")
        self.assertEqual("index-byte-limit", summary["status"])
        self.assertEqual([], list((smoke.output / "observations").iterdir()))

    def test_original_file_collision_does_not_overwrite_or_delete_existing_evidence(self):
        smoke = self.host()
        diagnostics = runner.HeldReturnUiDiagnostics()
        root = smoke.load_ui(ui_bytes(), 1)
        diagnostics.remember(smoke, smoke.marker_state(), root)
        existing = smoke.output / "observations/collision-rejected-held-ui-0001.xml"
        existing.write_bytes(b"Existing evidence stays unchanged")
        summary = diagnostics.finish(smoke, "collision")
        self.assertEqual("diagnostic-write-failed", summary["status"])
        self.assertEqual(b"Existing evidence stays unchanged", existing.read_bytes())
        self.assertNotIn("index", summary)

    def test_derived_reasons_distinguish_false_results_without_changing_the_predicate(self):
        for kind, reason in [("missing", "reveal-marker-absent"), ("disabled", "reveal-marker-disabled"),
                             ("outside", "reveal-marker-no-visible-intersection"), ("retiring", "native-activity-record-present")]:
            with self.subTest(kind=kind):
                smoke = self.host(kind)
                root = smoke.load_ui(ui_bytes("visible" if kind == "retiring" else kind), 1)
                state = smoke.marker_state()
                if kind == "retiring":
                    state["activities"].append(dict(component=NATIVE, lifecycle_state="DESTROYED"))
                self.assertFalse(smoke.concealed_readonly(state, root))
                diagnostics = runner.HeldReturnUiDiagnostics()
                diagnostics.remember(smoke, state, root)
                summary = diagnostics.finish(smoke, kind)
                self.assertEqual(reason, self.index(smoke, summary)["samples"][0]["reason"])

    def run_case(self, name, kinds, **kwargs):
        output = self.output / name
        output.mkdir()
        return run_loop(output, kinds, **kwargs)

    def test_actual_held_loop_retains_rejections_after_wait_and_still_accepts_partial_visibility(self):
        smoke, value, error = self.run_case("success", ["missing", "visible"])
        self.assertIsNone(error)
        self.assertIn("return_before_up", value)
        self.assertFalse(smoke.input_incomplete)
        self.assertNotIn("rejected_ui_diagnostics", value)
        summary = self.stream(smoke)
        sample = self.index(smoke, summary)["samples"][0]
        self.assertEqual("reveal-marker-absent", sample["reason"])
        self.assertEqual("states/00003.json", sample["state"]["file"])
        self.assertEqual(ui_bytes("missing", 2), (smoke.output / sample["xml"]["file"]).read_bytes())
        self.assertTrue(any(event == ("checkpoint", "concealed-return-and-up-completed") for event in smoke.events))

    def test_no_rejected_sample_adds_no_diagnostic_files_or_observation_entries(self):
        smoke, value, error = self.run_case("immediate", ["visible"])
        self.assertIsNone(error)
        self.assertNotIn("rejected_ui_diagnostics", value)
        self.assertIsNone(smoke.optional_diagnostics)
        self.assertFalse(list((smoke.output / "observations").glob("*rejected-held-ui*")))
        self.assertFalse(any("rejected" in item["name"] for item in smoke.adaptive_observations))

    def test_actual_held_timeout_stays_failed_with_original_rejected_samples_and_no_deadline_proof(self):
        smoke, value, error = self.run_case("failure", ["missing", "disabled"])
        self.assertIsNone(value)
        self.assertIsInstance(error, obs.ObservationFailure)
        self.assertEqual("No read-only concealed return was observed during the held stream.", str(error))
        self.assertFalse(smoke.input_incomplete)
        gesture = json.loads((smoke.output / "observations/host-held-held-input-result.json").read_bytes())
        self.assertNotIn("return_before_up", gesture)
        self.assertNotIn("rejected_ui_diagnostics", gesture)
        self.assertEqual(2, self.stream(smoke)["observations_seen"])
        self.assertFalse(any(event == ("input-observation", "after-concealed-return-clock") for event in smoke.events))
        self.assertFalse(list((smoke.output / "observations").glob("*concealed-before-up.xml")))

    def test_privacy_task_and_dialog_exceptions_propagate_without_becoming_false_or_success(self):
        for kind, fault, message in [("private", None, "Private hand semantics"), ("visible", "task", "retained shell task"),
                                      ("dialog", None, "stale Leave dialog")]:
            with self.subTest(kind=kind):
                smoke, value, error = self.run_case(kind, [kind], state_fault=fault)
                self.assertIsNone(value)
                self.assertIn(message, str(error))
                gesture = json.loads((smoke.output / "observations/host-held-held-input-result.json").read_bytes())
                sample = self.index(smoke, self.stream(smoke))["samples"][0]
                self.assertEqual("concealment-check-raised", sample["reason"])
                self.assertEqual(type(error).__name__, sample["check_error_type"])
                self.assertEqual(ui_bytes(kind, 2), (smoke.output / sample["xml"]["file"]).read_bytes())
                self.assertNotIn("return_before_up", gesture)

    def test_diagnostic_storage_failure_does_not_change_success_or_original_timeout(self):
        for name, kinds in [("success", ["missing", "visible"]), ("failed", ["missing", "missing"])]:
            with self.subTest(name=name):
                smoke, value, error = self.run_case(name, kinds, diagnostic_write_fault=True)
                gesture = json.loads((smoke.output / "observations/host-held-held-input-result.json").read_bytes())
                self.assertNotIn("rejected_ui_diagnostics", gesture)
                self.assertEqual("diagnostic-write-failed", self.stream(smoke)["status"])
                if name == "success":
                    self.assertIsNone(error)
                    self.assertIn("return_before_up", value)
                else:
                    self.assertEqual("No read-only concealed return was observed during the held stream.", str(error))
                    self.assertIsNone(value)

    def test_transport_timeout_and_nonzero_exit_remain_incomplete_after_diagnostic_flush(self):
        for name, outcome in [("nonzero", 1), ("timeout", subprocess.TimeoutExpired("synthetic-input", 50))]:
            with self.subTest(name=name):
                smoke, value, error = self.run_case(name, ["missing", "visible"], transport=outcome)
                self.assertIsNone(value)
                self.assertIsInstance(error, obs.ObservationFailure)
                self.assertTrue(smoke.input_incomplete)
                self.assertFalse(any(event[0] in ("wait-activity", "capture") for event in smoke.events))
                gesture = json.loads((smoke.output / "observations/host-held-held-input-result.json").read_bytes())
                self.assertNotIn("rejected_ui_diagnostics", gesture)
                self.assertEqual("retained", self.stream(smoke)["status"])

    def test_recorded_rejection_never_substitutes_for_an_expired_device_clock_proof(self):
        smoke, value, error = self.run_case("expired", ["missing", "visible"], expired_clock=True)
        self.assertIsNone(value)
        self.assertIsInstance(error, obs.ObservationFailure)
        gesture = json.loads((smoke.output / "observations/host-held-held-input-result.json").read_bytes())
        self.assertNotIn("return_before_up", gesture)
        self.assertNotIn("rejected_ui_diagnostics", gesture)
        self.assertEqual("retained", self.stream(smoke)["status"])
        self.assertFalse(list((smoke.output / "observations").glob("*concealed-before-up.xml")))

    def test_held_method_only_buffers_and_leaves_its_required_result_untouched(self):
        smoke, value, error = self.run_case("deferred", ["missing", "visible"], finalize=False)
        self.assertIsNone(error)
        self.assertIsNotNone(value)
        self.assertFalse(smoke.recording_active)
        self.assertFalse(list((smoke.output / "observations").glob("*rejected-held-ui*")))
        result_path = smoke.output / "observations/host-held-held-input-result.json"
        original = result_path.read_bytes()
        summary = runner.HeldReturnUiDiagnostics.flush_pending(smoke)
        self.assertEqual("retained", summary["streams"][0]["status"])
        self.assertEqual(original, result_path.read_bytes())

    def test_collector_initialization_failure_is_optional_and_cannot_skip_input_wait(self):
        with patch.object(runner.HeldReturnUiDiagnostics, "__init__", side_effect=MemoryError("Optional collector allocation")):
            smoke, value, error = self.run_case("allocation", ["missing", "visible"])
        self.assertIsNone(error)
        self.assertIn("return_before_up", value)
        self.assertTrue(smoke.wait_attempted)
        self.assertFalse(smoke.input_incomplete)
        self.assertTrue((smoke.output / "observations/host-held-held-input-result.json").is_file())
        self.assertEqual("collector-initialization-failed", self.stream(smoke)["status"])
        self.assertEqual("MemoryError", self.stream(smoke)["error_type"])

    def test_capture_allocation_failure_is_optional_for_success_and_original_exception(self):
        for name, kinds, expected_error in [("success", ["missing", "visible"], None),
                                            ("private", ["private"], "Private hand semantics")]:
            with self.subTest(name=name), patch.object(runner.HeldReturnUiDiagnostics, "remember_sample", side_effect=MemoryError("Optional sample allocation")):
                smoke, value, error = self.run_case(name, kinds)
                if expected_error is None:
                    self.assertIsNone(error)
                    self.assertIn("return_before_up", value)
                else:
                    self.assertIn(expected_error, str(error))
                self.assertTrue(smoke.wait_attempted)
                self.assertEqual(1, self.stream(smoke)["capture_failures"])

    def test_outer_optional_calls_cannot_replace_success_or_original_privacy_failure(self):
        for operation in ("begin", "remember"):
            for name, kinds in (("success", ["missing", "visible"]), ("private", ["private"])):
                with self.subTest(operation=operation, name=name), \
                        patch.object(runner.HeldReturnUiDiagnostics, operation, side_effect=MemoryError("Optional dispatch")):
                    smoke, value, error = self.run_case(operation + "-" + name, kinds)
                    if name == "success":
                        self.assertIsNone(error)
                        self.assertIn("return_before_up", value)
                    else:
                        self.assertIsNone(value)
                        self.assertIn("Private hand semantics", str(error))
                    self.assertTrue(smoke.wait_attempted)
                    self.assertFalse(smoke.input_incomplete)
                    self.assertTrue((smoke.output / "observations/host-held-held-input-result.json").is_file())
                    if operation == "remember":
                        self.assertEqual(1, self.stream(smoke)["capture_failures"])

    def test_required_held_result_write_failure_stays_the_original_failure(self):
        original_write = LoopReplay.write_json
        expected = OSError("Original required held result write failed")

        def write_json(smoke, name, value):
            if name.endswith("-held-input-result.json"):
                raise expected
            return original_write(smoke, name, value)

        with patch.object(LoopReplay, "write_json", write_json):
            smoke, value, error = self.run_case("required-write", ["missing", "visible"])
        self.assertIs(expected, error)
        self.assertIsNone(value)
        self.assertTrue(smoke.wait_attempted)
        self.assertFalse(smoke.recording_active)
        self.assertFalse((smoke.output / "observations/host-held-held-input-result.json").exists())
        self.assertEqual("retained", self.stream(smoke)["status"])

    def test_main_flushes_after_scenario_cleanup_restore_and_outcome_before_inventory(self):
        replay = run_main(self.output / "main-order")
        self.assertIsNone(replay.error)
        self.assertEqual(0, replay.value)
        self.assertEqual("passed-automated-scope", replay.result["status"])
        events = replay.events
        flush = events.index("optional-flush")
        self.assertEqual(["original-diagnostics", "original-restore", "original-utc"], events[flush - 3:flush])
        self.assertLess(max(index for index, event in enumerate(events) if event == "scenario-owner-cleanup-completed"), flush)
        self.assertLess(flush, events.index("optional-write"))
        self.assertLess(max(index for index, event in enumerate(events) if event == "optional-write"),
                        min(index for index, event in enumerate(events) if event.startswith("inventory:")))
        self.assertEqual("write:godot-adaptive-result.json", events[-1])
        retained = [row for row in replay.result["artifacts"] if "rejected-held-ui" in row["file"]]
        self.assertEqual(4, len(retained))
        self.assertEqual(["2d-landscape", "2d-seascape"],
                         [row["prefix"] for row in replay.result["rejected_ui_diagnostics"]["streams"]])

    def test_main_optional_faults_preserve_original_outcome_inventory_and_required_result(self):
        outcomes = [
            ("success", {}, 0, "passed-automated-scope", None),
            ("failed", dict(scenario_error=obs.ObservationFailure("Original scenario failure")), 1, "failed", "error"),
            ("unsupported", dict(scenario_error=obs.Unavailable("Original unsupported capability")), 2, "unsupported", "unsupported_reason"),
            ("cleanup", dict(cleanup_error=OSError("Original cleanup failure")), 1, "failed", "diagnostic_or_restore_errors"),
        ]
        for fault in ("flush", "summary", "write", "fallback"):
            for name, kwargs, code, status, field in outcomes:
                with self.subTest(fault=fault, outcome=name):
                    replay = run_main(self.output / (fault + "-" + name), optional_fault=fault, **kwargs)
                    self.assertIsNone(replay.error)
                    self.assertEqual(code, replay.value)
                    self.assertEqual(status, replay.result["status"])
                    if field is not None:
                        self.assertIn("Original", str(replay.result[field]))
                    self.assertIn("identity/host-fixture.json", [row["file"] for row in replay.result["artifacts"]])
                    self.assertEqual("write:godot-adaptive-result.json", replay.events[-1])
                    if fault == "fallback":
                        self.assertNotIn("rejected_ui_diagnostics", replay.result)

    def test_main_required_result_write_failure_is_not_swallowed_by_optional_finalization(self):
        expected = OSError("Original required final result write failed")
        replay = run_main(self.output / "main-required-write", optional_fault="write", result_write_error=expected)
        self.assertIs(expected, replay.error)
        self.assertIsNone(replay.value)
        self.assertIsNone(replay.result)
        self.assertTrue(any(event.startswith("inventory:") for event in replay.events))
        self.assertEqual("write:godot-adaptive-result.json", replay.events[-1])

    def test_four_source_held_streams_retain_later_failure_and_overflow_is_bounded(self):
        smoke = self.host()
        prefixes = ["2d-landscape", "2d-seascape", "3d-landscape", "3d-seascape"]
        for number, prefix in enumerate(prefixes, 1):
            collector = runner.HeldReturnUiDiagnostics.begin(smoke, prefix)
            self.assertIsNotNone(collector)
            # Earlier streams can have rejections and still ultimately pass;
            # they must leave room for the fourth source-defined held stream.
            root = smoke.load_ui(ui_bytes("missing", number), number)
            collector.remember(smoke, smoke.marker_state(number), root)
        for number in range(3):
            self.assertIsNone(runner.HeldReturnUiDiagnostics.begin(smoke, f"outside-source-scope-{number}"))
        self.assertEqual(4, len(smoke.held_ui_diagnostics_pending))
        summary = runner.HeldReturnUiDiagnostics.flush_pending(smoke)
        self.assertEqual(prefixes, [row["prefix"] for row in summary["streams"]])
        self.assertEqual(3, summary["omitted_streams"])
        final = summary["streams"][-1]
        self.assertEqual(ui_bytes("missing", 4), (smoke.output / self.index(smoke, final)["samples"][0]["xml"]["file"]).read_bytes())
        self.assertIsNone(runner.HeldReturnUiDiagnostics.flush_pending(smoke))


if __name__ == "__main__":
    unittest.main()
