#!/usr/bin/env python3
"""Reconcile the full retry production originals without extracting XCResults or media."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import shlex
import metadata_guard_v3 as guarded
import ios_current_attachment_schema_v1 as attachment_schema

BASE = Path("/root/projects/PartyDeck/artifacts/evidence-storage/34559902607")
SOURCE_ROOT = BASE.parent / "source-39405bb0-ios-scope-v2-7tdjsk4j/source-scope"
SOURCE = SOURCE_ROOT / "source"
NAME = "ios-reports-and-simulator-app"
SESSION_PREFIX = "build/ci/ios/godot-session/"
SESSION = BASE / NAME / SESSION_PREFIX
RUN = 34559902607
HEAD = "39405bb0fd6ba0214e70ed251aab1f9f571dc9aa"


def unique_object(pairs):
    output = {}
    for key, value in pairs:
        assert key not in output, "Duplicate JSON field."
        output[key] = value
    return output


def read(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique_object)


def record(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest}


def pinned(path, sha):
    value = record(path)
    assert value["sha256"] == sha, path
    return value


config = read(BASE / "collector-configuration-v1.json")
assert (config["runId"], config["headSha"], config["attempt"]) == (RUN, HEAD, 1)
assert record(Path(guarded.__file__))["sha256"] == config["metadataGuard"]["sha256"] == "921e84e155a3307ff7f691a032c638914b6323704f9a1d4fe6877a0977eb9af6"
METADATA = guarded.MetadataGuard(BASE, ceiling_bytes=config["metadataGuard"]["ceilingBytes"],
                                  minimum_available_bytes=config["metadataGuard"]["minimumAvailableBytes"])
assert config["metadataGuard"]["ceilingBytes"] == 16777216 and config["metadataGuard"]["minimumAvailableBytes"] == 1073741824
schema_pin = pinned(Path(attachment_schema.__file__), "fc9cea014f6996891fe643a0e97e9a337134d2192df20761192415b4c1b9d335")


def write(path, value):
    METADATA.write(path, (json.dumps(value, indent=2) + "\n").encode())


run_path = next(path for path in sorted((BASE / "api-snapshots").glob("20*-run.json"), reverse=True)
                if read(path)["status"] == "completed")
jobs_path = run_path.with_name(run_path.name.replace("-run.json", "-jobs.json"))
run, jobs = read(run_path), read(jobs_path)["jobs"]
assert run["id"] == RUN and run["head_sha"] == HEAD and run["run_attempt"] == 1
assert run["path"] == ".github/workflows/validate.yml" and run["event"] == "workflow_dispatch"
native_job = next(job for job in jobs if job["name"] == "iOS native tests and app smoke")
assert native_job["status"] == "completed"
for job in jobs:
    assert job["run_id"] == RUN and job["head_sha"] == HEAD and job["run_attempt"] == 1
steps = {step["name"]: step for step in native_job["steps"]}
skipped = ["Exercise the focused production Godot practice sessions", "Exercise both shipping Godot picker entries"]
assert all(steps[name]["conclusion"] == "skipped" for name in skipped)
assert next(job for job in jobs if job["name"] == "Android and shared JVM tests")["conclusion"] == "skipped"

source_pins = [
    pinned(SOURCE_ROOT / "source-scope-frozen-v1.json", "06d272806e41136094aa17eed32606b4f4c9391e327abede781690e28f48a7f0"),
    pinned(SOURCE_ROOT / "source-run-binding-v1.json", "f37d6cd9a91590991b7db681a15792820a67f893902b86dbfc30b5b92179bcf0"),
]
binding = read(SOURCE_ROOT / "source-run-binding-v1.json")
assert (binding["headSha"], binding["runId"], binding["attempt"]) == (HEAD, RUN, 1)
source_catalog = {row["sourcePath"]: row for row in binding["selectedSourceFiles"]}
test_source = pinned(SOURCE / "iosApp/PartyDeckUITests/PartyDeckGodotSessionUITests.swift",
                     "bb94c5b30414eed5e5a0ed9a51ab14fdce55101c6216ab00d8a4d30961d12fa6")
schema_source_paths = ["iosApp/PartyDeckUITests/PartyDeckGodotSessionUITests.swift",
                      "iosApp/PartyDeckUITests/PartyDeckUITests.swift",
                      "iosApp/PartyDeck/Godot/GodotPresentationPort.swift",
                      "iosApp/PartyDeck/Godot/GodotSessionQualificationObservation.swift",
                      "iosApp/PartyDeck/Godot/GodotPresentationViewController.swift",
                      "composeApp/src/commonMain/kotlin/dev/partydeck/app/controller/SessionQualificationObservation.kt"]
schema_sources = [pinned(SOURCE / relative, source_catalog[relative]["sha256"]) for relative in schema_source_paths]
checker_path = SOURCE / "scripts/check-ios-production-session-smoke.py"
checker_source = pinned(checker_path, "03a4aec41a60fd29522d6dee97d3732a470b5e1e868cba711a8a1da928229b41")
checker = runpy.run_path(str(checker_path))
integrity_path = BASE / f"{NAME}.integrity.json"
integrity = read(integrity_path)
assert integrity["runId"] == RUN and integrity["headSha"] == HEAD
assert integrity["allZipMembersStreamHashedAndCRCVerified"] and integrity["completeOriginalArchivePreserved"]
inventory_path = BASE / f"{NAME}.files.json"
inventory_list = read(inventory_path)
inventory = {item["path"]: item for item in inventory_list}
assert len(inventory) == len(inventory_list)
directory = read(BASE / f"{NAME}.zip-directory.json")
assert set(inventory) == {item["path"] for item in directory if not item["directory"]}


def original(relative):
    assert not Path(relative).is_absolute() and ".." not in Path(relative).parts
    member = SESSION_PREFIX + relative
    if member not in inventory:
        return None
    expected = inventory[member]
    if expected["retainedExtracted"]:
        value = record(SESSION / relative)
        assert all(value[key] == expected[key] for key in ("bytes", "sha256"))
        return {**value, "archiveMember": member, "retainedExtracted": True}
    return {"archivePath": integrity["archivePath"], "archiveMember": member,
            **{key: expected[key] for key in ("bytes", "sha256", "zipCRC32")}, "retainedExtracted": False}


def document(relative):
    value = original(relative)
    assert value and value["retainedExtracted"], relative
    return read(SESSION / relative)


log_text = (SESSION / "test.log").read_text(errors="replace")
started, finished, log_passed = checker["inspect_log"](log_text)
summary, result = document("test-summary.json"), document("result.json")
exports, settings = document("test-evidence-export.json"), document("build-settings.json")
summary_passed = checker["inspect_summary"](summary)
assert result["expected_cases"] == [f"{target}/{name}" for target, name in sorted(checker["EXPECTED"])]
assert result["started"] == [f"{target}/{name}" for target, name in started]
assert result["finished"] == [{"case": f"{target}/{name}", "status": status, "seconds": seconds}
                              for target, name, status, seconds in finished]
assert result["test_log_sha256"] == original("test.log")["sha256"]
assert result["test_summary_sha256"] == original("test-summary.json")["sha256"]
assert result["native_acceptance_or_shipping_promotion"] is False
assert result["named_test_evidence_complete"] is True and result["command_exit"] == 0 and result["problems"] == []
assert log_passed and summary_passed
assert all(type(exports.get(key)) is int and exports[key] == 0
           for key in ("attachments_export_exit_code", "summary_export_exit_code"))
assert steps["Exercise both real production Godot practice sessions"]["conclusion"] == "success"
early_path = BASE / "completed-native-job-log-outcomes-v1.json"
early = read(early_path)
assert (early["runId"], early["headSha"], early["attempt"]) == (RUN, HEAD, 1)
early_scope = early["scopes"]["production-sessions"]
assert early_scope["eachExpectedCaseStartedAndFinishedExactlyOnce"] and early_scope["allExpectedNamedCasesPassed"]
assert result["started"] == [row["case"] for row in early_scope["started"]]
assert result["finished"] == [{"case": row["case"], "status": row["status"], "seconds": row["wallSecondsText"]}
                              for row in early_scope["finished"]]
attachment_verifications = []
for item in result["attachments"]:
    value = original("attachments/" + item["path"])
    assert value["sha256"] == item["sha256"]
    attachment_verifications.append(value)
assert len(settings) == 2 and {item["target"] for item in settings} == {"PartyDeck", "PartyDeckUITests"}
for item in settings:
    value = item["buildSettings"]
    assert {"DEBUG", "PARTYDECK_GODOT_SESSION_QUALIFICATION"} <= set(shlex.split(value["SWIFT_ACTIVE_COMPILATION_CONDITIONS"]))
    assert value["CONFIGURATION"] == "Debug" and value["PLATFORM_NAME"] == "iphonesimulator"

captures, observations, failure_observations, scroll, ignored_json = [], [], [], [], []
manifest = document("attachments/manifest.json")
expected_identifiers = {"PartyDeckGodotSessionUITests/testProduction2DPracticeSession()": "2d",
                        "PartyDeckGodotSessionUITests/testProduction3DPracticeSession()": "3d"}
assert type(manifest) is list and len(manifest) == 2
assert {case["testIdentifier"] for case in manifest} == set(expected_identifiers)
seen_exports, label_occurrences = set(), Counter()
for case_index, case in enumerate(manifest, 1):
    identifier = case["testIdentifier"]
    mode = expected_identifiers[identifier]
    assert case["testIdentifierURL"] == "test://com.apple.xcode/PartyDeck/PartyDeckUITests/" + identifier.removesuffix("()")
    for attachment_index, attachment in enumerate(case["attachments"], 1):
        filename = attachment["exportedFileName"]
        assert type(filename) is str and filename == Path(filename).name and filename not in ("", ".", "..")
        assert filename not in seen_exports, "Duplicate exported attachment file identity."
        seen_exports.add(filename)
        relative = "attachments/" + filename
        value = original(relative)
        assert value is not None
        entry = {"testIdentifier": identifier, "testIdentifierURL": case["testIdentifierURL"],
                 "manifestCaseOrdinal": case_index, "caseAttachmentOrdinal": attachment_index,
                 "exportMetadata": attachment, "original": value, "mediaDirectlyViewedByCollector": False}
        suffix = Path(relative).suffix.lower()
        classification = attachment_schema.source_label(attachment["suggestedHumanReadableName"], mode)
        if classification:
            kind, source_name = classification
            label_occurrences[(identifier, kind, source_name)] += 1
            entry.update(sourceAttachmentKind=kind, sourceAttachmentName=source_name,
                         sameSourceLabelOccurrenceInManifest=label_occurrences[(identifier, kind, source_name)])
        if suffix in (".png", ".jpg", ".jpeg", ".mp4", ".mov"):
            captures.append(entry)
        if suffix != ".json":
            continue
        if classification is None or classification[0] not in ("observation", "body-scroll"):
            ignored_json.append({"testIdentifier": identifier, "caseAttachmentOrdinal": attachment_index,
                                 "original": value, "decoded": False,
                                 "reason": "Not an explicitly source-named sanitized observation or body-scroll attachment."})
            continue
        assert 0 < value["bytes"] <= 32768 and value["retainedExtracted"] is True
        data = document(relative)
        if classification[0] == "observation":
            attachment_schema.validate_observation(data, mode)
            state, port = data["controller"], data["port"]
            native = port.get("native")
            context = {
                "observationSequence": data["observationSequence"], "caseMode": mode,
                "controller": {key: state[key] for key in (
                    "sessionGeneration", "presentationOrdinal", "mode", "lifecycle", "screen", "sessionPresent", "practice",
                    "foreground", "backgrounded", "privacyEpoch", "leaveConfirmation")},
                "port": {key: port[key] for key in ("active", "closing", "ownerCreated", "portReadyConfirmed")},
            }
            for key in ("phase", "sessionRevision", "projectedRendererRevision", "projectedSessionRevision", "fallbackReason"):
                if key in state:
                    context["controller"][key] = state[key]
            for key in ("preparation", "lastCloseSucceeded"):
                if key in port:
                    context["port"][key] = port[key]
            if native is not None:
                context["native"] = {key: native[key] for key in (
                    "processIdentifier", "presentationGeneration", "lifecycleGeneration", "inputGeneration", "bootstrapCount",
                    "nativePresentedFrames", "iterations", "drawCalls", "readyEvents", "authorityReadyConfirmed",
                    "nativeForeground", "authorityForegroundGrant", "applicationBackgrounded", "privacyCoverVisible",
                    "renderLoopActive", "dormant", "emptyTree", "retainedEnginePolicy", "retainedIdentitiesMatchFirstEntry")}
                for key in ("bootstrapPhase", "maxBootstrapSeconds", "maxDrawSeconds", "maxIterateSeconds", "maxDrainSeconds"):
                    if key in native:
                        context["native"][key] = native[key]
            entry.update(observationSequence=data["observationSequence"], validatedSanitizedSchemaAndContext=True,
                         context=context, missingNullAndZeroPreserved=True)
            observations.append(entry)
            if "production smoke failure" in classification[1]:
                failure_observations.append({**entry, "observation": data})
        else:
            attachment_schema.validate_body_scroll(data, mode)
            assert str(data["round"]) == classification[1].split(" round ", 1)[1].split(" ", 1)[0]
            scroll.append({**entry, "coverage": data, "validatedSanitizedSchemaAndContext": True})
assert {entry["context"]["caseMode"] for entry in observations} == {"2d", "3d"}
failures = [{"line": number, "text": line} for number, line in enumerate(log_text.splitlines(), 1)
            if "error:" in line and "PartyDeckGodotSessionUITests" in line]
xcresult = [item for item in inventory.values() if "/PartyDeckGodotSessions.xcresult/" in item["path"]]
assert xcresult and all(not item["retainedExtracted"] for item in xcresult)
apps = [item for item in inventory.values() if item["path"].endswith(".app.tar.gz")]
assert all(not item["retainedExtracted"] for item in apps)
output = BASE / "production-session-outcome-v1.json"
value = {"runId": RUN, "headSha": HEAD, "attempt": 1, "reviewedAtUtc": datetime.now(timezone.utc).isoformat(),
         "auditor": record(Path(__file__)), "workflowConclusion": run["conclusion"],
         "nativeJobConclusion": native_job["conclusion"], "productionStep": steps["Exercise both real production Godot practice sessions"],
         "skippedOtherSelection": skipped, "skippedPlatformJobs": ["Android and shared JVM tests"],
         "originalRunMetadata": record(run_path), "originalJobMetadata": record(jobs_path),
         "originalNativeJobLog": record(BASE / f"job-{native_job['id']}.log"),
         "frozenSourceReferences": source_pins, "testSource": test_source, "checkerSource": checker_source,
         "attachmentSchemaAuditor": schema_pin, "sanitizedAttachmentSourceReferences": schema_sources,
         "originalNativeJobOutcomeAudit": record(early_path),
         "originalArchiveIntegrity": record(integrity_path), "originalMemberInventory": record(inventory_path),
         "originalTestLog": original("test.log"), "originalSummaryFile": original("test-summary.json"),
         "originalGateReceipt": original("result.json"), "originalExportStatus": original("test-evidence-export.json"),
         "originalBuildSettings": original("build-settings.json"), "effectiveQualificationSettingsVerified": True,
         "started": result["started"], "finished": result["finished"], "failuresInTestLog": failures,
         "originalSummary": summary, "originalGateResult": result, "originalExportExitCodes": exports,
         "exactTwoCaseLogPassed": log_passed, "exactTwoCaseSummaryPassed": summary_passed,
         "originalManifest": original("attachments/manifest.json"), "originalAttachmentHashesVerified": attachment_verifications,
         "observationPointers": observations, "failureObservationAttachments": failure_observations,
         "passiveBodyScrollEvidence": scroll, "capturePointers": captures, "allMediaUnviewedByCollector": True,
         "otherJSONAttachmentPointersNotDecoded": ignored_json,
         "sourceLabelOccurrencesUseOriginalManifestOrder": True,
         "rawRejectedJSONOrOpaqueUISnapshotsDecoded": False,
         "xcresultOriginalFileCount": len(xcresult), "xcresultOriginalBytes": sum(item["bytes"] for item in xcresult),
         "allOriginalXCResultMembersRetainedInZip": True, "xcresultWorkingExtractionCreated": False,
         "originalAppArchivesRetainedInsideCompleteZip": apps, "nativeAcceptanceOrShippingPromotionAdded": False,
         "scope": "Exact frozen source, immutable API snapshots, exported test log/summary/gate/settings and attachment hashes are reconciled. No raw XCResult or video decode is performed. Failure captures reuse only successfully decoded lastDocument; absent JSON does not establish a specific decoder error. XCTest wall time is not a CPU/GPU measurement. Production results do not qualify the separately audited ordinary, shared-native, UIKit, device or shipping scopes."}
write(output, value)
print(json.dumps({"receipt": record(output), "finished": value["finished"], "captureCount": len(captures),
                  "observationCount": len(observations), "passiveScrollEvidenceCount": len(scroll)}, indent=2))
