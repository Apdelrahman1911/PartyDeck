"""Record completed visual review without changing the earlier source audits."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


notes_path = Path('/tmp/partydeck-gallery-1717-visual-review-notes.json')
notes = read(notes_path)
audits = {}
for platform in ['android', 'ios']:
    record = notes[platform]
    assert sha(record['source_audit_path']) == record['source_audit_sha256']
    audits[platform] = read(record['source_audit_path'])

generated = datetime.now(timezone.utc).isoformat()
common = {key: copy.deepcopy(value) for key, value in notes.items()
          if key not in ['android', 'ios']}
common.update({
    'generated_utc': generated,
    'completed_visual_review': True,
    'notes_source': str(notes_path),
    'notes_sha256': sha(notes_path),
    'review_script_source': str(Path(__file__)),
    'review_script_sha256': sha(__file__),
    'baseline_published_commit_acknowledged_by_root':
        'bbf33f1c33c67fe1b910b821aaa1c0d0dd6bd398',
})


def sheets_with_identity(sheets):
    result = []
    for sheet in sheets:
        item = copy.deepcopy(sheet)
        path = Path(item['path'])
        assert not path.is_relative_to('/root/projects/PartyDeck/docs/screenshots')
        with Image.open(path) as picture:
            item['width_px'], item['height_px'] = picture.size
        item['sha256'] = sha(path)
        item['bytes'] = path.stat().st_size
        item['visually_reviewed'] = True
        result.append(item)
    return result


android = audits['android']
android_review = {**copy.deepcopy(common), **copy.deepcopy(notes['android'])}
android_review['review_sheets'] = sheets_with_identity(notes['android']['review_sheets'])
android_captures = [capture for case in android['android'] for capture in case['captures']]
android_sheet_sources = [source for sheet in android_review['review_sheets']
                         for source in sheet['originals']]
android_expected_sources = [capture['source_original'] for capture in android_captures]
android_expected_sources.extend(record['source_original'] for record in android['excluded'])
assert len(android_sheet_sources) == len(set(android_sheet_sources)) == 80
assert set(android_sheet_sources) == set(android_expected_sources)
assert android_review['sheets_seen'] == list(range(28))
assert len(android_captures) == 76
assert len(android['desktop']['captures']) == 22
assert android['desktop']['originals_matching_previously_reviewed_bytes'] == 22

entries = [entry for case in android['android'] for entry in case['entries']]
assert len(entries) == 12
assert all(case['passed'] for case in android['android'])
assert all(entry['completed_requested_exit_route'] for entry in entries)
assert all(entry['actual_os_process_death_observed'] for entry in entries)
assert all(entry['final_host']['closeSignalAcknowledged'] for entry in entries)
android_review['workflow_conclusion'] = android['workflow_conclusion']
android_review['producer_original_conclusion'] = android['producer_original_conclusion']
android_review['producer_conclusion_scope'] = (
    'The original producer receipt is null. The later final workflow concludes success; '
    'the original receipt is not rewritten to success.')
android_review['source_audit_visual_state_at_creation'] = android['independent_visual_review']
android_review['runtime_summary'] = {
    'passed_cases': sum(case['passed'] for case in android['android']),
    'process_entries': len(entries),
    'completed_requested_exits': sum(entry['completed_requested_exit_route'] for entry in entries),
    'actual_process_deaths': sum(entry['actual_os_process_death_observed'] for entry in entries),
    'native_barriers': sum(entry['close_delivery']['recorded_native_barrier'] for entry in entries),
    'native_main_callbacks': sum('main callback' in entry['close_delivery']['recorded_elapsed_realtime_ms']
                                 for entry in entries),
    'fallbacks': sum(entry['close_delivery']['recorded_fallback'] for entry in entries),
    'source_close_bounds_ms': android['source_close_bounds_ms'],
    'scheduling_cause_established': False,
    'scene_rgb_crops_verified': android['native_scene_rgb_crops_verified'],
    'scene_input_geometries_verified': android['scene_input_geometry_records_verified'],
    'native_input_geometries_verified': android['native_input_geometry_records_verified'],
    'process_logs_with_egl_error': sum(bool(entry['owner_log_classification']['rawErrorTextMatches'])
                                       for entry in entries),
    'shader_cache_warning_pairs_at_error_priority': sum(
        len(entry['owner_log_classification']['knownShaderCacheWarningTextPairs']) for entry in entries),
    'process_logs_with_shader_cache_warning_pairs': sum(
        bool(entry['owner_log_classification']['knownShaderCacheWarningTextPairs']) for entry in entries),
    'unclassified_engine_priority_error_lines': sum(
        len(entry['owner_log_classification']['unclassifiedEnginePriorityErrorLines']) for entry in entries),
}
android_review['cases'] = []
for case in android['android']:
    case_summary = {key: copy.deepcopy(case[key]) for key in ['case', 'mode', 'font_scale', 'passed']}
    case_summary['original_png_count'] = len(case['captures'])
    case_summary['entries'] = []
    for entry in case['entries']:
        item = {key: copy.deepcopy(entry[key]) for key in [
            'name', 'engine_pid', 'presentation_id', 'accepted_intent_counts',
            'completed_requested_exit_route', 'actual_os_process_death_observed',
            'requested_exit_route', 'close_delivery', 'native_back_system_events']}
        item['final_close_reason'] = entry['final_host']['closeReason']
        item['final_close_signal_acknowledged'] = entry['final_host']['closeSignalAcknowledged']
        item['final_authority_revision'] = entry['final_host']['revision']
        item['final_public_state'] = copy.deepcopy(entry['final_host']['publicState'])
        item['log_classification_counts'] = {
            key: len(value) for key, value in entry['owner_log_classification'].items()}
        case_summary['entries'].append(item)
    android_review['cases'].append(case_summary)
android_review['desktop'] = {
    'originals_preserved_as_distinct_source_records': len(android['desktop']['captures']),
    'originals_byte_matched_to_previously_reviewed_files':
        android['desktop']['originals_matching_previously_reviewed_bytes'],
    'new_direct_visual_inspections': 0,
    'authority_trace_sha256': android['desktop']['authority_trace_sha256'],
    'authority_trace_rows': android['desktop']['authority_trace_rows'],
    'source_fingerprint_sha256': android['desktop']['report']['sourceFingerprintSha256'],
    'source_revision': android['source_revision'],
    'working_tree_dirty': android['desktop']['report']['workingTreeDirty'],
    'report_status': android['desktop']['report']['status'],
    'pack_sha256': android['pack_sha256'],
}
android_review['historical_failures_preserved'] = (
    'CI 34456443339 retains both original 3D Close-acknowledgment failures. '
    'The successful later run does not change those records or prove an isolated scheduling cause.')

ios = audits['ios']
ios_review = {**copy.deepcopy(common), **copy.deepcopy(notes['ios'])}
ios_review['review_sheets'] = sheets_with_identity(notes['ios']['review_sheets'])
ios_sheet_sources = [source for sheet in ios_review['review_sheets'] for source in sheet['originals']]
ios_direct_sources = notes['ios']['direct_originals']
assert len(ios_sheet_sources) == len(set(ios_sheet_sources)) == 33
assert len(ios_direct_sources) == len(set(ios_direct_sources)) == 2
assert not set(ios_sheet_sources) & set(ios_direct_sources)
assert set(ios_sheet_sources + ios_direct_sources) == {
    capture['source_original'] for capture in ios['captures']}
assert ios_review['sheets_seen'] == list(range(12))
ios_review['source_audit_visual_state_at_creation'] = ios['other_original_visual_review']
ios_review['direct_originals'] = [
    {key: copy.deepcopy(capture[key]) for key in [
        'source_original', 'sha256', 'bytes', 'width_px', 'height_px',
        'scenario', 'metrics_source', 'test_result']}
    for capture in ios['captures'] if capture['source_original'] in ios_direct_sources]
ios_review['original_test_results_preserved'] = True
ios_review['workflow_conclusion'] = ios['workflow_conclusion']
ios_review['normal_text_v1_proposal_status'] = ios['normal_text_v1_proposal_status']
ios_review['original_attachment_payloads_verified'] = ios['original_xcresult_payloads_independently_verified']
ios_review['original_measurements_verified'] = ios['original_measurements_verified']
ios_review['actual_touch_geometries_verified'] = ios['actual_touch_geometry_verified']
ios_review['observed_controls_verified'] = ios['observed_control_records_verified']
ios_review['screenshot_checkpoints'] = []
for capture in ios['captures']:
    item = {key: copy.deepcopy(capture[key]) for key in [
        'source_original', 'sha256', 'scenario', 'presentation', 'font_scale', 'test_result']}
    measurements = capture.get('metrics')
    if measurements:
        item['metrics_source'] = capture['metrics_source']
        item['pictured_checkpoint'] = {key: measurements.get(key) for key in [
            'revision', 'roundNumber', 'phase', 'acceptedViewerPlays',
            'acceptedViewerChallenges', 'roundsAdvanced', 'reduceMotion', 'soundEnabled']}
        item['scope'] = 'Measurements paired with this original; not substituted for later app-stream progress.'
    ios_review['screenshot_checkpoints'].append(item)
ios_review['cases'] = []
for case in ios['cases']:
    item = {key: copy.deepcopy(case[key]) for key in [
        'name', 'identifier', 'result', 'duration_seconds', 'issues', 'presentation',
        'font_scale', 'measurement_count', 'actual_geometry_count',
        'observed_control_count', 'actual_geometry_by_action']}
    item['original_png_count'] = len(case['captures'])
    item['background_observations'] = copy.deepcopy(case['owner_original_case_audit']['backgroundStates'])
    item['full_reference_test_qualified'] = False
    item['secure_renderer_exit_only_passed'] = case['name'] == 'testSecureTableRendererExit()'
    ios_review['cases'].append(item)
assert sum(case['result'] == 'Failure' for case in ios['cases']) == 4
assert sum(case['result'] == 'Success' for case in ios['cases']) == 1
normal_initial = next(capture for capture in ios['captures']
                      if capture['presentation'] == '2d' and capture['font_scale'] == 1
                      and capture['scenario'].startswith('01 concealed'))
control = next(control for control in normal_initial['metrics']['native']['rendererDiagnostics']['controls']
               if control['group'] == 'partydeck_action_reveal')
rect, clip = control['rect'], control['clipRect']
visible_height = max(0, min(rect[1] + rect[3], clip[1] + clip[3]) - max(rect[1], clip[1]))
assert visible_height == 31 and rect[3] == 56
ios_review['normal_2d_initial_reveal'] = {
    'source_original': normal_initial['source_original'],
    'metrics_source': normal_initial['metrics_source'],
    'control': control,
    'visible_height_logical_points': visible_height,
    'total_height_logical_points': rect[3],
    'clipped_height_logical_points': rect[3] - visible_height,
    'display_scale': normal_initial['metrics']['native']['displayScale'],
    'clipped_height_pixels': (rect[3] - visible_height) * normal_initial['metrics']['native']['displayScale'],
    'scope': 'This run has 31 of 56 points visible; do not transfer the preceding run\'s 7-of-56 geometry.',
}
ios_review['home_state_discrepancy'] = {
    'all_four_reference_cases_visibly_reach_home': True,
    'all_four_original_receipts_report_application_background_false_and_state_4': True,
    'scope': 'Preserve actual Home and dock observations alongside the measured state discrepancy; '
             'do not invent a different application state or substitute the older delayed-Home failure.',
}
for case in ios['cases'][:4]:
    backgrounds = case['owner_original_case_audit']['backgroundStates']
    assert len(backgrounds) == 1
    observation = backgrounds[0]
    assert observation['homeVisible'] and observation['dockIcons']
    assert observation['applicationReportedBackground'] is False
    assert observation['observedApplicationState'] == 4

for platform, review in [('android', android_review), ('ios', ios_review)]:
    path = Path(f'/tmp/partydeck-gallery-1717-{platform}-visual-review.json')
    write_new(path, review)
    print(json.dumps({'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}))
