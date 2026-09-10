#!/usr/bin/env python3
"""Collect focused production originals through the registered shared arena gate."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import time
import traceback
import zipfile


RUN_ID = 34532837557
HEAD = "e4871e165f949c600ddd89b13e74d06fc34d2e04"
ATTEMPT = 1
REPOSITORY = "Apdelrahman1911/PartyDeck"
BASE = Path(__file__).resolve().parents[1]
BULK = Path("/dev/shm/partydeck-evidence-20260910/34532837557")
CONTROL = BASE.parent / "shm-evidence-arena-20260910"
GATE = CONTROL / "arena_gate_v3.py"
GATE_SHA = "7224787adebedbc842166fe4dbb3b74ff23cad1f2c7458d5f38c984337a8447a"
EXPECTED = {
    "ios-renderer-pack", "ios-renderer-pack-evidence",
    "ios-focused-production-reports-and-simulator-app",
}
APP_MEMBER = "build/ci/ios/godot-session/PartyDeck-session-simulator.app.tar.gz"
ENV = {**os.environ, "TMPDIR": str(BULK / ".download-tmp"), "PYTHONDONTWRITEBYTECODE": "1"}


class IntegrityError(RuntimeError):
    pass


class RetryCollection(RuntimeError):
    pass


class StorageFloorWait(RuntimeError):
    pass


def utc():
    return datetime.now(timezone.utc).isoformat()


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def file_record(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest}


def write_json(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")


def record_once(path, value):
    if path.exists():
        assert json.loads(path.read_bytes()) == value
    else:
        write_json(path, value)


def alias(path, target):
    if path.is_symlink():
        assert path.resolve(strict=True) == target.resolve(strict=True)
    else:
        assert not path.exists()
        path.symlink_to(target, target_is_directory=target.is_dir())


def emit(value):
    event = {"utc": utc(), **value}
    with (BASE / "collection-events.jsonl").open("a") as stream:
        stream.write(json.dumps(event) + "\n")
    print(json.dumps(event), flush=True)


def checked_artifact(artifact):
    assert artifact["name"] in EXPECTED and not artifact["expired"]
    assert artifact["workflow_run"]["id"] == RUN_ID
    assert artifact["workflow_run"]["head_sha"] == HEAD
    assert type(artifact["size_in_bytes"]) is int and artifact["size_in_bytes"] > 0
    assert artifact.get("digest", "").startswith("sha256:")
    return artifact


def archive_path(artifact):
    return BULK / "artifact-zips" / f"{artifact['id']}-{artifact['name']}.zip"


def safe_members(package):
    members = package.infolist()
    assert len({member.filename for member in members}) == len(members), "Duplicate ZIP paths."
    for member in members:
        path = PurePosixPath(member.filename)
        mode = member.external_attr >> 16
        assert path.parts and not path.is_absolute() and ".." not in path.parts
        assert "\\" not in member.filename and not stat.S_ISLNK(mode)
        assert stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR)
    return members


def verify_archive(artifact):
    archive = archive_path(artifact)
    record = file_record(archive)
    assert record["bytes"] == artifact["size_in_bytes"], "Original ZIP size differs from API."
    assert "sha256:" + record["sha256"] == artifact["digest"], "Original ZIP digest differs from API."
    return archive, record


def require_active_window():
    active = json.loads((CONTROL / "active-lease.json").read_bytes())
    assert active["owner"] == "engine_ci" and active["status"] in ("admitted", "active")
    assert active["owner_physical_root"] == str(BULK)
    (BULK / ".download-tmp").mkdir(exist_ok=True)
    return active


def stream_api_to_new_file(endpoint, destination, prefix, timeout):
    token = stamp()
    partial = destination.with_name(destination.name + ".partial-" + token)
    error_path = BASE / "download-commands" / f"{prefix}-{token}.stderr"
    command = ["gh", "api", endpoint]
    started, code, timed_out = utc(), None, False
    with partial.open("xb") as target, error_path.open("xb") as error:
        try:
            result = subprocess.run(command, stdout=target, stderr=error,
                                    stdin=subprocess.DEVNULL, env=ENV, timeout=timeout)
            code = result.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
    write_json(BASE / "download-commands" / f"{prefix}-{token}.json", {
        "runId": RUN_ID, "headSha": HEAD, "command": command, "startedAtUtc": started,
        "completedAtUtc": utc(), "exitCode": code, "timedOut": timed_out,
        "partial": file_record(partial), "stderr": file_record(error_path),
        "activeAllocationWindow": require_active_window(),
    })
    if timed_out or code != 0:
        raise RetryCollection(f"API transfer failed; original partial retained: {partial}")
    return partial


def download_worker(artifact):
    checked_artifact(artifact)
    require_active_window()
    archive = archive_path(artifact)
    if not archive.exists():
        partial = stream_api_to_new_file(
            f"repos/{REPOSITORY}/actions/artifacts/{artifact['id']}/zip",
            archive, f"artifact-{artifact['id']}", 1800)
        actual = file_record(partial)
        assert actual["bytes"] == artifact["size_in_bytes"]
        assert "sha256:" + actual["sha256"] == artifact["digest"]
        partial.rename(archive)
        archive.chmod(0o444)
    archive, actual = verify_archive(artifact)
    alias(BASE / "artifact-zips" / archive.name, archive)
    with zipfile.ZipFile(archive) as package:
        directory = [
            {"path": member.filename, "bytes": member.file_size,
             "compressedBytes": member.compress_size, "crc32": f"{member.CRC:08x}",
             "directory": member.is_dir(), "externalAttributes": member.external_attr}
            for member in safe_members(package)
        ]
    record_once(BASE / f"{artifact['name']}.zip-directory.json", directory)
    record_once(BASE / f"{artifact['name']}.archive-integrity.json", {
        "runId": RUN_ID, "headSha": HEAD, "attempt": ATTEMPT, "artifact": artifact,
        "originalArchive": actual, "apiSizeAndSHA256Verified": True,
        "memberCount": len(directory), "memberCRCAndHashesDeferredToExtraction": True,
        "scope": "Complete original API-digest-matching ZIP retained; no member payload removed.",
    })


def selected(member_name):
    return member_name != APP_MEMBER


def extraction_plan(artifact):
    directory = json.loads((BASE / f"{artifact['name']}.zip-directory.json").read_bytes())
    retained = [row for row in directory if not row["directory"] and selected(row["path"])]
    parents = {str(parent) for row in retained for parent in PurePosixPath(row["path"]).parents}
    rounded = sum(((row["bytes"] + 4095) // 4096) * 4096 for row in retained)
    return rounded + 4096 * len(parents) + 16 * 1024 ** 2


def extraction_worker(artifact):
    checked_artifact(artifact)
    require_active_window()
    archive, actual = verify_archive(artifact)
    destination = BULK / "extracted" / artifact["name"]
    assert not destination.exists(), "Preserve an earlier extraction before another attempt."
    stage = BULK / ".download-tmp" / f"extract-{artifact['id']}-{stamp()}"
    stage.mkdir()
    files, omitted = [], []
    with zipfile.ZipFile(archive) as package:
        for member in safe_members(package):
            if member.is_dir():
                continue
            keep = selected(member.filename)
            target = stage.joinpath(*PurePosixPath(member.filename).parts)
            if keep:
                target.parent.mkdir(parents=True, exist_ok=True)
            digest, length = hashlib.sha256(), 0
            with package.open(member) as source, (target.open("xb") if keep else nullcontext(None)) as output:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    length += len(chunk)
                    if output is not None:
                        output.write(chunk)
            assert length == member.file_size
            item = {"path": member.filename, "bytes": length, "sha256": digest.hexdigest(),
                    "zipCRC32": f"{member.CRC:08x}", "zipCRCVerifiedByCompleteStream": True,
                    "retainedExtracted": keep}
            if not keep:
                item["reason"] = "Complete original app tarball remains inside the intact ZIP; raw tarball bytes stream-hashed and ZIP CRC verified. Nested app verification is separate."
            files.append(item)
            if not keep:
                omitted.append(item)
    stage.rename(destination)
    alias(BASE / artifact["name"], destination)
    record_once(BASE / f"{artifact['name']}.files.json", files)
    record_once(BASE / f"{artifact['name']}.unextracted-members.json", omitted)
    record_once(BASE / f"{artifact['name']}.downloaded.json", artifact)
    write_json(BASE / f"{artifact['name']}.integrity.json", {
        "runId": RUN_ID, "headSha": HEAD, "attempt": ATTEMPT, "artifactId": artifact["id"],
        "name": artifact["name"], "archivePath": str(BASE / "artifact-zips" / archive.name),
        "physicalArchivePath": str(archive), "archiveBytes": actual["bytes"],
        "archiveDigest": "sha256:" + actual["sha256"], "apiDigest": artifact["digest"],
        "apiBytes": artifact["size_in_bytes"], "zipDigestMatchesApi": True, "zipSizeMatchesApi": True,
        "physicalExtractionPath": str(destination), "originalFileCount": len(files),
        "originalUncompressedBytes": sum(row["bytes"] for row in files),
        "extractedFileCount": sum(row["retainedExtracted"] for row in files),
        "extractedBytes": sum(row["bytes"] for row in files if row["retainedExtracted"]),
        "unextractedFileCount": len(omitted), "unextractedBytes": sum(row["bytes"] for row in omitted),
        "allZipMembersStreamHashedAndCRCVerified": True, "completeOriginalArchivePreserved": True,
        "allXCResultAndDiagnosticMembersExtracted": True, "appTarballRetainedInOriginalZip": bool(omitted),
        "collectionCompletedAtUtc": utc(),
        "scope": "Only the production app tarball is omitted from working extraction. Every original remains in the complete verified ZIP; all XCResults, logs, link maps, symbols, attachments and diagnostics are retained byte-for-byte. No native execution or media viewing.",
    })


def log_worker(job):
    require_active_window()
    assert job["run_id"] == RUN_ID and job["head_sha"] == HEAD and job["run_attempt"] == ATTEMPT
    assert job["status"] == "completed" and job["conclusion"] != "skipped"
    destination = BULK / "logs" / f"job-{job['id']}.log"
    if not destination.exists():
        partial = stream_api_to_new_file(
            f"repos/{REPOSITORY}/actions/jobs/{job['id']}/logs",
            destination, f"job-{job['id']}", 180)
        assert partial.stat().st_size > 0
        partial.rename(destination)
        destination.chmod(0o444)
    alias(BASE / destination.name, destination)
    write_json(BASE / f"job-{job['id']}.collected.json", {
        "runId": RUN_ID, "headSha": HEAD, "attempt": ATTEMPT,
        "jobId": job["id"], "name": job["name"], "conclusion": job["conclusion"],
        **file_record(destination), "collectedAtUtc": utc(),
    })


def gate_worker(operation, metadata_path, planned_bytes):
    token = stamp()
    log = BASE / "gate-windows" / f"{operation}-{token}.log"
    command = [sys.executable, str(GATE), "run", "--owner", "engine_ci",
               "--planned-bytes", str(planned_bytes), "--memory-reserve-bytes", str(8 * 1024 ** 2),
               "--", sys.executable, str(Path(__file__)), operation, str(metadata_path)]
    started = utc()
    with log.open("xb") as output:
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, env=ENV)
    write_json(BASE / "gate-windows" / f"{operation}-{token}.json", {
        "command": command, "startedAtUtc": started, "completedAtUtc": utc(),
        "exitCode": result.returncode, "plannedPeakAdditionalBytes": planned_bytes,
        "log": file_record(log), "gateSHA256": GATE_SHA,
    })
    if result.returncode == 75:
        raise StorageFloorWait(f"Shared storage window deferred; originals preserved. See {log}")
    if result.returncode == 74:
        raise RetryCollection(f"Transfer retry required; partial preserved. See {log}")
    if result.returncode:
        raise IntegrityError(f"Collection worker failed with exit {result.returncode}; see {log}")


def collect_artifact(artifact):
    checked_artifact(artifact)
    metadata = BASE / "request-metadata" / f"artifact-{artifact['id']}.json"
    record_once(metadata, artifact)
    if not (BASE / f"{artifact['name']}.archive-integrity.json").exists():
        gate_worker("download-artifact", metadata, artifact["size_in_bytes"] + 8 * 1024 ** 2)
    if not (BASE / f"{artifact['name']}.integrity.json").exists():
        gate_worker("extract-artifact", metadata, extraction_plan(artifact))
    return {"event": "artifact-collected", "name": artifact["name"], "id": artifact["id"]}


def collect_log(job):
    metadata = BASE / "request-metadata" / f"job-{job['id']}.json"
    record_once(metadata, job)
    receipt = BASE / f"job-{job['id']}.collected.json"
    if not receipt.exists():
        gate_worker("download-log", metadata, 64 * 1024 ** 2)
    preserved = json.loads(receipt.read_bytes())
    actual = file_record(BULK / "logs" / f"job-{job['id']}.log")
    assert preserved["jobId"] == job["id"] and preserved["headSha"] == HEAD
    assert all(preserved[key] == actual[key] for key in ("bytes", "sha256"))
    return {"event": "job-log-collected", "jobId": job["id"], "name": job["name"]}


def snapshot(endpoint, kind, token):
    result = subprocess.run(["gh", "api", endpoint], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=ENV, timeout=90)
    if result.returncode:
        raise RetryCollection(result.stderr.decode(errors="replace"))
    original = BASE / "api-snapshots" / f"{token}-{kind}.json"
    original.write_bytes(result.stdout)
    last = {"run": "last-run-status.json", "jobs": "last-jobs-status.json",
            "artifacts": "artifacts.json"}[kind]
    (BASE / last).write_bytes(result.stdout)
    return json.loads(result.stdout)


def monitor():
    for directory in ("api-snapshots", "download-commands", "gate-windows", "request-metadata", "artifact-zips"):
        (BASE / directory).mkdir(exist_ok=True)
    contract = {
        "runId": RUN_ID, "expectedHeadSha": HEAD, "expectedAttempt": ATTEMPT,
        "expectedWorkflow": ".github/workflows/validate.yml", "expectedEvent": "workflow_dispatch",
        "expectedInputs": {"platform": "ios-godot-production", "ios_godot_session": True,
                           "android_godot_session": False, "android_api": "35"},
        "inputsSource": "root-dispatch.json; corroborate focused job/step/scope evidence.",
        "expectedArtifacts": sorted(EXPECTED), "canonicalRoot": str(BASE), "physicalBulkRoot": str(BULK),
        "gate": str(GATE), "gateSHA256": GATE_SHA, "gatePolicy": str(CONTROL / "arena-policy-v3.json"),
        "originalZIPsPreserved": True, "appTarArchiveOnly": APP_MEMBER,
        "allXCResultsAndDiagnosticsRetained": True,
        "scope": "Sole engine_ci original collection for the new focused production run; no dispatch or native execution.",
    }
    record_once(BASE / "collection-contract.json", contract)
    write_json(BASE / f"collector-process-{stamp()}.json", {
        "pid": os.getpid(), "ppid": os.getppid(), "startedAtUtc": utc(),
        "script": file_record(Path(__file__)), "maximumConcurrentBulkTasks": 1,
        "gateEnforcesGlobalArenaCapAndDestinationAndMemoryFloors": True,
    })
    downloaded = {name for name in EXPECTED if (BASE / f"{name}.integrity.json").exists()}
    saved_logs = {json.loads(path.read_bytes())["jobId"] for path in BASE.glob("job-*.collected.json")}
    errors, pending, attempts, retry_after, previous = {}, {}, {}, {}, {}
    deadline = time.monotonic() + 210 * 60
    with ThreadPoolExecutor(max_workers=1) as bulk_pool, ThreadPoolExecutor(max_workers=3) as metadata_pool:
        while time.monotonic() < deadline:
            try:
                token = stamp()
                endpoints = [
                    (f"repos/{REPOSITORY}/actions/runs/{RUN_ID}", "run"),
                    (f"repos/{REPOSITORY}/actions/runs/{RUN_ID}/jobs?per_page=100", "jobs"),
                    (f"repos/{REPOSITORY}/actions/runs/{RUN_ID}/artifacts?per_page=100", "artifacts"),
                ]
                requests = [metadata_pool.submit(snapshot, endpoint, kind, token) for endpoint, kind in endpoints]
                run, jobs_document, artifacts_document = [request.result() for request in requests]
                assert run["id"] == RUN_ID and run["head_sha"] == HEAD and run["run_attempt"] == ATTEMPT
                assert run["event"] == "workflow_dispatch" and run["path"] == ".github/workflows/validate.yml"
                jobs, artifacts = jobs_document["jobs"], artifacts_document["artifacts"]
                assert jobs_document["total_count"] == len(jobs)
                assert artifacts_document["total_count"] == len(artifacts)
                assert len({artifact["name"] for artifact in artifacts}) == len(artifacts)
                assert not ({artifact["name"] for artifact in artifacts} - EXPECTED), "Unexpected artifact scope."
                for job in jobs:
                    assert job["run_id"] == RUN_ID and job["head_sha"] == HEAD and job["run_attempt"] == ATTEMPT
                    current = next((step["name"] for step in job.get("steps", []) if step["status"] == "in_progress"), job["status"])
                    signature = (current, job["status"], job["conclusion"])
                    if previous.get(job["id"]) != signature:
                        emit({"event": "job-status", "jobId": job["id"], "name": job["name"],
                              "current": current, "status": job["status"], "conclusion": job["conclusion"]})
                        previous[job["id"]] = signature
                for future in list(pending):
                    if not future.done():
                        continue
                    key = pending.pop(future)
                    try:
                        emit(future.result())
                        (downloaded if key[0] == "artifact" else saved_logs).add(key[1])
                    except StorageFloorWait as error:
                        retry_after[key] = time.monotonic() + 60
                        attempts[key] = max(0, attempts.get(key, 0) - 1)
                        emit({"event": "collection-deferred", "key": key, "error": str(error)})
                    except Exception as error:
                        emit({"event": "collection-error", "key": key, "error": str(error), "type": type(error).__name__})
                        if isinstance(error, IntegrityError) or attempts.get(key, 0) >= 3:
                            errors[str(key)] = str(error)
                        else:
                            retry_after[key] = time.monotonic() + 30
                in_flight = set(pending.values())
                for artifact in sorted(artifacts, key=lambda value: (value["name"].startswith("ios-focused-"), value["name"])):
                    key = ("artifact", artifact["name"])
                    if (key[1] not in downloaded and key not in in_flight and str(key) not in errors
                            and not artifact["expired"] and time.monotonic() >= retry_after.get(key, 0)):
                        attempts[key] = attempts.get(key, 0) + 1
                        pending[bulk_pool.submit(collect_artifact, artifact)] = key
                        emit({"event": "artifact-window-queued", "name": artifact["name"],
                              "artifactId": artifact["id"], "archiveBytes": artifact["size_in_bytes"]})
                for job in jobs:
                    key = ("log", job["id"])
                    if (job["status"] == "completed" and job["conclusion"] != "skipped" and key[1] not in saved_logs
                            and key not in in_flight and str(key) not in errors and time.monotonic() >= retry_after.get(key, 0)):
                        attempts[key] = attempts.get(key, 0) + 1
                        pending[bulk_pool.submit(collect_log, job)] = key
                if run["status"] == "completed":
                    available = {artifact["name"] for artifact in artifacts if not artifact["expired"]}
                    required_logs = {job["id"] for job in jobs if job["conclusion"] != "skipped"}
                    if (all(name in downloaded or str(("artifact", name)) in errors for name in available)
                            and all(job_id in saved_logs or str(("log", job_id)) in errors for job_id in required_logs)
                            and not pending):
                        receipt = {"runId": RUN_ID, "headSha": HEAD, "attempt": ATTEMPT,
                                   "conclusion": run["conclusion"], "downloadedArtifacts": sorted(downloaded),
                                   "missingExpectedArtifacts": sorted(EXPECTED - downloaded), "savedJobLogs": sorted(saved_logs),
                                   "collectionErrors": errors, "completedAtUtc": utc(), "output": str(BASE)}
                        write_json(BASE / "collection-complete.json", receipt)
                        emit({"event": "collection-completed", **receipt})
                        return
            except (RetryCollection, subprocess.TimeoutExpired, OSError, ValueError) as error:
                emit({"event": "monitor-error", "error": str(error), "type": type(error).__name__})
            time.sleep(25)
    raise RuntimeError("Monitoring deadline reached; original collection is incomplete.")


def main():
    os.umask(0o077)
    assert BASE == Path("/root/projects/PartyDeck/artifacts/evidence-storage/34532837557")
    assert (BASE / "bulk-shm").is_symlink() and (BASE / "bulk-shm").resolve() == BULK
    assert file_record(GATE)["sha256"] == GATE_SHA
    if len(sys.argv) == 1:
        monitor()
        return 0
    assert len(sys.argv) == 3
    operation, metadata_path = sys.argv[1], Path(sys.argv[2])
    assert metadata_path.parent == BASE / "request-metadata"
    value = json.loads(metadata_path.read_bytes())
    {"download-artifact": download_worker, "extract-artifact": extraction_worker,
     "download-log": log_worker}[operation](value)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RetryCollection:
        traceback.print_exc()
        raise SystemExit(74)
