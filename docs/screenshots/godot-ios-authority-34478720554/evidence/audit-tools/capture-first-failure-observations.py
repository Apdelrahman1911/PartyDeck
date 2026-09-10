"""Preserve exact failure and accepted-dormancy payloads from original XCResult exports."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

BASE = Path('/tmp/partydeck-engine-ci/34478720554')
HEAD = 'c6ea1dd9f7966517fbee87a06b633d01c432c24d'
STORAGE = Path('/root/projects/PartyDeck/artifacts/evidence-storage')

def read(path): return json.loads(path.read_text())
def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
def record(path): return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}

hosts = []
for name, relative, attachments_name, bundle_name, decoded_name in [
    ('authority', 'godot-ios-authority-gameplay/artifacts', 'authority-attachments', 'AuthorityHost.xcresult', '34478720554-xcresult-decoded'),
    ('retained', 'godot-ios-retained-host-test-attempt-1/retained-host-test/artifacts', 'attachments', 'RetainedHost.xcresult', '34478720554-retained-xcresult-decoded'),
]:
    artifacts = BASE / relative
    bundle = artifacts / bundle_name
    attachments = artifacts / attachments_name
    index_path = STORAGE / decoded_name / 'decoded-object-index.json'
    index = read(index_path)
    objects = {Path(item['source']).name.removeprefix('data.'): item for item in index['dataObjects']}
    connection = sqlite3.connect('file:' + str(bundle / 'database.sqlite3') + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    tests = [dict(row) for row in connection.execute('SELECT c.name,c.identifier,r.rowid AS runRow,r.result,r.duration FROM TestCaseRuns r JOIN TestCases c ON r.testCase_fk=c.rowid ORDER BY c.rowid')]
    issues = [dict(row) for row in connection.execute('SELECT testCaseRun_fk,compactDescription,detailedDescription,issueType FROM TestIssues')]
    rows = {row['uuid']: dict(row) for row in connection.execute('SELECT uuid,name,xcResultKitPayloadRefId FROM Attachments')}
    preserved = []
    for case_manifest in read(attachments / 'manifest.json'):
        case = next(test for test in tests if test['identifier'] == case_manifest['testIdentifier'])
        for item in case_manifest['attachments']:
            title = item['suggestedHumanReadableName']
            kind = ('last_rejected_wait' if title.startswith('Last rejected ') else
                    'later_failure_capture' if title.startswith(('Failed authority wait measurements', 'Failed retained observation measurements')) else
                    'accepted_dormant_home' if 'accepted native observation' in title else None)
            if not kind:
                continue
            path = attachments / item['exportedFileName']
            row = rows[path.stem]
            original = objects[row['xcResultKitPayloadRefId']]
            payload = record(path)
            assert payload['sha256'] == original['decodedSha256'] and payload['bytes'] == original['decodedBytes']
            assert digest(Path(original['source'])) == original['sourceSha256']
            value = read(path)
            preserved.append({'kind': kind, 'testIdentifier': case['identifier'], 'testResult': case['result'],
                'attachment': payload, 'name': title, 'timestamp': item.get('timestamp'),
                'xcresultAttachmentUuid': row['uuid'], 'xcresultOriginalName': row['name'],
                'xcresultPayloadRef': row['xcResultKitPayloadRefId'], 'xcresultObject': record(Path(original['source'])),
                'matchesOriginalXcresultPayload': True, 'value': value})
    hosts.append({'host': name, 'tests': tests, 'issues': issues, 'sqlite': record(bundle / 'database.sqlite3'),
        'manifest': record(attachments / 'manifest.json'), 'decodedObjectIndex': record(index_path), 'observations': preserved})

receipt = {'runId': 34478720554, 'headSha': HEAD, 'recordedAtUtc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Exact original exported payloads independently matched to decoded XCResult objects, with original case results. Last rejected observations remain separate from later capture; accepted dormancy is a bounded checkpoint and does not pass a failed case.',
    'hosts': hosts, 'nativeExecutionPerformedHere': False, 'noCrashClaim': False}
target = BASE / 'first-failure-observations.json'
with target.open('x') as stream: stream.write(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'receipt': record(target), 'hosts': [{'host': host['host'], 'observations': [
    {'kind': item['kind'], 'case': item['testIdentifier'], 'attachment': item['attachment']} for item in host['observations']]} for host in hosts]}), flush=True)
