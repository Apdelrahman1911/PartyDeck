#!/usr/bin/env python3
"""Bind original ordinary XCTest and three-case UIKit evidence to the exact retry."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import runpy
import metadata_guard_v3 as guarded

BASE = Path("/root/projects/PartyDeck/artifacts/evidence-storage/34559902607")
SOURCE_ROOT = BASE.parent / "source-39405bb0-ios-scope-v2-7tdjsk4j/source-scope"
SOURCE = SOURCE_ROOT / "source"
SUPPLEMENT = BASE / "source-supplements/uikit"
ARTIFACT = "ios-reports-and-simulator-app"
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
integrity_path = BASE / f"{ARTIFACT}.integrity.json"
integrity = read(integrity_path)
assert integrity["runId"] == RUN and integrity["headSha"] == HEAD
assert integrity["allZipMembersStreamHashedAndCRCVerified"]
inventory_path = BASE / f"{ARTIFACT}.files.json"
inventory_list = read(inventory_path)
inventory = {item["path"]: item for item in inventory_list}
assert len(inventory) == len(inventory_list)
early_path = BASE / "completed-native-job-log-outcomes-v1.json"
early = read(early_path)
assert early["headSha"] == HEAD and early["runId"] == RUN
steps = {step["number"]: step for step in early["steps"]}
assert steps[9]["conclusion"] == steps[14]["conclusion"] == steps[15]["conclusion"] == "success"
assert steps[9]["name"] == "Run native shared tests and link device framework"
assert steps[14]["name"] == "Build and test the iOS Simulator application"
assert steps[15]["name"] == "Qualify native UIKit Godot shell layout"
source_pins = [pinned(SOURCE_ROOT / "source-scope-frozen-v1.json", "06d272806e41136094aa17eed32606b4f4c9391e327abede781690e28f48a7f0"),
               pinned(SOURCE_ROOT / "source-run-binding-v1.json", "f37d6cd9a91590991b7db681a15792820a67f893902b86dbfc30b5b92179bcf0")]
binding = read(SOURCE_ROOT / "source-run-binding-v1.json")
assert (binding["runId"], binding["headSha"], binding["attempt"]) == (RUN, HEAD, 1)
source_catalog = {row["sourcePath"]: row for row in binding["selectedSourceFiles"]}
supplement_pin = pinned(SUPPLEMENT / "SUPPLEMENT.json", "c7b868c62d439f91b2ef2531d4128814cf632126769808f0432c5ed58dd9c206")
supplement = read(SUPPLEMENT / "SUPPLEMENT.json")
assert (supplement["runId"], supplement["headSha"], supplement["attempt"]) == (RUN, HEAD, 1)
assert supplement["existing234FileFreezeModified"] is False and supplement["blobObjectSha1MatchesTreeEntry"] is True


def source_for(relative):
    if relative == "scripts/check-ios-godot-layout.py":
        path = SUPPLEMENT / "check-ios-godot-layout.py"
        expected = supplement["source"]
    else:
        path, expected = SOURCE / relative, source_catalog[relative]
    actual = record(path)
    assert all(actual[key] == expected[key] for key in ("bytes", "sha256"))
    return path

ordinary_source = pinned(SOURCE / "iosApp/PartyDeckUITests/PartyDeckUITests.swift", "fcc57b669ca638da439b8a42d93d518d273b2df88b625e1dfe8408bc1d68f23d")


def original(relative):
    assert not Path(relative).is_absolute() and ".." not in Path(relative).parts
    expected = inventory[relative]
    if expected["retainedExtracted"]:
        actual = record(BASE / ARTIFACT / relative)
        assert all(actual[key] == expected[key] for key in ("bytes", "sha256")), relative
        return {**actual, "archiveMember": relative, "retainedExtracted": True}
    return {"archivePath": integrity["archivePath"], "archiveMember": relative,
            **{key: expected[key] for key in ("bytes", "sha256", "zipCRC32")}, "retainedExtracted": False}


def document(relative):
    assert original(relative)["retainedExtracted"]
    return read(BASE / ARTIFACT / relative)


def local_log(relative, scope):
    evidence = original(relative)
    text = (BASE / ARTIFACT / relative).read_text(errors="replace")
    started = re.findall(r"^Test Case '-\[([^\]\s]+) (test\w+)\]' started\.$", text, re.MULTILINE)
    finished = re.findall(r"^Test Case '-\[([^\]\s]+) (test\w+)\]' (passed|failed|skipped) \((\d+(?:\.\d+)?) seconds\)\.$", text, re.MULTILINE)
    cases = [{"case": f"{target}/{name}", "status": status, "wallSecondsText": seconds} for target, name, status, seconds in finished]
    expected = Counter(early["scopes"][scope]["expectedCaseSet"])
    assert Counter(f"{target}/{name}" for target, name in started) == Counter(row["case"] for row in cases) == expected
    assert cases == [{key: row[key] for key in ("case", "status", "wallSecondsText")} for row in early["scopes"][scope]["finished"]]
    assert all(row["status"] == "passed" for row in cases)
    assert "** TEST SUCCEEDED **" in text and "** TEST FAILED **" not in text
    return {"originalLog": evidence, "cases": cases, "counts": dict(Counter(row["status"] for row in cases)),
            "exactNamedCasesEachStartedAndFinishedOnce": True}, text


ordinary, _ = local_log("build/ci/ios/xcodebuild.log", "ordinary")
assert len(ordinary["cases"]) == 9
orchestration = document("build/ci/ios/interop/orchestration.json")
interop = document("build/ci/ios/interop/result.json")
assert orchestration["xcodeExitCode"] == orchestration["javaExitCode"] == 0 and orchestration["passed"] is True
assert interop["status"] == "PASS" and interop["version"] == 1
assert all(interop[key] == expected for key, expected in {"forwardBytesReceived": 65536, "forwardBytesSent": 20000,
                                                       "reverseBytesSent": 20000, "reverseBytesReceived": 65536}.items())
ordinary.update(testSource=ordinary_source, orchestrationReceipt=original("build/ci/ios/interop/orchestration.json"),
                xcodebuildExitCode=0, interopResult=original("build/ci/ios/interop/result.json"),
                javaSwiftTwoDirectionExchangePassed=True,
                nativeUnitCasesPassed=sum(row["case"].startswith("PartyDeckTests.") for row in ordinary["cases"]),
                uiCasesPassed=sum(row["case"].startswith("PartyDeckUITests.") for row in ordinary["cases"]),
                hostNameWaitSourceLine=next(index for index, line in enumerate((SOURCE / "iosApp/PartyDeckUITests/PartyDeckUITests.swift").read_text().splitlines(), 1)
                    if 'waitUntil("The entered host name must reach the native field value before hosting.")' in line),
                hostCasePassed=any(row["case"].endswith("/testSharedControllerHostsANativeTableAndShowsItsInvitation") and row["status"] == "passed" for row in ordinary["cases"]),
                ordinaryStep=steps[14])

layout, layout_text = local_log("build/ci/ios/godot-layout/test.log", "uikit-layout")
assert len(layout["cases"]) == 3
checker_path = source_for("scripts/check-ios-godot-layout.py")
checker_source = pinned(checker_path, "b35ce76b04efded3c8726eb739fd574cc5cbaa0542ebe2c9ba863530311a4bf7")
checker = runpy.run_path(str(checker_path))
summary = document("build/ci/ios/godot-layout/test-summary.json")
gate = document("build/ci/ios/godot-layout/result.json")
settings = document("build/ci/ios/godot-layout/build-settings.json")
status = document("build/ci/ios/godot-layout/command-status.json")
assert checker["inspect_log"](layout_text)[2] and checker["inspect_summary"](summary)
runner_plist = Path("/Users/runner/work/PartyDeck/PartyDeck/iosApp/PartyDeck/Info.plist")
assert checker["inspect_settings"](settings, runner_plist)
assert gate["source_revision"] == HEAD and gate["native_layout_named_test_evidence_complete"] is True
assert gate["build_settings_valid"] is True and gate["production_engine_or_shipping_promotion"] is False
assert gate["command_exit"] == 0 and gate["command_status"] == status
assert all(type(status[key]) is int and status[key] == 0 for key in checker["STATUS_KEYS"])
assert gate["finished"] == [{"case": row["case"], "status": row["status"], "seconds": row["wallSecondsText"]} for row in layout["cases"]]
mapped_sources = []
for item in gate["source_files"]:
    mapped_sources.append(pinned(source_for(item["path"]), item["sha256"]))
assert {item["path"] for item in gate["source_files"]} == set(checker["SOURCE_FILES"])
mapped_evidence = []
for item in gate["evidence_files"]:
    relative = item["path"][item["path"].index("build/ci/ios/"):]
    actual = original(relative)
    assert actual["sha256"] == item["sha256"]
    mapped_evidence.append(actual)
layout.update(originalSummary=original("build/ci/ios/godot-layout/test-summary.json"), summary=summary,
              originalGate=original("build/ci/ios/godot-layout/result.json"), gate=gate,
              originalSettings=original("build/ci/ios/godot-layout/build-settings.json"),
              originalCommandStatus=original("build/ci/ios/godot-layout/command-status.json"),
              checkerSource=checker_source, checkerSourceSupplement=supplement_pin,
              mappedSourceFiles=mapped_sources, mappedGateEvidence=mapped_evidence,
              effectiveAppAndNativeTestQualificationConditionsVerified=True, layoutStep=steps[15])
captures, manifests = [], []
for scope, prefix in (("ordinary", "build/ci/ios/attachments/"), ("uikit-layout", "build/ci/ios/godot-layout/attachments/")):
    manifest = document(prefix + "manifest.json")
    manifests.append({"scope": scope, "original": original(prefix + "manifest.json")})
    occurrences = Counter()
    for case_index, case in enumerate(manifest, 1):
        for attachment_index, attachment in enumerate(case["attachments"], 1):
            filename = attachment["exportedFileName"]
            assert filename == Path(filename).name and filename not in ("", ".", "..")
            key = (case["testIdentifier"], attachment["suggestedHumanReadableName"])
            occurrences[key] += 1
            captures.append({"scope": scope, "testIdentifier": case["testIdentifier"],
                             "manifestCaseOrdinal": case_index, "caseAttachmentOrdinal": attachment_index,
                             "sameRawLabelOccurrence": occurrences[key], "exportMetadata": attachment,
                             "original": original(prefix + attachment["exportedFileName"]), "mediaViewedByCollector": False})
shared_path = BASE / "shared-native-junit-audit-v1.json"
shared = read(shared_path)
assert (shared["runId"], shared["headSha"], shared["attempt"]) == (RUN, HEAD, 1)
assert shared["everyObservedCasePassed"] is True and shared["totals"]["tests"] > 0
assert all(shared["totals"][key] == 0 for key in ("failures", "errors", "skipped"))
output = BASE / "ordinary-and-uikit-outcomes-v1.json"
result = {"runId": RUN, "headSha": HEAD, "attempt": 1,
          "createdAtUtc": datetime.now(timezone.utc).isoformat(), "auditor": record(Path(__file__)),
          "sourceReferences": source_pins, "originalNativeJobLogOutcome": record(early_path),
          "originalArtifactIntegrity": record(integrity_path), "originalMemberInventory": record(inventory_path),
          "ordinary": ordinary, "uikitLayout": layout,
          "sharedNativeJUnit": {"audit": record(shared_path), "originalJobMetadata": early["originalJobMetadata"], "step": steps[9]},
          "attachmentManifests": manifests, "exportedAttachmentPointers": captures,
          "scope": "Dedicated original XCTest logs agree with the completed job log on nine ordinary passes and three separate UIKit passes. The original UIKit summary/gate/status/settings and its eight frozen source hashes are independently reconciled. Ordinary Java–Swift exchange and exact host-name wait source are bound. Original exported attachments are hashed and indexed without media viewing. Production sessions and actual packaged app-byte audits remain separate; no timing cause, physical-device or shipping acceptance is inferred."}
METADATA.write(output, (json.dumps(result, indent=2) + "\n").encode())
print(json.dumps({"audit": record(output), "ordinary": ordinary["counts"], "uikitLayout": layout["counts"],
                  "exportedAttachments": len(captures)}, indent=2))
