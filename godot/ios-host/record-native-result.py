#!/usr/bin/env python3
"""Record the five executed XCTest cases and the linked executable identity."""

import hashlib
import json
from pathlib import Path
import re
import sys


EXPECTED = {
    "testRealScenePauseResumeInputExitAndReopenRefusal",
    "testCloseInsideActualDrawRunLoopDefersCleanup",
    "testImmediateForegroundLossAndResumeRestartsDrawing",
    "testCloseBeforePresentationDoesNotConstructEngine",
    "testCloseDuringInitializationUsesCheckedCleanupBoundary",
}


def main() -> None:
    evidence, executable = map(Path, sys.argv[1:])
    log = (evidence / "host-test.log").read_text()
    # This exact XCTest record form was checked in the retained Xcode 26.4.1
    # shipping iOS run 34398824935. A started/skipped/retried case is not a pass.
    prefix = r"^Test Case '-\[ProbeHostUITests\.ProbeHostUITests (test\w+)\]' "
    started = re.findall(prefix + r"started\.$", log, re.MULTILINE)
    finished = re.findall(prefix + r"(passed|failed|skipped) \(([\d.]+) seconds\)\.$", log, re.MULTILINE)
    if set(started) != EXPECTED or len(started) != len(EXPECTED):
        raise SystemExit("The expected five native cases did not each start exactly once.")
    if {name for name, _, _ in finished} != EXPECTED or len(finished) != len(EXPECTED) or any(status != "passed" for _, status, _ in finished):
        raise SystemExit("The expected five native cases did not each finish with a pass.")
    if "** TEST SUCCEEDED **" not in log:
        raise SystemExit("The retained Xcode execution did not report success.")
    symbols = (evidence / "host-symbols.log").read_text()
    defined = {
        fields[-1] for line in symbols.splitlines()
        if len(fields := line.split()) >= 3 and fields[-2] in set("TtSsDdBbRr")
    }
    if "_main" not in defined or "_OBJC_CLASS_$_PDGodotRuntime" not in defined:
        raise SystemExit("The linked executable lacks its host/runtime definitions.")
    if "godot_swift_module10SwiftUIApp" in symbols:
        raise SystemExit("Godot's exporter-owned SwiftUI application entered the host link.")
    digest = hashlib.sha256()
    with executable.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    receipt = {
        "stage": "diagnostic_native_host_execution",
        "executable_sha256": digest.hexdigest(),
        "native_tests": [{"case": name, "status": status, "seconds": float(seconds)} for name, status, seconds in finished],
        "engine": json.loads((evidence / "engine-artifact.json").read_text()),
        "resources": json.loads((evidence / "host-resources.json").read_text()),
        "ios_runtime_executed": True,
        "diagnostic_scene_only": True,
        "last_light_gameplay_qualified": False,
        "reinitialization_qualified": False,
        "kmp_factory_qualified": False,
        "device_metal_qualified": False,
    }
    (evidence / "native-host-result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("Five diagnostic native tests passed; Last Light/KMP/reinitialization remain separate gates.")


if __name__ == "__main__":
    main()
