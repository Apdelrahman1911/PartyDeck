"""Audit frozen iOS originals and failed cases without executing the app or build."""
import ast
import collections
import ctypes
import ctypes.util
import hashlib
import json
import sqlite3
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO = Path('/root/projects/PartyDeck')
CI = Path('/tmp/partydeck-engine-ci/34460468965')
RUN = '34460468965'
REV = '31d148f9b6bbfa15d1746e1029858b86714362a3'
PACK = '8f24944d61b0430cfec4a32bb1d03d2c7da9f55918264e9cfcded1c675d21539'
OUT = Path('/tmp/partydeck-gallery-1717-ios-source-audit.json')
assert not OUT.exists()
tree = ast.parse(Path('/tmp/partydeck-gallery-1717-audit-android.py').read_text())
helper_names = {'read', 'sha', 'original', 'verify', 'png'}
nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in helper_names]
exec(compile(ast.Module(body=nodes, type_ignores=[]), '<read-only evidence helpers>', 'exec'))

freeze_path = CI / 'collection-evidence-frozen.json'
assert sha(freeze_path) == '5d9ede157649b12c2b6883dd9807b42f664bf22d9388fbf4201e3a978b073e71'
freeze = read(freeze_path)
assert str(freeze['runId']) == RUN and freeze['headSha'] == REV and len(freeze['files']) == 42
for record in freeze['files']:
    verify(record)
owner = read(CI / 'authority-attachment-evidence-summary.json')
collection = read(CI / 'collection-evidence-summary.json')
assert owner['headSha'] == collection['headSha'] == REV and collection['ciConclusion'] == 'failure'
archive_checks = []
for record in collection['originalArtifactZips']:
    path = Path(record['archivePath'])
    assert path.stat().st_size == record['archiveBytes'] == record['apiBytes']
    assert 'sha256:' + sha(path) == record['apiDigest'] == record['archiveDigest']
    base, count = CI / record['name'], 0
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        for info in archive.infolist():
            if info.is_dir():
                continue
            extracted = base / info.filename
            assert extracted.resolve().is_relative_to(base.resolve())
            assert extracted.is_file() and extracted.stat().st_size == info.file_size
            assert extracted.read_bytes() == archive.read(info), extracted
            count += 1
    assert count == record['extractedFileCount']
    archive_checks.append({'artifact':record['name'], 'archive':original(path),
        'github_digest_and_size_matched':True, 'crc_passed':True, 'all_extracted_members_byte_matched':count})
assert len(archive_checks) == 6

artifacts = CI / 'godot-ios-authority-gameplay/artifacts'
attachments_dir = artifacts / 'authority-attachments'
bundle = artifacts / 'AuthorityHost.xcresult'
assert sha(bundle / 'database.sqlite3') == owner['sqliteSha256']
assert sha(attachments_dir / 'manifest.json') == owner['manifestSha256']
con = sqlite3.connect('file:' + str(bundle / 'database.sqlite3') + '?mode=ro', uri=True)
con.row_factory = sqlite3.Row
tests = [dict(row) for row in con.execute('SELECT c.name,c.identifier,r.rowid AS runRow,r.result,r.duration FROM TestCaseRuns r JOIN TestCases c ON r.testCase_fk=c.rowid ORDER BY c.rowid')]
issues = [dict(row) for row in con.execute('SELECT testCaseRun_fk,compactDescription,detailedDescription,issueType FROM TestIssues')]
sql_attachments = {row['uuid']:dict(row) for row in con.execute('SELECT rowid,uuid,name,filenameOverride,xcResultKitPayloadRefId FROM Attachments')}
assert con.execute('SELECT count(*) FROM SkipNotices').fetchone()[0] == 0
con.close()
assert collections.Counter(test['result'] for test in tests) == {'Failure':4,'Success':1}
index_path = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34460468965-xcresult-decoded/decoded-object-index.json')
decoded_index = read(index_path)
objects = {Path(record['source']).name.removeprefix('data.'):record for record in decoded_index['dataObjects']}
lib = ctypes.CDLL(ctypes.util.find_library('zstd'))
lib.ZSTD_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
lib.ZSTD_decompress.restype = ctypes.c_size_t
lib.ZSTD_isError.argtypes = [ctypes.c_size_t]
lib.ZSTD_isError.restype = ctypes.c_uint

def decoded_payload(record):
    source = Path(record['source'])
    raw = source.read_bytes()
    assert len(raw) == record['sourceBytes'] and hashlib.sha256(raw).hexdigest() == record['sourceSha256']
    if record['zstdDecoded']:
        assert raw.startswith(bytes.fromhex('28b52ffd'))
        source_buffer = ctypes.create_string_buffer(raw)
        destination = ctypes.create_string_buffer(record['decodedBytes'])
        size = lib.ZSTD_decompress(destination, record['decodedBytes'], source_buffer, len(raw))
        assert not lib.ZSTD_isError(size) and size == record['decodedBytes']
        payload = destination.raw[:size]
    else:
        payload = raw
    assert len(payload) == record['decodedBytes'] and hashlib.sha256(payload).hexdigest() == record['decodedSha256']
    assert Path(record['decoded']).read_bytes() == payload
    return payload

raw_manifest = read(attachments_dir / 'manifest.json')
frozen_attachment_index = read(CI / 'authority-initial-attachment-index.json')
assert len(raw_manifest) == len(frozen_attachment_index) == 5
owner_by_path = {record['path']:record for record in owner['attachments']}
captures, attachment_evidence, cases = [], [], []
geometry_count = measurement_count = observed_count = payload_count = 0
for raw_case in raw_manifest:
    identifier = raw_case['testIdentifier']
    sql_case = next(test for test in tests if test['identifier'] == identifier)
    case_owner = next(test for test in owner['tests'] if test['identifier'] == identifier)
    assert all(case_owner[key] == sql_case[key] for key in ['name','identifier','runRow','result','duration'])
    assert case_owner['issues'] == [issue for issue in issues if issue['testCaseRun_fk'] == sql_case['runRow']]
    original_index_case = next(test for test in frozen_attachment_index if test['testIdentifier'] == identifier)
    original_index_by_name = {record['exportedFileName']:record for record in original_index_case['attachments']}
    mode = '3d' if '3D' in identifier else '2d'
    scale = 2.0 if '200Percent' in identifier else 1.0
    case_captures = []
    for item in sorted(raw_case['attachments'], key=lambda item:item['timestamp']):
        path = attachments_dir / item['exportedFileName']
        sql_record = sql_attachments[path.stem]
        obj = objects[sql_record['xcResultKitPayloadRefId']]
        payload = decoded_payload(obj)
        assert path.read_bytes() == payload
        original_owner = owner_by_path[str(path)]
        frozen_record = original_index_by_name[path.name]
        assert sha(path) == original_owner['sha256'] == frozen_record['sha256']
        assert path.stat().st_size == original_owner['bytes'] == frozen_record['bytes']
        assert original_owner['xcresultPayloadRef'] == sql_record['xcResultKitPayloadRefId']
        payload_count += 1
        common = {
            'relative_path':'attachments/' + path.name, 'ci_run':RUN,
            'source_revision':REV, 'source_revision_exact':True,
            'test_identifier':identifier, 'test_name':sql_case['name'], 'test_result':sql_case['result'],
            'timestamp':item['timestamp'], 'suggested_human_readable_name':item['suggestedHumanReadableName'],
            'attachment':{**item,'testIdentifier':identifier},
            'xcresult_original_object':obj['source'], 'xcresult_original_object_sha256':obj['sourceSha256'],
            'xcresult_payload_ref':sql_record['xcResultKitPayloadRefId'],
            'xcresult_payload_sha256':obj['decodedSha256'],
            'original_xcresult_payload_independently_verified':True,
        }
        if path.suffix == '.png':
            record = png(path, **common)
            assert (record['width_px'],record['height_px']) == (1206,2622)
            label = item['suggestedHumanReadableName'].rsplit('_0_',1)[0].removesuffix('.png')
            record.update(scenario=label, presentation=mode, font_scale=scale)
            matching = [measurement for measurement in case_owner['measurements']
                        if measurement['name'].rsplit('_0_',1)[0].removesuffix(' measurements') == label]
            assert len(matching) <= 1
            if matching:
                paired = matching[0]
                assert paired['timestamp'] >= item['timestamp']
                record.update(metrics_source=paired['file'], metrics=paired['value'],
                              metrics_timestamp=paired['timestamp'])
            else:
                assert 'home' in label.lower()
                assert len(case_owner['backgroundStates']) == 1
                record['home_state_observation'] = case_owner['backgroundStates'][0]
            captures.append(record)
            case_captures.append(record)
        else:
            attachment_evidence.append(original(path, **common))
    for measurement in case_owner['measurements']:
        assert read(measurement['file']) == measurement['value']
        measurement_count += 1
    for geometry in case_owner['actualGeometry']:
        value = read(geometry['file'])
        assert all(value[key] == geometry[key] for key in value)
        control, viewport = geometry['control'], geometry['viewport']
        rect, clip = control['rect'], control['clipRect']
        assert control['enabled'] and control['visible'] and rect[2] >= 44 and rect[3] >= 44
        assert clip[0] >= -0.5 and clip[1] >= -0.5
        assert clip[0] + clip[2] <= viewport['width'] + 0.5 and clip[1] + clip[3] <= viewport['height'] + 0.5
        assert rect[0] >= clip[0] - 0.5 and rect[1] >= clip[1] - 0.5
        assert rect[0] + rect[2] <= clip[0] + clip[2] + 0.5 and rect[1] + rect[3] <= clip[1] + clip[3] + 0.5
        geometry_count += 1
    for observed in case_owner['observedControls']:
        value = read(observed['file'])
        assert all(value[key] == observed[key] for key in value)
        observed_count += 1
    cases.append({'name':sql_case['name'], 'identifier':identifier, 'result':sql_case['result'],
        'duration_seconds':sql_case['duration'], 'issues':case_owner['issues'],
        'presentation':mode, 'font_scale':scale, 'captures':case_captures,
        'measurement_count':case_owner['measurementCount'], 'actual_geometry_count':case_owner['geometryCount'],
        'observed_control_count':case_owner['observedControlCount'], 'actual_geometry_by_action':case_owner['geometryByAction'],
        'owner_original_case_audit':case_owner})
assert payload_count == 394 and len(captures) == 35 and len(attachment_evidence) == 359
assert measurement_count == 31 and geometry_count == 65 and observed_count == 75
assert {path.name for path in attachments_dir.iterdir() if path.is_file()} == {record['original_filename'] if 'original_filename' in record else Path(record['source_original']).name for record in captures + attachment_evidence} | {'manifest.json'}

package = read(CI / 'authority-package-evidence-summary.json')
verify(package['appArchive'])
expected_members = {record['member']:record for record in package['files']}
seen = set()
with tarfile.open(package['appArchive']['path'], 'r:gz') as archive:
    for member in archive:
        if not member.isfile():
            continue
        expected = expected_members[member.name]
        data = archive.extractfile(member).read()
        assert len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256']
        seen.add(member.name)
assert seen == set(expected_members) and len(seen) == 15
pack_path = CI / 'godot-ios-host-renderer/partydeck-last-light.pck'
assert sha(pack_path) == package['packSha256'] == PACK
pack_receipt = read(pack_path.with_suffix('.receipt.json'))
source_receipt = read(CI / 'source-archive.json')
archive_path = Path(source_receipt['archivePath'])
assert archive_path.stat().st_size == source_receipt['bytes'] and sha(archive_path) == source_receipt['sha256']
source = Path(source_receipt['sourceDirectory'])
source_candidates = [
    '.github/workflows/godot-ios-hosts.yml', '.github/workflows/godot-ios-host.yml',
    'godot/ios-host/AuthorityHost/AuthorityHostModel.swift',
    'godot/ios-host/AuthorityHostUITests/AuthorityHostUITests.swift',
    'godot/ios-host/RetainedHost/RetainedModel.swift',
    'godot/ios-host/modules/partydeck_ios_probe/PDGodotRuntime.mm',
    'godot/ios-host/modules/partydeck_ios_probe/PDGodotEngineOwner.h',
    'godot/ios-host/test-authority-host.sh', 'godot/ios-host/test-retained-host.sh',
    'godot/ios-host/record-authority-result.py', 'godot/ios-host/record-retained-result.py',
    'godot/renderer/scripts/main.gd', 'godot/renderer/presentations/two_d/table.gd',
    'godot/renderer/presentations/three_d/table.gd', 'godot/tools/partydeck_pck.py',
]
source_paths = [relative for relative in source_candidates if (source / relative).is_file()]
assert 'godot/ios-host/AuthorityHostUITests/AuthorityHostUITests.swift' in source_paths
pack_inputs = {'godot/renderer/' + record['path']:record for record in pack_receipt['inputs']['files']}
needed, matched, member_count = set(source_paths) | set(pack_inputs), set(), 0
with tarfile.open(archive_path, 'r|gz') as archive:
    for member in archive:
        member_count += 1
        relative = member.name.partition('/')[2]
        if relative not in needed:
            continue
        payload = archive.extractfile(member).read()
        assert payload == (source / relative).read_bytes()
        if relative in pack_inputs:
            expected = pack_inputs[relative]
            assert len(payload) == expected['bytes'] and hashlib.sha256(payload).hexdigest() == expected['sha256']
        matched.add(relative)
assert matched == needed and member_count == source_receipt['memberCount']
namespace = {'__name__':'gallery_ios_pck_inspector'}
exec(compile((source / 'godot/tools/partydeck_pck.py').read_text(), 'immutable iOS PCK byte inspector', 'exec'),namespace)
assert namespace['read_pack'](pack_path) == pack_receipt['pack']
source_records = [original(source / relative, repository_path=relative, relative_path='source/' + relative) for relative in source_paths]

evidence_by_source = {}
def add_evidence(path, relative, kind):
    path = Path(path)
    key = str(path)
    if key in evidence_by_source:
        return
    assert path.suffix not in {'.png','.zip','.gz','.apk','.aab','.pck','.so','.a','.framework'}
    evidence_by_source[key] = original(path, relative_path=relative, artifact_type=kind)

for record in freeze['files']:
    path = Path(record['path'])
    relative = str(path.relative_to(CI)) if path.is_relative_to(CI) else 'runtime/' + path.name
    add_evidence(path, 'provenance/' + relative, 'original_frozen_owner_evidence')
add_evidence(freeze_path, 'provenance/' + freeze_path.name, 'original_collection_freeze')
add_evidence(attachments_dir / 'manifest.json', 'attachments/manifest.json', 'original_attachment_manifest')
for path in sorted(CI.glob('job-*.log')):
    add_evidence(path, 'provenance/' + path.name, 'original_ci_job_log')
for artifact, subdir in [
    ('godot-ios-authority-gameplay','evidence'), ('godot-ios-retained-host-test-attempt-1','evidence'),
    ('godot-ios-retained-host-test-attempt-1','retained-host-test/evidence'),
    ('godot-ios-host-renderer-evidence','renderer'), ('godot-ios-host-renderer-evidence','toolchain'),
]:
    base = CI / artifact / subdir
    for path in sorted(base.rglob('*')):
        if path.is_file():
            add_evidence(path, 'runtime-evidence/' + artifact + '/' + subdir + '/' + str(path.relative_to(base)),
                         'original_ci_build_or_runtime_evidence')
add_evidence(pack_path.with_suffix('.receipt.json'), 'provenance/partydeck-last-light.receipt.json', 'original_renderer_pack_receipt')
runtime_streams = []
for stream in decoded_index['appStreams']:
    payload = decoded_payload(stream)
    path = Path(stream['appOutputLog'])
    assert path.read_bytes() == payload
    add_evidence(path, 'runtime/' + path.name, 'original_decoded_xcresult_app_stream')
    runtime_streams.append({**original(path), 'xcresult_original_object':stream['source'],
        'xcresult_source_sha256':stream['sourceSha256'], 'payload_sha256':stream['decodedSha256']})
assert len(runtime_streams) == 1 and not decoded_index['crashCandidates']

supplement = Path('/tmp/partydeck-ios-normal-text-diagnosis-v1')
assert sha(supplement / 'normal-text-failure-diagnosis.json') == 'd268c5c07bd8c909989a8223ae4dde6ab2233e401a9ff608643777042c9c575d'
assert sha(supplement / 'normal-text-ax-metrics.json') == '422e2e470c76b3fffdcc04b1983ce640564b6a5ec4764c151e513e3226cac023'
supplement_records = []
for path in sorted(supplement.rglob('*')):
    if path.is_file():
        assert path.suffix != '.png'
        record = original(path, relative_path='review/normal-text-v1/' + str(path.relative_to(supplement)),
            artifact_type='later_normal_text_diagnosis_or_rejected_unapplied_v1_proposal')
        supplement_records.append(record)
secure = read(CI / 'secure-exit-evidence.json')
assert secure['result'] == 'Success' and secure['directOriginalVisualReview']
assert secure['originalImage']['sha256'] == '5fe080b99d5b0b2f7a47ff96e374510f1240f82cb93abc3bd38693aa1eca6c85'
assert secure['scope'].startswith('Secure default launch')
direct_names = {'1A0CB96E-19D3-47D8-8D72-BEC8B875D34F.png','6CFF04E3-5306-465E-B3C7-58FE0849238C.png'}
sheet_dir = Path('/tmp/partydeck-gallery-visual-review/after-1584/ios')
sheet_dir.mkdir(parents=True, exist_ok=True)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15)
review_sheets = []
for case in cases:
    images = [record for record in case['captures'] if Path(record['source_original']).name not in direct_names]
    for start in range(0,len(images),3):
        chosen = images[start:start+3]
        sheet = Image.new('RGB',(1230,960),'#f0f0f0')
        draw = ImageDraw.Draw(sheet)
        for index,record in enumerate(chosen):
            with Image.open(record['source_original']) as picture:
                reduced = picture.convert('RGB')
                reduced.thumbnail((390,870))
                sheet.paste(reduced,(index*410+10,80))
            for row,part in enumerate([record['scenario'][i:i+43] for i in range(0,len(record['scenario']),43)][:3]):
                draw.text((index*410+10,4+row*20),part,fill='black',font=font)
        path = sheet_dir / (case['name'].replace('()','') + '-' + str(start//3+1).zfill(2) + '.png')
        assert not path.exists()
        sheet.save(path)
        review_sheets.append({'path':str(path),'originals':[record['source_original'] for record in chosen],
            'derived_review_sheet_only':True,'published_in_gallery':False})
assert sum(len(sheet['originals']) for sheet in review_sheets) == 33
audit = {
    'generated_utc':datetime.now(timezone.utc).isoformat(),'reviewer':'review_design',
    'baseline_published_commit_acknowledged_by_root':'bbf33f1c33c67fe1b910b821aaa1c0d0dd6bd398',
    'ci_run':RUN,'source_revision':REV,'source_revision_exact':True,
    'collection_freeze':original(freeze_path),'workflow_conclusion':'failure',
    'archives':archive_checks,'captures':captures,'attachment_evidence':attachment_evidence,
    'cases':cases,'metadata_and_runtime_evidence':list(evidence_by_source.values()),
    'source_files':source_records,'normal_text_review_supplement':supplement_records,
    'normal_text_v1_proposal_status':'Rejected and unapplied diagnostic-currentness shortcut, per its owner; preserved as historical diagnosis. A later corrected proposal is separate and is not this run evidence.',
    'original_xcresult_payloads_independently_verified':payload_count,
    'original_measurements_verified':measurement_count,'actual_touch_geometry_verified':geometry_count,
    'observed_control_records_verified':observed_count,'runtime_streams':runtime_streams,
    'app_archive_members_verified':len(seen),'executable_sha256':package['executable']['sha256'],
    'pack_sha256':PACK,'pack_input_files_verified':len(pack_inputs),'source_files_matched_to_archive':len(matched),
    'secure_exit_original_receipt':original(CI / 'secure-exit-evidence.json'),
    'review_sheets':review_sheets,'direct_review_originals':[record['source_original'] for record in captures if Path(record['source_original']).name in direct_names],
    'direct_original_review_count':2,'other_original_visual_review':'Pending; 33 remaining originals are mapped to unviewed internal sheets.',
    'new_application_executions':0,'new_builds_or_runtime_tests':0,'git_commands_run':0
}
OUT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'audit':str(OUT),'sha256':sha(OUT),'original_pngs':len(captures),
    'attachment_evidence':len(attachment_evidence),'metadata_runtime':len(evidence_by_source),
    'source_files':len(source_records),'review_supplement_files':len(supplement_records),
    'review_sheets':len(review_sheets),'direct_originals':2},indent=2))

