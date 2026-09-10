#!/usr/bin/env python3
"""Keep Swift linking and real authority gameplay execution as separate receipts."""

import hashlib
import json
from pathlib import Path
import re
import sys


EXPECTED = {
    "testReferenceMatchIn2D", "testReferenceMatchIn3D",
    "testReferenceMatchIn2DAt200Percent", "testReferenceMatchIn3DAt200Percent",
    "testSecureTableRendererExit",
}


def main() -> None:
    stage = sys.argv[1]
    evidence, executable = map(Path, sys.argv[2:])
    if stage not in {"build", "test"}:
        raise SystemExit("Expected build or test stage.")
    if "** BUILD SUCCEEDED **" not in (evidence / "authority-host-build.log").read_text():
        raise SystemExit("The retained Swift authority-host build did not succeed.")
    symbols = (evidence / "authority-host-symbols.log").read_text()
    defined = {
        fields[-1] for line in symbols.splitlines()
        if len(fields := line.split()) >= 3 and fields[-2] in set("TtSsDdBbRr")
    }
    for required in ("_main", "_OBJC_CLASS_$_PDGodotRuntime",
                     "_OBJC_CLASS_$_PDGBIosQualificationFactory", "_OBJC_CLASS_$_PDGBIosQualificationAuthority"):
        if required not in defined:
            raise SystemExit(f"The Swift executable is missing its linked owner: {required}")
    if "godot_swift_module10SwiftUIApp" in symbols:
        raise SystemExit("Godot's exporter-owned SwiftUI application entered the host link.")
    digest = hashlib.sha256()
    with executable.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    receipt = {
        "stage": "swift_authority_host_link" if stage == "build" else "native_authority_gameplay_execution",
        "executable_sha256": digest.hexdigest(),
        "inputs": json.loads((evidence / "authority-host-inputs.json").read_text()),
        "engine": json.loads((evidence / "engine-artifact.json").read_text()),
        "swift_authority_host_compiled": True,
        "ios_authority_runtime_executed": stage == "test",
        "last_light_gameplay_qualified": stage == "test",
        "dormant_engine_reentry_qualified": False,
        "kmp_factory_qualified": False,
        "device_metal_qualified": False,
        "simulator_only": True,
        "reference_full_matches": {
            "executed": stage == "test",
            "randomness": "reference_seed_2",
            "presentations": [{"mode": mode, "text_scale": scale} for mode in ("2d", "3d") for scale in (1, 2)],
        },
        "secure_default": {
            "launch_and_renderer_exit_executed": stage == "test",
            "full_match_qualified": False,
        },
    }
    if stage == "test":
        log = (evidence / "authority-host-test.log").read_text()
        prefix = r"^Test Case '-\[AuthorityHostUITests\.AuthorityHostUITests (test\w+)\]' "
        started = re.findall(prefix + r"started\.$", log, re.MULTILINE)
        finished = re.findall(prefix + r"(passed|failed|skipped) \(([\d.]+) seconds\)\.$", log, re.MULTILINE)
        if set(started) != EXPECTED or len(started) != len(EXPECTED):
            raise SystemExit("The five authority gameplay cases must each start exactly once.")
        if {name for name, _, _ in finished} != EXPECTED or len(finished) != len(EXPECTED) or any(status != "passed" for _, status, _ in finished):
            raise SystemExit("The five authority gameplay cases must each finish with a pass.")
        if "** TEST SUCCEEDED **" not in log:
            raise SystemExit("The retained authority XCTest execution did not succeed.")
        receipt["native_tests"] = [{"case": name, "status": status, "seconds": float(seconds)} for name, status, seconds in finished]
    (evidence / f"authority-host-{stage}-result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("Recorded the linked Swift owner." if stage == "build" else "Five real authority gameplay tests passed; dormancy and KMP integration remain separate.")


if __name__ == "__main__":
    main()
