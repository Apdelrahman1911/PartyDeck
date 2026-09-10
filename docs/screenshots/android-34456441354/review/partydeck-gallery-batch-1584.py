"""Archive the two completed ordinary Android runs once; no Git or runtime execution."""
import ast
import copy
import hashlib
import html
import json
import os
import shutil
from pathlib import Path

from PIL import Image

REPO = Path('/root/projects/PartyDeck')
GALLERY = REPO / 'docs/screenshots'
DESIGN = REPO / 'godot/reviews/design-review.md'
STAGE = Path('/tmp/partydeck-gallery-1584-staged')
AUDIT_PATH = Path('/tmp/partydeck-gallery-1584-source-audit.json')
AUDIT = json.loads(AUDIT_PATH.read_text())
BASELINE_PATH = Path('/tmp/partydeck-gallery-before-1584.json')
new_roots = ['android-34456441354', 'android-34457458638']

# Load only reusable definitions; never execute an earlier builder body.
helper_source = Path('/tmp/partydeck-gallery-batch-1279.py').read_text()
helper_names = {'sha', 'read', 'preserve', 'evidence', 'audited_evidence', 'screenshot', 'row', 'markdown'}
helper_nodes = [node for node in ast.parse(helper_source).body
                if isinstance(node, ast.FunctionDef) and node.name in helper_names]
assert len(helper_nodes) == len(helper_names)
exec(compile(ast.Module(body=helper_nodes, type_ignores=[]), '<gallery-preservation-helpers>', 'exec'))

assert sha(AUDIT_PATH) == 'd586ac480bf729c7e3e3d8e30822e663c088ab027778150a97abc347caaf176e'
assert sha(GALLERY / 'manifest.json') == 'd257e913639a50150d3df666d81d60e47fd91f50116f9ff2e0fca144ecde0e4c'
assert (GALLERY / 'manifest.json').read_bytes() == BASELINE_PATH.read_bytes()
assert (GALLERY / 'README.md').read_bytes() == Path('/tmp/partydeck-gallery-before-1584-README.md').read_bytes()
assert DESIGN.read_bytes() == Path('/tmp/partydeck-gallery-before-1584-design-review.md').read_bytes()
saved_files = read('/tmp/partydeck-gallery-1584-baseline-files.json')
assert len(saved_files) == 5482
for record in saved_files:
    path = REPO / record['path']
    assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], path
baseline = read(BASELINE_PATH)
manifest = copy.deepcopy(baseline)
assert len(manifest['screenshots']) == 1460 and len(manifest['evidence']) == 3942
assert len(manifest['collections']) == 66
assert all(not (GALLERY / root).exists() for root in new_roots)
assert not STAGE.exists()
STAGE.mkdir()

TABLE = '| Original image | Scenario and provenance |\n| --- | --- |\n'
COMMON_REVIEW = new_roots[0] + '/review/partydeck-gallery-1584-source-audit.json'
SCENARIOS = {
    'home': 'Home at 100% text',
    'rules-intro': 'How to play introduction at 100% text',
    'rules-last-step': 'How to play after scrolling at 100% text',
    'rules-practice-action': 'Complete Rules Practice action at 100% text',
    'rules-practice-entered': 'Practice reached from Rules at 100% text',
    'rules-returned-home': 'Home after confirmed departure from Rules practice',
    'settings-changed': 'Settings changed: sound and haptics off, reduced motion on',
    'settings-return-home': 'Home after changing settings',
    'settings-persisted': 'Settings retained after relaunch',
    'practice-concealed': 'Practice with the private hand concealed',
    'practice-selected': 'Practice with one private card selected',
    'practice-resumed-concealed': 'Resumed practice with the private hand concealed',
    'practice-after-play': 'Public round result captured after the normal-text play',
    'practice-returned-home': 'Home after confirmed departure from practice',
    'host-lobby': 'Local host lobby before opening its invitation',
    'host-after-share': 'Local host lobby after dismissing sharing',
    'host-returned-home': 'Home after closing the local host lobby',
    'join-name-soft-ime': 'Focused Join name with the real keyboard at 100% text',
    'join-invalid': 'Join recovery after an invalid invitation at 100% text',
    'large-text-home-actions': 'Home actions at 200% text',
    'large-text-rules-intro': 'How to play introduction at 200% text',
    'large-text-rules-last-step': 'How to play after scrolling at 200% text',
    'large-text-rules-practice-action': 'Complete Rules Practice action at 200% text',
    'large-text-rules-practice-entered': 'Practice reached from Rules at 200% text',
    'large-text-rules-returned-home': 'Home after confirmed departure from Rules practice at 200% text',
    'large-text-settings': 'Settings at 200% text',
    'large-text-join-name-soft-ime': 'Focused Join name with the real keyboard at 200% text',
    'large-text-join-invalid': 'Join recovery after an invalid invitation at 200% text',
    'large-text-private-hand': 'Enlarged private hand at its captured scroll position',
    'large-text-play-action': 'Reachable Play and Challenge actions at 200% text',
    'final-screen': 'Final Home diagnostic at 200% text before environment restoration',
}
AFTER_PLAY = {
    ('34456441354', 'debug'): "Orbit catches Pip's three-Star bluff. Public Moon, Crown and Crown all mismatch; Pip uses light 1 and remains Still in. The named result and consequence are readable; Next round is partly clipped.",
    ('34456441354', 'optimized-test-signed'): "Pip challenges Moxie's two-Crown claim. Public Crown and Wild both match; Pip loses the challenge and remains Still in after light 1. The named result and consequence are readable; only the upper edge of the next-result action is visible.",
    ('34457458638', 'debug'): "Moxie catches Guest's one-Moon bluff with a public Star; Guest remains Still in after light 1. The named result and consequence are readable; Next round is partly clipped.",
    ('34457458638', 'optimized-test-signed'): "Pip challenges Moxie's two-Star claim. Public Star and Wild both match; Pip burns out at light 1. The named result and consequence are readable; Next round is below this viewport.",
}

def collection_id(run, variant):
    return 'android-' + run + ('-debug' if variant == 'debug' else '-optimized')

def notes_for(batch, case, capture):
    stage = capture['stage']
    run = batch['run']
    api36 = batch['api'] == 36
    variant = case['variant']
    notes = []
    if stage in ['rules-intro', 'rules-last-step', 'large-text-rules-intro', 'large-text-rules-last-step']:
        notes.append('Intermediate Rules scroll checkpoint; viewport-edge clipping is retained. The separate dedicated Practice-action image shows the complete button.')
    if stage in ['rules-practice-action', 'large-text-rules-practice-action']:
        notes.append('The complete Practice label and rounded button border are visible. Original native input geometry records the actual tap, followed by entry to Practice and confirmed return Home.')
        notes.append('No numeric clearance is transferred from an older run.')
    if stage == 'rules-practice-entered':
        if api36 and variant == 'debug':
            notes.append("Already an autonomous public result: Pip challenges Moxie's truthful one-Star claim and burns out at light 1. Next round clips below the viewport.")
        elif api36:
            notes.append("Already an autonomous public result: Orbit challenges Pip's truthful one-Moon claim and remains Still in after light 1. The Next round label is visible but its lower border clips.")
        else:
            notes.append('The actual Rules Practice tap reached the game table. This checkpoint does not imply that private cards were revealed or a Next round action was exercised.')
    if stage == 'large-text-rules-practice-entered':
        if api36:
            notes.append('Concealed round-1 ' + ('Moon' if variant == 'debug' else 'Star') + ' table with the complete Show hand action visible.')
        else:
            notes.append('Actual entry from the enlarged Rules action; the route returns Home after confirmed departure.')
    if stage in ['practice-concealed', 'practice-resumed-concealed']:
        notes.append('Private card faces, rank labels and selection are concealed in this checkpoint.')
    if stage == 'practice-selected':
        notes.append('One card is selected in the normal-text private hand; the complete Play and Challenge controls remain available.')
    if stage == 'practice-after-play':
        notes.append(AFTER_PLAY[(run, variant)])
        notes.append('The unchanged earlier played_card observation is "' + case['observations']['played_card'] + '". The original PNG is a later checkpoint that already includes autonomous public progress.')
        notes.append('Native Next round is not specifically exercised by this smoke flow.')
    if stage in ['host-lobby', 'host-after-share']:
        notes.append('The live invitation, QR and Sharesheet surfaces are intentionally omitted by the exact harness. This original shows the lobby before opening or after dismissing those surfaces.')
    if stage in ['join-name-soft-ime', 'large-text-join-name-soft-ime']:
        notes.append('The focused name field and actual software keyboard are visible together; the paired input-method log is preserved.')
    if stage == 'large-text-join-invalid':
        notes.append('The invalid-invitation recovery message remains readable in the scrolled form.')
        if api36:
            notes.append('The Join action fits in this debug image.' if variant == 'debug' else 'The lower Join-button boundary clips in this image; original tap geometry separately establishes reachability.')
    if stage == 'large-text-private-hand':
        notes.append('The enlarged hand uses vertical scrolling; simultaneous visibility of all cards, turn context and actions is not asserted.')
        if api36:
            notes.append('The fifth card clips at this scroll position. The later action checkpoint shows the complete hand and actions after further scrolling.')
    if stage == 'large-text-play-action':
        notes.append('The Play action is reached after scrolling. The 200% phase checks reachability and does not submit a play.')
        if api36:
            notes.append('All five cards, claim text and complete Play/Challenge actions are visible here; earlier table and turn context has scrolled above the viewport.')
    if stage == 'large-text-settings':
        notes.append('All three settings switches are readable; lower explanatory content continues beyond the viewport.')
    if stage == 'final-screen':
        notes.append('All Home actions are visible. The exact harness collects final diagnostics after the 200% flow and before restoring the environment; this is text 2.0, not text 1.0.')
        notes.append('Additional app diagnostic beyond the receipt’s 30 named route captures.')
    return notes

new_collection_rows = []
for batch in AUDIT['batches']:
    run, api = batch['run'], batch['api']
    root = 'android-' + run
    cases = {case['variant']: case for case in batch['cases']}
    assert batch['runtime']['passed'] and batch['runtime']['sameEmulatorBoot']
    assert batch['runtime']['godotSessionSmoke']['requested'] is False
    assert len(batch['captures']) == 62 and len(batch['excluded']) == 1
    for category in ['native_evidence', 'metadata', 'source_files', 'junit_reports']:
        for original in batch[category]:
            if category == 'source_files':
                relative = 'source/' + original['repository_path']
            elif category == 'junit_reports':
                relative = 'build-evidence/' + original['relative_path']
            else:
                relative = original['relative_path']
            variant = relative.split('/', 1)[0]
            owner = collection_id(run, variant) if variant in cases else root
            extra = {'artifact_type': {
                'native_evidence': 'original_android_runtime_evidence',
                'metadata': 'original_owner_provenance',
                'source_files': 'exact_revision_source_copy',
                'junit_reports': 'original_ci_junit_report',
            }[category], 'ci_run': run, 'source_revision': batch['source_revision'],
                'source_revision_exact': True}
            if category == 'source_files':
                extra['repository_path'] = original['repository_path']
            if category == 'junit_reports':
                extra['recorded_tests'] = original['recorded_tests']
                extra['actual_testcase_elements'] = original['actual_testcase_elements']
            audited_evidence(original, root + '/' + relative, owner, **extra)
    visual_path = Path('/tmp/partydeck-gallery-1584-visual-review-' + run + '.json')
    visual = read(visual_path)
    assert visual['originals_covered_by_owner_and_gallery_visual_reviews'] == 62
    evidence(visual_path, root + '/review/' + visual_path.name, root,
             artifact_type='later_gallery_visual_review', ci_run=run)
    copied_by_source = {record['source_original']: record['path'] for record in manifest['evidence']}
    receipt_relative = next(record['relative_path'] for record in batch['metadata']
                            if record['source_original'] == batch['owner_frozen_receipt']['source_original'])
    review_relative = 'review/' + visual_path.name
    source_audit_link = os.path.relpath(COMMON_REVIEW, root)
    for variant in ['debug', 'optimized-test-signed']:
        case = cases[variant]
        cid = collection_id(run, variant)
        directory = root + '/' + variant
        label = 'debug' if variant == 'debug' else 'optimized, test signed'
        title = f'Android API {api} {label} — CI {run}'
        platform = f'Android API {api} emulator, ' + ('debug APK' if variant == 'debug' else 'optimized test-signed APK')
        order = {stage: n for n, stage in enumerate(case['named_stages'] + ['final-screen'])}
        captures = sorted([capture for capture in batch['captures'] if capture['variant'] == variant],
                          key=lambda capture: order[capture['stage']])
        assert len(captures) == 31 and len(order) == 31
        records = []
        for capture in captures:
            extra = {
                'source_revision': batch['source_revision'], 'source_revision_exact': True,
                'ci_run': run, 'variant': variant, 'stage': capture['stage'],
                'receipt_path': root + '/' + variant + '/smoke-result.json',
                'ui_dump_path': copied_by_source[capture['ui_dump_source']],
                'apk_sha256': case['apk_sha256'],
                'apk_identity_scope': case['package_identity_scope'],
                'apk_bytes_independently_hashed_by_gallery': api == 35,
                'display_density_dpi': 280, 'android_api': api, 'runtime_passed': True,
                'run_godot_session_smoke_requested': False,
                'run_large_text_play_submitted': False,
                'native_next_round_exercised': False,
                'prior_byte_identical_originals': capture['prior_byte_identical_originals'],
                'visual_review_path': root + '/' + review_relative,
            }
            if capture['stage'] == 'final-screen':
                extra['diagnostic_before_environment_restore'] = True
            records.append(screenshot(capture, root + '/' + capture['relative_path'], cid,
                SCENARIOS[capture['stage']], platform, 'native_emulator', capture['font_scale'],
                notes_for(batch, case, capture), **extra))
        status = 'Both text-scale routes pass within this APK’s exercised smoke flow. Dedicated Rules Practice actions have complete labels and borders; intermediate scroll and result images retain clipping.'
        manifest['collections'].append({
            'id': cid, 'path': directory, 'title': title, 'platform': platform,
            'kind': 'native_emulator', 'tier': 'current', 'revision': batch['source_revision'],
            'source_revision_exact': True, 'ci_run': run,
            'source_directory': str(Path(captures[0]['source_original']).parent), 'count': 31,
            'status': status, 'text': f'Android API {api}, 720 × 1600 at 280 dpi, 100%/200% text.',
            'apk_sha256': case['apk_sha256'], 'apk_identity_scope': case['package_identity_scope'],
            'apk_bytes_independently_hashed_by_gallery': api == 35,
            'original_owner_receipt_path': root + '/' + receipt_relative,
            'later_visual_review_path': root + '/' + review_relative,
            'source_audit_path': COMMON_REVIEW,
            'qualification': {
                'runtime': 'passed', 'stage_captures': 30, 'final_diagnostic_capture': 1,
                'final_diagnostic_font_scale': 2.0, 'recorded_steps': case['recorded_steps'],
                'input_records': case['input_record_count'], 'input_actions': case['input_actions'],
                'all_input_geometry_valid': True, 'tap_steps_match_geometry_in_order': True,
                'rules_practice_taps': case['rules_practice_taps'],
                'rules_routes_and_complete_button_borders': 'passed at both text scales',
                'same_emulator_boot_with_other_variant': True,
                'large_text_play': 'reachability only; no play submitted',
                'native_next_round_exercised': False, 'godot_session_smoke_requested': False,
                'limits': 'Result and intermediate scroll views can clip. No physical-device, screen-reader, mixed-device LAN, camera-frame, Godot-session or store qualification.'
            }
        })
        attribution = (
            'The original owner reviewed all 60 named route captures across the two APKs in ten paired sheets. The later gallery review inspected both final diagnostics and both after-play originals; the after-play checks overlap the owner’s scope.'
            if api == 35 else
            'The original owner checked identities and dimensions. The later gallery review visually inspected all 62 app originals across the two APKs in 20 route sheets and one final/preparation sheet.'
        )
        package_statement = (
            'Both downloaded APKs were independently hashed for this gallery and matched their actual executed-input receipts.'
            if api == 35 else
            'APK hashes come from the actual executed-input receipts, with the optimized signing receipt agreeing. The full 474 MB package artifact was not downloaded; this gallery does not claim direct inspection of those APK bytes.'
        )
        content = f'''# {title}

[All screenshot collections](../../README.md) · [Run overview](../README.md) · [Other APK](../{'optimized-test-signed' if variant == 'debug' else 'debug'}/README.md)

**Evidence status:** The exercised ordinary app flow passes at 100% and 200% text. The dedicated Rules Practice actions show complete labels and rounded borders, and their actual taps reach Practice and confirmed return Home. This APK records **{case['recorded_steps']} steps, {case['input_record_count']} native input records, 30 named route captures and one final app diagnostic**. Debug and optimized APKs use the same emulator boot within this run.

Exact source revision: `{batch['source_revision']}`. Android API {api}, 720 × 1600 pixels, 280 dpi. Executed APK SHA-256: `{case['apk_sha256']}`. {package_statement}

The focused name and real keyboard are visible at both scales. Enlarged hands and actions are reached by scrolling; all content is not asserted to fit simultaneously. At 200%, Play is checked for reachability only and is **not submitted**. Native Next round is not specifically exercised. Result and intermediate scroll images retain their clipped content. No margin from an older collection is reused.

{AFTER_PLAY[(run, variant)]} The earlier original smoke observation says `played_card="{case['observations']['played_card']}"`; it remains unchanged because the PNG is a later checkpoint.

[Original smoke result](smoke-result.json) · [Actual input geometry](input-geometry.log) · [Native events](events.log) · [Display and API receipt](../display-configuration.json) · [Run outcomes](../runtime-variants.json) · [Original owner review](../{receipt_relative}) · [Later gallery visual review](../{review_relative}) · [Independent source/archive audit]({os.path.relpath(COMMON_REVIEW, directory)}).

{attribution} Review sheets remain outside the gallery. Every thumbnail below displays and opens its unchanged original PNG, with its paired UI dump and original result linked separately.

All final Home diagnostics are **200% text**, collected before environment restoration. Live invitation, QR and Sharesheet images are intentionally omitted by the exact harness; the displayed host views precede opening or follow dismissal. Godot session smoke was explicitly disabled. These results do not qualify native Godot presentation, physical devices, screen readers, mixed-device LAN, camera frames or store distribution.

'''
        for heading, predicate in [
            ('100% text route captures', lambda record: record['font_scale'] == 1.0),
            ('200% text route captures', lambda record: record['font_scale'] == 2.0 and record['stage'] != 'final-screen'),
            ('Final app diagnostic', lambda record: record['stage'] == 'final-screen')
        ]:
            content += '## ' + heading + '\n\n' + TABLE
            content += '\n'.join(row(record, directory) for record in records if predicate(record)) + '\n\n'
        markdown(directory, content)
        new_collection_rows.append((api, variant, f'| [{title}]({directory}/README.md) | 31 | Both text-scale Rules routes pass with complete dedicated Practice actions. Enlarged Play is reachability only; result and intermediate scroll clipping remain. Final Home is 200% text. |'))

    manifest['excluded_source_images'].extend(copy.deepcopy(batch['excluded']))
    package_statement = (
        'Both downloaded APK byte hashes match the executed-input receipts; the original package audit is retained.'
        if api == 35 else
        'Package identity is receipt-based: the full 474 MB package artifact was not downloaded. The optimized executed-input and signing receipts agree.'
    )
    overview = f'''# Android API {api} — ordinary app smoke, CI {run}

[All screenshot collections](../README.md)

Both APKs pass the exercised ordinary app flow on the same emulator boot at 100% and 200% text. All **62 original app PNGs** are preserved: 30 named route captures and one final Home diagnostic per APK. The final diagnostics are captured at **200% text before environment restoration**.

- [Debug: 31 originals](debug/README.md), {cases['debug']['recorded_steps']} steps and {cases['debug']['input_record_count']} native inputs.
- [Optimized, test signed: 31 originals](optimized-test-signed/README.md), {cases['optimized-test-signed']['recorded_steps']} steps and {cases['optimized-test-signed']['input_record_count']} native inputs.
- [Original runtime outcomes](runtime-variants.json), [display/API receipt](display-configuration.json), [preparation receipt](preparation/preparation-result.json) and [owner’s final review]({receipt_relative}).
- [Later gallery visual review]({review_relative}), [source/archive audit]({source_audit_link}) and [exact smoke harness](source/scripts/smoke-android-ui.py).

Exact revision: `{batch['source_revision']}`. Display: 720 × 1600 pixels at 280 dpi. {package_statement} The archive digest matches published GitHub metadata, and all 413 extracted members byte-match the report ZIP. Copies of original runtime evidence, provenance, pinned sources and all 38 JUnit XML files remain linked through the main manifest; report ZIPs and APK binaries remain outside this gallery.

Both dedicated Rules Practice actions have complete labels and borders. Intermediate Rules, enlarged-hand and public-result checkpoints can clip at the viewport edge. The enlarged Play phase establishes reachability without submitting a play; native Next round is not specifically exercised. Earlier played-card observations and later autonomous public-result images remain separate evidence.

Preparation passes on its first attempt with the app absent and without a reboot. The pre-install Launcher PNG is excluded with its original source, dimensions, hash and reason in the manifest. Live invitation, QR and Sharesheet surfaces were intentionally omitted by the harness. Both runs have `godotSessionSmoke.requested=false`; this collection does not change any Godot qualification result. Physical-device, screen-reader, mixed-device LAN, camera-frame and store qualification remain outside this evidence.

'''
    if api == 35:
        overview += 'The original owner visually reviewed the 60 named route originals in ten paired sheets. This later gallery review inspected two final diagnostics and two overlapping after-play originals, covering all 62 in combination.\n'
    else:
        overview += 'The owner’s earlier identity/dimension-only scope is preserved. The later gallery review inspected all 62 app originals in 21 internal sheets. The successful run’s resource configuration does not establish a uniquely isolated cause for earlier failures.\n'
    markdown(root, overview)

# Shared later audit/helper sources are copied once and linked from both runs.
for path in [AUDIT_PATH, Path('/tmp/partydeck-gallery-1584-source-audit.py'),
             Path('/tmp/partydeck-gallery-1584-record-visual-review.py'), Path(__file__)]:
    evidence(path, new_roots[0] + '/review/' + path.name, new_roots[0],
             artifact_type='later_gallery_preservation_audit')

assert len(manifest['screenshots']) == 1584
assert len(manifest['collections']) == 70
assert manifest['screenshots'][:1460] == baseline['screenshots']
assert manifest['evidence'][:3942] == baseline['evidence']
assert manifest['collections'][:66] == baseline['collections']
new_records = manifest['screenshots'][1460:] + manifest['evidence'][3942:]
assert len({record['source_original'] for record in new_records}) == len(new_records)
assert len({record['path'] for record in manifest['screenshots'] + manifest['evidence']}) == len(manifest['screenshots']) + len(manifest['evidence'])

index = Path('/tmp/partydeck-gallery-before-1584-README.md').read_text()
assert index.count('**1,460 original app and renderer captures**') == 1
index = index.replace('**1,460 original app and renderer captures**', '**1,584 original app and renderer captures**', 1)
header = '| Current reviewed collection | Images | Evidence scope |\n| --- | ---: | --- |\n'
assert index.count(header) == 1
new_collection_rows.sort(key=lambda item: (-item[0], item[1]))
index = index.replace(header, header + '\n'.join(item[2] for item in new_collection_rows) + '\n', 1)
old_exclusion = 'four from Godot CI 34450246541 and four from Godot CI 34456443339.'
new_exclusion = 'four from Godot CI 34450246541, four from Godot CI 34456443339, and one each from ordinary Android CI 34456441354 and API 36 CI 34457458638.'
assert index.count(old_exclusion) == 1
index = index.replace(old_exclusion, new_exclusion, 1)
marker = '- Failed runtime stages, historical layout defects and missing native qualification'
assert index.count(marker) == 1
new_note = '- Ordinary Android CI 34456441354 and API 36 CI 34457458638 add 124 originals from exact dad1c11 and f11f92e source respectively. Both APK variants pass within each same-boot run. Dedicated Rules actions fit at both scales; enlarged Play is reachability only, native Next round is not exercised, and intermediate/result clipping remains. All four final diagnostics are 200% Home before environment restoration. The API 35 owner’s 60 route reviews and this gallery’s two final reviews cover its 62 originals, with two overlapping after-play checks; all 62 API 36 originals were inspected in 21 internal sheets. The API 35 APK bytes were independently hashed; API 36 package identities come from executed-input/signing receipts because its package artifact was not downloaded. Both report ZIP digests and all extracted members were verified. Godot session smoke was disabled, and the existing Godot outcomes remain unchanged.\n'
index = index.replace(marker, new_note + marker, 1)
(STAGE / 'README.md').write_text(index)
(STAGE / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
checksum_records = {'docs/screenshots/' + record['path']: record['sha256']
                    for record in manifest['screenshots'] + manifest['evidence']}
checksum_records.update({record['path']: record['sha256'] for record in manifest['referenced_asset_proofs']})
asset_report = 'godot/renderer/assets/proofs/import_verification.json'
checksum_records[asset_report] = sha(REPO / asset_report)
(STAGE / 'SHA256SUMS').write_text(''.join(digest + '  ' + path + '\n'
                                      for path, digest in sorted(checksum_records.items())))
# Install only the new collection roots and three gallery index files.
for root in new_roots:
    assert not (GALLERY / root).exists()
    shutil.copytree(STAGE / root, GALLERY / root)
for name in ['README.md', 'manifest.json', 'SHA256SUMS']:
    (GALLERY / name).write_bytes((STAGE / name).read_bytes())
assert DESIGN.read_bytes() == Path('/tmp/partydeck-gallery-before-1584-design-review.md').read_bytes()
result = {
    'baseline_commit_acknowledged_by_root': 'c0efda7', 'new_roots': new_roots,
    'screenshots': len(manifest['screenshots']), 'new_originals': 124,
    'evidence': len(manifest['evidence']), 'new_evidence': len(manifest['evidence']) - 3942,
    'checksum_entries': len(checksum_records), 'collections': len(manifest['collections']),
    'new_collections': 4, 'new_readme_pages': 6, 'new_preparation_exclusions': 2,
    'manifest_sha256': sha(GALLERY / 'manifest.json'), 'design_review_byte_unchanged': True,
    'git_commands_run': 0, 'new_application_executions': 0, 'new_builds_or_runtime_tests': 0
}
result_path = Path('/tmp/partydeck-gallery-1584-build-result.json')
assert not result_path.exists()
result_path.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))

