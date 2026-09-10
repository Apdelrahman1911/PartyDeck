"""Retain an exact workflow head's source archive without executing its code."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile


run_id, head = sys.argv[1:3]
assert re.fullmatch(r"[1-9][0-9]*", run_id)
assert re.fullmatch(r"[0-9a-f]{40}", head)
base = Path('/tmp/partydeck-engine-ci') / run_id
assert base.is_dir(), 'Start the exact-head collector first.'
run_status = json.loads((base / 'last-run-status.json').read_text())
assert str(run_status['id']) == run_id and run_status['head_sha'] == head
archive = base / ('source-' + head[:7] + '.tar.gz')
source = base / ('source-' + head[:7])
receipt_path = base / 'source-archive.json'
assert not archive.exists() and not source.exists() and not receipt_path.exists(), 'Refusing to overwrite earlier source evidence.'
endpoint = 'repos/Apdelrahman1911/PartyDeck/tarball/' + head
with archive.open('xb') as output:
    subprocess.run(['gh', 'api', endpoint], stdout=output, check=True, timeout=900)
with archive.open('rb') as stream:
    archive_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
with tarfile.open(archive, mode='r:gz') as package:
    members = package.getmembers()
    roots = {Path(member.name).parts[0] for member in members}
    assert len(roots) == 1
    root = next(iter(roots))
    assert root.endswith('-' + head[:7]), root
    # GitHub gives a single top-level source directory. The data filter rejects
    # unsafe archive members, and an explicit prefix check keeps every file here.
    for member in members:
        parts = Path(member.name).parts
        assert parts[0] == root and '..' not in parts and not Path(member.name).is_absolute()
    package.extractall(base, filter='data')
    (base / root).rename(source)
receipt = {
    'runId': int(run_id), 'headSha': head, 'sourceEndpoint': endpoint,
    'archivePath': str(archive), 'bytes': archive.stat().st_size,
    'sha256': archive_sha, 'memberCount': len(members), 'sourceDirectory': str(source),
    'extractedAtUtc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Immutable-commit source archive only; no native, Gradle or engine execution.',
}
receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt), flush=True)
