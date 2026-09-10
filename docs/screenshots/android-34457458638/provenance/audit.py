#!/usr/bin/env python3
"""Audit retained API36 evidence without running the app, checker, or build."""

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import struct


RUN = Path(__file__).resolve().parent
WORK = RUN.parent
ANDROID = RUN / "android-jvm-reports/build/ci/android"
EXPECTED_SHA = "f11f92ed4ec4f91630396bf493ba2fd984f07bb9"
checks = []
evidence = []


def identity(path):
    raw = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def record(path):
    value = identity(path)
    evidence.append(value)
    return value


def load(path):
    record(path)
    return json.loads(path.read_text())


def require(name, passed):
    checks.append({"name": name, "passed": bool(passed)})


run = load(RUN / "run.json")
jobs = load(RUN / "jobs.json")
download = load(RUN / "artifact-download.json")
job = next(item for item in jobs["jobs"] if item["name"] == "Android and shared JVM tests")
require("Exact dispatched run and revision succeeded", run["id"] == 34457458638 and run["head_sha"] == EXPECTED_SHA and run["conclusion"] == "success")
require("Android job succeeded on ubuntu-24.04", job["id"] == 102807084425 and job["head_sha"] == EXPECTED_SHA and job["labels"] == ["ubuntu-24.04"] and job["conclusion"] == "success")
require("Reports ZIP identity and integrity were verified during collection", download["matches_published_digest"] and download["zip_crc_check_passed"] and download["downloaded_sha256"] == "b92ec1d1b6f546d8b9c4d1a5cf7b1f23f901306df820a84aef2c9795868e8bea")
job_log_path = RUN / "android-job.log"
record(job_log_path)
job_log = job_log_path.read_text()
require("Logged checkout and API36/session-disabled inputs match", EXPECTED_SHA in job_log and "PARTYDECK_ANDROID_API: 36" in job_log and "PARTYDECK_ANDROID_GODOT_SESSION_SMOKE: 0" in job_log)

texts = {}
for name in ("host-cpu.log", "host-memory-before-emulator.log", "acceleration.log", "system-image-source.log", "android-api.log", "emulator.log", "avd-config.log"):
    path = ANDROID / name
    record(path)
    texts[name] = path.read_text()
cpu_count = int(re.search(r"^CPU\(s\):\s+(\d+)", texts["host-cpu.log"], re.M).group(1))
cpu_model = re.search(r"^Model name:\s+(.+)", texts["host-cpu.log"], re.M).group(1)
memory_mib = int(re.search(r"^Mem:\s+(\d+)", texts["host-memory-before-emulator.log"], re.M).group(1))
properties = dict(line.split("=", 1) for line in texts["system-image-source.log"].splitlines() if "=" in line)
require("Four actual host CPUs and 16 GB class RAM are present", cpu_count == 4 and memory_mib == 15989)
require("KVM acceleration is installed and usable", "KVM (version 12) is installed and usable." in texts["acceleration.log"])
require("Expected stable emulator and swangle backend executed", "Android emulator version 37.1.11.0 (build_id 15917651)" in texts["emulator.log"] and "gles_mode_selected:swangle" in texts["emulator.log"])
require("Official full API36 x86_64 revision 2 image is recorded", properties.get("AndroidVersion.ApiLevel") == "36" and properties.get("Pkg.Revision") == "2" and properties.get("SystemImage.Abi") == "x86_64" and properties.get("SystemImage.TagId") == "default")
display = load(ANDROID / "display-configuration.json")
require("Actual guest API36 and required display were verified", texts["android-api.log"].strip() == "36" and display["actualAndroidApi"] == display["expectedAndroidApi"] == 36 and display["guestApiVerified"] and display["displayVerified"] and display["expectedPhysicalSize"] == [720, 1600] and display["expectedDensityDpi"] == 280)

preparation = load(ANDROID / "preparation/preparation-result.json")
require("Empty API36 AVD passed first boot without recovery", preparation["passed"] and not preparation["reboot_attempted"] and len(preparation["attempts"]) == 1 and preparation["attempts"][0]["passed"] and preparation["attempts"][0]["app_absent"] and preparation["attempts"][0]["android_api"] == "36")
require("Preparation diagnostics and restoration succeeded", all(not preparation["attempts"][0].get(key) for key in ("error", "diagnostic_errors", "environment_restore_errors")))

runtime = load(ANDROID / "runtime-variants.json")
require("Both APK checks passed on the prepared emulator", runtime["passed"] and runtime["sameEmulatorBoot"] and runtime["debugExitCode"] == runtime["optimizedTestSignedExitCode"] == 0)
require("Native Godot session opt-in was not exercised", runtime["godotSessionSmoke"]["requested"] is False and runtime["godotSessionSmoke"]["debugPhaseExitCode"] is None and runtime["godotSessionSmoke"]["optimizedTestSignedPhaseExitCode"] is None)
variants = {}
screenshots = []
for variant in ("debug", "optimized-test-signed"):
    result = load(ANDROID / variant / "smoke-result.json")
    observations = result["observations"]
    require(f"{variant}: complete 86-step receipt passed without diagnostic/restoration errors", result["passed"] and len(result["steps"]) == 86 and all(not result.get(key) for key in ("error", "diagnostic_errors", "environment_restore_errors")))
    require(f"{variant}: standard and 200% text with real soft-IME captures recorded", observations["large_text_font_scale"] == 2.0 and observations["soft_ime_captures"] == ["join-name-soft-ime", "large-text-join-name-soft-ime"])
    verified_images = []
    for name, dimensions in observations["screenshots"].items():
        path = ANDROID / variant / f"{name}.png"
        raw = path.read_bytes()
        if raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
            raise ValueError(f"Reported screenshot lacks a PNG/IHDR header: {path}")
        width, height = struct.unpack(">II", raw[16:24])
        verified_images.append([width, height] == [dimensions["width"], dimensions["height"]] == [720, 1600])
        screenshots.append({"variant": variant, "stage": name, "width": width, "height": height, **identity(path)})
    require(f"{variant}: all 30 reported stage captures exist with matching dimensions", len(verified_images) == 30 and all(verified_images))
    variants[variant] = {
        "passed": result["passed"], "recorded_steps": len(result["steps"]),
        "apk_sha256_from_executed_input_receipt": result["apk_sha256"],
        "ready_stage_captures": len(verified_images),
        "all_png_files": len(list((ANDROID / variant).glob("*.png"))),
        "font_scale": observations["large_text_font_scale"],
        "soft_ime_captures": observations["soft_ime_captures"],
        "played_card_observation": observations["played_card"],
    }

package = load(ANDROID / "packages/runtime-package.json")
require("Optimized executed-input hash matches disposable signing receipt", variants["optimized-test-signed"]["apk_sha256_from_executed_input_receipt"] == package["runtimeApkSha256"] and package["signingIdentity"] == "disposable-ci-test-key" and package["distributionSigned"] is False)
patterns = re.compile(r"ANR in|FATAL EXCEPTION|Fatal signal [0-9]|am_anr|am_crash", re.I)
diagnostic_scan = []
for directory in ("preparation", "debug", "optimized-test-signed"):
    for path in sorted((ANDROID / directory).rglob("*.log")):
        lines = path.read_text(errors="replace").splitlines()
        matches = [{"line": number, "text": text} for number, text in enumerate(lines, 1) if patterns.search(text)]
        diagnostic_scan.append({**record(path), "matches": matches})
require("No retained ANR/fatal exception/fatal signal markers in collected diagnostic logs", all(not item["matches"] for item in diagnostic_scan))
require("Actions log reports both completed APK flows", "Android debug runtime flows passed." in job_log and "Android optimized-test-signed runtime flows passed." in job_log and "AVD prepared; strict debug and optimized APK acceptance can begin." in job_log)
source = WORK / "checkpoint-source/androidApp/build.gradle.kts"
record(source)
require("Checkpoint app targets API36", "targetSdk = 36" in source.read_text())

(RUN / "screenshot-identities.json").write_text(json.dumps(screenshots, indent=2) + "\n")
(RUN / "diagnostic-marker-scan.json").write_text(json.dumps(diagnostic_scan, indent=2) + "\n")
(RUN / "runtime-evidence-identities.json").write_text(json.dumps(evidence, indent=2) + "\n")
recorded = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "status": "api36_baseline_runtime_evidence_pass" if all(item["passed"] for item in checks) else "audit_failed",
    "run_id": run["id"], "run_url": run["html_url"], "head_sha": EXPECTED_SHA,
    "job_id": job["id"], "checks_passed": sum(item["passed"] for item in checks),
    "checks_failed": sum(not item["passed"] for item in checks), "checks": checks,
    "research_receipt": identity(WORK / "research-receipt.json"),
    "checkpoint_sources": identity(WORK / "checkpoint-source.json"),
    "reports_archive": identity(RUN / "android-jvm-reports.zip"),
    "hardware": {"cpus": cpu_count, "memory_mib": memory_mib, "cpu_model": cpu_model, "kvm_usable": True},
    "runner_image": "20260831.293.1",
    "image_properties": properties, "display": display,
    "emulator_boot_ms": int(re.search(r"Boot completed in (\d+) ms", texts["emulator.log"]).group(1)),
    "preparation": {"passed": preparation["passed"], "attempts": len(preparation["attempts"]), "reboot_attempted": preparation["reboot_attempted"], "app_absent": preparation["attempts"][0]["app_absent"]},
    "variants": variants, "godot_session_requested": False,
    "diagnostics": {"log_files_scanned": len(diagnostic_scan), "matching_marker_count": sum(len(item["matches"]) for item in diagnostic_scan), "patterns": patterns.pattern, "scope": "Retained collected logs only. Generic crash_dump seccomp-policy warnings are not runtime crash events; no clean-driver-log or exhaustive-history claim."},
    "evidence_manifest": identity(RUN / "runtime-evidence-identities.json"),
    "screenshot_manifest": identity(RUN / "screenshot-identities.json"),
    "diagnostic_scan": identity(RUN / "diagnostic-marker-scan.json"),
    "source_classification": "The two-CPU API36 preparation failures remain valid historical infrastructure failures. The larger public Linux allocation now has an executed passing API36 baseline at the recorded checkpoint. The current run used the same runner image version as the previous API36 failure; CPU count is not asserted as a uniquely isolated cause.",
    "acceptance_scope": "Existing single-emulator debug and disposable-test-signed optimized application flows at standard and 200% text, including rules, settings persistence, practice privacy/background/play, local hosting/share teardown, invalid-Join recovery and soft keyboard checks.",
    "limits": [
        "Godot session smoke was explicitly disabled; this run does not qualify API36 native Godot presentation gameplay or renderer lifecycle.",
        "The full 474 MB package artifact was not downloaded by this bounded audit. APK identities above are the hashes from the actual executed-input and signing receipts; the optimized hashes agree. Package-byte reinspection is separate.",
        "Screenshot file identities and PNG dimensions were checked; this task did not independently perform a visual/accessibility review of every image.",
        "Physical-device, mixed-device LAN, camera-frame, distribution-signing and store qualification are outside this run.",
        "The researcher performed read-only status/artifact/source analysis. Root dispatched CI; no repository, workflow or acceptance change was made by this audit.",
    ],
}
(RUN / "final-receipt.json").write_text(json.dumps(recorded, indent=2) + "\n")
print(json.dumps({"status": recorded["status"], "passed": recorded["checks_passed"], "failed": recorded["checks_failed"], "receipt": identity(RUN / "final-receipt.json"), "failed_checks": [item for item in checks if not item["passed"]]}, indent=2))
raise SystemExit(0 if not recorded["checks_failed"] else 1)
