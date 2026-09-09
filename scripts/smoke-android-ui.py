#!/usr/bin/env python3
"""Install PartyDeck and exercise real Android navigation through accessibility tags."""

import argparse
import json
import pathlib
import re
import subprocess
import time
import xml.etree.ElementTree as ET


class AndroidSmoke:
    def __init__(self, serial, output):
        self.serial = serial
        self.output = output
        self.last_error = "No UI dump yet."
        self.steps = []

    def adb(self, *arguments, timeout=20, binary=False):
        result = subprocess.run(
            ["adb", "-s", self.serial, *arguments],
            capture_output=True,
            text=not binary,
            timeout=timeout,
            check=True,
        )
        return result.stdout

    def wait_for_boot(self):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                timeout = min(10, max(0.1, deadline - time.monotonic()))
                if self.adb("shell", "getprop", "sys.boot_completed", timeout=timeout).strip() == "1":
                    return
            except (subprocess.SubprocessError, OSError) as error:
                self.last_error = str(error)
            time.sleep(min(2, max(0, deadline - time.monotonic())))
        raise RuntimeError(f"Android did not boot within 180 seconds: {self.last_error}")

    def dump_ui(self, deadline=None):
        if deadline is None:
            deadline = time.monotonic() + 30

        def remaining_timeout():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("UI dump deadline expired.")
            return min(20, remaining)

        # A failed uiautomator dump can return exit 0 and leave its old file intact.
        # Remove it first so readiness can only use a fresh accessibility snapshot.
        self.adb("shell", "rm", "-f", "/sdcard/partydeck-ci-ui.xml", timeout=remaining_timeout())
        dump_output = self.adb("shell", "uiautomator", "dump", "/sdcard/partydeck-ci-ui.xml", timeout=remaining_timeout())
        (self.output / "last-ui-dump.log").write_text(dump_output)
        xml = self.adb("shell", "cat", "/sdcard/partydeck-ci-ui.xml", timeout=remaining_timeout())
        root = ET.fromstring(xml)
        (self.output / "last-ui.xml").write_text(xml)
        return root

    def wait_for_tag(self, tag, fallback_text=None):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                root = self.dump_ui(deadline)
                for node in root.iter("node"):
                    resource_id = node.get("resource-id", "")
                    matches_tag = resource_id == tag or resource_id.endswith("/" + tag)
                    matches_text = fallback_text is not None and fallback_text in (
                        node.get("text"), node.get("content-desc")
                    )
                    if (matches_tag or matches_text) and node.get("enabled") != "false":
                        return node
                self.last_error = f"Tag {tag!r} was absent from the accessibility tree."
            except (subprocess.SubprocessError, OSError, ET.ParseError) as error:
                self.last_error = str(error)
            time.sleep(min(1, max(0, deadline - time.monotonic())))
        raise RuntimeError(f"Screen did not become ready within 45 seconds: {self.last_error}")

    def tap(self, tag, fallback_text=None):
        node = self.wait_for_tag(tag, fallback_text)
        bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
        if bounds is None:
            raise RuntimeError(f"Tag {tag!r} has no usable on-screen bounds.")
        left, top, right, bottom = map(int, bounds.groups())
        if right <= left or bottom <= top:
            raise RuntimeError(f"Tag {tag!r} has empty on-screen bounds.")
        self.adb("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))
        self.steps.append(f"Tapped {tag}")

    def capture(self, name, ready_tag):
        self.wait_for_tag(ready_tag)
        screenshot = self.adb("exec-out", "screencap", "-p", binary=True)
        if not screenshot.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError(f"Android did not return a PNG screenshot for {name}.")
        (self.output / f"{name}.png").write_bytes(screenshot)
        (self.output / f"{name}.xml").write_text((self.output / "last-ui.xml").read_text())
        self.steps.append(f"Verified {name}: {ready_tag}")

    def run(self, apk):
        self.wait_for_boot()
        self.adb("shell", "input", "keyevent", "82")
        for setting in ["window_animation_scale", "transition_animation_scale", "animator_duration_scale"]:
            self.adb("shell", "settings", "put", "global", setting, "0")
        self.adb("install", "-r", str(apk), timeout=120)
        cleared = self.adb("shell", "pm", "clear", "dev.partydeck.app", timeout=30)
        if cleared.strip() != "Success":
            raise RuntimeError(f"Android could not reset the test app: {cleared}")
        (self.output / "uiautomator-help.log").write_text(self.adb("shell", "uiautomator", "help"))
        launch = self.adb("shell", "am", "start", "-W", "-n", "dev.partydeck.app/.MainActivity", timeout=60)
        (self.output / "launch.log").write_text(launch)
        if not re.search(r"^\s*Status:\s*ok\s*$", launch, re.MULTILINE):
            raise RuntimeError(f"Android activity did not complete startup with Status: ok: {launch}")

        self.capture("home", "home-practice")
        self.tap("home-settings")
        self.capture("settings", "settings-sound")
        self.tap("navigation-back")
        self.wait_for_tag("home-practice")
        self.tap("home-practice")
        self.capture("practice", "game-table")
        self.tap("navigation-back")
        # A dialog may have its own accessibility root. Its visible, localized
        # English button is a fallback if the activity's resource-ID opt-in is absent.
        self.tap("leave-confirm", fallback_text="Leave table")
        self.capture("returned-home", "home-practice")

    def diagnostics(self):
        for name, arguments, binary in [
            ("logcat.log", ("logcat", "-d", "-t", "2000"), False),
            ("final-screen.png", ("exec-out", "screencap", "-p"), True),
        ]:
            try:
                content = self.adb(*arguments, timeout=15, binary=binary)
                path = self.output / name
                path.write_bytes(content) if binary else path.write_text(content)
            except (subprocess.SubprocessError, OSError) as error:
                (self.output / (name + ".error.log")).write_text(str(error))
        try:
            self.dump_ui()
        except (subprocess.SubprocessError, OSError, ET.ParseError) as error:
            (self.output / "ui-dump.error.log").write_text(str(error))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--apk", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)
    if not arguments.apk.is_file():
        raise SystemExit(f"APK does not exist: {arguments.apk}")
    smoke = AndroidSmoke(arguments.serial, arguments.output)
    result = {"serial": arguments.serial, "passed": False, "steps": smoke.steps}
    try:
        smoke.run(arguments.apk)
        result["passed"] = True
        print("Android install, launch, settings, practice, and return-home smoke passed.", flush=True)
    except (RuntimeError, subprocess.SubprocessError, OSError) as error:
        result["error"] = str(error)
        raise
    finally:
        smoke.diagnostics()
        (arguments.output / "smoke-result.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
