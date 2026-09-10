"""Extract and hash the original retained preservation archive without native execution."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import tarfile

BASE = Path('/tmp/partydeck-engine-ci/34478720554')
HOST = BASE / 'godot-ios-retained-host-test-attempt-1'
ARCHIVE = HOST / 'retained-ci-preserved/retained-host-evidence.tar.gz'
OUTPUT = BASE / 'retained-preserved'
STAGE = BASE / '.download-tmp/retained-preserved'

def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()

assert not OUTPUT.exists() and not STAGE.exists()
STAGE.mkdir()
files, names = [], set()
with tarfile.open(ARCHIVE, 'r:gz') as package:
    members = package.getmembers()
    for member in members:
        path = PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts and '\\' not in member.name
        if str(path) == '.':
            assert member.isdir()
            continue
        assert str(path) not in names, member.name
        names.add(str(path))
        destination = STAGE.joinpath(*path.parts)
        if member.isdir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        assert member.isfile(), 'Unexpected special archive member: ' + member.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        length, sha = 0, hashlib.sha256()
        with package.extractfile(member) as source, destination.open('xb') as output:
            while data := source.read(1024 * 1024):
                length += len(data)
                sha.update(data)
                output.write(data)
        assert length == member.size
        files.append({'path': path.as_posix(), 'bytes': length, 'sha256': sha.hexdigest()})
STAGE.rename(OUTPUT)
duplicate_files = []
for item in files:
    original = HOST / item['path']
    if original.is_file():
        assert original.stat().st_size == item['bytes'] and digest(original) == item['sha256'], original
        duplicate_files.append(item['path'])
receipt = {'runId': 34478720554, 'headSha': 'c6ea1dd9f7966517fbee87a06b633d01c432c24d',
    'archivePath': str(ARCHIVE), 'archiveSha256': digest(ARCHIVE), 'archiveBytes': ARCHIVE.stat().st_size,
    'memberCount': len(members), 'files': files, 'rawDuplicateFilesVerified': duplicate_files,
    'extractionDirectory': str(OUTPUT), 'scope': 'Original preservation archive and duplicate raw payload identities only.'}
target = BASE / 'retained-preservation-audit.json'
with target.open('x') as stream: stream.write(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'fileCount': len(files), 'rawDuplicateFileCount': len(duplicate_files),
    'receipt': str(target), 'sha256': digest(target)}), flush=True)
