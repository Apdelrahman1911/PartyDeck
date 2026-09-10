#!/usr/bin/env python3
"""Observe production Android renderer switching through the real practice UI.

This checker installs and clears the specified app on a dedicated test device.
It never enables renderer choices, launches the private Activity directly, or
uses app test hooks. A Ready label is native host evidence, not engine gameplay
evidence. Original native/Recents pixels require a separate visual review.

Platform contracts checked against Android android-16.0.0_r1 sources:
  frameworks/base/services/core/java/com/android/server/wm/Task.java
  frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java
  frameworks/base/services/core/java/com/android/server/am/ActivityManagerShellCommand.java
  system/core/run-as/run-as.cpp; external/toybox/toys/lsb/pidof.c
  packages/apps/Launcher3/quickstep/res/layout/{overview_panel,fallback_recents_activity}.xml
Toybox ps formatting also checked against android-15.0.0_r1 and android-16.0.0_r1:
  external/toybox/toys/posix/ps.c
Sources: https://android.googlesource.com/platform/
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zlib


HELPER_PATH = Path(__file__).with_name("smoke-android-ui.py")
_SPEC = importlib.util.spec_from_file_location("partydeck_session_ui_helpers", HELPER_PATH)
ui = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = ui
_SPEC.loader.exec_module(ui)

PACKAGE = ui.PACKAGE
RENDERER_PROCESS = f"{PACKAGE}:godot"
MAIN_COMPONENT = f"{PACKAGE}/{PACKAGE}.MainActivity"
NATIVE_COMPONENT = f"{PACKAGE}/{PACKAGE}.godot.SessionGodotActivity"
READY = "Table ready."
OPENING = "Opening table…"
CARD = re.compile(r"^(Crown|Moon|Star|Wild)\. Card (\d+) of (\d+)\.$")
ACTIVITY_RECORD = re.compile(
    r"ActivityRecord\{[^{}\n]*?\bu(\d+) ([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+) t(\d+)(?:[^{}\n]*)\}"
)
RECENTS_IDS = {"overview_panel"}


class CheckFailure(RuntimeError):
    pass


class UnsupportedCheck(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise CheckFailure(message)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fresh_output(path):
    # Even an empty pre-existing directory may belong to another run.
    path.mkdir(parents=True, exist_ok=False)


def canonical_component(value):
    require(re.fullmatch(r"[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+", value), "Invalid Activity component.")
    package, activity = value.split("/", 1)
    return f"{package}/{package + activity if activity.startswith('.') else activity}"


def parse_pidof(returncode, stdout, stderr):
    if returncode == 1 and not stdout.strip() and not stderr.strip():
        return []
    require(returncode == 0 and not stderr.strip(), "pidof failed; absence is not established.")
    tokens = stdout.split()
    require(tokens and all(re.fullmatch(r"[1-9]\d*", value) for value in tokens), "Malformed pidof output.")
    pids = [int(value) for value in tokens]
    require(len(pids) == len(set(pids)), "Duplicate PID in pidof output.")
    return sorted(pids)


def parse_process_table(value):
    lines = [line for line in value.splitlines() if line.strip()]
    # Toybox pads the final NAME header, but not the final process-name field.
    # Normalize header whitespace only; process names must retain exact identity.
    require(lines and lines[0].split() == ["PID", "UID", "NAME"], "Unrecognized Android ps PID/UID/NAME output.")
    rows = {}
    for line in lines[1:]:
        fields = line.split(None, 2)
        require(len(fields) == 3 and re.fullmatch(r"[0-9]+", fields[0])
                and re.fullmatch(r"[0-9]+", fields[1]), "Malformed Android ps row.")
        pid, uid, name = int(fields[0]), int(fields[1]), fields[2]
        require(pid > 0 and pid not in rows, "Invalid or duplicate Android ps PID.")
        rows[pid] = {"pid": pid, "uid": uid, "name": name}
    return rows


def parse_focused_activity(value):
    # RootWindowContainer prints the focused Activity as "Resumed:" for each
    # task display area. A historical ActivityRecord or a merely resumed task
    # (topResumedActivity) does not establish foreground focus.
    display = None
    saw_default_display = False
    focused = []
    for line in value.splitlines():
        header = re.match(r"^Display #(\d+) \(activities from top to bottom\):", line)
        if header:
            display = int(header.group(1))
            saw_default_display |= display == 0
        if display != 0 or not re.match(r"^\s+Resumed:\s", line):
            continue
        match = ACTIVITY_RECORD.search(line)
        require(match is not None, "Unrecognized focused ActivityRecord format.")
        focused.append({"user_id": int(match[1]), "component": canonical_component(match[2]),
                        "task_id": int(match[3]), "display_id": 0})
    require(saw_default_display, "Activity dump lacks the verified default-display format.")
    unique = {json.dumps(item, sort_keys=True): item for item in focused}
    require(len(unique) <= 1, "Multiple focused Activities; this single-display smoke cannot attribute the foreground.")
    return next(iter(unique.values()), None)


def parse_proc_identity(pid, expected_name, expected_uid, cmdline, status, stat):
    name = cmdline.split(b"\0", 1)[0].decode("utf-8", errors="strict")
    require(name == expected_name, "Process cmdline does not match the exact expected app process.")
    uid = re.search(r"^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$", status, re.MULTILINE)
    require(uid is not None and all(int(value) == expected_uid for value in uid.groups()),
            "Process UID changed or is not the installed app UID.")
    end = stat.rfind(")")
    require(re.match(rf"^{pid} \(", stat) is not None and end >= 0, "Malformed /proc PID identity.")
    fields = stat[end + 1:].split()  # Field 3 (state) through the end; comm may contain spaces.
    require(len(fields) >= 20 and fields[19].isdigit() and int(fields[19]) > 0,
            "Missing process start time; refusing an unguarded signal.")
    return {"pid": pid, "uid": expected_uid, "name": name, "start_ticks": int(fields[19])}


def renderer_kill_script(shell, renderer):
    require(shell["name"] == PACKAGE and renderer["name"] == RENDERER_PROCESS,
            "Signal target names are not the exact shell and renderer.")
    require(shell["pid"] != renderer["pid"] and shell["uid"] == renderer["uid"],
            "Refusing a signal without distinct shell/renderer PIDs and a shared app UID.")
    for identity in (shell, renderer):
        for field in ("pid", "uid", "start_ticks"):
            require(type(identity[field]) is int and identity[field] > 0, "Invalid numeric signal identity.")
    statements = ["set -eu", f'[ "$(id -u)" = "{shell["uid"]}" ] || exit 70']
    for identity in (shell, renderer):
        pid = identity["pid"]
        statements += [
            f'[ "$(tr \'\\000\' \'\\n\' < /proc/{pid}/cmdline | head -n 1)" = "{identity["name"]}" ] || exit 71',
            f'proc_stat=$(cat /proc/{pid}/stat) || exit 72',
            'proc_tail=${proc_stat##*) }',
            'set -- $proc_tail',
            f'[ "${{20-}}" = "{identity["start_ticks"]}" ] || exit 73',
            f'proc_uids=$(sed -n \'s/^Uid:[[:space:]]*//p\' /proc/{pid}/status) || exit 74',
            'set -- $proc_uids',
            f'[ "$#" = 4 ] && [ "$1" = "{identity["uid"]}" ] && [ "$2" = "$1" ] && [ "$3" = "$1" ] && [ "$4" = "$1" ] || exit 75',
        ]
    statements += [f"kill -9 {renderer['pid']}", "printf 'PARTYDECK_RENDERER_SIGNALLED\\n'"]
    return "\n".join(statements)


def public_anchor(root, visible):
    values = {" ".join(node.get("text", "").split()) for node in root.iter("node")
              if node.get("package") == PACKAGE and visible(node)}
    rounds = [int(match[1]) for text in values if (match := re.fullmatch(r"ROUND (\d+)", text))]
    ranks = [match[1] for text in values if (match := re.fullmatch(r"(Crown|Moon|Star) table", text))]
    if len(rounds) != 1 or len(ranks) != 1 or "Your turn" not in values:
        return None
    return {"round": rounds[0], "table_rank": ranks[0], "turn": "Your turn"}


def first_card_sample(node):
    # Compose can put the checkbox/tag on the parent and the spoken card
    # description on a child (as in the retained real Android captures).
    samples = {match.groups() for child in node.iter("node")
               if child.get("package") == PACKAGE and (match := CARD.fullmatch(child.get("content-desc", "")))} if node is not None else set()
    require(len(samples) == 1, "The first card lacks one unambiguous indexed private-hand description.")
    rank, position, count = next(iter(samples))
    require(int(position) == 1 and int(count) > 0,
            "The first visible card lacks the expected indexed private-hand semantics.")
    return {"index": 0, "rank": rank, "hand_count": int(count)}


def compare_continuity(before, after):
    require(before["public"] == after["public"], "Public match state changed while no gameplay action was submitted.")
    require(before["first_card"] == after["first_card"], "The observable first card or hand count changed across presentation return.")
    return {"public": after["public"], "first_card": after["first_card"],
            "limit": "Observable round/rank/turn and one indexed card/count; no internal session ID or full-hand identity is exposed."}


def png_dimensions(value):
    """Validate a complete PNG without changing its bytes (https://www.w3.org/TR/PNG/)."""
    require(value[:8] == b"\x89PNG\r\n\x1a\n", "screencap did not return a PNG signature.")
    offset = 8
    header = None
    palette_entries = None
    compressed = bytearray()
    saw_data = False
    data_ended = False
    saw_end = False
    while offset < len(value):
        require(offset + 12 <= len(value), "Truncated PNG chunk header/CRC.")
        length = struct.unpack(">I", value[offset:offset + 4])[0]
        kind = value[offset + 4:offset + 8]
        require(re.fullmatch(rb"[A-Za-z]{4}", kind) and 65 <= kind[2] <= 90, "Invalid PNG chunk type.")
        end = offset + 12 + length
        require(length <= 0x7fffffff and end <= len(value), "Truncated or oversized PNG chunk.")
        payload = value[offset + 8:end - 4]
        expected_crc = struct.unpack(">I", value[end - 4:end])[0]
        require(zlib.crc32(kind + payload) & 0xffffffff == expected_crc, "PNG chunk CRC mismatch.")
        require(header is not None or kind == b"IHDR", "PNG does not begin with IHDR.")
        if kind == b"IHDR":
            require(header is None and length == 13 and offset == 8, "Invalid or duplicate PNG IHDR.")
            header = struct.unpack(">IIBBBBB", payload)
            width, height, depth, color, compression, filtering, interlace = header
            depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
            require(0 < width <= 0x7fffffff and 0 < height <= 0x7fffffff
                    and color in depths and depth in depths[color]
                    and compression == 0 and filtering == 0 and interlace in (0, 1), "Invalid PNG IHDR fields.")
        elif kind == b"PLTE":
            require(not saw_data and palette_entries is None and 0 < length <= 768 and length % 3 == 0
                    and header[3] not in (0, 4), "Invalid PNG palette/order.")
            palette_entries = length // 3
        elif kind == b"IDAT":
            require(not data_ended, "PNG IDAT chunks are not consecutive.")
            saw_data = True
            compressed.extend(payload)
        elif kind == b"IEND":
            require(length == 0 and saw_data and compressed and end == len(value), "PNG lacks image data or has an invalid final IEND.")
            saw_end = True
        else:
            require(kind[0] & 32, "Unknown critical PNG chunk.")
        if saw_data and kind != b"IDAT":
            data_ended = True
        offset = end
    require(header is not None and saw_end, "PNG is incomplete; IHDR/IDAT/IEND are required.")
    width, height, depth, color, _, _, interlace = header
    require(color != 3 or palette_entries is not None and palette_entries <= 2 ** depth,
            "Indexed PNG has no valid palette.")
    bits_per_pixel = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color] * depth
    passes = ((0, 0, 1, 1),) if interlace == 0 else (
        (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
        (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2),
    )
    rows = []
    for x, y, dx, dy in passes:
        pass_width = max(0, (width - x + dx - 1) // dx)
        pass_height = max(0, (height - y + dy - 1) // dy)
        if pass_width and pass_height:
            rows.append((pass_height, (pass_width * bits_per_pixel + 7) // 8 + 1))
    expected_bytes = sum(count * length for count, length in rows)
    require(expected_bytes <= 256 * 1024 * 1024, "Screenshot PNG exceeds the bounded decoded-size budget.")
    decoder = zlib.decompressobj()
    try:
        decoded = decoder.decompress(compressed, expected_bytes + 1)
    except zlib.error as error:
        raise CheckFailure("PNG IDAT data is not a valid zlib stream.") from error
    require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
            and len(decoded) == expected_bytes, "PNG scanline data is truncated, oversized, or has trailing compressed data.")
    offset = 0
    for count, length in rows:
        for _ in range(count):
            require(decoded[offset] <= 4, "PNG scanline has an invalid filter type.")
            offset += length
    return {"width": width, "height": height}


class GodotSessionSmoke(ui.AndroidSmoke):
    def __init__(self, serial, output, variant="debug", font_scale="1.0"):
        super().__init__(serial, output, variant)
        self.font_scale = font_scale
        self.checks = {}
        self.captures = []
        self.identity = {}
        self.shell_identity = None
        self.shell_task = None
        self.native_pids = []
        self.last_xml_bytes = None
        self.last_xml_time = None
        self.intentional_signals = []
        self.home_component = None
        self.logcat_started = False
        self.process_table_sequence = 0
        for directory in ("captures", "identity", "logs"):
            (output / directory).mkdir()

    def write_json(self, name, value):
        self.write_text(name, json.dumps(value, indent=2, sort_keys=True) + "\n")

    def command(self, *arguments, timeout=20, binary=False):
        return subprocess.run(["adb", "-s", self.serial, *arguments], capture_output=True,
                              text=not binary, timeout=timeout, check=False)

    @contextmanager
    def check(self, name):
        self.stage = name
        entry = {"status": "running", "started_utc": utc_now()}
        self.checks[name] = entry
        self.record(f"Checking {name}")
        try:
            yield entry
        except UnsupportedCheck as error:
            entry.update(status="unsupported", reason=ui.redacted(str(error)))
            self.record(f"Unsupported {name}: {error}")
        except Exception as error:
            entry.update(status="failed", error=ui.redacted(str(error)))
            raise
        else:
            entry.setdefault("scope", "UI/lifecycle observation only")
            if entry["status"] == "running":
                entry["status"] = "passed"
        finally:
            entry["ended_utc"] = utc_now()

    def dump_ui(self, deadline=None):
        deadline = deadline or time.monotonic() + 30
        self.last_xml_bytes = None
        self.last_xml_time = None

        def timeout():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("UI dump deadline expired.")
            return min(20, remaining)

        remote = "/sdcard/partydeck-ci-godot-session-ui.xml"
        self.adb("shell", "rm", "-f", remote, timeout=timeout())
        output = self.adb("shell", "uiautomator", "dump", remote, timeout=timeout())
        self.write_text("last-ui-dump.log", output)
        raw = self.adb("exec-out", "cat", remote, timeout=timeout(), binary=True)
        if b"partydeck:v1:" in raw or ui.QR_DESCRIPTION.encode() in raw:
            self.sensitive_surface = True
            raise CheckFailure("Unexpected live invitation surface; original UI/screenshot capture refused.")
        root = ET.fromstring(raw)
        if any("partydeck:v1:" in value or value == ui.QR_DESCRIPTION
               for node in root.iter() for value in node.attrib.values()):
            self.sensitive_surface = True
            raise CheckFailure("Unexpected live invitation surface; original UI/screenshot capture refused.")
        self.bind_ui(root)
        self.last_xml_bytes, self.last_xml_time = raw, utc_now()
        (self.output / "last-ui.xml").write_bytes(raw)
        return root

    def pids(self, name):
        result = self.command("shell", "pidof", name)
        return parse_pidof(result.returncode, result.stdout, result.stderr)

    def read_process_table(self):
        self.process_table_sequence += 1
        prefix = f"logs/process-table-{self.process_table_sequence:04d}"
        # UID is numeric in Toybox; -n makes that intent explicit and -w avoids
        # truncation. Keep the verified PID/UID/NAME schema, without USER aliases.
        arguments = ("shell", "ps", "-A", "-n", "-w", "-o", "PID,UID,NAME")
        receipt = {"argv": ["adb", "-s", self.serial, *arguments],
                   "started_utc": utc_now(), "returncode": None}
        stdout = stderr = None
        try:
            result = self.command(*arguments, binary=True)
            stdout, stderr = result.stdout, result.stderr
            receipt["returncode"] = result.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.stdout, error.stderr
            receipt.update(error="timeout", timeout_seconds=error.timeout)
            raise
        except OSError as error:
            receipt.update(error=type(error).__name__, message=ui.redacted(str(error)))
            raise
        finally:
            # Preserve every sample before decoding, parsing or consistency checks.
            # A timeout has no observed exit code; missing streams stay unavailable.
            receipt["ended_utc"] = utc_now()
            for stream, raw in (("stdout", stdout), ("stderr", stderr)):
                entry = {"available": raw is not None}
                if raw is not None:
                    name = f"{prefix}.{stream}.log"
                    (self.output / name).write_bytes(raw)
                    entry.update(file=name, bytes=len(raw), sha256=sha256_file(self.output / name))
                receipt[stream] = entry
            self.write_json(f"{prefix}.json", receipt)
        require(result.returncode == 0 and not result.stderr.strip(),
                f"Android ps failed (exit {result.returncode}); inspect {prefix}.json.")
        return result.stdout.decode("utf-8", errors="strict")

    def state(self):
        started = utc_now()
        # Process creation/exit can happen between these read-only commands.
        # Retry an inconsistent sample; never treat it as proof of identity.
        for attempt in range(3):
            activity = self.adb("shell", "dumpsys", "activity", "activities")
            shell_pids, child_pids = self.pids(PACKAGE), self.pids(RENDERER_PROCESS)
            processes = self.read_process_table()
            rows = parse_process_table(processes)
            relevant = []
            consistent = True
            for name, pids in ((PACKAGE, shell_pids), (RENDERER_PROCESS, child_pids)):
                require(len(pids) <= 1, f"Multiple exact {name} processes; attribution is ambiguous.")
                actual = sorted(pid for pid, row in rows.items() if row["name"] == name)
                consistent &= actual == pids
                relevant.extend(rows[pid] for pid in actual)
            if consistent:
                break
            time.sleep(0.05)
        require(consistent, "pidof and ps process identities repeatedly disagree.")
        self.write_text("logs/last-activity.log", activity)
        self.write_text("logs/last-processes.log", processes)
        return {"started_utc": started, "ended_utc": utc_now(), "foreground": parse_focused_activity(activity),
                "processes": relevant, "shell_pids": shell_pids, "renderer_pids": child_pids}

    def require_shell(self, state):
        require(self.shell_identity is not None and state["shell_pids"] == [self.shell_identity["pid"]],
                "The original Compose shell process did not survive.")
        require(self.shell_identity in state["processes"], "The Compose shell process identity changed.")

    def matches_activity(self, state, component):
        return state["foreground"] is not None and state["foreground"]["component"] == component

    def wait_activity(self, component, renderer_pid=None, child_absent=False, seconds=45):
        deadline = time.monotonic() + seconds
        last = None
        while time.monotonic() < deadline:
            last = self.state()
            self.require_shell(last)
            if (self.matches_activity(last, component)
                    and (component != NATIVE_COMPONENT or len(last["renderer_pids"]) == 1)
                    and (renderer_pid is None or last["renderer_pids"] == [renderer_pid])
                    and (not child_absent or not last["renderer_pids"])):
                if component == MAIN_COMPONENT:
                    require(last["foreground"]["task_id"] == self.shell_task, "Compose returned in a different task.")
                return last
            time.sleep(0.3)
        raise CheckFailure(f"Expected foreground {component} and requested process lifetime within {seconds}s; last state: {last}")

    def text_node(self, root, text):
        self.bind_ui(root)
        return next((node for node in root.iter("node") if node.get("package") == PACKAGE
                     and text in (node.get("text"), node.get("content-desc")) and self.visible(node)), None)

    def native_controls(self, root, ready=True):
        status = self.text_node(root, READY)
        if status is None and not ready:
            status = self.text_node(root, OPENING)
        standard = self.find_action(root, "native-standard-table", "Standard table")
        leave = self.find_action(root, "native-leave-table", "Leave table")
        if status is None or standard is None or leave is None:
            return None
        require(standard.get("class") == "android.widget.Button" and leave.get("class") == "android.widget.Button",
                "Native return controls are not Android Buttons.")
        self.assert_no_private_semantics(root)
        if status.get("text") == READY:
            require(self.text_node(root, "Your cards stay private") is None,
                    "Native Ready and the privacy cover are both visible.")
        return {"status": status.get("text") or status.get("content-desc"), "leave": leave}

    def capture_evidence(self, name, component=None, renderer_pid=None, diagnostic=False, ui_assertion=None):
        require(re.fullmatch(r"[a-z0-9][a-z0-9-]*", name), "Unsafe capture name.")
        prefix = f"captures/{name}"
        require(not (self.output / f"{prefix}.json").exists(), "Capture names must not overwrite prior evidence.")
        entry = {"name": name, "stage": self.stage, "started_utc": utc_now(), "status": "capturing",
                 "provenance": "Original adb exec-out screencap PNG and fresh uiautomator XML; acquired sequentially, not atomically.",
                 "pixel_privacy": "Requires visual review; native chrome and absent semantics do not verify engine pixels."}
        self.captures.append(entry)
        errors = []

        def failed(part, error):
            message = ui.redacted(str(error))
            entry[f"{part}_error"] = message
            errors.append(f"{part}: {message}")

        def capture_state(phase):
            try:
                state = self.state()
                entry[phase] = state
                for kind in ("activity", "processes"):
                    source = self.output / f"logs/last-{kind}.log"
                    (self.output / f"{prefix}-{phase}-{kind}.log").write_bytes(source.read_bytes())
                if not diagnostic and component is not None:
                    self.require_shell(state)
                    require(self.matches_activity(state, component), "Foreground Activity changed during capture.")
                    if renderer_pid is not None:
                        require(state["renderer_pids"] == [renderer_pid], "Renderer PID changed during capture.")
            except Exception as error:
                failed(f"{phase}_state", error)

        try:
            capture_state("before")
            try:
                root = self.dump_ui()
                require(self.last_xml_bytes is not None, "Fresh UI bytes are missing.")
                path = self.output / f"{prefix}.xml"
                path.write_bytes(self.last_xml_bytes)
                entry["ui"] = {"file": f"{prefix}.xml", "sha256": sha256_file(path),
                               "received_utc": self.last_xml_time, "sequence": self.ui_sequence}
                if not diagnostic:
                    self.reject_crash_dialog(root)
                if ui_assertion is not None:
                    ui_assertion(root)
            except Exception as error:
                failed("ui", error)
            # A failed UI/state assertion must retain its original failure pixels.
            # An invitation is the exception: neither pixels nor bearer XML are saved.
            require(not self.sensitive_surface, "A sensitive invitation surface prevents screenshot capture.")
            try:
                entry["screenshot_started_utc"] = utc_now()
                raw = self.adb("exec-out", "screencap", "-p", binary=True)
                entry["screenshot_received_utc"] = utc_now()
                try:
                    dimensions = png_dimensions(raw)
                except CheckFailure:
                    (self.output / f"{prefix}-invalid-screencap.bin").write_bytes(raw)
                    raise
                path = self.output / f"{prefix}.png"
                path.write_bytes(raw)
                entry["screenshot"] = {"file": f"{prefix}.png", "sha256": sha256_file(path), **dimensions}
            except Exception as error:
                failed("screenshot", error)
            capture_state("after")
            if errors and not diagnostic:
                raise CheckFailure("; ".join(errors))
            entry["status"] = "partial" if errors else "captured"
        except Exception as error:
            entry.update(status="failed", error=ui.redacted(str(error)))
            raise
        finally:
            entry["ended_utc"] = utc_now()
            self.write_json(f"{prefix}.json", entry)
        return entry

    def tap_action(self, tag, text=None, scroll="down"):
        self.tap_node(self.wait_for_action(tag, text, scroll=scroll), tag)

    def setup_session(self, apk):
        with self.check("installation") as entry:
            self.prepare_device()
            self.save_setting("system", "font_scale", self.font_scale)
            require(self.adb("shell", "settings", "get", "system", "font_scale").strip() == self.font_scale,
                    "Requested font scale was not applied.")
            homes = re.findall(r"^([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)$", (self.output / "home-activity.log").read_text(), re.MULTILINE)
            require(homes, "No resolved launcher component was retained.")
            self.home_component = canonical_component(homes[-1])
            self.write_text("logs/install.log", self.adb("install", "-r", str(apk), timeout=180))
            paths_output = self.adb("shell", "pm", "path", PACKAGE)
            self.write_text("identity/installed-paths.log", paths_output)
            paths = re.findall(r"^package:(/[^\r\n]+)$", paths_output, re.MULTILINE)
            require(len(paths) == 1 and paths[0].endswith("/base.apk"),
                    "Expected one installed base.apk; split/unrecognized packages cannot qualify this input APK.")
            installed = self.output / "identity/installed-base.apk"
            self.write_text("identity/pull.log", self.adb("pull", paths[0], str(installed), timeout=180))
            installed_hash = sha256_file(installed)
            require(installed_hash == self.identity["input_apk_sha256"], "Installed base.apk does not match the supplied APK bytes.")
            self.identity.update(installed_paths=paths, installed_apk_sha256=installed_hash,
                                 installed_apk_bytes=installed.stat().st_size,
                                 installed_copy="identity/installed-base.apk")
            self.write_text("identity/package.log", self.adb("shell", "dumpsys", "package", PACKAGE))
            self.write_text("identity/device.log", self.adb("shell", "getprop"))
            require(self.adb("shell", "pm", "clear", PACKAGE, timeout=30).strip() == "Success", "Could not clear the test package.")
            self.adb("logcat", "-b", "main", "-b", "system", "-b", "crash", "-b", "events", "-c")
            self.logcat_started = True
            self.identity["logcat_cleared_utc"] = utc_now()
            self.launch("godot-session-cold")
            self.wait_for_action("home-practice", scroll="down")
            state = self.state()
            require(self.matches_activity(state, MAIN_COMPONENT) and len(state["shell_pids"]) == 1
                    and not state["renderer_pids"], "Cold Home did not start in the sole Compose shell process.")
            self.shell_identity = next(item for item in state["processes"] if item["name"] == PACKAGE)
            self.shell_task = state["foreground"]["task_id"]
            self.identity.update(shell=self.shell_identity, shell_task_id=self.shell_task,
                                 launcher_component=self.home_component, actual_font_scale=self.font_scale)
            entry["installed_apk_sha256"] = installed_hash
            self.capture_evidence("home-cold", MAIN_COMPONENT)

    def observe_match(self, prefix):
        anchor = self.wait_until("Expected a visible stable human-turn round/rank", lambda root: public_anchor(root, self.visible), scroll="up")
        self.capture_evidence(f"{prefix}-public", MAIN_COMPONENT, ui_assertion=lambda root: require(
            public_anchor(root, self.visible) == anchor, "Public anchor changed before its original capture."))
        self.tap_action("game-reveal-hand", scroll="down")
        node = self.wait_for_tag("game-card-0", scroll="down")
        sample = first_card_sample(node)
        require(not ui.selected(node), "Card selection survived concealment/presentation return.")
        self.capture_evidence(f"{prefix}-first-card", MAIN_COMPONENT, ui_assertion=lambda root: require(
            first_card_sample(self.find(root, "game-card-0")) == sample
            and not ui.selected(self.find(root, "game-card-0")), "Private sample changed before its original capture."))
        return {"public": anchor, "first_card": sample}

    def select_first_card(self, prefix):
        self.tap_action("game-card-0", scroll="up")
        self.wait_until("Expected first card selection before switching", lambda root: ui.selected(self.find(root, "game-card-0")), scroll="up")
        self.wait_for_action("game-play", scroll="down")
        self.capture_evidence(f"{prefix}-selected", MAIN_COMPONENT, ui_assertion=lambda root: require(
            self.find_action(root, "game-play") is not None, "Selected-card play action is no longer enabled."))

    def require_concealed_return(self, baseline, prefix):
        self.wait_activity(MAIN_COMPONENT, child_absent=True)
        self.assert_concealed()
        def concealed(root):
            self.assert_no_private_semantics(root)
            require(self.find(root, "game-reveal-hand") is not None, "Concealed hand reveal action is missing.")

        self.capture_evidence(f"{prefix}-concealed", MAIN_COMPONENT, ui_assertion=concealed)
        self.wait_for_tag("game-play", enabled=False, scroll="down")
        self.capture_evidence(f"{prefix}-selection-cleared", MAIN_COMPONENT, ui_assertion=lambda root: require(
            self.find(root, "game-play", enabled=False) is not None, "Play is enabled without a fresh selection."))
        after = self.observe_match(prefix)
        return compare_continuity(baseline, after)

    def presentation_picker(self, root):
        """Locate the actual modal even when its separate Compose tree omits test IDs."""
        self.bind_ui(root)
        def labels(text):
            return [node for node in root.iter("node")
                    if node.get("package") == PACKAGE and node.get("text") == text
                    and node.get("class") == "android.widget.TextView"
                    and node.get("enabled") == "true" and self.visible(node)]

        titles, done_labels = labels("Table style"), labels("Done")
        if len(titles) != 1 or len(done_labels) != 1 or titles[0].get("clickable") != "false":
            return None
        done = done_labels[0]
        while done is not None and done.get("clickable") != "true":
            done = self.ui_parents.get(done)
        if (done is None or done.get("package") != PACKAGE or done.get("enabled") != "true"
                or done.get("checkable") == "true" or not self.visible(done)):
            return None
        panel = self.ui_parents.get(titles[0])
        while panel is not None and done not in panel.iter("node"):
            panel = self.ui_parents.get(panel)
        if panel is None or panel.get("package") != PACKAGE or not self.visible(panel):
            return None
        scrolls = [node for node in panel.iter("node")
                   if node.get("package") == PACKAGE and node.get("class") == "android.widget.ScrollView"]
        if (len(scrolls) != 1 or scrolls[0].get("enabled") != "true" or not self.visible(scrolls[0])
                or titles[0] in scrolls[0].iter("node") or done in scrolls[0].iter("node")):
            return None
        return panel, scrolls[0]

    def presentation_choice(self, root, mode):
        """Return a safe text hit region inside one current, enabled radio row."""
        require(mode in ("2d", "3d"), "Unknown production presentation choice.")
        picker = self.presentation_picker(root)
        if picker is None:
            return None
        panel, scroll = picker
        text = {"2d": "2D table", "3d": "3D table"}[mode]
        labels = [node for node in scroll.iter("node") if node.get("text") == text]
        if len(labels) != 1:
            return None
        label = labels[0]
        row = self.ui_parents.get(label)
        while row is not None and row is not scroll and row.get("checkable") != "true":
            row = self.ui_parents.get(row)
        if (row is None or row is scroll or row.get("package") != PACKAGE
                or row.get("enabled") != "true" or row.get("clickable") != "true"
                or row.get("checked") != "false" or label.get("package") != PACKAGE
                or label.get("class") != "android.widget.TextView" or label.get("enabled") != "true"
                or not self.visible(row) or not self.visible(label)):
            return None
        descendant = label
        while descendant is not row:
            if (descendant is None or descendant.get("package") != PACKAGE
                    or descendant.get("enabled") != "true" or descendant.get("clickable") != "false"):
                return None
            descendant = self.ui_parents.get(descendant)
        tag = f"presentation-choice-godot_{mode}"
        resource_id = row.get("resource-id", "")
        if resource_id and resource_id != tag and not resource_id.endswith("/" + tag):
            return None
        radios = [node for node in row.iter("node") if node.get("class") == "android.widget.RadioButton"]
        if (len(radios) != 1 or radios[0].get("package") != PACKAGE
                or radios[0].get("enabled") != "true" or not self.visible(radios[0])
                or (radios[0] is not row and radios[0].get("clickable") != "false")):
            return None
        bounds, target = ui.node_bounds(row), ui.node_bounds(label)
        if (ui.intersect_bounds(bounds, ui.node_bounds(panel)) != bounds
                or ui.intersect_bounds(target, bounds) != target):
            return None
        # Selectable rows intentionally meet the ScrollView's horizontal edges.
        # Keep the existing clearance at the actual text hit region inside the
        # fully visible row; do not weaken the generic button/action helper.
        viewport = ui.intersect_bounds(bounds, self.viewport(row))
        if min(target[0] - viewport[0], target[1] - viewport[1],
               viewport[2] - target[2], viewport[3] - target[3]) < ui.ACTION_VIEWPORT_CLEARANCE_PX:
            return None
        return label

    def wait_for_presentation_choice(self, mode):
        return self.wait_until(
            f"Expected one current enabled {mode} radio row in the production Table style dialog",
            lambda root: self.presentation_choice(root, mode), scroll="down",
        )

    def enter_native(self, mode, prefix, ready=True):
        self.wait_activity(MAIN_COMPONENT, child_absent=True)
        self.tap_action("presentation-picker", "Table style", scroll="up")
        self.wait_until("Expected the production Table style dialog", self.presentation_picker)
        self.wait_for_presentation_choice(mode)
        self.capture_evidence(f"{prefix}-selector", MAIN_COMPONENT, ui_assertion=lambda root: require(
            self.presentation_choice(root, mode) is not None, "The requested picker row changed before capture."))
        self.tap_node(self.wait_for_presentation_choice(mode), f"presentation-choice-godot_{mode}")
        state = self.wait_activity(NATIVE_COMPONENT)
        require(len(state["renderer_pids"]) == 1, "Native Activity has no sole renderer process.")
        pid = state["renderer_pids"][0]
        renderer = next(item for item in state["processes"] if item["name"] == RENDERER_PROCESS)
        require(pid != self.shell_identity["pid"] and renderer["uid"] == self.shell_identity["uid"],
                "Renderer is not a distinct app-owned process.")
        require(pid not in self.native_pids, "Renderer re-entry reused a previously observed PID; fresh lifetime is not established.")
        self.native_pids.append(pid)
        controls = self.wait_until("Expected native Ready/chrome" if ready else "Expected native Opening or Ready/chrome",
                                   lambda root: self.native_controls(root, ready), seconds=60)
        verified = self.state()
        self.require_shell(verified)
        require(verified["renderer_pids"] == [pid] and self.matches_activity(verified, NATIVE_COMPONENT),
                "Renderer process/Activity changed while waiting for its controls.")
        if ready:
            self.capture_evidence(f"{prefix}-native-ready", NATIVE_COMPONENT, pid, ui_assertion=lambda root: require(
                self.native_controls(root) is not None, "Native Ready/chrome is missing in its original capture."))
        return pid, state["foreground"]["task_id"], controls

    def resume_task(self, task, pid, prefix):
        require(type(task) is int and task > 0, "Invalid existing task ID.")
        result = self.adb("shell", "am", "task", "focus", str(task))
        self.write_text(f"logs/{prefix}-task-focus.log", result)
        require(re.search(rf"^Setting focus to task {task}\s*$", result, re.MULTILINE), "Android did not acknowledge existing-task focus.")
        state = self.wait_activity(NATIVE_COMPONENT, renderer_pid=pid)
        require(state["foreground"]["task_id"] == task, "Task focus resumed a different native task.")
        self.wait_until("Expected Ready after existing-task resume", lambda root: self.native_controls(root))
        self.capture_evidence(f"{prefix}-resumed", NATIVE_COMPONENT, pid, ui_assertion=lambda root: require(
            self.native_controls(root) is not None, "Native Ready/chrome is missing after resume."))

    def interrupt_native(self, mode, pid, task, recents=False):
        kind = "recents" if recents else "home"
        with self.check(f"{mode}.{kind}-interruption") as entry:
            self.adb("shell", "input", "keyevent", "KEYCODE_APP_SWITCH" if recents else "KEYCODE_HOME")
            launcher_package = self.home_component.split("/", 1)[0]

            def system_surface(root):
                self.assert_no_private_semantics(root)
                app_nodes = [node for node in root.iter("node") if node.get("package") == launcher_package]
                if not app_nodes:
                    return None
                if recents and not any(node.get("resource-id", "").rsplit("/", 1)[-1] in RECENTS_IDS
                                       and self.visible(node) for node in app_nodes):
                    return None
                return True

            self.wait_until(f"Expected resolved launcher {'Recents' if recents else 'Home'} UI", system_surface, seconds=30)
            state = self.state()
            self.require_shell(state)
            require(state["renderer_pids"] == [pid] and state["foreground"] is not None
                    and state["foreground"]["component"].split("/", 1)[0] == launcher_package,
                    "Interruption did not retain the child behind the actual launcher.")
            self.capture_evidence(f"{mode}-{kind}-system-ui", state["foreground"]["component"], pid,
                                  ui_assertion=lambda root: require(system_surface(root) is True,
                                                                    "System UI changed before its original capture."))
            entry["privacy"] = "No private Compose semantics in the system tree; original system pixels retained for visual review."
            self.resume_task(task, pid, f"{mode}-{kind}")

    @staticmethod
    def assert_no_private_semantics(root):
        for node in root.iter("node"):
            tag = node.get("resource-id", "").rsplit("/", 1)[-1]
            require(not tag.startswith("game-card-")
                    and re.search(r"\b(?:Crown|Moon|Star|Wild)\. Card \d+ of \d+\.", node.get("content-desc", "")) is None,
                    "Private hand semantics appeared on a concealed/system surface.")

    def signal_renderer(self, pid):
        result = self.command("shell", "run-as", PACKAGE, "id", "-u")
        self.write_text(f"logs/renderer-{pid}-run-as-capability.log", f"exit={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        if result.returncode != 0:
            raise UnsupportedCheck("run-as app identity is unavailable; exact child-process death was not exercised. "
                                   "No root or whole-package force-stop fallback is used.")
        require(re.fullmatch(r"\d+\s*", result.stdout) and not result.stderr.strip()
                and int(result.stdout) == self.shell_identity["uid"], "run-as returned a different app UID.")
        state = self.state()
        self.require_shell(state)
        require(state["renderer_pids"] == [pid] and self.matches_activity(state, NATIVE_COMPONENT),
                "Renderer identity/foreground changed before the requested signal.")
        identities = []
        for name, target in ((PACKAGE, self.shell_identity["pid"]), (RENDERER_PROCESS, pid)):
            values = {}
            for field in ("cmdline", "status", "stat"):
                response = self.command("shell", "run-as", PACKAGE, "cat", f"/proc/{target}/{field}", binary=field == "cmdline")
                if response.returncode != 0:
                    raise UnsupportedCheck("run-as cannot read exact process identity; renderer death was not exercised.")
                values[field] = response.stdout
            identities.append(parse_proc_identity(target, name, self.shell_identity["uid"], **values))
        script = renderer_kill_script(*identities)
        self.write_text(f"logs/renderer-{pid}-guarded-kill.log", script + "\n")
        signal = {"requested_utc": utc_now(), "shell": identities[0], "renderer": identities[1],
                  "signal": "SIGKILL", "scope": "Exact child PID guarded by app UID, cmdline, and process start time immediately before signal."}
        self.intentional_signals.append(signal)
        result = self.command("shell", "run-as", PACKAGE, "sh", "-c", shlex.quote(script))
        signal.update(returncode=result.returncode, stdout=ui.redacted(result.stdout), stderr=ui.redacted(result.stderr))
        require(result.returncode == 0 and result.stdout.strip() == "PARTYDECK_RENDERER_SIGNALLED" and not result.stderr.strip(),
                "Guarded child signal was not acknowledged; no process-death pass is permitted.")
        return signal

    def leave_dialog(self, prefix):
        self.wait_activity(MAIN_COMPONENT, child_absent=True)
        self.wait_for_action("leave-confirm", "Leave table")
        root = self.dump_ui()
        require(self.text_node(root, "Leave the table?") is not None
                and self.text_node(root, "This practice match will end. You can start a fresh one anytime.") is not None,
                "Native Leave did not reach the real practice session-end confirmation.")
        self.assert_no_private_semantics(root)
        self.capture_evidence(f"{prefix}-confirmation", MAIN_COMPONENT)

    def run_mode(self, mode, skip_renderer_death):
        with self.check(f"{mode}.practice-baseline") as entry:
            self.tap_action("home-practice")
            self.wait_for_human_turn()
            self.assert_concealed()
            baseline = self.observe_match(f"{mode}-baseline")
            entry["baseline"] = baseline
            self.select_first_card(f"{mode}-baseline")
        with self.check(f"{mode}.native-entry") as entry:
            pid, task, _ = self.enter_native(mode, f"{mode}-entry")
            entry.update(renderer_pid=pid, task_id=task, native_ready_observed=True,
                         engine_gameplay="Not exercised by native chrome checks.")
        self.interrupt_native(mode, pid, task)
        self.interrupt_native(mode, pid, task, recents=True)
        with self.check(f"{mode}.standard-return") as entry:
            self.tap_action("native-standard-table", "Standard table", scroll=None)
            entry["observable_continuity"] = self.require_concealed_return(baseline, f"{mode}-standard")
        with self.check(f"{mode}.renderer-death") as entry:
            if skip_renderer_death:
                entry.update(status="skipped", reason="Explicit --skip-renderer-death scope; process death is not qualified.")
            else:
                self.select_first_card(f"{mode}-death")
                pid, _, _ = self.enter_native(mode, f"{mode}-death")
                try:
                    entry["signal"] = self.signal_renderer(pid)
                except UnsupportedCheck:
                    # Complete the other authorized UI checks after recording this as
                    # unsupported. Standard is a real native return, not a kill substitute.
                    self.tap_action("native-standard-table", "Standard table", scroll=None)
                    self.require_concealed_return(baseline, f"{mode}-death-unsupported-return")
                    raise
                entry["observable_continuity"] = self.require_concealed_return(baseline, f"{mode}-death-return")
        with self.check(f"{mode}.leave-cancel") as entry:
            self.select_first_card(f"{mode}-leave-cancel")
            self.enter_native(mode, f"{mode}-leave-cancel")
            self.tap_action("native-leave-table", "Leave table", scroll=None)
            self.leave_dialog(f"{mode}-leave-cancel")
            self.tap_action("leave-cancel", "Stay at the table")
            entry["observable_continuity"] = self.require_concealed_return(baseline, f"{mode}-leave-cancel-return")
        with self.check(f"{mode}.leave-end") as entry:
            self.select_first_card(f"{mode}-leave-end")
            pid, _, controls = self.enter_native(mode, f"{mode}-leave-end", ready=False)
            entry["status_when_leave_became_accessible"] = controls["status"]
            entry["opening_cancellation"] = ("Opening label observed before Leave input; binding timing is not observable."
                                             if controls["status"] == OPENING else
                                             "Not observed: native Ready was already visible. Pre-binding cancellation is not qualified.")
            # Preserve the original observation before using its current button geometry.
            raw = self.last_xml_bytes
            path = self.output / f"captures/{mode}-leave-end-control-observation.xml"
            path.write_bytes(raw)
            entry["leave_control_ui"] = {"file": str(path.relative_to(self.output)), "sha256": sha256_file(path),
                                         "received_utc": self.last_xml_time, "renderer_pid": pid}
            entry["leave_input_started_utc"] = utc_now()
            self.tap_node(controls["leave"], "native-leave-table")
            self.leave_dialog(f"{mode}-leave-end")
            self.tap_action("leave-confirm", "Leave table")
            self.wait_for_action("home-practice", scroll="down")
            self.wait_activity(MAIN_COMPONENT, child_absent=True)
            root = self.dump_ui()
            require(not any(node.get("resource-id", "").rsplit("/", 1)[-1] in ("game-table", "game-hand", "leave-confirm")
                            for node in root.iter("node")), "Game/confirmation remains after the requested session end.")
            self.capture_evidence(f"{mode}-home-after-session-end", MAIN_COMPONENT)
            entry["session_end_observation"] = "Practice confirmation accepted; Home visible with the same shell and no renderer process."

    def diagnostics(self):
        errors = []
        for name, arguments in (
            ("logcat.log", ("logcat", "-d", "-b", "main", "-b", "system", "-b", "crash", "-v", "threadtime")),
            ("crash.log", ("logcat", "-d", "-b", "crash", "-v", "threadtime")),
            ("events.log", ("logcat", "-d", "-b", "events", "-v", "threadtime")),
            ("last-anr.log", ("shell", "dumpsys", "activity", "lastanr")),
        ):
            try:
                self.write_text(f"logs/{name}", self.adb(*arguments, timeout=20))
            except Exception as error:
                errors.append(f"{name}: {ui.redacted(str(error))}")
        try:
            capture = self.capture_evidence("final-diagnostic", diagnostic=True)
            if capture["status"] != "captured":
                errors.append("Final diagnostic capture is incomplete; see its per-part error fields.")
        except Exception as error:
            errors.append(f"final capture: {ui.redacted(str(error))}")
        crash = self.output / "logs/crash.log"
        if self.logcat_started and crash.exists():
            exact_app = re.escape(PACKAGE) + r"(?::godot)?"
            unexpected = [line for line in crash.read_text().splitlines()
                          if re.search(rf">>> {exact_app} <<<|Process: {exact_app}, PID: \d+", line)]
            if unexpected:
                self.observations["unexpected_app_crashes"] = unexpected
                errors.append("The run's cleared crash buffer contains an exact app-process Java/native crash.")
        return errors


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--serial", required=True, help="Dedicated adb test device; the app is installed and its data cleared.")
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Fresh directory that must not already exist.")
    parser.add_argument("--source-revision", required=True, help="Caller-attributed 40/64-digit source revision; not embedded APK proof.")
    parser.add_argument("--variant", choices=("debug", "optimized-test-signed"), default="debug")
    parser.add_argument("--modes", choices=("2d", "3d"), nargs="+", default=["2d", "3d"])
    parser.add_argument("--font-scale", choices=("1.0", "2.0"), default="1.0")
    parser.add_argument("--skip-renderer-death", action="store_true",
                        help="Explicitly omit the guarded run-as child kill (for scoped non-debuggable runs).")
    return parser


def main(argv=None):
    parser = argument_parser()
    arguments = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", arguments.source_revision):
        parser.error("--source-revision must be 40 or 64 hexadecimal digits")
    if not arguments.apk.is_file():
        parser.error(f"APK does not exist: {arguments.apk}")
    if len(arguments.modes) != len(set(arguments.modes)):
        parser.error("--modes must not contain duplicates")
    try:
        fresh_output(arguments.output)
    except FileExistsError:
        parser.error("--output already exists; choose a fresh directory to preserve prior evidence")
    smoke = GodotSessionSmoke(arguments.serial, arguments.output, arguments.variant, arguments.font_scale)
    smoke.identity.update(input_apk=str(arguments.apk.resolve()), input_apk_sha256=sha256_file(arguments.apk),
                          input_apk_bytes=arguments.apk.stat().st_size,
                          checker_sha256=sha256_file(Path(__file__)), helper_sha256=sha256_file(HELPER_PATH))
    result = {"schema_version": 1, "started_utc": utc_now(), "serial": arguments.serial,
              "variant_label": arguments.variant, "requested_modes": arguments.modes,
              "source_revision": {"value": arguments.source_revision.lower(), "attribution": "Caller-supplied; not embedded APK or checkout proof."},
              "identity": smoke.identity, "checks": smoke.checks, "captures": smoke.captures,
              "intentional_signals": smoke.intentional_signals, "steps": smoke.steps, "observations": smoke.observations,
              "limits": ["Native Ready/chrome is host bootstrap/lifecycle evidence, not engine gameplay.",
                         "Native and Recents pixel privacy requires review of the original captures.",
                         "Match continuity uses a surviving shell/task, public anchors and one indexed card/count; no internal session ID is exposed.",
                         "Pre-binding cancellation is not deterministically observable through production UI.",
                         "Single-device practice only; physical LAN, real-device/store signing and iOS are outside this check."]}
    failed = False
    try:
        smoke.setup_session(arguments.apk)
        for mode in arguments.modes:
            smoke.run_mode(mode, arguments.skip_renderer_death)
    except Exception as error:
        failed = True
        result.update(error=ui.redacted(str(error)), failed_stage=smoke.stage)
        print(f"FAILED {smoke.stage}: {ui.redacted(str(error))}", file=sys.stderr, flush=True)
    finally:
        try:
            errors = smoke.diagnostics()
        except Exception as error:
            errors = [ui.redacted(str(error))]
        try:
            errors.extend(smoke.restore_environment())
        except Exception as error:
            errors.append(f"Environment restore: {ui.redacted(str(error))}")
        if errors:
            result["diagnostic_or_restore_errors"] = errors
            failed = True
        unsupported = any(entry["status"] == "unsupported" for entry in smoke.checks.values())
        result["status"] = "failed" if failed else "unsupported" if unsupported else "passed"
        result["passed"] = result["status"] == "passed"
        result["ended_utc"] = utc_now()
        result["artifacts"] = [{"file": str(path.relative_to(arguments.output)), "bytes": path.stat().st_size,
                                "sha256": sha256_file(path)} for path in sorted(arguments.output.rglob("*")) if path.is_file()]
        smoke.write_json("godot-session-result.json", result)
    print(f"Android Godot session smoke: {result['status']}; {arguments.output / 'godot-session-result.json'}", flush=True)
    return 1 if failed else 2 if unsupported else 0


if __name__ == "__main__":
    sys.exit(main())
