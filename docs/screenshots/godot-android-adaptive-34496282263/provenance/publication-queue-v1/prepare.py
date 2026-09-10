"""Stage Android originals from completed owner inventories without repeating audits."""

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
import hashlib
import html
import json
import os
import re
import shutil
import stat
import struct


ROOT = Path('/root/projects/PartyDeck')
QUEUE = Path(__file__).resolve().parent
PAYLOAD = QUEUE / 'payload/docs/screenshots'
A36 = ROOT / 'artifacts/evidence-storage/34496282263'
A35 = ROOT / 'artifacts/evidence-storage/34496267571'
C36 = 'godot-android-adaptive-34496282263'
C35 = 'android-34496267571'
HEAD = '410c9386dd88b2ad0ab380e5b8f1f9bf19674b00'
MAP36 = 'triage/capture-publication-inventory.json'
MAP35 = 'review/capture-gallery-mapping.json'
INPUTS = [
    (A36, 'evidence-freeze.json', '754044355caa8b687325ede9c6f2cc864b275cb2195d64a959ac7b237673a71b'),
    (A36, 'triage/originals-audit.json', 'e1ce295fbd4f8d89c0fe5b1af4f0e46803da6bcc89a1025b00320a86f9eb493c'),
    (A36, MAP36, '6f4b20060ee22bd72e00691f403a7bbc499caae3bdf1870f983c37fad40c46a6'),
    (A36, 'triage/first-failures.json', '743eddd56b39e262a849ad471fcf8320dafc76a8984fc7ebdf48e9e75a063055'),
    (A35, 'original-collection-frozen.json', '29ba11c01c3d3f1477fbbaaa7462490d6ba1d4e2a5909d75b2a019475a0381af'),
    (A35, 'review-final-freeze.json', 'd1c83bfe323c488c6b0b52374ddea2cb5b49034144413a66be68d11141b4faa0'),
    (A35, MAP35, '71197b81b8e83f3ee6012e81a5dbcd935559edcc18bcb1e381f182704e32b765'),
    (A35, 'review/runtime-capture-audit.json', 'c85587a569955c5ab970e3fe63d2473e1cd964e5cbab896749cdfd988ca9b521'),
    (A35, 'review/first-failure-triage.json', '9a9cc8330eaedd246273ae37d41ad7c0d4b7a37167062b1f0755a87ac22950c4'),
]
VISUAL_INPUTS = [
    (Path('/tmp/partydeck-gallery-after-2013-api36-visual-review.json'), 'review-design-visual-review.json',
     '635a14e10100384c646d38f2f8b25ed2fd14e0607af7b96c27fc13ce16ba564d'),
    (Path('/tmp/partydeck-api36-debug2x-view-receipt-v1/visual-receipt.json'), 'ui-shell/visual-receipt.json',
     '68362976e905e99a2763b973e2087d24f17d8e99f1fbe7ed6e4cdc8d7726d19a'),
    (Path('/tmp/partydeck-api36-debug2x-view-receipt-v1/freeze.json'), 'ui-shell/freeze.json',
     'd3fa159a8195b85dff48a6bd57492924afc34af8aed1fcb9ce040274f60312c2'),
]


def load(path):
    return json.loads(path.read_bytes())


def info(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def href(target, start):
    return quote(os.path.relpath(target, start), safe='/')


assert not PAYLOAD.exists() and not (QUEUE / 'queue-freeze.json').exists()
source_receipts = []
receipt_index = {}
for base, relative, digest in INPUTS:
    actual = info(base / relative)
    assert actual['sha256'] == digest, relative
    source_receipts.append(dict(source=str(base / relative), **actual))
    receipt_index[str(base / relative)] = actual
for source, target_name, digest in VISUAL_INPUTS:
    actual = info(source)
    assert actual['sha256'] == digest, str(source)
    source_receipts.append(dict(source=str(source), **actual))
    receipt_index[str(source)] = actual

map36 = load(A36 / MAP36)
audit36 = load(A36 / 'triage/originals-audit.json')
map35 = load(A35 / MAP35)
runtime35 = load(A35 / 'review/runtime-capture-audit.json')
visual36 = load(VISUAL_INPUTS[0][0])
visual36_index = {row['source_original']: row for row in visual36['captures']}
ui36 = load(VISUAL_INPUTS[1][0])
ui36_index = {row['original_png']['original_path']: row for row in ui36['views']}
assert map36['headSha'] == map35['headSha'] == HEAD
assert map36['runId'] == 34496282263 and map35['runId'] == 34496267571
assert map36['originalCapturePairCount'] == 30 and len(map36['captures']) == 30
assert map35['imageCount'] == len(map35['images']) == 193
assert map35['categories'] == {'ordinary-ui': 62, 'native-session': 61, 'emulator-preparation': 1, 'compose-jvm-snapshot': 69}
assert map35['viewedOriginalCount'] == 7 and map35['viewedDerivedCount'] == 0
assert runtime35['variants']['debug']['finalResultAvailable'] is False
assert runtime35['variants']['optimized-test-signed']['finalResultAvailable'] is True
assert visual36['original_capture_count'] == 30 and visual36['direct_original_views'] == 28
assert visual36['source_revision'] == HEAD and visual36['source_mapping_sha256'] == receipt_index[str(A36 / MAP36)]['sha256']
assert ui36['view_count'] == 2 and ui36['head_sha'] == HEAD

copies, screenshots, evidence, published_mapping = [], [], [], []
destination_index = {}


def copy_original(source, base, target, collection, expected, kind='original_evidence'):
    source = Path(source)
    destination = PAYLOAD / target
    assert source.resolve().is_relative_to(base.resolve()) and not source.is_symlink()
    assert destination.resolve().is_relative_to(PAYLOAD)
    if target in destination_index:
        previous = destination_index[target]
        assert previous['source'] == str(source) and previous['sha256'] == expected['sha256']
        assert kind != 'original_app_capture', ('Duplicate capture identity', target)
        return previous
    actual = info(source)
    assert actual['sha256'] == expected['sha256'] and actual['bytes'] == expected.get('bytes', actual['bytes']), str(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    assert not destination.exists()
    shutil.copy2(source, destination)
    assert info(destination) == actual, target
    row = dict(source=str(source), staged=str(destination), destination='docs/screenshots/' + target,
               gallery_path=target, collection=collection, artifact_type=kind, **actual)
    copies.append(row)
    destination_index[target] = row
    if kind != 'original_app_capture':
        evidence.append(dict(path=target, original_filename=source.name, source_original=str(source),
                             collection=collection, artifact_type=kind, **actual))
    return row


def add_image(copied, dimensions, run, scenario, platform, kind, notes, **extra):
    raw = (PAYLOAD / copied['gallery_path']).read_bytes()
    assert raw[:8] == b'\x89PNG\r\n\x1a\n' and raw[12:16] == b'IHDR'
    assert list(struct.unpack('>II', raw[16:24])) == dimensions
    row = dict(id=copied['gallery_path'].removesuffix('.png'), collection=copied['collection'],
               path=copied['gallery_path'], original_filename=Path(copied['gallery_path']).name,
               scenario=scenario, platform=platform, artifact_type=kind,
               width_px=dimensions[0], height_px=dimensions[1], bytes=copied['bytes'], sha256=copied['sha256'],
               source_original=copied['source'], source_aliases=[], source_revision=HEAD,
               source_revision_exact=True, ci_run=run, ci_run_attempt=1,
               publication_reaudited_evidence=False, notes=notes, **extra)
    screenshots.append(row)
    return row


for base, relative, digest in INPUTS:
    collection = C36 if base == A36 else C35
    copy_original(base / relative, base, collection + '/provenance/' + relative, collection,
                  receipt_index[str(base / relative)], 'existing_owner_receipt')
for source, target_name, digest in VISUAL_INPUTS:
    copy_original(source, source.parent, C36 + '/provenance/' + target_name, C36,
                  receipt_index[str(source)], 'existing_owner_visual_review')

limits36 = ('Debug 1× passed initial native landscape entry, then failed held rotation. Debug 2× passed initial entry, '
            'reported held rotation unsupported, then failed portrait Standard first-card reachability. '
            'Both optimized cases aborted during Godot JNI bootstrap. No 3D, transition-video or pixel-privacy qualification follows from this run.')
case36 = {row['case']: row for row in audit36['cases']}
result36 = {}
for case_name, case in case36.items():
    for key in ('originalResult', 'originalExecution'):
        original = case[key]
        copied = copy_original(A36 / original['file'], A36, C36 + '/' + original['file'], C36, original)
        if key == 'originalResult':
            result36[case_name] = copied['gallery_path']

for capture in map36['captures']:
    targets = {}
    for key in ('png', 'xml', 'captureReceipt'):
        original = capture[key]
        target = C36 + '/' + original['file']
        copied = copy_original(A36 / original['file'], A36, target, C36, original,
                               'original_app_capture' if key == 'png' else 'original_evidence')
        targets[key] = target
        if key == 'png':
            png_copy = copied
    case = case36[capture['case']]
    receipt = load(PAYLOAD / targets['captureReceipt'])
    stage_status = case['checks'].get(capture['stage'], {}).get('status')
    notes = [capture['qualificationCaption'], limits36,
             'Original PNG/XML/JSON acquisition is sequential; this publication preparation adds no new visual or native qualification.',
             'Original checker failure: ' + case['error']]
    original_path = str(A36 / capture['png']['file'])
    visual = visual36_index[original_path]
    assert visual['source_mapping_record'] == capture
    assert visual['sha256'] == capture['png']['sha256'] and visual['bytes'] == capture['png']['bytes']
    if visual['review_method'] == 'published_exact_bytes':
        published_match = ROOT / 'docs/screenshots' / visual['published_match']
        assert published_match.resolve().is_relative_to(ROOT / 'docs/screenshots')
        assert info(published_match) == {key: visual[key] for key in ('bytes', 'sha256')}
    elif visual['review_method'] == 'same_batch_exact_bytes':
        matched = visual36_index[visual['matched_direct_original']]
        assert matched['actually_viewed_by_review_design'] is True and matched['sha256'] == visual['sha256']
    notes.insert(0, ('Existing direct visual observation: ' if visual['actually_viewed_by_review_design'] else
                     'Existing observation from a named byte-identical original; this capture was not directly viewed by review_design: ')
                    + visual['visual_observation'])
    ui_view = ui36_index.get(original_path)
    observers = ['review_design'] if visual['actually_viewed_by_review_design'] else []
    if ui_view:
        observers.append('ui_shell')
        for map_key, view_key in (('png', 'original_png'), ('xml', 'paired_xml'), ('captureReceipt', 'paired_acquisition_receipt')):
            assert all(capture[map_key][key] == ui_view[view_key][key] for key in ('bytes', 'sha256'))
        notes.insert(1, 'Existing ui_shell direct visual observation: ' + ui_view['visual_observation'])
    row = add_image(png_copy, [capture['dimensions']['width'], capture['dimensions']['height']], '34496282263',
                    capture['name'].replace('-', ' ').capitalize(),
                    f'Android API 36 x86_64 emulator, production {capture["variant"]} qualification APK',
                    'native_emulator_capture', notes,
                    font_scale=float(capture['fontScale']), case_name=capture['case'], case_status=capture['caseOutcome'],
                    captured_utc=receipt.get('screenshot_received_utc'), capture_completed_utc=receipt.get('ended_utc', receipt.get('endedUtc')),
                    recorded_stage=capture['stage'], recorded_stage_status=stage_status,
                    synthetic_invitation_fixture=False, existing_owner_visual_review=bool(observers),
                    visual_review_observers=observers, visual_review_method=visual['review_method'],
                    visual_observation=visual['visual_observation'],
                    visual_review_receipt_path=C36 + '/provenance/review-design-visual-review.json',
                    additional_visual_review_receipt_path=C36 + '/provenance/ui-shell/visual-receipt.json' if ui_view else None,
                    visual_review_matched_published_path=visual.get('published_match'),
                    visual_review_matched_original=visual.get('matched_direct_original'),
                    paired_ui_path=targets['xml'], capture_receipt_path=targets['captureReceipt'],
                    original_result_path=result36[capture['case']], source_mapping_path=C36 + '/provenance/' + MAP36,
                    engine_pixels_qualified=False, transition_privacy_qualified=False)
    published_mapping.append(dict(owner_record=capture, gallery_path=row['path'], paired_ui_path=targets['xml'],
                                  capture_receipt_path=targets['captureReceipt'], visual_review=visual,
                                  additional_ui_shell_view=ui_view))

videos = []
for video in map36['videos']:
    source = A36 / video['case'] / 'godot-adaptive/runtime' / video['original']['file']
    videos.append(dict(source_original=str(source), source_owner_record=video, published=False,
                       original_png_count_contribution=0, reason='Original video reference only; no derived frames and no transition/privacy qualification.'))

ordinary_titles = {
    'home': 'Home and practice route', 'rules-intro': 'Rules introduction', 'rules-last-step': 'Rules final step',
    'rules-practice-action': 'Rules Practice action checkpoint', 'rules-practice-entered': 'Practice entered from Rules',
    'rules-returned-home': 'Home after leaving Rules-entered practice', 'settings-changed': 'Changed settings',
    'settings-return-home': 'Home after settings', 'settings-persisted': 'Persisted settings checkpoint',
    'practice-concealed': 'Practice with the hand concealed', 'practice-selected': 'Practice card selection checkpoint',
    'practice-resumed-concealed': 'Practice concealed after resume', 'practice-after-play': 'Practice after the recorded play',
    'practice-returned-home': 'Home after leaving practice', 'host-lobby': 'Host lobby',
    'host-after-share': 'Host lobby after the sharing flow', 'host-returned-home': 'Home after leaving the host lobby',
    'join-name-soft-ime': 'Join name field with the software keyboard', 'join-invalid': 'Invalid join input feedback',
    'home-actions': 'Home action checkpoints', 'settings': 'Settings checkpoint', 'private-hand': 'Own-hand checkpoint',
    'play-action': 'Play action reachability checkpoint', 'final-screen': 'Final ordinary-smoke diagnostic',
}
runtime_root35 = A35 / 'android-jvm-reports/build/ci/android'
jvm_root35 = A35 / 'android-jvm-reports/composeApp/build/ui-snapshots'
optimized_result = runtime35['variants']['optimized-test-signed']['finalResult']
optimized_result_target = C35 + '/' + Path(optimized_result['path']).relative_to(runtime_root35).as_posix()
copy_original(Path(optimized_result['path']), A35, optimized_result_target, C35 + '-godot-session', optimized_result)
limits35 = ('Ordinary debug and optimized smokes passed. The debug native phase hit the executed ten-minute wrapper limit during '
            'partial 3d.renderer-death; no final debug result or complete check map exists. The optimized renderer aborted during Godot JNI startup. '
            'Neither native variant is fully qualified. Selected stills do not establish continuous privacy, engine gameplay or TalkBack speech/traversal.')
for capture in map35['images']:
    category = capture['category']
    source = Path(capture['png']['path'])
    variant = capture.get('variant')
    if category == 'compose-jvm-snapshot':
        collection = C35 + '-compose-jvm'
        target = C35 + '/compose-jvm/' + source.relative_to(jvm_root35).as_posix()
    else:
        suffix = variant if category == 'ordinary-ui' else 'godot-session' if category == 'native-session' else 'preparation'
        collection = C35 + '-' + suffix
        target = C35 + '/' + source.relative_to(runtime_root35).as_posix()
    copied = copy_original(source, A35, target, collection, capture['png'], 'original_app_capture')
    links = {}
    for key in ('xml', 'json'):
        original = capture[key]
        if original:
            paired_source = Path(original['path'])
            paired_target = C35 + '/' + paired_source.relative_to(runtime_root35).as_posix()
            copy_original(paired_source, A35, paired_target, collection, original)
            links[key] = paired_target
        else:
            links[key] = None
    name = source.stem
    notes = [limits35, *map35['limits']]
    case_status, result_path, capture_receipt_path = None, None, None
    stage = capture.get('stage')
    capture_time = None
    font_scale = None
    if category == 'ordinary-ui':
        short = name.removeprefix('large-text-')
        scenario = ordinary_titles.get(short, short.replace('-', ' ').capitalize())
        if name.startswith('large-text-'):
            scenario += ' — large text'
        case_status = 'passed'
        result_path = links['json']
        notes.insert(0, capture['association'])
        notes.insert(1, 'Original ordinary UI smoke passed; no full new accessibility or visual review is claimed.')
        if name == 'final-screen':
            notes.insert(1, 'This distinct final original is associated with last-ui.xml, not a named same-stem PNG/XML capture pair.')
        if short == 'play-action' and name.startswith('large-text-'):
            notes.insert(1, 'Recorded action reachability is not a second accepted-play claim.')
    elif category == 'native-session':
        scenario = name.replace('-', ' ').capitalize()
        capture_receipt_path = links['json']
        cap = load(PAYLOAD / capture_receipt_path)
        capture_time = cap.get('screenshot_received_utc')
        case_status = 'incomplete' if variant == 'debug' else 'failed'
        result_path = None if variant == 'debug' else optimized_result_target
        notes.insert(0, f'Original {variant} native stage: {stage}; capture status: {capture["captureResult"]}.')
        notes.insert(1, 'Native gameplay was not invoked by the API35 checker; a native Ready capture does not qualify gameplay.')
    elif category == 'emulator-preparation':
        scenario = 'Emulator preparation — original final screen'
        result_path = links['json']
        notes.insert(0, 'Emulator setup capture retained separately from app and engine behavior.')
    else:
        scenario = name.replace('-', ' ').capitalize()
        notes.insert(0, 'Original Compose/Skia JVM UI-test snapshot. It is not an emulator or device capture and supplies no native accessibility or renderer qualification.')
    if capture['viewedOriginal']:
        notes.insert(0, 'Existing direct visual observation: ' + capture['visualObservation'])
    platform = ('Compose/Skia JVM UI test capture' if category == 'compose-jvm-snapshot' else
                'Android API 35 x86_64 emulator preparation' if category == 'emulator-preparation' else
                f'Android API 35 x86_64 emulator, production {variant} APK')
    kind = 'jvm_ui_fixture_capture' if category == 'compose-jvm-snapshot' else 'native_emulator_capture'
    row = add_image(copied, capture['dimensions'], '34496267571', scenario, platform, kind, notes,
                    font_scale=font_scale, captured_utc=capture_time, case_status=case_status,
                    category=category, variant=variant, recorded_stage=stage, synthetic_invitation_fixture=False,
                    existing_owner_visual_review=capture['viewedOriginal'],
                    visual_review_observers=['review_release'] if capture['viewedOriginal'] else [],
                    visual_observation=capture['visualObservation'],
                    visual_review_receipt_path=C35 + '/provenance/' + MAP35 if capture['viewedOriginal'] else None,
                    paired_ui_path=links['xml'], capture_receipt_path=capture_receipt_path,
                    original_result_path=result_path, source_mapping_path=C35 + '/provenance/' + MAP35,
                    native_qualification=False, transition_privacy_qualified=False)
    published_mapping.append(dict(owner_record=capture, gallery_path=row['path'], paired_ui_path=links['xml'],
                                  capture_receipt_path=capture_receipt_path, original_result_path=result_path))

collections = [
    dict(id=C36, path=C36, count=30, title='Android API 36 adaptive — native entry and retained failures',
         platform='Android API 36 x86_64 emulator, debug and optimized qualification APKs', kind='native_emulator_capture', tier='native_current',
         revision=HEAD, source_revision_exact=True, ci_run='34496282263', workflow_conclusion='failure', status=limits36,
         text='30 original PNG/XML/JSON capture triples. Four installations passed; across the 96 adaptive scopes, two passed, four failed, one was unsupported and 89 were not reached. The visual receipt records 28 direct original views and two named exact-byte reuses, preserving every capture identity. Original video references remain in provenance only.'),
]
for variant in ('debug', 'optimized-test-signed'):
    collections.append(dict(id=C35 + '-' + variant, path=C35 + '/' + variant, count=31,
                            title=f'Android API 35 {variant} — ordinary UI smoke passed',
                            platform=f'Android API 35 x86_64 emulator, production {variant} APK', kind='native_emulator_capture', tier='native_current',
                            revision=HEAD, source_revision_exact=True, ci_run='34496267571', workflow_conclusion='failure',
                            status='The ordinary UI smoke passed. The separate native phase failed or ended incomplete; no full native qualification follows.',
                            text='30 named PNG/XML pairs and one distinct final PNG associated with last-ui.xml. Original result JSON and owner mapping are preserved.'))
collections += [
    dict(id=C35 + '-godot-session', path=C35 + '/godot-session', count=61,
         title='Android API 35 production native session — timeout and JNI crash',
         platform='Android API 35 x86_64 emulator, production debug and optimized qualification APKs', kind='native_emulator_capture', tier='native_current',
         revision=HEAD, source_revision_exact=True, ci_run='34496267571', workflow_conclusion='failure', status=limits35,
         text='55 debug and six optimized original PNG/XML/JSON triples. Seven originals have recorded direct visual observations. Debug has no final result; partial progression cannot supply a complete native pass.'),
    dict(id=C35 + '-preparation', path=C35 + '/preparation', count=1, title='Android API 35 emulator preparation',
         platform='Android API 35 x86_64 emulator preparation', kind='native_emulator_setup_capture', tier='native_current',
         revision=HEAD, source_revision_exact=True, ci_run='34496267571', workflow_conclusion='failure',
         status='Original emulator setup evidence; no app or engine qualification is claimed by this capture.',
         text='One original final screen, its separately retained last-ui.xml and the original preparation-attempt.json.'),
    dict(id=C35 + '-compose-jvm', path=C35 + '/compose-jvm', count=69, title='Compose JVM UI snapshots — CI 34496267571',
         platform='Compose/Skia JVM UI tests', kind='jvm_ui_fixture_capture', tier='fixture',
         revision=HEAD, source_revision_exact=True, ci_run='34496267571', workflow_conclusion='failure',
         status='Original JVM UI-test snapshots, separate from emulator and native-session outcomes.',
         text='69 original PNGs preserve their recorded filenames and exact CI source. No native iOS/Android accessibility, TalkBack or real Godot qualification is inferred.'),
]

for collection in collections:
    start = collection['path']
    mapping = C36 + '/provenance/' + MAP36 if collection['ci_run'] == '34496282263' else C35 + '/provenance/' + MAP35
    lines = [f'# {collection["title"]}', '', f'[All collections]({href("README.md", start)}) · '
             f'[Original CI run](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/{collection["ci_run"]})', '',
             collection['status'], '', collection['text'], '', f'Exact source: `{HEAD}`. [Original owner capture mapping]({href(mapping, start)}).', '',
             '| Original capture | Recorded scenario and retained limits |', '| --- | --- |']
    for row in screenshots:
        if row['collection'] != collection['id']:
            continue
        relative = href(row['path'], start)
        caption = html.escape(row['scenario'])
        links = []
        for key, label in (('paired_ui_path', 'Original XML'), ('capture_receipt_path', 'Original capture receipt'), ('original_result_path', 'Original result')):
            if row.get(key):
                links.append(f'[{label}]({href(row[key], start)})')
        notes = '<br>'.join(html.escape(note) for note in row['notes'])
        lines.append(f'| <a href="{relative}"><img src="{relative}" alt="{caption}" width="168"></a> | '
                     f'**{caption}**<br>{html.escape(row["platform"])}<br>'
                     f'[{html.escape(row["original_filename"])}]({relative}); {row["width_px"]} × {row["height_px"]} px<br>'
                     f'SHA-256: <code>{row["sha256"]}</code><br>{" · ".join(links)}<br>{notes} |')
    save(PAYLOAD / start / 'README.md', '\n'.join(lines) + '\n')

save(PAYLOAD / C35 / 'README.md', '# Android and JVM originals — CI 34496267571\n\n' + limits35 + '\n\n'
     'Exact source: `' + HEAD + '`.\n\n| Collection | Original PNGs | Scope |\n| --- | ---: | --- |\n'
     '| [Debug ordinary flow](debug/README.md) | 31 | Ordinary UI smoke passed. |\n'
     '| [Optimized ordinary flow](optimized-test-signed/README.md) | 31 | Ordinary UI smoke passed. |\n'
     '| [Native sessions](godot-session/README.md) | 61 | Debug incomplete after wrapper timeout; optimized JNI startup crash. |\n'
     '| [Emulator preparation](preparation/README.md) | 1 | Setup capture only. |\n'
     '| [Compose JVM snapshots](compose-jvm/README.md) | 69 | JVM UI tests, separate from emulator images. |\n\n'
     '[Original owner mapping](provenance/review/capture-gallery-mapping.json) · [First failure receipt](provenance/review/first-failure-triage.json) · '
     '[Frozen review](provenance/review-final-freeze.json). Distinct recorded original captures are retained even when their pixels match another capture.\n')

assert len(screenshots) == 223 and len({row['path'] for row in screenshots}) == 223
assert Counter(row['collection'] for row in screenshots) == {c['id']: c['count'] for c in collections}
assert sum(row['paired_ui_path'] is not None for row in screenshots) == 154
assert sum(row['capture_receipt_path'] is not None for row in screenshots) == 91
assert sum(row['existing_owner_visual_review'] is True for row in screenshots) == 35
generated_pages = [str(path.relative_to(PAYLOAD)) for path in sorted(PAYLOAD.rglob('README.md'))]
manifest = dict(schema_version=1, preparation_scope='Publication copy preparation only; frozen owner mappings and receipts reused. No builds, native execution, downloads, new image views or repeated evidence audits.',
                publication_state='Staged outside the live gallery for review_design; root owns Git.', source_revision=HEAD,
                original_png_count=223, original_emulator_png_count=154, original_jvm_snapshot_count=69,
                original_png_with_xml_count=154, original_png_xml_capture_receipt_triples=91,
                supplemental_review_sheet_count=0, supplemental_original_count_contribution=0,
                collections=collections, screenshots=screenshots, evidence=evidence, supplemental=[],
                copy_plan=copies, source_receipts=source_receipts, source_capture_publication_mapping=published_mapping,
                referenced_original_videos=videos, generated_gallery_pages=generated_pages)
save(QUEUE / 'publication-manifest.json', manifest)
save(QUEUE / 'copy-paths.tsv', 'sha256\tbytes\tsource\tstaged\tdestination\n' + ''.join(
    f'{row["sha256"]}\t{row["bytes"]}\t{row["source"]}\t{row["staged"]}\t{row["destination"]}\n' for row in copies))
save(QUEUE / 'gallery-index-rows.md', '| Proposed collection | Original PNGs | Evidence scope |\n| --- | ---: | --- |\n' + ''.join(
    f'| [{c["title"]}]({c["path"]}/README.md) | {c["count"]} | {c["status"]} |\n' for c in collections))
save(QUEUE / 'HANDOFF.md', '# Android screenshot publication queue\n\n'
     'Copy `godot-android-adaptive-34496282263` and `android-34496267571` from `payload/docs/screenshots/` into the gallery. '
     'Merge the six collection records, 223 original screenshot records, evidence and index rows through review_design’s existing workflow. '
     'These files are fragments; do not replace the shared manifest or README. Root owns Git.\n\n'
     'There are 30 API36 original capture triples and 193 API35 originals: 62 ordinary UI captures, 61 native-session triples, one emulator-preparation image and 69 Compose JVM snapshots. '
     'The two ordinary final screens retain their separately associated last-ui.xml files. The preparation image is setup evidence; the 69 JVM images are not emulator captures. '
     'Distinct original capture paths are never collapsed by shared content hashes. There are no new image derivatives or video frames.\n\n'
     'API36 preserves review_design’s 28 direct original views and two named exact-byte reuses, plus ui_shell’s two earlier direct views. '
     'API35 preserves review_release’s seven direct native views. Further gallery-owner review receipts may be integrated separately without changing these original captures.\n\n'
     + limits36 + '\n\n' + limits35 + '\n\n'
     'All copied bytes, PNG header dimensions and staged page/metadata links are checked. Native original results, XML, capture receipts and compact frozen owner provenance are preserved. '
     'Video source references retain their original status and hashes without copying video. No APK, PCK, ZIP or source file is copied. '
     'See `copy-paths.tsv`, `validation-report.json`, `payload-SHA256SUMS` and `queue-freeze.json`.\n')

page_links = 0
for relative in generated_pages:
    page = PAYLOAD / relative
    text = page.read_text()
    for link in re.findall(r'(?:href|src)="([^"]+)"', text) + re.findall(r'\]\(([^)\n]+)\)', text):
        parsed = urlsplit(html.unescape(link))
        if parsed.scheme or parsed.netloc:
            continue
        target = (page.parent / unquote(parsed.path)).resolve()
        if not target.exists():
            relative_target = target.relative_to(PAYLOAD)
            assert relative_target.as_posix() == 'README.md' and (ROOT / 'docs/screenshots' / relative_target).is_file(), (relative, link)
        page_links += 1
metadata_links = 0
for row in screenshots + evidence:
    for key in ('path', 'paired_ui_path', 'capture_receipt_path', 'original_result_path', 'source_mapping_path', 'visual_review_receipt_path', 'additional_visual_review_receipt_path'):
        if row.get(key):
            assert (PAYLOAD / row[key]).is_file(), (key, row[key])
            metadata_links += 1
for receipt in source_receipts:
    assert info(Path(receipt['source'])) == {key: receipt[key] for key in ('bytes', 'sha256')}
save(QUEUE / 'validation-report.json', dict(original_png_count=223, original_emulator_png_count=154,
     original_jvm_snapshot_count=69, source_and_staged_hash_checks=len(copies), png_header_dimension_checks=223,
     preserved_api36_direct_views=28, preserved_api36_exact_byte_review_reuses=2, preserved_api35_owner_direct_views=7,
     checked_page_links=page_links, checked_metadata_links=metadata_links, source_receipts_unchanged=True,
     new_image_views=0, generated_image_or_video_frames=0, repeated_evidence_audits=0,
     publication_integrity_only=True, shared_gallery_modified=False))
payload_files = sorted(path for path in (QUEUE / 'payload').rglob('*') if path.is_file())
payload_rows = [dict(file=str(path.relative_to(QUEUE)), **info(path)) for path in payload_files]
save(QUEUE / 'payload-SHA256SUMS', ''.join(f'{row["sha256"]}  {row["file"]}\n' for row in payload_rows))
freeze_rows = [dict(file=str(path.relative_to(QUEUE)), **info(path)) for path in sorted(QUEUE.rglob('*')) if path.is_file()]
save(QUEUE / 'queue-freeze.json', dict(schema_version=1, frozen_at_utc=datetime.now(timezone.utc).isoformat(),
     original_png_count=223, original_emulator_png_count=154, original_jvm_snapshot_count=69,
     supplemental_original_count_contribution=0, files=freeze_rows, file_count=len(freeze_rows),
     total_bytes=sum(row['bytes'] for row in freeze_rows), source_receipts=source_receipts,
     staged_only=True, shared_gallery_modified=False, git_performed=False, duplicate_audits_or_tests=0))
for path in QUEUE.rglob('*'):
    if path.is_file():
        path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
print(json.dumps(dict(queue=str(QUEUE), originals=223, emulator_originals=154, jvm_originals=69,
     payload_files=len(payload_rows), payload_bytes=sum(row['bytes'] for row in payload_rows),
     freeze=info(QUEUE / 'queue-freeze.json'), manifest=info(QUEUE / 'publication-manifest.json'))))
