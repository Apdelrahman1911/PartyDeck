"""Independently compare preserved ZIP/tar bytes, extracted files and API identities."""
from pathlib import Path, PurePosixPath
from hashlib import sha256
import json
import os
import stat
import tarfile
import zipfile

ROOT = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34503251315')
REVIEW = ROOT / 'review'
REVISION = '1cd34a36753ed0112e6684f6525592dab8ef2edb'


def stream_hash(stream):
    h, count = sha256(), 0
    while block := stream.read(1024 * 1024):
        h.update(block)
        count += len(block)
    return count, h.hexdigest()


def file_hash(path):
    with path.open('rb') as stream:
        return stream_hash(stream)[1]


def identity(path):
    return {'file': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size, 'sha256': file_hash(path)}


run_path = ROOT / 'last-run-status.json'
run = json.loads(run_path.read_text())
assert run['id'] == 34503251315 and run['head_sha'] == REVISION and run['run_attempt'] == 1
assert run['status'] == 'completed' and run['conclusion'] in ('success', 'failure')
assert run['event'] == 'workflow_dispatch' and run['path'] == '.github/workflows/validate.yml'
jobs_path = ROOT / 'last-jobs-status.json'
jobs = json.loads(jobs_path.read_text())['jobs']
assert len(jobs) == 4
assert all(j['run_id'] == run['id'] and j['head_sha'] == REVISION and j['run_attempt'] == 1 for j in jobs)
android = next(j for j in jobs if j['id'] == 102958971991)
assert android['conclusion'] == run['conclusion']
assert all(s['status'] == 'completed' for s in android['steps'])
assert all(j['conclusion'] == 'skipped' for j in jobs if j['id'] != android['id'])
complete_path = ROOT / 'collection-complete.json'
complete = json.loads(complete_path.read_text())
assert not complete['missingExpectedArtifacts'] and not complete['collectionErrors']
assert complete['savedJobLogs'] == [android['id']]
assert Path('/tmp/partydeck-engine-ci/34503251315').resolve() == ROOT.resolve()
assert not list((ROOT / '.download-tmp').rglob('*'))
metadata_path = ROOT / 'artifacts.json'
api_artifacts = json.loads(metadata_path.read_text())['artifacts']
assert {a['name'] for a in api_artifacts} == {'android-jvm-reports', 'android-packages-and-shrinker-reports'}
artifact_records = []
for artifact in api_artifacts:
    name = artifact['name']
    assert artifact['workflow_run']['id'] == run['id'] and artifact['workflow_run']['head_sha'] == REVISION
    archive = ROOT / 'artifact-zips' / f"{artifact['id']}-{name}.zip"
    archive_identity = identity(archive)
    assert archive_identity['bytes'] == artifact['size_in_bytes']
    assert 'sha256:' + archive_identity['sha256'] == artifact['digest']
    manifest_path = ROOT / (name + '.files.json')
    manifest = json.loads(manifest_path.read_text())
    expected = {entry['path']: entry for entry in manifest}
    assert len(expected) == len(manifest)
    extracted = ROOT / name
    actual_paths = {p.relative_to(extracted).as_posix() for p in extracted.rglob('*') if p.is_file()}
    assert actual_paths == set(expected)
    verified = []
    with zipfile.ZipFile(archive) as package:
        infos = package.infolist()
        assert len(infos) == len({i.filename for i in infos})
        historical = [i.filename for i in infos if i.filename.startswith(('docs/screenshots/', 'artifacts/'))]
        assert not historical, historical
        assert {i.filename for i in infos if not i.is_dir()} == set(expected)
        for info in infos:
            path = PurePosixPath(info.filename)
            assert not path.is_absolute() and '..' not in path.parts
            assert not stat.S_ISLNK(info.external_attr >> 16)
            if info.is_dir():
                continue
            with package.open(info) as stream:
                size, digest = stream_hash(stream)  # zipfile also validates CRC while reading.
            record = expected[info.filename]
            assert (size, digest) == (record['bytes'], record['sha256'])
            local = extracted / info.filename
            assert not local.is_symlink() and local.stat().st_size == size and file_hash(local) == digest
            verified.append(record)
    integrity_path = ROOT / (name + '.integrity.json')
    integrity = json.loads(integrity_path.read_text())
    assert integrity['archiveDigest'] == artifact['digest']
    assert integrity['extractedFileCount'] == len(verified)
    artifact_records.append({'id': artifact['id'], 'name': name, 'archive': archive_identity,
        'published_api_digest': artifact['digest'], 'published_api_size': artifact['size_in_bytes'],
        'file_manifest': identity(manifest_path), 'collector_integrity_receipt': identity(integrity_path),
        'independently_verified_file_count': len(verified),
        'all_zip_entry_crcs_and_sha256_match_manifest_and_extracted_bytes': True,
        'all_extracted_paths_match_original_zip': True,
        'excluded_historical_gallery_or_root_artifact_member_count': len(historical),
        'original_zip_names_contain_no_docs_screenshots_or_root_artifacts': True})
    print(json.dumps({'artifact': name, 'verified_files': len(verified), 'sha256': archive_identity['sha256']}), flush=True)

log_receipt_path = ROOT / 'job-102958971991.collected.json'
log_receipt = json.loads(log_receipt_path.read_text())
log_identity = identity(ROOT / 'job-102958971991.log')
assert (log_identity['bytes'], log_identity['sha256']) == (log_receipt['bytes'], log_receipt['sha256'])
assert log_receipt['headSha'] == REVISION and log_receipt['jobId'] == android['id']
summary = {'schema_version': 1, 'audit_result': 'pass', 'run_id': run['id'], 'source_revision': REVISION,
    'run': identity(run_path), 'jobs': identity(jobs_path), 'artifact_api_metadata': identity(metadata_path),
    'collector_completion': identity(complete_path), 'artifacts': artifact_records,
    'source': {'audit': 'See separate hash-bound shared-source-reuse.json; no second archive or extraction is created by this run.'},
    'android_job_log': log_identity, 'android_job_log_receipt': identity(log_receipt_path),
    'tmp_alias_resolves_to_workspace_storage': True, 'download_temporary_directory_empty': True,
    'ios_jobs': [{'id': j['id'], 'name': j['name'], 'conclusion': j['conclusion']}
                 for j in jobs if j['id'] != android['id']],
    'limits': 'File integrity and exact source/run attribution only; actual Android session outcome is preserved, and successful iOS/comparison behavior is not inferred.'}
out = REVIEW / 'collection-integrity-audit.json'
assert not out.exists(), out
out.write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({'receipt': identity(out), 'artifact_file_count': sum(a['independently_verified_file_count'] for a in artifact_records)}, indent=2), flush=True)
