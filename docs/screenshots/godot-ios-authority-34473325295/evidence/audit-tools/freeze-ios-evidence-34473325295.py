"""Freeze original run evidence and completed independent audits without rewriting inputs."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

BASE = Path('/tmp/partydeck-engine-ci/34473325295')
HEAD = '0f666e0ab7fdce63d5fa668442dae1c9fda86a1d'

def read(path): return json.loads(path.read_text())
def record(path):
    with path.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest}
def write_new(path, value):
    with path.open('x') as stream: stream.write(json.dumps(value, indent=2) + '\n')

run = read(BASE / 'last-run-status.json')
jobs = read(BASE / 'last-jobs-status.json')['jobs']
contract = read(BASE / 'collection-contract.json')
complete = read(BASE / 'collection-complete.json')
assert run['id'] == 34473325295 and run['head_sha'] == HEAD and run['run_attempt'] == 1
assert run['event'] == 'workflow_dispatch' and run['path'] == '.github/workflows/godot-ios-authority-host.yml'
assert run['status'] == 'completed' and run['conclusion'] == 'failure'
assert complete['headSha'] == HEAD and complete['attempt'] == 1
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
    assert integrity['runId'] == 34473325295 and integrity['headSha'] == HEAD
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
        'apiDigest': api['digest'], 'apiBytes': api['size_in_bytes'],
        'zipDigestAndSizeReverifiedAtFreeze': True,
        'extractedFileCount': len(inventory), 'extractedBytes': sum(item['bytes'] for item in inventory),
        'allExtractedHashesAndSizesReverifiedAtFreeze': True,
        'extractedSha256Inventory': record(inventory_path), 'originalIntegrityReceipt': record(integrity_path)})
logs = []
for job in jobs:
    path = BASE / f"job-{job['id']}.log"
    original = record(path)
    collection_path = BASE / f"job-{job['id']}.collected.json"
    collection = read(collection_path)
    assert original['sha256'] == collection['sha256'] and original['bytes'] == collection['bytes']
    assert collection['headSha'] == HEAD and collection['runId'] == 34473325295
    logs.append({'jobId': job['id'], 'name': job['name'], 'status': job['status'],
        'conclusion': job['conclusion'], 'failedSteps': [step['name'] for step in job['steps'] if step['conclusion'] == 'failure'],
        'originalLog': original, 'collectionReceipt': record(collection_path)})
assert len(logs) == 5 and Counter(job['conclusion'] for job in jobs) == Counter({'success': 4, 'failure': 1})

producer = read(BASE / 'producer-input-evidence-summary.json')
retained_input = read(BASE / 'retained-input-evidence-summary.json')
retained_package = read(BASE / 'retained-package-evidence-summary.json')
retained = read(BASE / 'retained-attachment-evidence-summary.json')
authority = read(BASE / 'authority-attachment-evidence-summary.json')
authority_execution = read(BASE / 'authority-execution-evidence-summary.json')
native_logs = read(BASE / 'native-log-evidence-summary.json')
for audit in [producer, retained_input, retained_package, retained, authority_execution]:
    assert all(check['passed'] for check in audit['checks'])
assert all(read(BASE / 'authority-package-evidence-summary.json')['checks'].values())
assert retained['attachmentCount'] == retained['xcresultHashMatchedAttachments'] == 112
assert authority['attachmentCount'] == authority['xcresultHashMatchedAttachments'] == 404
assert retained['testResults'] == {'Failure': 2, 'Success': 1}
assert authority['testResults'] == {'Success': 5}
case_overviews = []
for kind, audit in [('retained', retained), ('authority', authority)]:
    for case in audit['tests']:
        overview = {'host': kind, 'identifier': case['identifier'], 'result': case['result'],
            'durationSeconds': case['duration'], 'issues': case['issues'], 'attachmentCount': case['attachmentCount']}
        if kind == 'retained':
            overview.update(independentlyVerifiedScope=case['independentlyVerifiedScope'],
                dormantIntervalDurationsSeconds=[item['verifiedDurationSeconds'] for item in case['dormantIntervals']],
                runID=case['runID'], applicationJournal=case['applicationJournal'],
                lastRejectedWaitObservations=case['lastRejectedWaitObservations'])
        else:
            overview.update(independentChecks=case['independentChecks'], actualGeometryByAction=case['geometryByAction'])
        case_overviews.append(overview)
assert Counter(case['result'] for case in case_overviews) == Counter({'Success': 6, 'Failure': 2})
source_archive = read(BASE / 'source-archive.json')
source = record(Path(source_archive['archivePath']))
assert source['sha256'] == source_archive['sha256'] and source['bytes'] == source_archive['bytes']
assert source_archive['headSha'] == HEAD
assert read(BASE / 'early-retained-members/whole-zip-correlation.json')['wholeZipApiDigestVerified']
assert record(BASE / 'external-supplements/retained-failure-diagnosis.json')['sha256'] == '64c76dfb725af4ce205f252f4018618eb21f36652c4d6e5824433037bb54111d'

receipt_names = [
    'collection-contract.json', 'collector-process.json', 'collection-complete.json',
    'last-run-status.json', 'last-jobs-status.json', 'artifacts.json',
    'source-archive.json', 'source-delta-from-34464316979.json', 'source-currentness-observation-audit.json',
    'expected-native-freeze-v5.json', 'producer-input-evidence-summary.json',
    'retained-preservation-audit.json', 'retained-input-evidence-summary.json', 'retained-package-evidence-summary.json',
    'retained-attachment-evidence-summary.json', 'authority-package-evidence-summary.json',
    'authority-attachment-evidence-summary.json', 'authority-execution-evidence-summary.json',
    'native-log-evidence-summary.json', 'research/references.json',
    'early-retained-members/range-member-evidence.json', 'early-retained-members/whole-zip-correlation.json',
    'external-supplements/preservation-receipt.json', 'external-supplements/retained-failure-diagnosis.json',
]
receipt_index = [record(BASE / name) for name in receipt_names]
scripts = [record(path) for path in sorted((BASE / 'audit-tools').glob('*.py'))]
scripts += [record(BASE / name) for name in ['monitor-ios-hosts-34473325295.py', 'collect-exact-source.py']]
assert record(BASE / 'monitor-ios-hosts-34473325295.py')['sha256'] == read(BASE / 'collector-process.json')['collectorSha256']
command_receipts = [record(path) for path in sorted((BASE / 'audit-commands').iterdir()) if path.is_file()]
primary_research = [record(path) for path in sorted((BASE / 'research').rglob('*')) if path.is_file()]
decoded_indexes = [record(Path('/root/projects/PartyDeck/artifacts/evidence-storage') / name / 'decoded-object-index.json')
    for name in ['34473325295-retained-xcresult-decoded', '34473325295-xcresult-decoded']]
qualification = {
    'retainedEngineLifecycleQualified': retained['retainedEngineLifecycleQualified'],
    'sameProcessReentryQualified': retained['sameProcessReentryQualified'],
    'allFiveAuthoritySimulatorFixtureCasesPassed': True,
    'allAuthorityGameplayCasesQualified': True,
    'authorityQualificationScope': 'Four reference-seed-2 matches in 2D/3D at normal/200% text, plus secure launch and renderer exit, on the recorded Simulator.',
    'secureDefaultFullMatchQualified': False, 'kmpFactoryQualified': False,
    'deviceMetalQualified': False, 'physicalMotionShutdownQualified': False,
    'realAudioInterruptionQualified': False, 'simulatorRuntimeExecuted': True,
    'cleanNativeLogClaim': False, 'noCrashClaim': False,
}
summary = {
    'schemaVersion': 1, 'runId': 34473325295, 'headSha': HEAD, 'attempt': 1,
    'workflow': run['path'], 'workflowUrl': run['html_url'], 'event': run['event'], 'conclusion': run['conclusion'],
    'expectedInputs': {'host': 'both', 'retained_stage': 'test'},
    'verifiedInputsEvidence': record(BASE / 'retained-input-evidence-summary.json'),
    'collectedAtUtc': complete['completedAtUtc'], 'frozenAtUtc': datetime.now(timezone.utc).isoformat(),
    'collectorScope': 'Read-only GitHub/API/source collection and derived evidence audits. No build, export, dispatch, Git command or shared product-source edit.',
    'sourceArchive': source, 'artifactCount': len(artifacts), 'artifacts': artifacts,
    'extractedFileCount': sum(item['extractedFileCount'] for item in artifacts),
    'extractedBytes': sum(item['extractedBytes'] for item in artifacts), 'jobLogs': logs,
    'auditCheckCounts': {'producer': len(producer['checks']), 'retainedInputs': len(retained_input['checks']),
        'retainedPackage': len(retained_package['checks']), 'retainedAttachments': len(retained['checks']),
        'authorityExecutionReceipt': len(authority_execution['checks'])},
    'rendererPackSha256': producer['pack']['sha256'], 'rendererPackBytes': producer['pack']['bytes'],
    'rendererPackEntries': producer['pack']['entries'], 'nativeModuleSnapshotSha256': producer['moduleSnapshotSha256'],
    'upstreamPatchNames': producer['patches'], 'optionalMousePatchIncluded': False, 'threeDDemandOptimizationIncluded': False,
    'nativeTestResults': case_overviews, 'nativeTestCounts': dict(Counter(case['result'] for case in case_overviews)),
    'originalXcresultMatchedAttachments': retained['attachmentCount'] + authority['attachmentCount'],
    'retainedAttachmentCounts': {'total': retained['attachmentCount'], 'pngs': retained['pngCount'],
        'measurements': retained['measurementCount'], 'touchCandidates': retained['touchCandidateCount'],
        'dormantIntervals': retained['dormantIntervalCount'], 'lastRejectedWaitObservations': retained['lastRejectedWaitObservationCount']},
    'authorityAttachmentCounts': {'total': authority['attachmentCount'], 'pngs': authority['pngCount'],
        'measurements': authority['jsonMeasurementCount'], 'actualTouchGeometries': authority['jsonTouchGeometryCount'],
        'observedControls': authority['jsonObservedControlCount']},
    'nativeLogSummary': [{'host': host['host'], 'severityCounts': host['nativeSeverityCounts'],
        'classificationCounts': host['nativeClassificationCounts'],
        'genericXctestRestartMessages': len(host['xctestGenericRestartLines']),
        'cleanNativeLogClaim': False, 'noCrashClaim': False} for host in native_logs['hosts']],
    'qualification': qualification, 'receiptIndex': receipt_index, 'preservedAuditorScripts': scripts,
    'auditCommandsAndOutputs': command_receipts, 'primarySourceResearch': primary_research,
    'decodedObjectIndexes': decoded_indexes,
    'limitations': [
        'Both native hosts compiled, linked and executed. Authority passed five of five; retained passed one of three. The overall run remains failed.',
        'The retained background case fails its immediate native applicationActive assertion after dormant Home/activate. The exact returned dictionary was not attached; earlier dormant/Home evidence cannot substitute.',
        'The reentry case rejects the second 3D presentation while privacyCoverVisible remains true despite sceneStateApplied=true. Its original 15-second wait records 23.467616 seconds elapsed and a 10.262874-second last metrics query.',
        'A later captured read of the same lifetime has the cover removed. It does not satisfy the original deadline, and no old-handle result is established by that later read.',
        'The passing repeated-entry test uses a distinct 60-second entry timeout; it does not qualify the failed 15-second close-completion switch case.',
        'AX query duration, published snapshots and overall XCTest duration do not isolate native frame, renderer, texture, upload or scheduling cost. No measured performance improvement is claimed.',
        'The separate 3D demand optimization and optional physical-mouse startup guard are absent from these compiled inputs.',
        'Authority passing reference matches establish their recorded Simulator fixture scope. Secure default full-match behavior, production KMP integration, retained reentry and physical-device gates remain separate.',
        'Dormant interval auditing verifies recorded endpoint measurements and sample count; it does not reconstruct every intermediate AX read.',
        'Retained touch candidates precede the final input eligibility check and are not actual tap counts.',
        'Home evidence preserves raw application state even when it reports foreground alongside observed SpringBoard dock icons.',
        'PCK source fingerprints, entries and producer/consumer bytes are audited; .gdc bytecode is not reverse-decoded to claim literal source equality.',
        'Two top-level staged native archives are absent from retained preservation. Their CI receipts match original producer archives; absent staged paths are not independently reread.',
        'Fourteen unsupported-mouse errors, sixteen RGBAFloat-to-RGBAHalf warnings and two ambiguous retained XCTest restart messages remain in the preserved output. No clean-log or no-crash conclusion is claimed.',
        'Independent source diagnoses and proposed corrections are separate supplements and do not rewrite this run outcome.',
    ],
}
summary_path = BASE / 'collection-evidence-summary.json'
write_new(summary_path, summary)
freeze = {'schemaVersion': 1, 'runId': 34473325295, 'headSha': HEAD, 'attempt': 1,
    'frozenAtUtc': summary['frozenAtUtc'], 'conclusion': run['conclusion'], 'frozenSummary': record(summary_path),
    'receiptIndex': receipt_index, 'artifactOriginals': [{'name': item['name'], 'artifactId': item['artifactId'],
        **item['originalArchive']} for item in artifacts], 'preservedAuditorScripts': scripts,
    'qualification': qualification,
    'policy': 'Preserve these receipts, original artifacts and derived payloads unchanged. Add later diagnoses, corrections or native outcomes as separately hashed successor supplements.'}
freeze_path = BASE / 'collection-evidence-frozen.json'
write_new(freeze_path, freeze)
print(json.dumps({'frozen': record(freeze_path), 'summary': record(summary_path),
    'originalZipCount': len(artifacts), 'extractedFileCount': summary['extractedFileCount'],
    'matchedAttachments': summary['originalXcresultMatchedAttachments'], 'caseCounts': summary['nativeTestCounts']}, indent=2), flush=True)
