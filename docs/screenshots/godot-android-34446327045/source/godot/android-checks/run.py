#!/usr/bin/env python3
"""Qualify real Godot Android entries through native controls, adb touch and observed evidence."""

import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import time
import zipfile

from evidence import (
    CheckFailure, HostTrace, Rect, accepted_intent, active, completed_teardown, concealed,
    control_named, counter, healthy, local_transition, parse_document, read_png, require,
    require_rendered_pixels, scroll_gesture, touch_point, validate_host,
)


REPOSITORY = pathlib.Path(__file__).resolve().parents[2]
BASELINE_PATH = REPOSITORY / "scripts/smoke-android-ui.py"
PACKAGE = "dev.partydeck.godot.compare"
APP_LABEL = "PartyDeck · Godot comparison"
PRIVATE_FILE = "files/godot-qualification.json"
SETUP_SECONDS = 600
MODE_SECONDS = 900
ENTRY_SECONDS = 45
ACTION_SECONDS = 30
EXIT_SECONDS = 25
CLEANUP_SECONDS = 180
MAX_SCROLLS = 16
MAX_MATCH_ACTIONS = 300
REFERENCE_COUNTS = {"play": 2, "challenge": 2, "advance_round": 13}

# Reuse the checked device preparation/dump/input helpers without editing the
# production harness or installing the production application. This module is
# private to this process; only its package/activity constants are configured.
_spec = importlib.util.spec_from_file_location("partydeck_comparison_device", BASELINE_PATH)
baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(baseline)
baseline.PACKAGE = PACKAGE
baseline.ACTIVITY = f"{PACKAGE}/.ComparisonActivity"


class Device(baseline.AndroidSmoke):
    def __init__(self, serial, output, access):
        super().__init__(serial, output, "godot-comparison")
        self.access = access
        self.deadline = None
        self.ui_dump_attempts = 0
        self.ui_dump_result = None

    def timeout(self, limit):
        if self.deadline is None:
            return limit
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, f"{self.stage}: the bounded qualification deadline expired.")
        return min(limit, remaining)

    def adb(self, *arguments, timeout=20, binary=False):
        if arguments == ("shell", "uiautomator", "dump", "/sdcard/partydeck-ci-ui.xml") and not binary:
            # uiautomator can report failure on stderr while exiting zero.
            self.ui_dump_result = self.command(*arguments, timeout=timeout)
            self.ui_dump_result.check_returncode()
            return self.ui_dump_result.stdout
        return super().adb(*arguments, timeout=self.timeout(timeout), binary=binary)

    def command(self, *arguments, timeout=10):
        return subprocess.run(["adb", "-s", self.serial, *arguments], capture_output=True,
                              text=True, timeout=self.timeout(timeout), check=False)

    def pids(self, process_name):
        result = self.command("shell", "pidof", process_name)
        if result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip():
            return set()
        require(result.returncode == 0 and not result.stderr.strip()
                and re.fullmatch(r"[1-9][0-9]*(?:\s+[1-9][0-9]*)*\s*", result.stdout) is not None,
                "Could not establish actual Android process presence.")
        return {int(value) for value in result.stdout.split()}

    def pid_exists(self, pid):
        require(type(pid) is int and pid > 0, "Invalid process ID probe.")
        result = self.command("shell", "test", "-d", f"/proc/{pid}")
        require(result.returncode in (0, 1) and not result.stdout.strip() and not result.stderr.strip(),
                "Could not establish whether the old native PID still exists.")
        return result.returncode == 0

    def read_host(self, allow_missing=False):
        arguments = (("shell", "run-as", PACKAGE, "cat", PRIVATE_FILE) if self.access == "run-as" else
                     ("shell", "cat", f"/data/user/0/{PACKAGE}/{PRIVATE_FILE}"))
        result = self.command(*arguments)
        if result.returncode != 0:
            path = PRIVATE_FILE if self.access == "run-as" else f"/data/user/0/{PACKAGE}/{PRIVATE_FILE}"
            missing = (result.stdout + result.stderr).strip() == f"cat: {path}: No such file or directory"
            if allow_missing and result.returncode == 1 and missing:
                return None
            raise CheckFailure("Could not read the real app-private host evidence with the selected access mode.")
        require(not result.stderr.strip(), "Unexpected error while reading host evidence.")
        return validate_host(parse_document(result.stdout))

    def dump_ui(self, deadline=None):
        self.ui_dump_attempts += 1
        # An unsuccessful acquisition must invalidate the previous input tree.
        self.ui_root, self.ui_parents = None, {}
        self.ui_dump_result = None
        try:
            # The shared helper removes the device XML before every dump/read.
            return super().dump_ui(deadline)
        except baseline.TRANSIENT_ERRORS as error:
            self.ui_root, self.ui_parents = None, {}

            def text(value):
                return value.decode(errors="replace") if isinstance(value, bytes) else value

            try:
                failure = {
                    "attempt": self.ui_dump_attempts, "stage": self.stage,
                    "error_type": type(error).__name__, "error": str(error),
                    "returncode": getattr(error, "returncode", None),
                    "stdout": text(getattr(error, "stdout", None)),
                    "stderr": text(getattr(error, "stderr", None)),
                    "dump_returncode": getattr(self.ui_dump_result, "returncode", None),
                    "dump_stdout": text(getattr(self.ui_dump_result, "stdout", None)),
                    "dump_stderr": text(getattr(self.ui_dump_result, "stderr", None)),
                }
                with (self.output / "ui-dump-failures.log").open("a") as stream:
                    stream.write(baseline.redacted(json.dumps(failure, sort_keys=True)) + "\n")
            except OSError as retention_error:
                raise CheckFailure("Could not retain the failed fresh UI acquisition.") from retention_error
            raise

    def check_ui(self, deadline=None):
        deadline = time.monotonic() + ACTION_SECONDS if deadline is None else deadline
        if self.deadline is not None:
            deadline = min(deadline, self.deadline)
        last_error = None
        while time.monotonic() < deadline:
            try:
                root = self.dump_ui(deadline)
            except baseline.TRANSIENT_ERRORS as error:
                last_error = error
            else:
                # A crash/ANR is not a transient dump error and is never retried.
                self.reject_crash_dialog(root)
                if time.monotonic() < deadline:
                    return root
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))
        raise CheckFailure(f"{self.stage}: Could not acquire a fresh crash-checked Android UI "
                           f"before the existing deadline: {last_error}") from last_error

    def diagnostics(self):
        super().diagnostics()
        required = ("logcat.log", "events.log", "last-anr.log", "last-ui.xml", "final-screen.png")
        errors = ("logcat.log.error.log", "events.log.error.log", "last-anr.log.error.log",
                  "ui-dump.error.log", "final-screen.error.log")
        require(all((self.output / name).is_file() for name in required)
                and not any((self.output / name).exists() for name in errors),
                "Required final Android diagnostic collection was incomplete.")
        self.reject_crash_dialog(baseline.ET.parse(self.output / "last-ui.xml").getroot())
        read_png((self.output / "final-screen.png").read_bytes())

    def native_tap(self, tag, scroll=None, seconds=ACTION_SECONDS):
        node = self.wait_for_tag(tag, scroll=scroll, seconds=seconds)
        require(node.get("package") == PACKAGE, "Native control belongs to another application.")
        self.tap_node(node, tag)

    def assert_access(self):
        require(self.adb("shell", "am", "get-current-user").strip() == "0",
                "Qualification requires the dedicated emulator's primary Android user.")
        if self.access == "run-as":
            identity = self.adb("shell", "run-as", PACKAGE, "id", "-u").strip()
            require(identity.isdigit() and int(identity) > 0, "Debug run-as did not enter the application sandbox.")
            return {"method": "debug_run_as", "uid": int(identity)}
        build_type = self.adb("shell", "getprop", "ro.build.type").strip()
        require(build_type in ("userdebug", "eng")
                and self.adb("shell", "getprop", "ro.debuggable").strip() == "1"
                and self.adb("shell", "id", "-u").strip() == "0",
                "Root observation requires already-rooted adbd on an explicitly scheduled userdebug/eng emulator.")
        return {"method": "privileged_userdebug_private_file", "build_type": build_type, "uid": 0}


class EngineLog:
    def __init__(self, device, directory, pid):
        self.device, self.pid = device, pid
        self.path = directory / "runtime-logcat.log"
        self.errors = directory / "runtime-logcat.error.log"
        self.output = self.path.open("wb")
        self.error_output = self.errors.open("wb")
        self.process = subprocess.Popen(
            ["adb", "-s", device.serial, "logcat", "-v", "threadtime", "-b", "main", "-b", "system",
             "-b", "crash", "--pid", str(pid)], stdout=self.output, stderr=self.error_output,
        )

    def check(self):
        require(self.process.poll() is None, "Live process-specific logcat collection stopped unexpectedly.")
        return self.inspect(self.path.read_text(errors="replace"), complete=False)

    @staticmethod
    def inspect(text, complete=True):
        require("Unable to exit the renderer within" not in text,
                "Upstream Godot timed out exiting its renderer; a killed process is not successful teardown.")
        require(re.search(r"FATAL EXCEPTION:|Fatal signal [0-9]+|SCRIPT ERROR:|SHADER ERROR:|Parse Error:", text) is None,
                "Native or renderer failure appeared in the actual engine process log.")
        require(re.search(r"\b(?:godot|Godot)\s*:\s*ERROR:", text) is None,
                "Godot reported an engine or resource error in the actual process log.")
        # Godot 4.7.2 logs warnings and their locations at Android ERROR priority:
        # core/io/logger.cpp:61-79, platform/android/os_android.cpp:93-97.
        # This exact cache miss returns false and falls back to source compilation:
        # https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/gles3/shader_gles3.cpp#L615
        # Classify only the paired message; compilation errors are still rejected.
        pending, unclassified, partial_line = set(), [], False
        for raw_line in text.splitlines(keepends=True):
            if not complete and not raw_line.endswith(("\n", "\r")):
                partial_line = True
                continue
            line = raw_line.rstrip("\r\n")
            entry = re.fullmatch(
                r"\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s+([1-9]\d*)\s+([1-9]\d*)"
                r"\s+E\s+godot\s*:\s*(.*)", line,
            )
            if entry is not None:
                pid, tid, message = entry.groups()
                identity = (pid, tid)
                if message == "WARNING: Failed to load cached shader, recompiling.":
                    require(identity not in pending, "Repeated shader-cache warning without its source context.")
                    pending.add(identity)
                    continue
                if (message == "at: _load_from_cache (drivers/gles3/shader_gles3.cpp:615)"
                        and identity in pending):
                    pending.remove(identity)
                    continue
            unclassified.append(line)
        require(re.search(r"\bE\s+(?:godot|Godot)\s*:", "\n".join(unclassified)) is None,
                "Godot reported an engine or resource error in the actual process log.")
        require(not complete or not pending, "Incomplete shader-cache warning source context in the actual process log.")
        # Live reads can split the two logger writes. Wait for complete evidence
        # inside the existing host deadline; final process dumps must be complete.
        return not pending and not partial_line

    def close(self):
        running = self.process.poll() is None
        try:
            if running:
                # Process death can precede delivery to the live host reader.
                # Drain the device's retained PID log before checking teardown.
                final = self.device.adb("logcat", "-d", "-v", "threadtime", "-b", "main", "-b", "system",
                                        "-b", "crash", "--pid", str(self.pid), timeout=20)
                self.path.with_name("final-process-logcat.log").write_text(baseline.redacted(final))
                self.inspect(final)
        finally:
            try:
                stopped_before_signal = self.process.poll() is not None
                if not stopped_before_signal:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=5)
            finally:
                self.output.close()
                self.error_output.close()
        require(running and not stopped_before_signal,
                "Live process-specific logcat collection stopped before the final teardown check.")
        require(not self.errors.read_text().strip(), "Process-specific logcat collection reported an error.")
        self.inspect(self.path.read_text(errors="replace"))


class Qualification:
    def __init__(self, device, output):
        self.device, self.output = device, output
        self.chooser_pid = None
        self.trace = None
        self.engine_log = None
        self.entry_output = None
        self.seen_ids, self.seen_pids = set(), set()
        self.snapshot = None
        self.journal_revision = None
        self.mode_result = None
        self.captures = {}
        self.failure_pids = set()

    def journal(self, name, value):
        directory = self.entry_output or self.output
        with (directory / name).open("a") as stream:
            stream.write(json.dumps(value, sort_keys=True) + "\n")

    def collect_failure_state(self, phase):
        # Read-only failure evidence also works when entry failed before a trace
        # or live collector was established. Never persist an unvalidated host.
        errors = []
        observed = {"phase": phase, "stage": self.device.stage}
        try:
            pids = self.device.pids(PACKAGE + ":godot")
            observed["engine_pids"] = sorted(pids)
            require(len(pids) <= 1, "Ambiguous actual engine PIDs during failure collection.")
            self.failure_pids.update(pids)
        except Exception as error:
            observed["process_error"] = baseline.redacted(str(error))
            errors.append("failure process observation: " + observed["process_error"])
        if self.trace is not None:
            self.failure_pids.add(self.trace.pid)
        try:
            observed["host"] = self.device.read_host(allow_missing=True)
        except Exception as error:
            observed["host_error"] = baseline.redacted(str(error))
            errors.append("failure host observation: " + observed["host_error"])
        self.journal("failure-host-observations.log", observed)
        return errors

    def collect_failure_logs(self):
        errors = []
        directory = self.entry_output or self.output
        # Only PIDs observed under the actual package or an established trace
        # are read, including a PID which died during final UI/screenshot capture.
        for pid in sorted(self.failure_pids):
            try:
                value = self.device.adb("logcat", "-d", "-v", "threadtime", "-b", "main", "-b", "system",
                                        "-b", "crash", "--pid", str(pid), timeout=20)
                (directory / f"failure-process-{pid}-logcat.log").write_text(baseline.redacted(value))
                EngineLog.inspect(value)
            except Exception as error:
                errors.append(f"failure process {pid} log: " + baseline.redacted(str(error)))
        return errors

    def observe(self, value):
        self.trace.accept(value)
        if value["evidenceRevision"] != self.journal_revision:
            self.journal("host-observations.log", value)
            self.journal_revision = value["evidenceRevision"]
        healthy(value)
        self.snapshot = value
        return value

    def wait_host(self, description, predicate, seconds=ACTION_SECONDS):
        deadline = min(time.monotonic() + seconds, self.device.deadline)
        while time.monotonic() < deadline:
            # Crash/ANR rejection precedes accepting a cached or fresh JSON file.
            self.device.check_ui(deadline)
            value = self.observe(self.device.read_host())
            logs_ready = self.engine_log is None or self.engine_log.check()
            if logs_ready and predicate(value):
                return value
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))
        raise CheckFailure(f"{self.device.stage}: {description} within {seconds} seconds.")

    def refresh(self, description, predicate=lambda _: True, after=None):
        ready = self.wait_host("Expected a current completed diagnostic response", active)
        old = after or ready
        requested = max(counter(ready["diagnostics"]["requestId"], "request"),
                        counter(old["diagnostics"]["requestId"], "request"))
        sequence = max(counter(ready["diagnostics"]["sequence"], "sequence"),
                       counter(old["diagnostics"]["sequence"], "sequence"))
        # Exactly one visible native request; no blind repeated Refresh tapping.
        self.device.native_tap("refresh_diagnostics")
        return self.wait_host(description, lambda value: active(value)
                              and counter(value["diagnostics"]["requestId"], "request") > requested
                              and counter(value["diagnostics"]["sequence"], "sequence") > sequence
                              and predicate(value))

    def setup(self, apk, font_scale):
        self.device.deadline = time.monotonic() + SETUP_SECONDS
        self.device.prepare_device()
        self.device.stage = "Godot APK installation"
        sdk = self.device.adb("shell", "getprop", "ro.build.version.sdk").strip()
        require(sdk.isdigit() and int(sdk) >= 33,
                "Captured qualification requires API 33+; the host keeps secure-window privacy on older Android.")
        self.device.adb("install", "-r", str(apk), timeout=120)
        require(self.device.adb("shell", "pm", "clear", PACKAGE, timeout=30).strip() == "Success",
                "Could not reset the isolated comparison application.")
        installed = self.device.adb("shell", "pm", "path", PACKAGE).strip().splitlines()
        require(len(installed) == 1 and installed[0].startswith("package:"), "Expected one installed comparison APK.")
        installed_path = installed[0].removeprefix("package:")
        require(re.fullmatch(r"/data/app/[A-Za-z0-9_./~+=-]+/base\.apk", installed_path) is not None,
                "Unexpected installed APK path.")
        installed_hash = self.device.adb("shell", "sha256sum", installed_path).split()[0]
        require(installed_hash == hashlib.sha256(apk.read_bytes()).hexdigest(),
                "Installed comparison APK differs from the requested artifact.")
        access = self.device.assert_access()
        self.device.save_setting("system", "font_scale", font_scale)
        require(self.device.adb("shell", "settings", "get", "system", "font_scale").strip() == font_scale,
                "Requested Android font scale was not applied.")
        self.device.launch("chooser")
        self.device.wait_for_tag("launch_2d", scroll="down")
        pids = self.device.pids(PACKAGE)
        require(len(pids) == 1 and not self.device.pids(PACKAGE + ":godot"),
                "The initial native chooser must have its own process and no Godot engine.")
        self.chooser_pid = next(iter(pids))
        for tag, desired in (("reference_scenario", True), ("reduce_motion", True), ("sound_enabled", False)):
            node = self.device.wait_for_tag(tag, scroll="up")
            state = baseline.checked(node)
            require(state is not None, "Native scenario/preference checkbox has no observable checked state.")
            if state != desired:
                self.device.tap_node(node, tag)
            self.device.wait_until("Expected selected native scenario/preferences",
                                   lambda root: baseline.checked(self.device.find(root, tag)) == desired)
        self.capture_native("chooser")
        return {"sdk": int(sdk), "installed_apk_sha256": installed_hash, "evidence_access": access,
                "chooser_pid": self.chooser_pid, "font_scale": font_scale,
                "preferences": {"reference_scenario": True, "reduce_motion": True, "sound_enabled": False}}

    def enter(self, mode, name):
        self.device.stage = f"{mode} {name} entry"
        self.entry_output = self.output / mode / name
        self.entry_output.mkdir(parents=True)
        self.trace, self.snapshot, self.journal_revision = None, None, None
        require(self.device.pids(PACKAGE) == {self.chooser_pid} and not self.device.pids(PACKAGE + ":godot"),
                "Entry requires the surviving chooser and no previous native engine process.")
        self.device.native_tap("launch_" + mode, scroll="down")
        deadline = min(time.monotonic() + ENTRY_SECONDS, self.device.deadline)
        while time.monotonic() < deadline:
            self.device.check_ui(deadline)
            value = self.device.read_host(allow_missing=True)
            if value is not None and value["presentationId"] not in self.seen_ids:
                require(value["mode"] == mode and value["enginePid"] not in self.seen_pids
                        and value["enginePid"] != self.chooser_pid, "Entry did not create the requested fresh native lifetime.")
                require(self.device.pids(PACKAGE + ":godot") == {value["enginePid"]},
                        "Host evidence does not identify the actual live engine process.")
                self.trace = HostTrace(value["presentationId"], mode, value["enginePid"])
                self.seen_ids.add(value["presentationId"])
                self.seen_pids.add(value["enginePid"])
                self.engine_log = EngineLog(self.device, self.entry_output, value["enginePid"])
                self.observe(value)
                break
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))
        require(self.trace is not None, "The native chooser did not create fresh host evidence within the entry bound.")
        remaining = max(0.01, deadline - time.monotonic())
        value = self.wait_host("Expected actual native setup, Ready, first view and frame delivery", active, seconds=remaining)
        require(value["capturePolicy"] == "recents_disabled", "The native host did not disable Recents screenshots.")
        require(concealed(value["diagnostics"]), "New presentation retained a private face, label or selection.")
        require(value["publicState"]["canPlay"] and value["publicState"]["viewerHandCount"] == 5,
                "The fixed reference scenario did not start at its real viewer opener.")
        self.mode_result.setdefault("entries", []).append({"name": name, "presentation_id": value["presentationId"],
                                                          "engine_pid": value["enginePid"], "task_id": value["taskId"]})
        self.device.record(f"Verified real {mode} {name} setup, Ready and concealed renderer")
        return value

    def control(self, action, card_index=-1):
        self.device.stage = f"{self.trace.mode} {action} reachability"
        value = self.refresh("Expected fresh scene geometry before " + action)
        previous_geometry, stationary = None, 0
        for attempt in range(MAX_SCROLLS + 1):
            diagnostic = value["diagnostics"]
            control = control_named(diagnostic, action, card_index)
            require(control is not None and control["enabled"], "The actual scene offers no enabled " + action + " control.")
            rect, clip = Rect.read(control["rect"], "control"), Rect.read(control["clipRect"], "control clip")
            if control["visible"] and clip.encloses(rect):
                touch_point(diagnostic, control, value.get("engineSurface"), self.device.display_size)
                return value, control
            require(attempt < MAX_SCROLLS, "The scene control remained clipped after the bounded real scroll sequence.")
            geometry = (control["rect"], control["clipRect"])
            stationary = stationary + 1 if geometry == previous_geometry else 0
            require(stationary < 2, "The actual scene scroll did not move the clipped target.")
            previous_geometry = geometry
            start, end, duration_ms = scroll_gesture(diagnostic, control, value.get("engineSurface"), self.device.display_size)
            self.scene_input(value, control, "swipe", {"start": start, "end": end, "duration_ms": duration_ms})
            self.device.adb("shell", "input", "swipe", *(str(part) for point in (start, end) for part in point), str(duration_ms))
            after = self.refresh("Expected fresh scene geometry after scrolling", after=value)
            local_transition(value, after)
            value = after
        raise CheckFailure("Unreachable scene control.")

    def scene_input(self, value, control, kind, coordinates):
        # The latest UI must still be app-owned; do not apply old geometry to HOME.
        root = self.device.check_ui()
        require(any(node.get("package") == PACKAGE and node.get("resource-id", "").endswith("/host_status")
                    for node in root.iter("node")), "The native game window is no longer visible for scene input.")
        current = self.observe(self.device.read_host())
        require(active(current) and current["revision"] == value["revision"]
                and current.get("engineSurface") == value.get("engineSurface")
                and current["diagnostics"]["sequence"] == value["diagnostics"]["sequence"],
                "Scene geometry changed before input; refusing stale coordinates.")
        self.journal("scene-input-geometry.log", {
            "stage": self.device.stage, "action": kind, "presentationId": value["presentationId"],
            "revision": value["revision"], "diagnosticRequest": value["diagnostics"]["requestId"],
            "diagnosticSequence": value["diagnostics"]["sequence"], "group": control["group"],
            "cardIndex": control["cardIndex"], "rect": control["rect"], "clipRect": control["clipRect"],
            "rootViewport": value["diagnostics"]["viewport"], "engineSurface": value["engineSurface"],
            "coordinates": coordinates,
        })

    def tap_scene(self, action, card_index=-1):
        value, control = self.control(action, card_index)
        point = touch_point(value["diagnostics"], control, value.get("engineSurface"), self.device.display_size)
        self.scene_input(value, control, "tap", {"x": point[0], "y": point[1]})
        self.device.adb("shell", "input", "tap", str(point[0]), str(point[1]))
        return value

    def local_action(self, action, predicate, card_index=-1):
        before = self.tap_scene(action, card_index)
        after = self.refresh("Expected local scene response to " + action, predicate, after=before)
        local_transition(before, after)
        return after

    def reveal_select(self, capture=False):
        value = self.local_action("reveal", lambda item: not item["diagnostics"]["handConcealed"]
                                  and item["diagnostics"]["privateFaceCount"] > 0
                                  and item["diagnostics"]["privateLabelCount"] > 0)
        if capture:
            self.capture_scene("02-revealed", value)
        value = self.local_action("card", lambda item: item["diagnostics"]["selectedCount"] == 1
                                  and control_named(item["diagnostics"], "card", 0)["selected"], card_index=0)
        if capture:
            self.capture_scene("03-selected", value)
        return value

    def submit(self, action, kind):
        before = self.tap_scene(action)
        after = self.refresh("Expected exactly one real " + kind + " authority round trip",
                             lambda item: counter(item["acceptedIntents"], "intents") >
                             counter(before["acceptedIntents"], "intents"), after=before)
        accepted_intent(before, after, kind)
        require(concealed(after["diagnostics"]), "A submitted action or newer view retained private UI state.")
        self.mode_result["intent_counts"][kind] += 1
        return after

    def capture_native(self, name):
        directory = self.entry_output or self.output
        root = self.device.check_ui()
        data = self.device.adb("exec-out", "screencap", "-p", binary=True, timeout=15)
        picture = read_png(data)
        require((picture.width, picture.height) == self.device.display_size, "Capture uses an unexpected display orientation.")
        (directory / (name + ".png")).write_bytes(data)
        (directory / (name + ".xml")).write_text(baseline.ET.tostring(root, encoding="unicode"))
        self.device.record("Captured " + name)
        return picture

    def capture_scene(self, name, value):
        require(active(value), "Cannot capture a noninteractive or covered engine surface as a scene.")
        picture = self.capture_native(name)
        current = self.observe(self.device.read_host())
        require(active(current) and current["revision"] == value["revision"]
                and current["engineSurface"] == value["engineSurface"], "The engine changed during the required capture.")
        pixels = picture.crop(value["engineSurface"])
        require_rendered_pixels(pixels)
        digest = hashlib.sha256(pixels).hexdigest()
        (self.entry_output / (name + ".json")).write_text(json.dumps(value, indent=2) + "\n")
        self.journal("captures.log", {"name": name, "engine_rgb_sha256": digest, "surface": value["engineSurface"],
                                      "presentationId": value["presentationId"], "revision": value["revision"]})
        self.captures[name] = digest
        return digest

    def background(self):
        before = self.reveal_select()
        self.device.stage = f"{self.trace.mode} background privacy"
        self.device.adb("shell", "input", "keyevent", "KEYCODE_HOME")
        background = self.wait_host("Expected native cover and foreground rejection before pause",
                                    lambda item: item["lifecycle"] == "background" and not item["foreground"]
                                    and item["coverVisible"] and not item["foregroundFrameReady"])
        local_transition(before, background)
        require(self.device.pids(PACKAGE + ":godot") == {self.trace.pid}, "Backgrounding unexpectedly killed the engine.")
        resolved = self.device.adb("shell", "cmd", "package", "resolve-activity", "--brief", "-a",
                                   "android.intent.action.MAIN", "-c", "android.intent.category.HOME")
        components = re.findall(r"^([A-Za-z0-9_.]+)/(?:[A-Za-z0-9_.$]+)$", resolved, re.MULTILINE)
        require(components, "Could not identify Android's current HOME Activity.")
        home_package = components[-1]
        self.device.wait_until("Expected the actual launcher after backgrounding",
                               lambda root: any(node.get("package") == home_package for node in root.iter("node")))
        self.capture_native("05-background-home")
        self.device.adb("shell", "input", "keyevent", "KEYCODE_APP_SWITCH")
        self.device.wait_until("Expected the real launcher Overview panel",
                               lambda root: (
                                   any(node.get("package") == home_package
                                       and node.get("resource-id", "").endswith("/overview_panel")
                                       for node in root.iter("node"))
                                   and any(node.get("package") == home_package
                                           and APP_LABEL in (node.get("text", "") + node.get("content-desc", ""))
                                           for node in root.iter("node"))))
        self.capture_native("06-recents-privacy")
        paused = self.observe(self.device.read_host())
        require(not paused["foreground"] and paused["coverVisible"] and paused["capturePolicy"] == "recents_disabled",
                "The native host became exposed while its task was in Overview.")
        focused = self.device.adb("shell", "am", "task", "focus", str(before["taskId"]))
        require(f"Setting focus to task {before['taskId']}" in focused,
                "Android did not focus the existing native task.")
        resumed = self.refresh("Expected the same resumed presentation with all private bindings cleared",
                               lambda item: concealed(item["diagnostics"]), after=before)
        local_transition(before, resumed)
        require(self.device.pids(PACKAGE + ":godot") == {self.trace.pid}
                and self.device.pids(PACKAGE) == {self.chooser_pid}, "Resume replaced a native process.")
        self.capture_scene("07-resumed-concealed", resumed)
        self.mode_result["background_privacy"] = {
            "same_pid_and_presentation": True, "native_cover_observed": True,
            "resumed_private_bindings_and_selection_cleared": True, "recents_capture_policy": "recents_disabled",
            "recents_visual_review": "Required; inspect 06-recents-privacy.png. No pixel classifier proves privacy.",
        }

    def settle(self):
        return self.refresh("Expected opponent progression to an actionable viewer turn or actual round end",
                            lambda item: item["publicState"]["phase"] != "PLAYING"
                            or item["publicState"]["canPlay"] or item["publicState"]["canChallenge"])

    def match(self, mode):
        value = self.enter(mode, "match")
        self.capture_scene("01-concealed", value)
        self.reveal_select(capture=True)
        require(self.captures["01-concealed"] != self.captures["02-revealed"],
                "Revealing actual cards produced no changed rendered pixels.")
        hidden = self.local_action("hide", lambda item: concealed(item["diagnostics"]))
        self.capture_scene("04-covered", hidden)
        self.background()
        self.reveal_select()
        self.submit("play", "play")
        value = self.settle()
        self.capture_scene("08-after-play", value)
        outcomes = {}
        for _ in range(MAX_MATCH_ACTIONS):
            public = value["publicState"]
            if public["phase"] in ("ROUND_ENDED", "FINISHED"):
                outcomes[public["roundNumber"]] = {name: public[name] for name in ("truthful", "burnedOut")}
                require(concealed(value["diagnostics"]), "Round outcome retained private hand state.")
                if "09-public-outcome" not in self.captures:
                    self.capture_scene("09-public-outcome", value)
            if public["phase"] == "FINISHED":
                # Canonical seed-2 fixture/comparison receipts: 14 rounds, 41
                # authority revisions, two viewer plays/challenges, 13 advances.
                require(self.mode_result["intent_counts"] == REFERENCE_COUNTS
                        and public["roundNumber"] == 14 and value["revision"] == "41",
                        "The Android match differs from the canonical real-authority reference scenario.")
                require(public["winnerPresent"], "The real authority did not identify a winner.")
                self.mode_result["outcomes"] = outcomes
                self.mode_result["winner_round"] = public["roundNumber"]
                self.capture_scene("12-winner", value)
                self.return_to_chooser(mode)
                return
            if public["phase"] == "ROUND_ENDED":
                self.submit("next_round", "advance_round")
                value = self.settle()
                require(value["publicState"]["roundNumber"] == public["roundNumber"] + 1,
                        "Actual next-round input did not advance exactly one authority round.")
                if "10-next-round" not in self.captures:
                    self.capture_scene("10-next-round", value)
                continue
            if public["canChallenge"]:
                self.submit("challenge", "challenge")
                value = self.settle()
                if "11-after-challenge" not in self.captures:
                    self.capture_scene("11-after-challenge", value)
            else:
                require(public["canPlay"], "No projected viewer action is available after opponent progression.")
                self.reveal_select()
                self.submit("play", "play")
                value = self.settle()
        raise CheckFailure("The real authority did not reach a winner within the fixed action bound.")

    def return_to_chooser(self, mode):
        before = self.tap_scene("lobby")
        # The actual 2D scene confirms ending an unfinished match; after a
        # winner its Lobby action returns directly through the native bridge.
        if mode == "2d" and before["publicState"]["phase"] != "FINISHED":
            confirmation = self.refresh("Expected the unfinished-match lobby confirmation", lambda item: (
                control_named(item["diagnostics"], "lobby_confirm") is not None
                and control_named(item["diagnostics"], "lobby_confirm")["visible"]), after=before)
            local_transition(before, confirmation)
            self.capture_scene("13-lobby-confirmation", confirmation)
            before = self.tap_scene("lobby_confirm")
        final = self.exit_entry("return_to_chooser")
        accepted_intent(before, final, "return_to_lobby", changes_view=False)

    def exit_entry(self, reason):
        self.device.stage = f"{self.trace.mode} {reason} native teardown"
        final = self.wait_host("Expected final native destruction evidence",
                               lambda item: item["lifecycle"] == "process_exit_requested", seconds=EXIT_SECONDS)
        completed_teardown(final, reason)
        deadline = min(time.monotonic() + EXIT_SECONDS, self.device.deadline)
        while time.monotonic() < deadline:
            self.device.check_ui(deadline)
            if (not self.device.pids(PACKAGE + ":godot") and not self.device.pid_exists(self.trace.pid)):
                break
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))
        else:
            raise CheckFailure("Native teardown markers were written, but the actual old engine PID remains alive.")
        require(self.device.pids(PACKAGE) == {self.chooser_pid}, "Engine teardown killed or replaced the native chooser.")
        for tag in ("launch_2d", "launch_3d"):
            node = self.device.wait_for_tag(tag, scroll="down", seconds=EXIT_SECONDS)
            require(node.get("package") == PACKAGE, "The post-exit launch controls belong to another application.")
        # Read the retained final file once more after process death.
        retained = self.observe(self.device.read_host())
        completed_teardown(retained, reason)
        self.engine_log.close()
        self.engine_log = None
        self.capture_native("14-chooser-after-exit")
        (self.entry_output / "teardown.json").write_text(json.dumps({
            "host": retained, "old_pid_absent": True, "engine_process_absent": True,
            "surviving_chooser_pid": self.chooser_pid, "both_entries_enabled": True,
            "upstream_renderer_timeout_absent": True,
        }, indent=2) + "\n")
        self.device.record("Verified native destruction, actual PID absence and surviving chooser: " + reason)
        return final

    def reentry(self, mode, kind):
        value = self.enter(mode, kind)
        self.capture_scene("01-fresh-concealed", value)
        if kind == "scene-exit":
            before = self.tap_scene("exit")
            final = self.exit_entry("renderer_exit")
            require(counter(final["receivedEvents"], "events") == counter(before["receivedEvents"], "events") + 1,
                    "Actual scene Exit did not return through the native bridge.")
            for name in ("receivedIntents", "acceptedIntents"):
                require(final[name] == before[name], "Exit unexpectedly submitted an authority gameplay intent.")
        else:
            before = self.snapshot
            if mode == "2d":
                self.device.native_tap("exit_game")
                reason = "native_close"
            else:
                self.device.back()
                reason = "native_back"
            final = self.exit_entry(reason)
            local_transition(before, final)

    def run_mode(self, mode):
        self.device.deadline = time.monotonic() + MODE_SECONDS
        self.mode_result = {"mode": mode, "passed": False,
                            "intent_counts": {"play": 0, "challenge": 0, "advance_round": 0}}
        self.captures = {}
        self.match(mode)
        self.reentry(mode, "scene-exit")
        self.reentry(mode, "native-exit")
        self.mode_result["passed"] = True
        (self.output / mode / "result.json").write_text(json.dumps(self.mode_result, indent=2) + "\n")
        return self.mode_result


def apk_facts(apk):
    require(apk.is_file(), "The requested APK does not exist.")
    with zipfile.ZipFile(apk) as archive:
        member = archive.getinfo("assets/partydeck-last-light.pck")
        require(0 < member.file_size <= 512 * 1024 * 1024, "The APK has no bounded real renderer pack.")
        with archive.open(member) as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(), "apk_bytes": apk.stat().st_size,
            "embedded_pck_sha256": digest, "embedded_pck_bytes": member.file_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--apk", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--mode", choices=("both", "2d", "3d"), default="both")
    parser.add_argument("--font-scale", choices=("1.0", "2.0"), default="1.0")
    parser.add_argument("--evidence-access", choices=("run-as", "root"), default="run-as")
    arguments = parser.parse_args()
    require(not arguments.output.exists() or not any(arguments.output.iterdir()), "Use a new or empty evidence directory.")
    arguments.output.mkdir(parents=True, exist_ok=True)
    modes = ("2d", "3d") if arguments.mode == "both" else (arguments.mode,)
    result = {"passed": False, "modes": list(modes), "serial": arguments.serial, "mode_results": [],
              "scope": "Real local-practice Godot Android input/lifecycle; no production session, TalkBack, physical LAN or store qualification.",
              "limits_seconds": {"setup": SETUP_SECONDS, "per_mode": MODE_SECONDS, "cleanup": CLEANUP_SECONDS},
              "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (
                  pathlib.Path(__file__), pathlib.Path(__file__).with_name("evidence.py"), BASELINE_PATH)}}
    device = Device(arguments.serial, arguments.output, arguments.evidence_access)
    qualification = Qualification(device, arguments.output)
    failure = None
    device_started = False
    try:
        result.update(apk_facts(arguments.apk))
        device_started = True
        result["device"] = qualification.setup(arguments.apk, arguments.font_scale)
        for mode in modes:
            result["mode_results"].append(qualification.run_mode(mode))
        result["passed"] = True
    except Exception as error:
        failure = error
        result["error"] = baseline.redacted(str(error))
        result["stage"] = device.stage
        if qualification.mode_result is not None and qualification.mode_result not in result["mode_results"]:
            result["mode_results"].append(qualification.mode_result)
    finally:
        device.deadline = time.monotonic() + CLEANUP_SECONDS
        cleanup_errors = []
        try:
            if qualification.engine_log is not None:
                qualification.engine_log.close()
                qualification.engine_log = None
        except Exception as error:
            cleanup_errors.append("engine logs: " + baseline.redacted(str(error)))
        if device_started:
            collect_failure = failure is not None and qualification.entry_output is not None
            if collect_failure:
                try:
                    cleanup_errors.extend(qualification.collect_failure_state("before_final_diagnostics"))
                except Exception as error:
                    cleanup_errors.append("failure evidence: " + baseline.redacted(str(error)))
            try:
                device.diagnostics()
            except Exception as error:
                cleanup_errors.append("diagnostics: " + baseline.redacted(str(error)))
            finally:
                if collect_failure:
                    try:
                        cleanup_errors.extend(qualification.collect_failure_state("after_final_diagnostics"))
                    except Exception as error:
                        cleanup_errors.append("failure evidence: " + baseline.redacted(str(error)))
                    try:
                        cleanup_errors.extend(qualification.collect_failure_logs())
                    except Exception as error:
                        cleanup_errors.append("failure logs: " + baseline.redacted(str(error)))
                try:
                    cleanup_errors.extend(device.restore_environment())
                except Exception as error:
                    cleanup_errors.append("settings restoration: " + baseline.redacted(str(error)))
        if cleanup_errors:
            result["passed"] = False
            result["cleanup_errors"] = cleanup_errors
        result["steps"] = device.steps
        try:
            (arguments.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        except OSError:
            if failure is None:
                raise
    if not result["passed"]:
        print(result.get("error", "Godot diagnostic collection or settings restoration failed."), file=sys.stderr)
        return 1
    print("Real Android " + "/".join(modes) + " Godot qualification passed; inspect retained captures for visual review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
