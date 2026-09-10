"""Read-only exact-head workflow monitor and evidence downloader."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time


repository = "Apdelrahman1911/PartyDeck"
run_id, expected_head = sys.argv[1:3]
storage = Path("/root/projects/PartyDeck/artifacts/evidence-storage")
storage.mkdir(parents=True, exist_ok=True)
output = Path("/tmp/partydeck-engine-ci") / run_id
if not output.exists():
    stored_output = storage / run_id
    stored_output.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.symlink_to(stored_output, target_is_directory=True)
download_temporary = storage / ".download-tmp"
download_temporary.mkdir(parents=True, exist_ok=True)
artifact_names = {"godot-comparison-runtime-apk", "godot-comparison-builds"} | {
    f"godot-android-{mode}-font-{scale}-debug"
    for mode in ("2d", "3d") for scale in ("1.0", "2.0")
}
downloaded = {name for name in artifact_names if (output / (name + ".downloaded.json")).is_file()}
saved_logs = {int(path.stem.removeprefix("job-")) for path in output.glob("job-*.log") if path.stat().st_size > 0}
previous = {}
last_summary = 0
deadline = time.monotonic() + 150 * 60


def run_gh(arguments, timeout=60):
    result = subprocess.run(["gh", *arguments], capture_output=True, timeout=timeout,
                            env={**os.environ, "TMPDIR": str(download_temporary)})
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    return result.stdout


def fetch_json(endpoint, path):
    raw = run_gh(["api", endpoint])
    path.write_bytes(raw)
    return json.loads(raw)


def download_artifact(artifact):
    name = artifact["name"]
    print(f"Downloading {name} ({artifact['size_in_bytes']} bytes)", flush=True)
    run_gh(["run", "download", run_id, "--repo", repository, "--name", name,
            "--dir", str(output / name)], timeout=900)
    (output / f"{name}.downloaded.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return name


pending = {}
with ThreadPoolExecutor(max_workers=6) as pool:
    while time.monotonic() < deadline:
        try:
            run = fetch_json(f"repos/{repository}/actions/runs/{run_id}", output / "last-run-status.json")
            if run["head_sha"] != expected_head:
                raise SystemExit(f"Refusing mismatched head {run['head_sha']}; expected {expected_head}")
            jobs = fetch_json(f"repos/{repository}/actions/runs/{run_id}/jobs?per_page=100",
                              output / "last-jobs-status.json")["jobs"]
            heartbeat = time.monotonic() - last_summary >= 60
            for job in jobs:
                steps = job.get("steps", [])
                current = next((step["name"] for step in steps if step["status"] == "in_progress"), job["status"])
                failures = [step["name"] for step in steps if step.get("conclusion") == "failure"]
                signature = (current, tuple(failures), job["status"], job["conclusion"])
                if signature != previous.get(job["id"]) or heartbeat:
                    print(json.dumps({"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                      "jobId": job["id"], "name": job["name"], "current": current,
                                      "failures": failures, "status": job["status"], "conclusion": job["conclusion"]}), flush=True)
                    previous[job["id"]] = signature
            if heartbeat:
                last_summary = time.monotonic()

            artifacts = fetch_json(f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100",
                                   output / "artifacts.json")["artifacts"]
            in_flight = set(pending.values())
            for artifact in artifacts:
                name = artifact["name"]
                if name in artifact_names and name not in downloaded and name not in in_flight and not artifact["expired"]:
                    pending[pool.submit(download_artifact, artifact)] = name
                    in_flight.add(name)
            for future in list(pending):
                if not future.done():
                    continue
                name = pending.pop(future)
                try:
                    future.result()
                    downloaded.add(name)
                    print(f"Downloaded {name}: {output / name}", flush=True)
                except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as error:
                    print(f"Artifact download issue ({name}): {error}", flush=True)
            for job in jobs:
                if job["status"] == "completed" and job["id"] not in saved_logs and job["conclusion"] != "skipped":
                    try:
                        raw = run_gh(["api", f"repos/{repository}/actions/jobs/{job['id']}/logs"], timeout=120)
                        log = output / f"job-{job['id']}.log"
                        log.write_bytes(raw)
                        saved_logs.add(job["id"])
                        print(f"Saved {job['name']} log: {log}", flush=True)
                    except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as error:
                        print(f"Job log download issue ({job['id']}): {error}", flush=True)
            if run["status"] == "completed":
                available = {item["name"] for item in artifacts if item["name"] in artifact_names and not item["expired"]}
                required_logs = {job["id"] for job in jobs if job["conclusion"] != "skipped"}
                if available <= downloaded and required_logs <= saved_logs:
                    print(json.dumps({"runId": run_id, "head": expected_head,
                                      "conclusion": run["conclusion"], "downloadedArtifacts": sorted(downloaded),
                                      "missingExpectedArtifacts": sorted(artifact_names - downloaded),
                                      "output": str(output)}), flush=True)
                    break
        except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as error:
            print(f"Monitor read/download issue: {error}", flush=True)
        time.sleep(30)
    else:
        raise SystemExit("Monitoring deadline reached; inspect retained status before continuing.")
