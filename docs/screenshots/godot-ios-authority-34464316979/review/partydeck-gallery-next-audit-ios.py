"""Independent read-only source, XCResult, attachment and bounded layout audit.

No Git, build, app execution, artifact mutation, or gallery installation.
Completed phases are immutable checkpoints so a later phase does not repeat them.
"""
import ast
import collections
import ctypes
import ctypes.util
import hashlib
import json
import sqlite3
import sys
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

RUN = sys.argv[1]
EXPECTED = {
    '34464316979': {'revision':'ea84bf49e799675c181545cc3511460b11e0e23d',
        'pack':'a47392b4ca50e0433e1f42043b9473b08e9641d24117e251a4ab88e11027e3db',
        'authority':'269f1a9471cd7cbf8b1883fd853b4d342304c8dd7f0ea23b71bfdd97e4d33f18',
        'retained':'87846165f0291607273f351a9e5ec04237120fd9946c6a12c74b52e4d23e8232',
        'pngs':65},
    '34473325295': {'revision':'0f666e0ab7fdce63d5fa668442dae1c9fda86a1d',
        'pack':'91eeb2fba17dd291564bf2e005f85c0924f813f044f945297f10b281e608b2e6',
        'freeze':'1a4421450bc8d64a613e33dc5389d80ea1073bf2bd63c1ff2b123239deb6a4e6'},
}[RUN]
REPO = Path('/root/projects/PartyDeck')
CI = Path('/tmp/partydeck-engine-ci') / RUN
REV = EXPECTED['revision']
OUT = Path('/tmp/partydeck-gallery-next-ios-' + RUN + '-source-audit.json')
CACHE = Path('/tmp/partydeck-gallery-next-ios-' + RUN + '-checkpoints')
CACHE.mkdir(exist_ok=True)
assert not OUT.exists(), OUT
_helpers = ast.parse(Path('/tmp/partydeck-gallery-1717-audit-android.py').read_text())
_nodes = [n for n in _helpers.body if isinstance(n, ast.FunctionDef) and n.name in {'read','sha','original','verify','png'}]
exec(compile(ast.Module(body=_nodes, type_ignores=[]), '<read-only original helpers>', 'exec'))

def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')

def phase(name, function):
    path = CACHE / (name + '.json')
    if path.exists():
        value = read(path)
        assert value['run'] == RUN and value['revision'] == REV
        print(json.dumps({'phase':name,'reused_completed_checkpoint':str(path)}), flush=True)
        return value['result']
    result = function()
    save(path, {'run':RUN,'revision':REV,'completed_at':datetime.now(timezone.utc).isoformat(),'result':result})
    print(json.dumps({'phase':name,'completed':str(path)}), flush=True)
    return result

freeze_path = CI / 'collection-evidence-frozen.json'
if EXPECTED.get('freeze'):
    assert sha(freeze_path) == EXPECTED['freeze']
freeze = read(freeze_path)
assert str(freeze['runId']) == RUN and freeze['headSha'] == REV
collection = read(CI / 'collection-evidence-summary.json')
assert collection['headSha'] == REV and collection['rendererPackSha256'] == EXPECTED['pack']

# Hash and inspect each frozen original once, including logs retained externally.
def audit_frozen_metadata():
    checked = []
    paths = set()
    records = [freeze['frozenSummary']] + freeze['receiptIndex'] + freeze['preservedAuditorScripts']
    records += [x[k] for x in collection['artifacts'] for k in ['extractedSha256Inventory','originalIntegrityReceipt']]
    records += [x[k] for x in collection['jobLogs'] for k in ['originalLog','collectionReceipt']]
    for record in records:
        if record['path'] in paths:
            continue
        verify(record)
        paths.add(record['path'])
        checked.append(original(record['path']))
    return {'freeze':original(freeze_path),'original_records':checked,'conclusion':freeze['conclusion']}
metadata = phase('metadata', audit_frozen_metadata)

# Check ZIP CRC and match every extracted byte via independent streaming digests.
def audit_archives():
    results = []
    for artifact in collection['artifacts']:
        record = artifact['originalArchive']
        verify(record)
        frozen = next(x for x in freeze['artifactOriginals'] if x['name'] == artifact['name'])
        assert all(record[k] == frozen[k] for k in ['path','bytes','sha256'])
        assert artifact['apiDigest'] == 'sha256:' + record['sha256']
        assert artifact['apiBytes'] == record['bytes']
        base = CI / artifact['name']
        count = total = 0
        with zipfile.ZipFile(record['path']) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                dest = base / info.filename
                assert dest.resolve().is_relative_to(base.resolve())
                assert dest.is_file() and dest.stat().st_size == info.file_size, dest
                with archive.open(info) as stream:
                    zipped_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
                assert zipped_sha == sha(dest), dest
                count += 1
                total += info.file_size
        assert count == artifact['extractedFileCount'] and total == artifact['extractedBytes']
        results.append({'name':artifact['name'],'archive':original(record['path']),
            'github_digest_and_bytes_matched':True,'crc_verified_while_reading_all_members':True,
            'extracted_members_independently_byte_matched':count,'extracted_bytes':total})
        print(json.dumps({'archive':artifact['name'],'matched':count}), flush=True)
    return results
archives = phase('archives', audit_archives)

lib = ctypes.CDLL(ctypes.util.find_library('zstd'))
lib.ZSTD_decompress.argtypes = [ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t]
lib.ZSTD_decompress.restype = ctypes.c_size_t
lib.ZSTD_isError.argtypes = [ctypes.c_size_t]
lib.ZSTD_isError.restype = ctypes.c_uint

def original_payload(path, expected_size):
    raw = path.read_bytes()
    if raw.startswith(bytes.fromhex('28b52ffd')):
        src = ctypes.create_string_buffer(raw)
        dst = ctypes.create_string_buffer(expected_size)
        size = lib.ZSTD_decompress(dst, expected_size, src, len(raw))
        assert not lib.ZSTD_isError(size) and size == expected_size, path
        payload = dst.raw[:size]
    else:
        payload = raw
    assert len(payload) == expected_size
    return payload, hashlib.sha256(raw).hexdigest()

def scenario_name(name):
    name = name.rsplit('_0_',1)[0]
    return name.removesuffix('.png').removesuffix(' measurements')

def rect_contained(rect, clip, epsilon=0.5):
    return rect[0] >= clip[0]-epsilon and rect[1] >= clip[1]-epsilon and rect[0]+rect[2] <= clip[0]+clip[2]+epsilon and rect[1]+rect[3] <= clip[1]+clip[3]+epsilon

def independently_check_measurement_groups(case, suite):
    check_results = []
    for group in ['measurements','homeObservations','dormantIntervals','touchCandidates']:
        for record in case.get(group,[]):
            assert read(record['file']) == record['value'], record['file']
    if suite == 'authority':
        for record in case['actualGeometry']:
            value = read(record['file'])
            assert all(value[k] == record[k] for k in value)
            c, vp = value['control'], value['viewport']
            assert c['enabled'] and c['visible'] and min(c['rect'][2:]) >= 44
            assert rect_contained(c['clipRect'],[0,0,vp['width'],vp['height']])
            assert rect_contained(c['rect'],c['clipRect'])
        for group in ['observedControls','backgroundStates']:
            for record in case[group]:
                value = read(record['file'])
                assert all(value[k] == record[k] for k in value)
        check_results.append({'measurement_count':len(case['measurements']),
            'actual_geometry_count':len(case['actualGeometry']),
            'observed_control_count':len(case['observedControls']),
            'all_actual_geometry_visible_enabled_and_at_least_44pt':True,
            'all_actual_geometry_inside_viewport_and_clip':True})
        if case['result'] == 'Success' and 'ReferenceMatch' in case['name']:
            winner = next(x['value'] for x in case['measurements'] if '07 real winner' in x['name'])
            closed = case['measurements'][-1]['value']
            assert winner['phase'] == 'FINISHED' and winner['winnerId']
            assert closed['lifecycle'] == 'CLOSED' and closed['authorityReleased']
            check_results.append({'winner_and_closed_authority_measurements_rechecked':True,
                'winner_revision':winner['revision'],'winner_id':winner['winnerId']})
    else:
        eligible_count = 0
        for record in case['touchCandidates']:
            value = record['value']
            c = value['control']
            vp = value['metrics']['native']['rendererDiagnostics']['viewport']
            assert c['enabled'] and rect_contained(c['clipRect'],[0,0,vp['width'],vp['height']])
            eligible = bool(c['visible'] and rect_contained(c['rect'],c['clipRect']))
            assert eligible == record['eligibleVisibleTarget']
            if eligible:
                assert min(c['rect'][2:]) >= 44
                eligible_count += 1
        assert eligible_count == case['eligibleVisibleTargetCount']
        check_results.append({'touch_candidates':len(case['touchCandidates']),
            'eligible_visible_targets':eligible_count,'candidate_eligibility_independently_recomputed':True,
            'candidates_are_not_actual_tap_counts':True})
        for record in case['dormantIntervals']:
            value = record['value']
            before, after = value['before'],value['after']
            a,b = before['native'],after['native']
            stable = ['iterations','drawCalls','nativePresentedFrames','nativeFailedPresentations','readyEvents','intentEvents','exitEvents','engineFramesDrawn','treeIdentity','engineIdentity','viewIdentity','controllerIdentity','layerIdentity','processIdentifier']
            assert all(a[k] == b[k] for k in stable)
            assert all(a['audio'][k] == b['audio'][k] for k in ['callbackEntries','startAttempts','stopAttempts'])
            assert value['samples'] >= 2
            for point in [before,after]:
                n = point['native']
                assert point['state'] == n['state'] == 'dormant' and point['authorityReleased'] and n['dormant']
                assert not n['renderLoopActive'] and not n['surfaceAttached'] and not n['inputViewEnabled']
                assert n['emptyTree'] and n['emptyTreeNodeCount'] == 1 and n['oldSceneObjectsAbsent'] and n['bridgeConnections'] == 0
                assert n['idleTimerPolicyRestored'] and n['idleTimerDisabled'] == n['previousIdleTimerDisabled']
                assert n['audioQuiescenceObserved'] and not n['audio']['active'] and n['audio']['callbacksInFlight'] == 0
                assert all(n[k] == 0 for k in ['queuedCommands','queuedEvents','queuedBytes','queuedPrivateDocuments','drawDepth','retirementDepth'])
            check_results.append({'dormant_interval':record['file'],'endpoints_and_stopped_counters_rechecked':True,
                'recorded_sample_count':value['samples'],'intermediate_samples_not_reconstructed':True})
        for record in case['homeObservations']:
            value = record['value']
            assert value['springboardState'] == 4
            assert {x['identifier'] for x in value['dockIcons']} == {'Safari','Messages'}
            check_results.append({'home_observation':record['file'],'raw_application_state':value['applicationState'],
                'springboard_state':value['springboardState'],'dock_icons':[x['identifier'] for x in value['dockIcons']]})
        journal = case.get('applicationJournal')
        if journal:
            verify(journal)
            v = read(journal['path'])
            assert v['runID'] == case['runID'] and all(x['measurements']['runID'] == case['runID'] for x in v['journal'])
            check_results.append({'original_journal':original(journal['path']),'events':[x['event'] for x in v['journal']]})
    return check_results

def audit_suite(suite):
    owner_path = CI / (suite + '-attachment-evidence-summary.json')
    owner = read(owner_path)
    assert owner['headSha'] == REV
    if EXPECTED.get(suite):
        assert sha(owner_path) == EXPECTED[suite]
    if suite == 'authority':
        artifacts = CI / 'godot-ios-authority-gameplay/artifacts'
        attachments_dir = artifacts / 'authority-attachments'
        bundle = artifacts / 'AuthorityHost.xcresult'
        assert sha(bundle/'database.sqlite3') == owner['sqliteSha256']
        assert sha(attachments_dir/'manifest.json') == owner['manifestSha256']
    else:
        for key in ['manifest','sqlite','decodedObjectIndex','originalResult','inputAudit','packageAudit']:
            verify(owner[key])
        attachments_dir = Path(owner['manifest']['path']).parent
        bundle = Path(owner['sqlite']['path']).parent
    con = sqlite3.connect('file:' + str(bundle/'database.sqlite3') + '?mode=ro',uri=True)
    con.row_factory = sqlite3.Row
    tests = [dict(row) for row in con.execute('SELECT c.name,c.identifier,r.rowid AS runRow,r.result,r.duration FROM TestCaseRuns r JOIN TestCases c ON r.testCase_fk=c.rowid ORDER BY c.rowid')]
    issues = [dict(row) for row in con.execute('SELECT testCaseRun_fk,compactDescription,detailedDescription,issueType FROM TestIssues')]
    sql_attachments = {row['uuid']:dict(row) for row in con.execute('SELECT t.rowid,t.*,COALESCE(a.testCaseRun_fk,i.testCaseRun_fk) AS directlyLinkedTestCaseRun FROM Attachments t LEFT JOIN Activities a ON t.activity_fk=a.rowid LEFT JOIN TestIssues i ON t.testIssue_fk=i.rowid')}
    skipped = con.execute('SELECT count(*) FROM SkipNotices').fetchone()[0]
    con.close()
    assert skipped == 0 and len(tests) == len(owner['tests'])
    assert dict(collections.Counter(x['result'] for x in tests)) == owner['testResults']
    manifest = read(attachments_dir/'manifest.json')
    assert {x['identifier'] for x in tests} == {x['testIdentifier'] for x in manifest}
    owner_by_path = {x['path']:x for x in owner['attachments']}
    captures, attachments, cases = [],[],[]
    for raw in manifest:
        identifier = raw['testIdentifier']
        sql_case = next(x for x in tests if x['identifier'] == identifier)
        case = next(x for x in owner['tests'] if x['identifier'] == identifier)
        assert all(case[k] == sql_case[k] for k in sql_case)
        assert case['issues'] == [x for x in issues if x['testCaseRun_fk'] == case['runRow']]
        case_captures = []
        used_measurements = set()
        for item in sorted(raw['attachments'],key=lambda x:x['timestamp']):
            path = attachments_dir / item['exportedFileName']
            op = owner_by_path[str(path)]
            assert op['testIdentifier'] == identifier and op['timestamp'] == item['timestamp']
            assert op['name'] == item['suggestedHumanReadableName']
            row = sql_attachments[path.stem]
            assert abs(row['timestamp'] + 978307200 - item['timestamp']) < 0.002
            if row['directlyLinkedTestCaseRun'] is not None:
                assert row['directlyLinkedTestCaseRun'] == case['runRow']
            obj = bundle/'Data'/('data.' + row['xcResultKitPayloadRefId'])
            assert str(obj) == op['xcresultOriginalObject']
            assert row['xcResultKitPayloadRefId'] == op['xcresultPayloadRef']
            payload, raw_sha = original_payload(obj,op['bytes'])
            digest = hashlib.sha256(payload).hexdigest()
            assert payload == path.read_bytes() and digest == op['sha256'] == op['xcresultPayloadSha256']
            if 'xcresultOriginalObjectSha256' in op:
                assert raw_sha == op['xcresultOriginalObjectSha256']
            common = {'ci_run':RUN,'source_revision':REV,'source_revision_exact':True,'host_suite':suite,
                'test_identifier':identifier,'test_name':case['name'],'test_result':case['result'],
                'timestamp':item['timestamp'],'suggested_human_readable_name':item['suggestedHumanReadableName'],
                'attachment':{**item,'testIdentifier':identifier},'xcresult_original_object':str(obj),
                'xcresult_original_object_sha256':raw_sha,'xcresult_payload_ref':row['xcResultKitPayloadRefId'],
                'xcresult_payload_sha256':digest,'original_xcresult_payload_independently_verified':True,
                'sqlite_direct_test_case_link_available':row['directlyLinkedTestCaseRun'] is not None,
                'source_physical_path':str(path.resolve()),'relative_path':'attachments/' + path.name}
            if suite == 'retained':
                alias = CI/'retained-preserved/retained-host-test/artifacts/attachments'/path.name
                if alias.is_file():
                    assert alias.read_bytes() == payload
                    common['source_aliases'] = [str(alias),str(alias.resolve())]
            if path.suffix != '.png':
                attachments.append(original(path,**common))
                continue
            record = png(path,**common)
            assert (record['width_px'],record['height_px']) == (1206,2622)
            label = scenario_name(item['suggestedHumanReadableName'])
            record['original_filename'] = path.name
            record['scenario'] = label
            matching = [m for m in case['measurements'] if scenario_name(m['name']) == label and m['file'] not in used_measurements and m['timestamp'] >= item['timestamp']]
            if matching:
                paired = min(matching,key=lambda m:m['timestamp'])
                used_measurements.add(paired['file'])
                record.update(metrics_source=paired['file'],metrics=paired['value'],metrics_timestamp=paired['timestamp'],
                    metrics_seconds_after_capture=paired['timestamp']-item['timestamp'])
                assert record['metrics_seconds_after_capture'] < 60
                record['presentation'] = paired['value']['mode']
                record['font_scale'] = paired['value'].get('textScale')
            elif 'Home' in label:
                homes = case.get('homeObservations',case.get('backgroundStates',[]))
                assert homes
                nearest = min(homes,key=lambda m:abs(m['timestamp']-item['timestamp']))
                record['home_state_observation'] = nearest
                record['presentation'] = 'system_home'
                record['font_scale'] = None
            else:
                raise AssertionError(('unpaired original',str(path),label))
            if suite == 'authority':
                record['font_scale'] = 2.0 if '200Percent' in identifier else 1.0
                record['presentation'] = '3d' if '3D' in identifier else '2d'
            captures.append(record)
            case_captures.append(record)
        checked = independently_check_measurement_groups(case,suite)
        keep = ['name','identifier','runRow','result','duration','issues','attachmentCount','byExtension',
                'measurementCount','geometryCount','observedControlCount','geometryByAction','touchCandidatesByAction',
                'eligibleVisibleTargetCount','runID','applicationJournal','journalArguments','independentlyVerifiedScope']
        cases.append({**{k:case[k] for k in keep if k in case},'capture_files':[Path(x['source_original']).name for x in case_captures],
            'independent_gallery_checks':checked,
            'measurement_files':[x['file'] for x in case['measurements']],
            'home_observation_files':[x['file'] for x in case.get('homeObservations',case.get('backgroundStates',[]))],
            'dormant_interval_files':[x['file'] for x in case.get('dormantIntervals',[])]})
    assert len(captures) == owner['pngCount'] and len(captures)+len(attachments) == owner['attachmentCount']
    assert set(owner_by_path) == {x['source_original'] for x in captures+attachments}
    return {'suite':suite,'owner_audit':original(owner_path),'manifest':original(attachments_dir/'manifest.json'),
        'sqlite':original(bundle/'database.sqlite3'),'case_results':dict(collections.Counter(x['result'] for x in cases)),
        'cases':cases,'captures':captures,'attachment_records':attachments,
        'original_payloads_independently_verified':len(captures)+len(attachments),'skipped_tests':skipped,
        'original_scope':owner['scope'],
        'retained_qualification':{k:v for k,v in owner.items() if k.endswith('Qualified')}}
authority = phase('authority-payloads', lambda:audit_suite('authority'))
retained = phase('retained-payloads', lambda:audit_suite('retained'))

SOURCE_CANDIDATES = [
    '.github/workflows/godot-ios-hosts.yml','.github/workflows/godot-ios-host.yml',
    'godot/ios-host/AuthorityHost/AuthorityHostModel.swift',
    'godot/ios-host/AuthorityHostUITests/AuthorityHostUITests.swift',
    'godot/ios-host/RetainedHost/RetainedModel.swift',
    'godot/ios-host/RetainedHostUITests/RetainedHostUITests.swift',
    'godot/ios-host/modules/partydeck_ios_probe/PDGodotRuntime.mm',
    'godot/ios-host/modules/partydeck_ios_probe/PDGodotEngineOwner.h',
    'godot/ios-host/test-authority-host.sh','godot/ios-host/test-retained-host.sh',
    'godot/ios-host/record-authority-result.py','godot/ios-host/record-retained-result.py',
    'godot/renderer/scripts/main.gd','godot/renderer/scripts/renderer_controller.gd',
    'godot/renderer/presentations/two_d/table.gd','godot/renderer/presentations/three_d/table.gd',
    'godot/tools/partydeck_pck.py',
]
def audit_source_and_packages():
    source_receipt = read(CI/'source-archive.json')
    archive = {'path':source_receipt['archivePath'],'bytes':source_receipt['bytes'],'sha256':source_receipt['sha256']}
    verify(archive)
    assert source_receipt['headSha'] == REV
    source = Path(source_receipt['sourceDirectory'])
    pack_path = CI/'godot-ios-host-renderer/partydeck-last-light.pck'
    pack_receipt_path = pack_path.with_suffix('.receipt.json')
    pack_receipt = read(pack_receipt_path)
    assert sha(pack_path) == EXPECTED['pack'] == pack_receipt['pack']['sha256']
    selected = [x for x in SOURCE_CANDIDATES if (source/x).is_file()]
    pack_inputs = {'godot/renderer/' + x['path']:x for x in pack_receipt['inputs']['files']}
    needed = set(selected) | set(pack_inputs)
    matched = set()
    count = 0
    with tarfile.open(archive['path'],'r|gz') as stream:
        for member in stream:
            count += 1
            relative = member.name.partition('/')[2]
            if relative not in needed:
                continue
            with stream.extractfile(member) as payload_stream:
                payload = payload_stream.read()
            assert payload == (source/relative).read_bytes()
            if relative in pack_inputs:
                rec = pack_inputs[relative]
                assert len(payload) == rec['bytes'] and hashlib.sha256(payload).hexdigest() == rec['sha256']
            matched.add(relative)
    assert matched == needed and count == source_receipt['memberCount']
    ns = {'__name__':'gallery_frozen_pck_inspector'}
    exec(compile((source/'godot/tools/partydeck_pck.py').read_text(),'frozen PCK byte reader','exec'),ns)
    assert ns['read_pack'](pack_path) == pack_receipt['pack']
    packages = []
    for suite in ['authority','retained']:
        package = read(CI/(suite+'-package-evidence-summary.json'))
        rec = package.get('appArchive',package.get('archive'))
        verify(rec)
        members = {x['member']:x for x in package['files']}
        seen = set()
        with tarfile.open(rec['path'],'r|gz') as stream:
            for member in stream:
                if not member.isfile():
                    continue
                expect = members[member.name]
                with stream.extractfile(member) as payload_stream:
                    digest = hashlib.file_digest(payload_stream,'sha256').hexdigest()
                assert member.size == expect['bytes'] and digest == expect['sha256']
                if member.name.endswith('/partydeck-last-light.pck'):
                    assert digest == EXPECTED['pack']
                seen.add(member.name)
        assert seen == set(members)
        packages.append({'suite':suite,'app_archive':original(rec['path']),'all_members_reverified':len(seen),
            'bundled_pack_equals_producer':True})
    return {'source_archive':original(archive['path']),'source_archive_receipt':original(CI/'source-archive.json'),
        'source_members_count':count,'source_files_independently_matched':len(matched),
        'source_files_to_preserve':[original(source/x,repository_path=x,relative_path='source/'+x) for x in selected],
        'pack':original(pack_path),'pack_receipt':original(pack_receipt_path),
        'pack_entries_reparsed_and_matched':len(pack_receipt['pack']['entries']),'package_checks':packages,
        'source_bytecode_limit':'All producer input fingerprints and compiled pack entry hashes are checked. Source equality is not inferred by reverse-decoding .gdc bytecode.'}
source = phase('source-and-packages',audit_source_and_packages)

# Preserve compact originals in the gallery. Large raw archives/videos/logs remain
# byte-identified at their existing evidence-storage source, without duplicate blobs.
evidence = {}
external = {}
def add_evidence(path, relative, suite='authority',kind='original evidence'):
    path = Path(path)
    if str(path) in evidence:
        return
    record = original(path,relative_path=relative,host_suite=suite,artifact_type=kind)
    if path.stat().st_size > 2*1024*1024 and path.suffix not in {'.json','.sqlite3'}:
        external[str(path)] = {**record,'not_duplicated_reason':'Full original remains in evidence-storage; compact original receipts and failure observations are preserved in the gallery.'}
        return
    assert path.stat().st_size < 20*1024*1024, path
    assert path.suffix not in {'.png','.zip','.gz','.pck','.mp4','.a','.so','.dylib'}
    evidence[str(path)] = record

add_evidence(freeze_path,'collection-evidence-frozen.json')
for rec in metadata['original_records']:
    path = Path(rec['source_original'])
    relative = str(path.relative_to(CI)) if path.is_relative_to(CI) else 'supplemental/' + path.name
    add_evidence(path,relative)
for rec in source['source_files_to_preserve']:
    add_evidence(rec['source_original'],rec['relative_path'],kind='exact CI source')
add_evidence(source['pack_receipt']['source_original'],'producer/partydeck-last-light.receipt.json')
for suite_audit in [authority,retained]:
    suite = suite_audit['suite']
    for key in ['manifest','sqlite']:
        rec = suite_audit[key]
        add_evidence(rec['source_original'],('attachments/manifest.json' if key=='manifest' else 'xcresult/database.sqlite3'),suite)
    for rec in suite_audit['attachment_records']:
        path = Path(rec['source_original'])
        if path.suffix in {'.json','.txt'}:
            add_evidence(path,rec['relative_path'],suite,'original XCResult attachment')
        else:
            external[str(path)] = {**rec,'not_duplicated_reason':'Original video or XCTest internal attachment is retained at its original evidence-storage path; verified payload identity is recorded without adding another binary/log copy.'}
    for case in suite_audit['cases']:
        if case.get('applicationJournal'):
            path = Path(case['applicationJournal']['path'])
            add_evidence(path,'application-observations/'+path.name,suite,'original application journal')
    # Native harness records are needed to keep execution and failure qualification explicit.
    root = CI/'godot-ios-authority-gameplay' if suite=='authority' else CI/'godot-ios-retained-host-test-attempt-1/retained-host-test'
    for relative in ['evidence/result.json','evidence/execution.json','evidence/commands.json','artifacts/result.json']:
        path = root/relative
        if path.is_file():
            add_evidence(path,'native-harness/'+relative,suite)

captures = authority['captures'] + retained['captures']
if EXPECTED.get('pngs'):
    assert len(captures) == EXPECTED['pngs']
result = {'schema_version':1,'audit_kind':'independent original evidence read; no build or runtime execution',
    'run':RUN,'revision':REV,'pack_sha256':EXPECTED['pack'],'completed_at':datetime.now(timezone.utc).isoformat(),
    'frozen_metadata':metadata,'archive_checks':archives,'source_and_package_checks':source,
    'suites':[authority,retained],'capture_count':len(captures),'evidence_files':list(evidence.values()),
    'externally_retained_originals':list(external.values()),'original_collection_qualification':collection['qualification'],
    'original_collection_limitations':collection['limitations'],'audit_script':original(Path(__file__))}
save(OUT,result)
print(json.dumps({'audit':str(OUT),'sha256':sha(OUT),'captures':len(captures),'payloads':sum(x['original_payloads_independently_verified'] for x in [authority,retained]),'evidence_files':len(evidence),'external_originals':len(external)}),flush=True)
