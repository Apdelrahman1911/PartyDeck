"""Freeze collected original bytes separately from continuing derived review work."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

ROOT = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34503251315')


def identity(path):
    h = sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}


complete = json.loads((ROOT / 'collection-complete.json').read_text())
assert not complete['collectionErrors'] and not complete['missingExpectedArtifacts']
audit = ROOT / 'review/collection-integrity-audit.json'
assert json.loads(audit.read_text())['audit_result'] == 'pass'
assert json.loads((ROOT / 'collector-process-completion.json').read_text())['collectorKernelExitCode'] == 0
paths = []
for path in ROOT.rglob('*'):
    if not path.is_file():
        continue
    relative = path.relative_to(ROOT)
    if relative.parts[0] in ('review', 'audit-scripts'):
        continue
    assert not path.is_symlink()
    paths.append(path)
records = [identity(path) for path in sorted(paths)]
manifest = ROOT / 'original-collection-files.json'
with manifest.open('x') as stream:
    json.dump(records, stream, indent=2)
    stream.write('\n')
receipt = {
    'runId': 34503251315, 'headSha': '1cd34a36753ed0112e6684f6525592dab8ef2edb',
    'frozenAtUtc': datetime.now(timezone.utc).isoformat(), 'originalFileCount': len(records),
    'originalBytes': sum(record['bytes'] for record in records), 'fileManifest': identity(manifest),
    'completedCollection': identity(ROOT / 'collection-complete.json'),
    'independentArchiveIntegrityAudit': identity(audit),
    'sourceReuse': identity(ROOT / 'shared-source-reuse.json'),
    'collectorScript': identity(ROOT / 'audit-scripts/monitor-production-android-34503251315.py'),
    'freezeScript': identity(Path(__file__)),
    'scope': 'All collected original ZIPs, extracted artifact bytes, API snapshots, job logs and current top-level provenance receipts are frozen by path/size/SHA-256. Further derived review files live in review/ and audit-scripts/. Content-preserving hard links may change inode/link/mtime metadata only, with a separate before/after receipt; original ZIP bytes are preserved.',
}
path = ROOT / 'original-collection-frozen.json'
with path.open('x') as stream:
    json.dump(receipt, stream, indent=2)
    stream.write('\n')
print(json.dumps({'receipt': identity(path), 'fileCount': len(records)}, indent=2))
