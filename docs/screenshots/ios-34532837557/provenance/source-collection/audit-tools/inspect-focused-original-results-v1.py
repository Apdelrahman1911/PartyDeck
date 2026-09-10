#!/usr/bin/env python3
"""Bind the focused native outcome to original API, logs, summaries and attachments."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import shlex

BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE.parent / "source-e4871e1/source-e4871e1"
NAME = "ios-focused-production-reports-and-simulator-app"
ARTIFACT = (BASE / NAME).resolve()
SESSION = ARTIFACT / "build/ci/ios/godot-session"
RUN = 34532837557
HEAD = "e4871e165f949c600ddd89b13e74d06fc34d2e04"


def read(path):
    return json.loads(path.read_bytes())


def record(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest}


def optional_record(path):
    return record(path) if path.is_file() else None


def write(path, document):
    with path.open("x") as stream:
        stream.write(json.dumps(document, indent=2) + "\n")


run = read(BASE / "last-run-status.json")
assert run["id"] == RUN and run["head_sha"] == HEAD and run["run_attempt"] == 1
assert run["path"] == ".github/workflows/validate.yml" and run["event"] == "workflow_dispatch"
assert run["status"] == "completed"
jobs = read(BASE / "last-jobs-status.json")["jobs"]
native_job = next(job for job in jobs if job["name"] == "Focused iOS production Godot sessions")
assert native_job["status"] == "completed"
for job in jobs:
    assert job["run_id"] == RUN and job["head_sha"] == HEAD and job["run_attempt"] == 1
steps = {step["name"]: step for step in native_job["steps"]}
skipped = [
    "Run native shared tests and link device framework",
    "Preserve native shared test evidence before app compilation",
    "Build and test the iOS Simulator application",
    "Qualify native UIKit Godot shell layout",
    "Exercise both real production Godot practice sessions",
]
assert all(steps[name]["conclusion"] == "skipped" for name in skipped)
for name in ("Android and shared JVM tests", "iOS optimized unsigned device app"):
    assert next(job for job in jobs if job["name"] == name)["conclusion"] == "skipped"
job_log = BASE / f"job-{native_job['id']}.log"
assert job_log.is_file()

checker_path = SOURCE / "scripts/check-ios-production-session-smoke.py"
test_source = SOURCE / "iosApp/PartyDeckUITests/PartyDeckGodotSessionUITests.swift"
assert record(test_source)["sha256"] == "ec28d783a221a31af0fa6730d4dda734a1fad3c291e7938bc4916677babe62ab"
assert record(checker_path)["sha256"] == "03a4aec41a60fd29522d6dee97d3732a470b5e1e868cba711a8a1da928229b41"
checker = runpy.run_path(str(checker_path))
test_log = SESSION / "test.log"
summary_path = SESSION / "test-summary.json"
result_path = SESSION / "result.json"
exports_path = SESSION / "test-evidence-export.json"
settings_path = SESSION / "build-settings.json"
manifest_path = SESSION / "attachments/manifest.json"
log_text = test_log.read_text(errors="replace") if test_log.is_file() else ""
started, finished, log_passed = checker["inspect_log"](log_text)
summary = read(summary_path) if summary_path.is_file() else None
summary_passed = checker["inspect_summary"](summary)
result = read(result_path) if result_path.is_file() else None
exports = read(exports_path) if exports_path.is_file() else None
attachment_verifications = []
if result is not None:
    assert result["expected_cases"] == [f"{target}/{name}" for target, name in sorted(checker["EXPECTED"])]
    assert result["started"] == [f"{target}/{name}" for target, name in started]
    assert result["finished"] == [
        {"case": f"{target}/{name}", "status": status, "seconds": seconds}
        for target, name, status, seconds in finished
    ]
    assert result["test_log_sha256"] == (record(test_log)["sha256"] if test_log.is_file() else None)
    assert result["test_summary_sha256"] == (record(summary_path)["sha256"] if summary_path.is_file() else None)
    assert result["native_acceptance_or_shipping_promotion"] is False
    for item in result["attachments"]:
        original = record(SESSION / "attachments" / item["path"])
        assert original["sha256"] == item["sha256"]
        attachment_verifications.append(original)

settings_verified = None
if settings_path.is_file():
    settings = read(settings_path)
    assert len(settings) == 2 and {item["target"] for item in settings} == {"PartyDeck", "PartyDeckUITests"}
    for item in settings:
        value = item["buildSettings"]
        assert {"DEBUG", "PARTYDECK_GODOT_SESSION_QUALIFICATION"} <= set(shlex.split(value["SWIFT_ACTIVE_COMPILATION_CONDITIONS"]))
        assert value["CONFIGURATION"] == "Debug" and value["PLATFORM_NAME"] == "iphonesimulator"
    settings_verified = True

observations, captures, failures = [], [], []
if manifest_path.is_file():
    manifest = read(manifest_path)
    for case in manifest:
        for attachment in case["attachments"]:
            path = SESSION / "attachments" / attachment["exportedFileName"]
            original = record(path)
            entry = {
                "testIdentifier": case["testIdentifier"], "exportMetadata": attachment,
                "original": original, "mediaDirectlyViewedByCollector": False,
            }
            if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".mp4", ".mov"):
                captures.append(entry)
            if path.suffix.lower() == ".json" and original["bytes"] <= 32768:
                try:
                    value = read(path)
                except (ValueError, OSError):
                    continue
                if not isinstance(value, dict) or value.get("schemaVersion") != 1 or value.get("observationInstalled") is not True:
                    continue
                entry["observationSequence"] = value.get("observationSequence")
                observations.append(entry)
                if "production smoke failure" in attachment["suggestedHumanReadableName"]:
                    failures.append({**entry, "observation": value})

inventory = read(BASE / f"{NAME}.files.json")
directory = read(BASE / f"{NAME}.zip-directory.json")
assert {item["path"] for item in inventory} == {item["path"] for item in directory if not item["directory"]}
xcresult = [item for item in inventory if "/PartyDeckGodotSessions.xcresult/" in item["path"]]
assert all(item["retainedExtracted"] for item in xcresult)
omitted = [item for item in inventory if not item["retainedExtracted"]]
assert all(item["path"] == "build/ci/ios/godot-session/PartyDeck-session-simulator.app.tar.gz" for item in omitted)
native_step = steps["Exercise the focused production Godot practice sessions"]
document = {
    "runId": RUN, "headSha": HEAD, "attempt": 1, "reviewedAtUtc": datetime.now(timezone.utc).isoformat(),
    "workflowConclusion": run["conclusion"], "nativeJobConclusion": native_job["conclusion"],
    "focusedStep": native_step, "skippedEarlierSuites": skipped,
    "skippedPlatformJobs": ["Android and shared JVM tests", "iOS optimized unsigned device app"],
    "originalRunMetadata": record(BASE / "last-run-status.json"),
    "originalJobMetadata": record(BASE / "last-jobs-status.json"),
    "originalNativeJobLog": record(job_log),
    "exactSourceBinding": record(BASE / "exact-source-binding.json"),
    "testSource": record(test_source), "checkerSource": record(checker_path),
    "originalTestLog": optional_record(test_log), "originalSummaryFile": optional_record(summary_path),
    "originalGateReceipt": optional_record(result_path), "originalExportStatus": optional_record(exports_path),
    "originalBuildSettings": optional_record(settings_path), "effectiveQualificationSettingsVerified": settings_verified,
    "started": [f"{target}/{name}" for target, name in started],
    "finished": [{"case": f"{target}/{name}", "status": status, "seconds": seconds}
                 for target, name, status, seconds in finished],
    "originalSummary": summary, "originalGateResult": result, "originalExportExitCodes": exports,
    "exactTwoCaseLogPassed": log_passed, "exactTwoCaseSummaryPassed": summary_passed,
    "originalManifest": optional_record(manifest_path), "originalAttachmentHashesVerified": attachment_verifications,
    "observationPointers": observations, "failureObservationAttachments": failures,
    "capturePointers": captures, "allMediaUnviewedByCollector": True,
    "xcresultOriginalFileCount": len(xcresult), "xcresultOriginalBytes": sum(item["bytes"] for item in xcresult),
    "allOriginalXCResultMembersRetained": bool(xcresult),
    "originalAppArchivesRetainedInsideCompleteZip": omitted,
    "nativeAcceptanceOrShippingPromotionAdded": False,
    "scope": "Original focused-production case evidence and preserved archive scope only. The test log, original exported summary, gate receipt, hashes, settings and skipped-suite metadata are reconciled. Failure capture attachments reuse the test's lastDocument and are not automatically fresh observations at screenshot time. Case elapsed times are XCTest wall times, not exclusive native/CPU/GPU costs. Full Validate and other native qualification remain separate.",
}
target = BASE / "focused-production-outcome-v1.json"
write(target, document)
print(json.dumps({"receipt": record(target), "workflowConclusion": run["conclusion"],
                  "nativeJobConclusion": native_job["conclusion"], "finished": document["finished"],
                  "failureAttachments": len(failures), "captureCount": len(captures)}, indent=2))
