"""Correlate retained CI inputs and package using completed producer audit; no native execution."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import plistlib
import re
import struct
import tarfile
BASE = Path('/tmp/partydeck-engine-ci/34473325295')
HEAD = '0f666e0ab7fdce63d5fa668442dae1c9fda86a1d'
SOURCE = BASE / 'source-0f666e0'
HOST = SOURCE / 'godot/ios-host'
RETAINED = BASE / 'godot-ios-retained-host-test-attempt-1'
PRESERVED = BASE / 'retained-preserved'
ENGINE = BASE / 'godot-ios-host-engine'
FRAMEWORK = BASE / 'godot-ios-host-framework'
RENDERER = BASE / 'godot-ios-host-renderer'
checks = []
def read(path): return json.loads(path.read_text())
def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
def file_receipt(path): return {'sha256': digest(path), 'bytes': path.stat().st_size}
def record(path): return {'path': str(path), **file_receipt(path)}
def sha(data): return hashlib.sha256(data).hexdigest()
def check(label, condition):
    checks.append({'check': label, 'passed': bool(condition)})
    assert condition, label

def write_new(path, value):
    with path.open('x') as stream: stream.write(json.dumps(value, indent=2) + '\n')

producer = read(BASE / 'producer-input-evidence-summary.json')
check('completed producer audit at exact revision', producer['runId'] == 34473325295 and producer['headSha'] == HEAD and all(c['passed'] for c in producer['checks']))
run = read(BASE / 'last-run-status.json')
jobs = read(BASE / 'last-jobs-status.json')['jobs']
check('exact completed run/head/event/attempt', run['id'] == 34473325295 and run['head_sha'] == HEAD and run['event'] == 'workflow_dispatch' and run['run_attempt'] == 1 and run['status'] == 'completed')
context = read(RETAINED / 'evidence/retained-ci-context.json')
check('retained CI exact revision, workflow revision, stage, run and architecture', context['source_commit'] == context['expected_source_commit'] == context['workflow_sha'] == HEAD and context['requested_stage'] == 'test' and context['run_id'] == '34473325295' and context['run_attempt'] == '1' and context['system'] == 'Darwin' and context['machine'] == 'arm64')
workflow = (SOURCE / '.github/workflows/godot-ios-authority-host.yml').read_text()
consumer_jobs = [job for job in jobs if job['id'] in (102859300067, 102859300261)]
check('archived workflow and both executed consumers identify host=both', "if: ${{ inputs.host != 'retained' }}" in workflow and "if: ${{ inputs.host == 'retained' || inputs.host == 'both' }}" in workflow and len(consumer_jobs) == 2 and all(job['conclusion'] != 'skipped' for job in consumer_jobs))
check('consumers use distinct hosted runners', len({job['runner_id'] for job in consumer_jobs}) == 2)
engine = read(ENGINE / 'evidence/engine-artifact.json')
framework = read(FRAMEWORK / 'evidence/authority-framework-result.json')
input_copies = []
for name, producer in [('engine', ENGINE), ('framework', FRAMEWORK), ('renderer', RENDERER)]:
    for path in sorted(producer.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(producer)
        copy = PRESERVED / 'retained-inputs' / name / relative
        check('retained original producer file: ' + name + '/' + relative.as_posix(),
              copy.is_file() and file_receipt(copy) == file_receipt(path))
        input_copies.append(name + '/' + relative.as_posix())
retained_inputs = read(RETAINED / 'retained-host-test/evidence/inputs.json')
result = read(RETAINED / 'retained-host-test/evidence/result.json')
check('retained source hashes unchanged during native build and test invocation', retained_inputs['sources'] == result['source_hashes_after'])
for name, expected in retained_inputs['sources'].items():
    check('retained harness matches exact archived source: ' + name, digest(HOST / name) == expected)
verified = retained_inputs['verified_engine_framework_pack']
check('retained nested engine/framework inputs match independent producer bytes',
      verified['engine_receipt'] == engine and verified['framework_receipt'] == framework)
check('retained staged input receipt equals runner input', verified == read(PRESERVED / 'evidence/authority-host-inputs.json'))
check('retained framework receipt bytes match producer', verified['framework_receipt_file']
      == file_receipt(FRAMEWORK / 'evidence/authority-framework-result.json'))
resources = read(PRESERVED / 'evidence/host-resources.json')
check('retained resources nested receipt', verified['resources'] == resources)
check('retained bundled PCK bytes match audited producer', file_receipt(PRESERVED / 'host-resources/ProbeResources/partydeck-last-light.pck')
      == file_receipt(RENDERER / 'partydeck-last-light.pck') == resources['optional_shared_pack'])
check('retained bundled PCK companion receipt matches producer', file_receipt(PRESERVED / 'host-resources/ProbeResources/partydeck-last-light.receipt.json')
      == file_receipt(RENDERER / 'partydeck-last-light.receipt.json'))
for name, expected in resources['diagnostic_sources'].items():
    check('retained diagnostic resource: ' + name, digest(PRESERVED / 'host-resources' / name) == expected)
for name, expected in resources['license_bundle_sha256'].items():
    check('retained license: ' + name, digest(PRESERVED / 'host-resources/ProbeResources/Licenses' / name) == expected)
check('retained fixture and manifest bytes', digest(PRESERVED / 'host-resources/ProbeResources/Launch.json') == resources['fixture_sha256']
      and digest(PRESERVED / 'host-resources/ProbeResources/fixture-manifest.json') == resources['fixture_manifest_sha256'])
ci_inputs = read(RETAINED / 'evidence/retained-ci-inputs.json')
direct_receipt_files, staged_receipt_files = [], []
for item in ci_inputs['files']:
    relative = Path(item['path']).relative_to('godot/ios-host/build')
    candidate = PRESERVED / relative
    if not candidate.is_file() and relative.parts[0] == 'artifacts':
        candidate = ENGINE / relative
        staged_receipt_files.append(relative.as_posix())
    else:
        direct_receipt_files.append(relative.as_posix())
    check('CI input file receipt: ' + relative.as_posix(), file_receipt(candidate)
          == {key: item[key] for key in ('sha256', 'bytes')})

check('result embeds original inputs and exact file digest', result['inputs'] == retained_inputs and result['inputs_file_sha256'] == digest(RETAINED / 'retained-host-test/evidence/inputs.json'))
check('retained build and linkage succeeded', result['swift_harness_compiled'] is True and result['native_and_kotlin_owners_linked'] is True and '** BUILD SUCCEEDED **' in (RETAINED / 'retained-host-test/evidence/build.log').read_text())
expected_cases = {'testActiveAndDormantBackgroundTransitionsStayConcealed', 'testRepeated2DAnd3DKeepOneDormantEngine', 'testStaleFirstReadyAndCloseCompletionReentry'}
reported_all_passed = len(result['native_tests_started']) == len(result['native_tests']) == 3 and set(result['native_tests_started']) == expected_cases and {test['case'] for test in result['native_tests']} == expected_cases and all(test['status'] == 'passed' for test in result['native_tests'])
reported_qualified = reported_all_passed and result['command_exit_code'] == 0 and not result['problems']
check('retained suite qualification follows original recorded execution outcome', result['retained_engine_lifecycle_qualified'] == result['same_process_reentry_qualified'] == reported_qualified)
check('broader native claims remain explicitly unqualified', all(result[k] is False for k in ['kmp_factory_qualified','device_metal_qualified','physical_motion_shutdown_qualified','real_audio_interruption_qualified']) and result['simulator_only'] is True)
check('XCResult and both successful exports preserved', result['test_evidence']['xcresult_retained'] is True and result['test_evidence']['export_commands'] == {'attachments_export_exit_code':0,'summary_export_exit_code':0})
check('summary and export metadata receipt hashes', result['test_evidence']['summary_sha256'] == digest(RETAINED / 'retained-host-test/evidence/test-summary.json') and result['test_evidence']['export_metadata_sha256'] == digest(RETAINED / 'retained-host-test/evidence/test-evidence-export.json'))
check('application observation file inventory', result['application_observation_files'] == sorted(p.name for p in (RETAINED / 'retained-host-test/evidence/application-observations').glob('*.json')))
summary = {'runId':34473325295,'headSha':HEAD,'attempt':1,'scope':'Exact-source consumer input and preservation correlation. Original XCTest outcomes and any suite qualification are evaluated separately without an expected pass/fail assumption.', 'producerAudit':record(BASE / 'producer-input-evidence-summary.json'),'sourceArchive':record(BASE / 'source-archive.json'),'workflowInputs':{'host':'both','hostEvidence':'Both consumers executed under the exact archived workflow conditions.','retained_stage':'test','context':record(RETAINED / 'evidence/retained-ci-context.json')},'consumerRunners':[{'jobId':j['id'],'runnerId':j['runner_id'],'name':j['name']} for j in consumer_jobs], 'preservationAudit':record(BASE / 'retained-preservation-audit.json'),'originalProducerFilesInPreservationVerified':input_copies,'ciReceiptFilesDirectlyVerifiedFromPreservation':direct_receipt_files,'ciStagedArchiveReceiptsCorrelatedWithProducer':staged_receipt_files,'stagedArchiveLimit':'Top-level staged native archives are absent from the preservation tar. Their CI receipts match original producer archives; no independent reread of absent staged files is claimed.','retainedSourceHashes':retained_inputs['sources'],'checks':checks}
write_new(BASE / 'retained-input-evidence-summary.json',summary)
print(json.dumps({'inputAudit':record(BASE / 'retained-input-evidence-summary.json'),'checksPassed':len(checks)}),flush=True)
