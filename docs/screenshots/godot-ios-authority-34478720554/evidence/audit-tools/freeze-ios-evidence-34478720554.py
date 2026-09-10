"""Freeze actual collected outcomes, original bytes and completed read-only audits."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

BASE = Path('/tmp/partydeck-engine-ci/34478720554')
RUN = 34478720554
HEAD = 'c6ea1dd9f7966517fbee87a06b633d01c432c24d'
STORAGE = Path('/root/projects/PartyDeck/artifacts/evidence-storage')

def read(path): return json.loads(path.read_text())
def record(path):
    with path.open('rb') as stream: sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha}
def write_new(path, value):
    with path.open('x') as stream: stream.write(json.dumps(value, indent=2) + '\n')
def verify_record(expected):
    actual = record(Path(expected['path']))
    assert actual['sha256'] == expected['sha256'] and actual['bytes'] == expected['bytes'], expected['path']
    return actual

assert BASE.is_symlink() and BASE.resolve() == (STORAGE / str(RUN)).resolve()
run = read(BASE / 'last-run-status.json')
jobs = read(BASE / 'last-jobs-status.json')['jobs']
contract = read(BASE / 'collection-contract.json')
complete = read(BASE / 'collection-complete.json')
expected = read(BASE / 'coordinator-expected-inputs.json')
assert run['id'] == RUN and run['head_sha'] == HEAD and run['run_attempt'] == 1
assert run['event'] == 'workflow_dispatch' and run['path'] == '.github/workflows/godot-ios-authority-host.yml'
assert run['status'] == 'completed' and complete['conclusion'] == run['conclusion']
assert complete['headSha'] == HEAD and complete['runId'] == RUN and complete['attempt'] == 1
assert complete['missingExpectedArtifacts'] == [] and complete['collectionErrors'] == {}
assert set(complete['downloadedArtifacts']) == set(contract['expectedArtifacts'])
api_artifacts = {item['id']: item for item in read(BASE / 'artifacts.json')['artifacts']}
assert len(api_artifacts) == len(contract['expectedArtifacts']) == 6
artifacts = []
for name in contract['expectedArtifacts']:
    integrity_path = BASE / (name + '.integrity.json')
    integrity = read(integrity_path)
    api = api_artifacts[integrity['artifactId']]
    original = record(Path(integrity['archivePath']))
    assert integrity['runId'] == api['workflow_run']['id'] == RUN
    assert integrity['headSha'] == api['workflow_run']['head_sha'] == HEAD
    assert integrity['name'] == api['name'] == name
    assert integrity['zipDigestMatchesApi'] and integrity['zipSizeMatchesApi']
    assert 'sha256:' + original['sha256'] == integrity['apiDigest'] == integrity['archiveDigest'] == api['digest']
    assert original['bytes'] == integrity['apiBytes'] == integrity['archiveBytes'] == api['size_in_bytes']
    inventory_path = BASE / (name + '.files.json')
    inventory = read(inventory_path)
    assert len(inventory) == integrity['extractedFileCount']
    for item in inventory:
        actual = record(BASE / name / item['path'])
        assert actual['bytes'] == item['bytes'] and actual['sha256'] == item['sha256'], item['path']
    artifacts.append({'name': name, 'artifactId': api['id'], 'originalArchive': original,
        'apiDigest': api['digest'], 'apiBytes': api['size_in_bytes'], 'zipDigestAndSizeReverifiedAtFreeze': True,
        'extractedFileCount': len(inventory), 'extractedBytes': sum(item['bytes'] for item in inventory),
        'allExtractedHashesAndSizesReverifiedAtFreeze': True,
        'extractedSha256Inventory': record(inventory_path), 'originalIntegrityReceipt': record(integrity_path)})
    print(json.dumps({'originalReverified': name, 'files': len(inventory)}), flush=True)

logs = []
for job in jobs:
    assert job['status'] == 'completed' and job['head_sha'] == HEAD and job['run_id'] == RUN
    path = BASE / f"job-{job['id']}.log"
    collection_path = BASE / f"job-{job['id']}.collected.json"
    collection = read(collection_path)
    original = verify_record(collection)
    assert collection['headSha'] == HEAD and collection['runId'] == RUN
    logs.append({'jobId': job['id'], 'name': job['name'], 'status': job['status'],
        'conclusion': job['conclusion'], 'failedSteps': [step['name'] for step in job['steps'] if step['conclusion'] == 'failure'],
        'originalLog': original, 'collectionReceipt': record(collection_path)})
assert len(logs) == 5 and {job['jobId'] for job in logs} == set(complete['savedJobLogs'])

producer = read(BASE / 'producer-input-evidence-summary.json')
retained_input = read(BASE / 'retained-input-evidence-summary.json')
retained_package = read(BASE / 'retained-package-evidence-summary.json')
retained = read(BASE / 'retained-attachment-evidence-summary.json')
authority = read(BASE / 'authority-attachment-evidence-summary.json')
source_observations = read(BASE / 'source-currentness-observation-audit.json')
native_logs = read(BASE / 'native-log-evidence-summary.json')
for audit in [producer, retained_input, retained_package, retained, source_observations]:
    assert audit['runId'] == RUN and audit['headSha'] == HEAD and all(check['passed'] for check in audit['checks'])
assert all(read(BASE / 'authority-package-evidence-summary.json')['checks'].values())
assert retained['attachmentCount'] == retained['xcresultHashMatchedAttachments']
assert authority['attachmentCount'] == authority['xcresultHashMatchedAttachments'] + authority['xcresultIssueTextMatchedExports']
assert len(retained['tests']) == 3 and len(authority['tests']) == 5
for audit in [retained, authority]:
    assert Counter(test['result'] for test in audit['tests']) == Counter(audit['testResults'])
    for attachment in audit['attachments']:
        verify_record(attachment)

decoded_indexes = []
for suffix in ['-retained-xcresult-decoded', '-xcresult-decoded']:
    path = STORAGE / (str(RUN) + suffix) / 'decoded-object-index.json'
    index = read(path)
    for obj in index['dataObjects']:
        original = record(Path(obj['source']))
        decoded = record(Path(obj['decoded']))
        assert original['bytes'] == obj['sourceBytes'] and original['sha256'] == obj['sourceSha256']
        assert decoded['bytes'] == obj['decodedBytes'] and decoded['sha256'] == obj['decodedSha256']
    for stream in index['appStreams']:
        actual = record(Path(stream['appOutputLog']))
        assert actual['sha256'] == stream['decodedSha256'] and actual['bytes'] == stream['decodedBytes']
    decoded_indexes.append({**record(path), 'allOriginalAndDecodedObjectsReverifiedAtFreeze': True, 'objectCount': len(index['dataObjects'])})

source_archive = read(BASE / 'source-archive.json')
source = record(Path(source_archive['archivePath']))
assert source['sha256'] == source_archive['sha256'] and source['bytes'] == source_archive['bytes'] and source_archive['headSha'] == HEAD
assert producer['pack']['sha256'] == expected['packSha256'] and producer['pack']['bytes'] == expected['packBytes'] and producer['pack']['entries'] == expected['packEntries']
assert producer['moduleSnapshotSha256'] == expected['moduleSnapshotSha256']
assert record(BASE / 'expected-native-freeze-v6.json')['sha256'] == expected['nativeFreezeSha256']
previous_freeze = record(Path('/tmp/partydeck-engine-ci/34473325295/collection-evidence-frozen.json'))
assert previous_freeze['sha256'] == '1a4421450bc8d64a613e33dc5389d80ea1073bf2bd63c1ff2b123239deb6a4e6'

command_attempts = []
for path in sorted((BASE / 'audit-commands').glob('*.json')):
    if path.stem == 'collection-freeze':
        continue
    command = read(path)
    verify_record(command['log'])
    assert record(Path(command['command'][3]))['sha256'] == command['auditorSha256']
    command_attempts.append({'receipt': record(path), 'exitCode': command['exitCode'], 'log': command['log']})
required = ['producers', 'source-observations', 'decode-authority', 'decode-retained', 'retained-preservation',
    'retained-inputs', 'retained-package', 'retained-attachments', 'authority-v2', 'native-logs', 'first-failure-observations']
assert all(read(BASE / 'audit-commands' / (name + '.json'))['exitCode'] == 0 for name in required)
failed_attempts = [item for item in command_attempts if item['exitCode'] != 0]
assert len(failed_attempts) == 1 and Path(failed_attempts[0]['receipt']['path']).stem == 'authority'

early_probes = []
for path in sorted((BASE / 'early-log-probes').glob('*.json')):
    probe = read(path)
    response = verify_record(probe['response'])
    final_log = record(BASE / f"job-{probe['jobId']}.log")
    early_probes.append({'probeReceipt': record(path), 'originalResponse': response, 'returnCode': probe['returnCode'],
        'finalJobLog': final_log, 'identicalToFinalJobLog': response['sha256'] == final_log['sha256'] and response['bytes'] == final_log['bytes']})

def observation(item):
    value = item['value']
    result = {'originalAttachment': record(Path(item['file'])), 'name': item['name'], 'timestamp': item['timestamp']}
    for key in ['timeoutSeconds', 'elapsedSeconds']:
        if key in value: result[key] = value[key]
    return result

case_overviews = []
for host, audit in [('retained', retained), ('authority', authority)]:
    for case in audit['tests']:
        overview = {'host': host, 'identifier': case['identifier'], 'result': case['result'],
            'durationSeconds': case['duration'], 'issues': case['issues'], 'attachmentCount': case['attachmentCount'],
            'lastRejectedWaitObservations': [observation(item) for item in case['lastRejectedWaitObservations']]}
        if host == 'retained':
            overview.update(independentlyVerifiedScope=case['independentlyVerifiedScope'],
                dormantIntervalDurationsSeconds=[item['verifiedDurationSeconds'] for item in case['dormantIntervals']],
                runID=case['runID'], applicationJournal=case['applicationJournal'],
                acceptedDormantHomeObservations=[observation(item) for item in case['acceptedDormantHomeObservations']])
        else:
            overview.update(independentChecks=case['independentChecks'], actualGeometryByAction=case['geometryByAction'])
        case_overviews.append(overview)

authority_all_passed = all(test['result'] == 'Success' for test in authority['tests'])
qualification = {'retainedEngineLifecycleQualified': retained['retainedEngineLifecycleQualified'],
    'sameProcessReentryQualified': retained['sameProcessReentryQualified'],
    'allFiveAuthoritySimulatorFixtureCasesPassed': authority_all_passed,
    'allAuthorityGameplayCasesQualified': authority_all_passed,
    'authorityQualificationScope': 'Only each successful recorded case and its independently audited observations; failed cases remain failed.',
    'passingAuthorityCases': [test['identifier'] for test in authority['tests'] if test['result'] == 'Success'],
    'secureDefaultFullMatchQualified': False, 'kmpFactoryQualified': False,
    'deviceMetalQualified': False, 'physicalMotionShutdownQualified': False,
    'realAudioInterruptionQualified': False, 'simulatorRuntimeExecuted': True,
    'cleanNativeLogClaim': False, 'noCrashClaim': False}
receipt_names = ['collection-contract.json', 'collector-process.json', 'collection-complete.json',
    'last-run-status.json', 'last-jobs-status.json', 'artifacts.json', 'coordinator-expected-inputs.json',
    'source-archive.json', 'source-delta-from-34473325295.json', 'source-currentness-observation-audit.json',
    'native-runtime-and-retained-test-delta.patch', 'expected-native-freeze-v6.json', 'producer-input-evidence-summary.json',
    'retained-preservation-audit.json', 'retained-input-evidence-summary.json', 'retained-package-evidence-summary.json',
    'retained-attachment-evidence-summary.json', 'authority-package-evidence-summary.json',
    'authority-attachment-evidence-summary.json', 'first-failure-observations.json',
    'native-log-evidence-summary.json', 'research/references.json']
receipt_index = [record(BASE / name) for name in receipt_names]
scripts = [record(path) for path in sorted((BASE / 'audit-tools').glob('*.py'))]
scripts += [record(BASE / name) for name in ['monitor-ios-hosts-34478720554.py', 'collect-exact-source.py']]
assert record(BASE / 'monitor-ios-hosts-34478720554.py')['sha256'] == read(BASE / 'collector-process.json')['collectorSha256']
native_log_summary = [{'host': host['host'], 'severityCounts': host['nativeSeverityCounts'],
    'classificationCounts': host['nativeClassificationCounts'], 'genericXctestRestartMessages': len(host['xctestGenericRestartLines']),
    'cleanNativeLogClaim': False, 'noCrashClaim': False} for host in native_logs['hosts']]
summary = {'schemaVersion': 1, 'runId': RUN, 'headSha': HEAD, 'attempt': 1,
    'workflow': run['path'], 'workflowUrl': run['html_url'], 'event': run['event'], 'conclusion': run['conclusion'],
    'expectedInputs': contract['expectedInputs'], 'verifiedInputsEvidence': record(BASE / 'retained-input-evidence-summary.json'),
    'collectedAtUtc': complete['completedAtUtc'], 'frozenAtUtc': datetime.now(timezone.utc).isoformat(),
    'collectorScope': 'Read-only GitHub/API/source collection and derived evidence audits. No build, export, dispatch, Git command or shared product-source edit.',
    'sourceArchive': source, 'artifactCount': len(artifacts), 'artifacts': artifacts,
    'extractedFileCount': sum(item['extractedFileCount'] for item in artifacts),
    'extractedBytes': sum(item['extractedBytes'] for item in artifacts), 'jobLogs': logs,
    'jobConclusionCounts': dict(Counter(job['conclusion'] for job in jobs)),
    'auditCheckCounts': {'producer': len(producer['checks']), 'retainedInputs': len(retained_input['checks']),
        'retainedPackage': len(retained_package['checks']), 'retainedAttachments': len(retained['checks']),
        'sourceObservations': len(source_observations['checks'])},
    'rendererPackSha256': producer['pack']['sha256'], 'rendererPackBytes': producer['pack']['bytes'],
    'rendererPackEntries': producer['pack']['entries'], 'nativeModuleSnapshotSha256': producer['moduleSnapshotSha256'],
    'upstreamPatchNames': producer['patches'], 'optionalMousePatchIncluded': source_observations['optionalStartupMousePatchIncluded'],
    'threeDDemandOptimizationIncluded': source_observations['threeDDemandOptimizationIncluded'],
    'nativeTestResults': case_overviews, 'nativeTestCounts': dict(Counter(case['result'] for case in case_overviews)),
    'exportedAttachmentCount': retained['attachmentCount'] + authority['attachmentCount'],
    'originalXcresultMatchedAttachments': retained['xcresultHashMatchedAttachments'] + authority['xcresultHashMatchedAttachments'],
    'originalXcresultIssueTextMatchedExports': authority['xcresultIssueTextMatchedExports'],
    'retainedAttachmentCounts': {'total': retained['attachmentCount'], 'pngs': retained['pngCount'],
        'measurements': retained['measurementCount'], 'touchCandidates': retained['touchCandidateCount'],
        'dormantIntervals': retained['dormantIntervalCount'], 'lastRejectedWaitObservations': retained['lastRejectedWaitObservationCount'],
        'acceptedDormantHomeObservations': sum(len(test['acceptedDormantHomeObservations']) for test in retained['tests'])},
    'authorityAttachmentCounts': {'total': authority['attachmentCount'], 'pngs': authority['pngCount'],
        'measurements': authority['jsonMeasurementCount'], 'actualTouchGeometries': authority['jsonTouchGeometryCount'],
        'observedControls': authority['jsonObservedControlCount'], 'lastRejectedWaitObservations': authority['lastRejectedWaitObservationCount'],
        'issueTextExports': authority['xcresultIssueTextMatchedExports']},
    'nativeLogSummary': native_log_summary, 'qualification': qualification,
    'receiptIndex': receipt_index, 'preservedAuditorScripts': scripts, 'auditCommandAttempts': command_attempts,
    'auditAdapterCorrection': 'The original Authority audit attempt is preserved. Successor v2 separately verifies a timestamp-free generated issue-description export against original TestIssues text; all true attachment payloads are matched to original XCResult objects.',
    'earlyLogProbeCorrelations': early_probes,
    'primarySourceResearch': [record(path) for path in sorted((BASE / 'research').rglob('*')) if path.is_file()],
    'decodedObjectIndexes': decoded_indexes, 'previousCollectionFreezeReverifiedUnchanged': previous_freeze,
    'limitations': [
        'Actual test results come from the original native bundles. A successful selected checkpoint does not promote a failed case.',
        'The retained background case accepted the exact dormant Home/activate payload, then failed its separate 60-second second-3D entry wait. The stale reentry case failed its 15-second diagnostic wait while warming. Original rejected measurements and later capture remain separate.',
        'The Authority 2D/200% case reports an Xcode application-launch timeout before initial app measurements. No underlying OS cause or app-start state is inferred from that issue text.',
        'Both Authority 3D cases failed recorded diagnostic predicates after native input. Source diagnosis and pixel review are separate supplements; no cause or later-observation acceptance is inferred here.',
        'The passing repeated-entry case uses its existing 60-second entry timeout; it does not qualify the failed 15-second close-completion reentry path.',
        'AX query duration, published snapshots and total XCTest duration do not isolate main-thread waiting, accessibility traversal, frame work, texture upload or scheduling cost. No performance improvement is claimed.',
        'The demand-redraw implementation is present in this pack. The optional startup-mouse patch is absent. Root-reported packed assertion totals and review hash prefixes remain coordinator reports, not independently established native qualifications.',
        'The success-only Authority execution receipt is not present in this failed run; actual outcomes are independently read from XCResult.',
        'Dormant interval auditing verifies recorded endpoint measurements and sample count, not every intermediate AX read. Retained touch candidates precede final eligibility checks and are not actual tap counts.',
        'Home evidence preserves raw application state alongside observed SpringBoard dock icons.',
        'PCK source fingerprints, entries and producer/consumer bytes are audited; compiled GDScript is not reverse-decoded to claim literal source equality.',
        retained_input['stagedArchiveLimit'],
        'Severity-tagged errors, RGBA conversion warnings and ambiguous XCTest restart messages remain in the preserved logs. No clean-log or no-crash conclusion is claimed.',
        'Production KMP factory integration, secure-default full matches, physical sensors, real audio interruption and physical-device Metal gates are outside these passing case observations.',
        'Later diagnosis, correction and review receipts must be separate hashed supplements. The previous frozen collection remains unchanged.',
    ]}
summary_path = BASE / 'collection-evidence-summary.json'
write_new(summary_path, summary)
freeze = {'schemaVersion': 1, 'runId': RUN, 'headSha': HEAD, 'attempt': 1,
    'frozenAtUtc': summary['frozenAtUtc'], 'conclusion': run['conclusion'], 'frozenSummary': record(summary_path),
    'receiptIndex': receipt_index, 'artifactOriginals': [{'name': item['name'], 'artifactId': item['artifactId'], **item['originalArchive']} for item in artifacts],
    'preservedAuditorScripts': scripts, 'qualification': qualification,
    'previousCollectionFreezeReverifiedUnchanged': previous_freeze,
    'policy': 'Preserve these receipts, original artifacts and derived payloads unchanged. Add later diagnoses, corrections, command records or native outcomes as separately hashed successor supplements.'}
freeze_path = BASE / 'collection-evidence-frozen.json'
write_new(freeze_path, freeze)
print(json.dumps({'frozen': record(freeze_path), 'summary': record(summary_path), 'originalZipCount': len(artifacts),
    'extractedFileCount': summary['extractedFileCount'], 'exportedAttachments': summary['exportedAttachmentCount'],
    'matchedPayloads': summary['originalXcresultMatchedAttachments'], 'matchedIssueTextExports': summary['originalXcresultIssueTextMatchedExports'],
    'caseCounts': summary['nativeTestCounts'], 'nativeLogs': native_log_summary}, indent=2), flush=True)
