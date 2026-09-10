#!/usr/bin/env python3
"""Close the focused collection without copying, executing or viewing native payloads."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re


BASE = Path(__file__).resolve().parents[1]
BULK = (BASE / "bulk-shm").resolve()
NAME = "ios-focused-production-reports-and-simulator-app"
SESSION = BASE / NAME / "build/ci/ios/godot-session"
SOURCE = BASE.parent / "source-e4871e1/source-e4871e1"
RUN = 34532837557
HEAD = "e4871e165f949c600ddd89b13e74d06fc34d2e04"
EXPECTED = {NAME, "ios-renderer-pack", "ios-renderer-pack-evidence"}
APP_TAR = "build/ci/ios/godot-session/PartyDeck-session-simulator.app.tar.gz"


def utc():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_bytes())


def record(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest}


def same(actual, expected):
    assert actual["bytes"] == expected["bytes"]
    assert actual["sha256"] == expected["sha256"]


def write(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")


def label(item):
    name = item["exportMetadata"]["suggestedHumanReadableName"]
    name = re.sub(r"_\d+_[0-9A-Fa-f-]{36}\.[^.]+$", "", name)
    return name.removesuffix(" latest sanitized observation")


completion = read(BASE / "collection-complete.json")
assert completion["runId"] == RUN and completion["headSha"] == HEAD
assert completion["attempt"] == 1 and completion["conclusion"] == "failure"
assert set(completion["downloadedArtifacts"]) == EXPECTED
assert completion["missingExpectedArtifacts"] == [] and completion["collectionErrors"] == {}
assert set(completion["savedJobLogs"]) == {103057440580, 103057688066}
outcome = read(BASE / "focused-production-outcome-v1.json")
app_audit = read(BASE / "production-source-and-app-verification.json")
assert outcome["runId"] == app_audit["runId"] == RUN
assert outcome["headSha"] == app_audit["headSha"] == HEAD
assert [(item["case"].rsplit("/", 1)[1], item["status"]) for item in outcome["finished"]] == [
    ("testProduction2DPracticeSession", "failed"), ("testProduction3DPracticeSession", "passed")]
assert outcome["effectiveQualificationSettingsVerified"] is True
assert outcome["allMediaUnviewedByCollector"] is True

artifacts = read(BASE / "artifacts.json")["artifacts"]
assert len(artifacts) == 3 and {item["name"] for item in artifacts} == EXPECTED
bulk_records, archive_checks = {}, []
for artifact in sorted(artifacts, key=lambda item: item["name"]):
    name = artifact["name"]
    assert artifact["workflow_run"]["id"] == RUN and artifact["workflow_run"]["head_sha"] == HEAD
    integrity_path = BASE / f"{name}.integrity.json"
    integrity = read(integrity_path)
    assert integrity["runId"] == RUN and integrity["headSha"] == HEAD
    assert integrity["allZipMembersStreamHashedAndCRCVerified"] is True
    assert integrity["completeOriginalArchivePreserved"] is True
    archive = Path(integrity["physicalArchivePath"])
    actual = record(archive)
    same(actual, {"bytes": artifact["size_in_bytes"], "sha256": artifact["digest"].removeprefix("sha256:")})
    bulk_records[str(archive)] = actual
    members = read(BASE / f"{name}.files.json")
    directory = read(BASE / f"{name}.zip-directory.json")
    assert len({item["path"] for item in members}) == len(members)
    assert {item["path"] for item in members} == {item["path"] for item in directory if not item["directory"]}
    extracted_count = extracted_bytes = 0
    omitted = []
    for member in members:
        target = (BASE / name / member["path"]).resolve()
        assert target.is_relative_to(BULK)
        assert member["zipCRCVerifiedByCompleteStream"] is True
        if member["retainedExtracted"]:
            actual_member = record(target)
            same(actual_member, member)
            bulk_records[str(target)] = actual_member
            extracted_count += 1
            extracted_bytes += actual_member["bytes"]
        else:
            assert name == NAME and member["path"] == APP_TAR
            assert not target.exists()
            same(app_audit["apps"][0]["archiveMember"], member)
            omitted.append(member)
    assert extracted_count == integrity["extractedFileCount"]
    assert extracted_bytes == integrity["extractedBytes"]
    assert len(omitted) == (1 if name == NAME else 0)
    archive_checks.append({"artifactId": artifact["id"], "name": name,
                           "actualOriginalArchive": actual, "integrityReceipt": record(integrity_path),
                           "originalMemberHashInventory": record(BASE / f"{name}.files.json"),
                           "extractedFilesRehashed": extracted_count, "extractedBytesRehashed": extracted_bytes,
                           "unextractedMembers": omitted})

job_checks = []
for job_id in sorted(completion["savedJobLogs"]):
    receipt_path = BASE / f"job-{job_id}.collected.json"
    receipt = read(receipt_path)
    original = record(Path(receipt["path"]))
    same(original, receipt)
    bulk_records[str(Path(receipt["path"]).resolve())] = original
    job_checks.append({"jobId": job_id, "originalLog": original, "collectorReceipt": record(receipt_path)})
physical_files = {str(path.resolve()) for path in BULK.rglob("*") if path.is_file()}
assert physical_files == set(bulk_records)
assert not list((BULK / ".download-tmp").iterdir())
preservation_path = BASE / "preservation-verification-v1.json"
write(preservation_path, {
    "runId": RUN, "headSha": HEAD, "attempt": 1, "verifiedAtUtc": utc(),
    "canonicalRoot": str(BASE), "physicalBulkRoot": str(BULK),
    "originalArchives": archive_checks, "originalJobLogs": job_checks,
    "allOriginalArchivesRehashedAgainstApiDigests": True,
    "allExtractedFilesRehashedAgainstOriginalZipMemberInventories": True,
    "allExecutedJobLogsRehashedAgainstCollectorReceipts": True,
    "physicalFileCount": len(bulk_records), "physicalPayloadBytes": sum(item["bytes"] for item in bulk_records.values()),
    "noUninventoriedPhysicalFiles": True, "noPendingPartials": True,
    "originalAppTarOnlyInsideCompleteZip": True,
    "allXCResultAndDiagnosticMembersRetained": True,
    "packagedAppStreamingAudit": record(BASE / "production-source-and-app-verification.json"),
    "scope": "Existing payloads were reread and compared to the collector's original ZIP/API/log inventories. No transfer, native execution, payload deletion, duplicate app extraction, or media viewing occurred."
})

native_log = BASE / "job-103057688066.log"
native_log_record = record(native_log)
assert native_log_record["sha256"] == "a3a20be634d3c83a819620f6f50ab49a848bf5858994fcb0bd10874de6c410b5"
lines = native_log.read_bytes().splitlines(keepends=True)
first_line, last_line = 12145, 12244
excerpt = BASE / "focused-native-failure-context-original.log"
with excerpt.open("xb") as stream:
    stream.write(b"".join(lines[first_line - 1:last_line]))
summary = read(SESSION / "test-summary.json")
assert len(summary["testFailures"]) == 1 and summary["failedTests"] == summary["passedTests"] == 1
source_test = SOURCE / "iosApp/PartyDeckUITests/PartyDeckGodotSessionUITests.swift"
source_lines = source_test.read_text().splitlines()
assert "let text = node.value as? String" in source_lines[519]
manifest = read(SESSION / "attachments/manifest.json")
selected_names = {
    "7486CFB2-6A92-4624-A1DD-D559864588AE.json", "99AF59C5-7A66-46E7-A0F1-7428847B8C69.png",
    "C6EE2E29-6E57-4784-9BC6-0B7A76B20CE5.json", "65CD601F-0143-4553-AF50-C722297CA134.json",
    "4B7BA06B-97DF-4935-A5FA-712BA092E288.json", "1FAA2CD2-6B72-4E2D-84CA-C05B53EE6289.png"
}
selected = []
for case in manifest:
    for item in case["attachments"]:
        if item["exportedFileName"] in selected_names or item.get("isAssociatedWithFailure"):
            selected.append({"testIdentifier": case["testIdentifier"], "exportMetadata": item,
                             "original": record(SESSION / "attachments" / item["exportedFileName"]),
                             "mediaDirectlyViewedByCollector": False})
hierarchy = (SESSION / "attachments/260EDA7D-DDC8-4663-A572-5C40645F1662.txt").read_text()
assert "godot-session-status" not in hierarchy
assert all(token in hierarchy for token in ("partydeck-session-qualification", "leave-confirm", "leave-cancel"))
selection_path = BASE / "selected-original-evidence-v1.json"
write(selection_path, {
    "runId": RUN, "headSha": HEAD, "attempt": 1, "reviewedAtUtc": utc(),
    "originalNativeJobLog": native_log_record,
    "originalLogByteExcerpt": {"originalOneBasedFirstLine": first_line, "originalOneBasedLastLine": last_line,
                               "exactBytesIncludingOriginalLineTerminators": True, "excerpt": record(excerpt)},
    "originalSummary": record(SESSION / "test-summary.json"), "originalFailure": summary["testFailures"][0],
    "frozenSource": record(source_test),
    "sourceObservationRead": {"firstLine": 514, "lastLine": 521, "lines": source_lines[513:521]},
    "selectedOriginalAttachments": sorted(selected, key=lambda item: item["exportMetadata"]["timestamp"]),
    "failureAssociatedHierarchyFacts": {"godotSessionStatusAbsent": True,
        "swiftUiQualificationBadgePresent": True, "leaveConfirmPresent": True, "leaveCancelPresent": True},
    "customProductionSmokeFailureObservationAttachments": len(outcome["failureObservationAttachments"]),
    "limits": ["The later Leave JSON is the test's cached lastDocument; screenshot timing does not guarantee a new observation.",
               "The original log's generic runner restart line does not establish an app crash, exit reason, or native cause.",
               "2D is failed and 3D passed. No full-Validate, physical-device, shipping, performance or crash qualification is added.",
               "Selected images are indexed and hash verified; the collector has not directly viewed any media."]
})

captures = []
for item in sorted(outcome["capturePointers"], key=lambda entry: entry["exportMetadata"]["timestamp"]):
    source = Path(item["original"]["path"])
    canonical = SESSION / "attachments" / source.name
    matches = [entry for entry in outcome["observationPointers"]
               if entry["testIdentifier"] == item["testIdentifier"] and label(entry) == label(item)
               and abs(entry["exportMetadata"]["timestamp"] - item["exportMetadata"]["timestamp"]) <= 0.1]
    if source.suffix.lower() == ".png":
        assert len(matches) == 1
    else:
        assert source.suffix.lower() == ".mp4" and not matches
    captures.append({**item, "humanLabel": label(item), "canonicalOriginal": record(canonical),
                     "latestSanitizedObservationCompanions": matches,
                     "caseOutcome": "failed" if "testProduction2D" in item["testIdentifier"] else "passed",
                     "directViewNotes": None, "newCaptureOrAppExecution": False})
capture_path = BASE / "capture-handoff-v1.json"
write(capture_path, {
    "runId": RUN, "headSha": HEAD, "attempt": 1, "preparedAtUtc": utc(),
    "originalManifest": record(SESSION / "attachments/manifest.json"),
    "outcomeReceipt": record(BASE / "focused-production-outcome-v1.json"),
    "exactSourceBinding": record(BASE / "exact-source-binding.json"),
    "packagedAppVerification": record(BASE / "production-source-and-app-verification.json"),
    "actualPackSha256": app_audit["apps"][0]["actualPack"]["sha256"],
    "captures": captures, "captureCount": len(captures),
    "pngCount": sum(Path(item["original"]["path"]).suffix.lower() == ".png" for item in captures),
    "videoCount": sum(Path(item["original"]["path"]).suffix.lower() == ".mp4" for item in captures),
    "allObservationPointers": outcome["observationPointers"],
    "allMediaUnviewedByCollectorAtHandoff": True, "completedPeerViewNotesKnownToCollector": [],
    "scope": "Complete current focused-run media and observation pointers, with original case/timestamp/filename/hash provenance. PNG companions are matched by case, original human label and adjacent export timestamp; their cached lastDocument provenance does not guarantee screenshot-time freshness. This index copies no media, adds no visual acceptance, and must remain separate from later UI captures and video-review derivatives."
})

pins = {name: record(BASE / name) for name in [
    "collection-complete.json", "exact-source-binding.json", "production-source-and-app-verification.json",
    "focused-production-outcome-v1.json", "selected-original-evidence-v1.json", "capture-handoff-v1.json",
    "preservation-verification-v1.json"]}
handoff = [
    "Focused iOS production evidence: run 34532837557, attempt 1",
    "",
    f"Source: {HEAD}. The run and focused native job failed: testProduction2DPracticeSession failed; testProduction3DPracticeSession passed. The original XCResult summary independently reports one pass and one failure. Native test command exit 65; both required evidence exports exited 0.",
    "",
    "The 2D failure is the XCTest observation read at PartyDeckGodotSessionUITests.swift:520: no matching godot-session-status snapshot during the Leave transition. The failure-associated hierarchy shows the SwiftUI qualification badge and both Leave dialog controls, with the native status absent. Selected originals and the exact native-log interval are in selected-original-evidence-v1.json. A later cached observation is not a guaranteed fresh failure-time sample. The generic runner restart message is retained without attributing an app crash or native cause.",
    "",
    "All three API-digest-matching original ZIPs, both executed-job logs, all 1,626 XCResult member files and all diagnostics/attachments are retained. The production app tarball is retained only in its intact ZIP and was fully streamed, gzip/CRC checked, and member hashed. Its actual 160,908,168-byte arm64 iOS Simulator executable, Info.plist, PCK and resources match original runner receipts. All nine native source files match frozen e4871e1. Standalone native .a files are absent from this focused upload, so their archive hashes remain runner receipt evidence.",
    "",
    "capture-handoff-v1.json indexes every original focused capture (32 PNGs and one 2D screen recording) and all 47 observation pointers. The collector did not view media. Game-domain reached-predicate review, iOS lookup diagnosis, and design gallery review are separate peer work.",
    "",
    "Shared/JVM tests, ordinary iOS application tests, UIKit layout tests, and device packaging were skipped by the explicitly focused workflow. The failed 1/2 result does not qualify full Validate, physical devices, store/shipping readiness, CPU/GPU cost, timing causality, or a fixed native rerun.",
    "",
    f"Canonical root: {BASE}", f"Physical bulk root: {BULK}",
    "No source edits, new dispatch, native execution, duplicate transfer or media capture were performed by this collection.",
    "",
    "Pinned receipts:",
]
handoff.extend(f"- {name}: {value['sha256']}" for name, value in pins.items())
handoff.extend(["", "collection-frozen.json seals all real metadata files and the preserved physical payloads. Further analysis belongs in separately named supplements; frozen evidence must not be modified.", ""])
with (BASE / "HANDOFF.md").open("x") as stream:
    stream.write("\n".join(handoff))

metadata, aliases = [], []
for current, dirs, names in os.walk(BASE, followlinks=False):
    for name in list(dirs):
        path = Path(current) / name
        if path.is_symlink():
            aliases.append({"path": str(path), "target": str(path.readlink()), "resolvedTarget": str(path.resolve())})
            dirs.remove(name)
    for name in names:
        path = Path(current) / name
        if path.is_symlink():
            aliases.append({"path": str(path), "target": str(path.readlink()), "resolvedTarget": str(path.resolve())})
        else:
            metadata.append(record(path))
for item in metadata + list(bulk_records.values()):
    path = Path(item["path"])
    path.chmod(path.stat().st_mode & ~0o222)
freeze = {
    "runId": RUN, "headSha": HEAD, "attempt": 1, "frozenAtUtc": utc(),
    "canonicalRoot": str(BASE), "physicalBulkRoot": str(BULK),
    "collectorCompleted": True, "preservationVerification": record(preservation_path),
    "sourceBinding": pins["exact-source-binding.json"], "packagedAppVerification": pins["production-source-and-app-verification.json"],
    "namedOutcomeVerification": pins["focused-production-outcome-v1.json"],
    "selectedFailureEvidence": pins["selected-original-evidence-v1.json"], "captureHandoff": pins["capture-handoff-v1.json"],
    "handoff": record(BASE / "HANDOFF.md"),
    "metadataFiles": sorted(metadata, key=lambda item: item["path"]),
    "aliases": sorted(aliases, key=lambda item: item["path"]),
    "physicalPayloadFiles": sorted(bulk_records.values(), key=lambda item: item["path"]),
    "metadataFileCount": len(metadata), "physicalPayloadFileCount": len(bulk_records),
    "filesMadeReadOnly": True, "allOriginalPayloadsPreserved": True,
    "newNativeExecutionOrDispatch": False, "mediaViewedByCollector": False,
    "nativeAcceptanceOrShippingPromotionAdded": False,
    "scope": "Frozen original focused-production collection and its completed source/app/outcome/preservation audits. Hashes seal bytes; read-only modes prevent routine accidental edits. Later peer interpretation, candidate patches and gallery views belong in independent supplements, and do not change this failed 1/2 outcome."
}
freeze_path = BASE / "collection-frozen.json"
write(freeze_path, freeze)
freeze_path.chmod(0o444)
print(json.dumps({"freeze": record(freeze_path), "receipts": pins,
                  "metadataFileCount": len(metadata), "physicalPayloadFileCount": len(bulk_records)}, indent=2), flush=True)
