#!/usr/bin/env python3
"""Run the archived 2D input/privacy checker against the bounded source candidate."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess

WORK = Path(__file__).resolve().parent.parent
PROJECT = WORK / "candidate"
ENGINE = Path("/opt/partydeck-godot/godot")
FIXTURE = WORK / "fixtures/layout-launch-2d.json"
CHECKER = PROJECT / "presentations/two_d/checks/scene_check.gd"


def receipt(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


for width, height, scale in [(378, 655, 1), (320, 568, 1), (320, 568, 2)]:
    name = f"source-input-{width}x{height}-text-{scale}"
    output = WORK / "results" / name
    if output.exists():
        raise SystemExit(f"Refusing to overwrite evidence: {output}")
    output.mkdir()
    command = ["flock", "/tmp/partydeck-godot.lock", "xvfb-run", "-a", "-s", "-screen 0 1440x1100x24",
               str(ENGINE), "--audio-driver", "Dummy", "--rendering-method", "gl_compatibility",
               "--path", str(PROJECT), "--script", str(CHECKER), "--", "--manual-bridge",
               f"--check-fixture={FIXTURE}", f"--check-output={output}",
               f"--check-width={width}", f"--check-height={height}",
               f"--check-text-scale={scale}", "--check-touch-drag=true"]
    record = {"command": command, "startedUtc": datetime.now(timezone.utc).isoformat(),
              "inputs": [receipt(p) for p in [ENGINE, FIXTURE, CHECKER, PROJECT / "presentations/two_d/table.gd"]],
              "environmentOverride": {"LIBGL_ALWAYS_SOFTWARE": "1"},
              "scope": "Source fixture, real OpenGL and emulated touch/mouse. No native or accepted-authority claim."}
    (output / "execution.json").write_text(json.dumps(record, indent=2) + "\n")
    with (output / "process.log").open("w") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                env={**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1"}, timeout=90)
    record.update(exitCode=result.returncode, completedUtc=datetime.now(timezone.utc).isoformat(),
                  outputs=[receipt(p) for p in sorted(output.iterdir()) if p.name != "execution.json"])
    (output / "execution.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{name}: exit {result.returncode}; {len(list(output.glob('*.png')))} original PNGs", flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
