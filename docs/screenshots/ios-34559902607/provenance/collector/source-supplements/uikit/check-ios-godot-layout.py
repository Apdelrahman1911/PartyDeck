#!/usr/bin/env python3
"""Verify the separate three-case UIKit shell qualification; never count it as engine acceptance."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys


EXPECTED = {
    ("PartyDeckTests.GodotPresentationViewControllerTests", "testPortraitStageUsesAvailableHeightWithStandardText"),
    ("PartyDeckTests.GodotPresentationViewControllerTests", "testPortraitStageUsesAvailableHeightWithAccessibilityText"),
    ("PartyDeckTests.GodotPresentationViewControllerTests", "testNativeChildRemainsInsideTheHiddenAccessibilityContainer"),
}
PREFIX = r"^Test Case '-\[([^\]\s]+) (test\w+)\]' "
STATUS_KEYS = (
    "native_test_exit_code", "test_log_exit_code", "attachments_export_exit_code",
    "summary_export_exit_code", "app_verification_exit_code", "app_archive_exit_code",
)
SOURCE_FILES = (
    "scripts/validate-ios-godot-layout.sh", "scripts/check-ios-godot-layout.py",
    "iosApp/PartyDeck/Godot/GodotPresentationViewController.swift",
    "iosApp/PartyDeckTests/GodotPresentationViewControllerTests.swift",
    "iosApp/PartyDeck.xcodeproj/project.pbxproj", "iosApp/Configuration/App.xcconfig",
    "iosApp/PartyDeck/Info.plist", ".github/workflows/validate.yml",
)


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON field.")
        value[key] = item
    return value


def read_json(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def inspect_settings(value, app_plist):
    if not isinstance(value, list) or len(value) != 2:
        return False
    targets = {}
    for target in value:
        if not isinstance(target, dict) or target.get("target") not in {"PartyDeck", "PartyDeckTests"}:
            return False
        name = target["target"]
        settings = target.get("buildSettings")
        if name in targets or not isinstance(settings, dict):
            return False
        conditions = settings.get("SWIFT_ACTIVE_COMPILATION_CONDITIONS")
        if (not isinstance(conditions, str)
                or not {"DEBUG", "PARTYDECK_GODOT_SESSION_QUALIFICATION"} <= set(shlex.split(conditions))
                or settings.get("CONFIGURATION") != "Debug"
                or settings.get("PLATFORM_NAME") != "iphonesimulator"):
            return False
        targets[name] = settings
    if set(targets) != {"PartyDeck", "PartyDeckTests"}:
        return False
    app, tests = targets["PartyDeck"], targets["PartyDeckTests"]
    return (app.get("INFOPLIST_FILE") == str(app_plist) and app.get("GENERATE_INFOPLIST_FILE") == "NO"
            and app.get("PARTYDECK_GODOT_ACTIVATION_EXPECTATION") in (None, "")
            and tests.get("GENERATE_INFOPLIST_FILE") == "YES" and tests.get("INFOPLIST_FILE") in (None, ""))


def inspect_log(text):
    started = re.findall(PREFIX + r"started\.$", text, re.MULTILINE)
    finished = re.findall(PREFIX + r"(passed|failed|skipped) \((\d+(?:\.\d+)?) seconds\)\.$", text, re.MULTILINE)
    passed = (len(started) == len(EXPECTED) and set(started) == EXPECTED
              and len(finished) == len(EXPECTED)
              and {(target, name) for target, name, _, _ in finished} == EXPECTED
              and all(status == "passed" for _, _, status, _ in finished)
              and "** TEST SUCCEEDED **" in text and "** TEST FAILED **" not in text)
    return started, finished, passed


def inspect_summary(value):
    counts = {"totalTestCount": 3, "passedTests": 3, "failedTests": 0, "skippedTests": 0, "expectedFailures": 0}
    return (isinstance(value, dict) and value.get("result") == "Passed" and value.get("testFailures") == []
            and all(type(value.get(key)) is int and value[key] == count for key, count in counts.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    settings_parser = subparsers.add_parser("settings")
    result_parser = subparsers.add_parser("result")
    for target in (settings_parser, result_parser):
        target.add_argument("--build-settings", required=True, type=Path)
        target.add_argument("--app-plist", required=True, type=Path)
    for name in ("test-log", "xcresult", "attachments", "summary", "command-status", "source-root", "output"):
        result_parser.add_argument("--" + name, required=True, type=Path)
    result_parser.add_argument("--command-exit", required=True, type=int)
    args = parser.parse_args()
    problems = []
    try:
        settings_ok = inspect_settings(read_json(args.build_settings), args.app_plist)
    except (OSError, ValueError, RecursionError):
        settings_ok = False
    if not settings_ok:
        problems.append("Both actual app and native-test Simulator Debug targets must compile the explicit qualification condition and retain their intended plists.")
    if args.mode == "settings":
        print(json.dumps({"native_layout_build_settings_valid": settings_ok, "problems": problems}))
        return 0 if settings_ok else 1
    if args.output.exists():
        parser.error("Preserve the previous native layout receipt before another execution.")

    text = args.test_log.read_text(errors="replace") if args.test_log.is_file() else ""
    started, finished, log_ok = inspect_log(text)
    if not log_ok:
        problems.append("Exactly the three named UIKit cases must each start once and pass once; missing, failed, skipped, extra or repeated cases fail.")
    if args.command_exit != 0:
        problems.append("The native layout command or required evidence preservation failed.")
    try:
        command_status = read_json(args.command_status)
        if not isinstance(command_status, dict) or any(type(command_status.get(key)) is not int or command_status[key] != 0 for key in STATUS_KEYS):
            problems.append("Every native test, log, export, app verification and app archive command must report a successful exit.")
    except (OSError, ValueError, RecursionError):
        command_status = None
        problems.append("The separate native layout command-status receipt is missing or invalid.")
    try:
        summary_ok = inspect_summary(read_json(args.summary))
    except (OSError, ValueError, RecursionError):
        summary_ok = False
    if not summary_ok:
        problems.append("The original XCResult summary must independently report exactly three passes and zero failures, skips or expected failures.")
    result_files = [path for path in args.xcresult.rglob("*") if path.is_file() and path.stat().st_size > 0] if args.xcresult.is_dir() else []
    if not result_files:
        problems.append("The original nonempty native layout XCResult bundle must be preserved.")
    try:
        if not isinstance(read_json(args.attachments / "manifest.json"), list):
            raise ValueError("Invalid attachment manifest.")
    except (OSError, ValueError, RecursionError):
        problems.append("The original xcresulttool attachment export manifest must be preserved, including an empty manifest when no attachments exist.")
    sources = []
    for relative in SOURCE_FILES:
        source = args.source_root / relative
        if source.is_file():
            sources.append({"path": relative, "sha256": digest(source)})
        else:
            problems.append("Required native layout source identity is missing: " + relative)
    output = {
        "schemaVersion": 1, "stage": "native_uikit_shell_layout_named_test_evidence",
        "source_revision": os.environ.get("GITHUB_SHA"), "source_files": sources,
        "expected_cases": [f"{target}/{name}" for target, name in sorted(EXPECTED)],
        "started": [f"{target}/{name}" for target, name in started],
        "finished": [{"case": f"{target}/{name}", "status": status, "seconds": seconds} for target, name, status, seconds in finished],
        "command_exit": args.command_exit, "command_status": command_status,
        "build_settings_valid": settings_ok, "xcresult_preserved": bool(result_files),
        "evidence_files": [{"path": str(path), "sha256": digest(path)} for path in
                           [args.test_log, args.summary, args.build_settings, args.command_status, args.attachments / "manifest.json"] if path.is_file()],
        "native_layout_named_test_evidence_complete": not problems,
        "production_engine_or_shipping_promotion": False, "problems": problems,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(output, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"native_layout_named_test_evidence_complete": not problems, "problems": problems}))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
