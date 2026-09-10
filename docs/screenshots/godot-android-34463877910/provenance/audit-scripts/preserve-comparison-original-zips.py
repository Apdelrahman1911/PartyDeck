"""Adapted existing ZIP collector: preserve originals and verify the comparison collector extraction."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import time
import zipfile


REPOSITORY = "Apdelrahman1911/PartyDeck"
RUN_ID = int(sys.argv[1])
HEAD = sys.argv[2]
ATTEMPT = 1
BASE = Path("/tmp/partydeck-engine-ci") / str(RUN_ID)
STORAGE = Path("/root/projects/PartyDeck/artifacts/evidence-storage") / str(RUN_ID)
EXPECTED = {"godot-comparison-builds", "godot-comparison-runtime-apk"} | {
    f"godot-android-{mode}-font-{scale}-debug"
    for mode in ("2d", "3d") for scale in ("1.0", "2.0")
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
    files = []
    extracted = BASE / name
    assert extracted.is_dir()
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
            destination = extracted.joinpath(*path.parts)
            assert not destination.is_symlink()
            if member.is_dir():
                assert destination.is_dir()
                continue
            digest = hashlib.sha256()
            length = 0
            with package.open(member) as archived:
                while chunk := archived.read(1024 * 1024):
                    digest.update(chunk)
                    length += len(chunk)
            assert length == member.file_size == destination.stat().st_size
            with destination.open("rb") as actual:
                assert hashlib.file_digest(actual, "sha256").hexdigest() == digest.hexdigest()
            files.append({"path": member.filename, "bytes": length, "sha256": digest.hexdigest()})
    assert {str(path.relative_to(extracted)) for path in extracted.rglob("*") if path.is_file()} == {row["path"] for row in files}
    prior_metadata = json.loads((BASE / f"{name}.downloaded.json").read_text())
    assert prior_metadata["id"] == artifact_id and prior_metadata["workflow_run"]["head_sha"] == HEAD
    exclusive_json(BASE / f"{name}.files.json", files)
    exclusive_json(BASE / f"{name}.integrity.json", {
        **integrity, "extractedFileCount": len(files),
        "extractedBytes": sum(item["bytes"] for item in files),
        "zipEntriesReadWithCrcVerification": True,
        "everyExtractedFileMatchedOriginalZip": True,
        "collectionCompletedAtUtc": utc(),
    })
    return {"event": "original-zip-verified", **integrity, "files": len(files)}


for directory in ("artifact-zips", ".download-tmp", "api-snapshots"):
    (BASE / directory).mkdir(exist_ok=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
metadata = {}
for label, filename in [("run", "last-run-status.json"), ("jobs", "last-jobs-status.json"), ("artifacts", "artifacts.json")]:
    raw = (BASE / filename).read_bytes()
    metadata[label] = json.loads(raw)
    (BASE / "api-snapshots" / f"{stamp}-zip-collection-{label}.json").write_bytes(raw)
run = metadata["run"]
assert run["id"] == RUN_ID and run["head_sha"] == HEAD and run["run_attempt"] == 1
assert run["event"] == "workflow_dispatch" and run["path"] == ".github/workflows/godot-compare.yml"
artifacts = metadata["artifacts"]["artifacts"]
assert metadata["artifacts"]["total_count"] == len(artifacts)
assert len({artifact["name"] for artifact in artifacts}) == len(artifacts)
ready = [artifact for artifact in artifacts if artifact["name"] in EXPECTED and not artifact["expired"]
         and (BASE / f"{artifact['name']}.downloaded.json").is_file()
         and not (BASE / f"{artifact['name']}.integrity.json").exists()]
errors = []
with ThreadPoolExecutor(max_workers=3) as pool:
    futures = {pool.submit(download_artifact, artifact, time.time_ns()): artifact for artifact in ready}
    for future, artifact in futures.items():
        try:
            emit(future.result())
        except Exception as error:
            item = {"event": "original-zip-collection-error", "artifact": artifact["name"], "error": str(error), "type": type(error).__name__}
            emit(item)
            errors.append(item)
collected = sorted(name for name in EXPECTED if (BASE / f"{name}.integrity.json").is_file())
summary = {"runId": RUN_ID, "headSha": HEAD, "snapshot": stamp, "verifiedOriginalArtifacts": collected,
           "pendingExpectedArtifacts": sorted(EXPECTED - set(collected)), "errors": errors, "completedAtUtc": utc(),
           "scope": "Existing collector ZIP download/integrity logic adapted to verify already extracted original files; no build or runtime execution."}
exclusive_json(BASE / f"original-zip-collection-{stamp}.json", summary)
print(json.dumps(summary, indent=2), flush=True)
if errors:
    raise SystemExit(1)
