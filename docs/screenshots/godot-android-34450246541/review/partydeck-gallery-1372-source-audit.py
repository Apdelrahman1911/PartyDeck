"""Read-only archive audit for frozen CI 34450246541. No Git or app execution."""
import ast
import collections
import hashlib
import json
import re
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path('/root/projects/PartyDeck')
GALLERY = REPO / 'docs/screenshots'
CI = Path('/tmp/partydeck-engine-ci/34450246541')
REV = 'a7278686170243795e505ce4f6a6788e912c01fe'
PACK = '0440dc8a1e099031eb7e0a08304411908e8580f932673599f149d2088c0e7afe'
APK = '12699a84297d915344341e3cc794d43f04879fd719578a8a670f9df190d326b1'
SOURCE = CI / 'source-a727868'
OUT = Path('/tmp/partydeck-gallery-visual-review/after-1279')
OUT.mkdir(parents=True, exist_ok=True)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def original(path):
    path = Path(path)
    return {'source_original': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def png(path):
    record = original(path)
    with Image.open(path) as picture:
        assert picture.format == 'PNG'
        picture.verify()
    with Image.open(path) as picture:
        picture.load()
        record.update(width_px=picture.width, height_px=picture.height)
    return record


def check_original(record):
    path = Path(record.get('source_original', record.get('path')))
    assert sha(path) == record['sha256'], path
    assert path.stat().st_size == record['bytes'], path


# The root coordinator acknowledged published d36cf6b and independently checked
# the prior freeze against Git. Recheck that receipt and snapshot all owned files.
assert sha(GALLERY / 'manifest.json') == 'bdb7cbf736f5ba821b3e26ad0f3360896fa89e00d6b2367e184dcf71819fb8a1'
previous_freeze = read('/tmp/partydeck-gallery-1279-freeze.json')
for record in previous_freeze:
    check_original({**record, 'path': str(REPO / record['path'])})
assert len(previous_freeze) == 800
baseline = read(GALLERY / 'manifest.json')
assert len(baseline['screenshots']) == 1279 and len(baseline['evidence']) == 3022
baseline_files = [{'path': str(path.relative_to(REPO)), 'bytes': path.stat().st_size, 'sha256': sha(path)}
                  for path in sorted(GALLERY.rglob('*')) if path.is_file()]
baseline_files.append({'path': 'godot/reviews/design-review.md',
                       'bytes': (REPO / 'godot/reviews/design-review.md').stat().st_size,
                       'sha256': sha(REPO / 'godot/reviews/design-review.md')})
Path('/tmp/partydeck-gallery-1372-baseline-files.json').write_text(json.dumps(baseline_files, indent=2) + '\n')
Path('/tmp/partydeck-gallery-before-1372.json').write_bytes((GALLERY / 'manifest.json').read_bytes())
Path('/tmp/partydeck-gallery-before-1372-README.md').write_bytes((GALLERY / 'README.md').read_bytes())
Path('/tmp/partydeck-gallery-before-1372-design-review.md').write_bytes((REPO / 'godot/reviews/design-review.md').read_bytes())

frozen_path = CI / 'audit-frozen.json'
assert sha(frozen_path) == '1150c3be73311baad63b0e7d5847a9182d06c29efce7cd1099e598d148c8f256'
frozen = read(frozen_path)
assert frozen['headSha'] == REV and frozen['workflowConclusion'] == 'failure'
frozen_records = (frozen['files'] + frozen['artifactDownloadReceipts'] + frozen['jobLogs']
                  + [frozen['auditScript'], frozen['finalizationScript'], frozen['collectionInterruption']['receipt']])
for record in frozen_records:
    check_original(record)
check_original(frozen['sourceArchive'])
summary = read(CI / 'evidence-summary.json')
producer = read(CI / 'producer-evidence-summary.json')
assert summary['headSha'] == producer['headSha'] == REV
assert summary['conclusion'] == 'failure' and producer['conclusion'] is None
run_status = read(CI / 'last-run-status.json')
assert run_status['head_sha'] == REV and run_status['status'] == 'completed' and run_status['conclusion'] == 'failure'
assert str(run_status['id']) == '34450246541'
assert summary['packSha256'] == PACK and summary['packBytes'] == 1546312
packages = []
for record in frozen['identity']['packages']:
    check_original(record)
    path = Path(record['path'])
    with zipfile.ZipFile(path) as archive:
        candidates = [name for name in archive.namelist() if name.endswith('/assets/partydeck-last-light.pck') or name == 'assets/partydeck-last-light.pck']
        assert len(candidates) == 1
        assert hashlib.sha256(archive.read(candidates[0])).hexdigest() == record['embeddedPackSha256'] == PACK
    packages.append(original(path))
assert packages[0]['sha256'] == APK
pack_path = CI / 'godot-comparison-runtime-apk/renderer/partydeck-last-light.pck'
assert sha(pack_path) == PACK and pack_path.stat().st_size == 1546312
pack_receipt_path = pack_path.with_suffix('.receipt.json')
pack_receipt = read(pack_receipt_path)

# Source identity comes from the immutable downloaded tarball, never current files.
source_archive = read(CI / 'source-archive.json')
assert source_archive['headSha'] == REV and source_archive['sourceDirectory'] == str(SOURCE)
source_paths = [
    'godot/android-checks/run.py', 'godot/android-checks/evidence.py', 'scripts/smoke-android-ui.py',
    'godot/tools/partydeck_pck.py', 'godot/renderer/scripts/main.gd', 'godot/renderer/scripts/renderer_controller.gd',
    'godot/renderer/presentations/two_d/table.gd', 'godot/renderer/presentations/three_d/table.gd',
    'godot/android-host/src/main/kotlin/dev/partydeck/godot/compare/GodotGameActivity.kt',
    'godot/android-host/src/main/kotlin/dev/partydeck/godot/compare/ComparisonActivity.kt',
]
input_paths = {'godot/renderer/' + item['path']: item for item in pack_receipt['inputs']['files']}
archive_needed = set(source_paths) | set(input_paths)
source_matches, archive_member_count = set(), 0
with tarfile.open(source_archive['archivePath'], mode='r|gz') as archive:
    for member in archive:
        archive_member_count += 1
        relative = member.name.split('/', 1)[1] if '/' in member.name else ''
        if relative not in archive_needed:
            continue
        assert member.isfile(), relative
        stream = archive.extractfile(member)
        data = stream.read()
        path = SOURCE / relative
        assert path.read_bytes() == data, relative
        if relative in input_paths:
            item = input_paths[relative]
            assert len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'], relative
        source_matches.add(relative)
assert archive_member_count == source_archive['memberCount']
assert source_matches == archive_needed, sorted(archive_needed - source_matches)
source_records = [original(SOURCE / relative) for relative in source_paths]
runner = {Path(relative).name: sha(SOURCE / relative) for relative in source_paths[:3]}
assert sha(SOURCE / 'godot/renderer/presentations/two_d/table.gd') == '8d8650c8b6b6c5c5052b798e540d0b618dc2d916d7fdda0c95011eac6412f993'
correlation = read(CI / 'source-back-correction-correlation.json')
check_original(correlation['archivedHostSource'])
assert correlation['headSha'] == REV
assert correlation['archivedHostSource']['sha256'] == correlation['expectedReviewedBackCorrectionSha256'] == 'b6dc98d69013253a9c601f80dd417c52cd003bdd9c13adc2d8fd335a76e0f027'
namespace = {'__name__': 'gallery_pck_inspector'}
exec(compile((SOURCE / 'godot/tools/partydeck_pck.py').read_text(), 'immutable PCK byte inspector', 'exec'), namespace)
pack_inventory = namespace['read_pack'](pack_path)
assert pack_inventory == pack_receipt['pack']

inventory = read(CI / 'original-image-inventory.json')
assert inventory['headSha'] == REV and inventory['packSha256'] == PACK and inventory['runtimeApkSha256'] == APK
assert inventory['nativePngCount'] == len(inventory['native']) == 75
assert inventory['nativeRuntimePngCount'] == 71 and inventory['nativePreparationPngCount'] == 4
native_inventory = {record['path']: record for record in inventory['native']}
assert len(native_inventory) == 75
native_records = {}
for path, expected in native_inventory.items():
    record = png(Path(path))
    assert record['sha256'] == expected['sha256'] and record['bytes'] == expected['bytes']
    assert (record['width_px'], record['height_px']) == (expected['width'], expected['height']) == (720, 1600)
    native_records[path] = record

audit = {'baseline_published_commit_acknowledged_by_root': 'd36cf6b', 'review_sheets': []}

audit['android'] = []
audit['excluded'] = []
native_count = crop_count = geometry_count = native_input_count = exit_count = warning_log_count = warning_pair_count = 0
all_entry_records = []
summary_by_artifact = {case['artifact']: case for case in summary['androidCases']}
destroy_flags = ['bridgeClosed', 'nativeDestroyRequested', 'nativeDestroyReturned', 'nativeTerminating',
                 'nativeForceQuitCallback', 'processExitRequested']
for mode in ['2d', '3d']:
    for scale in ['1.0', '2.0']:
        artifact = f'godot-android-{mode}-font-{scale}-debug'
        base = CI / artifact
        runtime = base / 'android/runtime'
        case_summary = summary_by_artifact[artifact]
        result = read(runtime / 'result.json')
        expected_pass = mode == '2d' or scale == '2.0'
        assert result['modes'] == [mode] and result['passed'] == expected_pass == case_summary['passed']
        assert result['source_sha256'] == runner
        assert result['apk_sha256'] == result['device']['installed_apk_sha256'] == APK
        assert result['embedded_pck_sha256'] == PACK
        assert result['apk_bytes'] == packages[0]['bytes'] and result['embedded_pck_bytes'] == 1546312
        assert result['device']['sdk'] == 35 and result['device']['font_scale'] == scale
        assert result['device']['preferences'] == {'reference_scenario': True, 'reduce_motion': True, 'sound_enabled': False}
        assert result['mode_results'][0]['intent_counts'] == {'play': 2, 'challenge': 2, 'advance_round': 13}
        assert (runtime / 'display-size.log').read_text().strip() == 'Physical size: 720x1600'
        assert (runtime / 'display-density.log').read_text().strip() == 'Physical density: 280'
        package_inputs = read(base / 'package-inputs.json')
        assert package_inputs['sourceCommit'] == REV
        assert package_inputs['packSha256'] == package_inputs['embeddedPackSha256'] == PACK
        assert package_inputs['apkSha256'] == APK
        assert sha(base / 'package-inputs.json') == case_summary['packageInputsSha256']
        assert sha(runtime / 'result.json') == case_summary['resultSha256']
        preparation = read(base / 'android/emulator/preparation/preparation-result.json')
        assert preparation['passed'] is True and preparation['reboot_attempted'] is False
        runtime_paths = sorted(runtime.rglob('*.png'))
        captures = [native_records[str(path)] for path in runtime_paths]
        assert len(captures) == (14 if mode == '3d' and scale == '1.0' else 19)
        native_count += len(captures)
        for record in captures:
            expected = native_inventory[record['source_original']]
            assert expected['case'] == artifact and expected['wholeCasePassed'] == result['passed']
            assert expected['wholeCaseStage'] == result.get('stage')
        prep = base / 'android/emulator/preparation/attempt-1/final-screen.png'
        prep_record = dict(native_records[str(prep)])
        prep_record.update(ci_run='34450246541', source_revision=REV,
            reason='Pre-install Android Launcher; emulator preparation, not an app capture. Original retained outside gallery.')
        audit['excluded'].append(prep_record)
        assert set(base.rglob('*.png')) == set(runtime_paths + [prep])
        xml_files = sorted(runtime.rglob('*.xml'))
        for path in xml_files:
            ET.parse(path)

        entries = []
        scene_pairs = []
        native_inputs = lines(runtime / 'input-geometry.log')
        assert len(native_inputs) == case_summary['nativeInputCount']
        native_input_count += len(native_inputs)
        for item in native_inputs:
            assert item['package'] == 'dev.partydeck.godot.compare'
            if item['action'] == 'tap':
                x, y = item['coordinates']['x'], item['coordinates']['y']
                for left, top, right, bottom in [item['bounds'], item['viewport']]:
                    assert left <= x <= right and top <= y <= bottom
            else:
                assert item['action'] == 'swipe'
        events = (runtime / 'events.log').read_text().splitlines()
        actual_entries = result['mode_results'][0]['entries']
        assert [entry['name'] for entry in actual_entries] == (['match'] if not expected_pass else ['match', 'scene-exit', 'native-exit'])
        assert {path.name for path in (runtime / mode).iterdir() if path.is_dir()} == {entry['name'] for entry in actual_entries}
        for raw_entry in actual_entries:
            name = raw_entry['name']
            directory = runtime / mode / name
            observations = lines(directory / 'host-observations.log')
            assert observations
            pid, presentation = raw_entry['engine_pid'], raw_entry['presentation_id']
            assert all(host['enginePid'] == pid and host['presentationId'] == presentation for host in observations)
            assert all(int(host['authorityRejections']) == int(host['rejectedEvents']) == 0 for host in observations)
            assert all(host['diagnosticsTimedOut'] is False for host in observations)
            assert all(host['displayDensity'] == 1.75 for host in observations)
            transitions = []
            previous = 0
            for line_number, host in enumerate(observations, 1):
                count = int(host['acceptedIntents'])
                assert count >= previous
                if count > previous:
                    assert count == previous + 1
                    transitions.append({'observation_line': line_number, 'type': host['lastIntentType'],
                                        'count': count, 'revision': host['revision']})
                previous = count
            counts = dict(collections.Counter(row['type'] for row in transitions))
            expected_counts = {'play': 2, 'advance_round': 13, 'challenge': 2, 'return_to_lobby': 1} if name == 'match' else {}
            assert counts == expected_counts
            final = observations[-1]
            assert all(final[flag] is True for flag in destroy_flags)
            assert final['lifecycle'] == 'process_exit_requested'
            assert final['foreground'] is False and final['coverVisible'] is True and final['foregroundFrameReady'] is False

            process_log_path = directory / 'final-process-logcat.log'
            process_log = process_log_path.read_text()
            numbered_log = list(enumerate(process_log.splitlines(), 1))
            egl_lines = [{'line': n, 'text': text} for n, text in numbered_log if 'removeVertexArrayObject' in text and 'ERROR:' in text]
            assert egl_lines, process_log_path
            assert not re.search(r'FATAL EXCEPTION:|Fatal signal [0-9]+|SCRIPT ERROR:|SHADER ERROR:|Parse Error:|Unable to exit the renderer', process_log)
            termination_lines = [{'line': n, 'text': text} for n, text in numbered_log
                                 if re.search(r'Exiting render thread|Destroying Godot Engine|OnGodotTerminating', text)]
            assert len(termination_lines) == 3
            pending_warning = None
            warning_pairs = []
            for n, text in numbered_log:
                if not re.search(r'\bE\s+(?:godot|Godot)\s*:', text):
                    continue
                match = re.fullmatch(r'\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s+(\d+)\s+(\d+)\s+E\s+godot\s*:\s*(.*)', text)
                assert match, text
                if match.group(3) == 'WARNING: Failed to load cached shader, recompiling.':
                    assert pending_warning is None
                    pending_warning = (match.group(1, 2), {'line': n, 'text': text})
                else:
                    assert pending_warning and match.group(1, 2) == pending_warning[0]
                    assert match.group(3) == 'at: _load_from_cache (drivers/gles3/shader_gles3.cpp:615)'
                    warning_pairs.append([pending_warning[1], {'line': n, 'text': text}])
                    pending_warning = None
            assert pending_warning is None
            warning_log_count += bool(warning_pairs)
            warning_pair_count += len(warning_pairs)
            process_events = [{'line': n, 'text': text} for n, text in enumerate(events, 1)
                              if re.search(r'am_proc_(?:start|bound|died)\s*:\s*\[0,' + str(pid) + r',', text)]
            deaths = [event for event in process_events if 'am_proc_died' in event['text']]
            assert len(deaths) == 1 and 'dev.partydeck.godot.compare:godot' in deaths[0]['text']

            capture_rows = lines(directory / 'captures.log')
            for recorded in capture_rows:
                path = directory / (recorded['name'] + '.png')
                host = read(path.with_suffix('.json'))
                assert host['enginePid'] == pid and host['presentationId'] == presentation == recorded['presentationId']
                assert host['revision'] == recorded['revision']
                assert host['engineSurface'] == recorded['surface']
                assert host['readyAccepted'] and host['foregroundFrameReady'] and host['foreground']
                assert not host['coverVisible'] and host['lifecycle'] == 'active'
                assert host['diagnostics']['revision'] == host['revision']
                assert host['diagnostics']['presentationId'] == presentation
                surface = recorded['surface']
                with Image.open(path) as picture:
                    crop = picture.convert('RGB').crop((surface['x'], surface['y'], surface['x'] + surface['width'], surface['y'] + surface['height']))
                    assert hashlib.sha256(crop.tobytes()).hexdigest() == recorded['engine_rgb_sha256']
                scene_pairs.append({**recorded, 'path': str(path), 'host_source': str(path.with_suffix('.json')),
                    'host_sha256': sha(path.with_suffix('.json')), 'public_state': host['publicState'],
                    'privacy_diagnostics': {key: host['diagnostics'][key] for key in ['handConcealed', 'privateFaceCount', 'privateLabelCount', 'selectedCount']}})
            crop_count += len(capture_rows)
            geometry = lines(directory / 'scene-input-geometry.log')
            geometry_count += len(geometry)
            for item in geometry:
                assert item['presentationId'] == presentation
                matching = [host for host in observations if 'diagnostics' in host
                            and host['diagnostics']['sequence'] == item['diagnosticSequence']
                            and host['diagnostics']['requestId'] == item['diagnosticRequest']
                            and host['revision'] == item['revision']]
                assert matching
                assert any(control['group'] == item['group'] and control['cardIndex'] == item['cardIndex']
                           and control['rect'] == item['rect'] and control['clipRect'] == item['clipRect']
                           for host in matching for control in host['diagnostics']['controls'])
                surface, viewport = item['engineSurface'], item['rootViewport']
                assert any(host['engineSurface'] == surface and host['diagnostics']['viewport'] == viewport for host in matching)
                rect, clip = item['rect'], item['clipRect']
                if item['action'] == 'tap':
                    x = (item['coordinates']['x'] - surface['x']) * viewport['width'] / surface['width']
                    y = (item['coordinates']['y'] - surface['y']) * viewport['height'] / surface['height']
                    assert max(0, rect[0], clip[0]) <= x <= min(viewport['width'], rect[0] + rect[2], clip[0] + clip[2])
                    assert max(0, rect[1], clip[1]) <= y <= min(viewport['height'], rect[1] + rect[3], clip[1] + clip[3])
                else:
                    assert item['action'] == 'swipe'
                    for point in ['start', 'end']:
                        px, py = item['coordinates'][point]
                        x = (px - surface['x']) * viewport['width'] / surface['width']
                        y = (py - surface['y']) * viewport['height'] / surface['height']
                        assert max(0, clip[0]) <= x <= min(viewport['width'], clip[0] + clip[2])
                        assert max(0, clip[1]) <= y <= min(viewport['height'], clip[1] + clip[3])
                    assert 0 < item['coordinates']['duration_ms'] <= 2000

            teardown_path = directory / 'teardown.json'
            failed_close = mode == '3d' and scale == '1.0' and name == 'match'
            native_back_events = []
            assert teardown_path.exists() is (not failed_close)
            if not failed_close:
                teardown = read(teardown_path)
                assert teardown['host'] == final
                assert all(teardown[key] for key in ['old_pid_absent', 'engine_process_absent', 'both_entries_enabled', 'upstream_renderer_timeout_absent'])
                assert teardown['surviving_chooser_pid'] == result['device']['chooser_pid']
                expected_route = {'match': 'return_to_chooser', 'scene-exit': 'renderer_exit', 'native-exit': ('native_close' if mode == '2d' else 'native_back')}[name]
                assert final['closeReason'] == expected_route and final['closeSignalAcknowledged'] is True
                if name == 'native-exit' and mode == '3d':
                    fresh = read(directory / '01-fresh-concealed.json')
                    assert fresh['receivedEvents'] == final['receivedEvents'] == '1'
                    start_line = next(event['line'] for event in process_events if 'am_proc_start' in event['text'])
                    native_back_events = [{'line': n, 'text': text} for n, text in enumerate(events, 1)
                                          if start_line < n < deaths[0]['line'] and 'key_back_press' in text]
                    assert len(native_back_events) == 1
                chooser_xml = directory / '14-chooser-after-exit.xml'
                assert (directory / '14-chooser-after-exit.png').is_file()
                exit_count += 1
                failure = None
            else:
                assert result['stage'] == '3d return_to_chooser native teardown'
                assert result['error'] == 'Missing actual native teardown marker: closeSignalAcknowledged'
                assert final['closeReason'] == 'return_to_chooser' and final['closeSignalAcknowledged'] is False
                assert not (directory / '14-chooser-after-exit.png').exists()
                failure_observations = lines(directory / 'failure-host-observations.log')
                assert [item['phase'] for item in failure_observations] == ['before_final_diagnostics', 'after_final_diagnostics']
                assert all(item['host'] == final and item['engine_pids'] == [] for item in failure_observations)
                assert final['receivedEvents'] == '19' and final['acceptedIntents'] == final['receivedIntents'] == '18'
                start_line = next(event['line'] for event in process_events if 'am_proc_start' in event['text'])
                chooser_resumes = [{'line': n, 'text': text} for n, text in enumerate(events, 1)
                    if n > start_line and re.search(r'\s' + str(result['device']['chooser_pid']) + r'\s+'
                    + str(result['device']['chooser_pid']) + r'\s+I\s+wm_on_resume_called:', text)
                    and 'dev.partydeck.godot.compare.ComparisonActivity' in text]
                assert len(chooser_resumes) == 1
                assert not (runtime / mode / 'scene-exit').exists() and not (runtime / mode / 'native-exit').exists()
                chooser_xml = runtime / 'last-ui.xml'
                failure = {'expected_route': 'return_to_chooser', 'observed_route': 'return_to_chooser',
                           'close_signal_acknowledged': False, 'actual_lobby_intent_accepted': True,
                           'failure_observations': original(directory / 'failure-host-observations.log'),
                           'chooser_resume_events': chooser_resumes, 'final_engine_pids': [],
                           'dedicated_teardown_receipt_present': False,
                           'fresh_scene_exit_and_native_back_attempted': False}
            for launch in ['launch_2d', 'launch_3d']:
                nodes = [node for node in ET.parse(chooser_xml).iter('node') if node.get('resource-id', '').endswith('/' + launch)]
                assert len(nodes) == 1 and nodes[0].get('enabled') == nodes[0].get('clickable') == 'true'
                assert nodes[0].get('package') == 'dev.partydeck.godot.compare'

            if name == 'match':
                winner = read(directory / '12-winner.json')
                assert winner['revision'] == final['revision'] == '41'
                assert winner['publicState']['roundNumber'] == final['publicState']['roundNumber'] == 14
                assert winner['publicState']['phase'] == final['publicState']['phase'] == 'FINISHED'
                assert winner['publicState']['winnerPresent'] and final['publicState']['winnerPresent']
                assert winner['acceptedIntents'] == '17' and final['acceptedIntents'] == '18'
                backgrounds = [host for host in observations if host['lifecycle'] == 'background']
                assert backgrounds and all(not host['foreground'] and host['coverVisible'] and not host['foregroundFrameReady']
                                           and host['capturePolicy'] == 'recents_disabled' for host in backgrounds)
                for capture_name, concealed, selected in [('01-concealed', True, 0), ('02-revealed', False, 0),
                        ('03-selected', False, 1), ('04-covered', True, 0), ('07-resumed-concealed', True, 0)]:
                    host = read(directory / (capture_name + '.json'))
                    assert host['enginePid'] == pid and host['presentationId'] == presentation
                    assert host['revision'] == '0' and host['acceptedIntents'] == '0'
                    diag = host['diagnostics']
                    assert diag['handConcealed'] is concealed and diag['selectedCount'] == selected
                    if concealed:
                        assert diag['privateFaceCount'] == diag['privateLabelCount'] == 0
                    else:
                        assert diag['privateFaceCount'] == 5 and diag['privateLabelCount'] >= 5
                outcomes = {str(host['publicState']['roundNumber']): {key: host['publicState'][key] for key in ['truthful', 'burnedOut']}
                            for host in observations if host['publicState']['phase'] in ['ROUND_ENDED', 'FINISHED']}
                assert len(outcomes) == 14 and outcomes == result['mode_results'][0]['outcomes']
            else:
                fresh = read(directory / '01-fresh-concealed.json')
                assert fresh['revision'] == final['revision'] == '0'
                assert fresh['diagnostics']['handConcealed'] is True
                assert all(fresh['diagnostics'][key] == 0 for key in ['privateFaceCount', 'privateLabelCount', 'selectedCount'])
                assert final['acceptedIntents'] == final['receivedIntents'] == '0'
            entries.append({'name': name, 'engine_pid': pid, 'presentation_id': presentation,
                            'observations_count': len(observations), 'accepted_intent_counts': counts,
                            'accepted_intent_transitions': transitions, 'final_host': final,
                            'completed_requested_exit_route': not failed_close,
                            'actual_os_process_death_observed': True, 'os_process_events': process_events,
                            'teardown_source': str(teardown_path) if teardown_path.exists() else None,
                            'scene_input_geometry_records': len(geometry), 'scene_capture_crop_hashes': len(capture_rows),
                            'egl_error_lines': egl_lines, 'shader_cache_warning_pairs_at_error_priority': warning_pairs,
                            'destruction_log_lines': termination_lines, 'close_acknowledgment_failure': failure,
                            'native_back_system_events': native_back_events})
        assert len({entry['engine_pid'] for entry in entries}) == len({entry['presentation_id'] for entry in entries}) == len(actual_entries)
        assert len(scene_pairs) == (10 if not expected_pass else 12)
        all_entry_records.extend(entries)
        evidence_paths = sorted(path for path in (base / 'android').rglob('*') if path.is_file() and path.suffix != '.png')
        evidence_paths.append(base / 'package-inputs.json')
        audit['android'].append({'artifact': artifact, 'mode': mode, 'font_scale': float(scale),
            'source_directory': str(runtime), 'source_revision': REV, 'source_revision_exact': True,
            'passed': result['passed'], 'stage': result.get('stage'), 'error': result.get('error'),
            'captures': captures, 'scene_pairs': scene_pairs, 'entries': entries,
            'native_input_records': len(native_inputs), 'parsed_xml_files': len(xml_files),
            'evidence': [original(path) for path in evidence_paths]})

assert native_count == 71 and len(audit['excluded']) == 4
assert crop_count == 46 and geometry_count == 151 and native_input_count == 347
assert len(all_entry_records) == 10 and exit_count == 9 and warning_pair_count == 8
assert sum(bool(entry['native_back_system_events']) for entry in all_entry_records) == 1
assert sum(entry['close_acknowledgment_failure'] is not None for entry in all_entry_records) == 1

# Independently check the companion authority run and all original receipts.
desktop_source = CI / 'godot-comparison-builds/godot/qualification/build/ci/desktop'
report = read(desktop_source / 'report.json')
assert report['sourceCommit'] == REV and report['workingTreeDirty'] is False
assert report['status'] == 'passed' and report['sameAuthorityTrace'] is True
assert report['rendererArtifact']['sha256'] == PACK
results = [read(desktop_source / mode / 'result.json') for mode in ['2d', '3d']]
assert report['results'] == results and results[0]['authorityTrace'] == results[1]['authorityTrace']
desktop_records = []
listed_desktop = {record['path']: record for record in inventory['desktop']}
for mode, result in zip(['2d', '3d'], results):
    assert result['rendererExitCode'] == 0 and len(result['authorityTrace']) == 42
    assert [result[key] for key in ['viewerPlays', 'viewerChallenges', 'roundsAdvanced']] == [2, 2, 13]
    trace_sha = hashlib.sha256(json.dumps(result['authorityTrace'], separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    assert trace_sha == result['authorityTraceSha256'] == summary['desktop']['traceSha256']
    captures_by_path = {record['path']: record for record in result['captures']}
    for path in sorted((desktop_source / mode).glob('*.png')):
        receipt = read(path.with_suffix('.receipt.json'))
        assert receipt == captures_by_path[str(path.relative_to(desktop_source))]
        for key in ['sourceCommit', 'workingTreeDirty', 'sourceFingerprintSha256', 'rendererArtifact', 'runStartedUtc']:
            assert receipt[key] == report[key]
        capture = png(path)
        assert capture['sha256'] == receipt['sha256'] == listed_desktop[str(path)]['sha256']
        assert (capture['width_px'], capture['height_px']) == (receipt['width'], receipt['height']) == (430, 932)
        assert receipt['textScale'] == 1.0 and receipt['reduceMotion'] is True and receipt['seed'] == 2
        view = next(view for view in result['authorityTrace'] if view['revision'] == receipt['authorityRevision'])
        assert view['viewSha256'] == receipt['authorityViewSha256']
        old = GALLERY / 'godot-desktop-34446327045' / path.relative_to(desktop_source)
        assert sha(old) == capture['sha256']
        capture.update(mode=mode, receipt_source=str(path.with_suffix('.receipt.json')),
                       previously_reviewed_identical_original=str(old.relative_to(REPO)))
        desktop_records.append(capture)
    assert not re.search(r'(?m)^\s*(SCRIPT ERROR|ERROR|Parse Error|Failed to load script)', (desktop_source / mode / 'godot.log').read_text())
assert len(desktop_records) == len(listed_desktop) == 22
audit['desktop'] = {'source_directory': str(desktop_source), 'source_revision': REV, 'source_revision_exact': True,
    'working_tree_dirty': False, 'source_fingerprint_sha256': report['sourceFingerprintSha256'],
    'report': original(desktop_source / 'report.json'), 'captures': desktop_records,
    'authority_trace_sha256': trace_sha,
    'evidence': [original(path) for path in sorted(desktop_source.rglob('*')) if path.is_file() and path.suffix != '.png']}

# Internal contact sheets are separate from the original gallery inventory.
tree = ast.parse(Path('/tmp/partydeck-gallery-queued-source-audit.py').read_text())
sheet_helper = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'sheets']
assert len(sheet_helper) == 1
exec(compile(ast.Module(body=sheet_helper, type_ignores=[]), 'internal sheet helper only', 'exec'))
for case in audit['android']:
    audit['review_sheets'].extend(sheets(case['artifact'], case['captures'], Path(case['source_directory']), width=480))
assert len(audit['review_sheets']) == 26
assert sum(len(sheet['originals']) for sheet in audit['review_sheets']) == 71

metadata_paths = [Path(record['path']) for record in frozen_records if Path(record['path']).is_relative_to(CI)] + [frozen_path, pack_receipt_path]
build_source = CI / 'godot-comparison-builds/godot/qualification/build'
build_paths = [build_source / relative for relative in [
    'toolchain/install.receipt.json', 'renderer/partydeck-last-light.receipt.json',
    'ci/native-boundary/runtime.log', 'ci/native-boundary/results/report.json', 'ci/android-checker-tests.log',
    'modules/androidHost/reports/lint-results-debug.txt', 'modules/androidHost/reports/lint-results-debug.xml',
    'modules/androidHost/outputs/apk/release/output-metadata.json']]
build_paths += sorted((build_source / 'renderer/pack-logs').glob('*'))
build_paths += sorted(path for path in (build_source / 'modules').rglob('*.xml') if 'test-results' in path.parts)
assert all(path.is_file() for path in build_paths)
audit['provenance'] = {
    'run': '34450246541', 'source_revision': REV, 'source_revision_exact': True,
    'workflow_conclusion': 'failure', 'producer_receipt_conclusion': None,
    'frozen_audit': original(frozen_path), 'frozen_record_hashes_verified': len(frozen_records),
    'source_archive': original(Path(source_archive['archivePath'])),
    'immutable_source_files_byte_matched_to_tarball': len(source_matches),
    'renderer_source_input_hashes_verified': len(input_paths),
    'package_identities_verified': packages, 'pack_sha256': PACK, 'runtime_apk_sha256': APK,
    'all_pack_members_verified': len(pack_inventory['entries']),
    'exact_source_files': source_records,
    'metadata_evidence': [original(path) for path in sorted(set(metadata_paths))],
    'build_evidence': [original(path) for path in sorted(set(build_paths))],
    'engine_auditor_scripts': [original(Path(frozen[key]['path'])) for key in ['auditScript', 'finalizationScript']],
    'runtime_pngs': native_count, 'excluded_preparation_pngs': 4,
    'scene_crop_hashes_verified': crop_count, 'scene_input_geometries_verified': geometry_count,
    'native_input_records_verified': native_input_count, 'process_entries_verified': len(all_entry_records),
    'completed_requested_exit_routes': exit_count, 'failed_close_acknowledgment_routes': 1,
    'native_back_routes_executed_and_passed': 1, 'normal_3d_fresh_scene_exit_or_back_attempted': False,
    'process_logs_with_retained_egl_error': 10,
    'shader_cache_warning_pairs_at_error_priority': warning_pair_count,
    'process_logs_with_shader_cache_warning_pairs_at_error_priority': warning_log_count,
    'scope_limits': frozen['limits'],
    'excluded_interrupted_extraction': frozen['collectionInterruption'],
    'new_application_executions': 0, 'new_builds_or_tests': 0, 'git_commands_run': 0,
}
out = Path('/tmp/partydeck-gallery-1372-source-audit.json')
out.write_text(json.dumps(audit, indent=2) + '\n')
print(json.dumps({'output': str(out), 'sha256': sha(out),
    'native_runtime_pngs': native_count, 'excluded_preparation_pngs': 4,
    'desktop_pngs_matching_prior_reviewed_bytes': len(desktop_records),
    'scene_crop_hashes': crop_count, 'scene_input_geometry_records': geometry_count,
    'native_input_records': native_input_count, 'process_entries': len(all_entry_records),
    'completed_requested_exit_routes': exit_count, 'retained_egl_error_logs': 10,
    'shader_cache_warning_pairs': warning_pair_count, 'review_sheets_pending_inspection': len(audit['review_sheets']),
    'immutable_source_files_matched_to_tarball': len(source_matches), 'pack_members_verified': len(pack_inventory['entries'])}, indent=2))
