"""Preserve the 37 local GameplayLayout originals and existing owner receipts."""

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
import xml.etree.ElementTree as ET


ROOT = Path('/root/projects/PartyDeck')
QUEUE = Path(__file__).resolve().parent
PAYLOAD = QUEUE / 'payload/docs/screenshots'
SOURCE = ROOT / 'artifacts/evidence-storage/android-jni-standard-root-validation-20260910'
COLLECTION = 'compose-gameplay-layout-20260910-root-validation'
VISUAL = Path('/tmp/partydeck-gallery-after-2013-local-visual-review.json')
INPUTS = [
    (SOURCE / 'ui-snapshots.json', 'ui-snapshots.json', 'b1003a703b9c84ae461635de26700a8ec9773aec39c0e140861a0127893131f0'),
    (SOURCE / 'receipt.json', 'build-receipt.json', '33eb888166363015ec34b87873e7294bb823c42de5a21eb661ad4703b9c877d8'),
    (SOURCE / 'TEST-dev.partydeck.app.GameplayLayoutTest.xml', 'TEST-dev.partydeck.app.GameplayLayoutTest.xml', '03b7b9f51cb5857e7ea1617a93fdfcf95a6f214e86a1809706b7b2e105668ef5'),
    (VISUAL, 'visual-review.json', '21f01e2c4df434059e12b79971b89c20d39f9a2e874644956e880a8b9fc2a4f3'),
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


assert not PAYLOAD.exists() and not (QUEUE / 'queue-freeze.json').exists()
assert not (ROOT / 'docs/screenshots' / COLLECTION).exists()
source_receipts = []
for source, filename, digest in INPUTS:
    actual = info(source)
    assert actual['sha256'] == digest, str(source)
    source_receipts.append(dict(source=str(source), **actual))
mapping = load(SOURCE / 'ui-snapshots.json')
build = load(SOURCE / 'receipt.json')
visual = load(VISUAL)
report = ET.fromstring((SOURCE / 'TEST-dev.partydeck.app.GameplayLayoutTest.xml').read_bytes())
assert len(mapping['images']) == 37 and len({row['path'] for row in mapping['images']}) == 37
assert mapping['build_receipt_sha256'] == INPUTS[1][2] and build['exit_code'] == 0
assert build['native_execution'] is False
assert report.attrib['tests'] == '7' and all(report.attrib[key] == '0' for key in ('skipped', 'failures', 'errors'))
assert len(report.findall('testcase')) == 7
assert visual['original_capture_count'] == 37 and visual['direct_original_views'] == 1
assert visual['review_methods'] == {'published_exact_bytes': 36, 'direct_original': 1}
assert visual['source_mapping_sha256'] == INPUTS[0][2] and visual['source_files'] == mapping['source_files']
assert visual['build_receipt_sha256'] == INPUTS[1][2] and visual['derived_image_count'] == 0
visual_index = {row['source_original']: row for row in visual['captures']}
copies, screenshots, evidence = [], [], []
destinations = set()


def copy_original(source, target, expected, kind):
    destination = PAYLOAD / target
    assert source.is_file() and not source.is_symlink()
    assert source.resolve().is_relative_to(SOURCE) or source == VISUAL
    assert destination.resolve().is_relative_to(PAYLOAD) and target not in destinations
    actual = info(source)
    assert actual['sha256'] == expected['sha256'] and actual['bytes'] == expected.get('bytes', actual['bytes']), str(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    assert not destination.exists()
    shutil.copy2(source, destination)
    assert info(destination) == actual, target
    destinations.add(target)
    copied = dict(source=str(source), staged=str(destination), destination='docs/screenshots/' + target,
                  gallery_path=target, collection=COLLECTION, artifact_type=kind, **actual)
    copies.append(copied)
    if kind != 'original_jvm_capture':
        evidence.append(dict(path=target, original_filename=source.name, source_original=str(source),
                             collection=COLLECTION, artifact_type=kind, **actual))
    return copied


for source, filename, digest in INPUTS:
    copy_original(source, COLLECTION + '/provenance/' + filename, {'sha256': digest}, 'existing_owner_receipt')

limits = ('Original Compose/Skia JVM layout-test evidence. The seven GameplayLayout tests passed; no native device, '
          'real Godot renderer, iOS accessibility audit, TalkBack or performance qualification is supplied by this batch.')
revision_note = 'Recorded local source-file hashes and the build receipt identify this capture batch; no whole-tree capture commit is asserted.'
for original in mapping['images']:
    source = Path(original['path'])
    viewed = visual_index[str(source)]
    assert viewed['source_mapping_record'] == original
    assert viewed['sha256'] == original['sha256'] and viewed['bytes'] == original['bytes']
    if viewed['review_method'] == 'published_exact_bytes':
        published = ROOT / 'docs/screenshots' / viewed['published_match']
        assert published.resolve().is_relative_to(ROOT / 'docs/screenshots')
        assert info(published) == {key: original[key] for key in ('bytes', 'sha256')}
    else:
        assert viewed['review_method'] == 'direct_original' and source.name == 'game-selection-limit.png'
    target = COLLECTION + '/' + source.name
    copied = copy_original(source, target, original, 'original_jvm_capture')
    raw = (PAYLOAD / target).read_bytes()
    assert raw[:8] == b'\x89PNG\r\n\x1a\n' and raw[12:16] == b'IHDR'
    width, height = struct.unpack('>II', raw[16:24])
    assert (width, height) == (viewed['width'], viewed['height'])
    direct = viewed['actually_viewed_by_review_design']
    notes = [limits, revision_note,
             'The original suite report associates these captures with the successful seven-case run; no additional per-image test-case pairing is invented.',
             ('Existing direct visual observation: ' if direct else
              'Existing exact-byte visual-review reuse; this capture remains a distinct original and was not directly viewed by review_design: ')
             + viewed['visual_observation']]
    screenshots.append(dict(id=target.removesuffix('.png'), collection=COLLECTION, path=target,
        original_filename=source.name, scenario=source.stem.removeprefix('game-').replace('-', ' ').capitalize(),
        platform='Compose/Skia JVM GameplayLayout tests', artifact_type='jvm_ui_fixture_capture',
        width_px=width, height_px=height, font_scale=None, bytes=copied['bytes'], sha256=copied['sha256'],
        source_original=str(source), source_aliases=[], original_emitter_path=original['source'],
        source_revision=None, source_revision_exact=False, source_revision_note=revision_note,
        source_files=mapping['source_files'], ci_run=None, captured_utc=None,
        collection_recorded_utc=mapping['utc'], test_execution_timestamp=report.attrib['timestamp'],
        collection_timestamp_is_capture_timestamp=False, synthetic_invitation_fixture=False,
        existing_owner_visual_review=direct, visual_review_observers=['review_design'] if direct else [],
        visual_review_method=viewed['review_method'], visual_observation=viewed['visual_observation'],
        visual_review_matched_published_path=viewed.get('published_match'),
        visual_review_receipt_path=COLLECTION + '/provenance/visual-review.json',
        source_mapping_path=COLLECTION + '/provenance/ui-snapshots.json',
        build_receipt_path=COLLECTION + '/provenance/build-receipt.json',
        original_result_path=COLLECTION + '/provenance/TEST-dev.partydeck.app.GameplayLayoutTest.xml',
        paired_ui_path=None, capture_receipt_path=None, test_suite=report.attrib['name'],
        case_status='passed_suite', publication_reaudited_evidence=False,
        native_execution=False, notes=notes))

collection = dict(id=COLLECTION, path=COLLECTION, count=37,
    title='Compose GameplayLayout — local selection-feedback validation',
    platform='Compose/Skia JVM GameplayLayout tests', kind='jvm_ui_fixture_capture', tier='fixture',
    revision=None, source_revision_exact=False, source_revision_note=revision_note,
    source_files=mapping['source_files'], ci_run=None, source_directory=str(SOURCE / 'ui-snapshots'),
    status='Seven JVM GameplayLayout cases passed with zero failures, errors or skips. Native accessibility and renderer qualification remain separate.',
    text='37 original PNGs. One original selection-limit capture was directly reviewed; 36 retain exact-byte links to prior published originals without losing their current capture identities.')
lines = ['# ' + collection['title'], '', '[All collections](../README.md)', '', collection['status'], '', collection['text'], '',
         limits, '', revision_note, '', '[Original screenshot inventory](provenance/ui-snapshots.json) · '
         '[Original build receipt](provenance/build-receipt.json) · [Original suite report](provenance/TEST-dev.partydeck.app.GameplayLayoutTest.xml) · '
         '[Existing visual-review receipt](provenance/visual-review.json)', '',
         '| Original capture | Scenario and evidence scope |', '| --- | --- |']
for row in screenshots:
    relative = quote(row['original_filename'], safe='/')
    caption = html.escape(row['scenario'])
    notes = '<br>'.join(html.escape(note) for note in row['notes'])
    lines.append(f'| <a href="{relative}"><img src="{relative}" alt="{caption}" width="168"></a> | '
                 f'**{caption}**<br>[{row["original_filename"]}]({relative}); {row["width_px"]} × {row["height_px"]} px<br>'
                 f'SHA-256: <code>{row["sha256"]}</code><br>{notes} |')
save(PAYLOAD / COLLECTION / 'README.md', '\n'.join(lines) + '\n')
assert len(screenshots) == 37 and sum(row['existing_owner_visual_review'] for row in screenshots) == 1
manifest = dict(schema_version=1, preparation_scope='Publication copies from existing local screenshot inventory, build/suite receipts and finalized visual review. No new builds, tests, app execution, image views or derivatives.',
    publication_state='Staged outside the gallery for review_design after the four authorized CI collections; root owns Git.',
    original_png_count=37, original_jvm_snapshot_count=37, supplemental_review_sheet_count=0,
    supplemental_original_count_contribution=0, source_revision=None, source_revision_exact=False,
    source_revision_note=revision_note, source_files=mapping['source_files'], source_receipts=source_receipts,
    collections=[collection], screenshots=screenshots, evidence=evidence, supplemental=[], copy_plan=copies,
    generated_gallery_pages=[COLLECTION + '/README.md'])
save(QUEUE / 'publication-manifest.json', manifest)
save(QUEUE / 'copy-paths.tsv', 'sha256\tbytes\tsource\tstaged\tdestination\n' + ''.join(
    f'{row["sha256"]}\t{row["bytes"]}\t{row["source"]}\t{row["staged"]}\t{row["destination"]}\n' for row in copies))
save(QUEUE / 'gallery-index-rows.md', '| Proposed collection | Original PNGs | Evidence scope |\n| --- | ---: | --- |\n'
     f'| [{collection["title"]}]({COLLECTION}/README.md) | 37 | Seven successful local JVM layout tests; exact source-file hashes recorded, no whole-tree commit or native qualification asserted. |\n')
save(QUEUE / 'HANDOFF.md', '# Local GameplayLayout screenshot queue\n\n'
     f'Copy `{COLLECTION}` from `payload/docs/screenshots/` into the gallery after the four authorized CI runs. '
     'Merge this fragment’s one collection, 37 original screenshots, four evidence records and index row through review_design’s gallery workflow; root owns Git.\n\n'
     'All 37 originals preserve their bytes, filenames, dimensions, archived source paths and recorded emitter paths. '
     'One original selection-limit capture has direct visual observations; 36 are exact-byte matches to named previously published originals. '
     'They remain separate captures and are not marked directly viewed or collapsed into older records. No image derivatives are added.\n\n'
     + revision_note + '\n\n' + limits + '\n\n'
     'The original snapshot inventory, build receipt, seven-case JUnit report and finalized visual-review receipt are staged unchanged. '
     'No APK, source file or build log is copied. The inventory creation time is not substituted for an unrecorded per-image capture timestamp. '
     'Source/staged hash checks, PNG dimensions, published reuse references and staged links are verified in `validation-report.json`; '
     '`copy-paths.tsv`, `payload-SHA256SUMS` and `queue-freeze.json` bind the queue. No gallery or Git edits were made.\n')

page = PAYLOAD / COLLECTION / 'README.md'
page_links = 0
for link in re.findall(r'(?:href|src)="([^"]+)"', page.read_text()) + re.findall(r'\]\(([^)\n]+)\)', page.read_text()):
    parsed = urlsplit(html.unescape(link))
    if parsed.scheme or parsed.netloc:
        continue
    target = (page.parent / unquote(parsed.path)).resolve()
    if not target.exists():
        assert target == PAYLOAD / 'README.md' and (ROOT / 'docs/screenshots/README.md').is_file(), link
    page_links += 1
metadata_links = 0
for row in screenshots + evidence:
    for key in ('path', 'source_mapping_path', 'build_receipt_path', 'original_result_path', 'visual_review_receipt_path'):
        if row.get(key):
            assert (PAYLOAD / row[key]).is_file(), (key, row[key])
            metadata_links += 1
for receipt in source_receipts:
    assert info(Path(receipt['source'])) == {key: receipt[key] for key in ('bytes', 'sha256')}
save(QUEUE / 'validation-report.json', dict(original_png_count=37, source_and_staged_hash_checks=41,
    png_header_dimension_checks=37, checked_published_byte_reuse_references=36,
    checked_page_links=page_links, checked_metadata_links=metadata_links,
    original_suite_tests=7, original_suite_failures=0, original_suite_errors=0, original_suite_skips=0,
    preserved_direct_visual_views=1, source_receipts_unchanged=True, asserted_whole_tree_revision=False,
    new_tests_or_builds=0, new_image_views=0, generated_image_or_video_frames=0, repeated_evidence_audits=0,
    publication_integrity_only=True, shared_gallery_modified=False))
payload_files = sorted(path for path in (QUEUE / 'payload').rglob('*') if path.is_file())
payload_rows = [dict(file=str(path.relative_to(QUEUE)), **info(path)) for path in payload_files]
save(QUEUE / 'payload-SHA256SUMS', ''.join(f'{row["sha256"]}  {row["file"]}\n' for row in payload_rows))
freeze_rows = [dict(file=str(path.relative_to(QUEUE)), **info(path)) for path in sorted(QUEUE.rglob('*')) if path.is_file()]
save(QUEUE / 'queue-freeze.json', dict(schema_version=1, frozen_at_utc=datetime.now(timezone.utc).isoformat(),
    original_png_count=37, original_jvm_snapshot_count=37, supplemental_original_count_contribution=0,
    source_revision=None, source_revision_exact=False, source_files=mapping['source_files'],
    files=freeze_rows, file_count=len(freeze_rows), total_bytes=sum(row['bytes'] for row in freeze_rows),
    source_receipts=source_receipts, staged_only=True, shared_gallery_modified=False,
    git_performed=False, duplicate_audits_or_tests=0))
for path in QUEUE.rglob('*'):
    if path.is_file():
        path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
print(json.dumps(dict(queue=str(QUEUE), originals=37, payload_files=len(payload_rows),
    payload_bytes=sum(row['bytes'] for row in payload_rows), freeze=info(QUEUE / 'queue-freeze.json'),
    manifest=info(QUEUE / 'publication-manifest.json'))))
