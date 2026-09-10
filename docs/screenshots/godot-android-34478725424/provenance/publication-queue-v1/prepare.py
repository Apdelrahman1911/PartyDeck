"""Stage the ten attested viewed originals using existing owner receipts only."""

from datetime import datetime, timezone
from pathlib import Path
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
ANDROID = ROOT / 'artifacts/evidence-storage/34478725424'
IOS = ROOT / 'artifacts/evidence-storage/ios-validate-34480503751'
ROOT_REVIEW = ROOT / 'artifacts/evidence-storage/comparison-34478725424-root-review'
CA = 'godot-android-34478725424'
CI = 'godot-ios-production-34480503751'
ANDROID_HEAD = 'c6ea1dd9f7966517fbee87a06b633d01c432c24d'
IOS_HEAD = '7012ba031a4129c81cd118206f727a46a1c846e4'
RECEIPTS = [
    (ANDROID, 'handoff.json', 'd270786a54a248a9a991516c3001ec5451062d53284ca40f35409c28e1ce5fbc'),
    (ANDROID, 'collection-manifest-v1.json', '75019cbea917f2f024d2545a7c56bda9f9c7df76a8d4c3f71c28f8bd6bc17d24'),
    (ANDROID, 'analysis/runtime-evidence-v1.json', 'a310c5fc1f1fae1ee96b6a1b324e7428c4837012bdbf242c6b3ceb888fe9ded9'),
    (ANDROID, 'analysis/recents-visual-observations-v1.json', '816d619e8a5dc995ec31f32237e2f3b6c4737daf23262f0ca0d7a507b411b329'),
    (ANDROID, 'analysis/three-d-visual-observations-v1.json', 'd8a7bfa752a541b4c8874ecd30ccce8b4f9b9efa2e91753b6600d38042c55b34'),
    (ANDROID, 'FINDINGS.md', '04c7d3f3bf97a054392a128aff64aaa356f8b297bf012437dbd94ade751ab629'),
    (ROOT_REVIEW, 'receipt.json', '8afede53f1b807d4ebe7bfbb6629849ca5c3730cfba480b7f99f842677a5ef19'),
    (IOS, 'verification/production-session-failure-review.json', '93c84147c267f89703c51c44b6ab618373f4a1635f08b6fef9796512f6bf9644'),
]


def load(path):
    return json.loads(path.read_bytes())


def info(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False) + '\n')


assert not PAYLOAD.exists() and not (QUEUE / 'queue-freeze.json').exists()
source_receipts = []
receipt_index = {}
for base, relative, digest in RECEIPTS:
    actual = info(base / relative)
    assert actual['sha256'] == digest, relative
    source_receipts.append(dict(source=str(base / relative), **actual))
    receipt_index[str(base / relative)] = actual

handoff = load(ANDROID / 'handoff.json')
android_index = {row['path']: row for row in load(ANDROID / 'collection-manifest-v1.json')['files']}
android_audit = load(ANDROID / 'analysis/runtime-evidence-v1.json')
root_review = load(ROOT_REVIEW / 'receipt.json')
ios_review = load(IOS / 'verification/production-session-failure-review.json')
assert handoff['sourceCommit'] == root_review['sourceCommit'] == ANDROID_HEAD
assert handoff['runId'] == root_review['runId'] == 34478725424
assert handoff['runConclusion'] == 'success' and root_review['passed'] is True
assert ios_review['head_sha'] == IOS_HEAD and ios_review['run_id'] == 34480503751
assert ios_review['run_attempt'] == 1
assert ios_review['runtime_acceptance'] is False and ios_review['shipping_promotion'] is False

copies, screenshots, evidence = [], [], []
destinations = set()


def copy_original(base, relative, target, collection, expected, kind='original_evidence'):
    source, destination = base / relative, PAYLOAD / target
    assert source.resolve().is_relative_to(base.resolve()) and not source.is_symlink()
    assert destination.resolve().is_relative_to(PAYLOAD) and target not in destinations
    actual = info(source)
    assert actual['sha256'] == expected['sha256'], relative
    assert actual['bytes'] == expected.get('bytes', actual['bytes']), relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    assert not destination.exists()
    shutil.copy2(source, destination)
    assert info(destination) == actual, target
    destinations.add(target)
    row = dict(source=str(source), staged=str(destination), destination='docs/screenshots/' + target,
               gallery_path=target, collection=collection, artifact_type=kind, **actual)
    copies.append(row)
    if kind != 'original_app_capture':
        evidence.append(dict(path=target, original_filename=source.name, source_original=str(source),
                             collection=collection, artifact_type=kind, **actual))
    return row


def copy_android(relative, target, kind='original_evidence'):
    expected = android_index.get(relative) or receipt_index[str(ANDROID / relative)]
    return copy_original(ANDROID, relative, target, CA, expected, kind)


def add_image(copied, revision, run, scenario, platform, notes, **extra):
    target = copied['gallery_path']
    raw = (PAYLOAD / target).read_bytes()
    assert raw[:8] == b'\x89PNG\r\n\x1a\n'
    width, height = struct.unpack('>II', raw[16:24])
    row = dict(id=target.removesuffix('.png'), collection=copied['collection'], path=target,
               original_filename=Path(target).name, scenario=scenario, platform=platform,
               artifact_type='native_emulator_capture' if run == '34478725424' else 'native_simulator_failed_session_capture',
               width_px=width, height_px=height, bytes=copied['bytes'], sha256=copied['sha256'],
               source_original=copied['source'], source_aliases=[], source_revision=revision,
               source_revision_exact=True, ci_run=run, ci_run_attempt=1, captured_utc=None,
               synthetic_invitation_fixture=False, existing_owner_visual_review=True,
               publication_reaudited_evidence=False, notes=notes, **extra)
    screenshots.append(row)


android_cases = {case['artifact']: case for case in android_audit['cases']}
case_result_paths = {}
for artifact, case in android_cases.items():
    prefix = CA + '/' + artifact
    for key, suffix in [('result', '/runtime/result.json'), ('packageInputs', '/package-inputs.json')]:
        original = case[key]
        assert android_index[original['path']]['sha256'] == original['sha256']
        copied = copy_android(original['path'], prefix + suffix)
        if key == 'result':
            case_result_paths[artifact] = copied['gallery_path']

android_visual_receipts = [
    ('analysis/recents-visual-observations-v1.json', 'originalImage'),
    ('analysis/three-d-visual-observations-v1.json', 'image'),
]
for relative, image_key in android_visual_receipts:
    visual = load(ANDROID / relative)
    for viewed in visual['images']:
        original = viewed[image_key]
        source_path = Path(original['path'])
        artifact = source_path.parts[1].split('-', 1)[1]
        case = android_cases[artifact]
        assert android_index[original['path']]['sha256'] == original['sha256']
        tail = source_path.relative_to('archives/' + source_path.parts[1] + '/attempt-01/extracted/android').as_posix()
        target = CA + '/' + artifact + '/' + tail
        copied = copy_android(original['path'], target, 'original_app_capture')
        ui_path = str(Path(target).with_suffix('.xml'))
        copy_android(str(source_path.with_suffix('.xml')), ui_path)
        capture_path = None
        sibling = source_path.with_suffix('.json').as_posix()
        if (ANDROID / sibling).is_file():
            assert sibling in android_index
            capture_path = str(Path(target).with_suffix('.json'))
            copy_android(sibling, capture_path)
        else:
            assert sibling not in android_index
        stage = source_path.stem
        title = {
            '06-recents-privacy': 'Recents privacy frame',
            '02-revealed': 'Revealed 3D hand',
            '07-resumed-concealed': 'Concealed 3D hand after resume',
        }[stage]
        notes = [viewed['observation'], visual['scope']]
        if stage == '06-recents-privacy':
            notes.append('The 2D and 3D originals at this font scale have identical bytes and retain their separate source identities. No same-name JSON was retained for this Recents frame.')
        add_image(copied, ANDROID_HEAD, '34478725424',
                  f'{case["mode"].upper()} — {title} — {int(float(case["fontScale"]) * 100)}% text',
                  f'Android API {case["device"]["sdk"]} emulator, debug comparison host', notes,
                  mode=case['mode'], font_scale=float(case['fontScale']), case_status='passed',
                  paired_ui_path=ui_path, capture_receipt_path=capture_path,
                  original_result_path=case_result_paths[artifact],
                  visual_review_receipt_path=CA + '/provenance/' + Path(relative).name,
                  visual_review_observer=visual['observer'], visual_observation=viewed['observation'],
                  artifact_name=artifact, artifact_id=case['artifactId'],
                  recorded_device=case['device'], recorded_display=case['display'])

for relative in ['handoff.json', 'analysis/runtime-evidence-v1.json', 'analysis/recents-visual-observations-v1.json',
                 'analysis/three-d-visual-observations-v1.json', 'FINDINGS.md']:
    copy_android(relative, CA + '/provenance/' + Path(relative).name, 'existing_owner_receipt')
copy_original(ROOT_REVIEW, 'receipt.json', CA + '/provenance/root-review/receipt.json', CA,
              receipt_index[str(ROOT_REVIEW / 'receipt.json')], 'existing_root_review')

summary_record = ios_review['xcresult_summary']
summary = load(Path(summary_record['path']))
device = summary['devicesAndConfigurations'][0]['device']
assert summary['result'] == 'Failed' and summary['failedTests'] == 2 and summary['passedTests'] == 0
ios_platform = f'{device["platform"]} {device["osVersion"]}, {device["deviceName"]} ({device["architecture"]}), production qualification host'
for viewed in ios_review['failure_observations']:
    original, observation = viewed['screenshot'], viewed['observation']
    png_source, json_source = Path(original['path']), Path(observation['path'])
    png_target, json_target = (CI + '/attachments/' + p.name for p in (png_source, json_source))
    copied = copy_original(IOS, png_source.relative_to(IOS).as_posix(), png_target, CI, original, 'original_app_capture')
    copy_original(IOS, json_source.relative_to(IOS).as_posix(), json_target, CI, observation)
    mode = viewed['controller_mode'].removeprefix('GODOT_')
    viewport = viewed['renderer_viewport']
    notes = [viewed['visual_inspection'],
             f'Original failed production {mode} smoke; stretched native status area and clipped renderer viewport, no production interaction pass.',
             f'Recorded renderer viewport {viewport["width"]} × {viewport["height"]}; the original observation preserves the native bounds and coordinate-space labels.',
             'The first actual assertion failed: Observe fresh, current production renderer diagnostics. Six baseline cases and package checks were verified separately; runtime acceptance and shipping promotion remain false.']
    add_image(copied, IOS_HEAD, '34480503751', f'Failed production {mode} smoke — clipped renderer viewport',
              ios_platform, notes, mode=mode.lower(), font_scale=None, case_status='failed',
              paired_ui_path=None, capture_receipt_path=json_target,
              capture_receipt_kind='paired_original_renderer_observation',
              original_result_path=CI + '/provenance/test-summary.json',
              visual_review_receipt_path=CI + '/provenance/production-session-failure-review.json',
              visual_review_observer='ios_platform', visual_observation=viewed['visual_inspection'],
              test_identifier=viewed['test_identifier'], observation_sequence=viewed['observation_sequence'],
              recorded_renderer_viewport=viewport, recorded_native_geometry=viewed['geometry'],
              recorded_device=device, runtime_acceptance=False, shipping_promotion=False)

copy_original(IOS, 'verification/production-session-failure-review.json', CI + '/provenance/production-session-failure-review.json', CI,
              receipt_index[str(IOS / 'verification/production-session-failure-review.json')], 'existing_owner_receipt')
for key in ['xcresult_summary', 'named_case_evidence_review']:
    original = ios_review[key]
    path = Path(original['path'])
    copy_original(IOS, path.relative_to(IOS).as_posix(), CI + '/provenance/' + path.name, CI, original, 'original_result_or_review')

collections = [
    dict(id=CA, path=CA, count=8, title='Android comparison — eight viewed originals',
         platform='Android API 35 emulator, debug comparison host', kind='native_emulator_comparison_capture',
         tier='native_current', revision=ANDROID_HEAD, source_revision_exact=True, ci_run='34478725424',
         workflow_conclusion='success',
         status='Existing root review accepted four API35 comparison cases and twelve exits; this collection publishes the eight directly viewed originals.',
         text='Four Recents originals and four 3D reveal/resume frames at 100% and 200% text. The run contains 48 scene captures; these receipts attest direct viewing of eight. Identical-byte Recents captures remain distinct by source. No desktop originals or derived images were viewed for this run.',
         qualification_limits=root_review['acceptedScope'],
         provenance_paths=[CA + '/provenance/' + name for name in ['handoff.json', 'runtime-evidence-v1.json',
                           'recents-visual-observations-v1.json', 'three-d-visual-observations-v1.json', 'FINDINGS.md', 'root-review/receipt.json']]),
    dict(id=CI, path=CI, count=2, title='iOS production — both session smokes failed',
         platform=ios_platform, kind='native_simulator_failed_session_capture', tier='native_current',
         revision=IOS_HEAD, source_revision_exact=True, ci_run='34480503751',
         status='Both production session tests failed. Host text and Standard/Leave buttons occupy almost all the screen; the Godot viewport is clipped to a strip along the bottom.',
         text='Two viewed original PNGs retain their paired UUID observation JSONs. Recorded renderer viewport: 402 × 26. Six baseline cases and package checks were verified separately; no production interaction pass, runtime acceptance or shipping promotion.',
         qualification_limits='Failure evidence only. The original observations do not prove a unique source root cause or continuous state throughout the wait.',
         provenance_paths=[CI + '/provenance/' + name for name in ['production-session-failure-review.json', 'test-summary.json', 'production-tests.json']]),
]

for collection in collections:
    path = collection['path']
    lines = [f'# {collection["title"]}', '',
             f'[All collections](../README.md) · [Original CI run](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/{collection["ci_run"]})', '',
             collection['status'], '', collection['text'], '',
             f'Exact source: `{collection["revision"]}`; run attempt 1. Original PNG and metadata bytes, filenames, source identities and review limits are preserved.', '',
             collection['qualification_limits'], '',
             'Existing provenance: ' + ' · '.join(f'[{Path(p).name}]({os.path.relpath(p, path)})' for p in collection['provenance_paths']) + '.', '',
             '| Original capture | Recorded observation and scope |', '| --- | --- |']
    for row in screenshots:
        if row['collection'] != collection['id']:
            continue
        relative = os.path.relpath(row['path'], path)
        caption = html.escape(row['scenario'])
        links = []
        for key, label in [('paired_ui_path', 'Original XML'), ('capture_receipt_path', 'Original observation'),
                           ('original_result_path', 'Original result'), ('visual_review_receipt_path', 'Existing visual review')]:
            if row.get(key):
                links.append(f'[{label}]({os.path.relpath(row[key], path)})')
        context = html.escape(row['platform'])
        if row['font_scale'] is not None:
            context += f'; text {row["font_scale"]}×'
        notes = '<br>'.join(html.escape(note) for note in row['notes'])
        lines.append(f'| <a href="{relative}"><img src="{relative}" alt="{caption}" width="168"></a> | **{caption}**<br>{context}<br>[{row["original_filename"]}]({relative}); {row["width_px"]} × {row["height_px"]} px<br>SHA-256: <code>{row["sha256"]}</code><br>{" · ".join(links)}<br>{notes} |')
    save(PAYLOAD / path / 'README.md', '\n'.join(lines) + '\n')

assert len(screenshots) == 10 and len({row['path'] for row in screenshots}) == 10
assert sum(row['paired_ui_path'] is not None for row in screenshots) == 8
assert sum(row['capture_receipt_path'] is not None for row in screenshots) == 6
assert len({row['source_original'] for row in screenshots}) == 10
assert sum(collection['count'] for collection in collections) == 10
for row in screenshots:
    for key in ['path', 'paired_ui_path', 'capture_receipt_path', 'original_result_path', 'visual_review_receipt_path']:
        if row.get(key):
            assert (PAYLOAD / row[key]).is_file(), row[key]
page_link_count = 0
for page in PAYLOAD.rglob('README.md'):
    content = page.read_text()
    links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', content) + re.findall(r'(?:href|src)="([^"]+)"', content)
    for link in links:
        if link.startswith(('https://', '#')):
            continue
        target = (page.parent / link).resolve()
        assert target.is_relative_to(PAYLOAD)
        if target == PAYLOAD / 'README.md':
            assert (ROOT / 'docs/screenshots/README.md').is_file()
        else:
            assert target.is_file(), (page, link)
        page_link_count += 1

manifest = dict(schema_version=1,
                preparation_scope='Publication copy preparation only. Existing owner audits and visual receipts reused; no new app runs, tests, downloads, image viewing or repeated evidence audits.',
                publication_state='Ready outside docs/screenshots for review_design integration; root owns Git.',
                source_revisions={'34478725424': ANDROID_HEAD, '34480503751': IOS_HEAD},
                original_png_count=10, original_png_xml_pairs=8, original_png_observation_json_pairs=6,
                standalone_original_pngs=0, supplemental_review_sheet_count=0, supplemental_original_count_contribution=0,
                viewed_scope_confirmation={'34478725424': 'review_game confirms these eight are the complete directly viewed set; no desktop originals or derivatives.',
                                           '34480503751': 'ios_platform confirms these two are the complete directly viewed set; no derivatives.'},
                collections=collections, screenshots=screenshots, evidence=evidence, supplemental=[],
                source_receipts=source_receipts, copy_plan=copies,
                generated_gallery_pages=[str(p.relative_to(PAYLOAD)) for p in sorted(PAYLOAD.rglob('README.md'))])
save(QUEUE / 'publication-manifest.json', manifest)
save(QUEUE / 'copy-paths.tsv', 'sha256\tbytes\tsource\tstaged\tdestination\n' + ''.join(f'{r["sha256"]}\t{r["bytes"]}\t{r["source"]}\t{r["staged"]}\t{r["destination"]}\n' for r in copies))
save(QUEUE / 'gallery-index-rows.md', '| Proposed collection | Original PNGs | Evidence scope |\n| --- | ---: | --- |\n' + ''.join(f'| [{c["title"]}]({c["path"]}/README.md) | {c["count"]} | {c["status"]} |\n' for c in collections))
save(QUEUE / 'HANDOFF.md', '# Remaining viewed-image publication queue\n\nReady for review_design integration; root owns Git. Copy the two new roots under `payload/docs/screenshots/`: `godot-android-34478725424` and `godot-ios-production-34480503751`. Merge the collection, screenshot and evidence records from `publication-manifest.json` plus `gallery-index-rows.md` into the existing gallery; these are fragments, not replacements for shared files.\n\nThe queue contains ten originals: eight Android PNG/XML pairs, four of which also have original same-name JSON observations, and two iOS PNGs with their paired original UUID observation JSONs. No derivatives. Both source owners confirm these are their complete directly viewed sets for these runs. The remaining 40 Android scene captures were hash/geometry inspected, not directly viewed under these receipts. Identical-byte Recents originals retain separate source records. The 200% 3D resumed caption preserves the clipped hand and does not imply five fully visible backs.\n\nAndroid comparison run 34478725424 is tied to `c6ea1dd9f7966517fbee87a06b633d01c432c24d`; existing root acceptance is limited to four API35 comparison cases and twelve exits. iOS production run 34480503751 is tied to `7012ba031a4129c81cd118206f727a46a1c846e4`; both session tests failed with the clipped viewport, and runtime acceptance/shipping promotion remain false. Recorded viewport 402 × 26 retains its original coordinate context without adding units.\n\nOriginal bytes, names, exact source paths, byte lengths and SHA-256 values are in `copy-paths.tsv`; collection pages retain the failure and qualification captions. `payload-SHA256SUMS` covers every staged payload file, and `queue-freeze.json` freezes this prepared queue. Copy checks and metadata-link checks passed. No builds, tests, native runs, downloads, source/APK re-audits, shared gallery edits or Git operations were performed. The earlier 90-original/four-sheet queue remains unchanged.\n')

payload_rows = [dict(file=str(p.relative_to(QUEUE)), **info(p)) for p in sorted((QUEUE / 'payload').rglob('*')) if p.is_file()]
save(QUEUE / 'payload-SHA256SUMS', ''.join(f'{r["sha256"]}  {r["file"]}\n' for r in payload_rows))
freeze_rows = [dict(file=str(p.relative_to(QUEUE)), **info(p)) for p in sorted(QUEUE.rglob('*')) if p.is_file()]
freeze = dict(schema_version=1, frozen_at_utc=datetime.now(timezone.utc).isoformat(),
              original_png_count=10, original_png_xml_pairs=8, original_png_observation_json_pairs=6,
              supplemental_review_sheets=0, supplemental_original_count_contribution=0,
              files=freeze_rows, file_count=len(freeze_rows), total_bytes=sum(r['bytes'] for r in freeze_rows),
              payload_file_count=len(payload_rows), payload_bytes=sum(r['bytes'] for r in payload_rows),
              copied_original_file_count=len(copies), validated_local_page_links=page_link_count,
              source_receipts=source_receipts, staged_only=True, shared_gallery_modified=False,
              git_performed=False, duplicate_audits_or_tests=0, new_image_views=0)
save(QUEUE / 'queue-freeze.json', freeze)
for path in QUEUE.rglob('*'):
    if path.is_file():
        path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
print(json.dumps(dict(queue=str(QUEUE), originalPngs=10, pngXmlPairs=8, pngObservationJsonPairs=6,
                      derivedImages=0, payloadFiles=len(payload_rows), payloadBytes=sum(r['bytes'] for r in payload_rows),
                      freeze=info(QUEUE / 'queue-freeze.json'), manifest=info(QUEUE / 'publication-manifest.json'))))
