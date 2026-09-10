#!/usr/bin/env python3
"""Join completed original-view observations to unchanged source identities/outcomes."""
import collections
import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("/tmp/partydeck-gallery-api36-ui-game-review-34506161751-v1")
EXPECTED_PLAN = "ab4b07a022f492f7324abc7a40740a3877701f839f82a2fadcc8eff692f623a0"
EXPECTED_ASSIGNMENT = "4d039215e4529cc83e9ed04af31906c73f3bb2057ebab70902e8ff3156db0dcd"
SOURCE_SCRIPT = Path("/tmp/partydeck-api36-startup-split-analysis-34506161751-v1/source/scripts/smoke-android-godot-session.py")
EXPECTED_SCRIPT = "7e9e1cfeba1676ad82b621597c3d26e9e39355cfcabff563e24cdb118b70d097"
NOW = datetime.now(timezone.utc).isoformat()

def identity(path, expected_sha=None, expected_bytes=None):
    p = Path(path)
    data = p.read_bytes()
    result = {"path": str(p), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if expected_sha is not None:
        assert result["sha256"] == expected_sha, (str(p), "sha256")
    if expected_bytes is not None:
        assert len(data) == expected_bytes, (str(p), "bytes")
    return result

def write(name, data):
    (BASE / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

assert not (BASE / "freeze.json").exists(), "Refusing to rewrite a frozen review"
plan_ref = identity(BASE / "view-plan-snapshot.json", EXPECTED_PLAN)
assignment_ref = identity(BASE / "assignment.json", EXPECTED_ASSIGNMENT)
plan = json.loads((BASE / "view-plan-snapshot.json").read_text())
assignment = json.loads((BASE / "assignment.json").read_text())
original_plan_ref = identity(assignment["plan"]["path"], EXPECTED_PLAN)
source_refs = {key: identity(value["path"], value["sha256"], value["bytes"])
               for key, value in plan.items()
               if key in ("sourceMapping", "sourceFreeze", "sourceOutcomeMatrix", "peerReceipt")}
source_refs["sourcePlan"] = original_plan_ref
source_refs["sourceRevealScript"] = identity(SOURCE_SCRIPT, EXPECTED_SCRIPT)
matrix = json.loads(Path(source_refs["sourceOutcomeMatrix"]["path"]).read_text())
assert matrix == plan["sourceOutcomes"], "Plan outcome snapshot differs from source matrix"
cases = {case["case"]: case for case in matrix["cases"]}
assigned = sorted(assignment["assigned"], key=lambda x: x["directViewOrder"])
expected_orders = list(range(58, 114))
assert [row["directViewOrder"] for row in assigned] == expected_orders
direct = [row for row in plan["captures"] if row["review_method"] == "direct_original"]
assert len(direct) == 113 and len(plan["captures"]) == 125
assert [row["index"] for row in direct[57:]] == [row["planCaptureIndex"] for row in assigned]
ledger = json.loads((BASE / "viewed-orders.json").read_text())
assert ledger["viewedDirectOrders"] == expected_orders and ledger["actualOriginalViews"] == 56

notes = {}
batches = []
for path in sorted((BASE / "reviews").glob("*.json")):
    batch = json.loads(path.read_text())
    assert batch["viewMethod"] == "tools.view_image" and batch["detail"] == "original"
    assert batch["reviewer"] == "/root/ui_game"
    assert batch["actualOriginalViews"] == len(batch["notes"])
    batch_ref = identity(path)
    batches.append(batch_ref)
    for note in batch["notes"]:
        order = note["directViewOrder"]
        assert order not in notes, ("duplicate", order)
        notes[order] = (note, batch_ref, batch["recordedUtc"])
assert sorted(notes) == expected_orders
captures, original_identities, companions = [], [], []
for row in assigned:
    order = row["directViewOrder"]
    original = plan["captures"][row["planCaptureIndex"]]
    assert original == direct[order - 1]
    assert original["review_method"] == "direct_original"
    for key in ("path", "bytes", "sha256", "dimensions", "sourceMappingRow"):
        assert row[key] == original[key], (order, key)
    png_ref = identity(row["path"], row["sha256"], row["bytes"])
    header = Path(row["path"]).read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR"
    dimensions = list(struct.unpack(">II", header[16:24]))
    assert dimensions == row["dimensions"], (order, "PNG IHDR")
    png_ref["dimensions"] = dimensions
    original_identities.append(png_ref)
    mapping = row["sourceMappingRow"]
    assert mapping["original"] is True
    assert mapping["dimensions"] == {"width": dimensions[0], "height": dimensions[1]}
    source_case = cases[mapping["case"]]
    assert mapping["caseOutcome"] == source_case["overallStatus"] == "unsupported"
    assert mapping["failedStage"] == source_case["failedStage"]
    scopes = {scope["name"]: scope["status"] for scope in source_case["scopes"]}
    scope_status = scopes[mapping["stage"]]
    if mapping["stage"].endswith(".held-rotation"):
        assert scope_status == "unsupported"
    else:
        assert scope_status == "passed"
    for kind in ("xml", "captureReceipt"):
        ref = mapping[kind]
        path = Path("/root/projects/PartyDeck/artifacts/evidence-storage/34506161751") / ref["file"]
        companions.append({"kind": kind, **identity(path, ref["sha256"], ref["bytes"])})
    note, batch_ref, recorded = notes[order]
    captures.append({
        "directOrder": order, "planIndex": row["planCaptureIndex"],
        **png_ref,
        "runId": mapping["runId"], "headSha": mapping["headSha"],
        "attempt": mapping["attempt"], "case": mapping["case"],
        "variant": mapping["variant"], "fontScale": mapping["fontScale"], "name": mapping["name"],
        "sourceCaseOutcome": mapping["caseOutcome"],
        "originalNamedStage": mapping["stage"], "originalNamedStageOutcome": scope_status,
        "originalFailedStage": mapping["failedStage"],
        "originalQualificationCaption": mapping["qualificationCaption"],
        "actuallyViewed": True, "actualOriginalViews": 1,
        "reviewer": "/root/ui_game", "reviewMethod": "direct_original",
        "viewTool": "tools.view_image", "viewDetail": "original",
        "observationRecordedUtc": recorded,
        "observation": " ".join(note[key] for key in ("visibleState", "layout", "privacy")),
        "visibleState": note["visibleState"], "layout": note["layout"], "privacy": note["privacy"],
        "findings": note["findings"],
        "sourceNoteBatch": batch_ref,
        "sourceMappingReference": {"path": source_refs["sourceMapping"]["path"], "sha256": source_refs["sourceMapping"]["sha256"], "originalPngFile": mapping["png"]["file"]},
        "limitations": ["still-only", "source-outcomes-unchanged", "viewport-state-only"]
    })
assert len({row["path"] for row in captures}) == len(captures) == 56
assert len({row["sha256"] for row in captures}) == 56
for case_name in {row["case"] for row in captures}:
    result = cases[case_name]["originalResult"]
    source_refs["originalCaseResult"] = identity(result["path"], result["sha256"], result["bytes"])

identity_check = {
    "schemaVersion": 1, "reviewer": "/root/ui_game", "verifiedUtc": NOW, "status": "passed",
    "checks": {"exactAssignedOrders": expected_orders, "uniqueOriginalPaths": 56, "uniqueOriginalHashes": 56,
               "verifiedPngHashesBytesAndIhdrDimensions": 56, "verifiedXmlAndCaptureReceiptReferences": len(companions),
               "allAssignmentsDirectOriginal": True, "allNotesAndViewsOnePerAssignment": True,
               "sourceMatrixMatchesPlanSnapshot": True, "originalCaseAndScopeOutcomesPreserved": True},
    "sourceReferences": source_refs, "originals": original_identities, "companionIdentities": companions
}
write("identity-check.json", identity_check)
scope_counts = dict(collections.Counter(row["originalNamedStageOutcome"] for row in captures))
findings = collections.defaultdict(list)
for row in captures:
    for tag in row["findings"]:
        findings[tag].append(row["directOrder"])
receipt = {
    "schemaVersion": 1, "reviewer": "/root/ui_game", "reviewedAtUtc": NOW,
    "status": "completed-original-still-review",
    "runId": plan["runId"], "headSha": plan["headSha"],
    **source_refs,
    "sourcePlanSnapshot": plan_ref, "assignment": assignment_ref,
    "identityCheck": identity(BASE / "identity-check.json"),
    "viewLedger": identity(BASE / "viewed-orders.json"),
    "reviewMethod": "direct_original", "viewTool": "tools.view_image", "viewDetail": "original",
    "counts": {"assignedOriginals": 56, "actualOriginalViews": 56, "perOriginalRecords": 56,
               "reusedOrPeerRowsViewed": 0, "derivatives": 0, "videosViewed": 0,
               "captureRecordsByOriginalNamedScopeOutcome": scope_counts},
    "assignmentDescription": "Filtered direct-view orders 58–113 inclusive; original plan indices 63–123 with excluded reused/peer rows.",
    "originalRunNamedScopeCounts": matrix["counts"],
    "originalCaseNamedScopeCounts": {name: cases[name]["counts"] for name in {row["case"] for row in captures}},
    "runtimeOutcomesChanged": False, "newRuntimeOrPrivacyQualification": False,
    "appExecutionsOrBuilds": 0, "sourceOrTrackedGalleryEdits": 0,
    "originalImageBytesUnchangedAfterViewing": True, "newScreenshots": 0,
    "revealContext": {"source": source_refs["sourceRevealScript"],
                      "observeMatchLines": [973, 984], "selectFirstCardLines": [987, 995],
                      "requireConcealedReturnLines": [997, 1010],
                      "interpretation": "The executed source explicitly invokes game-reveal-hand before first-card captures and selects a card before selected captures. Those are deliberately revealed states, not concealed-state evidence."},
    "limitations": {
        "still-only": "A retained still establishes only visible captured pixels. It does not establish unobserved transitions, engine gameplay, held-input success, concealment timing or continuous pixel privacy.",
        "source-outcomes-unchanged": "All original overall case and named-scope outcomes remain unchanged. A passed named scope is inherited from the source matrix, not awarded by this visual review; held-return recovery stills do not convert unsupported held-rotation to passed.",
        "viewport-state-only": "Content outside or cut by the captured viewport does not establish permanent clipping or unreachable controls. No scrolling or interaction was performed for this review."
    },
    "limitsApplyToEveryCapture": True,
    "findingIndex": dict(sorted(findings.items())),
    "captures": captures
}
write("view-receipt.json", receipt)
report = """All 56 assigned originals were directly viewed once at original detail. This review covers filtered direct orders 58–113, from run 34506161751 at commit d06f83aa8f6905be515faf0f58690634714e5a2d, optimized-test-signed at font scale 2.0. Each PNG path, SHA-256, byte size and IHDR dimensions was checked against the frozen plan before viewing and verified again afterward. Every observation is joined to its original in view-receipt.json; the 14 batch files preserve the structured notes.

The overall source case remains unsupported. The receipt preserves 42 capture rows belonging to passed named scopes and 14 belonging to unsupported held-rotation scopes. These are capture counts, not new test outcomes. Original run totals remain 15 passed, 8 unsupported, 72 not-reached and 1 failed across 96 named scopes.

- Portrait selectors, leave confirmations and home views fit with readable text and clear choices. Landscape selector guidance is outside the view in direct orders 71 and 94.
- Public and concealed-hand views often retain a scroll position that places lower content or actions outside the image. Direct order 96 shows only the upper outline of Show hand, with its label below the image; order 93 cuts Challenge Orbit at the lower edge. Order 78 cuts the circular star badge flat at the upper content boundary. Per-original notes retain the other observed edges.
- Landscape native-ready orders 72 and 95 show readiness controls and public claim information, with no table or hand surface in the captured viewport. This does not establish that the renderer is absent or that gameplay succeeded.
- Portrait native 3D orders 82, 88, 105 and 111 show partial table/card backs and seat metadata outside the horizontal viewport, alongside an explicit Swipe seats cue. The table bottom extends below the vertical viewport.
- No private card face or rank was observed in the concealed-hand or native covered-hand stills. First-card and selected captures deliberately show revealed-hand states. Order 70 is a selected-hand state whose readable card identities are outside the captured viewport. Revealed states are not concealment evidence or automatically privacy defects.

The reveal interpretation is bound to the executed smoke-android-godot-session.py source (SHA-256 7e9e1cfeba1676ad82b621597c3d26e9e39355cfcabff563e24cdb118b70d097). Lines 973–984 explicitly tap game-reveal-hand before the first-card image, lines 987–995 select before the selected image, and lines 997–1010 capture concealment and disabled selection before invoking the reveal sequence.

These are observations about retained viewport pixels. They do not prove that offscreen controls are unreachable or that clipping persists after scrolling. No image is evidence of continuous pixel privacy, transition timing, engine gameplay or unobserved actions. Passed scope statuses are inherited unchanged from the outcome matrix; recovery images under unsupported held stages do not establish held-return success. This review produced no app executions, builds, new screenshots, derivatives, video decoding or tracked gallery edits.

The frozen delivery consists of view-receipt.json, identity-check.json, this findings report, all 14 note batches, the completed view ledger, the unchanged assignment and plan snapshot, and the receipt assembly script. Source references retain hashes for the plan, source mapping, evidence freeze, outcome matrix, original case result, prior peer receipt and executed reveal source. Original images remain at their source paths.
"""
(BASE / "findings.md").write_text(report)
local_files = [identity(p) for p in sorted(BASE.rglob("*")) if p.is_file() and p.name not in ("freeze.json", "SHA256SUMS")]
freeze = {
    "schemaVersion": 1, "reviewer": "/root/ui_game", "frozenAtUtc": NOW,
    "status": "complete", "task": "56 assigned direct original still views",
    "actualOriginalViews": 56, "directOrders": expected_orders,
    "files": local_files, "externalSourceReferences": source_refs,
    "originalPngIdentities": original_identities,
    "runtimeOutcomesChanged": False, "trackedFilesEdited": False
}
write("freeze.json", freeze)
digest_entries = [*local_files, identity(BASE / "freeze.json")]
(BASE / "SHA256SUMS").write_text("".join(f'{row["sha256"]}  {Path(row["path"]).relative_to(BASE)}\n' for row in digest_entries))
print(json.dumps({"status": "complete", "records": len(captures), "scopeOutcomeCaptureCounts": scope_counts,
                  "receipt": identity(BASE / "view-receipt.json"), "findings": identity(BASE / "findings.md"),
                  "freeze": identity(BASE / "freeze.json")}, indent=2))

