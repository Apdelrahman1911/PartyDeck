"""Prepare byte-preserving screenshot copies; consume existing frozen audits only."""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import html
import json
import os
import shutil
import stat
import struct

ROOT = Path('/root/projects/PartyDeck')
QUEUE = Path(__file__).resolve().parent
PAYLOAD = QUEUE / 'payload/docs/screenshots'
HEAD = 'fc431ee775990943dfe152f4f20fb9365db4e72d'
A36 = ROOT / 'artifacts/evidence-storage/34485033488'
A35 = ROOT / 'artifacts/evidence-storage/34485028785'
C36 = 'godot-android-adaptive-34485033488'
C35 = 'android-34485028785'
SUP = 'supplemental/android-adaptive-34485033488-review-sheets'


def load(path):
    return json.loads(path.read_bytes())


def info(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False) + '\n')


assert info(A36 / 'evidence-freeze.json')['sha256'] == 'f1a6e08dc085e6530f0a1229f899424de164a97c07e1736d2d93652dbb4f7672'
assert info(A35 / 'collection-frozen.json')['sha256'] == '4580c57a7d42b7c524b1948162bd75f74c6e4c5ff03c85e26d05213323132de8'
assert info(A35 / 'review/runtime-evidence-audit-v2.json')['sha256'] == '62735d02e852d3384ae544ce6fa26bb68ff13125148244b733ca9b0d9b6e9565'
f36 = load(A36 / 'evidence-freeze.json')
i36 = load(A36 / f36['originals']['file'])
i35 = load(A35 / 'collection-file-manifest.json')
index36 = {row['file']: row for row in i36['files'] + f36['derived']}
index35 = {row['file']: row for row in i35['files']}
index36['evidence-freeze.json'] = info(A36 / 'evidence-freeze.json')
index35['collection-frozen.json'] = info(A35 / 'collection-frozen.json')
copies, screenshots, evidence, collections, supplemental = [], [], [], [], []
destinations = set()


def copy_original(base, relative, target, collection, kind='original_evidence'):
    source = base / relative
    destination = PAYLOAD / target
    assert source.resolve().is_relative_to(base) and not source.is_symlink()
    assert destination.resolve().is_relative_to(PAYLOAD) and target not in destinations
    destinations.add(target)
    record = (index36 if base == A36 else index35)[relative]
    expected = {key: record[key] for key in ('bytes', 'sha256')}
    assert info(source) == expected, relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    assert not destination.exists()
    shutil.copy2(source, destination)
    assert info(destination) == expected, target
    row = dict(source=str(source), staged=str(destination), destination='docs/screenshots/' + target,
               gallery_path=target, collection=collection, artifact_type=kind, **expected)
    copies.append(row)
    if not kind.endswith('_capture'):
        evidence.append(dict(path=target, original_filename=source.name, source_original=str(source),
                             collection=collection, artifact_type=kind, **expected))
    return row


def image_record(collection, target, source, scenario, api, variant, scale, dimensions, notes,
                 paired_ui=None, receipt=None, result=None, captured=None, case_status=None, reviewed=False):
    metadata = info(PAYLOAD / target)
    row = dict(id=target.removesuffix('.png'), collection=collection, path=target,
               original_filename=Path(target).name, scenario=scenario,
               platform=f'Android API {api} x86_64 emulator, production Compose shell, {variant} APK',
               artifact_type='native_emulator_capture', width_px=dimensions[0], height_px=dimensions[1],
               font_scale=scale, source_original=str(source), source_aliases=[], source_revision=HEAD,
               source_revision_exact=True, ci_run='34485033488' if api == 36 else '34485028785',
               synthetic_invitation_fixture=False, notes=notes, captured_utc=captured,
               case_status=case_status, paired_ui_path=paired_ui, capture_receipt_path=receipt,
               original_result_path=result, engine_pixels_qualified=False,
               existing_owner_visual_review=reviewed, publication_reaudited_evidence=False, **metadata)
    screenshots.append(row)
    return row


captions36 = {
    'home-cold': 'Cold Compose Home — installation passed',
    '2d-landscape-baseline-public': 'Standard table public baseline before the failed 2D entry',
    '2d-landscape-baseline-first-card': 'Standard table first-card baseline before the failed 2D entry',
    '2d-landscape-baseline-selected': 'Standard table selection before the failed 2D entry',
    '2d-landscape-initial-selector': 'Table style dialog before the recorded 2D choice action',
    'final-diagnostic': 'Failed initial landscape check — final Standard table diagnostic',
}
cases36 = load(A36 / 'audit-v1/case-execution.json')['cases']
collections.append(dict(id=C36, path=C36, count=16, title='Android API 36 adaptive — four initial landscape failures',
                        platform='Android API 36 x86_64 emulator, production qualification APKs',
                        kind='native_emulator_failed_adaptive_capture', tier='native_current', revision=HEAD,
                        source_revision_exact=True, ci_run='34485033488', workflow_conclusion='failure',
                        status='All four installations pass; all four first initial-landscape checks fail. No native transition is qualified.',
                        text='16 original PNG/XML pairs. Normal text stops in Standard preparation; 200% text stops waiting for the Godot Activity after the logged picker action. No video; 92 named scopes unexecuted.'))
for case in cases36:
    variant, scale = case['variant'], case['fontScale']
    case_prefix = case['case'] + '/godot-adaptive/runtime/'
    result_target = C36 + '/' + case_prefix + 'godot-adaptive-result.json'
    copy_original(A36, case_prefix + 'godot-adaptive-result.json', result_target, C36)
    for cap in case['captures']:
        name = cap['name']
        png_target, xml_target = (C36 + '/' + cap[k]['file'] for k in ('png', 'xml'))
        receipt_relative = case_prefix + f'captures/{name}.json'
        receipt_target = C36 + '/' + receipt_relative
        copy_original(A36, cap['png']['file'], png_target, C36, 'original_app_capture')
        copy_original(A36, cap['xml']['file'], xml_target, C36)
        copy_original(A36, receipt_relative, receipt_target, C36)
        failure = ('The original check failed during Standard preparation with a UI dump timeout.' if scale == '1.0'
                   else 'The original check failed after a logged 2D choice action and a 45-second wait for the Godot Activity; no renderer process was sampled.')
        notes = [failure, 'Only the initial Compose-shell landscape setup was entered. Native rotation, held touch, reentry, leave, split-screen and 3D remain unqualified.']
        if name == 'final-diagnostic' and scale == '2.0':
            notes.append('The final original shows the Standard table with the hand concealed; the picker dialog is no longer visible.')
        if name == 'final-diagnostic' and scale == '1.0':
            notes.append('The original wide Standard layout retains clipped lower gameplay controls.')
        if name.endswith('selector'):
            notes.append('Pre-action original. A logged action label does not independently establish delivered coordinates or callback outcome.')
        image_record(C36, png_target, A36 / cap['png']['file'], captions36[name], 36, variant, float(scale),
                     [cap['dimensions']['width'], cap['dimensions']['height']], notes,
                     xml_target, receipt_target, result_target, cap['endedUtc'], 'failed', True)

for relative in ('evidence-freeze.json', 'RESULT.md', 'audit-v1/audit-result.json',
                 'audit-v1/case-audit-result.json', 'audit-v1/still-review.json'):
    copy_original(A36, relative, C36 + '/provenance/' + Path(relative).name, C36, 'existing_frozen_audit')

for sheet in load(A36 / 'audit-v1/still-overviews.json'):
    target = SUP + '/' + Path(sheet['derived']).name
    copied = copy_original(A36, sheet['derived'], target, 'android-adaptive-34485033488-review-sheets', 'derived_review_sheet')
    raw = (PAYLOAD / target).read_bytes()
    width, height = struct.unpack('>II', raw[16:24])
    supplemental.append(dict(path=target, source_original=copied['source'], original_filename=Path(target).name,
                             bytes=copied['bytes'], sha256=copied['sha256'], width_px=width, height_px=height,
                             original_png_count_contribution=0, case=sheet['case'],
                             caption='Derived review sheet of the preserved failed-run stills; resized and labeled for review. This is not an additional original capture.',
                             source_originals=sheet['sources']))
copy_original(A36, 'audit-v1/still-overviews.json', SUP + '/still-overviews.json',
              'android-adaptive-34485033488-review-sheets', 'original_derivation_receipt')

a35 = load(A35 / 'review/runtime-evidence-audit-v2.json')
assert a35['source_revision'] == HEAD
ordinary_names = {
    'home': 'Home and practice route', 'rules-intro': 'Rules introduction', 'rules-last-step': 'Rules final step',
    'rules-practice-action': 'Rules Practice action checkpoint', 'rules-practice-entered': 'Practice entered from Rules',
    'rules-returned-home': 'Home after leaving Rules-entered practice', 'settings-changed': 'Changed settings',
    'settings-return-home': 'Home after settings', 'settings-persisted': 'Persisted settings checkpoint',
    'practice-concealed': 'Practice with the hand concealed', 'practice-selected': 'Practice card selection checkpoint',
    'practice-resumed-concealed': 'Practice concealed after resume', 'practice-after-play': 'Practice after the recorded play',
    'practice-returned-home': 'Home after leaving practice', 'host-lobby': 'Host lobby',
    'host-after-share': 'Host lobby after the sharing flow', 'host-returned-home': 'Home after leaving the host lobby',
    'join-name-soft-ime': 'Join name field with the software keyboard', 'join-invalid': 'Invalid join input feedback',
    'home-actions': 'Home action checkpoints', 'settings': 'Settings checkpoint',
    'private-hand': 'Own-hand checkpoint', 'play-action': 'Play action reachability checkpoint',
}
for variant, ordinary in a35['ordinary_app_smokes'].items():
    short = 'optimized' if variant == 'optimized-test-signed' else variant
    collection = C35 + '-' + short
    path = C35 + '/' + variant
    collections.append(dict(id=collection, path=path, count=31,
                            title=f'Android API 35 {variant} — ordinary UI flow passed',
                            platform=f'Android API 35 x86_64 emulator, production {variant} APK',
                            kind='native_emulator_capture', tier='native_current', revision=HEAD,
                            source_revision_exact=True, ci_run='34485028785', workflow_conclusion='failure',
                            status=f'Ordinary UI smoke passed with {ordinary["step_count"]} recorded steps. Separate native entry failed.',
                            text='30 named PNG/XML pairs and the distinct final PNG. No new full visual/accessibility review is claimed by this publication preparation.'))
    result_target = path + '/smoke-result.json'
    copy_original(A35, ordinary['result']['file'], result_target, collection)
    for cap in ordinary['captures']:
        name = cap['name']
        large = name.startswith('large-text-')
        base_name = name.removeprefix('large-text-')
        title = ordinary_names.get(base_name, base_name.replace('-', ' ').capitalize()) + (' — 200% text' if large else '')
        png_target, xml_target = (path + '/' + Path(cap[k]['file']).name for k in ('png', 'xml'))
        copy_original(A35, cap['png']['file'], png_target, collection, 'original_app_capture')
        copy_original(A35, cap['xml']['file'], xml_target, collection)
        notes = ['The original ordinary Compose UI smoke passed. The overall workflow failed in the separate Godot session entry.',
                 'Publication uses the existing source-owner audit and original receipts; this is not a new visual, accessibility or native-engine qualification.']
        if name == 'large-text-play-action':
            notes.append('The named stage establishes recorded reachability only; it is not a second accepted-play claim.')
        image_record(collection, png_target, A35 / cap['png']['file'], title, 35, variant,
                     2.0 if large else 1.0, cap['dimensions'], notes, paired_ui=xml_target,
                     result=result_target, case_status='passed')
    final = ordinary['final_diagnostic_png']
    final_target = path + '/final-screen.png'
    copy_original(A35, final['file'], final_target, collection, 'original_app_capture')
    raw = (PAYLOAD / final_target).read_bytes()
    image_record(collection, final_target, A35 / final['file'], 'Final ordinary-smoke diagnostic — distinct original',
                 35, variant, 2.0, list(struct.unpack('>II', raw[16:24])),
                 ['Distinct final original retained after the passed ordinary UI flow. It has no named PNG/XML pair in the original capture list.',
                  'The source-owner audit did not include a full visual review of this final image.'],
                 result=result_target, case_status='passed')

session_collection = 'godot-android-session-34485028785'
collections.append(dict(id=session_collection, path=C35 + '/godot-session', count=12,
                        title='Android API 35 production Godot selection — both native entries failed',
                        platform='Android API 35 x86_64 emulator, production debug and optimized qualification APKs',
                        kind='native_emulator_failed_session_capture', tier='native_current', revision=HEAD,
                        source_revision_exact=True, ci_run='34485028785', workflow_conclusion='failure',
                        status='Installation and Compose baseline passed; both 2d.native-entry checks failed after the recorded choice action.',
                        text='12 original PNG/XML pairs. The 45-second native-activity wait expired with the concealed Compose table retained. No renderer/Ready, 3D, lifecycle, renderer-death or native pixel-privacy acceptance.'))
session_captions = {
    'home-cold': 'Cold Compose Home — installation passed',
    '2d-baseline-public': 'Concealed Compose practice baseline — baseline check passed',
    '2d-baseline-first-card': 'First indexed card sample before switching — deselected',
    '2d-baseline-selected': 'Compose first-card selection before switching',
    '2d-entry-selector': 'Production Table style modal before the actual 2D choice action',
    'final-diagnostic': 'Failed 2D native entry — concealed Compose table remains',
}
for variant, session in a35['godot_sessions'].items():
    prefix = f'android-jvm-reports/build/ci/android/godot-session/{variant}/runtime/'
    target_prefix = f'{C35}/godot-session/{variant}/runtime/'
    result_target = target_prefix + 'godot-session-result.json'
    copy_original(A35, session['result']['file'], result_target, session_collection)
    for cap in session['captures']:
        name = cap['name']
        png_relative, xml_relative = prefix + cap['screenshot']['file'], prefix + cap['ui']['file']
        png_target, xml_target = target_prefix + cap['screenshot']['file'], target_prefix + cap['ui']['file']
        receipt_relative, receipt_target = prefix + f'captures/{name}.json', target_prefix + f'captures/{name}.json'
        copy_original(A35, png_relative, png_target, session_collection, 'original_app_capture')
        copy_original(A35, xml_relative, xml_target, session_collection)
        copy_original(A35, receipt_relative, receipt_target, session_collection)
        notes = ['Both variants failed 2d.native-entry after the recorded choice action and a 45-second native-activity wait.',
                 'No native renderer/Ready was observed. 3D, lifecycle, renderer-death and native pixel privacy remain unqualified.']
        if name == '2d-baseline-first-card':
            sample = session['checks']['2d.practice-baseline']['baseline']['first_card']
            notes.append(f'The original baseline records {sample["rank"]} at index 0 in a five-card hand, deselected.')
        if name == '2d-entry-selector':
            notes.append('Original pre-tap modal: Standard selected, enabled 2D/3D rows. This frame alone does not prove a native launch.')
        image_record(session_collection, png_target, A35 / png_relative, session_captions[name], 35, variant, 1.0,
                     [cap['screenshot']['width'], cap['screenshot']['height']], notes,
                     xml_target, receipt_target, result_target, cap['screenshot_received_utc'], 'failed',
                     name in ('2d-entry-selector', 'final-diagnostic'))

for relative in ('collection-frozen.json', 'review/runtime-evidence-audit-v2.json',
                 'review/picker-to-native-failure-audit.json', 'review/RESULT.md'):
    copy_original(A35, relative, C35 + '/provenance/' + Path(relative).name, C35, 'existing_frozen_audit')


def gallery_page(collection):
    path = collection['path']
    lines = [f"# {collection['title']}", '', f"[All collections]({os.path.relpath('README.md', path)}) · [Original CI run](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/{collection['ci_run']})", '',
             collection['status'], '', collection['text'], '', f"Exact source: `{HEAD}`. Original PNG/XML/JSON bytes and the recorded failure limits are preserved.", '',
             '| Original capture | Scenario and retained limits |', '| --- | --- |']
    for row in screenshots:
        if row['collection'] != collection['id']:
            continue
        relative = os.path.relpath(row['path'], path)
        caption = html.escape(row['scenario'])
        links = []
        for key, label in (('paired_ui_path', 'Original XML'), ('capture_receipt_path', 'Original capture receipt'), ('original_result_path', 'Original result')):
            if row.get(key):
                links.append(f"[{label}]({os.path.relpath(row[key], path)})")
        notes = '<br>'.join(html.escape(note) for note in row['notes'])
        lines.append(f'| <a href="{relative}"><img src="{relative}" alt="{caption}" width="168"></a> | **{caption}**<br>{row["platform"]}; text {row["font_scale"]}×<br>[{row["original_filename"]}]({relative}); {row["width_px"]} × {row["height_px"]} px<br>SHA-256: <code>{row["sha256"]}</code><br>{" · ".join(links)}<br>{notes} |')
    save(PAYLOAD / path / 'README.md', '\n'.join(lines) + '\n')


for collection in collections:
    gallery_page(collection)
save(PAYLOAD / C35 / 'README.md', '# Android production captures — CI 34485028785\n\nThe ordinary UI smokes passed; the separate 2D native-entry checks failed. Exact source is `' + HEAD + '`.\n\n| Collection | Original PNGs | Outcome |\n| --- | ---: | --- |\n| [Debug ordinary flow](debug/README.md) | 31 | Ordinary UI smoke passed; no new full visual review. |\n| [Optimized ordinary flow](optimized-test-signed/README.md) | 31 | Ordinary UI smoke passed; no new full visual review. |\n| [Production table-style entry](godot-session/README.md) | 12 | Both native entry checks failed; no Godot renderer/Ready observed. |\n\nThe 72 named PNG/XML pairs and two distinct final PNGs preserve original failures and successes separately. [Existing owner result](provenance/RESULT.md) · [Original audit](provenance/runtime-evidence-audit-v2.json) · [Collection freeze](provenance/collection-frozen.json).\n')
sheet_lines = ['# Supplemental API36 review sheets', '', 'These four unchanged audit derivatives were viewed during review. They resize and label the 16 original stills; they contribute **zero** additional original captures. The run remains failed and unqualified. Original images and XML are in [the run collection](../../' + C36 + '/README.md).', '', '| Derived sheet | Provenance |', '| --- | --- |']
for row in supplemental:
    name = Path(row['path']).name
    sheet_lines.append(f'| <a href="{name}"><img src="{name}" alt="Derived failed-run review sheet" width="250"></a> | [{name}]({name})<br>{row["caption"]}<br>{row["width_px"]} × {row["height_px"]} px<br>SHA-256: <code>{row["sha256"]}</code> |')
sheet_lines += ['', '[Original source-image mappings and FFmpeg derivation](still-overviews.json).']
save(PAYLOAD / SUP / 'README.md', '\n'.join(sheet_lines) + '\n')

assert len(screenshots) == 90 and sum(row['paired_ui_path'] is not None for row in screenshots) == 88
assert len(supplemental) == 4 and sum(c['count'] for c in collections) == 90
assert len({row['path'] for row in screenshots}) == len(screenshots)
manifest = dict(schema_version=1, preparation_scope='Publication copy preparation only; existing frozen owner audits reused. No app runs, tests, downloads or repeated evidence audits.',
                publication_state='Queued outside docs/screenshots for the next batch; current 196-original publication remains unchanged.',
                do_not_publish_before='review_design current-batch push acknowledgment', source_revision=HEAD,
                original_png_count=90, original_png_xml_pairs=88, standalone_original_pngs=2,
                supplemental_review_sheet_count=4, supplemental_original_count_contribution=0,
                collections=collections, screenshots=screenshots, evidence=evidence, supplemental=supplemental,
                copy_plan=copies, generated_gallery_pages=[str(p.relative_to(PAYLOAD)) for p in sorted(PAYLOAD.rglob('README.md'))])
save(QUEUE / 'publication-manifest.json', manifest)
save(QUEUE / 'copy-paths.tsv', 'sha256\tbytes\tsource\tstaged\tdestination\n' + ''.join(f'{row["sha256"]}\t{row["bytes"]}\t{row["source"]}\t{row["staged"]}\t{row["destination"]}\n' for row in copies))
save(QUEUE / 'gallery-index-rows.md', '| Proposed next collection | Original PNGs | Evidence scope |\n| --- | ---: | --- |\n' + ''.join(f'| [{c["title"]}]({c["path"]}/README.md) | {c["count"]} | {c["status"]} |\n' for c in collections) + f'\nSupplemental: [four reviewed contact sheets]({SUP}/README.md); zero original-PNG count.\n')
save(QUEUE / 'HANDOFF.md', '# Next screenshot publication batch\n\nPrepared outside the live gallery as requested. Wait for review_design’s current 196-original batch push acknowledgment. Root owns Git.\n\nCopy the three new roots under `payload/docs/screenshots/` into `docs/screenshots/`: `godot-android-adaptive-34485033488`, `android-34485028785`, and `supplemental/android-adaptive-34485033488-review-sheets`. The complete originals and ready README pages are staged. `publication-manifest.json` supplies four collection records, 90 original screenshot records, paired evidence and four supplemental records. Merge those records and `gallery-index-rows.md` through the existing gallery owner’s next-batch workflow; do not replace the shared manifest or README with these fragments.\n\nThe queue contains 88 PNG/XML pairs and two distinct final ordinary PNGs, plus four clearly labeled derivatives with zero original-image count. Source hashes, staged/destination paths and byte lengths are in `copy-paths.tsv`; all staged PNG/XML/JSON bytes match their existing frozen source receipts. API36 failures and API35 native-entry failures remain explicit. The API35 ordinary scripts passed, but no new full visual/accessibility review is claimed. No APKs, ZIPs, source archives, signing material or native execution were added.\n')

payload_files = sorted(path for path in (QUEUE / 'payload').rglob('*') if path.is_file())
payload_rows = [dict(file=str(path.relative_to(QUEUE)), **info(path)) for path in payload_files]
save(QUEUE / 'payload-SHA256SUMS', ''.join(f'{row["sha256"]}  {row["file"]}\n' for row in payload_rows))
frozen_files = sorted(path for path in QUEUE.rglob('*') if path.is_file())
freeze_rows = [dict(file=str(path.relative_to(QUEUE)), **info(path)) for path in frozen_files]
freeze = dict(schema_version=1, frozen_at_utc=datetime.now(timezone.utc).isoformat(),
              original_png_count=90, original_png_xml_pairs=88, standalone_original_pngs=2,
              supplemental_review_sheets=4, supplemental_original_count_contribution=0,
              files=freeze_rows, file_count=len(freeze_rows), total_bytes=sum(row['bytes'] for row in freeze_rows),
              source_freezes={'34485033488': info(A36 / 'evidence-freeze.json'), '34485028785': info(A35 / 'collection-frozen.json')},
              staged_only=True, shared_gallery_modified=False, git_performed=False, duplicate_audits_or_tests=0)
save(QUEUE / 'queue-freeze.json', freeze)
for path in QUEUE.rglob('*'):
    if path.is_file():
        path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
print(json.dumps(dict(queue=str(QUEUE), originalPngs=90, originalPairs=88, standaloneOriginalPngs=2,
                      derivedReviewSheets=4, payloadFiles=len(payload_rows), payloadBytes=sum(row['bytes'] for row in payload_rows),
                      freeze=info(QUEUE / 'queue-freeze.json'), manifest=info(QUEUE / 'publication-manifest.json'))))
