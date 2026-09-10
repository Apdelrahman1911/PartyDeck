from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

work = Path(__file__).resolve().parent
name = sys.argv[1]
specifications = {
    "redraw": ("three_d_redraw_check.gd", ["--check-fixture=" + str(work / "fixtures/launch-3d.json")]),
    "native-bridge": ("native_bridge_check.gd", ["--check-fixtures=" + str(work / "fixtures")]),
    "terminal-return": ("terminal_return_render_check.gd", ["--check-fixtures=" + str(work / "fixtures")]),
    "3d-scene-portrait": ("three_d_scene_check.gd", ["--check-fixture=" + str(work / "fixtures/launch-3d.json"), "--check-width=390", "--check-height=844", "--check-text-scale=1"]),
    "3d-scene-large-text": ("three_d_scene_check.gd", ["--check-fixture=" + str(work / "fixtures/launch-3d.json"), "--check-width=390", "--check-height=844", "--check-text-scale=2", "--check-touch-drag=true"]),
}
script, arguments = specifications[name]
engine = Path("/opt/partydeck-godot/4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64")
project = work / "source/godot/renderer"
command = ["xvfb-run", "-a", "-s", "-screen 0 1280x1024x24", str(engine), "--path", str(project),
           "--audio-driver", "Dummy", "--rendering-method", "gl_compatibility", "--rendering-driver", "opengl3",
           "--log-file", str(work / (name + "-engine.log")), "--script", "res://tests/" + script, "--",
           "--check-output=" + str(work / name)] + arguments
started = time.monotonic()
with (work / (name + ".log")).open("w") as output:
    result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, timeout=180)
receipt = {"command": command, "exitCode": result.returncode, "elapsedSeconds": time.monotonic() - started,
           "engineSha256": hashlib.sha256(engine.read_bytes()).hexdigest(),
           "tableSha256": hashlib.sha256((project / "presentations/three_d/table.gd").read_bytes()).hexdigest(),
           "checkSha256": hashlib.sha256((project / "tests" / script).read_bytes()).hexdigest()}
report_path = work / name / "report.json"
if report_path.exists():
    report = json.loads(report_path.read_text())
    receipt["reportedResult"] = report.get("result")
    receipt["checks"] = len(report.get("checks", []))
    receipt["failedChecks"] = [check for check in report.get("checks", []) if not check.get("passed", False)]
    receipt["reportSha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
receipt["pngFiles"] = [str(path.relative_to(work)) for path in sorted((work / name).glob("*.png"))]
(work / (name + "-receipt.json")).write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt))
if result.returncode:
    print((work / (name + ".log")).read_text()[-10000:])
sys.exit(result.returncode)
