"""Independently audit the frozen successful Android/desktop originals; no Git or app execution."""
import collections
import hashlib
import json
import re
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO = Path('/root/projects/PartyDeck')
CI = Path('/tmp/partydeck-engine-ci/34463877910')
RUN = '34463877910'
REV = 'bbfde024d95f5e4d62a26b57495a6a90447d6033'
PACK = 'a47392b4ca50e0433e1f42043b9473b08e9641d24117e251a4ab88e11027e3db'
APK = '7aa1a9296e759729869f0a7542ea477d19bf0a5d16eb3a8953ce2ee56ec08d06'
OUT = Path('/tmp/partydeck-gallery-1717-android-source-audit.json')
assert not OUT.exists()

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def original(path, **extra):
    path = Path(path)
    return {'source_original': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size, **extra}

def verify(record):
    path = Path(record.get('path', record.get('source_original', '')))
    assert path.is_file() and path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], path

def lines(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []

def png(path, **extra):
    record = original(path, **extra)
    with Image.open(path) as picture:
        assert picture.format == 'PNG'
        picture.verify()
    with Image.open(path) as picture:
        picture.load()
        record.update(width_px=picture.width, height_px=picture.height)
    return record

freeze_path = CI / 'collection-frozen.json'
assert sha(freeze_path) == 'a7cae299ffbe7904934659fd527d66771de5529768c38a6ce84965a7d895166a'
freeze = read(freeze_path)
assert freeze['headSha'] == REV and freeze['runConclusion'] == 'success'
metadata_paths = {freeze_path.resolve()}

def add_identity(record):
    verify(record)
    path = Path(record['path'])
    if path.suffix not in {'.zip', '.gz', '.apk', '.aab', '.pck', '.aar', '.jar', '.so', '.a', '.dylib'}:
        metadata_paths.add(path.resolve())

for key in ['originalEvidenceFreeze', 'producerAudit', 'nativeAudit', 'sourceCloseCorrelation', 'originalCaptureInventory', 'humanResult']:
    add_identity(freeze[key])
for group in ['auditCommands', 'auditScripts', 'auditAdaptations']:
    for record in freeze[group]:
        add_identity(record)
frozen_originals = read(freeze['originalEvidenceFreeze']['path'])
assert frozen_originals['headSha'] == REV and frozen_originals['runConclusion'] == 'success'
for record in frozen_originals['metadata'].values():
    add_identity(record)
for record in frozen_originals['jobLogs'] + frozen_originals['preservedApiSnapshots']:
    add_identity(record)
for key in ['collectionContract', 'collectorConsole']:
    add_identity(frozen_originals[key])
add_identity(frozen_originals['source']['receipt'])
verify(frozen_originals['source']['archive'])
archive_checks = []
artifact_roots = {}
for artifact in frozen_originals['artifacts']:
    verify(artifact['zip'])
    assert artifact['githubDigest'] == 'sha256:' + artifact['zip']['sha256']
    assert artifact['githubBytes'] == artifact['zip']['bytes']
    base = Path(artifact['extractedRoot'])
    matched = 0
    with zipfile.ZipFile(artifact['zip']['path']) as archive:
        assert archive.testzip() is None
        for info in archive.infolist():
            if info.is_dir():
                continue
            path = base / info.filename
            assert path.resolve().is_relative_to(base.resolve())
            assert path.is_file() and path.stat().st_size == info.file_size
            assert path.read_bytes() == archive.read(info), path
            matched += 1
    assert matched == artifact['extractedFileCount']
    for key in ['integrityReceipt', 'extractedFileInventory']:
        add_identity(artifact[key])
    artifact_roots[artifact['name']] = base
    archive_checks.append({'name': artifact['name'], 'archive': artifact['zip'],
        'github_digest_matched': True, 'crc_passed': True, 'all_extracted_members_byte_matched': matched})
assert len(archive_checks) == 6 and sum(c['all_extracted_members_byte_matched'] for c in archive_checks) == 599

native_owner = read(freeze['nativeAudit']['path'])
producer = read(freeze['producerAudit']['path'])
assert native_owner['conclusion'] == 'success' and producer['conclusion'] is None
assert native_owner['headSha'] == producer['headSha'] == REV
assert native_owner['packSha256'] == producer['packSha256'] == PACK
packages = []
for record in native_owner['packages']:
    verify(record)
    with zipfile.ZipFile(record['path']) as archive:
        members = [name for name in archive.namelist() if name == 'assets/partydeck-last-light.pck' or name.endswith('/assets/partydeck-last-light.pck')]
        assert len(members) == 1
        assert hashlib.sha256(archive.read(members[0])).hexdigest() == PACK
    packages.append(original(record['path']))
assert packages[0]['sha256'] == APK
pack_path = CI / 'godot-comparison-runtime-apk/renderer/partydeck-last-light.pck'
assert sha(pack_path) == PACK and pack_path.stat().st_size == 1547096
pack_receipt = read(pack_path.with_suffix('.receipt.json'))
source_receipt = read(frozen_originals['source']['receipt']['path'])
source = Path(frozen_originals['source']['extractedRoot'])
assert source_receipt['headSha'] == REV
correlation = read(freeze['sourceCloseCorrelation']['path'])
source_paths = sorted(set([
    'godot/android-checks/run.py', 'godot/android-checks/evidence.py', 'scripts/smoke-android-ui.py',
    'godot/tools/partydeck_pck.py', 'godot/renderer/scripts/main.gd', 'godot/renderer/scripts/renderer_controller.gd',
    'godot/renderer/presentations/two_d/table.gd', 'godot/renderer/presentations/three_d/table.gd',
    'godot/android-host/src/main/kotlin/dev/partydeck/godot/compare/GodotGameActivity.kt',
    'godot/android-host/src/main/kotlin/dev/partydeck/godot/compare/ComparisonActivity.kt',
] + [record['path'] for record in correlation['files']]))
pack_inputs = {'godot/renderer/' + record['path']: record for record in pack_receipt['inputs']['files']}
needed = set(source_paths) | set(pack_inputs)
matched, source_member_count = set(), 0
with tarfile.open(frozen_originals['source']['archive']['path'], 'r|gz') as archive:
    for member in archive:
        source_member_count += 1
        relative = member.name.partition('/')[2]
        if relative not in needed:
            continue
        assert member.isfile()
        payload = archive.extractfile(member).read()
        assert payload == (source / relative).read_bytes(), relative
        if relative in pack_inputs:
            record = pack_inputs[relative]
            assert len(payload) == record['bytes'] and hashlib.sha256(payload).hexdigest() == record['sha256']
        matched.add(relative)
assert matched == needed
assert source_member_count == source_receipt['memberCount']
source_records = [original(source / relative, repository_path=relative, relative_path='source/' + relative)
                  for relative in source_paths]
runner = {Path(relative).name: sha(source / relative)
          for relative in ['godot/android-checks/run.py', 'godot/android-checks/evidence.py', 'scripts/smoke-android-ui.py']}
assert runner == correlation['checkerSourceHashes']
assert correlation['nativeWorkflowJobUnchanged'] and not correlation['fullWorkflowUnchanged']
assert correlation['strictTeardownCheckUnchanged'] and correlation['closeBoundsUnchanged']
assert correlation['closeBoundsMs'] == {'closeFallbackMs': 250, 'rendererExitWaitMs': 1500}
namespace = {'__name__': 'gallery_pck_inspector'}
exec(compile((source / 'godot/tools/partydeck_pck.py').read_text(), 'immutable PCK byte inspector', 'exec'), namespace)
assert namespace['read_pack'](pack_path) == pack_receipt['pack']

inventory = read(freeze['originalCaptureInventory']['path'])
by_resolved_png = {str(Path(record['path']).resolve()): record for record in inventory['captures']}
assert len(by_resolved_png) == 102
previous = read('/tmp/partydeck-gallery-before-1717.json')
previous_by_hash = {}
for record in previous['screenshots']:
    previous_by_hash.setdefault(record['sha256'], []).append(record['path'])
cases, excluded, desktop_records, native_evidence, desktop_evidence = [], [], [], [], []
crop_count = geometry_count = input_count = barriers = fallbacks = deaths = 0
for owner_case in native_owner['androidCases']:
    artifact = owner_case['artifact']
    base = artifact_roots[artifact]
    runtime = base / 'android/runtime'
    case_id = artifact.removeprefix('godot-android-')
    mode = case_id.split('-font-', 1)[0]
    scale = float(case_id.split('-font-', 1)[1].removesuffix('-debug'))
    result = read(runtime / 'result.json')
    assert result['passed'] and owner_case['passed']
    assert result['source_sha256'] == runner
    assert result['apk_sha256'] == result['device']['installed_apk_sha256'] == APK
    assert result['embedded_pck_sha256'] == PACK
    assert result['device']['sdk'] == 35 and float(result['device']['font_scale']) == scale
    assert result['device']['preferences'] == {'reference_scenario': True, 'reduce_motion': True, 'sound_enabled': False}
    assert result['mode_results'] == owner_case['modeResults']
    assert result['mode_results'][0]['intent_counts'] == {'play': 2, 'challenge': 2, 'advance_round': 13}
    assert sha(runtime / 'result.json') == owner_case['resultSha256']
    inputs = read(base / 'package-inputs.json')
    assert inputs['sourceCommit'] == REV and inputs['apkSha256'] == APK
    assert inputs['packSha256'] == inputs['embeddedPackSha256'] == PACK
    assert sha(base / 'package-inputs.json') == owner_case['packageInputsSha256']
    assert read(base / 'android/emulator/preparation/preparation-result.json')['passed']
    native_inputs = lines(runtime / 'input-geometry.log')
    assert len(native_inputs) == owner_case['nativeInputCount']
    for item in native_inputs:
        assert item['package'] == 'dev.partydeck.godot.compare'
        if item['action'] == 'tap':
            x, y = item['coordinates']['x'], item['coordinates']['y']
            for left, top, right, bottom in [item['bounds'], item['viewport']]:
                assert left <= x <= right and top <= y <= bottom
        else:
            assert item['action'] == 'swipe'
    input_count += len(native_inputs)
    raw_entries = result['mode_results'][0]['entries']
    assert [entry['name'] for entry in raw_entries] == ['match', 'scene-exit', 'native-exit']
    events = (runtime / 'events.log').read_text().splitlines()
    entries, scene_pairs = [], []
    for raw_entry in raw_entries:
        name = raw_entry['name']
        directory = runtime / mode / name
        owner_entry = next(entry for entry in owner_case['entries'] if entry['name'] == name)
        observations = lines(directory / 'host-observations.log')
        pid, presentation = raw_entry['engine_pid'], raw_entry['presentation_id']
        assert all(host['enginePid'] == pid and host['presentationId'] == presentation for host in observations)
        assert all(int(host['authorityRejections']) == int(host['rejectedEvents']) == 0 for host in observations)
        assert all(host['diagnosticsTimedOut'] is False for host in observations)
        transitions, prior_count = [], 0
        for number, host in enumerate(observations, 1):
            count = int(host['acceptedIntents'])
            assert count >= prior_count
            if count > prior_count:
                assert count == prior_count + 1
                transitions.append({'observation_line': number, 'type': host['lastIntentType'],
                                    'count': count, 'revision': host['revision']})
            prior_count = count
        accepted = dict(collections.Counter(row['type'] for row in transitions))
        assert accepted == ({'play': 2, 'challenge': 2, 'advance_round': 13, 'return_to_lobby': 1} if name == 'match' else {})
        final = observations[-1]
        flags = ['bridgeClosed', 'nativeDestroyRequested', 'nativeDestroyReturned', 'nativeTerminating',
                 'nativeForceQuitCallback', 'processExitRequested', 'closeSignalAcknowledged']
        assert all(final[flag] is True for flag in flags)
        assert final['lifecycle'] == 'process_exit_requested'
        assert not final['foreground'] and final['coverVisible'] and not final['foregroundFrameReady']
        teardown = read(directory / 'teardown.json')
        assert teardown['host'] == final
        assert all(teardown[key] for key in ['old_pid_absent', 'engine_process_absent', 'both_entries_enabled', 'upstream_renderer_timeout_absent'])
        route = {'match': 'return_to_chooser', 'scene-exit': 'renderer_exit',
                 'native-exit': 'native_close' if mode == '2d' else 'native_back'}[name]
        assert final['closeReason'] == route
        process_path = directory / 'final-process-logcat.log'
        log = process_path.read_text()
        assert sha(process_path) == owner_entry['ownedProcessLogSha256']
        assert not re.search(r'FATAL EXCEPTION:|Fatal signal [0-9]+|SCRIPT ERROR:|SHADER ERROR:|Parse Error:|Unable to exit the renderer', log)
        markers, marker_lines = {}, []
        for number, line in enumerate(log.splitlines(), 1):
            match = re.search(r'Close (requested|dispatch started|native barrier|main callback|fallback) elapsed_ms=(\d+)', line)
            if match:
                assert match.group(1) not in markers
                markers[match.group(1)] = int(match.group(2))
                marker_lines.append({'line': number, 'text': line})
        assert set(markers) == {'requested', 'dispatch started', 'native barrier', 'main callback'}
        assert list(markers.values()) == sorted(markers.values())
        barriers += 'native barrier' in markers
        fallbacks += 'fallback' in markers
        process_events = [{'line': number, 'text': line} for number, line in enumerate(events, 1)
                          if re.search(r'am_proc_(?:start|bound|died)\s*:\s*\[0,' + str(pid) + r',', line)]
        death_events = [event for event in process_events if 'am_proc_died' in event['text']]
        assert len(death_events) == 1 and 'dev.partydeck.godot.compare:godot' in death_events[0]['text']
        deaths += 1
        native_back_events = []
        if name == 'native-exit' and mode == '3d':
            start = next(event['line'] for event in process_events if 'am_proc_start' in event['text'])
            native_back_events = [{'line': number, 'text': line} for number, line in enumerate(events, 1)
                                  if start < number < death_events[0]['line'] and 'key_back_press' in line]
            assert len(native_back_events) == 1
            fresh = read(directory / '01-fresh-concealed.json')
            assert fresh['receivedEvents'] == final['receivedEvents'] == '1'
        chooser = ET.parse(directory / '14-chooser-after-exit.xml')
        for launch in ['launch_2d', 'launch_3d']:
            nodes = [node for node in chooser.iter('node') if node.get('resource-id', '').endswith('/' + launch)]
            assert len(nodes) == 1 and nodes[0].get('enabled') == nodes[0].get('clickable') == 'true'
        capture_rows = lines(directory / 'captures.log')
        assert len(capture_rows) == owner_entry['verifiedSceneCaptureCount']
        for captured in capture_rows:
            path = directory / (captured['name'] + '.png')
            host = read(path.with_suffix('.json'))
            assert host['enginePid'] == pid and host['presentationId'] == captured['presentationId'] == presentation
            assert host['revision'] == captured['revision'] == host['diagnostics']['revision']
            assert host['engineSurface'] == captured['surface']
            assert host['foreground'] and host['foregroundFrameReady'] and host['readyAccepted'] and not host['coverVisible']
            surface = captured['surface']
            with Image.open(path) as picture:
                rgb = picture.convert('RGB').crop((surface['x'], surface['y'], surface['x'] + surface['width'], surface['y'] + surface['height']))
                assert hashlib.sha256(rgb.tobytes()).hexdigest() == captured['engine_rgb_sha256']
            scene_pairs.append({**captured, 'path': str(path), 'host_source': str(path.with_suffix('.json')),
                'host_sha256': sha(path.with_suffix('.json')), 'public_state': host['publicState'],
                'privacy_diagnostics': {key: host['diagnostics'][key] for key in ['handConcealed', 'privateFaceCount', 'privateLabelCount', 'selectedCount']}})
        crop_count += len(capture_rows)
        geometry = lines(directory / 'scene-input-geometry.log')
        assert len(geometry) == owner_entry['sceneInputs']
        for item in geometry:
            matching = [host for host in observations if 'diagnostics' in host
                        and host['diagnostics']['sequence'] == item['diagnosticSequence']
                        and host['diagnostics']['requestId'] == item['diagnosticRequest']
                        and host['revision'] == item['revision']]
            assert matching and item['presentationId'] == presentation
            assert any(control['group'] == item['group'] and control['cardIndex'] == item['cardIndex']
                       and control['rect'] == item['rect'] and control['clipRect'] == item['clipRect']
                       for host in matching for control in host['diagnostics']['controls'])
            surface, viewport = item['engineSurface'], item['rootViewport']
            assert any(host['engineSurface'] == surface and host['diagnostics']['viewport'] == viewport for host in matching)
            rect, clip = item['rect'], item['clipRect']
            points = [[item['coordinates']['x'], item['coordinates']['y']]] if item['action'] == 'tap' else [item['coordinates'][end] for end in ['start', 'end']]
            assert item['action'] in {'tap', 'swipe'}
            for px, py in points:
                x = (px - surface['x']) * viewport['width'] / surface['width']
                y = (py - surface['y']) * viewport['height'] / surface['height']
                assert max(0, clip[0]) <= x <= min(viewport['width'], clip[0] + clip[2])
                assert max(0, clip[1]) <= y <= min(viewport['height'], clip[1] + clip[3])
                if item['action'] == 'tap':
                    assert rect[0] <= x <= rect[0] + rect[2] and rect[1] <= y <= rect[1] + rect[3]
        geometry_count += len(geometry)
        entries.append({'name': name, 'engine_pid': pid, 'presentation_id': presentation,
            'final_host': final, 'accepted_intent_counts': accepted, 'accepted_intent_transitions': transitions,
            'scene_input_geometry_records': len(geometry), 'scene_input_actions': dict(collections.Counter(item['action'] for item in geometry)),
            'completed_requested_exit_route': True, 'actual_os_process_death_observed': True,
            'requested_exit_route': route, 'native_back_system_events': native_back_events,
            'close_delivery': {'recorded_elapsed_realtime_ms': markers, 'original_log_lines': marker_lines,
                'source_configured_fallback_ms': 250, 'recorded_native_barrier': True,
                'recorded_fallback': False, 'scheduling_cause_established': False},
            'owner_log_classification': {key: owner_entry[key] for key in ['enginePriorityErrorLines',
                'knownShaderCacheWarningTextPairs', 'unclassifiedEnginePriorityErrorLines', 'rawErrorTextMatches']}})
    captures = []
    for path in sorted(runtime.rglob('*.png')):
        expected = by_resolved_png[str(path.resolve())]
        record = png(expected['path'], relative_path=case_id + '/' + str(path.relative_to(runtime)),
            case=case_id, mode=mode, font_scale=scale, source_revision=REV, source_revision_exact=True, ci_run=RUN,
            source_aliases=[str(path)] if str(path) != expected['path'] else [])
        assert record['sha256'] == expected['sha256'] and record['bytes'] == expected['bytes']
        assert (record['width_px'], record['height_px']) == (720, 1600)
        captures.append(record)
    assert len(captures) == 19
    prep_path = base / 'android/emulator/preparation/attempt-1/final-screen.png'
    prep = by_resolved_png[str(prep_path.resolve())]
    excluded.append(png(prep['path'], ci_run=RUN, source_revision=REV, source_revision_exact=True,
        reason='Pre-install Android Launcher; emulator preparation, not an app capture. Original retained outside gallery.'))
    records = []
    for path in sorted(base.rglob('*')):
        if not path.is_file() or path.suffix == '.png' or 'avd' in path.relative_to(base).parts:
            continue
        relative = case_id + '/' + (str(path.relative_to(runtime)) if path.is_relative_to(runtime)
                                   else 'provenance/' + str(path.relative_to(base)))
        records.append(original(path, relative_path=relative, case=case_id))
    native_evidence.extend(records)
    cases.append({'artifact': artifact, 'case': case_id, 'source_root': str(base), 'runtime_root': str(runtime),
        'mode': mode, 'font_scale': scale, 'result': result, 'passed': True, 'captures': captures,
        'evidence': records, 'entries': entries, 'scene_pairs': scene_pairs,
        'native_input_records': len(native_inputs), 'owner_original_case_audit': owner_case})
assert crop_count == 48 and geometry_count == 152 and input_count == 350
assert barriers == deaths == 12 and fallbacks == 0

desktop = CI / 'godot-comparison-builds/godot/qualification/build/ci/desktop'
desktop_report = read(desktop / 'report.json')
assert desktop_report['sourceCommit'] == REV and desktop_report['workingTreeDirty'] is False
for path in sorted(desktop.rglob('*.png')):
    expected = by_resolved_png[str(path.resolve())]
    record = png(expected['path'], relative_path=str(path.relative_to(desktop)),
        presentation=path.parent.name, font_scale=1.0, source_revision=REV, source_revision_exact=True,
        ci_run=RUN, source_aliases=[str(path)] if str(path) != expected['path'] else [])
    assert record['sha256'] == expected['sha256']
    record['prior_byte_identical_originals'] = previous_by_hash.get(record['sha256'], [])
    receipt_path = path.with_suffix('.receipt.json')
    receipt = read(receipt_path)
    assert receipt['sha256'] == record['sha256'] and receipt['sourceCommit'] == REV and not receipt['workingTreeDirty']
    assert receipt['rendererArtifact']['sha256'] == PACK
    record['receipt_source'] = str(receipt_path.resolve())
    record['receipt'] = receipt
    desktop_records.append(record)
assert len(desktop_records) == 22
desktop_results = [read(desktop / mode / 'result.json') for mode in ['2d', '3d']]
assert desktop_results[0]['authorityTrace'] == desktop_results[1]['authorityTrace']
assert len(desktop_results[0]['authorityTrace']) == 42
trace_digest = hashlib.sha256(json.dumps(desktop_results[0]['authorityTrace'], separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
for result in desktop_results:
    assert result['rendererExitCode'] == 0
    assert [result[key] for key in ['viewerPlays', 'viewerChallenges', 'roundsAdvanced']] == [2, 2, 13]
    assert trace_digest == result['authorityTraceSha256'] == native_owner['desktop']['traceSha256']
for record in desktop_records:
    result = next(result for result in desktop_results if result['presentation'] == record['presentation'])
    receipt = record['receipt']
    assert receipt == next(capture for capture in result['captures'] if capture['path'] == record['relative_path'])
    view = next(view for view in result['authorityTrace'] if view['revision'] == receipt['authorityRevision'])
    assert view['viewSha256'] == receipt['authorityViewSha256']
for name in ['godot-comparison-builds', 'godot-comparison-runtime-apk']:
    base = artifact_roots[name]
    for path in sorted(base.rglob('*')):
        if not path.is_file() or path.suffix in {'.png', '.apk', '.aab', '.pck', '.jar', '.aar', '.so', '.a', '.gz', '.zip', '.dylib'}:
            continue
        if path.resolve().is_relative_to(desktop.resolve()):
            record = original(path, relative_path=str(path.resolve().relative_to(desktop.resolve())))
            desktop_evidence.append(record)
        else:
            native_evidence.append(original(path, relative_path='build-evidence/' + name + '/' + str(path.relative_to(base))))
metadata = []
storage = Path(freeze['storage']).resolve()
for path in sorted(metadata_paths):
    relative = str(path.relative_to(storage)) if path.is_relative_to(storage) else path.name
    metadata.append(original(path, relative_path='provenance/' + relative))
all_sources = [record['source_original'] for record in native_evidence + desktop_evidence + metadata + source_records]
assert len(all_sources) == len(set(all_sources))

sheet_dir = Path('/tmp/partydeck-gallery-visual-review/after-1584/android')
sheet_dir.mkdir(parents=True, exist_ok=True)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
review_sheets = []
for case in cases:
    images = case['captures'] + [record for record in excluded if case['artifact'] in record['source_original']]
    for start in range(0, len(images), 3):
        chosen = images[start:start+3]
        sheet = Image.new('RGB', (1140, 880), '#f0f0f0')
        draw = ImageDraw.Draw(sheet)
        for index, record in enumerate(chosen):
            source_path = Path(record['source_original'])
            with Image.open(source_path) as picture:
                reduced = picture.convert('RGB')
                reduced.thumbnail((360, 800))
                sheet.paste(reduced, (index * 380 + 10, 70))
            label = str(source_path.relative_to(Path(case['source_root']))) if source_path.is_relative_to(Path(case['source_root'])) else source_path.name
            draw.text((index * 380 + 10, 6), case['case'], fill='black', font=font)
            for row, part in enumerate([label[i:i+40] for i in range(0, len(label), 40)][:2]):
                draw.text((index * 380 + 10, 26 + row*18), part, fill='black', font=font)
        path = sheet_dir / (case['case'] + '-' + str(start // 3 + 1).zfill(2) + '.png')
        assert not path.exists()
        sheet.save(path)
        review_sheets.append({'path': str(path), 'originals': [record['source_original'] for record in chosen],
            'derived_review_sheet_only': True, 'published_in_gallery': False})
audit = {
    'generated_utc': datetime.now(timezone.utc).isoformat(), 'reviewer': 'review_design',
    'baseline_published_commit_acknowledged_by_root': 'bbf33f1c33c67fe1b910b821aaa1c0d0dd6bd398',
    'ci_run': RUN, 'source_revision': REV, 'source_revision_exact': True,
    'collection_freeze': original(freeze_path), 'workflow_conclusion': 'success',
    'producer_original_conclusion': None, 'archives': archive_checks,
    'packages': packages, 'pack_sha256': PACK, 'pack_bytes':1547096,
    'source_archive_members_verified': len(matched), 'pack_input_files_verified':len(pack_inputs),
    'metadata': metadata, 'source_files': source_records, 'native_evidence': native_evidence,
    'desktop': {'source_root':str(desktop), 'report':desktop_report, 'captures':desktop_records,
        'evidence':desktop_evidence, 'authority_trace_sha256':trace_digest, 'authority_trace_rows':42,
        'originals_matching_previously_reviewed_bytes':sum(bool(record['prior_byte_identical_originals']) for record in desktop_records)},
    'android':cases, 'excluded':excluded, 'review_sheets':review_sheets,
    'native_scene_rgb_crops_verified':crop_count, 'scene_input_geometry_records_verified':geometry_count,
    'native_input_geometry_records_verified':input_count, 'native_barriers':barriers,
    'native_fallbacks':fallbacks, 'actual_process_deaths':deaths, 'source_close_bounds_ms':correlation['closeBoundsMs'],
    'independent_visual_review':'Pending; derivative sheets have been generated but not yet viewed.',
    'new_application_executions':0, 'new_builds_or_runtime_tests':0, 'git_commands_run':0
}
OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'audit':str(OUT), 'sha256':sha(OUT), 'native_originals':76, 'desktop_originals':22,
    'desktop_byte_matches':audit['desktop']['originals_matching_previously_reviewed_bytes'],
    'native_evidence':len(native_evidence), 'desktop_evidence':len(desktop_evidence),
    'metadata':len(metadata), 'source_files':len(source_records), 'review_sheets':len(review_sheets)},indent=2))
