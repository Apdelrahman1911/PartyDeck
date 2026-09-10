"""Host-only safety/evidence regressions; no Android or engine qualification."""

from contextlib import redirect_stderr, redirect_stdout
import copy
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zlib


SPEC = importlib.util.spec_from_file_location(
    "partydeck_godot_session_smoke", Path(__file__).resolve().parents[1] / "smoke-android-godot-session.py",
)
smoke = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = smoke
SPEC.loader.exec_module(smoke)


def activity_dump(focused=smoke.NATIVE_COMPONENT, task=19, extra=""):
    return ("ACTIVITY MANAGER ACTIVITIES (dumpsys activity activities)\n"
            "Display #0 (activities from top to bottom):\n"
            f"  topResumedActivity=ActivityRecord{{aa u0 {smoke.MAIN_COMPONENT} t19}}\n"
            f"    Resumed: ActivityRecord{{bb u0 {focused} t{task}}}\n" + extra)


def proc_stat(pid, start_ticks=4567):
    # A comm containing spaces and ')' prevents naïve whitespace-field parsing.
    return f"{pid} (process ) name) " + " ".join(["S"] + ["0"] * 18 + [str(start_ticks)] + ["0"] * 12)


def native_xml(status=smoke.READY):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node package="{smoke.PACKAGE}" bounds="[0,0][720,1600]">
    <node package="{smoke.PACKAGE}" class="android.widget.TextView" text="{status}"
          enabled="true" bounds="[20,100][680,170]" />
    <node package="{smoke.PACKAGE}" class="android.widget.Button" text="Standard table"
          enabled="true" clickable="true" bounds="[20,190][350,300]" />
    <node package="{smoke.PACKAGE}" class="android.widget.Button" text="Leave table"
          enabled="true" clickable="true" bounds="[370,190][700,300]" />
  </node>
</hierarchy>
'''.encode()


def png():
    def chunk(kind, value):
        return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x11\x22\x33")) + chunk(b"IEND", b""))


class DeviceReplay(smoke.GodotSessionSmoke):
    def __init__(self, output, raw=None):
        super().__init__("host-only-replay", output)
        self.display_size = (720, 1600)
        self.shell_identity = {"pid": 601, "uid": 10234, "name": smoke.PACKAGE}
        self.shell_task = 19
        self.raw = raw or native_xml()
        self.screenshot = png()
        self.commands = []
        self.remote_xml = b"old data that must be deleted"
        self.dump_succeeds = True
        self.foreground = smoke.NATIVE_COMPONENT
        self.run_as_supported = True
        self.proc_read_supported = True
        self.guard_returncode = 0

    def record(self, message):
        self.steps.append(message)

    def state(self):
        self.write_text("logs/last-activity.log", activity_dump(self.foreground))
        self.write_text("logs/last-processes.log", f"PID UID NAME\n601 10234 {smoke.PACKAGE}\n602 10234 {smoke.RENDERER_PROCESS}\n")
        return {"foreground": {"component": self.foreground, "task_id": 19, "display_id": 0, "user_id": 0},
                "shell_pids": [601], "renderer_pids": [602],
                "processes": [self.shell_identity, {"pid": 602, "uid": 10234, "name": smoke.RENDERER_PROCESS}]}

    def adb(self, *arguments, **kwargs):
        self.commands.append(arguments)
        if arguments[:3] == ("shell", "rm", "-f"):
            self.remote_xml = None
            return ""
        if arguments[:3] == ("shell", "uiautomator", "dump"):
            if self.dump_succeeds:
                self.remote_xml = self.raw
                return "UI hierchary dumped to: " + arguments[3]
            return "ERROR: could not get idle state."
        if arguments[:2] == ("exec-out", "cat"):
            if self.remote_xml is None:
                raise subprocess.CalledProcessError(1, arguments, stderr=b"No such file")
            return self.remote_xml
        if arguments == ("exec-out", "screencap", "-p"):
            return self.screenshot
        raise AssertionError(f"Unexpected replay adb command: {arguments}")

    def command(self, *arguments, **kwargs):
        self.commands.append(arguments)
        if arguments == ("shell", "run-as", smoke.PACKAGE, "id", "-u"):
            return subprocess.CompletedProcess(arguments, 0 if self.run_as_supported else 1,
                                               "10234\n" if self.run_as_supported else "",
                                               "" if self.run_as_supported else "run-as: package not debuggable\n")
        if arguments[:4] == ("shell", "run-as", smoke.PACKAGE, "cat"):
            if not self.proc_read_supported:
                return subprocess.CompletedProcess(arguments, 1, b"" if kwargs.get("binary") else "", "Permission denied")
            _, _, pid, field = arguments[4].split("/")
            name = smoke.PACKAGE if pid == "601" else smoke.RENDERER_PROCESS
            values = {"cmdline": name.encode() + b"\0", "status": "Name:\tprocess\nUid:\t10234\t10234\t10234\t10234\n",
                      "stat": proc_stat(int(pid))}
            return subprocess.CompletedProcess(arguments, 0, values[field], b"" if kwargs.get("binary") else "")
        if arguments[:5] == ("shell", "run-as", smoke.PACKAGE, "sh", "-c"):
            return subprocess.CompletedProcess(arguments, self.guard_returncode,
                                               "PARTYDECK_RENDERER_SIGNALLED\n" if self.guard_returncode == 0 else "", "")
        raise AssertionError(f"Unexpected replay process command: {arguments}")


class PickerReplay(DeviceReplay):
    def adb(self, *arguments, **kwargs):
        if arguments[:3] == ("shell", "input", "tap"):
            self.commands.append(arguments)
            return ""
        return super().adb(*arguments, **kwargs)


class PickerLookupTests(unittest.TestCase):
    """Original public picker XML replay; no APK, Android, or renderer execution."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="partydeck-picker-host-test-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        self.raw = (Path(__file__).parent / "fixtures/android-picker-34475047307.xml").read_bytes()
        self.device = PickerReplay(self.output, self.raw)

    def tree(self):
        return ET.fromstring(self.raw)

    def label(self, root, text):
        nodes = [node for node in root.iter("node") if node.get("text") == text]
        self.assertEqual(1, len(nodes))
        return nodes[0]

    def parent(self, root, node):
        return {child: owner for owner in root.iter() for child in owner}[node]

    def row(self, root):
        return self.parent(root, self.label(root, "2D table"))

    def test_original_capture_exposes_enabled_radio_rows_without_dialog_ids(self):
        self.assertEqual("a63cdeb42eb34c60fba2bcdc6f20e0583bf97e0db23a12cbb9b7b90ba2cb6f7e",
                         hashlib.sha256(self.raw).hexdigest())
        root = self.tree()
        self.assertIsNone(self.device.find(root, "presentation-options"))
        self.assertIsNone(self.device.find_action(root, "presentation-choice-godot_2d", "2D table"))
        for mode, expected in (("2d", (193, 911, 304, 952)), ("3d", (193, 1009, 303, 1050))):
            with self.subTest(mode=mode):
                target = self.device.presentation_choice(root, mode)
                self.assertIsNotNone(target)
                self.assertEqual(expected, smoke.ui.node_bounds(target))
                row = self.parent(root, target)
                for attribute in ("enabled", "clickable", "checkable"):
                    self.assertEqual("true", row.get(attribute))
                self.assertEqual("false", row.get("checked"))

    def test_picker_taps_a_fresh_visible_label_inside_the_enabled_row(self):
        old_target = self.device.presentation_choice(self.tree(), "2d")
        target = self.device.wait_for_presentation_choice("2d")
        self.assertFalse(self.device.visible(old_target))
        self.device.tap_node(target, "presentation-choice-godot_2d")
        self.assertEqual(("shell", "input", "tap", "248", "931"), self.device.commands[-1])
        event = json.loads((self.output / "input-geometry.log").read_text())
        self.assertEqual([193, 911, 304, 952], event["bounds"])
        self.assertEqual(smoke.PACKAGE, event["package"])
        self.assertEqual("android.widget.TextView", event["class"])
        self.assertEqual({"x": 248, "y": 931}, event["coordinates"])
        self.assertFalse(any("am" in command for command in self.device.commands))

    def test_picker_rejects_disabled_or_nonradio_targets(self):
        mutations = [
            ("row", "enabled", "false"), ("row", "clickable", "false"),
            ("row", "checkable", "false"), ("row", "checked", "true"),
            ("row", "package", "other.app"), ("label", "enabled", "false"),
            ("label", "clickable", "true"), ("radio", "clickable", "true"),
            ("label", "package", "other.app"), ("label", "class", "android.widget.ImageView"),
            ("radio", "enabled", "false"), ("radio", "class", "android.widget.CheckBox"),
        ]
        for part, attribute, value in mutations:
            with self.subTest(part=part, attribute=attribute, value=value):
                root = self.tree()
                row = self.row(root)
                target = {"row": row, "label": self.label(root, "2D table"),
                          "radio": next(node for node in row.iter("node")
                                        if node.get("class") == "android.widget.RadioButton")}[part]
                target.set(attribute, value)
                self.assertIsNone(self.device.presentation_choice(root, "2d"))

    def test_picker_requires_the_radio_row_to_own_the_label_action(self):
        for attribute, value in (("clickable", "true"), ("enabled", "false"), ("package", "other.app")):
            with self.subTest(attribute=attribute):
                root = self.tree()
                row, label = self.row(root), self.label(root, "2D table")
                wrapper = ET.Element("node", package=smoke.PACKAGE, enabled="true", clickable="false",
                                     checkable="false", bounds="[180,900][320,965]")
                wrapper.set(attribute, value)
                row.remove(label)
                row.append(wrapper)
                wrapper.append(label)
                self.assertIsNone(self.device.presentation_choice(root, "2d"))

    def test_picker_rejects_missing_ambiguous_or_conflicting_choices(self):
        for mutation in ("missing", "duplicate-label", "duplicate-row", "wrong-tag"):
            with self.subTest(mutation=mutation):
                root = self.tree()
                row, label = self.row(root), self.label(root, "2D table")
                if mutation == "missing":
                    label.set("text", "Unavailable")
                elif mutation == "duplicate-label":
                    row.append(copy.deepcopy(label))
                elif mutation == "duplicate-row":
                    self.parent(root, row).append(copy.deepcopy(row))
                else:
                    row.set("resource-id", "presentation-choice-godot_3d")
                self.assertIsNone(self.device.presentation_choice(root, "2d"))

    def test_picker_requires_unique_real_modal_markers(self):
        for mutation in ("title-missing", "title-duplicate", "title-package", "done-missing", "done-disabled"):
            with self.subTest(mutation=mutation):
                root = self.tree()
                title, done_label = self.label(root, "Table style"), self.label(root, "Done")
                if mutation == "title-missing":
                    title.set("text", "Other dialog")
                elif mutation == "title-duplicate":
                    self.parent(root, title).append(copy.deepcopy(title))
                elif mutation == "title-package":
                    title.set("package", "other.app")
                elif mutation == "done-missing":
                    done_label.set("text", "Other action")
                else:
                    self.parent(root, done_label).set("enabled", "false")
                self.assertIsNone(self.device.presentation_choice(root, "2d"))

    def test_picker_rejects_an_anchor_in_a_different_window(self):
        root = self.tree()
        done = self.parent(root, self.label(root, "Done"))
        self.parent(root, done).remove(done)
        root.append(done)
        self.assertIsNone(self.device.presentation_choice(root, "2d"))

    def test_picker_rejects_clipped_rows_and_unsafe_label_hit_regions(self):
        for mutation in ("scroll-top", "scroll-bottom", "row-gap", "label-gap", "second-scroll"):
            with self.subTest(mutation=mutation):
                root = self.tree()
                scroll = next(node for node in root.iter("node") if node.get("class") == "android.widget.ScrollView")
                if mutation == "scroll-top":
                    scroll.set("bounds", "[122,920][598,1078]")
                elif mutation == "scroll-bottom":
                    scroll.set("bounds", "[122,532][598,940]")
                elif mutation == "row-gap":
                    self.row(root).set("bounds", "[190,908][307,955]")
                elif mutation == "label-gap":
                    self.label(root, "2D table").set("bounds", "[122,911][598,952]")
                else:
                    self.parent(root, scroll).append(copy.deepcopy(scroll))
                self.assertIsNone(self.device.presentation_choice(root, "2d"))

    def test_matching_exported_tags_keep_the_same_real_target(self):
        for tag in ("presentation-choice-godot_2d", "dev.partydeck.app:id/presentation-choice-godot_2d"):
            with self.subTest(tag=tag):
                root = self.tree()
                self.row(root).set("resource-id", tag)
                self.assertIs(self.label(root, "2D table"), self.device.presentation_choice(root, "2d"))

    def test_picker_does_not_reuse_stale_nodes_or_accept_unknown_modes(self):
        first = self.device.presentation_choice(self.tree(), "2d")
        self.device.presentation_choice(self.tree(), "3d")
        with self.assertRaisesRegex(RuntimeError, "current visible viewport"):
            self.device.tap_node(first, "stale-picker-target")
        self.assertEqual([], self.device.commands)
        with self.assertRaises(smoke.CheckFailure):
            self.device.presentation_choice(self.tree(), "4d")


class SessionSmokeSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="partydeck-session-host-test-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)

    def test_pidof_absence_requires_the_documented_empty_exit_one(self):
        self.assertEqual([], smoke.parse_pidof(1, "", ""))
        self.assertEqual([32, 76], smoke.parse_pidof(0, "76 32\n", ""))
        for result in ((0, "", ""), (1, "32", ""), (1, "", "denied"), (2, "", ""),
                       (0, "32 nope", ""), (0, "32 32", ""), (0, "0", "")):
            with self.subTest(result=result), self.assertRaises(smoke.CheckFailure):
                smoke.parse_pidof(*result)

    def test_focused_activity_ignores_history_merely_resumed_tasks_and_other_displays(self):
        dump = activity_dump(smoke.MAIN_COMPONENT, extra=(
            f"  Hist #1: ActivityRecord{{cc u0 {smoke.NATIVE_COMPONENT} t19}}\n"
            "Display #2 (activities from top to bottom):\n"
            f"    Resumed: ActivityRecord{{dd u0 {smoke.NATIVE_COMPONENT} t88}}\n"))
        self.assertEqual(smoke.MAIN_COMPONENT, smoke.parse_focused_activity(dump)["component"])
        only_history = "Display #0 (activities from top to bottom):\n" + f"  topResumedActivity=ActivityRecord{{aa u0 {smoke.NATIVE_COMPONENT} t19}}\n"
        self.assertIsNone(smoke.parse_focused_activity(only_history))

    def test_process_table_keeps_full_names_and_rejects_an_unknown_schema(self):
        rows = smoke.parse_process_table(f"  PID UID NAME\n601 10234 {smoke.PACKAGE}\n602 10234 {smoke.RENDERER_PROCESS}-other\n")
        self.assertEqual(smoke.RENDERER_PROCESS + "-other", rows[602]["name"])
        for text in ("USER PID NAME\nu0_a234 602 dev.partydeck.app\n", "PID USER NAME\n602 10234 name\n",
                     "PID UID NAME EXTRA\n602 10234 name\n", "PID UID NAME\n602 u0_a234 name\n",
                     "PID UID NAME\n602 x name\n", "PID UID NAME\n602 ١٠٢٣٤ name\n",
                     "PID UID NAME\n٠٦٠٢ 10234 name\n", "PID UID NAME\n0 10234 name\n",
                     "PID UID NAME\n602 10234 name\n602 10234 other\n"):
            with self.subTest(text=text), self.assertRaises(smoke.CheckFailure):
                smoke.parse_process_table(text)

    def test_toybox_padded_header_does_not_normalize_process_names(self):
        # Source-derived fixture: AOSP Android 15/16 get_headers() keeps NAME's
        # 27-column padding. The failed CI run did not retain its actual stdout.
        header = f"{'PID':>6} {'UID':>5} {'NAME':<27}"
        for newline in ("\n", "\r\n"):
            text = newline.join((header, f"601 10234 {smoke.PACKAGE}",
                                 f"602 10234 {smoke.RENDERER_PROCESS}-other",
                                 "603 0 [kernel worker]", f"604 10234 {smoke.PACKAGE} ", ""))
            with self.subTest(newline=newline):
                rows = smoke.parse_process_table(text)
                self.assertEqual(smoke.PACKAGE, rows[601]["name"])
                self.assertEqual(smoke.RENDERER_PROCESS + "-other", rows[602]["name"])
                self.assertEqual("[kernel worker]", rows[603]["name"])
                self.assertEqual(smoke.PACKAGE + " ", rows[604]["name"])

    def test_process_sample_retains_exact_bytes_and_command_before_parsing(self):
        device = smoke.GodotSessionSmoke("host-only-replay", self.output)
        raw = (f"{'PID':>6} {'UID':>5} {'NAME':<27}\r\n"
               f"601 10234 {smoke.PACKAGE}\r\n602 10234 {smoke.RENDERER_PROCESS}\r\n").encode()
        result = subprocess.CompletedProcess([], 0, raw, b"")
        original_parser = smoke.parse_process_table

        def parse_after_preservation(value):
            receipt = json.loads((self.output / "logs/process-table-0001.json").read_text())
            self.assertEqual(raw, (self.output / receipt["stdout"]["file"]).read_bytes())
            self.assertEqual(b"", (self.output / receipt["stderr"]["file"]).read_bytes())
            self.assertEqual(smoke.sha256_file(self.output / receipt["stdout"]["file"]), receipt["stdout"]["sha256"])
            self.assertEqual(0, receipt["returncode"])
            self.assertEqual(["adb", "-s", "host-only-replay", "shell", "ps", "-A", "-n", "-w", "-o", "PID,UID,NAME"], receipt["argv"])
            return original_parser(value)

        with patch.object(device, "adb", return_value=activity_dump()), \
                patch.object(device, "pids", side_effect=[[601], [602]]), \
                patch.object(device, "command", return_value=result) as command, \
                patch.object(smoke, "parse_process_table", side_effect=parse_after_preservation):
            state = device.state()
        command.assert_called_once_with("shell", "ps", "-A", "-n", "-w", "-o", "PID,UID,NAME", binary=True)
        self.assertEqual([601], state["shell_pids"])
        self.assertEqual([602], state["renderer_pids"])

    def test_rejected_process_header_keeps_original_output(self):
        device = smoke.GodotSessionSmoke("host-only-replay", self.output)
        raw = b"PID USER NAME   \r\n601 10234 name\r\n"
        with patch.object(device, "adb", return_value=activity_dump()), \
                patch.object(device, "pids", side_effect=[[601], []]), \
                patch.object(device, "command", return_value=subprocess.CompletedProcess([], 0, raw, b"")), \
                self.assertRaises(smoke.CheckFailure):
            device.state()
        self.assertEqual(raw, (self.output / "logs/process-table-0001.stdout.log").read_bytes())
        self.assertFalse((self.output / "logs/last-processes.log").exists())

    def test_process_command_errors_retain_stdout_stderr_and_exit(self):
        for index, returncode in enumerate((0, 2)):
            output = self.output / str(index)
            output.mkdir()
            device = smoke.GodotSessionSmoke("host-only-replay", output)
            raw, error = b"PID UID NAME   \n", b"ps: read error\xff\r\n"
            with patch.object(device, "command", return_value=subprocess.CompletedProcess([], returncode, raw, error)), \
                    self.assertRaises(smoke.CheckFailure):
                device.read_process_table()
            receipt = json.loads((output / "logs/process-table-0001.json").read_text())
            self.assertEqual(returncode, receipt["returncode"])
            self.assertEqual(raw, (output / receipt["stdout"]["file"]).read_bytes())
            self.assertEqual(error, (output / receipt["stderr"]["file"]).read_bytes())

    def test_process_timeout_retains_partial_bytes_without_inventing_exit(self):
        device = smoke.GodotSessionSmoke("host-only-replay", self.output)
        partial = b"PID UID NAME   \r\n601 10234 "
        timeout = subprocess.TimeoutExpired(["adb"], 20, output=partial, stderr=None)
        with patch.object(device, "command", side_effect=timeout), self.assertRaises(subprocess.TimeoutExpired):
            device.read_process_table()
        receipt = json.loads((self.output / "logs/process-table-0001.json").read_text())
        self.assertIsNone(receipt["returncode"])
        self.assertEqual("timeout", receipt["error"])
        self.assertEqual(20, receipt["timeout_seconds"])
        self.assertEqual(partial, (self.output / receipt["stdout"]["file"]).read_bytes())
        self.assertEqual({"available": False}, receipt["stderr"])

    def test_process_launch_failure_records_unavailable_streams(self):
        device = smoke.GodotSessionSmoke("host-only-replay", self.output)
        with patch.object(device, "command", side_effect=FileNotFoundError("adb unavailable")), \
                self.assertRaises(FileNotFoundError):
            device.read_process_table()
        receipt = json.loads((self.output / "logs/process-table-0001.json").read_text())
        self.assertIsNone(receipt["returncode"])
        self.assertEqual("FileNotFoundError", receipt["error"])
        self.assertEqual({"available": False}, receipt["stdout"])
        self.assertEqual({"available": False}, receipt["stderr"])

    def test_invalid_process_output_encoding_remains_available(self):
        device = smoke.GodotSessionSmoke("host-only-replay", self.output)
        raw = b"PID UID NAME\n601 10234 \xff\n"
        with patch.object(device, "command", return_value=subprocess.CompletedProcess([], 0, raw, b"")), \
                self.assertRaises(UnicodeDecodeError):
            device.read_process_table()
        self.assertEqual(raw, (self.output / "logs/process-table-0001.stdout.log").read_bytes())

    def test_inconsistent_process_samples_never_accept_a_similar_name_or_overwrite_originals(self):
        device = smoke.GodotSessionSmoke("host-only-replay", self.output)
        raw = f"PID UID NAME   \n601 10234 {smoke.PACKAGE}-other\n".encode()
        with patch.object(device, "adb", return_value=activity_dump()), \
                patch.object(device, "pids", side_effect=[[601], []] * 3), \
                patch.object(device, "command", return_value=subprocess.CompletedProcess([], 0, raw, b"")), \
                patch.object(smoke.time, "sleep"), self.assertRaisesRegex(smoke.CheckFailure, "repeatedly disagree"):
            device.state()
        for sequence in range(1, 4):
            self.assertEqual(raw, (self.output / f"logs/process-table-{sequence:04d}.stdout.log").read_bytes())
            self.assertTrue((self.output / f"logs/process-table-{sequence:04d}.json").is_file())
        self.assertFalse((self.output / "logs/last-processes.log").exists())

    def test_ambiguous_or_unrecognized_focus_cannot_prove_foreground(self):
        for value in ("ACTIVITY " + smoke.NATIVE_COMPONENT,
                      activity_dump() + f"    Resumed: ActivityRecord{{bb u0 {smoke.MAIN_COMPONENT} t29}}\n",
                      "Display #0 (activities from top to bottom):\n    Resumed: broken-format\n"):
            with self.subTest(value=value), self.assertRaises(smoke.CheckFailure):
                smoke.parse_focused_activity(value)
        self.assertEqual(smoke.NATIVE_COMPONENT, smoke.canonical_component(f"{smoke.PACKAGE}/.godot.SessionGodotActivity"))

    def test_process_identity_requires_exact_name_uid_pid_and_start_time(self):
        args = dict(pid=602, expected_name=smoke.RENDERER_PROCESS, expected_uid=10234,
                    cmdline=smoke.RENDERER_PROCESS.encode() + b"\0",
                    status="Uid:\t10234\t10234\t10234\t10234\n", stat=proc_stat(602))
        self.assertEqual(4567, smoke.parse_proc_identity(**args)["start_ticks"])
        for change in ({"cmdline": smoke.PACKAGE.encode() + b"\0"},
                       {"cmdline": (smoke.RENDERER_PROCESS + "-other").encode() + b"\0"},
                       {"status": "Uid: 10234 0 10234 10234\n"}, {"stat": proc_stat(999)},
                       {"stat": "602 (name) S 0 0"}):
            with self.subTest(change=change), self.assertRaises(smoke.CheckFailure):
                smoke.parse_proc_identity(**(args | change))

    def test_guard_rejects_shell_target_wrong_uid_and_untrusted_values(self):
        shell = {"name": smoke.PACKAGE, "pid": 601, "uid": 10234, "start_ticks": 42}
        child = {"name": smoke.RENDERER_PROCESS, "pid": 602, "uid": 10234, "start_ticks": 57}
        for change in ({"pid": 601}, {"uid": 9999}, {"pid": "602; kill -9 601"}, {"name": smoke.PACKAGE}):
            with self.subTest(change=change), self.assertRaises(smoke.CheckFailure):
                smoke.renderer_kill_script(shell, child | change)
        script = smoke.renderer_kill_script(shell, child)
        self.assertIn("/proc/601/cmdline", script)
        self.assertIn("/proc/602/status", script)
        self.assertIn('${20-}', script)
        self.assertEqual(["kill -9 602"], [line for line in script.splitlines() if line.startswith("kill ")])
        self.assertLess(script.index("/proc/602/stat"), script.index("kill -9 602"))
        self.assertNotIn("force-stop", script)

    def test_unsupported_run_as_never_runs_a_signal_or_falls_back_to_root(self):
        device = DeviceReplay(self.output)
        device.run_as_supported = False
        with device.check("death"):
            device.signal_renderer(602)
        self.assertEqual("unsupported", device.checks["death"]["status"])
        self.assertEqual([("shell", "run-as", smoke.PACKAGE, "id", "-u")], device.commands)
        self.assertEqual([], device.intentional_signals)

    def test_unreadable_identity_does_not_trigger_a_signal(self):
        device = DeviceReplay(self.output)
        device.proc_read_supported = False
        with self.assertRaises(smoke.UnsupportedCheck):
            device.signal_renderer(602)
        self.assertFalse(any("-c" in command for command in device.commands))

    def test_identity_guard_failure_is_a_failure_not_unsupported_or_passed(self):
        device = DeviceReplay(self.output)
        device.guard_returncode = 73
        with self.assertRaises(smoke.CheckFailure), device.check("death"):
            device.signal_renderer(602)
        self.assertEqual("failed", device.checks["death"]["status"])
        command = next(command for command in device.commands if "-c" in command)
        script = shlex.split(command[-1])[0]
        self.assertIn("kill -9 602", script)
        self.assertNotIn("kill -9 601", script)
        self.assertEqual(73, device.intentional_signals[0]["returncode"])

    def test_original_compose_fixture_exposes_parent_tag_and_child_card_description(self):
        path = Path(__file__).resolve().parents[2] / "docs/screenshots/android-34432935952/debug/practice-selected.xml"
        root = ET.parse(path).getroot()
        device = DeviceReplay(self.output)
        device.bind_ui(root)
        card = device.find(root, "game-card-0")
        self.assertEqual("", card.get("content-desc"))
        self.assertEqual({"index": 0, "rank": "Moon", "hand_count": 5}, smoke.first_card_sample(card))
        self.assertEqual({"round": 2, "table_rank": "Crown", "turn": "Your turn"}, smoke.public_anchor(root, device.visible))
        self.assertTrue(smoke.ui.selected(card))

    def test_observable_continuity_rejects_changed_round_rank_turn_card_or_count(self):
        before = {"public": {"round": 2, "table_rank": "Crown", "turn": "Your turn"},
                  "first_card": {"index": 0, "rank": "Moon", "hand_count": 5}}
        self.assertIn("no internal session ID", smoke.compare_continuity(before, copy.deepcopy(before))["limit"])
        for group, key, value in (("public", "round", 3), ("public", "table_rank", "Star"),
                                  ("public", "turn", "Orbit's turn"), ("first_card", "rank", "Wild"),
                                  ("first_card", "hand_count", 4)):
            after = copy.deepcopy(before)
            after[group][key] = value
            with self.subTest(key=key), self.assertRaises(smoke.CheckFailure):
                smoke.compare_continuity(before, after)

    def test_private_semantics_are_rejected_even_with_extra_description_text(self):
        for attributes in ({"resource-id": "game-card-0"}, {"content-desc": "Selected. Moon. Card 1 of 5. Button."}):
            root = ET.Element("hierarchy")
            ET.SubElement(root, "node", attributes)
            with self.subTest(attributes=attributes), self.assertRaises(smoke.CheckFailure):
                smoke.GodotSessionSmoke.assert_no_private_semantics(root)

    def test_native_ready_with_a_cover_or_compose_controls_is_rejected(self):
        device = DeviceReplay(self.output)
        root = ET.fromstring(native_xml())
        self.assertIsNotNone(device.native_controls(root))
        button = next(node for node in root.iter("node") if node.get("text") == "Standard table")
        button.set("class", "android.view.View")
        with self.assertRaises(smoke.CheckFailure):
            device.native_controls(root)
        button.set("class", "android.widget.Button")
        ET.SubElement(root, "node", {"package": smoke.PACKAGE, "text": "Your cards stay private", "bounds": "[20,400][700,800]"})
        device.bind_ui(ET.fromstring(ET.tostring(root)))
        with self.assertRaises(smoke.CheckFailure):
            device.native_controls(device.ui_root)

    def test_ready_chrome_in_the_wrong_activity_cannot_pass_a_capture(self):
        device = DeviceReplay(self.output)
        device.foreground = smoke.MAIN_COMPONENT
        with self.assertRaises(smoke.CheckFailure):
            device.capture_evidence("wrong-activity", smoke.NATIVE_COMPONENT, 602)
        receipt = json.loads((self.output / "captures/wrong-activity.json").read_text())
        self.assertEqual("failed", receipt["status"])
        self.assertEqual(device.raw, (self.output / "captures/wrong-activity.xml").read_bytes())
        self.assertEqual(device.screenshot, (self.output / "captures/wrong-activity.png").read_bytes())

    def test_a_restarted_shell_cannot_count_as_a_continuous_session(self):
        device = DeviceReplay(self.output)
        state = copy.deepcopy(device.state())
        state["shell_pids"] = [701]
        with self.assertRaises(smoke.CheckFailure):
            device.require_shell(state)
        state = copy.deepcopy(device.state())
        state["processes"][0]["uid"] = 10235
        with self.assertRaises(smoke.CheckFailure):
            device.require_shell(state)

    def test_original_png_xml_and_hashes_are_retained_without_reencoding(self):
        device = DeviceReplay(self.output)
        receipt = device.capture_evidence("original", smoke.NATIVE_COMPONENT, 602)
        self.assertEqual(device.raw, (self.output / "captures/original.xml").read_bytes())
        self.assertEqual(device.screenshot, (self.output / "captures/original.png").read_bytes())
        self.assertEqual(smoke.sha256_file(self.output / "captures/original.xml"), receipt["ui"]["sha256"])
        self.assertEqual("captured", receipt["status"])
        self.assertIn("not atomically", receipt["provenance"])
        self.assertIn("Requires visual review", receipt["pixel_privacy"])
        with self.assertRaises(smoke.CheckFailure):
            device.capture_evidence("original", smoke.NATIVE_COMPONENT, 602)

    def test_zero_exit_failed_uiautomator_dump_cannot_reuse_stale_xml(self):
        device = DeviceReplay(self.output)
        device.dump_ui()
        device.dump_succeeds = False
        with self.assertRaises(subprocess.CalledProcessError):
            device.dump_ui()
        self.assertIsNone(device.last_xml_bytes)
        self.assertEqual(("shell", "rm", "-f", "/sdcard/partydeck-ci-godot-session-ui.xml"), device.commands[-3])

    def test_invalid_screenshot_is_preserved_as_failure_bytes(self):
        device = DeviceReplay(self.output)
        device.screenshot = b"screencap failed\n"
        with self.assertRaises(smoke.CheckFailure):
            device.capture_evidence("bad-png", smoke.NATIVE_COMPONENT, 602)
        self.assertEqual(device.screenshot, (self.output / "captures/bad-png-invalid-screencap.bin").read_bytes())
        self.assertFalse((self.output / "captures/bad-png.png").exists())
        self.assertEqual("failed", json.loads((self.output / "captures/bad-png.json").read_text())["status"])

    def test_valid_ihdr_alone_does_not_make_a_truncated_png_a_capture(self):
        device = DeviceReplay(self.output)
        device.screenshot = png()[:33]
        with self.assertRaises(smoke.CheckFailure):
            device.capture_evidence("truncated-png", smoke.NATIVE_COMPONENT, 602)
        self.assertEqual(device.screenshot, (self.output / "captures/truncated-png-invalid-screencap.bin").read_bytes())
        self.assertFalse((self.output / "captures/truncated-png.png").exists())
        self.assertEqual("failed", json.loads((self.output / "captures/truncated-png.json").read_text())["status"])

    def test_png_requires_complete_chunks_crc_and_decodable_scanlines(self):
        def chunk(kind, value):
            return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value))

        corrupt_crc = bytearray(png())
        corrupt_crc[29] ^= 1
        for raw in (png()[:-12], png() + b"extra", bytes(corrupt_crc),
                    png()[:33] + chunk(b"IDAT", b"not zlib") + chunk(b"IEND", b""),
                    png()[:33] + chunk(b"IDAT", zlib.compress(b"\x05\x11\x22\x33")) + chunk(b"IEND", b""),
                    png()[:33] + chunk(b"IDAT", zlib.compress(b"\x00\x11")) + chunk(b"IEND", b"")):
            with self.subTest(raw=raw), self.assertRaises(smoke.CheckFailure):
                smoke.png_dimensions(raw)

    def test_unexpected_invitation_is_not_written_as_original_evidence(self):
        device = DeviceReplay(self.output, b'<hierarchy><node text="partydeck:v1:secret" /></hierarchy>')
        with self.assertRaises(smoke.CheckFailure):
            device.capture_evidence("invitation", diagnostic=True)
        self.assertTrue(device.sensitive_surface)
        self.assertFalse((self.output / "captures/invitation.png").exists())
        self.assertFalse((self.output / "captures/invitation.xml").exists())
        self.assertFalse((self.output / "last-ui.xml").exists())

    def test_malformed_bearer_xml_prevents_screenshot_even_when_xml_cannot_parse(self):
        device = DeviceReplay(self.output, b'<hierarchy><node text="partydeck:v1:synthetic_test_bearer">')
        with self.assertRaises(smoke.CheckFailure):
            device.capture_evidence("malformed-invitation", diagnostic=True)
        self.assertTrue(device.sensitive_surface)
        self.assertFalse(any(command == ("exec-out", "screencap", "-p") for command in device.commands))
        self.assertFalse((self.output / "captures/malformed-invitation.xml").exists())

    def test_xml_character_references_cannot_hide_an_invitation_from_the_guard(self):
        device = DeviceReplay(self.output, b'<hierarchy><node text="partydeck&#58;v1&#58;synthetic" /></hierarchy>')
        with self.assertRaises(smoke.CheckFailure):
            device.capture_evidence("encoded-invitation", diagnostic=True)
        self.assertTrue(device.sensitive_surface)
        self.assertFalse(any(command == ("exec-out", "screencap", "-p") for command in device.commands))

    def test_existing_output_is_not_modified(self):
        prior = self.output / "prior-result.json"
        prior.write_bytes(b"retained receipt\n")
        with self.assertRaises(FileExistsError):
            smoke.fresh_output(self.output)
        self.assertEqual(b"retained receipt\n", prior.read_bytes())

    def test_cli_reports_unsupported_as_exit_two_and_never_passed(self):
        class UnsupportedReplay(smoke.GodotSessionSmoke):
            def setup_session(self, apk):
                pass

            def run_mode(self, mode, skip_renderer_death):
                with self.check(f"{mode}.renderer-death"):
                    raise smoke.UnsupportedCheck("host-only unsupported fixture")

            def diagnostics(self):
                return []

            def restore_environment(self):
                return []

        apk = self.output / "input.apk"
        apk.write_bytes(b"host-only fixture, never installed")
        output = self.output / "fresh-run"
        with patch.object(smoke, "GodotSessionSmoke", UnsupportedReplay), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            status = smoke.main(["--serial", "host-only", "--apk", str(apk), "--output", str(output),
                                 "--source-revision", "a" * 40, "--modes", "2d"])
        self.assertEqual(2, status)
        result = json.loads((output / "godot-session-result.json").read_text())
        self.assertEqual("unsupported", result["status"])
        self.assertFalse(result["passed"])
        self.assertEqual(["2d"], result["requested_modes"])


if __name__ == "__main__":
    unittest.main()
