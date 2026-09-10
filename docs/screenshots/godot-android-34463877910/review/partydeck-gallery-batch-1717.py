"""Archive 133 verified originals and their evidence after the 1,584-image push."""
import copy
import hashlib
import html
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

REPO = Path('/root/projects/PartyDeck')
GALLERY = REPO / 'docs/screenshots'
DESIGN = REPO / 'godot/reviews/design-review.md'
STAGE = Path('/tmp/partydeck-gallery-1717-staged')
BASELINE_PATH = Path('/tmp/partydeck-gallery-before-1717.json')
BASELINE_FILES_PATH = Path('/tmp/partydeck-gallery-1717-baseline-files.json')
BASELINE_INDEX_PATH = Path('/tmp/partydeck-gallery-before-1717-README.md')
BASELINE_DESIGN_PATH = Path('/tmp/partydeck-gallery-before-1717-design-review.md')
BASELINE_COMMIT = 'bbf33f1c33c67fe1b910b821aaa1c0d0dd6bd398'
ANDROID_ROOT = 'godot-android-34463877910'
DESKTOP_ROOT = 'godot-desktop-34463877910'
IOS_ROOT = 'godot-ios-authority-34460468965'
NEW_ROOTS = [ANDROID_ROOT, DESKTOP_ROOT, IOS_ROOT]
ANDROID_REV = 'bbfde024d95f5e4d62a26b57495a6a90447d6033'
IOS_REV = '31d148f9b6bbfa15d1746e1029858b86714362a3'
ANDROID_AUDIT_PATH = Path('/tmp/partydeck-gallery-1717-android-source-audit.json')
IOS_AUDIT_PATH = Path('/tmp/partydeck-gallery-1717-ios-source-audit.json')
ANDROID_REVIEW_PATH = Path('/tmp/partydeck-gallery-1717-android-visual-review.json')
IOS_REVIEW_PATH = Path('/tmp/partydeck-gallery-1717-ios-visual-review.json')
PROTECTED_MARKER = b'## Visual direction and asset reuse'
BT = chr(96)
TABLE = '| Original image | Scenario and provenance |\n| --- | --- |\n'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def unchanged_baseline():
    for record in baseline_files:
        path = REPO / record['path']
        assert path.is_file(), record['path']
        assert path.stat().st_size == record['bytes'], record['path']
        assert sha(path) == record['sha256'], record['path']
    assert (GALLERY / 'manifest.json').read_bytes() == BASELINE_PATH.read_bytes()
    assert (GALLERY / 'README.md').read_bytes() == BASELINE_INDEX_PATH.read_bytes()
    assert DESIGN.read_bytes() == BASELINE_DESIGN_PATH.read_bytes()
    assert not any((GALLERY / root).exists() for root in NEW_ROOTS)


def preserve(source, relative):
    source = Path(source)
    target = STAGE / relative
    assert not target.exists(), relative
    assert '..' not in Path(relative).parts and not Path(relative).is_absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    assert sha(target) == sha(source), relative
    return target


def evidence(record, root, **extra):
    source = Path(record['source_original'])
    assert source.stat().st_size == record['bytes']
    assert sha(source) == record['sha256']
    relative = root + '/' + record['relative_path']
    target = preserve(source, relative)
    result = {
        'path': relative, 'original_filename': source.name,
        'source_original': record['source_original'], 'sha256': record['sha256'],
        'bytes': target.stat().st_size, 'collection': root,
        **{key: copy.deepcopy(value) for key, value in record.items()
           if key not in ['relative_path', 'source_original', 'sha256', 'bytes']},
        **extra,
    }
    assert result['original_filename'] == source.name == target.name
    manifest['evidence'].append(result)
    source_key = str(source.resolve())
    assert source_key not in evidence_source_paths, source_key
    evidence_source_paths[source_key] = relative
    return result


def review_evidence(source, root):
    source = Path(source)
    return evidence({
        'source_original': str(source), 'sha256': sha(source),
        'bytes': source.stat().st_size, 'relative_path': 'review/' + source.name,
    }, root, artifact_type='later_independent_gallery_review')


def evidence_path(source):
    return evidence_source_paths[str(Path(source).resolve())]


def screenshot(capture, root, scenario, platform, kind, scale, notes, **extra):
    relative = root + '/' + capture['relative_path']
    source = Path(capture['source_original'])
    assert sha(source) == capture['sha256']
    assert source.stat().st_size == capture['bytes']
    target = preserve(source, relative)
    with Image.open(target) as picture:
        picture.load()
        assert picture.format == 'PNG'
        width, height = picture.size
    assert (width, height) == (capture['width_px'], capture['height_px'])
    assert source.name == target.name
    record = {
        'id': relative.removesuffix('.png'), 'collection': root, 'path': relative,
        'original_filename': source.name, 'scenario': scenario, 'platform': platform,
        'artifact_type': kind, 'width_px': width, 'height_px': height, 'font_scale': scale,
        'bytes': capture['bytes'], 'sha256': capture['sha256'],
        'source_original': capture['source_original'],
        'source_aliases': copy.deepcopy(capture.get('source_aliases', [])),
        'source_revision': capture['source_revision'],
        'source_revision_exact': capture['source_revision_exact'], 'ci_run': capture['ci_run'],
        'synthetic_invitation_fixture': False, 'notes': notes, **extra,
    }
    manifest['screenshots'].append(record)
    return record


def row(record, root):
    relative = os.path.relpath(record['path'], root)
    caption = html.escape(record['scenario']).replace('|', '&#124;')
    details = [
        '**' + caption + '**', html.escape(record['platform']),
        f"Original: [{record['original_filename']}]({relative})",
        f"{record['width_px']} × {record['height_px']} px; text {record['font_scale']:g}×",
        f"SHA-256: <code>{record['sha256']}</code>",
    ]
    for key, label in [
        ('receipt_path', 'Original receipt'), ('ui_dump_path', 'Original UI dump'),
        ('metrics_path', 'Original measurements'), ('result_path', 'Original result'),
        ('background_observation_path', 'Original Home observation'),
    ]:
        if key in record:
            details.append(f"[{label}]({os.path.relpath(record[key], root)})")
    details.extend(html.escape(note).replace('|', '&#124;') for note in record['notes'])
    return (
        f'| <a href="{relative}"><img src="{relative}" alt="{caption}" width="168"></a> | '
        + '<br>'.join(details) + ' |'
    )


def markdown(root, content):
    path = STAGE / root / 'README.md'
    assert not path.exists()
    path.write_text(content.rstrip() + '\n')


def native_notes(case, capture):
    mode, scale = case['mode'], case['font_scale']
    name = Path(capture['source_original']).name
    entry = Path(capture['source_original']).parent.name
    result = []
    if name in ['01-concealed.png', '01-fresh-concealed.png']:
        if mode == '2d':
            result.append('The complete Reveal action and concealed-panel borders are visible.')
            if scale == 2:
                result.append('Lower actions continue below this initial viewport.')
        else:
            result.append('Private faces, rank labels and selection are concealed; Show hand is complete.')
            if scale == 2:
                result.append('Turn, rank and round remain pinned; the lower table/hand continues below the viewport.')
    if name in ['02-revealed.png', '03-selected.png']:
        if mode == '2d':
            result.append('The hand scrolls horizontally; this frame does not show every card in full.')
            if scale == 2:
                result.append('Two enlarged cards fit with a clipped third; Play and Challenge are below the hand-focused viewport.')
            else:
                result.append('Three full cards and a clipped next card are visible; the large Star heading clips after scrolling while the turn/claim context stays visible.')
        elif scale == 2:
            result.append('Pinned Show/Hide and turn/rank/round context remain visible. Enlarged card controls scroll; lower controls and Play are not all visible together.')
        else:
            result.append('All five normal-size cards and rank words fit. The seat roster scrolls horizontally.')
        if name == '03-selected.png':
            result.append('Moon is visibly selected with a check/outline or explicit Selected · Moon control.')
    if name in ['04-covered.png', '07-resumed-concealed.png']:
        result.append('Private faces, per-card rank labels and selection are absent after concealment.')
        if name == '07-resumed-concealed.png':
            result.append('Original process and presentation receipts establish the exercised same-process concealed resume.')
    if name == '05-background-home.png':
        result.append('Actual Android Home during the privacy exercise; distinct from the excluded pre-install Launcher image.')
    if name == '06-recents-privacy.png':
        result.append('The actual Recents preview is opaque and contains no private game content.')
    if name in ['08-after-play.png', '09-public-outcome.png', '10-next-round.png', '11-after-challenge.png']:
        if name in ['08-after-play.png', '09-public-outcome.png']:
            result.append('Round-1 public result: Moxie challenges Ari’s Star claim, public Moon does not match, and Ari tests light 1 and stays in.')
        elif name == '10-next-round.png':
            result.append('This capture is already the round-2 public result, with Pip challenging Moxie’s Crown claim.')
        else:
            result.append('This capture is the round-4 public result, with Ari challenging Orbit’s Crown claim.')
        if scale == 2 and mode == '2d':
            result.append('Only the upper explanation fits. The rest of the consequence and Next action continue below this screenshot; later accepted input is separate evidence.')
        elif scale == 2:
            result.append('The named consequence and public mismatch text fit; Next is clipped or below this viewport. Later accepted input establishes reachability.')
        else:
            result.append('The complete named consequence and Next action are visible.')
    if name == '12-winner.png':
        result.append('Orbit wins at round 14/revision 41 after the public Moon disproves Moxie’s Crown claim and Moxie burns out on light 4.')
        if scale == 2 and mode == '2d':
            result.append('The final consequence and Return to lobby continue below this viewport; the accepted return is retained in the input and teardown receipts.')
        elif scale == 2:
            result.append('The named final consequence fits in text. The table and Back to room action continue below this viewport.')
        elif mode == '3d':
            result.append('The correct Crown emblem, complete named consequence and Back to room action are visible.')
        else:
            result.append('The complete named consequence and Return to lobby action are visible.')
    if name == '14-chooser-after-exit.png':
        route = {'match': 'accepted match return', 'scene-exit': 'fresh renderer Exit',
                 'native-exit': 'fresh native Close' if mode == '2d' else 'fresh native Back'}[entry]
        result.append(f'The {route} restores the chooser with both presentation actions; the original teardown records acknowledgment and actual child-process death.')
    if name in ['chooser.png', 'final-screen.png']:
        result.append('The chooser shows both presentation actions. This distinct original keeps its own source and hash even when pixels match another chooser.')
    return result


def native_scenario(case, capture):
    mode, scale = case['mode'].upper(), case['font_scale']
    path = Path(capture['source_original'])
    descriptions = {
        '01-concealed.png': 'reference match begins concealed',
        '02-revealed.png': 'own hand revealed',
        '03-selected.png': 'Moon selected for a Star claim',
        '04-covered.png': 'private hand covered and selection cleared',
        '05-background-home.png': 'actual Home during privacy exercise',
        '06-recents-privacy.png': 'opaque Recents preview',
        '07-resumed-concealed.png': 'same-process resume with concealed hand',
        '08-after-play.png': 'public result after actual viewer play',
        '09-public-outcome.png': 'round-1 public outcome',
        '10-next-round.png': 'round-2 public result after Next',
        '11-after-challenge.png': 'round-4 public result after actual challenge',
        '12-winner.png': 'Orbit wins at round 14',
        'chooser.png': 'initial native chooser',
        'final-screen.png': 'final native chooser diagnostic',
    }
    if path.name == '01-fresh-concealed.png':
        route = 'scene Exit' if path.parent.name == 'scene-exit' else (
            'native Close' if case['mode'] == '2d' else 'native Back')
        description = 'fresh concealed entry before ' + route
    elif path.name == '14-chooser-after-exit.png':
        route = {'match': 'match return', 'scene-exit': 'fresh scene Exit',
                 'native-exit': 'fresh native Close' if case['mode'] == '2d' else 'fresh native Back'}[path.parent.name]
        description = 'chooser restored after ' + route
    else:
        description = descriptions[path.name]
    return f'Native {mode} {description} — {scale:g}× text'


def ios_notes(case, capture):
    scenario, mode, scale = capture['scenario'], capture['presentation'], capture['font_scale']
    result = []
    if case['result'] == 'Failure':
        result.append('Original reference test: Failure. ' + '; '.join(
            issue['compactDescription'] for issue in case['issues']))
    else:
        result.append('Original secure default renderer Exit test: Success; no full secure match or retained-engine lifecycle is qualified.')
    if scenario.startswith('01 concealed'):
        if mode == '2d' and scale == 1:
            result.append('Initial Reveal clips: 31 of 56 logical points are visible; 25 points/75 pixels are below the clip. Later scrolled Reveal frames fit.')
        elif mode == '2d':
            result.append('Reveal is complete; the lower Choose cards action clips.')
        else:
            result.append('Show hand and turn/rank/round context are complete. The seat roster scrolls; at enlarged text the lower table continues below the viewport.')
    elif scenario.startswith('02 revealed'):
        if mode == '2d':
            result.append('Moon is selected with a check/outline. The hand scrolls horizontally and does not show every card together.')
        elif scale == 2:
            result.append('Selected · Moon, two Crown controls and one Star fit; the fifth control is below. Visual table cards clip at the upper scroll edge.')
        else:
            result.append('All five normal-size card faces/rank words and Play 1 fit; Moon has a check/outline.')
    elif scenario.startswith('03 private') or scenario.startswith('Same authority resumed'):
        result.append('Only concealed cards remain; private faces, per-card rank labels and selection are absent. Reveal/Show hand is complete.')
    elif scenario.startswith('Native cover'):
        result.append('Native Pause presents an opaque cover with no private game content.')
    elif scenario.startswith('Actual Home'):
        result.append('SpringBoard and dock icons are visibly present. The original observation still reports applicationReportedBackground=false and application state 4; both observations are preserved.')
    elif scenario.startswith('04 actual') or scenario.startswith('05 public'):
        result.append('Paired screenshot checkpoint: round 1/revision 2, one accepted viewer play. Moxie challenges Ari’s Star claim and public Moon does not match.')
        if scale == 1:
            result.append('The complete light-1 Still in consequence and Next action fit.')
        elif mode == '2d':
            result.append('The remaining consequence and Next action continue below this viewport.')
        else:
            result.append('The complete named consequence fits, while the public card/table clips and Next is below the viewport.')
        if mode == '3d':
            result.append('Later Next touches and app-stream progress are separate evidence; this earlier screenshot checkpoint is not the final test state.')
    elif scenario.startswith('07 real winner'):
        result.append('Orbit wins at round 14; paired authority revision is 42. The complete named Crown-claim challenge, Moon mismatch, Moxie’s light-4 burnout and Return to lobby fit. The failed 42-versus-41 assertion is retained.')
    elif scenario == 'Failed authority wait':
        result.append('Viewed directly at original resolution. Five cards are covered; Reveal and Call the bluff are complete and Choose cards is disabled. YOUR HAND clips at the upper scroll edge.')
        result.append('Paired failure measurement: round 4/revision 10, one accepted play and three advances. Visible controls do not override the bounded-diagnostics failure.')
    elif scenario.startswith('Secure default'):
        result.append('Viewed directly at original resolution. Table closed, the relaunch instruction, Host +1 and Closed status appear; the Godot surface is absent.')
    return result


baseline_files = read(BASELINE_FILES_PATH)
baseline = read(BASELINE_PATH)
assert len(baseline_files) == 6019
assert len(baseline['screenshots']) == 1584 and len(baseline['evidence']) == 4349
assert sha(BASELINE_PATH) == 'd05d4812d9c558a9a28936a9289ea59668b3a9c9b340d75d43986176699dc49d'
assert not STAGE.exists()
unchanged_baseline()
android = read(ANDROID_AUDIT_PATH)
ios = read(IOS_AUDIT_PATH)
android_review = read(ANDROID_REVIEW_PATH)
ios_review = read(IOS_REVIEW_PATH)
assert sha(ANDROID_AUDIT_PATH) == 'd753bd079ea26a946b16cddb55c15bdb342e86af2d8b4e068e5e1053727c6a70'
assert sha(IOS_AUDIT_PATH) == '0b383752857b1abbb08c847818e8ceebc23a92f7f939915fe1ed2086c8f9a86b'
assert sha(ANDROID_REVIEW_PATH) == '37c5e9f1eb2575ca7fa5d8ed44d4f2a27434e663f8520343f7954e4b70773423'
assert sha(IOS_REVIEW_PATH) == '87da198cc69bd2ecf0ea090c5f86cf374d85250baad4161a2e8d97bfb7d274eb'
assert android_review['completed_visual_review'] and ios_review['completed_visual_review']
STAGE.mkdir()
manifest = copy.deepcopy(baseline)
evidence_source_paths = {}
new_evidence_groups = [
    (ANDROID_ROOT, android['native_evidence'] + android['metadata'] + android['source_files']),
    (DESKTOP_ROOT, android['desktop']['evidence']),
    (IOS_ROOT, ios['attachment_evidence'] + ios['metadata_and_runtime_evidence']
     + ios['source_files'] + ios['normal_text_review_supplement']),
]
assert sum(len(records) for _, records in new_evidence_groups) == 1017
for root, records in new_evidence_groups:
    for record in records:
        evidence(record, root)
for path in [
    ANDROID_AUDIT_PATH, Path('/tmp/partydeck-gallery-1717-audit-android.py'),
    ANDROID_REVIEW_PATH, Path('/tmp/partydeck-gallery-1717-review-synthesis.py'),
    Path('/tmp/partydeck-gallery-1717-visual-review-notes.json'), Path(__file__),
    Path('/tmp/partydeck-gallery-1717-validate.py'),
]:
    review_evidence(path, ANDROID_ROOT)
for path in [IOS_AUDIT_PATH, Path('/tmp/partydeck-gallery-1717-audit-ios.py'), IOS_REVIEW_PATH]:
    review_evidence(path, IOS_ROOT)

android_records = []
for case in android['android']:
    pairs = {str(Path(pair['path']).resolve()): pair for pair in case['scene_pairs']}
    entries = {entry['name']: entry for entry in case['entries']}
    for capture in case['captures']:
        source = Path(capture['source_original'])
        entry = entries.get(source.parent.name)
        extra = {
            'case': case['case'], 'presentation_requested': case['mode'],
            'result_path': ANDROID_ROOT + '/' + case['case'] + '/result.json',
            'native_case_script_passed': case['passed'], 'full_matrix_qualified': False,
            'kmp_factory_qualified': False, 'display_density_dpi': 280,
            'display_density': 1.75, 'reference_scenario': True, 'seed': 2,
            'reduce_motion': True, 'sound_enabled': False,
            'apk_sha256': case['result']['apk_sha256'],
            'renderer_artifact_sha256': android['pack_sha256'],
            'case_process_entries': len(case['entries']),
            'case_completed_requested_exit_routes': sum(
                item['completed_requested_exit_route'] for item in case['entries']),
            'case_accepted_gameplay_intent_counts': {
                key: case['entries'][0]['accepted_intent_counts'][key]
                for key in ['play', 'challenge', 'advance_round']},
        }
        xml_source = source.with_suffix('.xml')
        if str(xml_source.resolve()) in evidence_source_paths:
            extra['ui_dump_path'] = evidence_path(xml_source)
        pair = pairs.get(str(source.resolve()))
        if pair:
            extra.update({
                'metrics_path': evidence_path(pair['host_source']),
                'engine_rgb_sha256': pair['engine_rgb_sha256'],
                'engine_surface': pair['surface'], 'authority_revision': pair['revision'],
                'presentation_id': pair['presentationId'],
                'privacy_diagnostics': pair['privacy_diagnostics'], 'public_state': pair['public_state'],
            })
        if entry:
            extra.update({
                'entry': entry['name'], 'engine_pid': entry['engine_pid'],
                'entry_completed_requested_exit_route': entry['completed_requested_exit_route'],
                'entry_actual_os_process_death_observed': entry['actual_os_process_death_observed'],
                'entry_accepted_intent_counts': entry['accepted_intent_counts'],
                'entry_final_close_reason': entry['final_host']['closeReason'],
                'entry_final_close_signal_acknowledged': entry['final_host']['closeSignalAcknowledged'],
                'entry_close_delivery': entry['close_delivery'],
                'teardown_path': ANDROID_ROOT + '/' + case['case'] + '/'
                    + case['mode'] + '/' + entry['name'] + '/teardown.json',
            })
        android_records.append(screenshot(
            capture, ANDROID_ROOT, native_scenario(case, capture),
            f"Android API 35 emulator, actual native {case['mode'].upper()} comparison host, debug APK",
            'native_emulator_capture', case['font_scale'], native_notes(case, capture), **extra))

desktop_records = []
old_by_path = {record['path']: record for record in baseline['screenshots']}
desktop_report = android['desktop']['report']
for capture in android['desktop']['captures']:
    prior_path = 'godot-desktop-34456443339/' + capture['relative_path']
    prior = old_by_path[prior_path]
    assert prior['sha256'] == capture['sha256']
    assert prior_path in capture['prior_byte_identical_originals']
    receipt = capture['receipt']
    diagnostics = receipt['diagnostics']
    desktop_records.append(screenshot(
        capture, DESKTOP_ROOT, prior['scenario'],
        'Godot 4.7.2 desktop, packed renderer, real Kotlin authority, X11/Xvfb',
        'authority_gameplay_capture', 1.0, copy.deepcopy(prior['notes']),
        working_tree_dirty=False, source_fingerprint_sha256=desktop_report['sourceFingerprintSha256'],
        receipt_path=evidence_path(capture['receipt_source']),
        authority_revision=receipt['authorityRevision'], authority_view_sha256=receipt['authorityViewSha256'],
        seed=receipt['seed'], reduce_motion=receipt['reduceMotion'], presentation=capture['presentation'],
        renderer_artifact_sha256=android['pack_sha256'],
        privacy_diagnostics={key: diagnostics.get(key) for key in [
            'handConcealed', 'privateFaceCount', 'privateLabelCount', 'selectedCount']},
        visually_reviewed_identical_original=prior_path,
        prior_byte_identical_originals=copy.deepcopy(capture['prior_byte_identical_originals'])))

ios_records = []
ios_case_by_name = {case['name']: case for case in ios['cases']}
for capture in ios['captures']:
    case = ios_case_by_name[capture['test_name']]
    extra = {
        'captured_utc': datetime.fromtimestamp(capture['timestamp'], timezone.utc).isoformat(),
        'attachment': copy.deepcopy(capture['attachment']),
        'suggested_human_readable_name': capture['suggested_human_readable_name'],
        'test_name': capture['test_name'], 'test_identifier': capture['test_identifier'],
        'test_result': capture['test_result'], 'presentation': capture['presentation'],
        'display_scale': 3, 'executable_sha256': ios['executable_sha256'],
        'renderer_artifact_sha256': ios['pack_sha256'],
        'xcresult_original_object': capture['xcresult_original_object'],
        'xcresult_original_object_sha256': capture['xcresult_original_object_sha256'],
        'xcresult_payload_ref': capture['xcresult_payload_ref'],
        'xcresult_payload_sha256': capture['xcresult_payload_sha256'],
        'original_xcresult_payload_independently_verified': True,
        'full_reference_match_qualified': False, 'full_native_matrix_qualified': False,
        'kmp_factory_qualified': False,
        'case_actual_touch_counts': copy.deepcopy(case['actual_geometry_by_action']),
        'case_original_issues': copy.deepcopy(case['issues']),
        'later_normal_text_v1_proposal_status': ios['normal_text_v1_proposal_status'],
        'direct_original_resolution_review': capture['source_original'] in [
            record['source_original'] for record in ios_review['direct_originals']],
    }
    metrics = capture.get('metrics')
    if metrics:
        extra.update({
            'metrics_path': evidence_path(capture['metrics_source']),
            'metrics_timestamp': capture['metrics_timestamp'],
            'authority_revision': metrics['revision'], 'round_number': metrics['roundNumber'],
            'phase': metrics['phase'], 'native_state': metrics['native']['state'],
            'reference_seed_2': metrics['referenceSeed2'], 'reduce_motion': metrics['reduceMotion'],
            'sound_enabled': metrics['soundEnabled'],
            'accepted_gameplay_intent_counts_at_screenshot': {
                'play': metrics['acceptedViewerPlays'], 'challenge': metrics['acceptedViewerChallenges'],
                'advance_round': metrics['roundsAdvanced']},
            'measurements_scope': 'Original paired screenshot checkpoint; later app-stream progress remains separate.',
            'metrics_summary': {key: metrics.get(key) for key in [
                'authorityReleased', 'foreground', 'hostCounter', 'lifecycle', 'lastOutcome',
                'lastReasonCode', 'winnerId', 'observedApplicationState', 'closeReason']},
            'privacy_diagnostics': {key: metrics['native'].get('rendererDiagnostics', {}).get(key)
                                    for key in ['handConcealed', 'privateFaceCount', 'privateLabelCount', 'selectedCount']},
        })
    elif capture['scenario'].startswith('Actual Home'):
        observation = case['owner_original_case_audit']['backgroundStates'][0]
        extra['background_observation_path'] = evidence_path(observation['file'])
        extra['background_observation'] = copy.deepcopy(observation)
    ios_records.append(screenshot(
        capture, IOS_ROOT, capture['scenario'],
        'iPhone 17 simulator, actual native Last Light authority host',
        'native_simulator_capture', capture['font_scale'], ios_notes(case, capture), **extra))

assert len(android_records) == 76 and len(desktop_records) == 22 and len(ios_records) == 35
for record in android['excluded']:
    exclusion = copy.deepcopy(record)
    exclusion.setdefault('original_filename', Path(record['source_original']).name)
    exclusion['visual_classification'] = 'Pre-install Launcher viewed in an internal review sheet; excluded infrastructure image.'
    manifest['excluded_source_images'].append(exclusion)

android_collection = {
    'id': ANDROID_ROOT, 'path': ANDROID_ROOT,
    'title': 'Godot Android — all four comparison cases and twelve exits pass, CI 34463877910',
    'platform': 'Android API 35 x86_64 emulator, native debug host, 720 × 1600 at 280 dpi, 100%/200% text',
    'kind': 'native_partial_qualification_capture', 'tier': 'native_current',
    'revision': ANDROID_REV, 'source_revision_exact': True, 'ci_run': android['ci_run'],
    'source_directory': '/tmp/partydeck-engine-ci/34463877910', 'count': len(android_records),
    'status': 'All four complete scripts pass: full match, Home/Recents/concealed resume, match return, fresh scene Exit and fresh native Close/Back.',
    'text': 'Twelve acknowledged exits and actual process deaths; twelve native barriers/main callbacks and zero fallbacks. Large-text viewport clipping remains.',
    'workflow_conclusion': android['workflow_conclusion'],
    'producer_receipt_conclusion': android['producer_original_conclusion'],
    'apk_sha256': android['android'][0]['result']['apk_sha256'],
    'renderer_artifact_sha256': android['pack_sha256'],
    'cases': copy.deepcopy(android_review['cases']),
    'qualification': {**copy.deepcopy(android_review['runtime_summary']),
                      'full_native_matrix_qualified': False, 'production_kmp_factory_qualified': False,
                      'scope_limits': copy.deepcopy(android_review['qualification_limits'])},
    'source_audit_path': evidence_path(ANDROID_AUDIT_PATH),
    'later_visual_review_path': evidence_path(ANDROID_REVIEW_PATH),
}
desktop_collection = {
    'id': DESKTOP_ROOT, 'path': DESKTOP_ROOT,
    'title': 'Godot 2D and 3D — desktop CI 34463877910',
    'platform': 'Godot 4.7.2 desktop, packed renderer, real Kotlin authority, 430 × 932',
    'kind': 'authority_gameplay_capture', 'tier': 'gameplay_current',
    'revision': ANDROID_REV, 'source_revision_exact': True, 'working_tree_dirty': False,
    'ci_run': android['ci_run'], 'source_directory': android['desktop']['source_root'],
    'count': len(desktop_records), 'source_fingerprint_sha256': desktop_report['sourceFingerprintSha256'],
    'renderer_artifact': copy.deepcopy(desktop_report['rendererArtifact']),
    'authority_trace_sha256': android['desktop']['authority_trace_sha256'],
    'run_started_utc': desktop_report['runStartedUtc'], 'run_completed_utc': desktop_report['completedUtc'],
    'status': 'Both desktop modes pass equal complete 42-view authority traces and exit 0; all 22 originals match previously reviewed bytes.',
    'text': 'Exact clean bbfde024 source and PCK a47392b4; separate source identities and original image receipts retained.',
    'source_audit_path': evidence_path(ANDROID_AUDIT_PATH),
    'later_visual_review_path': evidence_path(ANDROID_REVIEW_PATH),
}
ios_collection = {
    'id': IOS_ROOT, 'path': IOS_ROOT,
    'title': 'Godot iOS authority host — four reference failures and secure Exit success, CI 34460468965',
    'platform': 'iPhone 17 simulator, actual native authority host, 1206 × 2622 pixels, display scale 3',
    'kind': 'native_simulator_partial_authority_capture', 'tier': 'native_current',
    'revision': IOS_REV, 'source_revision_exact': True, 'ci_run': ios['ci_run'],
    'source_directory': '/tmp/partydeck-engine-ci/34460468965/godot-ios-authority-gameplay/artifacts/authority-attachments',
    'count': len(ios_records), 'workflow_conclusion': ios['workflow_conclusion'],
    'status': 'All four reference cases fail. Normal 2D reaches the winner but fails revision 42 versus expected 41; secure default renderer Exit passes.',
    'text': 'All 394 original attachment payloads retained, including 35 PNGs and four recordings. Actual Home images coexist with false/background-state-4 observations.',
    'tests': copy.deepcopy(ios_review['cases']),
    'executable_sha256': ios['executable_sha256'], 'renderer_artifact_sha256': ios['pack_sha256'],
    'source_audit_path': evidence_path(IOS_AUDIT_PATH),
    'later_visual_review_path': evidence_path(IOS_REVIEW_PATH),
    'normal_2d_initial_reveal': copy.deepcopy(ios_review['normal_2d_initial_reveal']),
    'normal_text_v1_proposal_status': ios['normal_text_v1_proposal_status'],
    'qualification': {
        'original_xcresult_payloads_verified': ios['original_xcresult_payloads_independently_verified'],
        'paired_measurements': ios['original_measurements_verified'],
        'actual_touch_geometries': ios['actual_touch_geometry_verified'],
        'observed_controls': ios['observed_control_records_verified'],
        'full_reference_tests_passed': 0, 'secure_renderer_exit_passed': True,
        'full_native_matrix_qualified': False, 'production_kmp_factory_qualified': False,
        'scope_limits': copy.deepcopy(ios_review['qualification_limits']),
    },
}
manifest['collections'].extend([android_collection, desktop_collection, ios_collection])

pack_receipt_relative = (
    'build-evidence/godot-comparison-builds/godot/qualification/build/renderer/'
    'partydeck-last-light.receipt.json')
assert (STAGE / ANDROID_ROOT / pack_receipt_relative).is_file()
android_intro = f"""# Godot Android — all four comparison cases and twelve exits pass

[All screenshot collections](../README.md) · [CI run 34463877910](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34463877910) · [Companion desktop originals](../{DESKTOP_ROOT}/README.md) · [Earlier Close failures](../godot-android-34456443339/README.md)

**Evidence status:** All four complete API 35 debug comparison scripts pass. Each seed-2 match finishes at round 14/revision 41, with two accepted viewer plays, two challenges, thirteen advances and an accepted lobby return. Actual Home, opaque Recents and same-process concealed resume complete in all four cases. This collection retains **76 runtime originals**; four separate pre-install Launcher images remain excluded infrastructure evidence.

| Case | Original PNGs | Complete recorded script | Entries / acknowledged exits |
| --- | ---: | --- | ---: |
| 2D / 100% | 19 | Full match, match return, fresh scene Exit and fresh native Close pass | 3 / 3 |
| 2D / 200% | 19 | The same complete script passes at enlarged text | 3 / 3 |
| 3D / 100% | 19 | Full match, match return, fresh scene Exit and fresh native Back pass | 3 / 3 |
| 3D / 200% | 19 | The same complete script passes at enlarged text | 3 / 3 |

Exact clean CI source is {BT}{ANDROID_REV}{BT}. The runtime APK SHA-256 is {BT}{android_collection['apk_sha256']}{BT}; the PCK SHA-256 is {BT}{android['pack_sha256']}{BT} ({android['pack_bytes']:,} bytes). Original [pack receipts]({pack_receipt_relative}), build reports, native inputs and all source identities are retained. All six original ZIPs, their extracted members, three APK/AAB package identities, embedded pack and recorded pack inputs were independently verified. APK, AAB, PCK and ZIP binaries stay outside the gallery.

The four recorded runs use the Android API 35 x86_64 emulator at 720 × 1600 pixels, 280 dpi, 100%/200% text, reduced motion on and sound off. They qualify this comparison host and these scripts. API 36, optimized native execution, production KMP factories, physical devices, LAN, screen-reader traversal, audio dormancy and store acceptance remain outside this evidence.

All twelve entries have a separate acknowledged teardown and actual OS process death. Match return records {BT}return_to_chooser{BT}; fresh scene Exit records {BT}renderer_exit{BT}; final 2D Close records {BT}native_close{BT}; final 3D system Back records {BT}native_back{BT} with zero renderer-event delta. Twelve native barrier/main callbacks and **zero fallbacks** are logged. The 250 ms fallback and 1500 ms renderer wait remain unchanged; this run does not establish an isolated scheduling cause for the earlier failures.

The complete initial 2D Reveal button and concealed-panel borders fit at both text scales. At 200%, portions of the hand, result explanation and Next/Return actions continue below captured viewports. The screenshots preserve that clipping; later native geometry and accepted inputs establish reachability. The 3D enlarged controls retain pinned Show/Hide and turn/rank/round context while content scrolls. Covered and resumed frames conceal private ranks, faces and selection, and actual Recents previews are opaque.

All twelve original process logs retain the EGL {BT}removeVertexArrayObject{BT} error. Ten shader-cache warning pairs remain at error priority, with their original classification and lines preserved. The original [producer receipt](provenance/producer-evidence-summary.json) has a null conclusion; the later [workflow status](provenance/last-run-status.json) is success. Neither original is rewritten. Both failed 3D Close acknowledgments in CI 34456443339 retain their earlier failed status.

[Independent source audit](review/{ANDROID_AUDIT_PATH.name}) · [Later completed visual review](review/{ANDROID_REVIEW_PATH.name}) · [Original native owner audit](provenance/native-evidence-automated.json) · [Collection freeze](provenance/collection-frozen.json). The audit reconciles 48 scene RGB crops, 152 scene-input geometries and 350 native inputs. All 76 runtime originals and the four excluded preparation images were inspected in 28 internal sheets. Those derivatives stay outside the gallery. The source audit's then-pending visual-review field remains unchanged; the later review record supplies completion.

Source alias: {BT}/tmp/partydeck-engine-ci/34463877910{BT}; original storage: {BT}/root/projects/PartyDeck/artifacts/evidence-storage/34463877910{BT}. Every thumbnail displays and opens its unchanged original PNG, with source paths and exact revision retained in the manifest.
"""
for case in android['android']:
    records = [record for record in android_records if record['case'] == case['case']]
    android_intro += f"\n## {case['mode'].upper()} / {case['font_scale'] * 100:g}% text\n\n"
    android_intro += TABLE + '\n'.join(row(record, ANDROID_ROOT) for record in records) + '\n'
markdown(ANDROID_ROOT, android_intro)

desktop_intro = f"""# Godot 2D and 3D — desktop CI 34463877910

[All screenshot collections](../README.md) · [CI run 34463877910](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34463877910) · [Companion Android originals](../{ANDROID_ROOT}/README.md)

**Evidence status:** Both desktop modes complete the same **42-view authority trace** and exit 0. Actual Godot input, the shared bridge and Kotlin authority execute two viewer plays, two challenges and thirteen advances. All **22 original PNGs** match [previously reviewed desktop originals](../godot-desktop-34456443339/README.md), including the Crown winner emblem, public Moon and named challenge/burnout explanation. Each capture retains its new source identity and original receipt.

The [authority report](report.json) records exact clean revision {BT}{ANDROID_REV}{BT} with {BT}workingTreeDirty=false{BT}. Actual Godot 4.7.2, Compatibility / X11 / Xvfb, 430 × 932 pixels, text 1.0, reduced motion and seed 2. Run start: {BT}{desktop_report['runStartedUtc']}{BT}. PCK SHA-256: {BT}{android['pack_sha256']}{BT}. Source fingerprint: {BT}{desktop_report['sourceFingerprintSha256']}{BT}. Complete trace SHA-256: {BT}{android['desktop']['authority_trace_sha256']}{BT}.

The [exact pack receipt](../{ANDROID_ROOT}/{pack_receipt_relative}), immutable source archive, embedded package pack and PCK inventory were independently checked. The companion Android API 35 debug run separately passes all four complete comparison scripts and all twelve exit routes. That native evidence remains bounded to the recorded emulator and debug host.

[2D result](2d/result.json) · [3D result](3d/result.json) · [2D log](2d/godot.log) · [3D log](3d/godot.log). Per-image receipts agree with the full authority traces inside each result JSON. The play-pending frames retain the revealed own hand while selection clears before the authority reply.

[Independent source audit](../{ANDROID_ROOT}/review/{ANDROID_AUDIT_PATH.name}) · [Review record](../{ANDROID_ROOT}/review/{ANDROID_REVIEW_PATH.name}). These 22 originals were matched byte-for-byte to earlier visually reviewed files; they are not counted as new direct visual inspections. Native accessibility, production KMP factories, audio dormancy and physical-device performance remain outside the desktop evidence.

Original source: {BT}{android['desktop']['source_root']}{BT}. Every thumbnail displays and opens its unchanged original PNG.
"""
for mode in ['2d', '3d']:
    desktop_intro += f'\n## {mode.upper()}\n\n' + TABLE
    desktop_intro += '\n'.join(row(record, DESKTOP_ROOT) for record in desktop_records
                              if record['presentation'] == mode) + '\n'
markdown(DESKTOP_ROOT, desktop_intro)

ios_evidence_prefix = 'runtime-evidence/godot-ios-authority-gameplay/evidence/'
ios_intro = f"""# Godot iOS authority host — four reference failures and secure Exit success

[All screenshot collections](../README.md) · [CI run 34460468965](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34460468965) · [Earlier authority run](../godot-ios-authority-34439760695/README.md)

**Evidence status: all four reference tests fail; secure default renderer Exit passes.** These are the original results from the actual Swift host, Kotlin authority framework and Godot renderer. Reaching a pictured checkpoint does not replace a failed test result. All **35 original PNGs and 359 non-PNG attachments** remain retained with their original UUID filenames.

| Test | Original PNGs | Original result and recorded progress |
| --- | ---: | --- |
| 2D / 200% | 9 | Fails: “The real renderer must report current bounded diagnostics.” The final failure measurement is round 4/revision 10, with one accepted play, three advances and zero viewer challenges. Three actual Next taps are retained. |
| 2D / 100% | 9 | Fails the revision assertion: 42 versus expected 41. Reaches the round-14 winner with two plays, thirteen advances, zero viewer challenges and one lobby touch. The failed reference test is not qualified as passing. |
| 3D / 200% | 8 | Fails with controlMissing. Actual input receipts include one play and three Next taps. The last paired outcome screenshot is the earlier round-1 checkpoint, not the final app-stream progress. |
| 3D / 100% | 8 | Fails: “The actual Godot control must be enabled.” Actual receipts include one play and one Next tap. Its outcome screenshots likewise precede later recorded progress. |
| Secure default renderer Exit | 1 | Passes one actual scene Exit, cleanup and released ownership with responsive Host +1. It does not qualify a full secure match or retained-engine lifecycle. |

Exact source revision is {BT}{IOS_REV}{BT}. The [simulator metadata]({ios_evidence_prefix}authority-simulator.json), [Xcode record]({ios_evidence_prefix}authority-host-xcode-version.log) and original runtime logs identify the environment. The originals are 1206 × 2622 pixels at display scale 3; open scenes report a 378 × 691 logical-point surface using {BT}GDTOpenGLLayer{BT}. All 31 paired measurements record normal motion and sound enabled. These settings do not establish audio dormancy or physical-device performance.

The app executable SHA-256 is {BT}{ios['executable_sha256']}{BT}; the PCK SHA-256 is {BT}{ios['pack_sha256']}{BT}. All six artifact ZIPs and their extracted bytes were independently verified. All 394 attachment payloads match the original SQLite UUID mappings and decoded XCResult objects; the app archive's fifteen members and bounded source/pack inputs also match. [Package audit](provenance/authority-package-evidence-summary.json) · [Original pack receipt](provenance/partydeck-last-light.receipt.json) · [Attachment audit](provenance/authority-attachment-evidence-summary.json) · [Original XCTest log]({ios_evidence_prefix}authority-host-test.log).

All four reference cases visibly reach Home with SpringBoard dock icons. Their original observations still report {BT}applicationReportedBackground=false{BT} and application state 4. The gallery preserves the measured discrepancy alongside the Home images and subsequent concealed resumes; it does not invent a replacement state or transfer an older run's Home failure. Manual Pause frames show an opaque native cover. These images do not establish iOS App Switcher snapshot privacy.

Normal 2D initial Reveal still clips: the original control is 56 logical points high, with 31 points visible and 25 points/75 pixels below its clip. Later scrolled Reveal frames fit. At 200%, hand controls, result explanations and Next actions can continue below the captured viewport. The original two-dimensional failure image shows covered cards and complete Reveal/Call the bluff controls at round 4; those visible controls do not override the diagnostics failure. Normal 2D's winner image shows the complete named Crown-claim challenge, Moon mismatch, Moxie's light-4 burnout and Return to lobby, while its measured revision remains 42.

The [normal-text diagnosis](review/normal-text-v1/normal-text-failure-diagnosis.json), original AX lines, source/proposal provenance and base/proposed files are preserved as a seventeen-file historical supplement. Its **v1 patch is rejected and unapplied**: it is a diagnostic-currentness shortcut, not a tested correction. The later corrected proposal is separate work and is not evidence from this historical run.

[Independent source audit](review/{IOS_AUDIT_PATH.name}) · [Later completed visual review](review/{IOS_REVIEW_PATH.name}) · [Collection freeze](provenance/collection-evidence-frozen.json). Review reconciles 31 measurements, 65 actual touch geometries and 75 observed controls. Thirty-three originals were inspected in twelve internal sheets; the requested failure original and secure Exit original were viewed directly at original resolution without making derivatives. All derived sheets remain outside the gallery. The earlier source audit's pending visual-review wording stays unchanged.

Four original recordings and the original decoded [app output stream](runtime/app-stdout-stderr-001.log) are preserved. The decoder receipt reports no crash candidates. Full native matrix, production KMP factories, screen-reader traversal, App Switcher privacy, retained lifecycle, LAN, audio dormancy and physical-device acceptance remain open. Archive and package binaries stay outside the gallery.

Source: {BT}/tmp/partydeck-engine-ci/34460468965/godot-ios-authority-gameplay/artifacts/authority-attachments{BT}. Thumbnails display and link only the unchanged originals. Original suggested attachment names, timestamps, source objects, exact revision and paired measurements remain in the manifest.
"""
for case in ios['cases']:
    heading = ('Secure default renderer Exit' if case['name'] == 'testSecureTableRendererExit()'
               else f"{case['presentation'].upper()} / {case['font_scale'] * 100:g}% text")
    ios_intro += '\n## ' + heading + '\n\n' + TABLE
    ios_intro += '\n'.join(row(record, IOS_ROOT) for record in ios_records
                          if record['test_name'] == case['name']) + '\n'
markdown(IOS_ROOT, ios_intro)

new_index = BASELINE_INDEX_PATH.read_text()
assert new_index.count('**1,584 original app and renderer captures**') == 1
new_index = new_index.replace('**1,584 original app and renderer captures**',
                              '**1,717 original app and renderer captures**')
native_marker = '## Godot native host evidence\n\n| Collection | Images | Evidence scope |\n| --- | ---: | --- |\n'
assert new_index.count(native_marker) == 1
new_index = new_index.replace(native_marker, native_marker + (
    f'| [Godot Android — CI 34463877910]({ANDROID_ROOT}/README.md) | 76 | All four complete API 35 debug scripts and all twelve exits pass. Twelve native barriers/main callbacks, zero fallback; 200% viewport clipping remains. |\n'
    f'| [Godot iOS authority host — CI 34460468965]({IOS_ROOT}/README.md) | 35 | All four reference tests fail; secure Exit passes. Normal 2D reaches the winner but fails revision 42 versus 41. Actual Home/state discrepancies and later-progress limits remain explicit. |\n'
))
desktop_marker = '## Godot gameplay through the real authority\n\n| Collection | Images | Evidence scope |\n| --- | ---: | --- |\n'
assert new_index.count(desktop_marker) == 1
new_index = new_index.replace(desktop_marker, desktop_marker + (
    f'| [Godot 2D and 3D — desktop CI 34463877910]({DESKTOP_ROOT}/README.md) | 22 | Exact clean bbfde024 source, PCK a47392b4…, equal complete 42-view traces and exits 0. All original bytes match prior reviewed images; new source identities remain distinct. |\n'
))
old_latest = '- Latest frozen Android CI 34456443339 retains'
assert new_index.count(old_latest) == 1
new_index = new_index.replace(old_latest, '- Earlier frozen Android CI 34456443339 retains')
index_insert_marker = '- Failed runtime stages, historical layout defects and missing native qualification are recorded'
assert new_index.count(index_insert_marker) == 1
new_index = new_index.replace(index_insert_marker, (
    '- Latest archived Android CI 34463877910 adds 76 runtime originals from exact bbfde024/PCK a47392b4…. All four complete API 35 debug scripts pass with round-14/revision-41 winners, Home/Recents/concealed resumes and three acknowledged exits per case. All twelve actual process deaths, native barriers and main callbacks reconcile, with zero fallback and unchanged 250/1500 ms bounds. Both native 3D Back routes record zero renderer-event delta. All twelve logs retain an EGL error and ten shader-cache warning pairs remain. Initial 2D Reveal fits; large-text scrolling and clipping remain visible. The source audit checks 48 scene RGB crops, 152 scene-input geometries and 350 native inputs. All 76 originals were visually reviewed in 28 internal sheets that also show four excluded preparation images. The 22 companion desktop originals match previously reviewed bytes with equal complete 42-view traces and exits 0. The producer’s original null conclusion remains alongside the later workflow success; historical Close failures are unchanged.\n'
    '- iOS authority CI 34460468965 adds 35 original PNGs and all 394 original attachments from exact 31d148f/PCK 8f24944d…. Four reference tests remain failed, and secure default renderer Exit passes. Normal 2D reaches the round-14 winner but fails revision 42 versus 41; 2D/200% fails current bounded diagnostics at round 4/revision 10 after three actual Next taps. 3D/200% records three Next taps before controlMissing, and normal 3D records one before its control-enabled failure; their pictured round-1 outcomes are earlier checkpoints. All four actual Home images coexist with original foreground-state-4/false observations. Normal 2D initial Reveal has 31 of 56 logical points visible, with 25 points/75 pixels clipped. Thirty-three originals were reviewed in twelve internal sheets; the failure and secure Exit originals were reviewed directly without creating derivatives. The seventeen-file normal-text v1 supplement remains rejected and unapplied historical diagnosis. All test results, original recordings, decoded app output and source/package identities remain preserved; later proposals and newer runs are separate work.\n'
    + index_insert_marker
))

original_design = BASELINE_DESIGN_PATH.read_bytes()
assert original_design.count(PROTECTED_MARKER) == 1
design_prefix, design_suffix = original_design.split(PROTECTED_MARKER, 1)
design_prefix = design_prefix.decode()
old_status = '**Status: latest frozen Android run reviewed; both 3D Close acknowledgments fail.**'
assert design_prefix.count(old_status) == 1
new_status = f"""**Status: latest archived Android comparison passes all four scripts and all twelve exits.** [Android CI 34463877910](../../docs/screenshots/{ANDROID_ROOT}/README.md) retains 76 runtime originals from exact {BT}bbfde024{BT}, PCK {BT}a47392b4…{BT}. All four API 35 debug seed-2 matches reach round 14/revision 41 with two viewer plays, two challenges, thirteen advances, actual Home/Recents and same-process concealed resumes. Match return, fresh scene Exit and fresh native Close (2D) or Back (3D) all complete with acknowledgment and actual child-process death. All twelve exits record native barrier/main callback, with zero fallback; both 3D Back routes have zero renderer-event delta. The 250 ms fallback and 1500 ms renderer wait remain unchanged, and no isolated scheduling cause is established.

Initial 2D Reveal fits at both scales. At 200%, parts of hands, explanations and Next/Return actions continue below captured viewports; later native input establishes reachability. All twelve original logs retain the EGL error and ten shader-cache warning pairs remain. The original producer conclusion is null, while the final workflow succeeds. All 76 runtime originals were visually reviewed in 28 internal sheets that also include four excluded preparation images. [Desktop CI 34463877910](../../docs/screenshots/{DESKTOP_ROOT}/README.md) adds 22 distinct originals matched to previously reviewed bytes, with equal complete 42-view traces and exits 0. Derived sheets stay outside the gallery. Full native matrix, production KMP factories, accessibility, audio dormancy and physical-device acceptance remain open.

**Latest archived iOS authority run retains four reference failures and secure Exit success.** [iOS CI 34460468965](../../docs/screenshots/{IOS_ROOT}/README.md) preserves 35 originals and all 394 attachment payloads from exact {BT}31d148f{BT}, PCK {BT}8f24944d…{BT}. Normal 2D reaches the round-14 winner but fails revision 42 versus expected 41; it records two plays, thirteen advances, zero viewer challenges and one lobby touch. 2D/200% fails current bounded diagnostics at round 4/revision 10 after one play and three advances. 3D/200% records three Next taps before {BT}controlMissing{BT}; normal 3D records one before the enabled-control assertion fails. Their pictured round-1 outcomes are earlier checkpoints and do not represent final app-stream progress.

All four iOS reference cases visibly reach Home and subsequently resume concealed, while the original Home observations still report application state 4 and background=false. Normal 2D initial Reveal has 31 of 56 logical points visible, leaving 25 points/75 pixels clipped. Secure Exit alone passes released ownership, cleanup and responsive Host +1. Thirty-three originals were reviewed in twelve internal sheets; the requested failure and secure Exit originals were viewed directly without derivatives. All 31 measurements use normal motion and sound enabled. The normal-text v1 proposal remains rejected and unapplied historical diagnosis; later corrected proposals are separate work. App Switcher privacy, retained lifecycle, production factories, screen-reader support, audio dormancy and physical-device qualification remain open.

"""
design_prefix = design_prefix.replace(old_status, new_status
    + '**Earlier frozen Android run reviewed; both 3D Close acknowledgments fail.**', 1)
new_design = design_prefix.encode() + PROTECTED_MARKER + design_suffix
assert new_design.split(PROTECTED_MARKER, 1)[1] == original_design.split(PROTECTED_MARKER, 1)[1]

for key in ['collections', 'screenshots', 'evidence', 'excluded_source_images']:
    assert manifest[key][:len(baseline[key])] == baseline[key], key
assert manifest['referenced_asset_proofs'] == baseline['referenced_asset_proofs']
assert len(manifest['screenshots']) == 1717
assert len(manifest['collections']) == 73
new_screenshots = manifest['screenshots'][len(baseline['screenshots']):]
new_evidence = manifest['evidence'][len(baseline['evidence']):]
new_paths = [record['path'] for record in new_screenshots + new_evidence]
assert len(new_paths) == len(set(new_paths))
assert len(new_evidence) == 1027
assert not any(Path(path).suffix.lower() in ['.apk', '.aab', '.pck', '.zip'] for path in new_paths)
assert all((STAGE / record['path']).name == record['original_filename']
           for record in new_screenshots + new_evidence)
assert {str(path.relative_to(STAGE)) for path in STAGE.rglob('*.png')} == {
    record['path'] for record in new_screenshots}
staged_manifest = STAGE / 'manifest.json'
staged_manifest.write_bytes(json_bytes(manifest))
(STAGE / 'README.md').write_text(new_index)
(STAGE / 'design-review.md').write_bytes(new_design)

checksums = {}
for line in (GALLERY / 'SHA256SUMS').read_text().splitlines():
    digest, path = line.split('  ', 1)
    assert path not in checksums
    checksums[path] = digest
assert 'docs/screenshots/manifest.json' not in checksums
prior_record_checksum_paths = {
    'docs/screenshots/' + record['path'] for record in baseline['screenshots'] + baseline['evidence']}
auxiliary_checksum_paths = set(checksums) - prior_record_checksum_paths
assert len(auxiliary_checksum_paths) == 5
for record in new_screenshots + new_evidence:
    repo_path = 'docs/screenshots/' + record['path']
    assert repo_path not in checksums
    checksums[repo_path] = record['sha256']
(STAGE / 'SHA256SUMS').write_text(''.join(
    digest + '  ' + path + '\n' for path, digest in sorted(checksums.items())))
assert len(checksums) == len(manifest['screenshots']) + len(manifest['evidence']) + len(auxiliary_checksum_paths)

# Preserve the baseline until the complete new archive is ready, then install only owned paths.
unchanged_baseline()
for root in NEW_ROOTS:
    shutil.copytree(STAGE / root, GALLERY / root)
for name in ['manifest.json', 'README.md', 'SHA256SUMS']:
    (GALLERY / name).write_bytes((STAGE / name).read_bytes())
DESIGN.write_bytes(new_design)

new_evidence_path_list = Path('/tmp/partydeck-gallery-1717-new-evidence-paths.txt')
assert not new_evidence_path_list.exists()
new_evidence_path_list.write_text(''.join(
    'docs/screenshots/' + record['path'] + '\n' for record in new_evidence))
handoff = {
    'baseline_commit_acknowledged_by_root': BASELINE_COMMIT,
    'new_collections': NEW_ROOTS, 'screenshots': len(manifest['screenshots']),
    'evidence_files': len(manifest['evidence']), 'checksum_entries': len(checksums),
    'new_original_pngs': len(new_screenshots), 'new_evidence_files': len(new_evidence),
    'new_readme_pages': len(NEW_ROOTS), 'manifest_sha256': sha(GALLERY / 'manifest.json'),
    'auxiliary_checksum_paths': sorted(auxiliary_checksum_paths),
    'new_evidence_path_list': str(new_evidence_path_list),
    'evidence_by_collection': dict(Counter(record['collection'] for record in new_evidence)),
    'new_application_executions': 0, 'new_builds_or_runtime_tests': 0, 'git_commands_run': 0,
}
with Path('/tmp/partydeck-gallery-1717-build-receipt.json').open('x') as stream:
    json.dump(handoff, stream, indent=2, ensure_ascii=False)
    stream.write('\n')
print(json.dumps(handoff, indent=2))
