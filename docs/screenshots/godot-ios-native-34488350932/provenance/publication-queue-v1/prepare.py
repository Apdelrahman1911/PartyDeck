"""Stage original iOS captures using frozen owner mappings; no new evidence audit."""

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
NATIVE = ROOT / 'artifacts/evidence-storage/34488350932'
PRODUCTION = ROOT / 'artifacts/evidence-storage/ios-validate-34496252392'
CN = 'godot-ios-native-34488350932'
CP = 'ios-34496252392'
NATIVE_HEAD = '4f694296b08899176831e7c444c6f8082d40d64b'
PRODUCTION_HEAD = '410c9386dd88b2ad0ab380e5b8f1f9bf19674b00'
NATIVE_MAP = 'external-supplements/gallery-source-map-v1/mapping.json'
PRODUCTION_MAP = 'retained-original-capture-mapping.json'
INPUTS = [
    (NATIVE, 'collection-evidence-frozen.json', 'e3b9fa16fffd1370aacb6c23b4f750f9e9f22d0b4a7db8cedc0b272e629dfe0c'),
    (NATIVE, 'collection-evidence-summary.json', 'a2b732c42fa264b2ed4436f764fdb5390c430304ddf7eb8c5b43aae768bc3136'),
    (NATIVE, NATIVE_MAP, '65ab98a558e5bdfb9c84af6a28f8f5496283e1c8a9bf3194a786d778a3af9f90'),
    (NATIVE, 'external-supplements/gallery-source-map-v1/receipt.json', 'e43182b6b4dbb32d01502243d0d1e99dca51cad62c0bf5c3a1074f4784e7e454'),
    (PRODUCTION, PRODUCTION_MAP, '1e8ea2317cddda349e36a624ec4f5fb74b6db90d1d4d6f8d2c28e1b1089706fe'),
    (PRODUCTION, 'collection-complete.json', '15ef59e3fbf07b598dc0a50e93b9777ba7cc3048d3777951cd69c0a1dfdfa227'),
    (PRODUCTION, 'viewed-images.json', '8dd76928ffddd13713383c3eefb7fcdb88fef8b210f723ffc7afb9db474d0514'),
    (PRODUCTION, 'ordinary-native-layout-scope.json', '6cf1f5b40ff0bf6d5dbcc3bf1803a1809c94fa4fc9c567dfd9ff3da71f2f050a'),
    (PRODUCTION, 'ordinary-xctest-results.json', 'd7f58dd6406c6d48b626584bfe34b1298c1141912c9c629350380cdeaa5b1273'),
    (PRODUCTION, 'live-errors/standard-audit-attachments/receipt.json', 'acdc30645de1bdbe4b4d47ffe3ca0a24be26fab0ec0159cc6ff55b16948963aa'),
]
VISUAL_INPUTS = [
    (Path('/tmp/partydeck-gallery-after-2013-native-visual-review.json'), CN,
     'native-visual-review.json', '644800f9e8c3e54cd1f7d51fd712783feff969a490c25cc2eceedccd54494d8a'),
    (Path('/tmp/partydeck-gallery-after-2013-ios-production-observations.json'), CP,
     'review-design-visual-observations.json', 'd0eea8cf0675ba53a2729186c8206d7632f9014146e1a7308df09002313799dd'),
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
    source = base / relative
    actual = info(source)
    assert actual['sha256'] == digest, relative
    source_receipts.append(dict(source=str(source), **actual))
    receipt_index[str(source)] = actual
for source, collection, filename, digest in VISUAL_INPUTS:
    actual = info(source)
    assert actual['sha256'] == digest, str(source)
    source_receipts.append(dict(source=str(source), **actual))
    receipt_index[str(source)] = actual

native = load(NATIVE / NATIVE_MAP)
native_summary = load(NATIVE / 'collection-evidence-summary.json')
production = load(PRODUCTION / PRODUCTION_MAP)
production_tests = load(PRODUCTION / 'ordinary-xctest-results.json')
viewed = load(PRODUCTION / 'viewed-images.json')
scope = load(PRODUCTION / 'ordinary-native-layout-scope.json')
native_visual = load(VISUAL_INPUTS[0][0])
native_visual_index = {row['source_original']: row for row in native_visual['captures']}
production_visual = {row['original_filename']: row for row in load(VISUAL_INPUTS[1][0])}
assert native['runId'] == 34488350932 and native['headSha'] == native_summary['headSha'] == NATIVE_HEAD
assert native['counts'] == dict(attachments=502, retainedScreenshots=28, authorityScreenshots=45, screenshots=73, companionPayloads=429)
assert native['nativeOutcome'] == dict(authorityPassed=5, retainedPassed=2, retainedFailed=1, retainedSuiteQualified=False)
assert production['runId'] == 34496252392 and production['headSha'] == PRODUCTION_HEAD
assert production['captureReferences'] == 10 and production['uniqueCapturePayloads'] == 8
assert production['unmappedPngPayloads'] == [] and production_tests['passed'] == 8 and production_tests['failed'] == 1
assert scope['actualUnguardedNativeLayoutTestsPassed'] == 3
assert scope['guardedQualificationGeometryAssertionsExecuted'] is False
assert scope['separateNativeLayoutGateQualified'] is False and scope['productionGodotSessionsExecuted'] is False
assert native_visual['original_capture_count'] == 73 and native_visual['direct_original_views'] == 64
assert native_visual['same_batch_exact_bytes_reuse'] == 9 and native_visual['derived_image_count'] == 0
assert native_visual['source_revision'] == NATIVE_HEAD and len(native_visual_index) == 73

copies, screenshots, evidence, generated_provenance = [], [], [], []
destinations = set()


def copy_original(source, base, target, collection, expected, kind='original_evidence', **context):
    source = Path(source)
    destination = PAYLOAD / target
    assert source.resolve().is_relative_to(base.resolve()) and not source.is_symlink()
    assert destination.resolve().is_relative_to(PAYLOAD) and target not in destinations
    actual = info(source)
    assert actual['sha256'] == expected['sha256'], str(source)
    assert actual['bytes'] == expected.get('bytes', actual['bytes']), str(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    assert not destination.exists()
    shutil.copy2(source, destination)
    assert info(destination) == actual, target
    destinations.add(target)
    copied = dict(source=str(source), canonical_source=str(source.resolve()), staged=str(destination),
                  destination='docs/screenshots/' + target, gallery_path=target, collection=collection,
                  artifact_type=kind, **actual)
    copies.append(copied)
    if kind != 'original_app_capture':
        evidence.append(dict(path=target, original_filename=source.name, source_original=str(source),
                             collection=collection, artifact_type=kind, **actual, **context))
    return copied


def generated_index(target, value, collection, inputs):
    save(PAYLOAD / target, value)
    generated_provenance.append(target)
    evidence.append(dict(path=target, original_filename=None, source_original=None, collection=collection,
                         artifact_type='publication_metadata_index', generated_from=inputs,
                         original_png_count_contribution=0, **info(PAYLOAD / target)))


def add_image(copied, width, height, revision, run, scenario, platform, notes, **context):
    raw = (PAYLOAD / copied['gallery_path']).read_bytes()
    assert raw[:8] == b'\x89PNG\r\n\x1a\n' and raw[12:16] == b'IHDR'
    assert struct.unpack('>II', raw[16:24]) == (width, height)
    row = dict(id=copied['gallery_path'].removesuffix('.png'), collection=copied['collection'],
               path=copied['gallery_path'], original_filename=Path(copied['gallery_path']).name,
               scenario=scenario, platform=platform, artifact_type='native_simulator_capture',
               width_px=width, height_px=height, bytes=copied['bytes'], sha256=copied['sha256'],
               source_original=copied['source'], source_revision=revision, source_revision_exact=True,
               ci_run=run, ci_run_attempt=1, publication_reaudited_evidence=False, notes=notes, **context)
    screenshots.append(row)
    return row


for base, relative, _ in INPUTS:
    collection = CN if base == NATIVE else CP
    tail = ('source-map/' + Path(relative).name) if relative.startswith('external-supplements/') else relative
    target = collection + '/provenance/' + tail
    copy_original(base / relative, base, target, collection, receipt_index[str(base / relative)], 'existing_owner_receipt')
for source, collection, filename, digest in VISUAL_INPUTS:
    copy_original(source, source.parent, collection + '/provenance/' + filename, collection,
                  receipt_index[str(source)], 'existing_owner_visual_review')

native_tests = {row['identifier']: row for row in native_summary['nativeTestResults']}
native_published = []
native_source_only = []
companion_scope = 'Associated by recorded test case, attachment name and timestamp only; no per-screenshot pairing is attested.'
native_limits = ('Retained lifecycle and same-process reentry remain unqualified after the stale-first-ready failure. '
                 'Five Authority Simulator fixture cases passed, including four reference full matches and secure launch/exit. '
                 'Secure-default full match, production KMP factory, physical sensors, device Metal and real audio interruption remain unqualified. '
                 'No clean-native-log or no-crash claim is made.')
for attachment in native['attachments']:
    host = attachment['host']
    collection = CN + '-' + host
    source = Path(attachment['path'])
    if source.suffix not in ('.png', '.json', '.txt'):
        assert attachment['kind'] == 'original_companion_payload' and source.suffix in ('.mp4', '')
        reference = dict(owner_record=attachment, path=None, exported_filename=source.name,
                         canonical_source=str(source.resolve()), association_scope=companion_scope,
                         published=False, original_png_count_contribution=0,
                         reason='Original video or synthesized-event payload retained at the exact source path; this images-and-text queue preserves its metadata reference only.')
        native_source_only.append(reference)
        native_published.append(reference)
        continue
    target = f'{CN}/{host}/attachments/{source.name}'
    original_image = attachment['kind'] == 'original_screenshot'
    copied = copy_original(source, NATIVE, target, collection, attachment,
                           'original_app_capture' if original_image else 'original_companion_payload',
                           original_attachment_name=attachment['name'], test_identifier=attachment['testIdentifier'],
                           recorded_timestamp=attachment['timestamp'], association_scope=companion_scope)
    native_published.append(dict(owner_record=attachment, path=target, exported_filename=source.name,
                                 canonical_source=str(source.resolve()), association_scope=companion_scope,
                                 published=True))
    if not original_image:
        continue
    visual = native_visual_index[attachment['path']]
    assert all(visual[key] == attachment[source_key] for key, source_key in (
        ('sha256', 'sha256'), ('bytes', 'bytes'), ('timestamp', 'timestamp'),
        ('test_identifier', 'testIdentifier'), ('attachment_original_name', 'name')))
    if not visual['actually_viewed_by_review_design']:
        matched = native_visual_index[visual['matched_direct_original']]
        assert matched['actually_viewed_by_review_design'] is True
        assert matched['sha256'] == visual['sha256'] and matched['bytes'] == visual['bytes']
    native_published[-1]['visual_review'] = visual
    test = native_tests[attachment['testIdentifier']]
    case_anchor = 'case-' + hashlib.sha256(attachment['testIdentifier'].encode()).hexdigest()[:12]
    notes = [f'Original native {host} host attachment; original XCTest case result: {test["result"]}.',
             companion_scope, native_limits]
    notes.extend(issue['compactDescription'] for issue in test.get('issues', []))
    notes.append(('Direct original visual observation: ' if visual['actually_viewed_by_review_design'] else
                  'Observation reused from a named byte-identical direct original; this capture was not directly viewed: ')
                 + visual['visual_observation'])
    label = re.sub(r'_\d+_[0-9A-Fa-f-]{36}\.png$', '', attachment['name'])
    font_scale = (2.0 if 'At200Percent' in attachment['testIdentifier'] else 1.0) if host == 'authority' else None
    add_image(copied, attachment['width'], attachment['height'], NATIVE_HEAD, '34488350932', label,
              f'iOS Simulator, native {host} fixture host', notes,
              source_aliases=[str(source.resolve())], original_attachment_name=attachment['name'],
              exported_filename=source.name, test_identifier=attachment['testIdentifier'],
              case_status='passed' if test['result'] == 'Success' else 'failed',
              recorded_timestamp=attachment['timestamp'],
              captured_utc=datetime.fromtimestamp(attachment['timestamp'], timezone.utc).isoformat(timespec='milliseconds'),
              font_scale=font_scale, synthetic_invitation_fixture=None, production_kmp_factory_qualified=False,
              existing_owner_visual_review=visual['actually_viewed_by_review_design'],
              visual_review_observers=['review_design'], visual_review_method=visual['review_method'],
              visual_review_receipt_path=f'{CN}/provenance/native-visual-review.json',
              visual_review_matched_original=visual.get('matched_direct_original'),
              visual_observation=visual['visual_observation'],
              paired_ui_path=None, capture_receipt_path=None,
              companion_index_path=f'{CN}/{host}/companions.md', companion_index_anchor=case_anchor,
              source_mapping_path=f'{CN}/provenance/source-map/mapping.json',
              publication_attachment_index_path=f'{CN}/provenance/published-attachment-index.json',
              original_result_path=f'{CN}/provenance/collection-evidence-summary.json',
              attachment=attachment, qualification=native_summary['qualification'])

generated_index(f'{CN}/provenance/published-attachment-index.json',
                dict(schema_version=1, run_id='34488350932', source_revision=NATIVE_HEAD,
                     source_mapping=str(NATIVE / NATIVE_MAP), association_scope=companion_scope,
                     original_png_count=73, original_companion_count=429,
                     staged_original_text_companions=426, source_only_companion_references=3,
                     attachments=native_published), CN,
                [str(NATIVE / NATIVE_MAP)])

for host in ('retained', 'authority'):
    start = f'{CN}/{host}'
    rows = [row for row in native_published if row['owner_record']['host'] == host]
    lines = [f'# Original {host} host companions', '', companion_scope, '',
             '[Original screenshots](README.md) · [Complete publication mapping](../provenance/published-attachment-index.json)', '']
    tests = sorted({row['owner_record']['testIdentifier'] for row in rows})
    for test in tests:
        anchor = 'case-' + hashlib.sha256(test.encode()).hexdigest()[:12]
        lines += [f'<a id="{anchor}"></a>', '', f'## {test}', '',
                  '| Original companion attachment | Recorded time (UTC) | Exported file and SHA-256 |', '| --- | --- | --- |']
        companions = sorted((row for row in rows if row['owner_record']['testIdentifier'] == test and
                             row['owner_record']['kind'] == 'original_companion_payload'),
                            key=lambda row: (row['owner_record']['timestamp'], row['owner_record']['name']))
        for row in companions:
            owner = row['owner_record']
            when = datetime.fromtimestamp(owner['timestamp'], timezone.utc).isoformat(timespec='milliseconds')
            attachment_link = (f'[{html.escape(owner["name"])}]({href(row["path"], start)})' if row['published'] else
                               f'{html.escape(owner["name"])} — source-only reference; [original mapping](../provenance/source-map/mapping.json)')
            lines.append(f'| {attachment_link} | {when} | '
                         f'<code>{row["exported_filename"]}</code><br><code>{owner["sha256"]}</code> |')
        lines.append('')
    save(PAYLOAD / start / 'companions.md', '\n'.join(lines) + '\n')

production_viewed = {row['originalFilename']: row for row in viewed['viewedOriginals']}
production_status = {row['identifier']: row['status'] for row in production_tests['tests']}
production_images = [row for row in production['captures'] if row['uniformTypeIdentifier'] == 'public.png']
videos = [dict(owner_record=row, published=False, original_png_count_contribution=0,
               reason='Images-only publication queue; original video reference and hash retained without derived frames.')
          for row in production['captures'] if row['uniformTypeIdentifier'] == 'public.mpeg-4']
assert len(production_images) == 9 and len({row['filename'] for row in production_images}) == 9
assert len({row['sha256'] for row in production_images}) == 7 and len(videos) == 1
production_published = []
production_limits = ('Ordinary Standard unfiltered .all accessibility audit failed: “Hit area is too small.” '
                     'Six ordinary unit tests passed, including three real UIKit tests; UI tests had two passes and one failure. '
                     'Guarded qualification geometry assertions, the separate layout gate/checker and both real Godot production sessions did not execute.')
for capture in sorted(production_images, key=lambda row: (row['timestamp'], row['filename'])):
    source = Path(capture['payloadPath'])
    target = CP + '/attachments/' + capture['filename']
    copied = copy_original(source, PRODUCTION, target, CP, capture, 'original_app_capture')
    matching_view = production_viewed.get(capture['filename'])
    aliases = []
    if matching_view:
        assert matching_view['sha256'] == capture['sha256'] and matching_view['bytes'] == capture['bytes']
        assert matching_view['originalXctestPayloadId'] == capture['payloadId']
        assert info(Path(matching_view['path'])) == {key: capture[key] for key in ('bytes', 'sha256')}
        assert production_visual[capture['filename']]['sha256'] == capture['sha256']
        aliases.append(matching_view['path'])
    shared = [other['filename'] for other in production_images if other['payloadId'] == capture['payloadId'] and other['filename'] != capture['filename']]
    notes = [production_limits, 'Recorded names identify capture stages; this publication preparation adds no native or visual qualification.']
    if shared:
        notes.append('This is a distinct recorded capture event with its own original filename and timestamp, even though XCTest reused its content-addressed payload.')
    if capture['name'] == 'App Screenshot':
        notes.append('Existing direct review: three selected cards with visible badges, readable feedback, and complete Play 3 cards / Challenge Orbit controls.')
    if capture['name'] == 'Element Screenshot':
        notes.append('Original XCTest element attachment showing “Choose up to 3 cards”; not an agent crop or derivative. The 416 × 56 pixel extent at 3× scale is not an exported exact accessibility rectangle.')
    row = add_image(copied, capture['pixels']['width'], capture['pixels']['height'], PRODUCTION_HEAD, '34496252392',
                    capture['name'], 'iOS Simulator, ordinary production Compose app host', notes,
                    source_aliases=aliases, original_attachment_name=capture['filename'],
                    recorded_attachment_name=capture['name'], test_identifier=capture['test'],
                    case_status='passed' if production_status[capture['test']] == 'Success' else 'failed',
                    captured_utc=capture['timestamp'], font_scale=None, synthetic_invitation_fixture=False,
                    existing_owner_visual_review=bool(matching_view),
                    visual_review_observers=['ios_platform', 'review_design'] if matching_view else [],
                    visual_review_receipt_path=CP + '/provenance/viewed-images.json' if matching_view else None,
                    visual_review_design_receipt_path=CP + '/provenance/review-design-visual-observations.json' if matching_view else None,
                    paired_ui_path=None, capture_receipt_path=None,
                    source_mapping_path=CP + '/provenance/' + PRODUCTION_MAP,
                    publication_attachment_index_path=CP + '/provenance/published-capture-index.json',
                    original_result_path=CP + '/provenance/ordinary-xctest-results.json',
                    qualification_scope_path=CP + '/provenance/ordinary-native-layout-scope.json',
                    duplicate_payload_distinct_capture_names=shared, xcresult_payload_id=capture['payloadId'],
                    attachment=capture, production_godot_sessions_executed=False,
                    guarded_qualification_geometry_assertions_executed=False,
                    actual_unguarded_native_layout_tests_passed=3)
    production_published.append(dict(owner_record=capture, path=target, source_aliases=aliases,
                                      existing_owner_visual_review=bool(matching_view),
                                      duplicate_payload_distinct_capture_names=shared))

generated_index(CP + '/provenance/published-capture-index.json',
                dict(schema_version=1, run_id='34496252392', source_revision=PRODUCTION_HEAD,
                     original_png_count=9, unique_png_payloads=7, original_capture_events=production_published,
                     retained_video_references=videos, aliases_count_as_additional_originals=False,
                     identity_policy='Preserve distinct recorded original filenames and timestamps; do not deduplicate capture events by payload hash.',
                     qualification_limits=production_limits), CP, [str(PRODUCTION / PRODUCTION_MAP), str(PRODUCTION / 'viewed-images.json')])

collections = [
    dict(id=CN + '-retained', path=CN + '/retained', count=28, title='iOS retained native host — two passes, one failed wait',
         platform='iOS Simulator, native retained fixture host', kind='native_simulator_fixture_capture', tier='native_current',
         revision=NATIVE_HEAD, source_revision_exact=True, ci_run='34488350932', workflow_conclusion='failure',
         status='Active/dormant background and repeated 2D/3D cases passed; stale-first-ready/close-completion reentry failed its renderer-diagnostics wait. The retained suite remains unqualified.',
         text='28 original PNGs and 65 original JSON/TXT companions are staged. Three additional companion identities (one MP4 and two synthesized-event payloads) are source-only references. Original exported UUID filenames, attachment names, case identities and times are preserved.'),
    dict(id=CN + '-authority', path=CN + '/authority', count=45, title='iOS Authority native host — five Simulator fixture passes',
         platform='iOS Simulator, native Authority fixture host', kind='native_simulator_fixture_capture', tier='native_current',
         revision=NATIVE_HEAD, source_revision_exact=True, ci_run='34488350932', workflow_conclusion='failure',
         status='Five Authority Simulator fixture cases passed: four reference full matches and secure launch/renderer exit. Secure-default full match and production KMP factory integration remain unqualified.',
         text='45 original PNGs and 361 original JSON/TXT companions. The overall run failed in the separate retained-host case; no new pixel review is claimed by publication preparation.'),
    dict(id=CP, path=CP, count=9, title='iOS ordinary production app — Standard accessibility failure',
         platform='iOS Simulator, ordinary production Compose app host', kind='native_simulator_capture', tier='native_current',
         revision=PRODUCTION_HEAD, source_revision_exact=True, ci_run='34496252392', workflow_conclusion='failure',
         status=production_limits,
         text='Nine original PNG capture identities across seven payloads. Distinct original filenames and times are retained even when XCTest reused bytes. The two original failure attachments were directly viewed. One retained MP4 is referenced in provenance only; no frames or derivatives are added.'),
]

for collection in collections:
    start = collection['path']
    lines = [f'# {collection["title"]}', '', f'[All collections]({href("README.md", start)}) · '
             f'[Original CI run](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/{collection["ci_run"]})', '',
             collection['status'], '', collection['text'], '', f'Exact source: `{collection["revision"]}`.', '']
    if collection['ci_run'] == '34488350932':
        lines += [native_limits, '', 'The separate visual-review receipt lists 64 directly viewed originals across both native hosts and nine named exact-byte matches to those originals. All 73 capture identities remain distinct. Publication performs no new image views.', '',
                  '[Original companions by case and time](companions.md) · [Frozen owner summary](../provenance/collection-evidence-summary.json) · [Original visual-review receipt](../provenance/native-visual-review.json)', '']
    else:
        lines += ['[Original capture mapping](provenance/retained-original-capture-mapping.json) · '
                  '[Actual ordinary XCTest results](provenance/ordinary-xctest-results.json) · '
                  '[Qualification scope](provenance/ordinary-native-layout-scope.json) · [Viewed originals](provenance/viewed-images.json)', '']
    lines += ['| Original capture | Recorded identity and evidence scope |', '| --- | --- |']
    for row in screenshots:
        if row['collection'] != collection['id']:
            continue
        relative = href(row['path'], start)
        caption = html.escape(row['scenario'])
        name = html.escape(row['original_attachment_name'])
        links = [f'[Owner mapping]({href(row["source_mapping_path"], start)})',
                 f'[Original case results]({href(row["original_result_path"], start)})']
        if row.get('companion_index_path'):
            links.append(f'[Case companions]({href(row["companion_index_path"], start)}#{row["companion_index_anchor"]})')
        notes = '<br>'.join(html.escape(note) for note in row['notes'])
        lines.append(f'| <a href="{relative}"><img src="{relative}" alt="{caption}" width="168"></a> | '
                     f'**{caption}**<br>[{name}]({relative})<br>Exported file: <code>{html.escape(row["original_filename"])}</code><br>'
                     f'{row["width_px"]} × {row["height_px"]} px · {row["captured_utc"]}<br>'
                     f'<code>{html.escape(row["test_identifier"])}</code> — {row["case_status"]}<br>'
                     f'SHA-256: <code>{row["sha256"]}</code><br>{" · ".join(links)}<br>{notes} |')
    save(PAYLOAD / start / 'README.md', '\n'.join(lines) + '\n')

save(PAYLOAD / CN / 'README.md', '# iOS native hosts — CI 34488350932\n\n'
     + native_limits + '\n\nExact source: `' + NATIVE_HEAD + '`. Renderer pack SHA-256: `'
     + native_summary['rendererPackSha256'] + '`.\n\n'
     '| Collection | Original PNGs | Staged text companions | Outcome |\n| --- | ---: | ---: | --- |\n'
     '| [Retained native host](retained/README.md) | 28 | 65 | Two cases passed; stale-first-ready/close-completion reentry failed. Three additional companions are indexed as source-only references. |\n'
     '| [Authority native host](authority/README.md) | 45 | 361 | Five original Simulator fixture cases passed. |\n\n'
     '[Frozen owner summary](provenance/collection-evidence-summary.json) · [Original owner mapping](provenance/source-map/mapping.json) · '
     '[Publication attachment index](provenance/published-attachment-index.json). Companions retain their recorded case/name/time associations; no one-to-one screenshot pairing is invented.\n')

assert len(screenshots) == 82 and len({row['path'] for row in screenshots}) == 82
assert sum(c['count'] for c in collections) == 82
assert sum(row['artifact_type'] == 'original_companion_payload' for row in evidence) == 426
assert len(native_source_only) == 3 and sum(Path(row['owner_record']['path']).suffix == '.mp4' for row in native_source_only) == 1
assert sum(row['existing_owner_visual_review'] is True for row in screenshots) == 66
generated_pages = [str(path.relative_to(PAYLOAD)) for path in sorted(PAYLOAD.rglob('*.md'))]
manifest = dict(schema_version=1, preparation_scope='Publication copy preparation from frozen owner projections only; no builds, native execution, source audit, downloads, image views or derivatives.',
                publication_state='Staged outside the live gallery for review_design; root owns Git.',
                original_png_count=82, original_companion_payload_count=429, supplemental_review_sheet_count=0,
                staged_original_companion_payload_count=426, source_only_original_companion_count=3,
                supplemental_original_count_contribution=0, source_receipts=source_receipts,
                collections=collections, screenshots=screenshots, evidence=evidence, supplemental=[],
                referenced_original_videos=videos + [row for row in native_source_only if Path(row['owner_record']['path']).suffix == '.mp4'],
                source_only_original_companion_references=native_source_only, copy_plan=copies,
                generated_gallery_pages=generated_pages, generated_provenance=generated_provenance)
save(QUEUE / 'publication-manifest.json', manifest)
save(QUEUE / 'copy-paths.tsv', 'sha256\tbytes\tsource\tstaged\tdestination\n' + ''.join(
    f'{row["sha256"]}\t{row["bytes"]}\t{row["source"]}\t{row["staged"]}\t{row["destination"]}\n' for row in copies))
save(QUEUE / 'gallery-index-rows.md', '| Proposed collection | Original PNGs | Evidence scope |\n| --- | ---: | --- |\n' + ''.join(
    f'| [{c["title"]}]({c["path"]}/README.md) | {c["count"]} | {c["status"]} |\n' for c in collections))
save(QUEUE / 'HANDOFF.md', '# iOS screenshot publication queue\n\n'
     'Copy both roots in `payload/docs/screenshots/` into the gallery: `godot-ios-native-34488350932` and `ios-34496252392`. '
     'Merge this queue’s three collection records, 82 original screenshot records, evidence records and index rows through review_design’s gallery workflow. '
     'The shared manifest and README must receive these fragments rather than being replaced. Root owns Git.\n\n'
     'The queue preserves all 73 native-host originals and 426 original JSON/TXT companions. All 429 companion identities are indexed; one MP4 and two synthesized-event payloads retain explicit source-only references. '
     'Companions are grouped by their recorded case/name/time without invented per-image pairing. '
     'Both the exported UUID basenames and recorded original attachment names are retained. The separate finalized native visual-review receipt preserves 64 direct original views and nine named byte-identical matches. Those nine remain distinct captures and are not marked directly viewed.\n\n'
     'Production preserves nine original PNG capture identities across seven payloads. Shared payload hashes never collapse distinct filenames/timestamps. '
     'The recovered App Screenshot and Element Screenshot copies are aliases of those two exact recorded originals, not two extra originals. '
     'The original XCTest Element Screenshot is not an agent crop. The MP4 is referenced with its exact source identity/hash; no video or derived frame is staged.\n\n'
     + native_limits + '\n\n' + production_limits + '\n\n'
     'Original byte hashes and PNG dimensions are checked against the frozen mappings. URL-encoded filenames and staged metadata links are checked. '
     'Only images and provenance are copied; no source, APK, PCK, ZIP, native execution, duplicate evidence audit or Git operation is performed. '
     'See `copy-paths.tsv`, `validation-report.json`, `payload-SHA256SUMS` and `queue-freeze.json`.\n')

link_count = 0
for relative in generated_pages:
    page = PAYLOAD / relative
    content = page.read_text()
    links = re.findall(r'(?:href|src)="([^"]+)"', content) + re.findall(r'\]\(([^)\n]+)\)', content)
    for link in links:
        parsed = urlsplit(html.unescape(link))
        if parsed.scheme or parsed.netloc:
            continue
        target = (page.parent / unquote(parsed.path)).resolve() if parsed.path else page
        if not target.exists():
            gallery_relative = target.relative_to(PAYLOAD)
            assert gallery_relative.as_posix() == 'README.md' and (ROOT / 'docs/screenshots' / gallery_relative).is_file(), (relative, link)
        elif parsed.fragment:
            assert f'id="{unquote(parsed.fragment)}"' in target.read_text(), (relative, link)
        link_count += 1

metadata_links = 0
for row in screenshots + evidence:
    for key in ('path', 'companion_index_path', 'source_mapping_path', 'publication_attachment_index_path',
                'original_result_path', 'visual_review_receipt_path', 'visual_review_design_receipt_path', 'qualification_scope_path'):
        if row.get(key):
            assert (PAYLOAD / row[key]).is_file(), (key, row[key])
            metadata_links += 1
for receipt in source_receipts:
    assert info(Path(receipt['source'])) == {key: receipt[key] for key in ('bytes', 'sha256')}
save(QUEUE / 'validation-report.json', dict(original_pngs=82, native_originals=73, production_originals=9,
     production_unique_png_payloads=7, original_native_companions=429,
     staged_original_native_text_companions=426, source_only_native_companion_references=3,
     source_and_staged_hash_checks=len(copies), png_header_dimension_checks=82,
     checked_page_links=link_count, checked_metadata_links=metadata_links,
     preserved_native_direct_views=64, preserved_native_exact_byte_review_matches=9,
     preserved_viewed_original_aliases=2, source_receipts_unchanged=True,
     new_image_views=0, generated_image_or_video_frames=0, repeated_evidence_audits=0,
     publication_integrity_only=True, shared_gallery_modified=False))

payload_files = sorted(path for path in (QUEUE / 'payload').rglob('*') if path.is_file())
payload_rows = [dict(file=str(path.relative_to(QUEUE)), **info(path)) for path in payload_files]
save(QUEUE / 'payload-SHA256SUMS', ''.join(f'{row["sha256"]}  {row["file"]}\n' for row in payload_rows))
freeze_rows = [dict(file=str(path.relative_to(QUEUE)), **info(path)) for path in sorted(QUEUE.rglob('*')) if path.is_file()]
save(QUEUE / 'queue-freeze.json', dict(schema_version=1, frozen_at_utc=datetime.now(timezone.utc).isoformat(),
     original_png_count=82, native_original_png_count=73, production_original_png_count=9,
     original_native_companion_count=429, staged_original_native_text_companions=426,
     source_only_native_companion_references=3, supplemental_original_count_contribution=0,
     files=freeze_rows, file_count=len(freeze_rows), total_bytes=sum(row['bytes'] for row in freeze_rows),
     source_receipts=source_receipts, staged_only=True, shared_gallery_modified=False,
     git_performed=False, duplicate_audits_or_tests=0))
for path in QUEUE.rglob('*'):
    if path.is_file():
        path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
print(json.dumps(dict(queue=str(QUEUE), originals=82, original_native_companions=429,
     staged_original_native_text_companions=426, source_only_native_companion_references=3,
     payload_files=len(payload_rows), payload_bytes=sum(row['bytes'] for row in payload_rows),
     freeze=info(QUEUE / 'queue-freeze.json'), manifest=info(QUEUE / 'publication-manifest.json'))))
