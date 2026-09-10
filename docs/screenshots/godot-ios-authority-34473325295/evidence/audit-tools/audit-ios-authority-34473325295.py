"""Audit a collected iOS authority run without executing Xcode or native code."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import plistlib
import sqlite3
import struct
import sys
import tarfile

run, head = sys.argv[1:3]
base = Path('/tmp/partydeck-engine-ci') / run
consumer = base / 'godot-ios-authority-gameplay'
evidence = consumer / 'evidence'
artifacts = consumer / 'artifacts'
source = base / ('source-' + head[:7])
decoded = Path('/root/projects/PartyDeck/artifacts/evidence-storage') / (run + '-xcresult-decoded')
sys.path.insert(0, str(source / 'godot/android-checks'))
from evidence import read_png

def read(path):
    return json.loads(path.read_text())

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def receipt(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}

input_audit = read(base / 'producer-input-evidence-summary.json')
run_status = read(base / 'last-run-status.json')
assert run_status['head_sha'] == head and run_status['status'] == 'completed'
inputs = read(evidence / 'authority-host-inputs.json')
build = read(evidence / 'authority-host-build-result.json')
resources = read(evidence / 'host-resources.json')
engine = read(base / 'godot-ios-host-engine/evidence/engine-artifact.json')
framework = read(base / 'godot-ios-host-framework/evidence/authority-framework-result.json')
assert inputs == build['inputs']
assert build['engine'] == inputs['engine_receipt'] == engine
assert inputs['framework_receipt'] == framework
assert inputs['resources'] == resources
assert inputs['framework_receipt_file']['sha256'] == digest(evidence / 'authority-framework-result.json')
assert (evidence / 'engine-source-commit.txt').read_text().strip() == head
assert (evidence / 'authority-source-commit.txt').read_text().strip() == head
archive = artifacts / 'AuthorityHost-simulator.app.tar.gz'
with tarfile.open(archive) as tar:
    members = {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
files = [{'member': name, 'bytes': len(value), 'sha256': sha(value)} for name, value in members.items()]
old = read(Path('/tmp/partydeck-engine-ci/34464316979/authority-package-evidence-summary.json'))
old_files = {item['member']: item for item in old['files']}
same_files = [item['member'] for item in files if old_files.get(item['member']) == item]
exe = members['AuthorityHost.app/AuthorityHost']
assert sha(exe) == build['executable_sha256']
magic, cpu, subtype, filetype, commands, command_bytes, flags, reserved = struct.unpack_from('<IiiIIIII', exe)
assert magic == 0xfeedfacf and cpu == 0x100000c and filetype == 2
offset, uuid, versions = 32, None, []
for _ in range(commands):
    cmd, size = struct.unpack_from('<II', exe, offset)
    assert size >= 8 and offset + size <= len(exe)
    if cmd == 0x1b:
        uuid = exe[offset+8:offset+24].hex()
    if cmd == 0x32:
        platform, minos, sdk = struct.unpack_from('<III', exe, offset+8)
        versions.append({'platform': platform, 'minos': minos, 'sdk': sdk})
    offset += size
assert uuid and any(v['platform'] == 7 and v['sdk'] == 0x1a0400 for v in versions)
plist = plistlib.loads(members['AuthorityHost.app/Info.plist'])
assert plist['CFBundleSupportedPlatforms'] == ['iPhoneSimulator'] and plist['DTXcodeBuild'] == '17E202'
pack = members['AuthorityHost.app/ProbeResources/partydeck-last-light.pck']
pack_sha = sha(pack)
assert pack_sha == resources['optional_shared_pack']['sha256']
assert pack_sha == digest(base / 'godot-ios-host-renderer/partydeck-last-light.pck')
assert json.loads(members['AuthorityHost.app/ProbeResources/partydeck-last-light.receipt.json'])['pack']['sha256'] == pack_sha
assert sha(members['AuthorityHost.app/ProbeResources/Launch.json']) == resources['fixture_sha256']
assert sha(members['AuthorityHost.app/ProbeResources/fixture-manifest.json']) == resources['fixture_manifest_sha256']
for name, expected in resources['license_bundle_sha256'].items():
    assert sha(members['AuthorityHost.app/ProbeResources/Licenses/' + name]) == expected
package_summary = {'auditUsesExactRunSource': True, 'runId': int(run), 'headSha': head, 'scope': 'Actual linked Simulator app identity; runtime qualification is separate.',
    'appArchive': receipt(archive), 'archiveFileCount': len(files), 'files': files,
    'executable': {'bytes': len(exe), 'sha256': sha(exe), 'machOUuid': uuid, 'cputype': cpu, 'filetype': filetype, 'buildVersions': versions},
    'plist': plist, 'packSha256': pack_sha, 'inputAuditReceipt': receipt(base / 'producer-input-evidence-summary.json'),
    'checks': {'executableReceiptMatches': True, 'nestedInputsMatch': True, 'nestedEngineMatches': True,
        'nestedResourcesMatch': True, 'exactSourceMarkers': True, 'packReceiptMatches': True, 'fixtureMatches': True,
        'fixtureManifestMatches': True, 'licensesMatch': True, 'arm64SimulatorMachO': True,
        'consumerPckMatchesAuditedProducer': True, 'consumerEngineReceiptMatchesProducer': True,
        'consumerFrameworkReceiptMatchesProducer': True},
    'comparisonWithPreviousAuthorityRun': {'runId': 34464316979, 'previousPackageSummarySha256': digest(Path('/tmp/partydeck-engine-ci/34464316979/authority-package-evidence-summary.json')),
        'sameMemberPayloads': same_files, 'allMemberPayloadsIdentical': len(same_files) == len(files) == len(old_files),
        'sameExecutable': sha(exe) == old['executable']['sha256'], 'sameMachOUuid': uuid == old['executable']['machOUuid']},
    'buildReceiptScope': 'The build receipt is emitted before testing and intentionally retains false execution/qualification booleans. Actual case results below come from xcresult.'}
with (base / 'authority-package-evidence-summary.json').open('x') as stream:
    stream.write(json.dumps(package_summary, indent=2) + '\n')
print(json.dumps({'packageAuditPassed': True, 'appBytes': archive.stat().st_size, 'appSha256': digest(archive),
    'sameAppMemberPayloads': len(same_files), 'totalAppMembers': len(files), 'sameExecutable': package_summary['comparisonWithPreviousAuthorityRun']['sameExecutable']}), flush=True)

bundle = artifacts / 'AuthorityHost.xcresult'
con = sqlite3.connect(f'file:{bundle}/database.sqlite3?mode=ro', uri=True)
con.row_factory = sqlite3.Row
tests = [dict(row) for row in con.execute('SELECT c.name,c.identifier,r.rowid AS runRow,r.result,r.duration '
    'FROM TestCaseRuns r JOIN TestCases c ON r.testCase_fk=c.rowid ORDER BY c.rowid')]
issues = [dict(row) for row in con.execute('SELECT testCaseRun_fk,compactDescription,detailedDescription,issueType FROM TestIssues')]
expected_cases = {'testReferenceMatchIn2D()', 'testReferenceMatchIn3D()', 'testReferenceMatchIn2DAt200Percent()', 'testReferenceMatchIn3DAt200Percent()', 'testSecureTableRendererExit()'}
assert len(tests) == 5 and {test['name'] for test in tests} == expected_cases
assert con.execute('SELECT count(*) FROM SkipNotices').fetchone()[0] == 0
rows = {row['uuid']: dict(row) for row in con.execute('SELECT rowid,uuid,name,filenameOverride,xcResultKitPayloadRefId FROM Attachments')}
objects = {Path(item['source']).name.removeprefix('data.'): item for item in read(decoded / 'decoded-object-index.json')['dataObjects']}
attachments_path = artifacts / 'authority-attachments'
manifest_path = attachments_path / 'manifest.json'
manifest = read(manifest_path)
records, per_test = [], []
for test_manifest in manifest:
    identifier = test_manifest['testIdentifier']
    case = next(test for test in tests if test['identifier'] == identifier)
    attachments, measurements, actual_geometry, observed_controls, background_states = [], [], [], [], []
    for item in sorted(test_manifest['attachments'], key=lambda item: item['timestamp']):
        path = attachments_path / item['exportedFileName']
        row = rows[path.stem]
        obj = objects[row['xcResultKitPayloadRefId']]
        value_sha = digest(path)
        assert value_sha == obj['decodedSha256'] and path.stat().st_size == obj['decodedBytes']
        record = {**receipt(path), 'name': item['suggestedHumanReadableName'], 'timestamp': item['timestamp'],
            'testIdentifier': identifier, 'attachmentUuid': row['uuid'], 'xcresultPayloadRef': row['xcResultKitPayloadRefId'],
            'xcresultPayloadSha256': obj['decodedSha256'], 'xcresultOriginalObject': obj['source'], 'matchesOriginalXcresultPayload': True}
        if path.suffix == '.png':
            picture = read_png(path.read_bytes())
            record.update(width=picture.width, height=picture.height, pngVerifiedAndDecoded=True)
        if path.suffix == '.json':
            value = read(path)
            if 'measurements' in record['name'].lower():
                measurements.append({'name': record['name'], 'file': str(path), 'timestamp': record['timestamp'], 'value': value})
                record['jsonKind'] = 'measurement'
            elif record['name'].startswith('Actual native touch geometry'):
                actual_geometry.append({'file': str(path), 'timestamp': record['timestamp'], **value})
                record['jsonKind'] = 'actual_touch_geometry'
                control, viewport = value['control'], value['viewport']
                r, clip = control['rect'], control['clipRect']
                assert control['enabled'] and control['visible'] and r[2] >= 44 and r[3] >= 44
                assert clip[0] >= -0.5 and clip[1] >= -0.5 and clip[0]+clip[2] <= viewport['width']+0.5 and clip[1]+clip[3] <= viewport['height']+0.5
                assert r[0] >= clip[0]-0.5 and r[1] >= clip[1]-0.5 and r[0]+r[2] <= clip[0]+clip[2]+0.5 and r[1]+r[3] <= clip[1]+clip[3]+0.5
            elif record['name'].startswith('Observed control before input'):
                observed_controls.append({'file': str(path), 'timestamp': record['timestamp'], **value})
                record['jsonKind'] = 'observed_control_before_input'
            elif record['name'].startswith('Actual Home and application state observation'):
                background_states.append({'file': str(path), 'timestamp': record['timestamp'], **value})
                record['jsonKind'] = 'observed_application_state'
            else:
                record['jsonKind'] = 'other'
        attachments.append(record)
        records.append(record)
    counts = dict(Counter(item['action'] for item in actual_geometry))
    checks = {}
    if case['result'] == 'Success':
        closed_records = [item for item in measurements if item['value'].get('state') == 'closed']
        assert len(closed_records) == 1
        closed = closed_records[0]['value']
        native = closed['native']
        assert closed['authorityReleased'] and closed['lifecycle'] == 'CLOSED'
        assert native['cleanupCount'] == 1 and native['cleanupDepth'] == 0
        assert native['viewReleased'] and native['controllerReleased'] and native['idleTimerPolicyRestored']
        assert not any(native[k] for k in ['osSingletonPresent', 'bridgeRegistered', 'renderLoopActive', 'quarantined'])
        assert native['queuedCommands'] == native['queuedEvents'] == 0 and closed['hostCounter'] == 1
        checks['closedAuthorityAndNativeOwnershipVerified'] = True
        if 'ReferenceMatch' in identifier:
            winner_records = [item for item in measurements if item['name'].startswith('07 real winner')]
            assert len(winner_records) == 1
            winner = winner_records[0]['value']
            for value in [winner, closed]:
                assert value['roundNumber'] == 14 and value['revision'] == '41'
                assert value['acceptedViewerPlays'] == value['acceptedViewerChallenges'] == 2 and value['roundsAdvanced'] == 13
                assert value['winnerId'] and value['referenceSeed2']
            assert closed['closeReason'] == 'RETURN_TO_LOBBY'
            assert {key: counts.get(key,0) for key in ['play','challenge','next_round','lobby']} == {'play':2,'challenge':2,'next_round':13,'lobby':1}
            assert len(background_states) == 1 and background_states[0]['homeVisible'] is True
            home = background_states[0]
            assert home['observedSpringBoardState'] == 4 and home['observedApplicationState'] != 1
            assert home['elapsedSeconds'] <= 20
            assert len(home['dockIcons']) == 2 and {icon['identifier'] for icon in home['dockIcons']} == {'Safari', 'Messages'}
            assert all(icon['hittable'] and len(icon['frame']) == 4 and icon['frame'][2] > 0 and icon['frame'][3] > 0 for icon in home['dockIcons'])
            initial = next(item['value'] for item in measurements if item['name'].startswith('01 concealed'))
            resumed = next(item['value'] for item in measurements if item['name'].startswith('Same authority resumed'))
            paused = next(item['value'] for item in measurements if item['name'].startswith('Native cover'))
            assert paused['native']['privacyCoverVisible'] and not paused['native']['renderLoopActive'] and not paused['foreground']
            presentation = initial['native']['rendererDiagnostics']['presentationId']
            for value in [initial, paused, resumed, winner]:
                n, d = value['native'], value['native']['rendererDiagnostics']
                assert n['bootstrapCount'] == n['readyEvents'] == 1 and n['renderingLayerClass'] == 'GDTOpenGLLayer'
                assert d['presentationId'] == presentation and d['handConcealed'] and d['selectedCount'] == d['privateFaceCount'] == d['privateLabelCount'] == 0
            checks.update(referenceCountsAndWinnerVerified=True, actualTouchCountsVerified=True, samePresentationPauseHomeResumeVerified=True, actualHomeDockAccessibilityVerified=True)
        else:
            assert closed['closeReason'] == 'EXIT_REQUESTED' and not closed['referenceSeed2']
            assert closed['acceptedViewerPlays'] == closed['acceptedViewerChallenges'] == closed['roundsAdvanced'] == 0
            assert native['exitEvents'] == 1 and counts == {'exit': 1}
            checks['secureLaunchAndExitOnlyVerified'] = True
    per_test.append({**case, 'issues': [issue for issue in issues if issue['testCaseRun_fk'] == case['runRow']],
        'attachmentCount': len(attachments), 'byExtension': dict(Counter(Path(item['path']).suffix for item in attachments)),
        'measurementCount': len(measurements), 'geometryCount': len(actual_geometry), 'observedControlCount': len(observed_controls),
        'measurements': measurements, 'geometryByAction': counts, 'actualGeometry': actual_geometry,
        'observedControls': observed_controls, 'backgroundStates': background_states, 'independentChecks': checks})
    print(json.dumps({'test': identifier, 'result': case['result'], 'attachments': len(attachments), 'measurements': len(measurements),
        'actualTouchCount': len(actual_geometry), 'observedControlCount': len(observed_controls)}), flush=True)
assert {test['identifier'] for test in tests} == {test['testIdentifier'] for test in manifest}
summary = {'runId': int(run), 'headSha': head, 'manifestSha256': digest(manifest_path), 'sqliteSha256': digest(bundle / 'database.sqlite3'),
    'attachmentCount': len(records), 'pngCount': sum(Path(item['path']).suffix == '.png' for item in records),
    'jsonMeasurementCount': sum(item['measurementCount'] for item in per_test),
    'jsonTouchGeometryCount': sum(item['geometryCount'] for item in per_test),
    'jsonObservedControlCount': sum(item['observedControlCount'] for item in per_test),
    'xcresultHashMatchedAttachments': len(records), 'testResults': dict(Counter(test['result'] for test in tests)),
    'tests': per_test, 'attachments': records, 'scope': 'Original attachment payload identity and independently checked measured state/geometry. Actual Home is established by recorded dock accessibility and SpringBoard state; applicationReportedBackground is preserved as observed, with no invented state. Visual review and failure diagnosis are separate.'}
output = base / 'authority-attachment-evidence-summary.json'
with output.open('x') as stream:
    stream.write(json.dumps(summary, indent=2) + '\n')
print(json.dumps({'output': str(output), 'sha256': digest(output), 'attachments': len(records), 'pngs': summary['pngCount'],
    'measurements': summary['jsonMeasurementCount'], 'actualTouchGeometry': summary['jsonTouchGeometryCount'],
    'observedControls': summary['jsonObservedControlCount']}), flush=True)
