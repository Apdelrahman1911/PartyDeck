"""Preserve the exact GitHub source archive without Git or build execution."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile


RUN = 34473325295
HEAD = "0f666e0ab7fdce63d5fa668442dae1c9fda86a1d"
BASE = Path("/tmp/partydeck-engine-ci") / str(RUN)
ENDPOINT = "repos/Apdelrahman1911/PartyDeck/tarball/" + HEAD
ARCHIVE = BASE / ("source-" + HEAD[:7] + ".tar.gz")
SOURCE = BASE / ("source-" + HEAD[:7])
STAGE = BASE / ".download-tmp" / ("source-" + HEAD[:7])


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


assert not SOURCE.exists() and not ARCHIVE.exists()
started = utc()
partial = ARCHIVE.with_suffix(".tar.gz.partial")
with partial.open("xb") as stream:
    command = subprocess.run(["gh", "api", ENDPOINT], stdout=stream,
                             stderr=subprocess.PIPE, timeout=1200)
assert command.returncode == 0, command.stderr.decode(errors="replace")
partial.rename(ARCHIVE)
STAGE.mkdir()
with tarfile.open(ARCHIVE, "r:gz") as package:
    members = package.getmembers()
    roots = {PurePosixPath(member.name).parts[0] for member in members}
    assert len(roots) == 1 and next(iter(roots)).endswith(HEAD[:7]), roots
    names = set()
    symlinks = []
    for member in members:
        original = PurePosixPath(member.name)
        assert not original.is_absolute() and ".." not in original.parts
        assert "\\" not in member.name
        relative = PurePosixPath(*original.parts[1:])
        if str(relative) == ".":
            assert member.isdir()
            continue
        assert str(relative) not in names, str(relative)
        names.add(str(relative))
        destination = STAGE.joinpath(*relative.parts)
        if member.isdir():
            destination.mkdir(parents=True, exist_ok=True)
        elif member.isfile():
            destination.parent.mkdir(parents=True, exist_ok=True)
            with package.extractfile(member) as source, destination.open("xb") as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
            assert destination.stat().st_size == member.size
            destination.chmod(member.mode & 0o777)
        elif member.issym():
            symlinks.append((destination, member.linkname))
        else:
            raise AssertionError("Unsupported archive member: " + member.name)
    for destination, target in symlinks:
        assert not Path(target).is_absolute()
        (destination.parent / target).resolve().relative_to(STAGE.resolve())
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(target)
STAGE.rename(SOURCE)
receipt = {
    "runId": RUN, "headSha": HEAD, "sourceEndpoint": ENDPOINT,
    "archivePath": str(ARCHIVE), "bytes": ARCHIVE.stat().st_size,
    "sha256": digest(ARCHIVE), "memberCount": len(members),
    "sourceDirectory": str(SOURCE), "collectionStartedAtUtc": started,
    "extractedAtUtc": utc(), "symlinkCount": len(symlinks),
    "scope": "Exact-commit GitHub API source archive only; no Git, native, Gradle, or engine execution.",
}
with (BASE / "source-archive.json").open("x") as stream:
    stream.write(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt), flush=True)
