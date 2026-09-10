#!/usr/bin/env python3
"""Prepare-only candidate for production Android Godot adaptive UI observations.

Installs/clears the exact supplied APK on a dedicated device. Requires the frozen
session checker and host ffmpeg/ffprobe. Uses real practice and renderer choices.
Native gameplay, Back/card dragging, opening races and pixel privacy require
separate execution/review. No app test hooks or direct private Activity launch.
"""

import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid

from adaptive_observations import (
    ObservationFailure, Unavailable, activity_records, attributed_focus, before_up,
    component, held_touch, input_clock, no_active_touch, require, split_capability,
    split_pair, stable_key, tracked_changes, window_display,
)


SESSION_SHA256 = "dd8723ec9233597790a727ec266896c9ac67ae1445d940a71b068a0d8d068b12"
UI_SHA256 = "fc208dfbb04356eff921f5388996afc06eecff53ceb8347e621508eba7c85741"


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def load_session(path):
    require(sha256(path) == SESSION_SHA256, "Session checker does not match the independently accepted bytes.")
    require(sha256(path.with_name("smoke-android-ui.py")) == UI_SHA256, "Session UI dependency changed.")
    spec = importlib.util.spec_from_file_location("partydeck_adaptive_pinned_session", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def recorder_signal_script(identity, argv):
    require(argv[0] == "/system/bin/screenrecord" and len(argv) == 6
            and argv[1:3] == ["--time-limit", "60"] and argv[3] == "--size"
            and re.fullmatch(r"\d+x\d+", argv[4])
            and re.fullmatch(r"/sdcard/partydeck-adaptive-[0-9a-f]{32}\.mp4", argv[5]),
            "Refusing an unrecognized recorder command.")
    require(type(identity["pid"]) is int and identity["pid"] > 0
            and type(identity["uid"]) is int and identity["uid"] >= 0
            and type(identity["start_ticks"]) is int and identity["start_ticks"] > 0,
            "Invalid recorder process identity.")
    require(identity["name"] == argv[0], "Recorder name does not match the owned command.")
    pid = identity["pid"]
    expected = shlex.quote("\n".join(argv))
    return "\n".join([
        "set -eu",
        f'[ "$(id -u)" = "{identity["uid"]}" ] || exit 70',
        f'record_task_cmd=$(tr \'\\000\' \'\\n\' < /proc/{pid}/cmdline) || exit 71',
        f'[ "$record_task_cmd" = {expected} ] || exit 72',
        f'record_task_stat=$(cat /proc/{pid}/stat) || exit 73',
        'record_task_tail=${record_task_stat##*) }',
        'set -- $record_task_tail',
        f'[ "${{20-}}" = "{identity["start_ticks"]}" ] || exit 74',
        f'record_task_uids=$(sed -n \'s/^Uid:[[:space:]]*//p\' /proc/{pid}/status) || exit 75',
        'set -- $record_task_uids',
        f'[ "$#" = 4 ] && [ "$1" = "{identity["uid"]}" ] && [ "$2" = "$1" ] && [ "$3" = "$1" ] && [ "$4" = "$1" ] || exit 76',
        f"kill -2 {pid}",
        "printf 'PARTYDECK_SCREENRECORD_SIGINT\\n'",
    ])


def verify_video(path, width, height, output_prefix):
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries",
                            "stream=codec_type,width,height,nb_read_frames:format=duration", "-of", "json", str(path)],
                           capture_output=True, text=True, timeout=45, check=False)
    output_prefix.with_suffix(".ffprobe.json").write_text(probe.stdout)
    output_prefix.with_suffix(".ffprobe.log").write_text(probe.stderr)
    require(probe.returncode == 0 and not probe.stderr.strip(), "Original video failed ffprobe.")
    payload = json.loads(probe.stdout)
    streams = payload.get("streams", [])
    require(len(streams) == 1 and streams[0].get("codec_type") == "video", "Expected one original screenrecord video stream.")
    stream = streams[0]
    require((stream.get("width"), stream.get("height")) == (width, height)
            and str(stream.get("nb_read_frames", "")).isdigit()
            and int(stream["nb_read_frames"]) >= 2
            and float(payload.get("format", {}).get("duration", 0)) > 0,
            "Original video lacks complete frames at the requested canvas size.")
    decode = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                             "-map", "0:v:0", "-f", "null", "-"],
                            capture_output=True, text=True, timeout=45, check=False)
    output_prefix.with_suffix(".decode.log").write_text(decode.stdout + decode.stderr)
    require(decode.returncode == 0 and not decode.stderr.strip(), "Original transition video did not decode cleanly.")
    return dict(file=path.name, sha256=sha256(path), bytes=path.stat().st_size,
                width=width, height=height, frames=int(stream["nb_read_frames"]),
                duration_seconds=float(payload["format"]["duration"]),
                pixel_privacy="Review required; decode success does not establish cover order or privacy.")


class OriginalRecording:
    def __init__(self, smoke, name, dimensions):
        self.smoke, self.name = smoke, name
        self.width, self.height = dimensions
        self.remote = f"/sdcard/partydeck-adaptive-{uuid.uuid4().hex}.mp4"
        self.argv = ["/system/bin/screenrecord", "--time-limit", "60", "--size",
                     f"{self.width}x{self.height}", self.remote]
        self.process, self.identity, self.handles = None, None, []
        self.path_available, self.started_successfully = False, False
        self.entry = dict(name=name, status="starting", started_utc=smoke.session.utc_now(),
                          argv=self.argv, canvas=list(dimensions), projection="Original fixed canvas; Android updates full-display projection on rotation.")
        smoke.videos.append(self.entry)

    def start(self):
        require(self.width > 0 and self.height > 0 and self.width % 2 == self.height % 2 == 0,
                "Screenrecord canvas requires observed positive even dimensions.")
        require(self.smoke.command("shell", "test", "-e", self.remote).returncode == 1,
                "Recording path already exists or cannot be checked.")
        self.path_available = True
        uid = self.smoke.adb("shell", "id", "-u").strip()
        require(uid.isdigit(), "Cannot attribute recorder UID.")
        self.uid = int(uid)
        for extension in ("stdout.log", "stderr.log"):
            self.handles.append((self.smoke.output / "videos" / f"{self.name}.{extension}").open("xb"))
        self.process = subprocess.Popen(["adb", "-s", self.smoke.serial, "shell", *self.argv],
                                        stdout=self.handles[0], stderr=self.handles[1])
        deadline = time.monotonic() + 8
        previous_size = None
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise Unavailable("Device screenrecord could not keep the requested original recording running.")
            candidates = []
            for pid in self.smoke.pids("screenrecord"):
                raw = self.smoke.command("exec-out", "cat", f"/proc/{pid}/cmdline", binary=True)
                if raw.returncode != 0 or raw.stdout != b"\0".join(item.encode() for item in self.argv) + b"\0":
                    continue
                status = self.smoke.adb("shell", "cat", f"/proc/{pid}/status")
                stat = self.smoke.adb("shell", "cat", f"/proc/{pid}/stat")
                candidates.append(self.smoke.session.parse_proc_identity(pid, self.argv[0], self.uid, raw.stdout, status, stat))
            require(len(candidates) <= 1, "Multiple exact owned recorders; refusing ambiguous cleanup.")
            if candidates:
                self.identity = candidates[0]
                current = self.smoke.command("shell", "stat", "-c", "%s", self.remote)
                if current.returncode == 0 and current.stdout.strip().isdigit():
                    current_size = int(current.stdout.strip())
                    if previous_size is not None and current_size > previous_size > 0:
                        self.started_successfully = True
                        self.entry.update(status="recording", identity=self.identity, growth_observed_utc=self.smoke.session.utc_now(),
                                          initial_file_sizes=[previous_size, current_size])
                        return
                    previous_size = current_size
            time.sleep(0.25)
        raise Unavailable("Cannot prove the exact recorder identity and growing original output on this device.")

    def finish(self):
        errors = []
        completed = self.process is None
        try:
            if self.process is not None and self.process.poll() is None and self.identity is not None:
                try:
                    script = recorder_signal_script(self.identity, self.argv)
                    self.entry["stop_requested_utc"] = self.smoke.session.utc_now()
                    result = self.smoke.command("shell", "sh", "-c", shlex.quote(script), timeout=10)
                    self.entry["signal"] = dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
                    require(result.returncode == 0 and result.stdout.strip() == "PARTYDECK_SCREENRECORD_SIGINT",
                            "Recorder identity guard refused the owned stop signal.")
                except Exception as error:
                    # Still await the recorder's own limit and retain completed
                    # failure evidence if the stop identity check failed.
                    errors.append(error)
            if self.process is not None:
                # An unattributable recorder is allowed to reach its own 60 s
                # limit. No broad kill or unrelated process signal is used.
                for _ in range(4):
                    try:
                        self.entry["returncode"] = self.process.wait(timeout=20)
                        completed = True
                        break
                    except subprocess.TimeoutExpired:
                        pass
                else:
                    raise ObservationFailure("Owned adb recording transport did not finish within its bounded cleanup wait.")
                if self.started_successfully and self.entry["returncode"] != 0:
                    errors.append(ObservationFailure("Device recording command did not finish successfully."))
            try:
                self.smoke.dump_ui()
            except Exception as error:
                self.entry["final_ui_guard_error"] = self.smoke.session.ui.redacted(str(error))
            if self.smoke.sensitive_surface:
                self.entry.update(status="withheld-sensitive-surface", reason="Unexpected invitation prevents preserving this recording.")
            elif self.process is not None and self.smoke.command("shell", "test", "-e", self.remote).returncode == 0:
                path = self.smoke.output / "videos" / f"{self.name}.mp4"
                self.smoke.write_text(f"videos/{self.name}.pull.log", self.smoke.adb("pull", self.remote, str(path), timeout=30))
                # Keep original MP4 even if validation fails.
                self.entry["original"] = dict(file=str(path.relative_to(self.smoke.output)), sha256=sha256(path), bytes=path.stat().st_size)
                if self.started_successfully:
                    self.entry["validation"] = verify_video(path, self.width, self.height, path.with_suffix(""))
                    self.entry["status"] = "captured-review-required"
                else:
                    self.entry["status"] = "startup-unavailable-original-retained"
            elif not self.started_successfully:
                self.entry["status"] = "startup-unavailable"
            else:
                errors.append(ObservationFailure("Completed recording lost its original output."))
        except Exception as error:
            self.entry.update(status="failed", error=self.smoke.session.ui.redacted(str(error)))
            errors.append(error)
        finally:
            for handle in self.handles:
                handle.close()
            # Only this random path belongs to this recording. Failed originals
            # stay local; sensitive originals are never pulled.
            try:
                if self.path_available and completed:
                    self.smoke.adb("shell", "rm", "-f", self.remote)
                elif self.path_available:
                    self.entry["remote_retained"] = self.remote
            except Exception as error:
                errors.append(error)
            self.entry["ended_utc"] = self.smoke.session.utc_now()
            self.smoke.write_json(f"videos/{self.name}.json", self.entry)
        if errors:
            self.entry["errors"] = [self.smoke.session.ui.redacted(str(error)) for error in errors]
            self.entry["status"] = "failed"
            self.smoke.write_json(f"videos/{self.name}.json", self.entry)
            raise errors[0]

    def checkpoint(self, label):
        require(self.identity is not None, "Recorder checkpoint lacks owned process identity.")
        pid = self.identity["pid"]
        raw = self.smoke.adb("exec-out", "cat", f"/proc/{pid}/cmdline", binary=True)
        require(raw == b"\0".join(item.encode() for item in self.argv) + b"\0",
                "Owned recorder command changed before the transition checkpoint.")
        status = self.smoke.adb("shell", "cat", f"/proc/{pid}/status")
        stat = self.smoke.adb("shell", "cat", f"/proc/{pid}/stat")
        identity = self.smoke.session.parse_proc_identity(pid, self.argv[0], self.uid, raw, status, stat)
        require(identity == self.identity, "Recorder lifetime changed before the transition checkpoint.")
        size = self.smoke.adb("shell", "stat", "-c", "%s", self.remote).strip()
        require(size.isdigit() and int(size) >= self.entry["initial_file_sizes"][-1],
                "Original recording output disappeared before the transition checkpoint.")
        self.entry.setdefault("checkpoints", []).append(dict(label=label, utc=self.smoke.session.utc_now(),
                                                             identity=identity, output_bytes=int(size)))


class AdaptiveScenarios:
    def __init__(self, session, serial, output, variant, font_scale, hold_ms):
        super().__init__(serial, output, variant, font_scale)
        self.session, self.hold_ms = session, hold_ms
        self.state_sequence, self.observation_sequence = 0, 0
        self.videos, self.adaptive_observations, self.cleanup_errors = [], [], []
        self.saved_rotation, self.split_owned = None, False
        self.input_incomplete = False
        self.companion_task = None
        for name in ("states", "observations", "videos"):
            (output / name).mkdir()

    @contextmanager
    def check(self, name):
        with super().check(name) as entry:
            try:
                yield entry
            except Unavailable as error:
                raise self.session.UnsupportedCheck(str(error)) from error

    def state(self):
        # Small reviewed extension of the pinned process observation. Do not
        # monkeypatch its global single-window parser.
        for _ in range(3):
            self.state_sequence += 1
            started = self.session.utc_now()
            activity = self.adb("shell", "dumpsys", "activity", "activities")
            window = self.adb("shell", "dumpsys", "window", "displays")
            shell_pids, child_pids = self.pids(self.session.PACKAGE), self.pids(self.session.RENDERER_PROCESS)
            processes = self.read_process_table()
            prefix = f"states/{self.state_sequence:05d}"
            for kind, raw in (("activity", activity), ("window", window), ("processes", processes)):
                self.write_text(f"{prefix}-{kind}.log", raw)
                self.write_text(f"logs/last-{kind}.log", raw)
            rows = self.session.parse_process_table(processes)
            relevant, consistent = [], True
            for name, pids in ((self.session.PACKAGE, shell_pids), (self.session.RENDERER_PROCESS, child_pids)):
                require(len(pids) <= 1, "Multiple exact app processes; cannot attribute lifetime.")
                actual = sorted(pid for pid, row in rows.items() if row["name"] == name)
                consistent &= actual == pids
                relevant.extend(rows[pid] for pid in actual)
            records, resumed = activity_records(activity)
            display = window_display(window)
            focus = attributed_focus(records, resumed, display)
            expected_focus_name = {self.session.MAIN_COMPONENT: self.session.PACKAGE,
                                   self.session.NATIVE_COMPONENT: self.session.RENDERER_PROCESS}.get(focus["component"]) if focus else None
            if expected_focus_name is not None:
                row = rows.get(focus.get("app_pid"))
                consistent &= (row is not None and row["name"] == expected_focus_name
                               and focus.get("process_name") == expected_focus_name)
            state = dict(started_utc=started, ended_utc=self.session.utc_now(), foreground=focus,
                         processes=relevant, shell_pids=shell_pids, renderer_pids=child_pids,
                         activities=records, resumed=resumed, display=display, original_log_prefix=prefix,
                         sampling="Sequential Activity, WM and process reads; unmatched focus is unattributed.")
            self.write_json(prefix + ".json", state)
            if consistent:
                return state
            time.sleep(0.05)
        raise ObservationFailure("App PID/name identity did not settle across independent observations.")

    def save_observation(self, name, raw=None, **fields):
        self.observation_sequence += 1
        prefix = f"observations/{self.observation_sequence:04d}-{name}"
        entry = dict(name=name, utc=self.session.utc_now(), stage=self.stage, **fields)
        if raw is not None:
            path = self.output / (prefix + ".log")
            path.write_text(raw)
            entry["raw"] = dict(file=str(path.relative_to(self.output)), sha256=sha256(path))
        self.write_json(prefix + ".json", entry)
        self.adaptive_observations.append(entry)
        return entry

    def input_observation(self, name):
        raw = self.adb("shell", "dumpsys", "input", timeout=10)
        return raw, self.save_observation(name, raw=raw)

    def stable_activity(self, target, orientation=None, rotation=None, mode=None, seconds=35):
        deadline, previous = time.monotonic() + seconds, None
        while time.monotonic() < deadline:
            state = self.state()
            self.require_shell(state)
            focus = state["foreground"]
            if focus and focus["component"] == target:
                cfg = focus["configuration"]
                if (orientation is None or cfg["orientation"] == orientation) and (mode is None or cfg["windowing_mode"] == mode) and (rotation is None or state["display"]["rotation"] == cfg["display_rotation"] == rotation):
                    key = stable_key(state)
                    if previous == key:
                        return state
                    previous = key
                else:
                    previous = None
            else:
                previous = None
            time.sleep(0.2)
        raise ObservationFailure("Actual focused Activity configuration/window mode did not stabilize as requested.")

    def set_rotation(self, rotation, target, orientation):
        require(type(rotation) is int and 0 <= rotation <= 3, "Invalid rotation request.")
        self.save_observation("rotation-request", requested_rotation=rotation)
        self.adb("shell", "wm", "user-rotation", "-d", "0", "lock", str(rotation))
        actual = self.adb("shell", "wm", "user-rotation", "-d", "0").strip()
        require(actual == f"lock {rotation}", "Android did not retain the requested user rotation lock.")
        return self.stable_activity(target, orientation=orientation, rotation=rotation)

    def prepare_capabilities(self):
        for command in ("ffprobe", "ffmpeg"):
            if shutil.which(command) is None:
                raise Unavailable(f"Host {command} is unavailable; original transition video cannot be validated.")
            version = subprocess.run([command, "-version"], capture_output=True, text=True, timeout=10, check=True)
            self.write_text(f"identity/{command}.log", version.stdout + version.stderr)
        self.saved_rotation = self.adb("shell", "wm", "user-rotation", "-d", "0").strip()
        require(re.fullmatch(r"free|lock [0-3]", self.saved_rotation), "Cannot save the exact original user rotation policy.")
        self.save_observation("original-rotation", policy=self.saved_rotation)
        path = self.adb("shell", "command", "-v", "screenrecord").strip()
        if path != "/system/bin/screenrecord":
            raise Unavailable("The verified system screenrecord executable is unavailable.")
        help_result = self.command("shell", path, "--help")
        self.write_json("identity/screenrecord-help.json", dict(returncode=help_result.returncode,
                                                                stdout=help_result.stdout, stderr=help_result.stderr))
        if help_result.returncode != 0:
            raise Unavailable("System screenrecord help/capability query failed.")

    @contextmanager
    def recording(self, name, state):
        clip = OriginalRecording(self, name, state["display"]["size"])
        primary_error = None
        try:
            clip.start()
            yield clip
        except BaseException as error:
            primary_error = error
            raise
        finally:
            try:
                clip.finish()
            except Exception as error:
                self.cleanup_errors.append(f"{name}: {self.session.ui.redacted(str(error))}")
                if primary_error is None:
                    raise

    def begin_practice(self, prefix):
        self.tap_action("home-practice")
        self.wait_for_human_turn()
        self.assert_concealed()
        baseline = self.observe_match(prefix)
        self.select_first_card(prefix)
        return baseline

    def concealed_readonly(self, state, root):
        if not self.matches_activity(state, self.session.MAIN_COMPONENT) or state["renderer_pids"]:
            return False
        require(state["foreground"]["task_id"] == self.shell_task, "Return changed the retained shell task.")
        require(not any(item["component"] == self.session.NATIVE_COMPONENT for item in state["activities"]),
                "Native Activity remains after supposed retirement.")
        self.assert_no_private_semantics(root)
        require(self.text_node(root, "Leave the table?") is None, "Held touch opened a stale Leave dialog.")
        return self.find(root, "game-reveal-hand") is not None

    def rotate_while_held(self, pid, before, portrait_rotation, prefix):
        controls = self.dump_ui()
        require(self.native_controls(controls) is not None, "Held-input entry lacks real native Ready/chrome.")
        control = self.find_action(controls, "native-standard-table", "Standard table")
        require(control is not None, "Native Standard table control is not reachable.")
        bounds = self.session.ui.intersect_bounds(self.session.ui.node_bounds(control), self.viewport(control))
        require(bounds is not None, "Native control has no observed visible bounds.")
        point = [(bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2]
        path = self.output / "observations" / f"{prefix}-held-control.xml"
        path.write_bytes(self.last_xml_bytes)
        geometry = self.save_observation("held-control", bounds=list(bounds), point=point,
                                         xml=dict(file=str(path.relative_to(self.output)), sha256=sha256(path)),
                                         scope="Continuous touch on native Standard table control; no Back or card-drag coverage.")
        raw, _ = self.input_observation("before-held-touch")
        require(no_active_touch(raw), "Another active pointer prevents attributing this injected gesture.")
        # Verify device-clock capability before starting the gesture.
        pre_clock = input_clock(raw)
        arguments = ["adb", "-s", self.serial, "shell", "input", "touchscreen", "-d", "0", "swipe",
                     str(point[0]), str(point[1]), str(point[0]), str(point[1]), str(self.hold_ms)]
        with self.recording(prefix + "-rotation", before) as recording:
            with (self.output / "observations" / f"{prefix}-input.stdout.log").open("xb") as stdout, (self.output / "observations" / f"{prefix}-input.stderr.log").open("xb") as stderr:
                process = subprocess.Popen(arguments, stdout=stdout, stderr=stderr)
                self.input_incomplete = True
                gesture = self.save_observation("held-input-start", argv=arguments, geometry=geometry, duration_ms=self.hold_ms)
                try:
                    held = None
                    for _ in range(10):
                        require(process.poll() is None, "Continuous input ended before target delivery was observed.")
                        first = self.state()
                        self.require_shell(first)
                        require(self.matches_activity(first, self.session.NATIVE_COMPONENT) and first["renderer_pids"] == [pid],
                                "Native Activity lost foreground before the adaptive transition.")
                        raw, observation = self.input_observation("held-target")
                        try:
                            held = held_touch(raw, first["foreground"]["window"], pid, self.shell_identity["uid"], point)
                        except ObservationFailure:
                            time.sleep(0.1)
                            continue
                        last = self.state()
                        require(stable_key(first) == stable_key(last) and stable_key(last) == stable_key(before),
                                "Native target/configuration changed around the held-touch observation.")
                        require(held["down_time_ns"] + 1_000_000 > pre_clock["lower_ns"],
                                "Held touch downTime predates this injection's clock boundary.")
                        deadline = before_up(input_clock(raw), held, self.hold_ms)
                        require(deadline["remaining_lower_bound_ns"] > 8_000_000_000, "Insufficient device-observed hold remains for rotation.")
                        gesture.update(held=held, target_observation=observation, pre_rotation_deadline=deadline)
                        break
                    if held is None:
                        raise Unavailable("Platform did not expose a corroborated live touch on the exact native target.")
                    self.save_observation("held-rotation-request", rotation=portrait_rotation)
                    self.adb("shell", "wm", "user-rotation", "-d", "0", "lock", str(portrait_rotation))
                    end = time.monotonic() + self.hold_ms / 1000
                    returned = None
                    while time.monotonic() < end:
                        require(process.poll() is None, "Input ended before the concealed return was observed.")
                        after = self.state()
                        self.require_shell(after)
                        if not self.matches_activity(after, self.session.MAIN_COMPONENT) or after["renderer_pids"]:
                            time.sleep(0.1)
                            continue
                        root = self.dump_ui(deadline=time.monotonic() + 8)
                        if not self.concealed_readonly(after, root):
                            continue
                        cfg = after["foreground"]["configuration"]
                        require(after["display"]["rotation"] == cfg["display_rotation"] == portrait_rotation
                                and cfg["orientation"] == "port", "Rotation command did not produce actual portrait geometry.")
                        changes = tracked_changes(before["foreground"]["configuration"], cfg)
                        require(changes, "No tracked configuration/size change was observed.")
                        raw, clock_observation = self.input_observation("after-concealed-return-clock")
                        proof = before_up(input_clock(raw), held, self.hold_ms)
                        require(process.poll() is None, "Input transport ended before the device deadline proof completed.")
                        xml_path = self.output / "observations" / f"{prefix}-concealed-before-up.xml"
                        xml_path.write_bytes(self.last_xml_bytes)
                        returned = self.save_observation("concealed-before-up", state=after, changes=changes,
                                                         deadline=proof, clock=clock_observation,
                                                         xml=dict(file=str(xml_path.relative_to(self.output)), sha256=sha256(xml_path)))
                        break
                    require(returned is not None, "No read-only concealed return was observed during the held stream.")
                    gesture["return_before_up"] = returned
                finally:
                    # Absolutely no taps, swipes, selection/reveal helpers or task
                    # changes until this exact continuous stream has finished.
                    try:
                        gesture["returncode"] = process.wait(timeout=self.hold_ms / 1000 + 20)
                        if gesture["returncode"] == 0:
                            self.input_incomplete = False
                    except subprocess.TimeoutExpired as error:
                        gesture["status"] = "input-transport-timeout"
                        raise ObservationFailure("Continuous input did not complete; no further UI actions are permitted.") from error
                    finally:
                        gesture["ended_utc"] = self.session.utc_now()
                        self.write_json(f"observations/{prefix}-held-input-result.json", gesture)
                    require(gesture["returncode"] == 0, "Continuous input did not finish successfully.")
            final = self.wait_activity(self.session.MAIN_COMPONENT, child_absent=True)
            root = self.dump_ui()
            require(self.concealed_readonly(final, root), "Concealed return changed after matching UP.")
            self.capture_evidence(prefix + "-after-up", self.session.MAIN_COMPONENT)
            recording.checkpoint("concealed-return-and-up-completed")
        return gesture

    def finish_practice(self, mode, baseline, prefix):
        self.select_first_card(prefix + "-leave")
        self.enter_native(mode, prefix + "-leave")
        self.tap_action("native-leave-table", "Leave table", scroll=None)
        self.leave_dialog(prefix + "-leave")
        self.tap_action("leave-confirm", "Leave table")
        self.wait_for_action("home-practice", scroll="down")
        self.wait_activity(self.session.MAIN_COMPONENT, child_absent=True)
        self.capture_evidence(prefix + "-home", self.session.MAIN_COMPONENT)

    def landscape_scenario(self, mode, direction):
        prefix = f"{mode}-{direction}"
        with self.check(prefix + ".initial-landscape") as entry:
            display = self.state()["display"]
            self.set_rotation(display[direction], self.session.MAIN_COMPONENT, "land")
            baseline = self.begin_practice(prefix + "-baseline")
            pid, task, _ = self.enter_native(mode, prefix + "-initial")
            native = self.stable_activity(self.session.NATIVE_COMPONENT, "land", display[direction], "fullscreen")
            entry.update(baseline=baseline, renderer_pid=pid, task_id=task, actual=native)
        with self.check(prefix + ".held-rotation") as entry:
            entry["gesture"] = self.rotate_while_held(pid, native, display["portrait"], prefix)
            entry["observable_continuity"] = self.require_concealed_return(baseline, prefix + "-rotation-return")
        # If the narrow held-input capability was unavailable before rotation,
        # recover through actual UI and keep its unsupported outcome. Recovery
        # is never counted as a held-input or adaptive success.
        if self.checks[prefix + ".held-rotation"]["status"] == "unsupported":
            state = self.state()
            if self.matches_activity(state, self.session.NATIVE_COMPONENT):
                self.tap_action("native-standard-table", "Standard table", scroll=None)
            self.require_concealed_return(baseline, prefix + "-unsupported-return")
            self.set_rotation(display["portrait"], self.session.MAIN_COMPONENT, "port")
        with self.check(prefix + ".portrait-reentry-standard") as entry:
            self.select_first_card(prefix + "-reentry")
            fresh_pid, _, _ = self.enter_native(mode, prefix + "-portrait")
            entry["actual"] = self.stable_activity(self.session.NATIVE_COMPONENT, "port", display["portrait"], "fullscreen")
            require(fresh_pid != pid, "Re-entry reused the retired native PID.")
            self.tap_action("native-standard-table", "Standard table", scroll=None)
            entry["observable_continuity"] = self.require_concealed_return(baseline, prefix + "-standard-return")
        with self.check(prefix + ".native-leave-home"):
            self.finish_practice(mode, baseline, prefix)

    def focus_shell_task(self):
        require(type(self.shell_task) is int and self.shell_task > 0, "Missing original shell task.")
        self.adb("shell", "am", "task", "focus", str(self.shell_task))
        return self.wait_activity(self.session.MAIN_COMPONENT, child_absent=True)

    def wait_split(self, seconds=35, child_absent=True):
        deadline = time.monotonic() + seconds
        last_error = "No paired Activity geometry yet."
        while time.monotonic() < deadline:
            state = self.state()
            self.require_shell(state)
            try:
                panes = split_pair(state["activities"], self.shell_task, self.companion_task, state["display"]["size"])
                require(state["foreground"] is not None and state["foreground"]["task_id"] in (self.shell_task, self.companion_task),
                        "An unrelated window owns foreground in split-screen.")
                require(not child_absent or not state["renderer_pids"], "Native renderer did not retire on entering split-screen.")
                return state, panes
            except ObservationFailure as error:
                last_error = str(error)
                time.sleep(0.2)
        raise ObservationFailure("Advertised split request did not establish actual paired geometry: " + last_error)

    def split_scenario(self, mode):
        prefix = mode + "-split"
        with self.check(prefix + ".support") as entry:
            queries = {}
            for label, args in (("multiwindow", ("shell", "am", "supports-multiwindow")),
                                ("split_screen", ("shell", "am", "supports-split-screen-multi-window")),
                                ("help", ("shell", "wm", "shell", "help"))):
                result = self.command(*args)
                queries[label] = dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
            self.save_observation("split-capability", queries=queries)
            if any(item["returncode"] != 0 for item in queries.values()):
                raise Unavailable("Android does not expose all verified split capability/automation queries; see original command responses.")
            entry.update(split_capability(queries["multiwindow"]["stdout"], queries["split_screen"]["stdout"], queries["help"]["stdout"]))
        if self.checks[prefix + ".support"]["status"] != "passed":
            return
        with self.check(prefix + ".entry-after-ready") as entry:
            display = self.state()["display"]
            self.set_rotation(display["landscape"], self.session.MAIN_COMPONENT, "land")
            resolved = self.adb("shell", "cmd", "package", "resolve-activity", "--brief", "-a", "android.settings.DISPLAY_SETTINGS")
            self.save_observation("companion-resolved", raw=resolved)
            matches = re.findall(r"^([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)$", resolved, re.M)
            if len(matches) != 1:
                raise Unavailable("No unambiguous read-only display Settings companion resolves on this device.")
            resolved_package = component(matches[0]).split("/", 1)[0]
            self.adb("shell", "am", "start", "-W", "-a", "android.settings.DISPLAY_SETTINGS")
            companion = self.state()["foreground"]
            require(companion is not None and companion["component"].split("/", 1)[0] == resolved_package
                    and companion["task_id"] != self.shell_task, "Resolved Settings companion is not actually focused in a distinct task.")
            self.companion_task = companion["task_id"]
            entry["companion"] = companion
            self.focus_shell_task()
            baseline = self.begin_practice(prefix + "-baseline")
            pid, _, _ = self.enter_native(mode, prefix + "-full")
            before = self.stable_activity(self.session.NATIVE_COMPONENT, mode="fullscreen")
            self.split_owned = True
            with self.recording(prefix + "-entry", before) as recording:
                self.save_observation("split-entry-request", companion_task=self.companion_task, native_pid=pid)
                self.adb("shell", "wm", "shell", "splitscreen", "moveToSideStage", str(self.companion_task), "1")
                actual, panes = self.wait_split()
                require(panes[0]["component"] == self.session.MAIN_COMPONENT, "Native split entry did not return to Compose.")
                changes = tracked_changes(before["foreground"]["configuration"], panes[0]["configuration"])
                require(changes, "Split request only moved a window; no actual tracked size/configuration change.")
                self.focus_shell_task()
                self.wait_split()
                self.capture_evidence(prefix + "-entry-concealed", self.session.MAIN_COMPONENT,
                                      ui_assertion=lambda root: self.assert_no_private_semantics(root))
                recording.checkpoint("split-entry-and-concealed-return-observed")
                entry.update(actual=actual, tracked_changes=changes)
            entry["observable_continuity"] = self.require_concealed_return(baseline, prefix + "-entry-return")
        if self.checks[prefix + ".entry-after-ready"]["status"] != "passed":
            return
        with self.check(prefix + ".stable-split-launch-exit") as entry:
            self.select_first_card(prefix + "-reentry")
            self.enter_native(mode, prefix + "-pane")
            before = self.stable_activity(self.session.NATIVE_COMPONENT, mode="multi-window")
            actual, panes = self.wait_split(child_absent=False)
            require(panes[0]["component"] == self.session.NATIVE_COMPONENT, "Native renderer was not actually visible in the stable split pane.")
            entry["native_split"] = actual
            with self.recording(prefix + "-exit", before) as recording:
                self.adb("shell", "wm", "shell", "splitscreen", "exitSplitScreen", str(self.shell_task))
                self.wait_activity(self.session.MAIN_COMPONENT, child_absent=True)
                after = self.stable_activity(self.session.MAIN_COMPONENT, mode="fullscreen")
                self.split_owned = False
                changes = tracked_changes(before["foreground"]["configuration"], after["foreground"]["configuration"])
                require(changes, "Split exit did not change the actual tracked size/configuration.")
                self.capture_evidence(prefix + "-exit-concealed", self.session.MAIN_COMPONENT,
                                      ui_assertion=lambda root: self.assert_no_private_semantics(root))
                recording.checkpoint("split-exit-and-concealed-return-observed")
                entry.update(fullscreen_return=after, tracked_changes=changes)
            entry["observable_continuity"] = self.require_concealed_return(baseline, prefix + "-exit-return")
        with self.check(prefix + ".fullscreen-reentry-leave-home"):
            self.finish_practice(mode, baseline, prefix)

    def restore_adaptive(self):
        errors = list(self.cleanup_errors)
        if self.input_incomplete:
            errors.append("Input transport did not complete; no further UI mutations or environment restoration were attempted.")
            return errors
        if self.split_owned:
            try:
                self.adb("shell", "wm", "shell", "splitscreen", "exitSplitScreen", str(self.shell_task))
                self.stable_activity(self.session.MAIN_COMPONENT, mode="fullscreen")
                self.split_owned = False
            except Exception as error:
                errors.append("Owned split cleanup: " + str(error))
        if self.saved_rotation is not None:
            try:
                self.adb("shell", "wm", "user-rotation", "-d", "0", *self.saved_rotation.split())
                require(self.adb("shell", "wm", "user-rotation", "-d", "0").strip() == self.saved_rotation,
                        "Original user rotation policy was not restored.")
            except Exception as error:
                errors.append("Rotation restore: " + str(error))
        errors.extend(self.restore_environment())
        return errors


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-checker", type=Path, required=True, help="Exact independently accepted smoke-android-godot-session.py.")
    parser.add_argument("--serial", required=True)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="A fresh directory; existing evidence is never overwritten.")
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--variant", choices=("debug", "optimized-test-signed"), default="debug")
    parser.add_argument("--modes", choices=("2d", "3d"), nargs="+", default=["2d", "3d"])
    parser.add_argument("--font-scale", choices=("1.0", "2.0"), default="1.0")
    parser.add_argument("--hold-ms", type=int, default=30000, help="Continuous touch duration, 10000–45000 ms.")
    return parser


def main(argv=None):
    parser = argument_parser()
    args = parser.parse_args(argv)
    if not args.apk.is_file() or not args.session_checker.is_file():
        parser.error("Both the exact APK and accepted session checker must exist")
    if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", args.source_revision):
        parser.error("--source-revision requires 40 or 64 hexadecimal digits")
    if len(args.modes) != len(set(args.modes)) or not 10000 <= args.hold_ms <= 45000:
        parser.error("Use unique modes and a bounded 10000–45000 ms hold")
    try:
        session = load_session(args.session_checker)
        session.fresh_output(args.output)
    except (ObservationFailure, FileExistsError) as error:
        parser.error(str(error))
    runner_type = type("AdaptiveGodotSmoke", (AdaptiveScenarios, session.GodotSessionSmoke), {})
    smoke = runner_type(session, args.serial, args.output, args.variant, args.font_scale, args.hold_ms)
    smoke.identity.update(input_apk=str(args.apk.resolve()), input_apk_sha256=sha256(args.apk), input_apk_bytes=args.apk.stat().st_size,
                          accepted_session_sha256=SESSION_SHA256, accepted_ui_sha256=UI_SHA256,
                          candidate_sha256=sha256(Path(__file__)), observations_sha256=sha256(Path(__file__).with_name("adaptive_observations.py")))
    result = dict(schema_version=1, started_utc=session.utc_now(), serial=args.serial,
                  source_revision=dict(value=args.source_revision.lower(), attribution="Caller-supplied; not embedded source/APK proof."),
                  variant=args.variant, modes=args.modes, font_scale=args.font_scale, identity=smoke.identity,
                  checks=smoke.checks, captures=smoke.captures, videos=smoke.videos, observations=smoke.adaptive_observations,
                  steps=smoke.steps,
                  limits=["Automated host/chrome, configuration and lifecycle observations; no engine gameplay assertion.",
                          "Original transition pixels require review for concealment and cover ordering.",
                          "Held input is one native Standard-control touch; Back-key and card-drag cases remain outstanding.",
                          "Held-touch deadline evidence requires precise InputDispatcher times; a non-debuggable Android platform build can redact them regardless of APK variant.",
                          "Configuration change during opening, viewport-only bootstrap changes, half-turns and divider dragging are not exercised.",
                          "Actual paired multi-window geometry is required; unsupported platform or automation support is a distinct outcome.",
                          "Continuity is surviving shell/task plus round/rank/turn and one indexed card/count, not internal session identity.",
                          "Single-device practice only; physical-network and store-device qualification are separate."])
    failed, aborted_unsupported = False, False
    try:
        smoke.prepare_capabilities()
        smoke.setup_session(args.apk)
        require(smoke.shell_identity is not None, "No installed exact-APK shell identity was established.")
        for mode in args.modes:
            for direction in ("landscape", "seascape"):
                smoke.landscape_scenario(mode, direction)
            smoke.split_scenario(mode)
    except (Unavailable, session.UnsupportedCheck) as error:
        aborted_unsupported = True
        result.update(unsupported_reason=session.ui.redacted(str(error)), stopped_stage=smoke.stage)
    except Exception as error:
        failed = True
        result.update(error=session.ui.redacted(str(error)), failed_stage=smoke.stage)
        print(f"FAILED {smoke.stage}: {session.ui.redacted(str(error))}", file=sys.stderr, flush=True)
    finally:
        try:
            errors = smoke.diagnostics() if smoke.logcat_started else []
        except Exception as error:
            errors = [str(error)]
        try:
            errors.extend(smoke.restore_adaptive())
        except Exception as error:
            errors.append("Cleanup: " + str(error))
        if errors:
            failed = True
            result["diagnostic_or_restore_errors"] = [session.ui.redacted(error) for error in errors]
        unsupported = aborted_unsupported or any(entry["status"] == "unsupported" for entry in smoke.checks.values())
        result.update(status="failed" if failed else "unsupported" if unsupported else "passed-automated-scope",
                      pixel_privacy_review="required", ended_utc=session.utc_now())
        result["artifacts"] = [dict(file=str(path.relative_to(args.output)), bytes=path.stat().st_size, sha256=sha256(path))
                               for path in sorted(args.output.rglob("*")) if path.is_file()]
        smoke.write_json("godot-adaptive-result.json", result)
    print(f"Android adaptive observations: {result['status']}; {args.output / 'godot-adaptive-result.json'}", flush=True)
    return 1 if failed else 2 if unsupported else 0


if __name__ == "__main__":
    sys.exit(main())
