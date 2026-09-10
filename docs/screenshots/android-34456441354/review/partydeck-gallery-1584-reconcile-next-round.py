"""Correct unpublished Next-round claims from the original native input evidence."""
import copy
import hashlib
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('/root/projects/PartyDeck')
GALLERY = REPO / 'docs/screenshots'
AUDIT_PATH = Path('/tmp/partydeck-gallery-1584-source-audit.json')
OUT = Path('/tmp/partydeck-gallery-1584-next-round-reconciliation.json')
assert not OUT.exists()

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def identity(path):
    path = Path(path)
    return {'source_original': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}

audit = read(AUDIT_PATH)
cases = []
for batch in audit['batches']:
    for case in batch['cases']:
        folder = Path(batch['source_root']) / case['variant']
        geometry = [json.loads(line) for line in (folder / 'input-geometry.log').read_text().splitlines() if line.strip()]
        receipt = read(folder / 'smoke-result.json')
        next_taps = [item for item in geometry if item['action'] == 'tap' and item['label'] == 'game-next-round']
        expected = 1 if batch['run'] == '34456441354' and case['variant'] == 'debug' else 0
        assert len(next_taps) == expected
        assert not any(item['action'] == 'tap' and item['label'] == 'game-next-round'
                       and item['stage'] == 'practice actions and privacy' for item in geometry)
        play_taps = [item for item in geometry if item['action'] == 'tap' and item['label'] == 'game-play']
        assert len(play_taps) == 1 and play_taps[0]['stage'] == 'practice actions and privacy'
        steps = []
        if next_taps:
            step_index = receipt['steps'].index('Tapped game-next-round')
            steps = receipt['steps'][step_index - 1:step_index + 5]
            assert steps == [
                'Tapped home-practice', 'Tapped game-next-round', 'Tapped game-reveal-hand',
                'Tapped game-card-0', 'Verified large-text-private-hand: game-card-0',
                'Verified large-text-play-action: game-play']
            assert any('large-text-join-invalid' in step for step in receipt['steps'][:step_index])
            assert receipt['observations']['large_text_font_scale'] == 2.0
            assert next_taps[0]['coordinates'] == {'x': 360, 'y': 1426}
            assert next_taps[0]['bounds'] == [35, 1365, 685, 1488]
            assert next_taps[0]['ui_sequence'] == 182
        cases.append({
            'ci_run': batch['run'], 'variant': case['variant'], 'source_revision': batch['source_revision'],
            'source_revision_exact': True, 'native_next_round_tap_count': len(next_taps),
            'native_next_round_exercised': bool(next_taps),
            'font_scale_at_next_round_tap': 2.0 if next_taps else None,
            'next_round_native_input_records': next_taps,
            'ordered_steps_around_next_round': steps,
            'input_geometry': identity(folder / 'input-geometry.log'),
            'smoke_result': identity(folder / 'smoke-result.json'),
            'subsequent_originals': [record for record in batch['captures']
                if record['variant'] == case['variant'] and record['stage'] in {'large-text-private-hand', 'large-text-play-action'}],
            'normal_after_play_checkpoint_advanced_by_next': False,
            'large_text_play_submitted': False,
            'scope': (
                'One ancillary native Next round tap during 200% practice setup, followed by concealed-hand verification, Reveal, selection and hand/Play-action checkpoints. No separate authority trace or capture of the target at the exact tap instant is claimed.'
                if next_taps else 'No native Next round tap is recorded in this case.'
            )
        })
reconciliation = {
    'recorded_utc': datetime.now(timezone.utc).isoformat(), 'reviewer': 'review_design',
    'source_audit': identity(AUDIT_PATH),
    'cases': cases,
    'native_next_round_taps_total': 1,
    'all_tapped_normal_plays': 4,
    'large_text_play_submitted': False,
    'normal_after_play_result_checkpoints_advanced_by_next': False,
    'source_harness_sha256': '7d6cef007b3d4fb64c6aaaf2e55c3039dc02853332607ccba4a239bc8cd1e5f3',
    'source_explanation': [
        'wait_for_human_turn (source lines 481–500) can tap game-next-round until game-play becomes available.',
        'large_text (lines 620–654) invokes invalid_join before starting practice and calling wait_for_human_turn. The input stage retains large-text-join validation and recovery because the stage is not reset after that helper returns Home.',
        'The API 35 debug native tap is in enlarged practice after Home Practice, not in the Join form.',
        'The later hand/action checkpoints follow Reveal and selection. Their scrolled viewport does not expose an exact current-round number, so this receipt does not assert a pictured round-2 label.',
        'The 200% phase reaches game-play without tapping it. The four normal after-play result captures are followed by leaving the table, not by a Next round tap.'
    ],
    'review_correction': 'The initial gallery assertion of zero Next taps across all four cases was too broad. Original owner receipts and source audit remain unchanged. Unpublished gallery claims are corrected to the per-case evidence above.',
    'initial_gallery_validation_attempt': {
        'path': '/tmp/partydeck-gallery-validate-1584.py', 'outcome': 'Reviewer assertion failed while checking for zero game-next-round taps.',
        'application_or_runtime_failure': False
    },
    'new_application_executions': 0, 'new_builds_or_runtime_tests': 0, 'git_commands_run': 0
}
OUT.write_text(json.dumps(reconciliation, ensure_ascii=False, indent=2) + '\n')
common_relative = 'android-34456441354/review/' + OUT.name
by_case = {(record['ci_run'], record['variant']): record for record in cases}
manifest_path = GALLERY / 'manifest.json'
manifest = read(manifest_path)
assert len(manifest['screenshots']) == 1584 and len(manifest['evidence']) == 4347
assert sha(manifest_path) == 'afd25c0f182ef7b7ffbf78569201a509b51eeaa0f8249090313479a1480d0d42'
normal_sentence = 'No Next round tap follows this normal-text result checkpoint; the flow leaves the table afterward.'
old_sentence = 'Native Next round is not specifically exercised.'
for record in manifest['screenshots'][1460:]:
    case = by_case[(record['ci_run'], record['variant'])]
    record['native_next_round_exercised'] = case['native_next_round_exercised']
    record['case_native_next_round_tap_count'] = case['native_next_round_tap_count']
    record['next_round_reconciliation_path'] = common_relative
    record['normal_after_play_checkpoint_advanced_by_next'] = False
    if record['stage'] == 'practice-after-play':
        record['notes'] = [normal_sentence if note == 'Native Next round is not specifically exercised by this smoke flow.' else note
                           for note in record['notes']]
for collection in manifest['collections'][66:]:
    variant = 'debug' if collection['id'].endswith('-debug') else 'optimized-test-signed'
    case = by_case[(collection['ci_run'], variant)]
    q = collection['qualification']
    q['native_next_round_exercised'] = case['native_next_round_exercised']
    q['native_next_round_tap_count'] = case['native_next_round_tap_count']
    q['next_round_native_input_records'] = case['next_round_native_input_records']
    q['native_next_round_scope'] = case['scope']
    collection['next_round_reconciliation_path'] = common_relative
    page = GALLERY / collection['path'] / 'README.md'
    content = page.read_text()
    assert content.count(old_sentence) == 1
    description = (
        'The 200% practice setup records one native Next round tap while waiting for a human turn, followed by Reveal, selection and hand/Play-action checkpoints. This is separate from the normal after-play result below.'
        if case['native_next_round_tap_count'] else 'This case records no native Next round tap.'
    )
    content = content.replace(old_sentence, description, 1)
    content = content.replace('Native Next round is not specifically exercised by this smoke flow.', normal_sentence)
    marker = '## 100% text route captures'
    assert content.count(marker) == 1
    link = os.path.relpath(common_relative, collection['path'])
    content = content.replace(marker, '[Later Next round input reconciliation](' + link + '). The original input stage label is retained; its source context distinguishes Join recovery from subsequent practice.\n\n' + marker, 1)
    page.write_text(content)
for batch in audit['batches']:
    run = batch['run']
    root = 'android-' + run
    visual_path = Path('/tmp/partydeck-gallery-1584-visual-review-' + run + '.json')
    visual = read(visual_path)
    run_cases = [case for case in cases if case['ci_run'] == run]
    visual['native_next_round_exercised'] = any(case['native_next_round_exercised'] for case in run_cases)
    visual['native_next_round_taps_by_variant'] = {case['variant']: case['native_next_round_tap_count'] for case in run_cases}
    visual['normal_after_play_checkpoint_advanced_by_next'] = False
    visual['later_source_reconciliation'] = identity(OUT)
    visual['later_source_reconciliation_scope'] = 'A native input audit adds the one API 35 debug 200% Next tap; visual inspection counts and original owner records remain unchanged.'
    visual_path.write_text(json.dumps(visual, ensure_ascii=False, indent=2) + '\n')
    original_record = next(record for record in manifest['evidence'] if record['source_original'] == str(visual_path))
    target = GALLERY / original_record['path']
    target.write_bytes(visual_path.read_bytes())
    original_record['sha256'] = sha(target)
    original_record['bytes'] = target.stat().st_size
    overview = GALLERY / root / 'README.md'
    content = overview.read_text()
    assert content.count('native Next round is not specifically exercised.') == 1
    content = content.replace('native Next round is not specifically exercised.',
        'debug records one native Next round tap during 200% practice setup, while optimized records none.' if batch['api'] == 35
        else 'neither APK records a native Next round tap.', 1)
    content += '\n[Later Next round input reconciliation](' + os.path.relpath(common_relative, root) + ').\n'
    overview.write_text(content)

index_path = GALLERY / 'README.md'
index = index_path.read_text()
old_fragment = 'enlarged Play is reachability only, native Next round is not exercised, and intermediate/result clipping remains.'
new_fragment = 'enlarged Play is reachability only and intermediate/result clipping remains. API 35 debug records one Next round tap during enlarged practice setup; the other three cases record none.'
assert index.count(old_fragment) == 1
index_path.write_text(index.replace(old_fragment, new_fragment, 1))
for source in [OUT, Path(__file__)]:
    relative = 'android-34456441354/review/' + source.name
    target = GALLERY / relative
    assert not target.exists()
    target.write_bytes(source.read_bytes())
    manifest['evidence'].append({'path': relative, 'original_filename': source.name, 'source_original': str(source),
        'sha256': sha(target), 'bytes': target.stat().st_size, 'collection': 'android-34456441354',
        'artifact_type': 'later_gallery_native_input_reconciliation'})
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
checksums = {'docs/screenshots/' + record['path']: record['sha256'] for record in manifest['screenshots'] + manifest['evidence']}
checksums.update({record['path']: record['sha256'] for record in manifest['referenced_asset_proofs']})
asset_report = 'godot/renderer/assets/proofs/import_verification.json'
checksums[asset_report] = sha(REPO / asset_report)
(GALLERY / 'SHA256SUMS').write_text(''.join(digest + '  ' + path + '\n' for path, digest in sorted(checksums.items())))
build_path = Path('/tmp/partydeck-gallery-1584-build-result.json')
old_build = build_path.read_bytes()
backup = Path('/tmp/partydeck-gallery-1584-build-result-before-next-round-correction.json')
assert not backup.exists()
backup.write_bytes(old_build)
build = json.loads(old_build)
build.update(evidence=len(manifest['evidence']), new_evidence=len(manifest['evidence']) - 3942,
             checksum_entries=len(checksums), manifest_sha256=sha(manifest_path),
             native_next_round_tap_reconciliation=identity(OUT))
build_path.write_text(json.dumps(build, indent=2) + '\n')
print(json.dumps({'evidence':len(manifest['evidence']), 'checksums':len(checksums),
    'manifest_sha256':sha(manifest_path), 'next_round_native_taps':1,
    'reconciliation':identity(OUT)}, indent=2))

