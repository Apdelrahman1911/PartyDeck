#!/usr/bin/env python3
"""Exercise the installed Android UI; no app test hooks or production signing keys."""

import argparse
import hashlib
import json
import pathlib
import re
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


PACKAGE = "dev.partydeck.app"
ACTIVITY = f"{PACKAGE}/.MainActivity"
QR_DESCRIPTION = "Private table invitation QR code. Share and Copy are also available."
INVALID_INVITATION = "That invitation does not look right. Scan or paste the full invitation again."
INVITATION_HINT = "Only accept an invitation from the person hosting your table."
TRANSIENT_ERRORS = (subprocess.SubprocessError, OSError, ET.ParseError)
ACTION_VIEWPORT_CLEARANCE_PX = 8


def redacted(text):
    # System chooser/log output can contain the bearer URI. Never persist it.
    return re.sub(r"partydeck:v1:[A-Za-z0-9_-]+", "partydeck:v1:[redacted]", text)


def node_bounds(node):
    if node is None:
        return None
    match = re.fullmatch(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", node.get("bounds", ""))
    return tuple(map(int, match.groups())) if match else None


def intersect_bounds(first, second):
    if first is None or second is None:
        return None
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    return (left, top, right, bottom) if left < right and top < bottom else None


def checked(node):
    if node is not None:
        for candidate in node.iter("node"):
            if candidate.get("checkable") == "true":
                return candidate.get("checked") == "true"
    return None


def selected(node):
    return node is not None and (node.get("selected") == "true" or checked(node) is True)


class AndroidSmoke:
    def __init__(self, serial, output, variant="unspecified"):
        self.serial = serial
        self.output = output
        self.variant = variant
        self.last_error = "No UI dump yet."
        self.steps = []
        self.observations = {}
        self.stage = "initialization"
        self.display_size = (0, 0)
        self.rotation = 0
        self.saved_settings = {}
        self.sensitive_surface = False
        self.launch_count = 0
        self.ui_root = None
        self.ui_parents = {}
        self.ui_sequence = 0

    def adb(self, *arguments, timeout=20, binary=False):
        result = subprocess.run(
            ["adb", "-s", self.serial, *arguments], capture_output=True,
            text=not binary, timeout=timeout, check=True,
        )
        return result.stdout

    def record(self, message):
        self.steps.append(message)
        print(f"[{self.variant}] {message}", flush=True)

    def write_text(self, name, value):
        (self.output / name).write_text(redacted(value))

    def save_setting(self, namespace, name, value):
        key = (namespace, name)
        if key not in self.saved_settings:
            self.saved_settings[key] = self.adb("shell", "settings", "get", namespace, name).strip()
        self.adb("shell", "settings", "put", namespace, name, value)

    def restore_environment(self):
        errors = []
        for (namespace, name), value in self.saved_settings.items():
            try:
                command = ("delete", namespace, name) if value in ("", "null") else ("put", namespace, name, value)
                self.adb("shell", "settings", *command, timeout=10)
            except TRANSIENT_ERRORS as error:
                errors.append(f"{namespace}/{name}: {error}")
        if errors:
            self.write_text("restore-errors.log", "\n".join(errors))
        return errors

    def wait_for_boot(self):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                timeout = min(10, max(0.1, deadline - time.monotonic()))
                if self.adb("shell", "getprop", "sys.boot_completed", timeout=timeout).strip() == "1":
                    return
            except TRANSIENT_ERRORS as error:
                self.last_error = str(error)
            time.sleep(min(1, max(0, deadline - time.monotonic())))
        raise RuntimeError(f"Android did not boot within 180 seconds: {self.last_error}")

    def dump_ui(self, deadline=None):
        deadline = deadline or time.monotonic() + 30

        def timeout():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("UI dump deadline expired.")
            return min(20, remaining)

        # uiautomator can exit zero after a failed dump and leave an old file.
        self.adb("shell", "rm", "-f", "/sdcard/partydeck-ci-ui.xml", timeout=timeout())
        output = self.adb("shell", "uiautomator", "dump", "/sdcard/partydeck-ci-ui.xml", timeout=timeout())
        self.write_text("last-ui-dump.log", output)
        xml = self.adb("shell", "cat", "/sdcard/partydeck-ci-ui.xml", timeout=timeout())
        root = ET.fromstring(xml)
        self.bind_ui(root)
        self.write_text("last-ui.xml", xml)
        return root

    def reject_crash_dialog(self, root):
        error_ids = {"android:id/aerr_close", "android:id/aerr_wait", "android:id/aerr_restart"}
        if any(node.get("resource-id") in error_ids for node in root.iter("node")):
            titles = [node.get("text", "") for node in root.iter("node")
                      if node.get("resource-id") == "android:id/alertTitle"]
            title = "; ".join(titles) or "Android crash/ANR dialog"
            raise RuntimeError(f"{self.stage}: {title}. Runtime checks cannot continue through a crash/ANR dialog.")

    def bind_ui(self, root):
        if root is not self.ui_root:
            self.ui_root = root
            self.ui_parents = {child: parent for parent in root.iter() for child in parent}
            self.ui_sequence += 1
            self.rotation = int(root.get("rotation", "0"))

    def viewport(self, node, include_self=False):
        # Nodes from an older dump have no current geometry. Compose can report
        # bounds beyond a ScrollView even when that part is under a system bar.
        if node is None or (node is not self.ui_root and node not in self.ui_parents):
            return None
        width, height = self.display_size
        if self.rotation % 2:
            width, height = height, width
        viewport = (0, 0, width, height)
        ancestor = node if include_self else self.ui_parents.get(node)
        while ancestor is not None:
            if (ancestor is node or ancestor.get("scrollable") == "true" or ancestor.get("class") in (
                    "android.widget.ScrollView", "android.widget.HorizontalScrollView",
                    "androidx.core.widget.NestedScrollView")):
                viewport = intersect_bounds(viewport, node_bounds(ancestor))
                if viewport is None:
                    return None
            ancestor = self.ui_parents.get(ancestor)
        return viewport

    def visible(self, node):
        bounds, viewport = node_bounds(node), self.viewport(node)
        return bounds is not None and viewport is not None and intersect_bounds(bounds, viewport) == bounds

    def find(self, root, tag, fallback_text=None, enabled=True):
        self.bind_ui(root)
        for node in root.iter("node"):
            resource_id = node.get("resource-id", "")
            matches_tag = resource_id == tag or resource_id.endswith("/" + tag)
            matches_text = fallback_text is not None and fallback_text in (node.get("text"), node.get("content-desc"))
            is_enabled = node.get("enabled") != "false"
            if (matches_tag or matches_text) and (enabled is None or is_enabled == enabled) and self.visible(node):
                return node
        return None

    def wait_until(self, description, predicate, seconds=45, scroll=None):
        deadline = time.monotonic() + seconds
        swipes = 0
        direction = scroll
        previous_layout = None
        stationary = 0
        reversed_direction = False
        while time.monotonic() < deadline:
            try:
                root = self.dump_ui(deadline)
                self.reject_crash_dialog(root)
                value = predicate(root)
                if value is not None and value is not False:
                    return value
                self.last_error = description
                if scroll and swipes < 16:
                    layout = ET.tostring(root)
                    stationary = stationary + 1 if layout == previous_layout else 0
                    previous_layout = layout
                    if stationary >= 2 and not reversed_direction:
                        direction = "up" if direction == "down" else "down"
                        reversed_direction = True
                    self.swipe(direction, root, timeout=min(10, max(0.1, deadline - time.monotonic())))
                    swipes += 1
            except TRANSIENT_ERRORS as error:
                self.last_error = str(error)
            time.sleep(min(0.4, max(0, deadline - time.monotonic())))
        raise RuntimeError(f"{self.stage}: {description} within {seconds} seconds: {self.last_error}")

    def wait_for_tag(self, tag, fallback_text=None, enabled=True, scroll=None, seconds=45):
        return self.wait_until(
            f"Expected visible {tag!r}",
            lambda root: self.find(root, tag, fallback_text, enabled), seconds, scroll,
        )

    def find_action(self, root, tag, fallback_text=None):
        label = self.find(root, tag, fallback_text)
        action = label
        while action is not None and action.get("clickable") != "true":
            action = self.ui_parents.get(action)
        # A text fallback can expose only the few pixels above a scroll edge.
        # Require its complete enabled button, not that clipped text rectangle.
        if (action is None or action.get("package") != PACKAGE
                or action.get("enabled") == "false" or not self.visible(action)
                or intersect_bounds(node_bounds(label), node_bounds(action)) != node_bounds(label)):
            return None
        # A clickable parent's reported bounds can themselves be clamped at the
        # scroll edge. Require a small visible gap in display pixels, rather than
        # treating edge contact as evidence that the whole button was captured.
        bounds, viewport = node_bounds(action), self.viewport(action)
        if min(bounds[0] - viewport[0], bounds[1] - viewport[1],
               viewport[2] - bounds[2], viewport[3] - bounds[3]) < ACTION_VIEWPORT_CLEARANCE_PX:
            return None
        return action

    def wait_for_action(self, tag, fallback_text=None, scroll=None, seconds=45):
        return self.wait_until(
            f"Expected a fully visible enabled action {tag!r} with {ACTION_VIEWPORT_CLEARANCE_PX}px viewport clearance",
            lambda root: self.find_action(root, tag, fallback_text), seconds, scroll,
        )

    def swipe(self, direction, root, timeout=10):
        self.bind_ui(root)
        # App scrolling must not turn a launcher/shade tree into a system gesture.
        candidates = [(node, self.viewport(node, include_self=True)) for node in root.iter("node")
                      if node.get("package") == PACKAGE and node.get("scrollable") == "true"
                      and node.get("enabled") != "false"]
        candidates = [(node, bounds) for node, bounds in candidates
                      if bounds is not None and bounds[3] - bounds[1] > 100]
        if not candidates:
            return
        node, viewport = max(candidates, key=lambda candidate: (
            (candidate[1][2] - candidate[1][0]) * (candidate[1][3] - candidate[1][1])))
        left, top, right, bottom = viewport
        x = (left + right) // 2
        upper = top + (bottom - top) // 4
        lower = top + (bottom - top) * 3 // 4
        start, end = (lower, upper) if direction == "down" else (upper, lower)
        self.record_input("swipe", direction, node, viewport,
                          {"start": [x, start], "end": [x, end], "duration_ms": 250})
        self.adb("shell", "input", "swipe", str(x), str(start), str(x), str(end), "250", timeout=timeout)

    def record_input(self, action, label, node, viewport, coordinates):
        # Allowlist geometry only: never include node text, descriptions or values.
        evidence = {
            "stage": self.stage, "action": action, "label": label,
            "ui_sequence": self.ui_sequence, "rotation": self.rotation,
            "display_size": self.display_size,
            "package": node.get("package", ""), "resource_id": node.get("resource-id", ""),
            "class": node.get("class", ""), "bounds": node_bounds(node),
            "viewport": viewport, "coordinates": coordinates,
        }
        with (self.output / "input-geometry.log").open("a") as output:
            output.write(redacted(json.dumps(evidence, sort_keys=True)) + "\n")

    def tap_node(self, node, label, height_fraction=0.5):
        if not self.visible(node):
            raise RuntimeError(f"{label!r} is not fully inside its current visible viewport.")
        if not 0 < height_fraction < 1:
            raise ValueError("Tap height fraction must be inside the target.")
        left, top, right, bottom = node_bounds(node)
        x, y = (left + right) // 2, top + int((bottom - top) * height_fraction)
        self.record_input("tap", label, node, self.viewport(node), {"x": x, "y": y})
        self.adb("shell", "input", "tap", str(x), str(y))
        self.record(f"Tapped {label}")

    def tap(self, tag, fallback_text=None, scroll=None):
        self.tap_node(self.wait_for_tag(tag, fallback_text, scroll=scroll), tag)

    def back(self):
        self.adb("shell", "input", "keyevent", "KEYCODE_BACK")

    def capture(self, name, ready_tag, fallback_text=None, scroll=None, action=False):
        if action:
            self.wait_for_action(ready_tag, fallback_text, scroll=scroll)
        else:
            self.wait_for_tag(ready_tag, fallback_text, enabled=None, scroll=scroll)
        if self.sensitive_surface:
            raise RuntimeError("Refusing to save a screenshot of a live invitation or system share preview.")
        screenshot = self.adb("exec-out", "screencap", "-p", binary=True)
        if not screenshot.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError(f"Android did not return a PNG screenshot for {name}.")
        (self.output / f"{name}.png").write_bytes(screenshot)
        (self.output / f"{name}.xml").write_text((self.output / "last-ui.xml").read_text())
        self.observations.setdefault("screenshots", {})[name] = dict(zip(("width", "height"), struct.unpack(">II", screenshot[16:24])))
        self.record(f"Verified {name}: {ready_tag}")

    def launch(self, name):
        output = self.adb("shell", "am", "start", "-W", "-n", ACTIVITY, timeout=60)
        self.launch_count += 1
        self.write_text(f"launch-{self.launch_count}-{name}.log", output)
        if not re.search(r"^\s*Status:\s*ok\s*$", output, re.MULTILINE):
            raise RuntimeError(f"Activity startup did not return Status: ok: {redacted(output)}")

    def replace_text(self, tag, value, scroll="down", ime_capture=None):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("UI smoke text fixtures must be simple shell-safe ASCII.")
        # The supporting error/hint can be tall at 200% text. Tap the editable
        # field's upper area, rather than the center of that decorated height.
        self.tap_node(self.wait_for_tag(tag, scroll=scroll), tag, height_fraction=0.25)
        # Opening the IME can shrink the viewport and move the focused field
        # off screen. Scroll it back into view before sending editing keys.
        self.wait_until(f"Expected focused editable {tag}", lambda root: self.editable_field(root, tag, focused=True), scroll=scroll)
        # A refocusing/recomposing field can miss Ctrl+A. Never assume that
        # Delete cleared it: CI observed insertion into the previous text.
        self.adb("shell", "input", "keycombination", "KEYCODE_CTRL_LEFT", "KEYCODE_A")
        self.adb("shell", "input", "keyevent", "KEYCODE_DEL")
        field = self.wait_until(f"Expected focused editable {tag} after clearing", lambda root: self.editable_field(root, tag, focused=True))
        remaining = field.get("text", "")
        if remaining:
            if len(remaining) > 128:
                raise RuntimeError(f"{tag} contains more text than the bounded CI replacement allows.")
            # Clear both sides of the cursor. Unlike End, this also handles a
            # wrapped field where an end key can mean only the current line.
            self.adb("shell", "input", "keyevent",
                     *(["KEYCODE_DEL"] * len(remaining)),
                     *(["KEYCODE_FORWARD_DEL"] * len(remaining)), timeout=30)
            self.record(f"Cleared remaining text in {tag} after Select all did not clear it")
        self.wait_until(f"Expected empty focused editable {tag}", lambda root: (
            self.editable_field(root, tag, focused=True) is not None and self.field_contains(root, tag, "")
        ))
        self.adb("shell", "input", "text", value)
        self.wait_until(f"Expected edited {tag}", lambda root: self.field_contains(root, tag, value))
        if ime_capture:
            def visible_ime(root):
                if self.editable_field(root, tag, focused=True) is None:
                    return None
                state = self.adb("shell", "dumpsys", "input_method", timeout=10)
                self.write_text(f"{ime_capture}-input-method.log", state)
                return state if all(re.search(rf"\b{name}=true\b", state) for name in (
                    "mInputShown", "mIsInputViewShown", "mDecorViewVisible", "mWindowVisible",
                )) else None

            self.wait_until(f"Expected visible soft keyboard for {tag}", visible_ime, seconds=30)
            self.capture(ime_capture, tag)
            self.observations.setdefault("soft_ime_captures", []).append(ime_capture)
        # Some AVDs expose a hardware keyboard and never show the soft IME.
        # Back in that case would leave the form instead of dismissing input.
        ime_state = self.adb("shell", "dumpsys", "input_method")
        if re.search(r"\bmInputShown=true\b", ime_state):
            self.back()

    def editable_field(self, root, tag, focused=None):
        node = self.find(root, tag, enabled=None)
        if node is not None:
            for child in node.iter("node"):
                if (child.get("class") == "android.widget.EditText" and child.get("package") == PACKAGE
                        and child.get("enabled") != "false" and self.visible(child)
                        and (focused is None or (child.get("focused") == "true") == focused)):
                    return child
        return None

    def field_contains(self, root, tag, value):
        node = self.editable_field(root, tag)
        return node is not None and node.get("text") == value

    def prepare_device(self):
        self.stage = "emulator readiness"
        self.wait_for_boot()
        self.adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
        self.adb("shell", "input", "keyevent", "KEYCODE_MENU")
        for setting in ("window_animation_scale", "transition_animation_scale", "animator_duration_scale"):
            self.save_setting("global", setting, "0")
        self.save_setting("system", "font_scale", "1.0")
        self.save_setting("secure", "show_ime_with_hard_keyboard", "1")
        if self.adb("shell", "settings", "get", "secure", "show_ime_with_hard_keyboard").strip() != "1":
            raise RuntimeError("Android did not enable the soft keyboard with its hardware keyboard attached.")
        size_output = self.adb("shell", "wm", "size")
        sizes = re.findall(r"(?:Physical|Override) size:\s*(\d+)x(\d+)", size_output)
        if not sizes:
            raise RuntimeError(f"Could not determine Android display size: {size_output}")
        self.display_size = tuple(map(int, sizes[-1]))
        self.observations["display_size"] = self.display_size
        self.write_text("display-size.log", size_output)
        self.write_text("display-density.log", self.adb("shell", "wm", "density"))
        self.write_text("input-help.log", self.adb("shell", "input", "help"))
        self.write_text("uiautomator-help.log", self.adb("shell", "uiautomator", "help"))
        def launcher_ready(root):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("HOME resolution deadline expired.")
            # First-boot setup can hand HOME to the launcher after KEYCODE_HOME.
            # Match each fresh tree against the currently resolved Activity.
            home = self.adb("shell", "cmd", "package", "resolve-activity", "--brief", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.HOME", timeout=min(20, remaining))
            self.write_text("home-activity.log", home)
            components = re.findall(r"^([A-Za-z0-9_.]+)/(?:[A-Za-z0-9_.$]+)$", home, re.MULTILINE)
            if not components:
                raise RuntimeError("Android has no resolved HOME Activity for the runtime check.")
            return any(node.get("package") == components[-1] for node in root.iter("node"))

        self.adb("shell", "input", "keyevent", "KEYCODE_HOME")
        # boot_completed alone allowed a System UI ANR to cover the first app
        # in CI. Require consecutive fresh launcher trees before installation.
        for _ in range(3):
            deadline = time.monotonic() + 90
            self.wait_until("Expected a responsive Android launcher", launcher_ready, seconds=90)
        self.record("Verified responsive Android launcher before app installation")

    def setup(self, apk):
        self.prepare_device()
        self.stage = "install and launch"
        self.adb("install", "-r", str(apk), timeout=120)
        cleared = self.adb("shell", "pm", "clear", PACKAGE, timeout=30)
        if cleared.strip() != "Success":
            raise RuntimeError(f"Android could not reset the test app: {cleared}")
        self.launch("cold")
        self.capture("home", "home-practice", scroll="down")

    def rules(self, prefix="rules"):
        self.stage = prefix
        self.tap("home-how-to", scroll="down")
        self.capture(f"{prefix}-intro", "rules-first-step", "Know the table.", scroll="down")
        self.capture(f"{prefix}-last-step", "rules-last-step", "Be the last light.", scroll="down")
        self.back()
        self.wait_for_tag("home-practice", scroll="down")
        self.tap("home-how-to", scroll="down")
        # Home has the same practice label; prove the second navigation arrived.
        self.wait_for_tag("rules-first-step", "Know the table.", scroll="down")
        self.capture(f"{prefix}-practice-action", "rules-practice", "Try a practice table", scroll="down", action=True)
        self.tap_node(self.wait_for_action("rules-practice", "Try a practice table", scroll="down"), "rules-practice")
        self.wait_for_tag("game-table", enabled=None)
        self.capture(f"{prefix}-practice-entered", "game-table")
        self.leave_table()
        self.capture(f"{prefix}-returned-home", "home-practice", scroll="down")
        self.record("Verified Rules Back, readable practice action, direct game entry and confirmed return Home")

    def settings_persistence(self):
        self.stage = "settings persistence"
        self.tap("home-settings", scroll="up")
        expected = {}
        for tag in ("settings-sound", "settings-haptics", "settings-reduce-motion"):
            node = self.wait_for_tag(tag, scroll="down")
            initial = checked(node)
            if initial is None:
                raise RuntimeError(f"{tag} does not expose its switch state to accessibility.")
            expected[tag] = not initial
            self.tap_node(node, tag)
            self.wait_until(f"Expected changed switch state for {tag}", lambda root: checked(self.find(root, tag)) == expected[tag])
        self.capture("settings-changed", "settings-reduce-motion")
        self.back()
        self.capture("settings-return-home", "home-practice", scroll="down")
        self.adb("shell", "am", "force-stop", PACKAGE)
        self.launch("saved-settings")
        self.tap("home-settings", scroll="up")
        for tag, value in expected.items():
            self.wait_for_tag(tag, scroll="down")
            self.wait_until(f"Expected saved {tag} after process restart", lambda root: checked(self.find(root, tag)) == value)
        self.observations["persisted_switches"] = expected
        self.capture("settings-persisted", "settings-reduce-motion")
        self.back()
        self.wait_for_tag("home-practice", scroll="down")
        self.record("Verified all three settings survive a real process restart")

    def wait_for_human_turn(self):
        deadline = time.monotonic() + 120
        rounds = 0
        while time.monotonic() < deadline:
            root = self.dump_ui(deadline)
            self.reject_crash_dialog(root)
            if self.find(root, "game-play", enabled=None) is not None:
                return
            next_round = self.find(root, "game-next-round")
            if next_round is not None:
                rounds += 1
                if rounds > 8:
                    raise RuntimeError("Practice did not offer a human play within eight rounds.")
                self.tap_node(next_round, "game-next-round")
            elif self.find(root, "game-winner", enabled=None) is not None:
                raise RuntimeError("Practice ended before the human play could be exercised.")
            else:
                self.swipe("down", root)
            time.sleep(0.3)
        raise RuntimeError("Practice did not offer a human play within 120 seconds.")

    def assert_concealed(self):
        self.wait_for_tag("game-reveal-hand", scroll="up")
        root = self.dump_ui()
        for node in root.iter("node"):
            tag = node.get("resource-id", "").rsplit("/", 1)[-1]
            if tag.startswith("game-card-") or re.search(r"\b(?:Crown|Moon|Star|Wild)\. Card \d+ of \d+\.", node.get("content-desc", "")):
                raise RuntimeError("A concealed hand still exposes private card semantics.")

    @staticmethod
    def hand_count(root):
        for node in root.iter("node"):
            match = re.search(r"\bCard \d+ of (\d+)\.", node.get("content-desc", ""))
            if match:
                return int(match.group(1))
        return None

    def leave_table(self, hosting=False):
        self.back()
        self.tap("leave-confirm", "End table" if hosting else "Leave table")
        self.wait_for_tag("home-practice", scroll="down")

    def practice(self):
        self.stage = "practice actions and privacy"
        self.tap("home-practice", scroll="down")
        self.wait_for_tag("game-table", enabled=None)
        self.wait_for_human_turn()
        self.assert_concealed()
        self.capture("practice-concealed", "game-reveal-hand")
        self.tap("game-reveal-hand")
        self.wait_for_tag("game-card-0")
        self.tap("game-card-0")
        self.wait_until("Expected a selected private card", lambda root: selected(self.find(root, "game-card-0")))
        self.wait_for_tag("game-play")
        self.capture("practice-selected", "game-card-0")
        self.tap("game-hide-hand")
        self.assert_concealed()
        self.wait_for_tag("game-play", enabled=False)
        self.tap("game-reveal-hand")
        self.wait_until("Expected selection cleared by Hide hand", lambda root: (
            self.find(root, "game-card-0") is not None and not selected(self.find(root, "game-card-0"))
        ))
        self.tap("game-card-0")
        self.wait_for_tag("game-play")
        self.adb("shell", "input", "keyevent", "KEYCODE_HOME")
        self.wait_until("Expected PartyDeck to leave the foreground", lambda root: not any(
            node.get("package") == PACKAGE for node in root.iter("node")
        ))
        self.launch("resume-practice")
        self.wait_for_tag("game-table", enabled=None)
        self.assert_concealed()
        self.wait_for_tag("game-play", enabled=False)
        self.capture("practice-resumed-concealed", "game-reveal-hand")
        self.tap("game-reveal-hand")
        self.wait_until("Expected selection cleared after background", lambda root: (
            self.find(root, "game-card-0") is not None and not selected(self.find(root, "game-card-0"))
        ))
        count_before = self.hand_count(self.dump_ui())
        if count_before is None:
            raise RuntimeError("The revealed hand does not expose a card count.")
        self.tap("game-card-0")
        self.tap("game-play")

        def accepted_play(root):
            if self.find(root, "problem-panel", enabled=None) is not None:
                raise RuntimeError("Playing a selected card raised a session error.")
            if self.find(root, "game-round-result", enabled=None) is not None:
                return "round result after play"
            if self.find(root, "game-winner", enabled=None) is not None:
                return "match result after play"
            return "hand decreased by one" if self.hand_count(root) == count_before - 1 else None

        self.observations["played_card"] = self.wait_until("Expected an accepted one-card play", accepted_play)
        self.capture("practice-after-play", "game-table")
        self.leave_table()
        self.capture("practice-returned-home", "home-practice")
        self.record("Verified reveal, selection, hide, background concealment, one-card play and leave")

    def host_invitation(self):
        self.stage = "host and invitation"
        self.tap("home-host", scroll="up")
        self.replace_text("host-name", "CIPlayer")
        self.tap("host-create", scroll="down")
        self.capture("host-lobby", "lobby-invitation", scroll="down")
        self.sensitive_surface = True
        self.tap("lobby-invitation")
        self.wait_for_tag("invitation-qr", QR_DESCRIPTION, enabled=None, scroll="down")
        self.tap("invitation-copy", "Copy invitation", scroll="down")
        self.wait_for_tag("invitation-done", "Done")
        self.tap("invitation-share", "Share invitation", scroll="up")
        self.wait_until("Expected the Android system Sharesheet", lambda root: any(
            node.get("package") in ("android", "com.android.intentresolver") for node in root.iter("node")
        ) and not any(node.get("package") == PACKAGE for node in root.iter("node")))
        self.back()
        self.tap("invitation-done", "Done")
        self.wait_for_tag("lobby-invitation")
        self.sensitive_surface = False
        self.capture("host-after-share", "lobby-invitation")
        self.leave_table(hosting=True)
        self.capture("host-returned-home", "home-practice")
        self.record("Verified real host, invitation QR/copy, Sharesheet cancellation and host teardown")

    def invalid_join(self, prefix="join"):
        self.stage = f"{prefix} validation and recovery"
        self.tap("home-join", scroll="up")
        self.replace_text("join-name", "CIPlayer", ime_capture=f"{prefix}-name-soft-ime")
        self.replace_text("join-invitation", "not-an-invitation")
        self.tap("join-submit", scroll="down")
        self.capture(f"{prefix}-invalid", "invalid-invitation", INVALID_INVITATION, scroll="up")
        self.replace_text("join-invitation", "edited-invitation", scroll="up")
        self.wait_for_tag("invitation-hint", INVITATION_HINT, enabled=None)
        self.wait_for_tag("join-submit", scroll="down")
        self.wait_for_tag("join-name", scroll="up")
        if not self.field_contains(self.dump_ui(), "join-name", "CIPlayer"):
            raise RuntimeError("Editing an invalid invitation discarded the player name.")
        self.back()
        self.wait_for_tag("home-practice", scroll="down")
        self.record("Verified invalid invitation feedback, editing recovery, preserved name and Back")

    def large_text(self):
        self.stage = "large text"
        self.save_setting("system", "font_scale", "2.0")
        self.adb("shell", "am", "force-stop", PACKAGE)
        self.launch("large-text")
        if self.adb("shell", "settings", "get", "system", "font_scale").strip() != "2.0":
            raise RuntimeError("Android did not apply font_scale=2.0.")
        self.observations["large_text_font_scale"] = 2.0
        for tag in ("home-host", "home-join", "home-practice", "home-how-to"):
            self.wait_for_tag(tag, scroll="down")
        self.capture("large-text-home-actions", "home-practice", scroll="up")
        self.rules("large-text-rules")
        self.tap("home-settings", scroll="up")
        for tag in ("settings-sound", "settings-haptics", "settings-reduce-motion"):
            self.wait_for_tag(tag, scroll="down")
        self.capture("large-text-settings", "settings-reduce-motion")
        self.back()
        self.invalid_join("large-text-join")
        self.tap("home-practice", scroll="down")
        self.wait_for_human_turn()
        self.assert_concealed()
        self.tap("game-reveal-hand", scroll="down")
        self.tap("game-card-0", scroll="down")
        self.wait_until("Expected a selected card at large text", lambda root: selected(self.find(root, "game-card-0")))
        self.capture("large-text-private-hand", "game-card-0")
        self.wait_for_tag("game-play", scroll="down")
        self.capture("large-text-play-action", "game-play")
        self.tap("game-hide-hand", scroll="up")
        self.assert_concealed()
        self.leave_table()
        self.record("Verified 200% text reachability for Home, rules, settings, Join, hand and play action")

    def run(self, apk):
        self.setup(apk)
        self.rules()
        self.settings_persistence()
        self.practice()
        self.host_invitation()
        self.invalid_join()
        self.large_text()
        self.stage = "complete"

    def diagnostics(self):
        # The emulator has bounded logcat buffers; retain startup events rather
        # than losing ANRs under repeated uiautomator process startup messages.
        for name, arguments in (
            ("logcat.log", ("logcat", "-d", "-b", "main", "-b", "system", "-b", "crash")),
            ("events.log", ("logcat", "-d", "-b", "events")),
            ("last-anr.log", ("shell", "dumpsys", "activity", "lastanr")),
        ):
            try:
                self.write_text(name, self.adb(*arguments, timeout=20))
            except TRANSIENT_ERRORS as error:
                self.write_text(name + ".error.log", str(error))
        try:
            self.dump_ui()
        except TRANSIENT_ERRORS as error:
            self.write_text("ui-dump.error.log", str(error))
        if self.sensitive_surface:
            self.write_text("final-screen-omitted.log", "A live invitation or Sharesheet may be visible; screenshot omitted.\n")
        else:
            try:
                screenshot = self.adb("exec-out", "screencap", "-p", timeout=15, binary=True)
                if screenshot.startswith(b"\x89PNG\r\n\x1a\n"):
                    (self.output / "final-screen.png").write_bytes(screenshot)
            except TRANSIENT_ERRORS as error:
                self.write_text("final-screen.error.log", str(error))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--apk", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--variant", choices=("debug", "optimized-test-signed"), default=None)
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)
    if not arguments.apk.is_file():
        raise SystemExit(f"APK does not exist: {arguments.apk}")
    smoke = AndroidSmoke(arguments.serial, arguments.output, arguments.variant or "unspecified")
    result = {
        "serial": arguments.serial, "variant": smoke.variant, "passed": False,
        "apk_sha256": hashlib.sha256(arguments.apk.read_bytes()).hexdigest(),
        "steps": smoke.steps, "observations": smoke.observations,
        "scope": "Single-emulator UI and local hosting; physical LAN, camera frames and store signing are separate gates.",
    }
    run_failed = False
    try:
        smoke.run(arguments.apk)
        result["passed"] = True
    except Exception as error:
        run_failed = True
        result["error"] = redacted(str(error))
        result["stage"] = smoke.stage
        raise
    finally:
        try:
            smoke.diagnostics()
        except Exception as error:
            result["passed"] = False
            result["diagnostic_errors"] = [redacted(str(error))]
        finally:
            # A diagnostic parse/write failure must not skip restoring settings
            # or replace the original app failure with a cleanup exception.
            try:
                restore_errors = smoke.restore_environment()
            except Exception as error:
                restore_errors = [str(error)]
            if restore_errors:
                result["passed"] = False
                result["environment_restore_errors"] = [redacted(error) for error in restore_errors]
            try:
                (arguments.output / "smoke-result.json").write_text(json.dumps(result, indent=2) + "\n")
            except OSError as error:
                if not run_failed:
                    raise
                print(f"Could not write Android smoke result: {redacted(str(error))}", file=sys.stderr, flush=True)
    if not result["passed"]:
        raise SystemExit("Android diagnostic collection or environment restoration failed; see smoke-result.json.")
    print(f"Android {smoke.variant} runtime flows passed.", flush=True)


if __name__ == "__main__":
    main()
