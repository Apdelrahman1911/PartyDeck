#!/usr/bin/env python3
"""Read retained evidence; write bounded, derived review metadata beside this file."""
import hashlib
import json
import platform
import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "34478720554"
HEAD = "c6ea1dd9f7966517fbee87a06b633d01c432c24d"
PREFIX = "godot-ios-authority-gameplay/artifacts/"
VIDEO = PREFIX + "authority-attachments/856F498D-90C1-48CC-8225-0A35C78305BA.mp4"
ISSUE = PREFIX + "authority-attachments/AF79D284-8E9C-467C-8A1E-0682033E9CE0.txt"
DATABASE = PREFIX + "AuthorityHost.xcresult/database.sqlite3"
LOG = "job-102876625127.log"
EPOCH_OFFSET = 978307200
EXPECTED = {
    VIDEO: "399b9f05d4f06728d0709e16fd80a989ad81299a6985376aac8c62e774b2fa25",
    ISSUE: "2bcf965f26c60b8d66b4ee5eee23a25ecc8b4d46b7752cb41484b3d4c3867bfe",
    DATABASE: "126f56be9263b31d35fe8166c7cabb88a737d6903604a4c87db46c440670ec3c",
    LOG: "736f3ec7ace43d042cb8995b24213b76d80d239ea24d9144c7b72dde8079a7c0",
}


def identity(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def save(name, document):
    path = ROOT / name
    # Existing completed receipts must not be silently replaced by a rerun.
    with path.open("x") as stream:
        json.dump(document, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")


def utc(unix_seconds):
    return datetime.fromtimestamp(unix_seconds, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def converted(raw):
    # Round only the human-readable conversion; retain the original SQLite REAL.
    unix = round(raw + EPOCH_OFFSET, 6)
    return {"sqlite_raw_seconds": raw, "unix_seconds": unix, "utc_milliseconds": utc(round(unix, 3))}


started = datetime.now(timezone.utc).isoformat()
summary_path = SOURCE / "authority-attachment-evidence-summary.json"
summary = json.loads(summary_path.read_text())
assert summary["runId"] == 34478720554 and summary["headSha"] == HEAD
assert summary["sqliteSha256"] == EXPECTED[DATABASE]
test = next(t for t in summary["tests"] if t["runRow"] == 1)
attachment_exports = [a for a in summary["attachments"] if a["testIdentifier"] == test["identifier"]]
assert len(attachment_exports) == 2
source_excerpts = [
    ("source-c6ea1dd/godot/ios-host/AuthorityHostUITests/AuthorityHostUITests.swift", [(1, 27), (113, 129)]),
    ("source-c6ea1dd/godot/ios-host/AuthorityHost/AuthorityHostApp.swift", [(1, 103)]),
    ("source-c6ea1dd/godot/ios-host/AuthorityHost/AuthorityModel.swift", [(1, 62)]),
]
input_names = list(EXPECTED) + [
    "authority-attachment-evidence-summary.json",
    "source-archive.json",
    "collection-evidence-frozen.json",
] + [p for p, _ in source_excerpts]
before = {name: identity(SOURCE / name) for name in input_names}
for name, expected in EXPECTED.items():
    assert before[name]["sha256"] == expected, name

connection_uri = (SOURCE / DATABASE).as_uri() + "?mode=ro"
connection = sqlite3.connect(connection_uri, uri=True)
connection.row_factory = sqlite3.Row
queries = []


def query(name, sql, parameters=()):
    rows = [dict(row) for row in connection.execute(sql, parameters)]
    queries.append({"name": name, "sql": sql, "parameters": list(parameters), "rows": rows})
    return rows


query("relevant_schemas", "SELECT name, sql FROM sqlite_master WHERE name IN ('TestCases', 'TestCaseRuns', 'TestIssues', 'Activities', 'Attachments', 'UserInfos', 'UserInfoKeyValues', 'SourceCodeContexts', 'SourceCodeLocations') ORDER BY name")
cases = query("test_cases", "SELECT rowid, * FROM TestCases WHERE rowid IN (1, 2) ORDER BY rowid")
runs = query("test_case_runs", "SELECT rowid, * FROM TestCaseRuns WHERE rowid IN (1, 2) ORDER BY rowid")
issues = query("failed_case_issues", "SELECT rowid, * FROM TestIssues WHERE testCaseRun_fk = 1 ORDER BY rowid")
tree = """WITH RECURSIVE activity_tree AS (
    SELECT rowid AS activity_rowid, * FROM Activities WHERE testCaseRun_fk = ? {root_limit}
    UNION
    SELECT a.rowid AS activity_rowid, a.* FROM Activities a
      JOIN activity_tree t ON a.parent_fk = t.activity_rowid
) SELECT * FROM activity_tree ORDER BY activity_rowid"""
failed_activities = query("failed_case_complete_activity_tree", tree.format(root_limit=""), (1,))
next_activities = query("next_normal_case_launch_and_first_tap_activity_tree", tree.format(root_limit="AND orderInParent <= 4"), (2,))
failed_ids = [a["activity_rowid"] for a in failed_activities]
placeholders = ",".join("?" for _ in failed_ids)
attachments = query("failed_case_database_attachments", f"SELECT rowid, * FROM Attachments WHERE activity_fk IN ({placeholders}) OR testIssue_fk IN (SELECT rowid FROM TestIssues WHERE testCaseRun_fk = 1) ORDER BY rowid", failed_ids)
query("recording_user_info", "SELECT rowid, * FROM UserInfos WHERE rowid = 1")
user_info = query("recording_user_info_key_values", "SELECT rowid, * FROM UserInfoKeyValues WHERE userInfo_fk = 1 ORDER BY rowid")
query("issue_source_context", "SELECT rowid, * FROM SourceCodeContexts WHERE rowid = 1")
query("issue_source_location", "SELECT rowid, * FROM SourceCodeLocations WHERE rowid = 1")
connection.close()
assert len(failed_activities) == 17
assert len(issues) == 1 and len(attachments) == 1
assert (SOURCE / ISSUE).read_text() == issues[0]["compactDescription"]
assert runs[0]["result"] == "Failure" and runs[1]["result"] == "Success"
failed_synthesis = [a for a in failed_activities if a["title"] == "Synthesize event"]
next_synthesis = [a for a in next_activities if a["title"] == "Synthesize event"]
assert not failed_synthesis and len(next_synthesis) == 1
save("xcresult-readonly-query-results.json", {
    "database": before[DATABASE], "connection_uri": connection_uri,
    "read_only": True, "sqlite_version": sqlite3.sqlite_version,
    "activity_selection": "Recursively includes children whose testCaseRun_fk is null; filtering that column alone omits nested launch/tap activities.",
    "queries": queries,
})

excerpts = []
for name, ranges in source_excerpts:
    lines = (SOURCE / name).read_text().splitlines()
    excerpts.append({"source": before[name], "ranges": [
        {"start_line": first, "end_line": last,
         "lines": [{"line": n, "text": lines[n - 1]} for n in range(first, last + 1)]}
        for first, last in ranges
    ]})
save("archived-source-excerpts.json", {"head_sha": HEAD, "excerpts": excerpts})
log_lines = (SOURCE / LOG).read_text().splitlines()
selected_log_lines = [{"line": n, "text": log_lines[n - 1]} for n in range(2133, 2206)]
selected_log_lines += [{"line": n, "text": line} for n, line in enumerate(log_lines, 1)
                       if "testReferenceMatchIn2D]' passed" in line]
save("retained-log-excerpts.json", {"source": before[LOG], "lines": selected_log_lines,
    "timing_note": "Outer CI timestamps are log arrival/print times and can lag embedded event times; do not equate them with event time."})

manifest = json.loads((ROOT / "decoded-frame-manifest.json").read_text())
assert manifest["original_video"]["sha256"] == EXPECTED[VIDEO]
assert manifest["frame_count"] == 129 and len(manifest["frames"]) == 129
frame_by_number = {frame["index_zero_based"] + 1: frame for frame in manifest["frames"]}
viewed = [
    (1, "iOS Home; clock 12:59; AuthorityHostUI... runner icon."),
    (2, "iOS Home; clock 1:00."),
    (129, "Full Authority chooser, Play in 2D / Play in 3D, Sound, repeatable scenario, Idle."),
    (3, "iOS Home; new LastLightComp... icon visible at right."),
    (25, "Expanding white app window over blurred Home; opening transition."),
    (60, "Blank white full app view with iOS status bar and home indicator."),
    (100, "Full Authority chooser and Idle."),
    (72, "Blank white full app view with iOS status bar and home indicator."),
    (73, "Faint Authority chooser during fade-in; Play in 2D / Play in 3D, Sound, repeatable scenario and Idle visible."),
]
viewed_frames = [{**frame_by_number[number], "observation": observation,
                  "view_order": order, "individual_view_timestamp": None}
                 for order, (number, observation) in enumerate(viewed, 1)]
save("viewed-frames.json", {
    "run_id": 34478720554, "head_sha": HEAD, "original_video": before[VIDEO],
    "decoded_frame_manifest": identity(ROOT / "decoded-frame-manifest.json"),
    "viewed_frame_count": len(viewed_frames), "frames": viewed_frames,
    "publication_queue_recipient": "/root/review_design",
    "publication_queue_status": "All nine exact paths, PTS values and SHA-256 hashes sent by collaboration messages; final frozen manifest to follow. Publication review pending.",
    "classification": "Derived frames from an original CI video, not original CI PNG attachments; chooser visibility does not qualify native gameplay or 200-percent renderer behavior.",
    "transform": manifest["transform"],
    "view_tool": "tools.view_image; the preserved PNGs retain full 1206 x 2622 resolution; the tool may scale its display.",
    "time_note": "Original frame PTS is retained exactly. Per-image inspection wall-clock timestamps were not individually recorded."
})

start = min(a["startTime"] for a in failed_activities)
recording_timestamp = attachments[0]["timestamp"]
probe = json.loads((ROOT / "decoder/ffprobe-container.stdout").read_text())
creation_text = probe["format"]["tags"]["creation_time"]
creation_unix = datetime.fromisoformat(creation_text.replace("Z", "+00:00")).timestamp()
candidate_origins = {
    "mp4_creation_metadata_if_used_as_pts_zero": creation_unix,
    "recording_attachment_timestamp_if_used_as_pts_zero": recording_timestamp + EPOCH_OFFSET,
}
activity_timeline = [{"activity_rowid": a["activity_rowid"], "title": a["title"],
    "parent_fk": a["parent_fk"], "start": converted(a["startTime"]),
    "finish": converted(a["finishTime"]),
    "seconds_after_test_start": round(a["startTime"] - start, 6),
    "failure_ids": a["failureIDs"]} for a in failed_activities]
save("timeline.json", {
    "timestamp_conversion": {"sqlite_reference_epoch": "2001-01-01T00:00:00Z",
        "unix_offset_seconds": EPOCH_OFFSET,
        "corroboration": "Converted first activity matches its embedded 2026-09-10 12:58:59.472 title; recording attachment conversion matches the collector's Unix export timestamp 1789045142.094.",
        "precision": "Raw SQLite REAL values retained; readable UTC rounded to milliseconds."},
    "issue": {"uuid": issues[0]["uuid"], "time": converted(issues[0]["timestamp"]),
        "seconds_after_recording_attachment_timestamp": round(issues[0]["timestamp"] - recording_timestamp, 6)},
    "recording_attachment": converted(recording_timestamp),
    "mp4_creation_time": creation_text,
    "origin_metadata_difference_seconds": round(recording_timestamp + EPOCH_OFFSET - creation_unix, 6),
    "recording_user_info": user_info,
    "absolute_video_origin_status": "Unresolved: attachment metadata has orientation and scale but no explicit PTS-zero wall-clock mapping. These two metadata values are candidate origins, not proven timing bounds.",
    "activities": activity_timeline,
    "viewed_frame_candidate_alignments": [{"file": f["file"],
        "pts_time_seconds": f["original_video_frame"]["pts_time"],
        "conditional_utc_by_origin": {name: utc(round(origin + float(f["original_video_frame"]["pts_time"]), 3))
                                     for name, origin in candidate_origins.items()}}
        for f in viewed_frames],
    "failed_case_synthesize_event_count": len(failed_synthesis),
    "next_normal_case_first_tap_synthesize_event_count": len(next_synthesis),
    "inference_limit": "Tap is an attempted XCTest action. Missing synthesis does not prove no event reached the app. Late chooser visibility is supported; native scene entry, delivered tap, OS root cause and a justified implementation fix are not established."
})

total_bytes = 0
for frame in manifest["frames"]:
    path = ROOT / frame["file"]
    actual = identity(path)
    assert actual["sha256"] == frame["sha256"] and actual["bytes"] == frame["bytes"], path
    with path.open("rb") as stream:
        header = stream.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", header[16:24]) == (1206, 2622)
    total_bytes += actual["bytes"]
after = {name: identity(SOURCE / name) for name in input_names}
assert before == after
save("inspection-checks.json", {
    "original_input_identities_unchanged_during_export": before == after,
    "expected_original_video_issue_database_log_hashes_match": True,
    "issue_export_exactly_matches_database_description": True,
    "failed_case_complete_activity_tree_count": len(failed_activities),
    "failed_case_database_attachment_count": len(attachments),
    "failed_case_ci_export_count": len(attachment_exports),
    "ci_export_note": "One database video attachment plus the CI-exported issue text; the issue text has no database Attachments row or export timestamp.",
    "failed_case_synthesize_event_count": len(failed_synthesis),
    "next_normal_case_first_tap_synthesize_event_count": len(next_synthesis),
    "all_129_decoded_png_hashes_sizes_dimensions_verified": True,
    "decoded_png_bytes": total_bytes, "viewed_frame_count": len(viewed_frames),
    "native_tests_or_builds_executed_by_this_review": False,
})
save("input-provenance.json", {
    "run_id": 34478720554, "head_sha": HEAD, "source_root": str(SOURCE),
    "review_root": str(ROOT), "started_utc": started,
    "finished_utc": datetime.now(timezone.utc).isoformat(),
    "python_version": platform.python_version(),
    "script": identity(Path(__file__)), "original_inputs": before,
    "original_inputs_after_export": after,
    "collector_test_summary": test, "collector_exported_attachments": attachment_exports,
    "source_archive_receipt": json.loads((SOURCE / "source-archive.json").read_text()),
    "scope": "Read-only inspection of retained evidence plus derived frame/metadata storage. No source edits, Git, native build/test, new CI collection, retries or deadline changes."
})
print(json.dumps({"status": "complete", "output_root": str(ROOT),
    "failed_case_activities": len(failed_activities), "viewed_frames": len(viewed_frames),
    "verified_decoded_frames": len(manifest["frames"]), "decoded_png_bytes": total_bytes}))
