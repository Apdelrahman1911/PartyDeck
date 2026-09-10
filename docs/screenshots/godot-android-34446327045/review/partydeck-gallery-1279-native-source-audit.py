"""Read-only gallery audit of frozen CI 34446327045; never executes the app."""
import collections
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from PIL import Image

REPO = Path('/root/projects/PartyDeck')
CI = Path('/tmp/partydeck-engine-ci/34446327045')
REV = 'b7f2f4f2c2d03b8e599d4b0fc73bf2d35f6640eb'
PACK = '0ed324c19016f28987d6294f915c107f62234670b149f73bab585af93e29ae6d'
APK = '8f6cbccbb1313ff2f0d17da5879275ebfc0f25b5d8592ce884d02bc3f91d9a76'
SOURCE = CI / 'source-b7f2f4f'


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
        assert picture.format == 'PNG', path
        picture.verify()
    with Image.open(path) as picture:
        picture.load()
        record.update(width_px=picture.width, height_px=picture.height)
    return record


def check_original(record):
    path = Path(record.get('source_original', record.get('path')))
    assert sha(path) == record['sha256'], path
    assert path.stat().st_size == record['bytes'], path


local_path = Path('/tmp/partydeck-gallery-1279-local-source-audit.json')
audit = read(local_path)
checked_local_paths = set()


def recheck_records(value):
    if isinstance(value, dict):
        if {'source_original', 'sha256', 'bytes'} <= value.keys():
            if value['source_original'] not in checked_local_paths:
                check_original(value)
                checked_local_paths.add(value['source_original'])
        for child in value.values():
            recheck_records(child)
    elif isinstance(value, list):
        for child in value:
            recheck_records(child)


recheck_records(audit)
frozen_path = CI / 'audit-frozen.json'
assert sha(frozen_path) == '9590bdb307e30dad47f1ce018219b55582c7cb1fe9e25928e7a51a9f2cb3f698'
frozen = read(frozen_path)
assert frozen['headSha'] == REV and frozen['workflowConclusion'] == 'failure'
frozen_records = frozen['files'] + frozen['artifactDownloadReceipts'] + frozen['jobLogs'] + [frozen['auditScript']]
for record in frozen_records:
    check_original(record)
summary = read(CI / 'evidence-summary.json')
producer = read(CI / 'producer-evidence-summary.json')
assert summary['headSha'] == producer['headSha'] == REV
assert summary['conclusion'] == 'failure' and producer['conclusion'] is None
run = read(CI / 'last-run-status.json')
assert run['head_sha'] == REV and run['status'] == 'completed' and run['conclusion'] == 'failure'
assert str(run['id']) == '34446327045'
assert summary['packSha256'] == PACK and summary['packBytes'] == 1546216

packages = []
for record in frozen['identity']['packages']:
    check_original(record)
    path = Path(record['path'])
    with zipfile.ZipFile(path) as archive:
        pack_paths = [name for name in archive.namelist() if name.endswith('/assets/partydeck-last-light.pck') or name == 'assets/partydeck-last-light.pck']
        assert len(pack_paths) == 1
        assert hashlib.sha256(archive.read(pack_paths[0])).hexdigest() == record['embeddedPackSha256'] == PACK
    packages.append(original(path))
assert packages[0]['sha256'] == APK
assert sha(CI / 'godot-comparison-runtime-apk/renderer/partydeck-last-light.pck') == PACK
source_archive = read(CI / 'source-archive.json')
assert source_archive['headSha'] == REV and source_archive['sourceDirectory'] == str(SOURCE)
check_original({'path': source_archive['archivePath'], 'bytes': source_archive['bytes'], 'sha256': source_archive['sha256']})

source_paths = [
    'godot/android-checks/run.py', 'godot/android-checks/evidence.py', 'scripts/smoke-android-ui.py',
    'godot/renderer/scripts/main.gd', 'godot/renderer/scripts/renderer_controller.gd',
    'godot/renderer/presentations/two_d/table.gd', 'godot/renderer/presentations/three_d/table.gd',
]
# Retain the exact host implementation relevant to native close and destruction.
source_paths += [str(path.relative_to(SOURCE)) for path in sorted((SOURCE / 'godot').rglob('*.kt'))
                 if path.name in ['GodotGameActivity.kt', 'ComparisonActivity.kt', 'NativeRendererBridge.kt']]
source_records = []
for relative in source_paths:
    path = SOURCE / relative
    committed = subprocess.check_output(['git', 'show', REV + ':' + relative], cwd=REPO)
    assert path.read_bytes() == committed, relative
    source_records.append(original(path))
runner = {Path(relative).name: sha(SOURCE / relative) for relative in source_paths[:3]}
assert sha(SOURCE / 'godot/renderer/presentations/two_d/table.gd') == '46fde47e8da4dbb8c8f91e0a4215ceabb4040a8ddfcbab54c8573d5b9cc96eef'

inventory = read(CI / 'original-image-inventory.json')
assert inventory['headSha'] == REV and inventory['packSha256'] == PACK and inventory['runtimeApkSha256'] == APK
assert inventory['nativePngCount'] == len(inventory['native']) == 78
native_inventory = {record['path']: record for record in inventory['native']}
assert len(native_inventory) == 78
native_records = {}
for path, expected in native_inventory.items():
    record = png(Path(path))
    assert record['sha256'] == expected['sha256'] and record['bytes'] == expected['bytes']
    assert (record['width_px'], record['height_px']) == (expected['width'], expected['height']) == (720, 1600)
    native_records[path] = record

audit['android'] = []
audit['excluded'] = []
native_count = crop_count = geometry_count = native_input_count = exit_count = warning_log_count = 0
all_entry_records = []
summary_by_artifact = {case['artifact']: case for case in summary['androidCases']}
destroy_flags = ['bridgeClosed', 'nativeDestroyRequested', 'nativeDestroyReturned', 'nativeTerminating',
                 'nativeForceQuitCallback', 'processExitRequested', 'closeSignalAcknowledged']
for mode in ['2d', '3d']:
    for scale in ['1.0', '2.0']:
        artifact = f'godot-android-{mode}-font-{scale}-debug'
        base = CI / artifact
        runtime = base / 'android/runtime'
        case_summary = summary_by_artifact[artifact]
        result = read(runtime / 'result.json')
        assert result['modes'] == [mode] and result['passed'] == (mode == '2d') == case_summary['passed']
        assert result['source_sha256'] == runner
        assert result['apk_sha256'] == result['device']['installed_apk_sha256'] == APK
        assert result['embedded_pck_sha256'] == PACK
        assert result['apk_bytes'] == packages[0]['bytes'] and result['embedded_pck_bytes'] == 1546216
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
        assert len(captures) == (19 if mode == '2d' else 18)
        native_count += len(captures)
        for record in captures:
            expected = native_inventory[record['source_original']]
            assert expected['case'] == artifact and expected['wholeCasePassed'] == result['passed']
            assert expected['wholeCaseStage'] == result.get('stage')
        prep = base / 'android/emulator/preparation/attempt-1/final-screen.png'
        prep_record = dict(native_records[str(prep)])
        prep_record.update(ci_run='34446327045', source_revision=REV,
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
        assert [entry['name'] for entry in actual_entries] == ['match', 'scene-exit', 'native-exit']
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
            failed_back = mode == '3d' and name == 'native-exit'
            assert teardown_path.exists() is (not failed_back)
            if not failed_back:
                teardown = read(teardown_path)
                assert teardown['host'] == final
                assert all(teardown[key] for key in ['old_pid_absent', 'engine_process_absent', 'both_entries_enabled', 'upstream_renderer_timeout_absent'])
                assert teardown['surviving_chooser_pid'] == result['device']['chooser_pid']
                expected_route = {'match': 'return_to_chooser', 'scene-exit': 'renderer_exit', 'native-exit': 'native_close'}[name]
                assert final['closeReason'] == expected_route
                chooser_xml = directory / '14-chooser-after-exit.xml'
                assert (directory / '14-chooser-after-exit.png').is_file()
                exit_count += 1
                failure = None
            else:
                assert result['stage'] == '3d native_back native teardown'
                assert result['error'] == 'Native host did not finish the expected close route.'
                assert final['closeReason'] == 'renderer_exit'
                assert not (directory / '14-chooser-after-exit.png').exists()
                failure_observations = lines(directory / 'failure-host-observations.log')
                assert [item['phase'] for item in failure_observations] == ['before_final_diagnostics', 'after_final_diagnostics']
                assert all(item['host'] == final and item['engine_pids'] == [] for item in failure_observations)
                fresh = read(directory / '01-fresh-concealed.json')
                assert fresh['receivedEvents'] == '1' and final['receivedEvents'] == '2'
                start_line = next(event['line'] for event in process_events if 'am_proc_start' in event['text'])
                back_events = [{'line': n, 'text': text} for n, text in enumerate(events, 1)
                               if start_line < n < deaths[0]['line'] and 'key_back_press' in text]
                assert len(back_events) == 1
                chooser_resumes = [{'line': n, 'text': text} for n, text in enumerate(events, 1)
                    if n > back_events[0]['line'] and re.search(r'\s' + str(result['device']['chooser_pid']) + r'\s+'
                    + str(result['device']['chooser_pid']) + r'\s+I\s+wm_on_resume_called:', text)
                    and 'dev.partydeck.godot.compare.ComparisonActivity' in text]
                assert len(chooser_resumes) == 1
                chooser_xml = runtime / 'last-ui.xml'
                failure = {'expected_route': 'native_back', 'observed_route': 'renderer_exit',
                           'renderer_exit_event_delta': 1, 'failure_observations': original(directory / 'failure-host-observations.log'),
                           'os_back_events': back_events, 'chooser_resume_events': chooser_resumes,
                           'final_engine_pids': [], 'dedicated_teardown_receipt_present': False}
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
                            'completed_requested_exit_route': not failed_back,
                            'actual_os_process_death_observed': True, 'os_process_events': process_events,
                            'teardown_source': str(teardown_path) if teardown_path.exists() else None,
                            'scene_input_geometry_records': len(geometry), 'scene_capture_crop_hashes': len(capture_rows),
                            'egl_error_lines': egl_lines, 'shader_cache_warning_pairs_at_error_priority': warning_pairs,
                            'destruction_log_lines': termination_lines, 'native_back_failure': failure})
        assert len({entry['engine_pid'] for entry in entries}) == len({entry['presentation_id'] for entry in entries}) == 3
        assert len(scene_pairs) == 12
        all_entry_records.extend(entries)
        evidence_paths = sorted(path for path in (base / 'android').rglob('*') if path.is_file() and path.suffix != '.png')
        evidence_paths.append(base / 'package-inputs.json')
        audit['android'].append({'artifact': artifact, 'mode': mode, 'font_scale': float(scale),
            'source_directory': str(runtime), 'source_revision': REV, 'source_revision_exact': True,
            'passed': result['passed'], 'stage': result.get('stage'), 'error': result.get('error'),
            'captures': captures, 'scene_pairs': scene_pairs, 'entries': entries,
            'native_input_records': len(native_inputs), 'parsed_xml_files': len(xml_files),
            'evidence': [original(path) for path in evidence_paths]})

assert native_count == 74 and len(audit['excluded']) == 4
assert crop_count == 48 and geometry_count == 156 and native_input_count == 354
assert len(all_entry_records) == 12 and exit_count == 10 and warning_log_count == 10
assert len({record['source_original'] for case in audit['android'] for record in case['captures']}) == 74
visual_path = Path('/tmp/partydeck-gallery-1279-visual-review.json')
visual = read(visual_path)
assert visual['batch_originals'] == 150
assert visual['originals_visually_reviewed_in_internal_contact_sheets'] == 106
assert visual['desktop_originals_byte_matched_to_previously_reviewed_originals'] == 44

metadata_paths = [Path(record['path']) for record in frozen_records if Path(record['path']).is_relative_to(CI)] + [frozen_path]
metadata_paths += [CI / 'godot-comparison-runtime-apk/renderer/partydeck-last-light.receipt.json']
metadata_paths += [path for path in sorted((CI / 'godot-comparison-builds').rglob('*'))
                   if path.is_file() and path.name in ['comparison-build.json', 'package-inputs.json', 'output-metadata.json']]
audit['android_provenance'] = {
    'run': '34446327045', 'source_revision': REV, 'source_revision_exact': True,
    'workflow_conclusion': 'failure', 'producer_receipt_conclusion': None,
    'frozen_audit': original(frozen_path), 'frozen_record_hashes_verified': len(frozen_records),
    'source_archive_hash_verified': True, 'package_identities_verified': packages,
    'pack_sha256': PACK, 'runtime_apk_sha256': APK,
    'exact_git_source_files_verified': source_records,
    'metadata_evidence': [original(path) for path in sorted(set(metadata_paths))],
    'engine_auditor_script': original(Path(frozen['auditScript']['path'])),
    'runtime_pngs': native_count, 'excluded_preparation_pngs': 4,
    'scene_crop_hashes_verified': crop_count, 'scene_input_geometries_verified': geometry_count,
    'native_input_records_verified': native_input_count, 'process_entries_verified': len(all_entry_records),
    'completed_requested_exit_routes': exit_count, 'failed_native_back_routes': 2,
    'process_logs_with_retained_egl_error': 12, 'process_logs_with_shader_cache_warning_pairs_at_error_priority': warning_log_count,
    'scope_limits': [
        'API 35 debug emulator local-practice comparison only; no KMP production factory, optimized native, physical-device, accessibility, audio-dormancy or full native-matrix acceptance.',
        'Both final 3D native Back entries fail the requested route despite actual child process death and chooser restoration.',
        'There is no separate raw shell process-list attachment. Executed checker receipts, exact source, OS process-death events, destruction logs and fresh PIDs support process absence.',
        'All twelve process logs retain the EGL removeVertexArrayObject ERROR; ten also retain known shader-cache warning pairs at error priority. No clean-driver-log claim.',
        'The later source-only Reveal correction is not in this exact pack.',
    ],
}
audit['review'] = {'local_audit': original(local_path), 'visual_review': original(visual_path),
                  'local_source_paths_rechecked': len(checked_local_paths),
                  'new_runtime_executions': 0, 'new_builds_or_tests': 0}
out = Path('/tmp/partydeck-gallery-1279-source-audit.json')
out.write_text(json.dumps(audit, indent=2) + '\n')
print(json.dumps({'output': str(out), 'sha256': sha(out), 'local_sources_rechecked': len(checked_local_paths),
    'native_runtime_pngs': native_count, 'excluded_preparation_pngs': 4, 'scene_crop_hashes': crop_count,
    'scene_input_geometry_records': geometry_count, 'native_input_records': native_input_count,
    'process_entries': len(all_entry_records), 'completed_requested_exit_routes': exit_count,
    'retained_egl_error_logs': 12, 'shader_cache_warning_logs': warning_log_count}, indent=2))
