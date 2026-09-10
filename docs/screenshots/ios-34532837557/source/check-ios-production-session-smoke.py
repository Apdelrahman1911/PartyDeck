#!/usr/bin/env python3
"""Require both real production XCTest cases; never promote a platform/shipping qualification."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


EXPECTED = {
    ("PartyDeckUITests.PartyDeckGodotSessionUITests", "testProduction2DPracticeSession"),
    ("PartyDeckUITests.PartyDeckGodotSessionUITests", "testProduction3DPracticeSession"),
}
PREFIX = r"^Test Case '-\[([^\]\s]+) (test\w+)\]' "


def inspect_log(text: str) -> tuple[list, list, bool]:
    started = re.findall(PREFIX + r"started\.$", text, re.MULTILINE)
    finished = re.findall(PREFIX + r"(passed|failed|skipped) \((\d+(?:\.\d+)?) seconds\)\.$", text, re.MULTILINE)
    passed = (
        len(started) == len(EXPECTED) and set(started) == EXPECTED
        and len(finished) == len(EXPECTED)
        and {(target, name) for target, name, _, _ in finished} == EXPECTED
        and all(status == "passed" for _, _, status, _ in finished)
        and "** TEST SUCCEEDED **" in text
        and "** TEST FAILED **" not in text
    )
    return started, finished, passed


def inspect_summary(value: object) -> bool:
    expected = {"totalTestCount": 2, "passedTests": 2, "failedTests": 0, "skippedTests": 0, "expectedFailures": 0}
    return (isinstance(value, dict) and value.get("result") == "Passed" and value.get("testFailures") == []
            and all(type(value.get(key)) is int and value[key] == count for key, count in expected.items()))


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-log", required=True, type=Path)
    parser.add_argument("--xcresult", required=True, type=Path)
    parser.add_argument("--attachments", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--command-exit", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve the existing result receipt before another execution.")
    problems = []
    text = args.test_log.read_text(errors="replace") if args.test_log.is_file() else ""
    started, finished, passed = inspect_log(text)
    if not passed:
        problems.append("The two exact XCTest cases must each start once and pass once; zero, missing, skipped, failed, extra or repeated cases fail.")
    if args.command_exit != 0:
        problems.append("The native test command or required evidence export did not exit successfully.")
    result_preserved = args.xcresult.is_dir() and any(path.is_file() and path.stat().st_size > 0 for path in args.xcresult.rglob("*"))
    if not result_preserved:
        problems.append("The original nonempty XCResult bundle must be preserved.")
    attachments = [path for path in sorted(args.attachments.rglob("*")) if path.is_file() and path.stat().st_size > 0]
    screenshots = [path for path in attachments if path.suffix.lower() in {".png", ".jpg", ".jpeg"}]
    observations = []
    for path in attachments:
        if path.suffix.lower() != ".json" or path.stat().st_size > 32768:
            continue
        try:
            value = json.loads(path.read_bytes())
            if isinstance(value, dict) and value.get("schemaVersion") == 1 and value.get("observationInstalled") is True:
                observations.append(path)
        except (OSError, ValueError, RecursionError):
            continue
    if not screenshots or not observations:
        problems.append("Original screenshot and sanitized observation attachments must both be exported.")
    summary_hash = None
    try:
        summary = json.loads(args.summary.read_bytes())
        summary_hash = digest(args.summary)
        if not inspect_summary(summary):
            problems.append("The XCResult summary must independently report exactly two passes with zero failures, skips or expected failures.")
    except (OSError, ValueError, RecursionError):
        problems.append("The original XCResult test summary must be exported and preserved.")
    result = {
        "schemaVersion": 1,
        "stage": "production_session_named_test_evidence",
        "command_exit": args.command_exit,
        "expected_cases": [f"{target}/{name}" for target, name in sorted(EXPECTED)],
        "started": [f"{target}/{name}" for target, name in started],
        "finished": [{"case": f"{target}/{name}", "status": status, "seconds": seconds}
                     for target, name, status, seconds in finished],
        "test_log_sha256": digest(args.test_log) if args.test_log.is_file() else None,
        "test_summary_sha256": summary_hash,
        "xcresult_preserved": result_preserved,
        "attachments": [{"path": path.relative_to(args.attachments).as_posix(), "sha256": digest(path)} for path in attachments],
        "named_test_evidence_complete": passed and not problems,
        "native_acceptance_or_shipping_promotion": False,
        "problems": problems,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves earlier failures and prevents accidental replacement by a rerun.
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"named_test_evidence_complete": result["named_test_evidence_complete"], "problems": problems}))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
