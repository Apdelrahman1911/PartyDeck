#!/usr/bin/env python3
"""Record real retained-engine build/test outcomes, including incomplete failures."""

import datetime
import hashlib
import json
from pathlib import Path
import re
import sys


EXPECTED = {
    "testRepeated2DAnd3DKeepOneDormantEngine",
    "testActiveAndDormantBackgroundTransitionsStayConcealed",
    "testStaleFirstReadyAndCloseCompletionReentry",
}


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def read(path: Path) -> str:
    return path.read_text(errors="replace") if path.is_file() else ""


def read_object(path: Path, problems: list, label: str) -> tuple:
    checksum = None
    try:
        data = path.read_bytes()
        checksum = hashlib.sha256(data).hexdigest()
        value = json.loads(data)
    except (OSError, ValueError, RecursionError) as error:
        problems.append(f"{label} could not be read as JSON: {error}")
        return {}, checksum
    if not isinstance(value, dict) or not value:
        problems.append(f"{label} must be a nonempty JSON object.")
        return {}, checksum
    return value, checksum


def main() -> None:
    stage = sys.argv[1]
    evidence, executable = map(Path, sys.argv[2:4])
    command_exit = int(sys.argv[4])
    if stage not in {"build", "test"}:
        raise SystemExit("Expected build or test stage.")
    root = Path(__file__).resolve().parent
    problems = []
    inputs, inputs_sha256 = read_object(evidence / "inputs.json", problems, "Build input metadata")
    sources = inputs.get("sources", {})
    valid_sources = isinstance(sources, dict) and bool(sources) and all(
        isinstance(name, str) and bool(name) and "\0" not in name and not Path(name).is_absolute()
        and ".." not in Path(name).parts and isinstance(checksum, str)
        and re.fullmatch(r"[0-9a-f]{64}", checksum)
        for name, checksum in sources.items()
    )
    after = {}
    if valid_sources:
        for name in sources:
            try:
                after[name] = digest(root / name) if (root / name).is_file() else None
            except OSError as error:
                after[name] = None
                problems.append(f"Could not recheck compiled source {name}: {error}")
    else:
        problems.append("Build input sources must map relative source paths to SHA-256 strings.")
    if not sources or sources != after:
        problems.append("The actual compiled source inputs were missing or changed during the run.")
    verified_inputs = inputs.get("verified_engine_framework_pack")
    if not isinstance(verified_inputs, dict) or not verified_inputs:
        problems.append("A receipt-matched engine, Kotlin framework and pack were not staged.")
    built = "** BUILD SUCCEEDED **" in read(evidence / "build.log") and executable.is_file()
    symbols = read(evidence / "symbols.log")
    defined = {fields[-1] for line in symbols.splitlines()
               if len(fields := line.split()) >= 3 and fields[-2] in set("TtSsDdBbRr")}
    required = {"_main", "_OBJC_CLASS_$_PDGodotEngineOwner", "_OBJC_CLASS_$_PDGodotPresentation",
                "_OBJC_CLASS_$_PDGBIosQualificationFactory", "_OBJC_CLASS_$_PDGBIosQualificationAuthority"}
    linked = required <= defined and "godot_swift_module10SwiftUIApp" not in symbols
    if not built or not linked:
        problems.append("The linked Swift harness and actual native/Kotlin owners were not all verified.")
    log = read(evidence / "test.log")
    prefix = r"^Test Case '-\[RetainedHostUITests\.RetainedHostUITests (test\w+)\]' "
    started = re.findall(prefix + r"started\.$", log, re.MULTILINE)
    finished = re.findall(prefix + r"(passed|failed|skipped) \((\d+(?:\.\d+)?) seconds\)\.$", log, re.MULTILINE)
    all_passed = set(started) == EXPECTED and len(started) == len(EXPECTED) and \
        {name for name, _, _ in finished} == EXPECTED and len(finished) == len(EXPECTED) and \
        all(status == "passed" for _, status, _ in finished) and "** TEST SUCCEEDED **" in log
    if stage == "test" and not all_passed:
        problems.append("The three actual retained-engine XCTest cases did not each finish with a pass.")
    test_evidence = {}
    if stage == "test":
        artifacts = evidence.parent / "artifacts"
        bundle = artifacts / "RetainedHost.xcresult"
        bundle_retained = bundle.is_dir() and any(bundle.iterdir())
        attachments = [file.relative_to(artifacts).as_posix()
                       for file in sorted((artifacts / "attachments").rglob("*"))
                       if file.is_file() and file.stat().st_size > 0]
        exports, exports_sha256 = read_object(evidence / "test-evidence-export.json", problems, "Native test evidence export metadata")
        _, summary_sha256 = read_object(evidence / "test-summary.json", problems, "XCResult test summary")
        if not bundle_retained:
            problems.append("The native test XCResult bundle was not retained.")
        if not attachments:
            problems.append("The native test attachment export was not retained.")
        for name in ("attachments_export_exit_code", "summary_export_exit_code"):
            if type(exports.get(name)) is not int or exports[name] != 0:
                problems.append(f"Native test evidence export did not succeed: {name}.")
        test_evidence = {
            "xcresult_retained": bundle_retained, "attachment_files": attachments,
            "export_commands": exports, "export_metadata_sha256": exports_sha256,
            "summary_sha256": summary_sha256,
        }
    if command_exit != 0:
        problems.append(f"The native runner or evidence export returned exit code {command_exit}.")
    qualified = stage == "test" and all_passed and not problems
    result = {
        "stage": "retained_engine_lifecycle_execution" if stage == "test" else "retained_host_swift_link",
        "recorded_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "command_exit_code": command_exit, "problems": problems,
        "inputs": inputs, "inputs_file_sha256": inputs_sha256, "source_hashes_after": after,
        "executable_sha256": digest(executable) if executable.is_file() else None,
        "swift_harness_compiled": built, "native_and_kotlin_owners_linked": linked,
        "native_tests_started": started,
        "native_tests": [{"case": name, "status": status, "seconds": float(seconds)} for name, status, seconds in finished],
        "test_evidence": test_evidence,
        "retained_engine_lifecycle_qualified": qualified,
        "same_process_reentry_qualified": qualified,
        "kmp_factory_qualified": False, "device_metal_qualified": False,
        "physical_motion_shutdown_qualified": False, "real_audio_interruption_qualified": False,
        "simulator_only": True,
        "observed_scope": "Whole-scene replacement; 2D/3D real input and concealed entry; native close ordering; stale handle and epoch rejection; native-shell display/audio/input/motion observations; actual application Home/activate. Unavailable simulator sensors remain unqualified.",
        "application_observation_files": [file.name for file in sorted((evidence / "application-observations").glob("*.json"))],
    }
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"stage": result["stage"], "qualified": qualified, "problems": problems}, indent=2))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
