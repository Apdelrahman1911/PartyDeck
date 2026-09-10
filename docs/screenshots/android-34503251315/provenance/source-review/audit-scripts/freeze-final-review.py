"""Rehash current frozen originals and bind the completed scoped API35 review."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath

ROOT = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34503251315')
HEAD = '1cd34a36753ed0112e6684f6525592dab8ef2edb'


def identity(path):
    assert path.is_file() and not path.is_symlink()
    value = sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            value.update(block)
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size, 'sha256': value.hexdigest()}


def read(name):
    return json.loads((ROOT / name).read_text())


assert identity(ROOT / 'original-collection-frozen.json')['sha256'] == '057eb0ff361756f8207ca225f4b4202d0be94cbd050eb6962cf9ff0e814bcad7'
original_freeze = read('original-collection-frozen.json')
assert original_freeze['runId'] == 34503251315 and original_freeze['headSha'] == HEAD
assert identity(ROOT / 'original-collection-files.json') == original_freeze['fileManifest']
originals = read('original-collection-files.json')
assert len(originals) == original_freeze['originalFileCount']
for entry in originals:
    relative = PurePosixPath(entry['path'])
    assert not relative.is_absolute() and '..' not in relative.parts
    assert identity(ROOT / relative) == entry, entry['path']
assert len({row['path'] for row in originals}) == len(originals)
run = read('last-run-status.json')
assert run['id'] == 34503251315 and run['head_sha'] == HEAD and run['run_attempt'] == 1
assert run['status'] == 'completed' and run['conclusion'] == 'success'
unit = read('review/test-and-lint-audit.json')
host = read('review/python-checker-case-audit.json')
assert host['caseCount'] == len(host['cases']) == host['summaries'][0]['count']
assert host['outcomes'] == {'ok': host['caseCount']}
assert unit['totals']['tests'] == unit['case_identity_count']
assert all(unit['totals'][k] == 0 for k in ('failures', 'errors', 'skipped'))
runtime = read('review/runtime-result-triage.json')
assert all(v['status'] == 'passed' and v['phaseExitCode'] == 0 for v in runtime['variants'].values())
assert all(v['engineGameplayRequested'] is False for v in runtime['variants'].values())
captures = read('review/runtime-capture-audit.json')
standard = read('review/standard-ui-xml-audit.json')
assert standard['result'] == read('review/packaged-activation-audit.json')['result'] == 'pass'
assert read('review/collection-integrity-audit.json')['audit_result'] == read('review/package-audit.json')['result'] == 'pass'
gallery = read('review/capture-gallery-mapping.json')
visual = read('review/original-visual-review.json')
assert gallery['imageCount'] == len(gallery['images'])
assert gallery['viewedOriginalCount'] == visual['originalViewCount'] == len(visual['images'])
assert gallery['viewedDerivedCount'] == visual['derivedViewCount'] == 0
assert gallery['categories']['native-session'] == sum(v['completeCaptureCount'] for v in captures['variants'].values())
assert standard['observationCounts'] == {v: a['originalStandardUiObservationCount'] for v, a in captures['variants'].items()}
records = [identity(path) for directory in ('review', 'audit-scripts')
           for path in sorted((ROOT / directory).rglob('*')) if path.is_file()]
manifest = ROOT / 'review-final-files.json'
with manifest.open('x') as stream:
    json.dump(records, stream, indent=2)
    stream.write('\n')
summary = {
    'runId': 34503251315, 'headSha': HEAD, 'attempt': 1,
    'frozenAtUtc': datetime.now(timezone.utc).isoformat(),
    'status': 'review complete; approved for the recorded API35 native session scope',
    'originalFreeze': identity(ROOT / 'original-collection-frozen.json'),
    'originalFileCountReverified': len(originals), 'allOriginalPathHashSizesReverified': True,
    'derivedFileCount': len(records), 'derivedManifest': identity(manifest),
    'review': identity(ROOT / 'review/REVIEW.md'),
    'captureMapping': identity(ROOT / 'review/capture-gallery-mapping.json'),
    'originalVisualReview': identity(ROOT / 'review/original-visual-review.json'),
    'hostTests': {'count': host['caseCount'], 'allOk': True},
    'junit': {'suiteCount': unit['report_count'], **unit['totals']},
    'lintWarnings': unit['lint_warning_count'],
    'nativeChecks': {v: a['checkStatuses'] for v, a in runtime['variants'].items()},
    'nativeProcessReceiptCount': sum(v['processSampleCount'] for v in captures['variants'].values()),
    'nativeCompleteCaptureCount': gallery['categories']['native-session'],
    'standardXmlObservationCount': sum(standard['observationCounts'].values()),
    'originalImageCount': gallery['imageCount'], 'directlyViewedOriginalCount': visual['originalViewCount'],
    'scope': 'All collected originals and completed review artifacts are bound by path, size and SHA-256. Approval covers the actual requested API35 native bootstrap/lifecycle and Standard UI evidence. API35 engine gameplay was not invoked; optimized renderer death was explicitly skipped. Selected original stills, continuous privacy, TalkBack, physical LAN/devices and distribution signing retain the limits stated in REVIEW.md. JUnit, host-test, lint and native runtime counts/outcomes come from this run. The selected prior JNI result applies only through the separately documented identical complete DEX bytes.',
}
output = ROOT / 'review-final-freeze.json'
with output.open('x') as stream:
    json.dump(summary, stream, indent=2)
    stream.write('\n')
print(json.dumps({'freeze': identity(output), 'review': summary['review'],
                  'originalFilesReverified': len(originals), 'derivedFileCount': len(records),
                  'nativeChecks': summary['nativeChecks'], 'junit': summary['junit'],
                  'hostTests': summary['hostTests']}, indent=2))
