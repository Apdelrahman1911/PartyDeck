"""Read-only combined iOS monitor; retain original API bytes, ZIPs, and logs."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import time
import zipfile


REPOSITORY = "Apdelrahman1911/PartyDeck"
RUN_ID = 34478720554
HEAD = "c6ea1dd9f7966517fbee87a06b633d01c432c24d"
ATTEMPT = 1
BASE = Path("/tmp/partydeck-engine-ci") / str(RUN_ID)
STORAGE = Path("/root/projects/PartyDeck/artifacts/evidence-storage") / str(RUN_ID)
EXPECTED = {
    "godot-ios-host-renderer", "godot-ios-host-renderer-evidence",
    "godot-ios-host-engine", "godot-ios-host-framework",
    "godot-ios-authority-gameplay", "godot-ios-retained-host-test-attempt-1",
}
assert BASE.is_symlink() and BASE.resolve() == STORAGE.resolve()
ENV = {**os.environ, "TMPDIR": str(BASE / ".download-tmp")}


def utc():
    return datetime.now(timezone.utc).isoformat()


def emit(event):
    value = {"utc": utc(), **event}
    with (BASE / "collection-events.jsonl").open("a") as stream:
        stream.write(json.dumps(value) + "\n")
    print(json.dumps(value), flush=True)


def exclusive_json(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")


def gh(arguments, timeout=90, target=None):
    result = subprocess.run(["gh", *arguments], stdout=target or subprocess.PIPE,
                            stderr=subprocess.PIPE, env=ENV, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    return result.stdout


def api_snapshot(endpoint, label, stamp):
    raw = gh(["api", endpoint])
    (BASE / "api-snapshots" / f"{stamp}-{label}.json").write_bytes(raw)
    last = {"run": "last-run-status.json", "jobs": "last-jobs-status.json",
            "artifacts": "artifacts.json"}[label]
    (BASE / last).write_bytes(raw)
    return json.loads(raw)


class IntegrityError(RuntimeError):
    pass


def download_artifact(artifact, attempt):
    name, artifact_id = artifact["name"], artifact["id"]
    assert name in EXPECTED and not artifact["expired"]
    origin = artifact["workflow_run"]
    assert origin["id"] == RUN_ID and origin["head_sha"] == HEAD
    archive = BASE / "artifact-zips" / f"{artifact_id}-{name}.zip"
    partial = archive.with_suffix(f".zip.partial-{attempt}")
    started = utc()
    if not archive.exists():
        with partial.open("xb") as stream:
            gh(["api", f"repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip"],
               timeout=1200, target=stream)
        partial.rename(archive)
    with archive.open("rb") as stream:
        actual_digest = "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()
    actual_size = archive.stat().st_size
    integrity = {
        "artifactId": artifact_id, "name": name, "runId": RUN_ID, "headSha": HEAD,
        "apiDigest": artifact.get("digest"), "archiveDigest": actual_digest,
        "archiveBytes": actual_size, "apiBytes": artifact["size_in_bytes"],
        "zipDigestMatchesApi": actual_digest == artifact.get("digest"),
        "zipSizeMatchesApi": actual_size == artifact["size_in_bytes"],
        "archivePath": str(archive), "collectionStartedAtUtc": started,
    }
    if not integrity["zipDigestMatchesApi"] or not integrity["zipSizeMatchesApi"]:
        exclusive_json(BASE / f"{name}.integrity-failure.json", integrity)
        raise IntegrityError(f"ZIP integrity mismatch: {name}")
    stage = BASE / ".download-tmp" / f"extract-{artifact_id}-{attempt}"
    stage.mkdir()
    files = []
    with zipfile.ZipFile(archive) as package:
        members = package.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)):
            raise IntegrityError(f"Duplicate ZIP paths: {name}")
        for member in members:
            path = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            if (path.is_absolute() or ".." in path.parts or "\\" in member.filename
                    or not path.parts or stat.S_ISLNK(mode)):
                raise IntegrityError(f"Unsafe ZIP member: {name}/{member.filename}")
            destination = stage.joinpath(*path.parts)
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            length = 0
            with package.open(member) as source, destination.open("xb") as target:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    length += len(chunk)
                    target.write(chunk)
            assert length == member.file_size
            files.append({"path": member.filename, "bytes": length, "sha256": digest.hexdigest()})
    assert not (BASE / name).exists()
    stage.rename(BASE / name)
    exclusive_json(BASE / f"{name}.files.json", files)
    exclusive_json(BASE / f"{name}.downloaded.json", artifact)
    exclusive_json(BASE / f"{name}.integrity.json", {
        **integrity, "extractedFileCount": len(files),
        "extractedBytes": sum(item["bytes"] for item in files),
        "collectionCompletedAtUtc": utc(),
    })
    return {"event": "artifact-collected", **integrity, "files": len(files)}


def collect_log(job):
    raw = gh(["api", f"repos/{REPOSITORY}/actions/jobs/{job['id']}/logs"], timeout=120)
    assert raw, "Empty job log"
    path = BASE / f"job-{job['id']}.log"
    with path.open("xb") as stream:
        stream.write(raw)
    receipt = {"runId": RUN_ID, "headSha": HEAD, "attempt": ATTEMPT,
               "jobId": job["id"], "name": job["name"], "conclusion": job["conclusion"],
               "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
               "collectedAtUtc": utc(), "path": str(path)}
    exclusive_json(BASE / f"job-{job['id']}.collected.json", receipt)
    return {"event": "job-log-collected", **receipt}


exclusive_json(BASE / "collection-contract.json", {
    "runId": RUN_ID, "expectedHeadSha": HEAD, "expectedAttempt": ATTEMPT,
    "expectedWorkflow": ".github/workflows/godot-ios-authority-host.yml",
    "expectedEvent": "workflow_dispatch", "expectedInputs": {"host": "both", "retained_stage": "test"},
    "inputsVerification": "Expected from coordinator; verify against retained CI context and logs.",
    "expectedArtifacts": sorted(EXPECTED), "startedAtUtc": utc(),
    "storage": str(STORAGE), "alias": str(BASE),
    "scope": "Read-only API/archive/source collection. No CI dispatch or native/Gradle build.",
})
downloaded = set()
saved_logs = set()
permanent_errors = {}
pending = {}
attempts = {}
previous = {}
last_heartbeat = 0
deadline = time.monotonic() + 210 * 60
with ThreadPoolExecutor(max_workers=6) as pool:
    while time.monotonic() < deadline:
        try:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            run = api_snapshot(f"repos/{REPOSITORY}/actions/runs/{RUN_ID}", "run", stamp)
            assert run["id"] == RUN_ID and run["head_sha"] == HEAD
            assert run["run_attempt"] == ATTEMPT and run["event"] == "workflow_dispatch"
            assert run["path"] == ".github/workflows/godot-ios-authority-host.yml"
            jobs_document = api_snapshot(f"repos/{REPOSITORY}/actions/runs/{RUN_ID}/jobs?per_page=100", "jobs", stamp)
            jobs = jobs_document["jobs"]
            assert jobs_document["total_count"] == len(jobs)
            heartbeat = time.monotonic() - last_heartbeat >= 60
            for job in jobs:
                assert job["run_id"] == RUN_ID and job["head_sha"] == HEAD
                assert job["run_attempt"] == ATTEMPT
                steps = job.get("steps", [])
                current = next((step["name"] for step in steps if step["status"] == "in_progress"), job["status"])
                failures = [step["name"] for step in steps if step.get("conclusion") == "failure"]
                signature = (current, tuple(failures), job["status"], job["conclusion"])
                if signature != previous.get(job["id"]) or heartbeat:
                    emit({"event": "job-status", "jobId": job["id"], "name": job["name"],
                          "current": current, "failures": failures,
                          "status": job["status"], "conclusion": job["conclusion"]})
                    previous[job["id"]] = signature
            if heartbeat:
                last_heartbeat = time.monotonic()
            document = api_snapshot(f"repos/{REPOSITORY}/actions/runs/{RUN_ID}/artifacts?per_page=100", "artifacts", stamp)
            artifacts = document["artifacts"]
            assert document["total_count"] == len(artifacts)
            assert len({item["name"] for item in artifacts}) == len(artifacts)
            for future in list(pending):
                if future.done():
                    key = pending.pop(future)
                    try:
                        emit(future.result())
                        (downloaded if key[0] == "artifact" else saved_logs).add(key[1])
                    except Exception as error:
                        emit({"event": "collection-error", "key": key, "error": str(error), "type": type(error).__name__})
                        if isinstance(error, (IntegrityError, AssertionError, FileExistsError)) or attempts.get(key, 0) >= 3:
                            permanent_errors[str(key)] = str(error)
            in_flight = set(pending.values())
            for artifact in artifacts:
                name = artifact["name"]
                key = ("artifact", name)
                if name in EXPECTED and name not in downloaded and key not in in_flight and str(key) not in permanent_errors and not artifact["expired"]:
                    attempts[key] = attempts.get(key, 0) + 1
                    pending[pool.submit(download_artifact, artifact, attempts[key])] = key
                    emit({"event": "artifact-download-started", "name": name, "id": artifact["id"], "bytes": artifact["size_in_bytes"]})
            for job in jobs:
                key = ("log", job["id"])
                if job["status"] == "completed" and job["conclusion"] != "skipped" and job["id"] not in saved_logs and key not in in_flight and str(key) not in permanent_errors:
                    attempts[key] = attempts.get(key, 0) + 1
                    pending[pool.submit(collect_log, job)] = key
            if run["status"] == "completed":
                available = {item["name"] for item in artifacts if item["name"] in EXPECTED and not item["expired"]}
                required_logs = {job["id"] for job in jobs if job["conclusion"] != "skipped"}
                artifact_done = all(name in downloaded or str(("artifact", name)) in permanent_errors for name in available)
                logs_done = all(job_id in saved_logs or str(("log", job_id)) in permanent_errors for job_id in required_logs)
                if artifact_done and logs_done and not pending:
                    receipt = {"runId": RUN_ID, "headSha": HEAD, "attempt": ATTEMPT,
                               "conclusion": run["conclusion"], "downloadedArtifacts": sorted(downloaded),
                               "missingExpectedArtifacts": sorted(EXPECTED - downloaded),
                               "savedJobLogs": sorted(saved_logs), "collectionErrors": permanent_errors,
                               "completedAtUtc": utc(), "output": str(BASE)}
                    exclusive_json(BASE / "collection-complete.json", receipt)
                    emit({"event": "collection-completed", **receipt})
                    break
        except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as error:
            emit({"event": "monitor-error", "error": str(error), "type": type(error).__name__})
        time.sleep(25)
    else:
        raise SystemExit("Monitoring deadline reached; retained snapshots are incomplete.")
