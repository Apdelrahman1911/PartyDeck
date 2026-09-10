#!/usr/bin/env python3
"""Consolidate preserved Android CI evidence; never execute app/test/build tools."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parents[1]
NATIVE = OUT / "extracted/10144559609-android-jvm-reports/build/ci/android"
COMMIT = "dad1c11741bd4322bb8b2afb9f18f3db5f50c919"


def read(path):
    return json.loads(Path(path).read_text())


def evidence(path):
    path = Path(path).resolve()
    content = path.read_bytes()
    return {"path": str(path), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def contained(bounds, viewport):
    return (viewport[0] <= bounds[0] < bounds[2] <= viewport[2]
            and viewport[1] <= bounds[1] < bounds[3] <= viewport[3])


def point_inside(point, bounds):
    return bounds[0] <= point[0] < bounds[2] and bounds[1] <= point[1] < bounds[3]


def save(name, value):
    path = OUT / "review" / name
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")
    return evidence(path)


expected_receipts = {
    "artifact-download-receipt.json": "0a88b93ae662e2d77cef895ca67fffbe84a4c5ed2eb665e79f74572d3c801d91",
    "review/test-xml-audit.json": "664506c168d690315e67f23b1f92c54c3595de76ede2fd36f4f8c3736a34ad1f",
    "review/package-audit.json": "69266777e7037cbe15f00de98b359d8124a943e166ee8ad4cc0fd96ff1800f8a",
    "review/original-native-image-inventory.json": "d17286ee6cd1cae4861c015b3ca22bc6f6d63fee0a246f68dd0f61076ed0c916",
}
for relative, expected in expected_receipts.items():
    assert evidence(OUT / relative)["sha256"] == expected, relative
collection = read(OUT / "artifact-download-receipt.json")
tests = read(OUT / "review/test-xml-audit.json")
packages = read(OUT / "review/package-audit.json")
images = read(OUT / "review/original-native-image-inventory.json")
job = read(tests["job_metadata"])
assert all(item["commit"] == COMMIT for item in [collection, tests, packages])
assert job["head_sha"] == COMMIT and job["id"] == 102803833812
assert job["run_id"] == 34456441354 and job["conclusion"] == "success"
assert tests["result"] == packages["result"] == "pass"
assert evidence(collection["job_log"]["path"])["sha256"] == collection["job_log"]["sha256"]

runtime = read(NATIVE / "runtime-variants.json")
display = read(NATIVE / "display-configuration.json")
preparation = read(NATIVE / "preparation/preparation-result.json")
assert runtime["passed"] and runtime["sameEmulatorBoot"]
assert runtime["debugExitCode"] == runtime["optimizedTestSignedExitCode"] == 0
assert runtime["godotSessionSmoke"]["requested"] is False
assert display["actualAndroidApi"] == 35 and display["guestApiVerified"] and display["displayVerified"]
assert (NATIVE / "android-api.log").read_text().strip() == "35"
assert display["expectedPhysicalSize"] == [720, 1600] and display["expectedDensityDpi"] == 280
assert preparation["passed"] and not preparation["reboot_attempted"]
assert len(preparation["attempts"]) == 1
assert preparation["attempts"][0]["passed"] and preparation["attempts"][0]["app_absent"]
image_index = {str(Path(item["path"]).resolve()): item for item in images["original_images"]}
assert len(image_index) == 63 and images["all_originals_decoded_and_720x1600"]
assert set(image_index) == {str(path.resolve()) for path in NATIVE.rglob("*.png")}
expected_routes = [line for line in (OUT / "review/expected-routes.txt").read_text().splitlines() if line]
assert len(expected_routes) == 30
variants = {}
route_pngs = set()
for variant in ["debug", "optimized-test-signed"]:
    folder = NATIVE / variant
    smoke = read(folder / "smoke-result.json")
    assert smoke["passed"] and smoke["variant"] == variant
    assert smoke["apk_sha256"] == packages["packages"][variant]["artifact"]["sha256"]
    assert not [key for key in smoke if re.search(r"error|failure|diagnostic", key, re.I)]
    observations = smoke["observations"]
    assert set(observations["screenshots"]) == set(expected_routes)
    assert observations["large_text_font_scale"] == 2.0
    assert observations["played_card"] == "hand decreased by one"
    assert observations["persisted_switches"] == {
        "settings-sound": False, "settings-haptics": False, "settings-reduce-motion": True}
    assert observations["soft_ime_captures"] == ["join-name-soft-ime", "large-text-join-name-soft-ime"]
    pairs = []
    for route in expected_routes:
        png, xml = folder / (route + ".png"), folder / (route + ".xml")
        tree = ET.parse(xml).getroot()
        nodes = sum(1 for _ in tree.iter("node"))
        assert tree.tag == "hierarchy" and nodes > 0
        png_ref = evidence(png)
        assert png_ref["sha256"] == image_index[str(png.resolve())]["sha256"]
        pairs.append({"route": route, "png": png_ref, "xml": evidence(xml), "xml_node_count": nodes})
        route_pngs.add(str(png.resolve()))
    geometry = [json.loads(line) for line in (folder / "input-geometry.log").read_text().splitlines()]
    for row in geometry:
        bounds, viewport, coordinates = row["bounds"], row["viewport"], row["coordinates"]
        assert row["display_size"] == [720, 1600] and row["rotation"] == 0
        assert contained(viewport, [0, 0, 720, 1600])
        if row["action"] == "tap":
            point = [coordinates["x"], coordinates["y"]]
            assert contained(bounds, viewport) and point_inside(point, bounds) and point_inside(point, viewport)
        else:
            assert row["action"] == "swipe"
            assert all(point_inside(coordinates[end], viewport) for end in ["start", "end"])
    assert [row["label"] for row in geometry if row["action"] == "tap"] == [
        step[7:] for step in smoke["steps"] if step.startswith("Tapped ")]
    rules_taps = [row.copy() for row in geometry if row["label"] == "rules-practice"]
    assert [row["stage"] for row in rules_taps] == ["rules", "large-text-rules"]
    for row in rules_taps:
        b, v = row["bounds"], row["viewport"]
        row["minimum_viewport_clearance_px"] = min(b[0] - v[0], b[1] - v[1], v[2] - b[2], v[3] - b[3])
        assert row["minimum_viewport_clearance_px"] >= 8
    variants[variant] = {
        "passed": True, "smoke_receipt": evidence(folder / "smoke-result.json"),
        "actual_apk": packages["packages"][variant]["artifact"], "apk_hash_matches_smoke": True,
        "input_geometry_log": evidence(folder / "input-geometry.log"),
        "input_record_count": len(geometry), "input_actions": dict(Counter(row["action"] for row in geometry)),
        "all_input_geometry_valid": True, "tap_steps_match_geometry_in_order": True,
        "rules_practice_taps": rules_taps, "route_pairs": pairs,
        "persisted_switches": observations["persisted_switches"], "played_card": observations["played_card"],
        "large_text_font_scale": observations["large_text_font_scale"],
        "soft_ime_logs": [evidence(folder / (route + "-input-method.log")) for route in observations["soft_ime_captures"]],
        "error_diagnostic_restore_failure_fields": [],
    }
assert [variants[key]["input_record_count"] for key in variants] == [67, 64]
crash_pattern = r"FATAL EXCEPTION|\bFatal signal\b|\bANR in dev\.partydeck\.app\b|\bam_anr\b.*dev\.partydeck\.app|\bam_crash\b.*dev\.partydeck\.app"
logs = sorted(NATIVE.rglob("*.log"))
crash_matches = [{"path": str(path), "line": number} for path in logs
                 for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1)
                 if re.search(crash_pattern, line, re.I)]
failure_files = [str(path) for path in NATIVE.rglob("*") if path.is_file()
                 and re.search(r"failure|error|invalid[-_]screencap", path.name, re.I)]
assert not crash_matches and not failure_files
native = {
    "result": "pass", "run_id": 34456441354, "job_id": 102803833812, "commit": COMMIT,
    "created_utc": datetime.now(timezone.utc).isoformat(), "builder": evidence(__file__),
    "runtime_variants": {"evidence": evidence(NATIVE / "runtime-variants.json"), "content": runtime},
    "display": {"evidence": evidence(NATIVE / "display-configuration.json"), "content": display,
                "raw_api_evidence": evidence(NATIVE / "android-api.log")},
    "preparation": {"evidence": evidence(NATIVE / "preparation/preparation-result.json"), "content": preparation},
    "variants": variants, "route_png_xml_pair_count": 60, "original_png_count": 63, "input_record_count": 131,
    "non_route_pngs": [image_index[path] for path in sorted(set(image_index) - route_pngs)],
    "image_inventory": evidence(OUT / "review/original-native-image-inventory.json"),
    "visual_review": {
        "completed_in_prior_segment_of_this_independent_review": True, "route_images_inspected": 60,
        "paired_contact_sheets_inspected": 10, "blocking_findings": [],
        "findings": ["Rules practice CTA readable and fully visible at normal and 200% text in both variants.",
                     "Join focused name field and soft keyboard visible at normal and 200% text in both variants.",
                     "Large hand, selection and play action reachable by scrolling."],
        "limits": ["Intermediate scroll captures can clip viewport-edge content; simultaneous fit is not asserted.",
                   "Practice-after-play can show a subsequent bot-driven round result; native Next Round is not specifically qualified.",
                   "Live invitation/QR and Sharesheet images intentionally omitted by pinned harness; geometry and steps preserve those flows."]},
    "crash_log_scan": {"pattern": crash_pattern, "files": [evidence(path) for path in logs], "matches": crash_matches},
    "failure_or_capture_error_files": failure_files,
    "package_audit": evidence(OUT / "review/package-audit.json"), "originals_modified": False,
    "reviewer_execution": "Read-only preserved-evidence inspection and derived receipt generation; no app, device, Godot, build or test reruns."
}
native_ref = save("native-runtime-audit.json", native)
renderer_reports = [report for report in tests["reports"] if report["module"] == "androidRenderer"]
final = {
    "verdict": "PASS", "blocking_findings": [], "created_utc": datetime.now(timezone.utc).isoformat(),
    "repository": collection["repository"], "workflow": "Validate", "run_id": 34456441354,
    "job_id": 102803833812, "commit": COMMIT, "job_conclusion": "success", "job_url": job["html_url"],
    "job_metadata": evidence(tests["job_metadata"]), "original_job_log": collection["job_log"],
    "tests": {"xml_suites": tests["report_count"], "totals": tests["totals"], "module_counts": tests["module_counts"],
              "all_38_xml_timestamps_within_this_build_step": tests["xml_timestamps_within_current_build_step"] == 38,
              "renderer_17_case_ids_match_prior_independent_baseline": tests["runtime_library_17_case_ids_match_prior_independent_baseline"],
              "renderer_suites": [{"suite": report["suite"], "cases": [case["name"] for case in report["cases"]]} for report in renderer_reports],
              "separate_python_checker_tests": 36, "separate_checker_log_evidence": tests["separate_python_checker_log_summaries"]},
    "packages": {key: value["artifact"] for key, value in packages["packages"].items()},
    "optimized_package_lineage": {
        "all_550_unsigned_release_payload_entries_unchanged": packages["optimized_runtime_all_unsigned_payload_bytes_unchanged"] and packages["compared_unsigned_payload_count"] == 550,
        "added_signature_entries": packages["runtime_extra_signature_entries"],
        "disposable_certificate_sha256": packages["packages"]["optimized-test-signed"]["signer_certificate_sha256"][0],
        "not_debuggable": packages["optimized_apk_is_not_debuggable"], "distribution_signed": False,
        "signature_and_16kib_alignment_verified": True,
        "debug_dex_class_count": 33018, "release_dex_class_count": 4509,
        "same_reviewed_pck_in_all_four_archives": packages["same_reviewed_adaptive_pck_in_all_four_archives"],
        "pck": packages["packages"]["debug"]["pck"]},
    "native_runtime": {"android_api": 35, "display_px": [720, 1600], "density_dpi": 280,
                       "same_emulator_boot": True, "debug_passed": True, "optimized_test_signed_passed": True,
                       "actual_apk_hashes_match_smoke_receipts": True, "preparation_first_attempt_passed_without_reboot": True,
                       "route_png_xml_pairs": 60, "original_pngs": 63, "input_records": 131,
                       "normal_and_200_percent_text_reviewed": True, "receipt": native_ref},
    "qualified_routes": ["Home", "Rules Back, readable practice CTA, direct practice entry and confirmed return Home",
                         "Three settings survive actual force-stop/relaunch",
                         "Practice reveal/select/hide, background concealment, accepted one-card play and leave",
                         "Local host creation, invitation QR/copy, Sharesheet cancellation and teardown",
                         "Invalid Join feedback, edit recovery, name preservation and Back",
                         "200% text Home, Rules, Settings, Join with soft keyboard, hand selection and play-action reachability"],
    "qualification_limits": ["Android job 102803833812 at dad1c11741bd4322bb8b2afb9f18f3db5f50c919 only; no verdict on the whole workflow, iOS or API 36.",
                             "Godot chooser remains unadvertised in pinned sources and Godot session smoke was disabled; no native Godot-session or renderer gameplay qualification.",
                             "Single-emulator shell UI and local hosting; physical LAN, camera frames and distribution signing are outside this evidence.",
                             "QR/Sharesheet flow qualified from original steps and input geometry; their live images were intentionally excluded.",
                             "Scroll reachability is qualified, not simultaneous fit of every control; native Next Round was not specifically qualified."],
    "original_artifacts": collection["artifacts"],
    "receipt_references": [evidence(OUT / path) for path in expected_receipts] + [evidence(OUT / "source/source-receipt.json"), native_ref],
    "preservation": {"workspace_evidence_root": str(OUT), "tmp_symlink": "/tmp/partydeck-android-production-native-34456441354",
                     "original_archives_logs_screenshots_preserved": True,
                     "download_resume_was_transfer_recovery_not_ci_failure": True},
    "reviewer_execution": "Independent read-only XML, package, native-log and screenshot audit; no build/test/app/device/Godot reruns, CI dispatch, source edits or Git mutations."
}
final_ref = save("final-native-review-receipt.json", final)
print(json.dumps({"native_receipt": native_ref, "final_receipt": final_ref, "verdict": "PASS", "blocking_findings": []}, indent=2))
