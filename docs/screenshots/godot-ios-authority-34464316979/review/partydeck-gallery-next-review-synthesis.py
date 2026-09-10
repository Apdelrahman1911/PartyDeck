"""Bind completed visual observations to unchanged originals and raw outcomes."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

TMP = Path('/tmp')
BASELINE_COMMIT = '9a197392ccaa2605e55f9f751c1e3c3f610e623e'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def identity(path):
    path = Path(path)
    return {'source_original': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


generated = datetime.now(timezone.utc).isoformat()
common = {
    'schema_version': 1,
    'completed_visual_review': True,
    'completed_at': generated,
    'reviewer': 'review_design',
    'baseline_published_commit_acknowledged_by_root': BASELINE_COMMIT,
    'new_builds_or_runtime_tests': 0,
    'git_commands_run': 0,
    'review_script': identity(__file__),
}
expected_audits = {
    '34464316979': 'ea39d0871c6f8801cb8c6b7898a39dacc57c31ddb43811c7dc1c598d6efa24e0',
    '34473325295': 'bf0c2cb564faf7fb6e84a5796096cc10517d8eb1bbb0e9190b9f310194e9719b',
    '34478720554': '5ade7dad32d7b23c2a5b6d970fab405c1718f24a6d136ec6aa02a563025d6a76',
}
pairs = [
    ('34473325295', 'retained', 'testStaleFirstReadyAndCloseCompletionReentry()',
     'F3EFD573-7769-4516-B13C-B4DEF6FBDCAF.json', 'ED71EDA6-E3F2-41C9-9DC6-D7C15BBB2961.json',
     15, 'running', True, True, True, 0, 'The rejected wait is still covered; the later capture has removed the cover.'),
    ('34478720554', 'authority', 'testReferenceMatchIn3DAt200Percent()',
     '21E9A419-A371-41D1-9B0C-4164A6A48C72.json', '3AA280F9-FE59-4676-AFF3-AF91665F1E94.json',
     15, 'running', False, True, False, 0, 'The rejected wait has selectedCount 0; the later capture has selectedCount 1.'),
    ('34478720554', 'authority', 'testReferenceMatchIn3D()',
     '9DC14C92-2D62-4F73-812A-4E292DAD8FE2.json', 'CCA006B1-CAED-44C7-8E42-11BF8E8E2920.json',
     15, 'running', False, True, True, 0, 'The rejected wait is concealed; the later capture is revealed and unselected.'),
    ('34478720554', 'retained', 'testActiveAndDormantBackgroundTransitionsStayConcealed()',
     'C976E486-2BBE-4125-81E9-4F722E2BFE91.json', 'C5D9BB0C-018D-4C03-B9FB-3F3E4894ACE3.json',
     60, 'warming', True, None, None, None, 'The rejected second-3D entry is warming and covered without renderer diagnostics; the later capture is running, applied and concealed.'),
    ('34478720554', 'retained', 'testStaleFirstReadyAndCloseCompletionReentry()',
     '2FDCF4F5-7F8B-4E32-8FB6-7A3077417A80.json', '4E008F81-C87B-4112-A3C2-2D30D9648303.json',
     15, 'warming', True, None, None, None, 'The rejected reentry is warming and covered without renderer diagnostics; the later capture is running, applied and concealed.'),
]


def compact_measurements(measurements):
    native = measurements['native']
    diagnostics = native['rendererDiagnostics']
    return {
        'observed_metrics_query_seconds': measurements.get('observedMetricsQuerySeconds'),
        'native_state': native['state'],
        'privacy_cover_visible': native['privacyCoverVisible'],
        'renderer_diagnostics_present': bool(diagnostics),
        'renderer_diagnostics': {key: diagnostics[key] for key in [
            'sceneStateApplied', 'handConcealed', 'privateFaceCount', 'privateLabelCount',
            'selectedCount', 'requestId', 'sequence', 'revision', 'presentationId'] if key in diagnostics},
        'authority_checkpoint': {key: measurements[key] for key in [
            'revision', 'roundNumber', 'phase', 'lifecycle', 'acceptedViewerPlays',
            'acceptedViewerChallenges', 'roundsAdvanced'] if key in measurements},
    }


ios_reviews = []
for run, expected in expected_audits.items():
    audit_path = TMP / f'partydeck-gallery-next-ios-{run}-source-audit.json'
    assert sha(audit_path) == expected
    audit = read(audit_path)
    notes_path = TMP / f'partydeck-gallery-next-ios-{run}-visual-notes.json'
    notes = read(notes_path)
    sheets_path = TMP / f'partydeck-gallery-next-review-sheets/{run}/index.json'
    sheets = read(sheets_path)
    reviewed_sheets = []
    for sheet in sheets:
        path = Path(sheet['path'])
        assert not path.is_relative_to('/root/projects/PartyDeck/docs/screenshots')
        with Image.open(path) as image:
            size = image.size
        reviewed_sheets.append({**copy.deepcopy(sheet), **identity(path),
                                'width_px': size[0], 'height_px': size[1], 'visually_reviewed': True,
                                'published': False, 'purpose': 'internal review sheet; originals are published unchanged'})
    captures = [capture for suite in audit['suites'] for capture in suite['captures']]
    sources = [capture['source_original'] for capture in captures]
    sheet_sources = [source for sheet in sheets for source in sheet['files']]
    assert len(sheet_sources) == len(set(sheet_sources)) == len(captures) == audit['capture_count']
    assert set(sheet_sources) == set(sources)
    review = {**copy.deepcopy(common), 'run': run, 'source_revision': audit['revision'],
              'pack_sha256': audit['pack_sha256'], 'source_audit': identity(audit_path),
              'visual_notes': identity(notes_path), 'review_method': notes['review_method'],
              'review_sheet_index': identity(sheets_path), 'review_sheets': reviewed_sheets,
              'original_png_count': len(captures), 'suites': [], 'rejected_wait_comparisons': [],
              'original_collection_qualification': copy.deepcopy(audit['original_collection_qualification']),
              'original_collection_limitations': copy.deepcopy(audit['original_collection_limitations']),
              'large_original_evidence_retention': 'All original archives and extracted payloads were independently verified. Compact evidence is published; large logs, binaries, videos and internal attachments retain exact source paths and hashes in the audit without unnecessary duplicate gallery copies.'}
    for suite in audit['suites']:
        suite_notes = notes[suite['suite']]
        assert len(suite['cases']) == len(suite_notes)
        case_summaries = []
        by_name = {capture['original_filename']: capture for capture in suite['captures']}
        for case, visual in zip(suite['cases'], suite_notes):
            assert len(case['capture_files']) == len(visual['notes'])
            case_summary = {key: copy.deepcopy(case[key]) for key in [
                'name', 'identifier', 'result', 'duration', 'issues', 'attachmentCount',
                'measurementCount', 'geometryCount', 'observedControlCount', 'geometryByAction',
                'independent_gallery_checks'] if key in case}
            case_summary['summary'] = visual['summary']
            case_summary['original_png_count'] = len(case['capture_files'])
            case_summary['captures'] = []
            for name, note in zip(case['capture_files'], visual['notes']):
                capture = by_name[name]
                assert capture['test_name'] == case['name']
                case_summary['captures'].append({
                    'source_original': capture['source_original'], 'sha256': capture['sha256'],
                    'original_filename': name, 'scenario': capture['scenario'],
                    'notes': [note], 'font_scale': capture['font_scale'],
                    'direct_original_resolution_review': False,
                })
            case_summaries.append(case_summary)
        review['suites'].append({
            'suite': suite['suite'], 'case_results': copy.deepcopy(suite['case_results']),
            'passed_cases': sum(case['result'] == 'Success' for case in suite['cases']),
            'cases': case_summaries, 'original_png_count': len(suite['captures']),
            'original_payloads_independently_verified': suite['original_payloads_independently_verified'],
            'original_issue_text_exports_independently_verified': suite.get('original_issue_text_exports_independently_verified', 0),
            'retained_qualification': copy.deepcopy(suite['retained_qualification']),
            'touch_scope': 'Actual geometry attachments are counted separately from observed-control eligibility. Retained touch candidates are never counted as delivered taps.',
            'font_scale_scope': 'Authority font scales come from recorded measurements/test identity. Retained capture font_scale remains null where not separately recorded.',
        })
    evidence_by_name = {Path(record['source_original']).name: record for record in audit['evidence_files']}
    for pair in pairs:
        pair_run, suite_name, test_name, rejected_name, later_name, timeout, state, cover, applied, concealed, selected, observation = pair
        if pair_run != run:
            continue
        rejected = evidence_by_name[rejected_name]
        later = evidence_by_name[later_name]
        assert sha(rejected['source_original']) == rejected['sha256']
        assert sha(later['source_original']) == later['sha256']
        raw = read(rejected['source_original'])
        late_raw = read(later['source_original'])
        before = compact_measurements(raw['measurements'])
        after = compact_measurements(late_raw)
        assert raw['timeoutSeconds'] == timeout
        assert before['native_state'] == state and before['privacy_cover_visible'] is cover
        assert before['renderer_diagnostics'].get('sceneStateApplied') is applied
        assert before['renderer_diagnostics'].get('handConcealed') is concealed
        assert before['renderer_diagnostics'].get('selectedCount') == selected
        associated = [capture for capture in captures if capture.get('metrics_source') == later['source_original']]
        assert len(associated) == 1 and associated[0]['test_name'] == test_name
        review['rejected_wait_comparisons'].append({
            'suite': suite_name, 'test_name': test_name,
            'rejected_original': identity(rejected['source_original']),
            'timeout_seconds': raw['timeoutSeconds'], 'elapsed_seconds': raw['elapsedSeconds'],
            'last_rejected_measurements': before,
            'later_measurements_original': identity(later['source_original']),
            'later_measurements': after,
            'later_png_original': identity(associated[0]['source_original']),
            'observation': observation,
            'qualification': 'The later capture does not satisfy the original deadline. Query duration does not isolate native frame, texture or scheduling cost; an old-handle probe is not qualified.',
        })
    if run == '34473325295':
        review['dormant_home_failure'] = {
            'checkpoint': 'immediate applicationActive assertion after dormant Home/activate',
            'exact_returned_dictionary_attached': False,
            'last_png_is_actual_home': True,
            'scope': 'Do not substitute an earlier endpoint dictionary for the unrecorded returned dictionary at this assertion.',
        }
    if run == '34478720554':
        review['launch_failure'] = {'original_png_count': 0, 'measurement_count': 0,
                                    'issue_text_export_has_attachment_payload': False,
                                    'issue_text_export_has_timestamp': False,
                                    'later_video_is_supplemental': True}
        review['demand_redraw_source_scope'] = 'This archived pack includes the demand-redraw change. The preceding 34473325295 pack does not. The optional mouse-interception patch is absent from both; the differing test outcomes do not establish an isolated performance or stall fix.'
    path = TMP / f'partydeck-gallery-next-ios-{run}-visual-review.json'
    write_new(path, review)
    ios_reviews.append(identity(path))

demand_path = TMP / 'partydeck-gallery-next-demand-source-audit.json'
assert sha(demand_path) == 'aa2966e7b78fce0342ee3d71619d91fc0baaa2990aa307fd75e9ca4f41b4f64d'
demand = read(demand_path)
demand_notes_path = TMP / 'partydeck-gallery-next-demand-visual-notes.json'
demand_notes = read(demand_notes_path)
demand_sheets_path = TMP / 'partydeck-gallery-next-review-sheets/demand-redraw/index.json'
demand_sheets = read(demand_sheets_path)
demand_sheet_sources = [source for sheet in demand_sheets for source in sheet['files']]
assert len(demand_sheet_sources) == 13 and set(demand_sheet_sources) == {c['source_original'] for c in demand['captures']}
demand_review = {**copy.deepcopy(common), 'source_audit': identity(demand_path),
                 'visual_notes': identity(demand_notes_path), 'original_png_count': 13,
                 'summary': demand_notes['summary'], 'review_method': demand_notes['review_method'],
                 'review_sheet_index': identity(demand_sheets_path),
                 'review_sheets': [{**sheet, **identity(sheet['path']), 'visually_reviewed': True, 'published': False} for sheet in demand_sheets],
                 'captures': [], 'preserved_failures': copy.deepcopy(demand['preserved_failures']),
                 'limits': copy.deepcopy(demand['limits'])}
for name in ['3d-scene-portrait', '3d-scene-large-text']:
    captures = [c for c in demand['captures'] if Path(c['relative_path']).parts[0] == name]
    assert len(captures) == len(demand_notes[name])
    for capture, note in zip(captures, demand_notes[name]):
        demand_review['captures'].append({'source_original': capture['source_original'], 'sha256': capture['sha256'], 'notes': [note]})
write_new(TMP / 'partydeck-gallery-next-demand-visual-review.json', demand_review)

winner = read(TMP / 'partydeck-gallery-next-winner-source-audit.json')
winner_notes = [
    'The complete named winner wraps across two lines beneath the emblem. Round 20, Back to room and See the final reveal all fit without clipping.',
    'At 200% text the named winner wraps across three complete lines. Round 20 and the full Back to room control fit; See the final reveal wraps clearly across two lines. The header title also wraps without obscuring its controls.',
    'The short landscape layout keeps the emblem at left and the full single-line named winner at right. Round 20, Back to room and See the final reveal all fit.',
    'The centered tablet layout shows the complete single-line named winner, emblem, Round 20 and both actions with ample spacing and no visible clipping.',
]
winner_review = {**copy.deepcopy(common), 'source_audit': identity(TMP / 'partydeck-gallery-next-winner-source-audit.json'),
                 'original_png_count': 4, 'review_method': 'All four original PNG files viewed directly at original resolution.',
                 'summary': 'The named winner and both actions fit in phone, 200% text, short landscape and tablet fixtures. The recorded stable polite winner semantics remain JVM-only evidence.',
                 'captures': [{**identity(c['source_original']), 'notes': [note], 'direct_original_resolution_review': True} for c, note in zip(winner['captures'], winner_notes)],
                 'limits': copy.deepcopy(winner['limits'])}
write_new(TMP / 'partydeck-gallery-next-winner-visual-review.json', winner_review)

video = read(TMP / 'partydeck-gallery-next-video-source-audit.json')
video_observations = [
    'Actual iOS Home is visible with clock 12:59, the runner icon and Safari/Messages dock. No game view is visible.',
    'Actual iOS Home remains visible with clock 1:00, the runner icon and Safari/Messages dock.',
    'Actual iOS Home now includes a separate LastLightComp... icon at the right. This frame still contains no game view.',
    'A blank white rounded app window expands over the blurred Home screen. No chooser or gameplay content is visible.',
    'The app area is blank white beneath the status bar. No chooser, hand or gameplay control is visible.',
    'The app area remains blank white. This is the last blank sample immediately before the retained 3.501667-second sample gap.',
    'The chooser is faint during the fade: Last Light, Choose your table, both entry actions, Sound and Idle can be seen. This later chooser is separate from the failed launch assertion.',
    'The full chooser is readable with Play in 2D, Play in 3D, Sound, Repeatable comparison scenario and Idle. No renderer scene or delivered gameplay input is shown.',
    'The final retained sample remains a full Idle chooser with both entry actions. It does not establish native scene entry or a 200% renderer appearance.',
]
video_review = {**copy.deepcopy(common), 'source_audit': identity(TMP / 'partydeck-gallery-next-video-source-audit.json'),
                'original_ci_png_count': 0, 'derived_frame_count': 9,
                'review_method': 'All nine selected decoded PNG files independently viewed directly through the image tool. Their unchanged source dimensions are 1206 by 2622; the display tool may resize its preview.',
                'frames': [{**identity(frame['source_original']), 'pts_time': frame['original_video_frame']['pts_time'], 'notes': [note]} for frame, note in zip(video['frames'], video_observations)],
                'limits': copy.deepcopy(video['limits']),
                'absolute_pts_origin_resolved': False}
write_new(TMP / 'partydeck-gallery-next-video-visual-review.json', video_review)
write_new(TMP / 'partydeck-gallery-next-review-synthesis-receipt.json', {
    **common, 'ios_reviews': ios_reviews,
    'new_original_pngs': 196, 'supplemental_decoded_frames': 9,
    'reviewed_internal_sheets': 60, 'direct_original_views': 4, 'direct_supplemental_views': 9,
    'all_original_pngs_individually_covered_by_notes': True,
})
print(json.dumps({'new_original_pngs': 196, 'supplemental_decoded_frames': 9,
                  'raw_rejected_and_later_pairs': len(pairs)}, indent=2))
