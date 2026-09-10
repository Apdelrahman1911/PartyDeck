"""Audit exact run 34456443339, preserving both Close acknowledgment failures."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

run, head = sys.argv[1:3]
assert run == '34456443339' and head == 'dad1c11741bd4322bb8b2afb9f18f3db5f50c919'
base = Path('/tmp/partydeck-engine-ci') / run
source = base / ('source-' + head[:7])
sys.path.insert(0, str(source / 'godot/android-checks'))
from evidence import read_png, completed_teardown, CheckFailure

def read(path):
    return json.loads(path.read_text())

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

def png_record(path):
    picture = read_png(path.read_bytes())
    return {'path': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size,
            'width': picture.width, 'height': picture.height, 'pngVerifiedAndDecoded': True}

producer_path = base / 'producer-evidence-summary.json'
summary = read(producer_path)
assert summary['producerAuditPassed'] and summary['headSha'] == head
summary['producerAuditReceiptSha256'] = digest(producer_path)
run_status = read(base / 'last-run-status.json')
assert str(run_status['id']) == run and run_status['head_sha'] == head
assert run_status['status'] == 'completed'
summary['conclusion'] = run_status['conclusion']
summary['runStatusReceiptSha256'] = digest(base / 'last-run-status.json')
summary['jobConclusions'] = [{key: job[key] for key in ['id', 'name', 'status', 'conclusion']}
                            for job in read(base / 'last-jobs-status.json')['jobs']]
package_sha = summary['packages'][0]['sha256']
pack_sha = summary['packSha256']
source_hashes = {path.name: digest(path) for path in [source / 'godot/android-checks/run.py',
    source / 'godot/android-checks/evidence.py', source / 'scripts/smoke-android-ui.py']}
correlation_path = base / 'source-close-barrier-correlation.json'
correlation = read(correlation_path)
assert correlation['headSha'] == head and correlation['sourceArchiveVerified']
assert correlation['checkerAndWorkflowUnchanged'] and correlation['strictTeardownCheckUnchanged']
assert correlation['checkerSourceHashes'] == source_hashes
summary['sourceCloseBarrierCorrelationReceiptSha256'] = digest(correlation_path)
expected_intents = {'play': 2, 'challenge': 2, 'advance_round': 13, 'return_to_lobby': 1}
host_fields = ['enginePid', 'presentationId', 'displayDensity', 'readyAccepted', 'foregroundFrameReady',
    'acceptedIntents', 'receivedIntents', 'receivedEvents', 'revision', 'lifecycle', 'lastIntentType',
    'closeReason', 'bridgeClosed', 'nativeDestroyRequested', 'nativeDestroyReturned', 'nativeTerminating',
    'nativeForceQuitCallback', 'nativeDestroyElapsedMs', 'processExitRequested', 'publicState',
    'diagnosticsRequested', 'diagnosticsTimedOut', 'closeSignalAcknowledged']
cases = []
for mode in ['2d', '3d']:
    for scale in ['1.0', '2.0']:
        name = f'godot-android-{mode}-font-{scale}-debug'
        artifact = base / name
        runtime = artifact / 'android/runtime'
        result = read(runtime / 'result.json')
        assert result['passed'] is (mode == '2d')
        assert result['limits_seconds'] == {'setup': 600, 'per_mode': 900, 'cleanup': 180}
        assert not result.get('cleanup_errors')
        package_input = read(artifact / 'package-inputs.json')
        assert package_input['sourceCommit'] == head
        assert package_input['packSha256'] == package_input['embeddedPackSha256'] == pack_sha
        assert package_input['apkSha256'] == package_sha
        assert result['source_sha256'] == source_hashes
        assert result['apk_sha256'] == result['device']['installed_apk_sha256'] == package_sha
        assert result['embedded_pck_sha256'] == pack_sha
        assert result['device']['font_scale'] == scale and result['device']['sdk'] == 35
        preparation = read(artifact / 'android/emulator/preparation/preparation-result.json')
        assert preparation['passed'] and preparation['reboot_attempted'] is False
        entries = []
        entry_names = [entry['name'] for entry in result['mode_results'][0]['entries']]
        assert entry_names == (['match', 'scene-exit', 'native-exit'] if result['passed'] else ['match'])
        assert set(entry_names) == {path.name for path in (runtime / mode).iterdir() if path.is_dir()}
        event_path = runtime / 'events.log'
        event_lines = event_path.read_text().splitlines()
        for kind in entry_names:
            directory = runtime / mode / kind
            observations = lines(directory / 'host-observations.log')
            failure_observations = lines(directory / 'failure-host-observations.log')
            teardown_path = directory / 'teardown.json'
            teardown = read(teardown_path) if teardown_path.exists() else None
            final = teardown['host'] if teardown else failure_observations[-1]['host']
            pid, presentation = final['enginePid'], final['presentationId']
            owned_path = directory / 'final-process-logcat.log'
            owned = owned_path.read_text()
            matches = lambda pattern: [{'line': n, 'text': line} for n, line in enumerate(owned.splitlines(), 1)
                                      if re.search(pattern, line)]
            fatal = matches(r'FATAL EXCEPTION:|Fatal signal [0-9]+|SCRIPT ERROR:|SHADER ERROR:|Parse Error:|Unable to exit the renderer')
            priority_errors = matches(r'\bE\s+(?:godot|Godot)\s*:')
            shader_warning_pairs, unclassified_priority, pending_warning = [], [], None
            for item in priority_errors:
                parsed = re.fullmatch(r'\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s+(\d+)\s+(\d+)\s+E\s+godot\s*:\s*(.*)', item['text'])
                if parsed and parsed.group(3) == 'WARNING: Failed to load cached shader, recompiling.' and pending_warning is None:
                    pending_warning = (parsed.group(1,2), item)
                elif (parsed and parsed.group(3) == 'at: _load_from_cache (drivers/gles3/shader_gles3.cpp:615)'
                      and pending_warning and parsed.group(1,2) == pending_warning[0]):
                    shader_warning_pairs.append([pending_warning[1], item])
                    pending_warning = None
                else:
                    unclassified_priority.append(item)
            if pending_warning:
                unclassified_priority.append(pending_warning[1])
            other_errors = matches(r'\bERROR:')
            terminations = matches(r'Exiting render thread|Destroying Godot Engine|OnGodotTerminating')
            captures = []
            for capture in lines(directory / 'captures.log'):
                png = directory / (capture['name'] + '.png')
                host = read(directory / (capture['name'] + '.json'))
                assert host['enginePid'] == pid and host['presentationId'] == presentation == capture['presentationId']
                assert host['revision'] == capture['revision'] and host['engineSurface'] == capture['surface']
                assert host['readyAccepted'] and host['foregroundFrameReady'] and host['foreground']
                assert not host['coverVisible'] and host['lifecycle'] == 'active'
                assert host['diagnostics']['presentationId'] == presentation
                assert host['diagnostics']['revision'] == host['revision']
                pixels = read_png(png.read_bytes()).crop(capture['surface'])
                assert hashlib.sha256(pixels).hexdigest() == capture['engine_rgb_sha256']
                captures.append({'name': capture['name'], 'sha256': digest(png),
                    'engineRgbSha256': capture['engine_rgb_sha256'], 'presentationId': presentation,
                    'revision': host['revision'], 'diagnosticSequence': host['diagnostics']['sequence']})
            inputs = lines(directory / 'scene-input-geometry.log')
            for item in inputs:
                assert item['presentationId'] == presentation
                diagnostic_matches = [host for host in observations if 'diagnostics' in host
                    and host['diagnostics']['sequence'] == item['diagnosticSequence']
                    and host['diagnostics']['requestId'] == item['diagnosticRequest']
                    and host['revision'] == item['revision']]
                assert diagnostic_matches, (kind, item)
                matching_geometry = [control for host in diagnostic_matches for control in host['diagnostics']['controls']
                    if control['group'] == item['group'] and control['cardIndex'] == item['cardIndex']
                    and control['rect'] == item['rect'] and control['clipRect'] == item['clipRect']]
                assert matching_geometry, (kind, item)
                surface, viewport = item['engineSurface'], item['rootViewport']
                assert any(host['engineSurface'] == surface and host['diagnostics']['viewport'] == viewport
                           for host in diagnostic_matches)
                rect, clip = item['rect'], item['clipRect']
                if item['action'] == 'tap':
                    x = (item['coordinates']['x'] - surface['x']) * viewport['width'] / surface['width']
                    y = (item['coordinates']['y'] - surface['y']) * viewport['height'] / surface['height']
                    assert max(0, rect[0], clip[0]) <= x <= min(viewport['width'], rect[0]+rect[2], clip[0]+clip[2])
                    assert max(0, rect[1], clip[1]) <= y <= min(viewport['height'], rect[1]+rect[3], clip[1]+clip[3])
                elif item['action'] == 'swipe':
                    for point in ['start', 'end']:
                        px, py = item['coordinates'][point]
                        x = (px - surface['x']) * viewport['width'] / surface['width']
                        y = (py - surface['y']) * viewport['height'] / surface['height']
                        assert max(0, clip[0]) <= x <= min(viewport['width'], clip[0]+clip[2])
                        assert max(0, clip[1]) <= y <= min(viewport['height'], clip[1]+clip[3])
                    assert 0 < item['coordinates']['duration_ms'] <= 2000
                else:
                    raise AssertionError(item['action'])
            process_events = [{'line': number, 'text': line} for number, line in enumerate(event_lines, 1)
                if re.search(r'am_proc_(?:start|bound|died)\s*:\s*\[0,' + str(pid) + r',', line)]
            deaths = [event for event in process_events if 'am_proc_died' in event['text']]
            assert len(deaths) == 1 and 'dev.partydeck.godot.compare:godot' in deaths[0]['text']
            entry = {'name': kind, 'enginePid': pid, 'presentationId': presentation,
                'observations': len(observations), 'hostObservationsSha256': digest(directory / 'host-observations.log'),
                'finalHost': {key: final.get(key) for key in host_fields}, 'sceneInputs': len(inputs),
                'sceneInputActions': dict(Counter(item['action'] for item in inputs)),
                'sceneTapGroups': dict(Counter(item['group'] for item in inputs if item['action'] == 'tap')),
                'sceneTapCentersWithinReportedTargetClipAndViewport': True,
                'sceneInputGeometryMatchesRetainedDiagnosticSnapshot': True,
                'sceneSwipeEndpointsWithinReportedClipAndViewport': True,
                'verifiedSceneCaptureCount': len(captures), 'sceneCaptureProofs': captures,
                'ownedProcessLog': str(owned_path), 'ownedProcessLogSha256': digest(owned_path),
                'fatalOrExplicitRendererFailureMatches': fatal, 'enginePriorityErrorLines': priority_errors,
                'knownShaderCacheWarningTextPairs': shader_warning_pairs,
                'unclassifiedEnginePriorityErrorLines': unclassified_priority,
                'rawErrorTextMatches': other_errors, 'positiveTerminationLogLines': terminations,
                'osProcessEvents': process_events, 'actualOsProcessDeathObserved': True,
                'completedRequestedExitRoute': teardown is not None}
            close_events = []
            for number, line in enumerate(owned.splitlines(), 1):
                parsed = re.fullmatch(
                    r'\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s+(\d+)\s+(\d+)\s+I\s+'
                    r'(PartyDeckGodotBridge|PartyDeckGodotHost): Close '
                    r'(requested|dispatch started|native barrier|main callback|fallback) elapsed_ms=(\d+)', line)
                if parsed:
                    process, thread, tag, stage, elapsed = parsed.groups()
                    assert int(process) == pid
                    close_events.append({'line': number, 'text': line, 'pid': int(process), 'tid': int(thread),
                                         'tag': tag, 'stage': stage, 'elapsedRealtimeMs': int(elapsed)})
            expected_stages = (['requested', 'dispatch started', 'native barrier', 'main callback'] if teardown
                               else ['requested', 'fallback'])
            assert [event['stage'] for event in close_events] == expected_stages
            assert close_events[0]['tid'] == pid and close_events[-1]['tid'] == pid
            elapsed = {event['stage']: event['elapsedRealtimeMs'] for event in close_events}
            assert list(elapsed.values()) == sorted(elapsed.values())
            if teardown:
                assert close_events[1]['tid'] == close_events[2]['tid'] != pid
                assert final['closeSignalAcknowledged'] is True
            else:
                assert elapsed['fallback'] - elapsed['requested'] == {'1.0': 250, '2.0': 251}[scale]
                assert final['closeSignalAcknowledged'] is False
            entry['closeSignalLogObservation'] = {
                'events': close_events,
                'nativeBarrierObserved': 'native barrier' in elapsed,
                'dispatchObserved': 'dispatch started' in elapsed,
                'mainCallbackObserved': 'main callback' in elapsed,
                'fallbackObserved': 'fallback' in elapsed,
                'requestToDispatchMs': elapsed['dispatch started'] - elapsed['requested'] if teardown else None,
                'requestToNativeBarrierMs': elapsed['native barrier'] - elapsed['requested'] if teardown else None,
                'barrierToMainCallbackMs': elapsed['main callback'] - elapsed['native barrier'] if teardown else None,
                'requestToFallbackMs': elapsed['fallback'] - elapsed['requested'] if not teardown else None,
                'agreesWithFinalHostAcknowledgment': True,
                'scope': 'Observed exact-PID native log stages; absence of dispatch does not identify the scheduling cause.',
            }
            expected_reason = {'match': 'return_to_chooser', 'scene-exit': 'renderer_exit',
                               'native-exit': 'native_close' if mode == '2d' else 'native_back'}[kind]
            strict_error = None
            try:
                completed_teardown(final, expected_reason)
            except CheckFailure as error:
                strict_error = str(error)
            assert (strict_error is None) is (teardown is not None)
            if not teardown:
                assert strict_error == result['error']
            entry['archivedStrictTeardownCheck'] = {
                'passed': strict_error is None,
                'error': strict_error,
                'sourceSha256': source_hashes['evidence.py'],
            }
            transitions, prior = [], 0
            for number, item in enumerate(observations, 1):
                count = int(item['acceptedIntents'])
                assert count >= prior
                if count > prior:
                    assert count == prior + 1
                    transitions.append({'observationLine': number, 'acceptedIntents': count, 'type': item['lastIntentType'],
                        'revision': item['revision'], 'round': item['publicState']['roundNumber'],
                        'phase': item['publicState']['phase']})
                prior = count
            entry['acceptedIntentTransitions'] = transitions
            entry['independentIntentCounts'] = dict(Counter(item['type'] for item in transitions))
            if kind == 'match':
                assert entry['independentIntentCounts'] == expected_intents
                winner = read(directory / '12-winner.json')
                assert winner['revision'] == '41' and winner['publicState']['roundNumber'] == 14
                assert winner['publicState']['phase'] == 'FINISHED' and winner['publicState']['winnerPresent']
                assert int(winner['acceptedIntents']) == 17
                backgrounds = [item for item in observations if item['lifecycle'] == 'background']
                assert backgrounds and all(not item['foreground'] and item['coverVisible'] and not item['foregroundFrameReady']
                    and item['capturePolicy'] == 'recents_disabled' for item in backgrounds)
                resumed = read(directory / '07-resumed-concealed.json')
                diag = resumed['diagnostics']
                assert diag['handConcealed'] and diag['selectedCount'] == diag['privateFaceCount'] == diag['privateLabelCount'] == 0
                assert resumed['revision'] == '0' and int(resumed['acceptedIntents']) == 0
                outcomes = {str(item['publicState']['roundNumber']): {key: item['publicState'][key] for key in ['truthful','burnedOut']}
                    for item in observations if item['publicState']['phase'] in ['ROUND_ENDED','FINISHED']}
                assert outcomes == result['mode_results'][0]['outcomes'] and len(outcomes) == 14
                entry['observedOutcomesMatchResult'] = True
                entry['samePresentationBackgroundAndConcealedResumeVerified'] = True
                for capture_name, concealed, selected in [('01-concealed', True, 0), ('02-revealed', False, 0),
                        ('03-selected', False, 1), ('04-covered', True, 0), ('07-resumed-concealed', True, 0)]:
                    capture_host = read(directory / (capture_name + '.json'))
                    capture_diag = capture_host['diagnostics']
                    assert capture_host['revision'] == '0' and capture_host['acceptedIntents'] == '0'
                    assert capture_diag['handConcealed'] is concealed and capture_diag['selectedCount'] == selected
                    if concealed:
                        assert capture_diag['privateFaceCount'] == capture_diag['privateLabelCount'] == 0
                    else:
                        assert capture_diag['privateFaceCount'] == 5 and capture_diag['privateLabelCount'] >= 5
                entry['capturedConcealRevealSelectCoverAndResumeTransitionsVerified'] = True
            else:
                assert not transitions and int(final['acceptedIntents']) == int(final['receivedIntents']) == 0
                fresh = read(directory / '01-fresh-concealed.json')
                assert fresh['revision'] == '0' and fresh['diagnostics']['handConcealed']
                assert fresh['diagnostics']['selectedCount'] == fresh['diagnostics']['privateFaceCount'] == fresh['diagnostics']['privateLabelCount'] == 0
                expected_event_delta = 1 if kind == 'scene-exit' else 0
                assert int(final['receivedEvents']) - int(fresh['receivedEvents']) == expected_event_delta
                assert final['revision'] == fresh['revision']
                entry['verifiedExitEventDelta'] = expected_event_delta
            if teardown:
                reason = {'match': 'return_to_chooser', 'scene-exit': 'renderer_exit',
                          'native-exit': 'native_close' if mode == '2d' else 'native_back'}[kind]
                assert final['closeReason'] == reason and final['lifecycle'] == 'process_exit_requested'
                for flag in ['bridgeClosed', 'nativeDestroyRequested', 'nativeDestroyReturned', 'nativeTerminating',
                             'nativeForceQuitCallback', 'processExitRequested', 'closeSignalAcknowledged']:
                    assert final[flag] is True, flag
                for flag in ['old_pid_absent', 'engine_process_absent', 'both_entries_enabled', 'upstream_renderer_timeout_absent']:
                    assert teardown[flag] is True, flag
                assert teardown['surviving_chooser_pid'] == result['device']['chooser_pid']
                assert final == observations[-1] and not fatal and not unclassified_priority
                assert len(terminations) == 3
                assert all(int(item['authorityRejections']) == int(item['rejectedEvents']) == 0 for item in observations)
                assert all(item['enginePid'] == pid and item['presentationId'] == presentation for item in observations)
                assert all(not item['diagnosticsTimedOut'] for item in observations)
                chooser_xml = directory / '14-chooser-after-exit.xml'
                tree = ET.parse(chooser_xml)
                for launch in ['launch_2d', 'launch_3d']:
                    nodes = [node for node in tree.iter('node') if node.get('resource-id', '').endswith('/' + launch)]
                    assert len(nodes) == 1 and nodes[0].get('enabled') == 'true' and nodes[0].get('clickable') == 'true'
                    assert nodes[0].get('package') == 'dev.partydeck.godot.compare'
                entry['teardown'] = {key: value for key, value in teardown.items() if key != 'host'}
                entry['teardownReceiptSha256'] = digest(teardown_path)
                entry['chooserXmlSha256'] = digest(chooser_xml)
                entry['lifecycleReceiptAndLogsVerified'] = True
                if kind == 'native-exit' and mode == '3d':
                    start_line = next(event['line'] for event in process_events if 'am_proc_start' in event['text'])
                    end_line = deaths[0]['line']
                    back_events = [{'line': number, 'text': line} for number, line in enumerate(event_lines, 1)
                        if start_line < number < end_line and 'key_back_press' in line]
                    assert len(back_events) == 1 and entry['verifiedExitEventDelta'] == 0
                    entry['nativeBackSystemEvents'] = back_events
            else:
                assert mode == '3d' and scale in ['1.0', '2.0'] and kind == 'match' and not result['passed']
                assert result['stage'] == '3d return_to_chooser native teardown'
                assert result['error'] == 'Missing actual native teardown marker: closeSignalAcknowledged'
                assert final['lifecycle'] == 'process_exit_requested' and final['closeReason'] == 'return_to_chooser'
                assert final == observations[-1] and final['closeSignalAcknowledged'] is False
                for flag in ['bridgeClosed', 'nativeDestroyRequested', 'nativeDestroyReturned', 'nativeTerminating',
                             'nativeForceQuitCallback', 'processExitRequested']:
                    assert final[flag] is True, flag
                assert len(terminations) == 3 and not fatal and not unclassified_priority
                assert int(final['nativeDestroyElapsedMs']) >= 0
                assert not final['foreground'] and final['coverVisible'] and not final['foregroundFrameReady']
                assert all(not item['diagnosticsTimedOut'] for item in observations)
                assert all(int(item['authorityRejections']) == int(item['rejectedEvents']) == 0 for item in observations)
                assert all(item['enginePid'] == pid and item['presentationId'] == presentation for item in observations)
                assert final['acceptedIntents'] == final['receivedIntents'] == '18'
                assert final['receivedEvents'] == '19' and final['revision'] == '41'
                assert [observation['phase'] for observation in failure_observations] == ['before_final_diagnostics', 'after_final_diagnostics']
                assert all(observation['engine_pids'] == [] and observation['host'] == final for observation in failure_observations)
                start_line = next(event['line'] for event in process_events if 'am_proc_start' in event['text'])
                chooser_resumes = [{'line': number, 'text': line} for number, line in enumerate(event_lines, 1)
                    if start_line < number and re.search(r'\s' + str(result['device']['chooser_pid'])
                       + r'\s+' + str(result['device']['chooser_pid']) + r'\s+I\s+wm_on_resume_called:', line)
                    and 'dev.partydeck.godot.compare.ComparisonActivity' in line]
                assert len(chooser_resumes) == 1
                for launch in ['launch_2d', 'launch_3d']:
                    nodes = [node for node in ET.parse(runtime / 'last-ui.xml').iter('node')
                             if node.get('resource-id', '').endswith('/' + launch)]
                    assert len(nodes) == 1 and nodes[0].get('enabled') == 'true' and nodes[0].get('clickable') == 'true'
                entry['closeAcknowledgmentFailure'] = {'expectedRoute': 'return_to_chooser', 'observedRoute': final['closeReason'],
                    'closeSignalAcknowledged': False, 'actualLobbyIntentAccepted': True,
                    'sameChooserPidResumeEvents': chooser_resumes,
                    'finalChooserControlsXmlSha256': digest(runtime / 'last-ui.xml'),
                    'dedicatedTeardownReceiptPresent': False, 'freshSceneExitAndNativeBackAttempted': False,
                    'limits': 'The strict close-acknowledgment check failed before the dedicated old-PID/chooser success loop. Actual OS death and final chooser observations do not qualify the missing acknowledgment. Native Back was not exercised in this case.'}
                entry['finalEnginePids'] = failure_observations[-1]['engine_pids']
                entry['failureObservationsSha256'] = digest(directory / 'failure-host-observations.log')
            entries.append(entry)
        assert len({entry['enginePid'] for entry in entries}) == len({entry['presentationId'] for entry in entries}) == len(entries)
        actual_entries = result['mode_results'][0]['entries']
        assert [(entry['name'],entry['enginePid'],entry['presentationId']) for entry in entries] == [
            (entry['name'],entry['engine_pid'],entry['presentation_id']) for entry in actual_entries]
        native_inputs = lines(runtime / 'input-geometry.log')
        for item in native_inputs:
            assert item['package'] == 'dev.partydeck.godot.compare'
            if item['action'] == 'tap':
                left, top, right, bottom = item['bounds']
                x, y = item['coordinates']['x'], item['coordinates']['y']
                assert left <= x <= right and top <= y <= bottom
                left, top, right, bottom = item['viewport']
                assert left <= x <= right and top <= y <= bottom
        cases.append({'artifact': name, 'passed': result['passed'], 'stage': result.get('stage'), 'error': result.get('error'),
            'sourceHashesVerified': True, 'installedPackageHashVerified': True, 'freshAvdPreparationPassed': True,
            'modeResults': result['mode_results'], 'perModeLimitSeconds': result['limits_seconds']['per_mode'],
            'limitsSeconds': result['limits_seconds'],
            'resultSha256': digest(runtime / 'result.json'), 'packageInputsSha256': digest(artifact / 'package-inputs.json'),
            'nativeInputLogSha256': digest(runtime / 'input-geometry.log'), 'nativeInputCount': len(native_inputs),
            'nativeInputActions': dict(Counter(item['action'] for item in native_inputs)),
            'nativeTapCentersWithinReportedTargetAndViewport': True,
            'eventsLogSha256': digest(event_path),
            'cleanupErrors': result.get('cleanup_errors', []), 'entries': entries,
            'originalPngs': [png_record(path) for path in sorted(artifact.rglob('*.png'))]})

summary['androidCases'] = cases
summary['nativeOriginalPngsDecoded'] = sum(len(case['originalPngs']) for case in cases)
assert [case['passed'] for case in cases] == [True, True, False, False]
assert summary['nativeOriginalPngsDecoded'] == 70
summary['directOriginalVisualReview'] = []
summary['directOriginalVisualReviewCount'] = 0
summary['directOriginalVisualReviewStatus'] = 'Pending separate actual original-image inspection; this automated receipt makes no visual-review claim.'
summary['native2dLifecycleQualificationPassed'] = all(case['passed'] for case in cases if '2d-font' in case['artifact'])
summary['native3dLifecycleQualificationPassed'] = all(case['passed'] for case in cases if '3d-font' in case['artifact'])
summary['nativeLifecycleQualificationPassed'] = all(case['passed'] for case in cases)
all_entries = [entry for case in cases for entry in case['entries']]
assert len(all_entries) == 8 and sum(entry['completedRequestedExitRoute'] for entry in all_entries) == 6
driver_error_entries = sum(any('eglCodecCommon' in line['text'] and 'removeVertexArrayObject' in line['text']
                              for line in entry['rawErrorTextMatches']) for entry in all_entries)
shader_warning_pairs = sum(len(entry['knownShaderCacheWarningTextPairs']) for entry in all_entries)
summary['scopeLimits'] = ['API 35 debug Android local-practice comparison only; no optimized runtime, API 36, physical-device, LAN, accessibility, audio dormancy, or store qualification.',
    'Process absence is supported by executed checker receipts, exact checker source, destruction logs, OS am_proc_died events and fresh subsequent process entries; no separate raw shell process-list attachment is present.',
    'Both 3D cases fail the missing closeSignalAcknowledged marker during match return. Neither attempts fresh scene Exit or native Back. Actual process deaths do not qualify the missing acknowledgment; no 3D Back route is qualified by this run.',
    f'{driver_error_entries} of {len(all_entries)} process logs retain an eglCodecCommon removeVertexArrayObject ERROR. The logs retain {shader_warning_pairs} known shader-cache warning pairs at error priority. No clean-driver-log claim is made.',
    'Original image review concerns the named captures only and does not establish continuous video coverage or a general visual-design approval.',
    'Artifact download provenance is retained, but no independent raw ZIP digest audit is claimed.']
output = base / 'native-evidence-automated.json'
with output.open('x') as stream:
    stream.write(json.dumps(summary, indent=2) + '\n')
print(json.dumps({'output': str(output), 'sha256': digest(output), 'pngsDecoded': summary['nativeOriginalPngsDecoded'],
    'directOriginalImagesReviewed': 0, 'cases': [{'artifact': case['artifact'], 'passed': case['passed'],
        'entries': len(case['entries']), 'sceneCapturesVerified': sum(e['verifiedSceneCaptureCount'] for e in case['entries']),
        'originalPngs': len(case['originalPngs'])} for case in cases]}, indent=2))
