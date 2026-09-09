#!/usr/bin/env python3
"""Prepare the wrapper-owned empty AVD before either APK acceptance run."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
import uuid
import xml.etree.ElementTree as ET


# Reuse the same strict launcher checks and redacted diagnostics as app smoke.
# This CLI helper must not leave bytecode files in the source checkout.
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "partydeck_android_ui_smoke", Path(__file__).with_name("smoke-android-ui.py"),
)
ui_smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ui_smoke
spec.loader.exec_module(ui_smoke)
ERRORS = (RuntimeError, ValueError, *ui_smoke.TRANSIENT_ERRORS)


def require_app_absent(smoke):
    packages = smoke.adb("shell", "pm", "list", "packages", ui_smoke.PACKAGE)
    smoke.write_text("installed-app-check.log", packages)
    if f"package:{ui_smoke.PACKAGE}" in packages.splitlines():
        raise RuntimeError("AVD preparation requires PartyDeck to be absent; recovery cannot retry an installed app.")


def boot_id(smoke, timeout=10):
    value = smoke.adb("shell", "cat", "/proc/sys/kernel/random/boot_id", timeout=timeout).strip()
    return str(uuid.UUID(value))


def system_ui_boot_anr(error, output):
    if not str(error).startswith("emulator readiness: System UI isn't responding."):
        return False
    try:
        root = ET.parse(output / "failure-ui.xml").getroot()
        titles = [node.get("text") for node in root.iter("node")
                  if node.get("resource-id") == "android:id/alertTitle"]
        logcat = (output / "logcat.log").read_text()
        return "System UI isn't responding" in titles and "ANR in com.android.systemui" in logcat
    except (OSError, ET.ParseError):
        return False


def prepare_attempt(serial, output, number):
    output.mkdir(parents=True, exist_ok=True)
    smoke = ui_smoke.AndroidSmoke(serial, output, f"avd-preparation-{number}")
    # If an unexpected installed app is present, never capture its private UI.
    smoke.sensitive_surface = True
    result = {"attempt": number, "passed": False, "app_absent": False, "recovery_allowed": False}
    error = None
    diagnostic_errors = []
    try:
        smoke.wait_for_boot()
        require_app_absent(smoke)
        smoke.sensitive_surface = False
        result["app_absent"] = True
        result["boot_id"] = boot_id(smoke)
        result["android_api"] = smoke.adb("shell", "getprop", "ro.build.version.sdk").strip()
        smoke.write_text("android-api.log", result["android_api"] + "\n")
        smoke.prepare_device()
        result["passed"] = True
    except ERRORS as caught:
        error = caught
        result["error"] = ui_smoke.redacted(str(caught))
        result["stage"] = smoke.stage
        # diagnostics() makes another fresh dump; preserve the failing tree too.
        try:
            for name in ("last-ui.xml", "last-ui-dump.log"):
                source = output / name
                if source.is_file():
                    smoke.write_text(name.replace("last-", "failure-"), source.read_text())
        except OSError as diagnostic_error:
            diagnostic_errors.append(ui_smoke.redacted(str(diagnostic_error)))
    finally:
        try:
            smoke.diagnostics()
        except ERRORS as diagnostic_error:
            diagnostic_errors.append(ui_smoke.redacted(str(diagnostic_error)))
        finally:
            # Diagnostic parsing or writes must never bypass setting restoration.
            try:
                restore_errors = smoke.restore_environment()
            except ERRORS as restore_error:
                restore_errors = [ui_smoke.redacted(str(restore_error))]
            if diagnostic_errors:
                result["passed"] = False
                result["diagnostic_errors"] = diagnostic_errors
            if restore_errors:
                result["passed"] = False
                result["environment_restore_errors"] = restore_errors
            result["recovery_allowed"] = bool(
                number == 1 and result["app_absent"] and result.get("boot_id")
                and not diagnostic_errors and not restore_errors
                and error is not None and system_ui_boot_anr(error, output)
            )
            result["steps"] = smoke.steps
            (output / "preparation-attempt.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def reboot_once(serial, output, previous_boot_id):
    smoke = ui_smoke.AndroidSmoke(serial, output, "avd-reboot")
    # Recheck directly before the only reboot; never recover an app smoke.
    require_app_absent(smoke)
    smoke.write_text("reboot-command.log", smoke.adb("reboot", timeout=20))
    deadline = time.monotonic() + 180
    last_error = "The kernel boot ID has not changed."
    while time.monotonic() < deadline:
        try:
            remaining = max(0.1, deadline - time.monotonic())
            current_id = boot_id(smoke, timeout=min(10, remaining))
            if current_id != previous_boot_id:
                remaining = max(0.1, deadline - time.monotonic())
                if smoke.adb("shell", "getprop", "sys.boot_completed", timeout=min(10, remaining)).strip() == "1":
                    return current_id
        except ui_smoke.TRANSIENT_ERRORS as error:
            last_error = str(error)
        time.sleep(min(1, max(0, deadline - time.monotonic())))
    raise RuntimeError(f"AVD did not complete a new boot within 180 seconds: {last_error}")


def prepare(serial, output):
    output.mkdir(parents=True, exist_ok=True)
    result = {
        "serial": serial, "passed": False, "reboot_attempted": False, "attempts": [],
        "scope": "Empty AVD preparation only; neither APK is installed or accepted by this phase.",
    }
    try:
        first = prepare_attempt(serial, output / "attempt-1", 1)
        result["attempts"].append(first)
        if first["passed"]:
            result["passed"] = True
        elif first["recovery_allowed"]:
            print("First-boot System UI ANR preserved; rebooting the empty AVD once before app acceptance.", flush=True)
            result["reboot_attempted"] = True
            result["new_boot_id"] = reboot_once(serial, output, first["boot_id"])
            second = prepare_attempt(serial, output / "attempt-2", 2)
            result["attempts"].append(second)
            result["passed"] = second["passed"]
        if not result["passed"]:
            raise RuntimeError("AVD preparation failed; neither APK acceptance run may start.")
    except ERRORS as error:
        result["error"] = ui_smoke.redacted(str(error))
        raise
    finally:
        (output / "preparation-result.json").write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    prepare(arguments.serial, arguments.output)
    print("AVD prepared; strict debug and optimized APK acceptance can begin.", flush=True)


if __name__ == "__main__":
    main()
