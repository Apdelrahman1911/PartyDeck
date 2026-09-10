"""Independently bind this run to the owner's frozen exact-commit source.

No download, extraction, normalization, source mutation, build or test execution.
"""
import base64
from datetime import datetime, timezone
from hashlib import sha1, sha256
import json
from pathlib import Path, PurePosixPath

ROOT = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34503251315')
SHARED = ROOT.parent / 'source-1cd34a3'
HEAD = '1cd34a36753ed0112e6684f6525592dab8ef2edb'
RUN = 34503251315
PINS = {
    'source-1cd34a3.tar.gz': '4492698249f2450baa5f8a36fb8fad888374127ff50665744e7489f7e3c9c24e',
    'source-archive.json': 'be616f4fefeabddfc611a378ab062e27972f582565a365f5dd80d83e24f84c7c',
    'source-extraction-audit.json': '8b3078007248e1e858a8fd7acda54d4ba53524526f3c2205afdaa6824042a13b',
    'collection-frozen.json': '129e70e217d0d84c5e2f71fdf7ac8f11048e843fe41ff06d0422dba5fd81ca82',
}


def identity(path):
    assert path.is_file() and not path.is_symlink(), path
    before = path.stat()
    digest = sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    after = path.stat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns) == (
        after.st_ino, after.st_size, after.st_mtime_ns), path
    return {'path': str(path), 'bytes': after.st_size, 'sha256': digest.hexdigest()}


def safe_relative(value):
    p = PurePosixPath(value)
    assert value and not p.is_absolute() and '..' not in p.parts and '\\' not in value, value
    assert p.as_posix() == value, value
    return p


def git_blob(data):
    return sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


freeze_identity = identity(SHARED / 'collection-frozen.json')
assert freeze_identity['sha256'] == PINS['collection-frozen.json']
freeze = json.loads((SHARED / 'collection-frozen.json').read_text())
assert freeze['status'] == 'complete_frozen' and freeze['head_sha'] == HEAD
assert freeze['root'] == str(SHARED) and RUN in freeze['related_run_ids']
identities = {'collection-frozen.json': freeze_identity}
for entry in freeze['files']:
    relative = safe_relative(entry['path'])
    assert entry['path'] not in identities, entry['path']
    actual = identity(SHARED / relative)
    assert (actual['bytes'], actual['sha256']) == (entry['bytes'], entry['sha256']), entry['path']
    identities[entry['path']] = actual
assert set(identities) == {p.relative_to(SHARED).as_posix()
                           for p in SHARED.rglob('*') if p.is_file() or p.is_symlink()}
assert len(freeze['files']) == freeze['file_count_excluding_this_manifest']
assert sum(i['bytes'] for n, i in identities.items() if n != 'collection-frozen.json') == freeze['bytes_excluding_this_manifest']
assert all(identities[n]['sha256'] == pin for n, pin in PINS.items())

archive = json.loads((SHARED / 'source-archive.json').read_text())
audit = json.loads((SHARED / 'source-extraction-audit.json').read_text())
commit = json.loads((SHARED / 'source-commit.json').read_text())
tree = json.loads((SHARED / 'source-git-tree.json').read_text())
assert archive['headSha'] == audit['headSha'] == commit['sha'] == HEAD
assert not tree['truncated']
assert archive['gitTreeSha'] == audit['gitTreeSha'] == tree['sha'] == commit['tree']['sha'] == freeze['git_tree_sha']
assert RUN in archive['relatedRunIds'] and RUN in audit['relatedRunIds']
assert archive['sourceEndpoint'] == 'repos/Apdelrahman1911/PartyDeck/tarball/' + HEAD
for key, name in [('sourceArchive', 'source-1cd34a3.tar.gz'),
                  ('sourceArchiveReceipt', 'source-archive.json'),
                  ('sourceCommit', 'source-commit.json'),
                  ('sourceGitTree', 'source-git-tree.json'),
                  ('unextractedGalleryMemberInventory', 'unextracted-source-gallery-members.json')]:
    assert audit[key] == identities[name], key
assert archive['sha256'] == identities['source-1cd34a3.tar.gz']['sha256']
assert archive['bytes'] == identities['source-1cd34a3.tar.gz']['bytes']
assert archive['sourceCommit'] == identities['source-commit.json']
assert archive['sourceGitTree'] == identities['source-git-tree.json']
assert all(audit[key] for key in ('allExtractedFilesMatchArchive', 'allArchiveFilesBoundToExactCommit',
    'gzipEndOfStreamVerified', 'archiveMemberSetMatchesExactGitTree',
    'unextractedGalleryInventoryMatchesArchive', 'noUnexpectedExtractedFiles', 'completeOriginalArchivePreserved'))

source = Path(archive['sourceDirectory'])
assert source == Path(audit['sourceDirectory']) and source == SHARED / 'source-1cd34a3'
tree_entries = {v['path']: v for v in tree['tree']}
assert len(tree_entries) == len(tree['tree']) == audit['gitTreeEntryCount']
records = audit['extractedSourceFiles']
names = set()
conversions = []
for entry in records:
    relative = safe_relative(entry['path'])
    assert relative.parts[:2] != ('docs', 'screenshots') and entry['path'] not in names
    names.add(entry['path'])
    actual = identities[source.name + '/' + entry['path']]
    assert (actual['bytes'], actual['sha256']) == (entry['bytes'], entry['sha256']), entry['path']
    data = (source / relative).read_bytes()
    assert sha256(data).hexdigest() == entry['sha256']
    expected = tree_entries[entry['path']]
    assert expected['type'] == entry['gitType'] == 'blob'
    assert expected['sha'] == entry['gitSha'] and expected['mode'] == entry['gitMode']
    assert entry['gitBlobMatchesExactCommit']
    if git_blob(data) != expected['sha']:
        assert entry['path'] == 'gradlew.bat', entry['path']
        raw_blob = json.loads((SHARED / 'source-git-blob-gradlew-bat.json').read_text())
        assert raw_blob['encoding'] == 'base64'
        raw_data = base64.b64decode(raw_blob['content'])
        assert raw_blob['sha'] == expected['sha'] == git_blob(raw_data)
        assert len(raw_data) == raw_blob['size'] == expected['size']
        assert data.replace(b'\r\n', b'\n') == raw_data
        assert raw_data.replace(b'\n', b'\r\n') == data
        assert '*.bat text eol=crlf whitespace=cr-at-eol' in (source / '.gitattributes').read_text()
        conversions.append({'path': entry['path'], 'archiveBytes': len(data), 'gitBlobBytes': len(raw_data),
                            'crlfCount': data.count(b'\r\n'), 'rawGitBlobSha': expected['sha'],
                            'archiveFormGitBlobSha': git_blob(data), 'archiveFormPreserved': True,
                            'rawBlobReceipt': identities['source-git-blob-gradlew-bat.json']})
    else:
        assert len(data) == expected['size']
assert names == {v['path'] for v in tree['tree'] if v['type'] == 'blob'
                 and PurePosixPath(v['path']).parts[:2] != ('docs', 'screenshots')}
assert names == {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file() or p.is_symlink()}
assert len(records) == archive['extractedFileCount'] == audit['extractedFileCount']
assert sum(r['bytes'] for r in records) == audit['extractedBytes']
assert len(conversions) == len(audit['documentedArchiveTextConversions']) == 1
assert audit['documentedArchiveTextConversions'] == archive['documentedArchiveTextConversions']

gallery = json.loads((SHARED / 'unextracted-source-gallery-members.json').read_text())
gallery_names = set()
for entry in gallery:
    relative = safe_relative(entry['path'])
    assert relative.parts[:2] == ('docs', 'screenshots') and entry['path'] not in gallery_names
    gallery_names.add(entry['path'])
    expected = tree_entries[entry['path']]
    assert expected['sha'] == entry['gitSha'] and expected['type'] == entry['gitType']
    if expected['type'] == 'blob':
        assert expected['size'] == entry['bytes'] and entry['gitBlobMatchesExactCommit']
assert gallery_names == {v['path'] for v in tree['tree'] if PurePosixPath(v['path']).parts[:2] == ('docs', 'screenshots')}
assert len(gallery) == archive['unextractedGalleryMemberCount'] == audit['unextractedGalleryMemberCount']
assert not (source / 'docs/screenshots').exists()
run = json.loads((ROOT / 'last-run-status.json').read_text())
assert run['id'] == RUN and run['head_sha'] == HEAD and run['run_attempt'] == 1
summary = {
    'schemaVersion': 2, 'runId': RUN, 'headSha': HEAD, 'gitTreeSha': tree['sha'],
    'createdAtUtc': datetime.now(timezone.utc).isoformat(),
    'sharedSourceDirectory': str(source), 'sharedOwner': '/root/game_domain',
    'frozenOwnerPinsReverified': {n: identities[n] for n in PINS},
    'frozenFileCountIndependentlyRehashed': len(freeze['files']),
    'allFrozenFilesRehashedAgainstOwnerFreeze': True, 'noUnexpectedFrozenFiles': True,
    'extractedFileCount': len(records), 'extractedBytes': sum(r['bytes'] for r in records),
    'allExtractedFilesRehashedAgainstFrozenAudit': True,
    'allExtractedFilesIndependentlyBoundToExactGitBlobs': True,
    'documentedArchiveTextConversionsIndependentlyVerified': conversions,
    'unextractedGalleryMemberCount': len(gallery),
    'galleryMemberMetadataIndependentlyComparedToExactGitTree': True,
    'completeOriginalArchiveHashReverified': True, 'noArchiveCopyOrSecondExtractionCreated': True,
    'auditScript': identity(Path(__file__)),
    'scope': 'Independent SHA-256 rehash of every frozen owner file, including the complete original archive, receipts and extracted implementation. Each implementation file was also independently compared to its Git blob; the sole gradlew.bat CRLF archive form was exactly reversed in memory and compared to the retained raw Git blob. Gallery identities were checked against the exact tree without extracting them. Full tar payload and gzip membership validation remains the explicitly identified frozen owner audit; no download, extraction, source change, build, test or device execution occurred.',
}
path = ROOT / 'shared-source-reuse.json'
with path.open('x') as stream:
    json.dump(summary, stream, indent=2)
    stream.write('\n')
print(json.dumps({'receipt': identity(path), 'sourceDirectory': str(source),
                  'sourceFilesVerified': len(records), 'frozenFilesRehashed': len(freeze['files']),
                  'archiveTextConversionsVerified': conversions}, indent=2))
