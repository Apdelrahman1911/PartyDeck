"""Validate and freeze the installed gallery batch without Git or app execution."""
import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

from PIL import Image

REPO = Path('/root/projects/PartyDeck')
GALLERY = REPO / 'docs/screenshots'
DESIGN = REPO / 'godot/reviews/design-review.md'
MUTABLE = {
    'docs/screenshots/README.md', 'docs/screenshots/manifest.json',
    'docs/screenshots/SHA256SUMS', 'godot/reviews/design-review.md',
}
NEW_ROOTS = [
    'godot-android-34463877910', 'godot-desktop-34463877910',
    'godot-ios-authority-34460468965',
]
PROTECTED_MARKER = b'## Visual direction and asset reuse'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


baseline_path = Path('/tmp/partydeck-gallery-before-1717.json')
baseline = read(baseline_path)
baseline_files = read('/tmp/partydeck-gallery-1717-baseline-files.json')
build = read('/tmp/partydeck-gallery-1717-build-receipt.json')
manifest = read(GALLERY / 'manifest.json')
android = read('/tmp/partydeck-gallery-1717-android-source-audit.json')
ios = read('/tmp/partydeck-gallery-1717-ios-source-audit.json')
android_review = read('/tmp/partydeck-gallery-1717-android-visual-review.json')
ios_review = read('/tmp/partydeck-gallery-1717-ios-visual-review.json')
assert len(baseline_files) == 6019
assert build['new_collections'] == NEW_ROOTS
assert build['manifest_sha256'] == sha(GALLERY / 'manifest.json')
assert sha(baseline_path) == 'd05d4812d9c558a9a28936a9289ea59668b3a9c9b340d75d43986176699dc49d'
for key in ['collections', 'screenshots', 'evidence', 'excluded_source_images']:
    assert manifest[key][:len(baseline[key])] == baseline[key], key
for key in ['schema_version', 'description', 'referenced_asset_proofs']:
    assert manifest[key] == baseline[key], key
assert len(manifest['screenshots']) == 1717
assert len(manifest['collections']) == 73
assert len(manifest['evidence']) == build['evidence_files']
assert len(manifest['excluded_source_images']) == len(baseline['excluded_source_images']) + 4

baseline_paths = {record['path'] for record in baseline_files}
unchanged = 0
first_batch = 0
for record in baseline_files:
    if record['path'] in MUTABLE:
        continue
    path = REPO / record['path']
    assert path.is_file(), record['path']
    assert path.stat().st_size == record['bytes'], record['path']
    assert sha(path) == record['sha256'], record['path']
    unchanged += 1
    if record['path'].startswith('docs/screenshots/first-batch/'):
        first_batch += 1
assert first_batch == 132
assert {str(path.relative_to(REPO)) for path in (GALLERY / 'first-batch').rglob('*')
        if path.is_file()} == {path for path in baseline_paths if path.startswith('docs/screenshots/first-batch/')}
original_design = Path('/tmp/partydeck-gallery-before-1717-design-review.md').read_bytes()
current_design = DESIGN.read_bytes()
assert original_design.count(PROTECTED_MARKER) == current_design.count(PROTECTED_MARKER) == 1
assert original_design.split(PROTECTED_MARKER, 1)[1] == current_design.split(PROTECTED_MARKER, 1)[1]

new_screenshots = manifest['screenshots'][len(baseline['screenshots']):]
new_evidence = manifest['evidence'][len(baseline['evidence']):]
assert len(new_screenshots) == 133
assert len(new_evidence) == build['new_evidence_files'] == 1027
assert len({record['path'] for record in manifest['screenshots']}) == len(manifest['screenshots'])
assert len({record['id'] for record in manifest['screenshots']}) == len(manifest['screenshots'])
all_manifest_paths = [record['path'] for record in manifest['screenshots'] + manifest['evidence']]
assert len(all_manifest_paths) == len(set(all_manifest_paths))
new_record_paths = {record['path'] for record in new_screenshots + new_evidence}
new_readmes = {root + '/README.md' for root in NEW_ROOTS}
expected_owned = baseline_paths | {'docs/screenshots/' + path for path in new_record_paths | new_readmes}
actual_owned = {str(path.relative_to(REPO)) for path in GALLERY.rglob('*') if path.is_file()}
actual_owned.add(str(DESIGN.relative_to(REPO)))
assert actual_owned == expected_owned, {
    'unexpected': sorted(actual_owned - expected_owned),
    'missing': sorted(expected_owned - actual_owned),
}
assert {str(path.relative_to(GALLERY)) for path in GALLERY.rglob('*.png')} == {
    record['path'] for record in manifest['screenshots']}
assert not any(Path(path).suffix.lower() in ['.apk', '.aab', '.pck', '.zip'] for path in new_record_paths)

source_copies_verified = 0
new_source_keys = []
for record in new_screenshots + new_evidence:
    path = GALLERY / record['path']
    source = Path(record['source_original'])
    assert source.is_file(), str(source)
    assert path.name == source.name == record['original_filename'], record['path']
    assert path.stat().st_size == source.stat().st_size == record['bytes'], record['path']
    assert sha(path) == sha(source) == record['sha256'], record['path']
    source_copies_verified += 1
    new_source_keys.append(str(source.resolve()))
assert len(new_source_keys) == len(set(new_source_keys))
evidence_paths_text = Path('/tmp/partydeck-gallery-1717-new-evidence-paths.txt').read_text().splitlines()
assert evidence_paths_text == ['docs/screenshots/' + record['path'] for record in new_evidence]

decoded_pngs = 0
for record in manifest['screenshots']:
    with Image.open(GALLERY / record['path']) as picture:
        picture.load()
        assert picture.format == 'PNG'
        assert picture.size == (record['width_px'], record['height_px']), record['path']
    decoded_pngs += 1
for collection in manifest['collections']:
    assert collection['count'] == sum(record['collection'] == collection['id']
                                      for record in manifest['screenshots']), collection['id']

expected_new_captures = (
    [capture for case in android['android'] for capture in case['captures']]
    + android['desktop']['captures'] + ios['captures'])
capture_by_source = {str(Path(capture['source_original']).resolve()): capture
                     for capture in expected_new_captures}
assert len(capture_by_source) == 133
for record in new_screenshots:
    capture = capture_by_source[str(Path(record['source_original']).resolve())]
    for key in ['source_original', 'sha256', 'bytes', 'width_px', 'height_px',
                'source_revision', 'source_revision_exact', 'ci_run']:
        assert record[key] == capture[key], (record['path'], key)
    if capture.get('source_aliases'):
        assert record['source_aliases'] == capture['source_aliases']
    if record['collection'] == NEW_ROOTS[1]:
        prior = GALLERY / record['visually_reviewed_identical_original']
        assert sha(prior) == record['sha256']
        receipt = read(GALLERY / record['receipt_path'])
        assert receipt['sha256'] == record['sha256']
        assert receipt['sourceCommit'] == record['source_revision']
        assert receipt['authorityRevision'] == record['authority_revision']
    if record['collection'] == NEW_ROOTS[2]:
        assert record['attachment'] == capture['attachment']
        assert record['test_result'] == capture['test_result']
        assert record['scenario'] == capture['scenario']
        assert record['suggested_human_readable_name'] == capture['suggested_human_readable_name']
        assert record['xcresult_payload_ref'] == capture['xcresult_payload_ref']
        assert record['xcresult_payload_sha256'] == capture['xcresult_payload_sha256']
        if capture.get('metrics'):
            assert read(GALLERY / record['metrics_path']) == capture['metrics']
            assert record['authority_revision'] == capture['metrics']['revision']
            assert record['round_number'] == capture['metrics']['roundNumber']
for record in new_screenshots:
    for key in ['receipt_path', 'ui_dump_path', 'metrics_path', 'result_path',
                'background_observation_path', 'teardown_path']:
        if key in record:
            assert (GALLERY / record[key]).is_file(), (record['path'], key)
for exclusion, audited in zip(manifest['excluded_source_images'][-4:], android['excluded']):
    for key in ['source_original', 'sha256', 'bytes', 'width_px', 'height_px']:
        assert exclusion[key] == audited[key]
    assert not any(record['source_original'] == exclusion['source_original'] for record in new_screenshots)

checksums = {}
for line in (GALLERY / 'SHA256SUMS').read_text().splitlines():
    digest, path = line.split('  ', 1)
    assert re.fullmatch('[0-9a-f]{64}', digest)
    assert path not in checksums
    checksums[path] = digest
assert len(checksums) == build['checksum_entries']
assert len(checksums) == len(manifest['screenshots']) + len(manifest['evidence']) + len(build['auxiliary_checksum_paths'])
for path, digest in checksums.items():
    assert sha(REPO / path) == digest, path
for record in manifest['screenshots'] + manifest['evidence']:
    assert checksums['docs/screenshots/' + record['path']] == record['sha256']
assert 'docs/screenshots/manifest.json' not in checksums
assert set(checksums) == {
    'docs/screenshots/' + record['path'] for record in manifest['screenshots'] + manifest['evidence']
} | set(build['auxiliary_checksum_paths'])

# Original evidence Markdown can retain source-context links; gallery-authored pages must resolve.
immutable_evidence_paths = {record['path'] for record in manifest['evidence']}
pages = [path for path in GALLERY.rglob('*.md')
         if str(path.relative_to(GALLERY)) not in immutable_evidence_paths]
pages.append(DESIGN)
local_links = 0
new_thumbnails = []
for page in pages:
    content = page.read_text()
    links = re.findall(r'\]\(([^)\n]+)\)', content)
    links += re.findall(r'(?:href|src)="([^"]+)"', content)
    for target in links:
        target = html_target = unquote(target.strip().strip('<>'))
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        target_path = (page.parent / parsed.path).resolve()
        assert target_path.exists(), (str(page), html_target)
        local_links += 1
    if page == GALLERY / page.parent.name / 'README.md' and page.parent.name in NEW_ROOTS:
        for target, displayed in re.findall(r'<a href="([^"]+)"><img src="([^"]+)"[^>]*>', content):
            assert target == displayed
            actual = (page.parent / unquote(target)).resolve()
            assert actual.suffix == '.png'
            new_thumbnails.append(str(actual.relative_to(GALLERY)))
assert Counter(new_thumbnails) == Counter(record['path'] for record in new_screenshots)

authored = [GALLERY / 'README.md', GALLERY / 'manifest.json', DESIGN]
authored.extend(GALLERY / root / 'README.md' for root in NEW_ROOTS)
authored.extend(Path('/tmp') / name for name in [
    'partydeck-gallery-batch-1717.py', 'partydeck-gallery-1717-validate.py',
    'partydeck-gallery-1717-review-synthesis.py', 'partydeck-gallery-1717-visual-review-notes.json',
    'partydeck-gallery-1717-android-visual-review.json', 'partydeck-gallery-1717-ios-visual-review.json',
])
for path in authored:
    text = path.read_text()
    assert text.endswith('\n') and not text.endswith('\n\n'), str(path)
    assert all(line == line.rstrip() for line in text.splitlines()), str(path)
    assert not re.search(r'^(<<<<<<<|=======|>>>>>>>)', text, re.MULTILINE), str(path)
    if path.suffix == '.py':
        ast.parse(text, filename=str(path))

android_collection = next(collection for collection in manifest['collections']
                          if collection['id'] == NEW_ROOTS[0])
assert android_collection['cases'] == android_review['cases']
assert android_collection['workflow_conclusion'] == 'success'
assert android_collection['producer_receipt_conclusion'] is None
summary = android_review['runtime_summary']
assert summary['passed_cases'] == 4 and summary['completed_requested_exits'] == 12
assert summary['actual_process_deaths'] == summary['native_barriers'] == summary['native_main_callbacks'] == 12
assert summary['fallbacks'] == 0
assert summary['source_close_bounds_ms'] == {'closeFallbackMs': 250, 'rendererExitWaitMs': 1500}
assert summary['process_logs_with_egl_error'] == 12
assert summary['shader_cache_warning_pairs_at_error_priority'] == 10
ios_collection = next(collection for collection in manifest['collections'] if collection['id'] == NEW_ROOTS[2])
assert ios_collection['tests'] == ios_review['cases']
assert Counter(test['result'] for test in ios_collection['tests']) == {'Failure': 4, 'Success': 1}
assert ios_collection['normal_2d_initial_reveal']['visible_height_logical_points'] == 31
assert ios_collection['normal_2d_initial_reveal']['clipped_height_pixels'] == 75
assert 'Rejected and unapplied' in ios_collection['normal_text_v1_proposal_status']

freeze_paths = sorted(MUTABLE | {'docs/screenshots/' + path for path in new_record_paths | new_readmes})
freeze = [{'path': path, 'bytes': (REPO / path).stat().st_size, 'sha256': sha(REPO / path)}
          for path in freeze_paths]
freeze_path = Path('/tmp/partydeck-gallery-1717-freeze.json')
write_new(freeze_path, freeze)
validation = {
    **build,
    'prior_manifest_prefixes_unchanged': True,
    'prior_files_byte_unchanged': unchanged,
    'first_batch_files_byte_unchanged': first_batch,
    'new_sources_byte_identical': source_copies_verified,
    'all_original_pngs_decode': decoded_pngs,
    'all_checksum_entries_verified': len(checksums),
    'local_links_checked': local_links,
    'new_original_file_thumbnails_checked': len(new_thumbnails),
    'design_review_protected_suffix_byte_unchanged': True,
    'design_review_protected_suffix_sha256': hashlib.sha256(
        PROTECTED_MARKER + current_design.split(PROTECTED_MARKER, 1)[1]).hexdigest(),
    'authored_text_whitespace_checks_passed': True,
    'no_derived_review_pngs_added': True,
    'no_apk_aab_pck_or_zip_binaries_added': True,
    'android_cases_passed': 4, 'android_entries_and_completed_exits': 12,
    'android_native_barriers_and_main_callbacks': 12, 'android_fallbacks': 0,
    'android_original_egl_errors_retained': 12, 'android_original_shader_warning_pairs_retained': 10,
    'android_runtime_originals_visually_reviewed': 76,
    'android_internal_review_sheets': 28,
    'desktop_originals_byte_matched_to_previously_reviewed_files': 22,
    'ios_originals_visually_reviewed': 35,
    'ios_internal_sheet_originals': 33, 'ios_direct_original_resolution_reviews': 2,
    'ios_internal_review_sheets': 12, 'ios_reference_test_failures_retained': 4,
    'ios_secure_exit_test_success_retained': True,
    'ios_original_xcresult_attachment_payloads_preserved': 394,
    'ios_normal_text_v1_proposal_rejected_and_unapplied': True,
    'historical_android_close_failures_unchanged': True,
    'freeze_files': len(freeze), 'freeze_sha256': sha(freeze_path),
    'new_application_executions': 0, 'new_builds_or_runtime_tests': 0, 'git_commands_run': 0,
}
validation_path = Path('/tmp/partydeck-gallery-1717-validation.json')
write_new(validation_path, validation)
handoff_path = Path('/tmp/partydeck-gallery-1717-handoff.json')
write_new(handoff_path, {
    'freeze_path': str(freeze_path), 'freeze_sha256': sha(freeze_path),
    'validation_path': str(validation_path), 'validation_sha256': sha(validation_path),
    'evidence_path_list': '/tmp/partydeck-gallery-1717-new-evidence-paths.txt',
    'evidence_path_list_sha256': sha('/tmp/partydeck-gallery-1717-new-evidence-paths.txt'),
    'manifest_sha256': sha(GALLERY / 'manifest.json'), 'freeze_files': len(freeze),
    'screenshots': len(manifest['screenshots']), 'evidence_files': len(manifest['evidence']),
    'checksum_entries': len(checksums), 'new_original_pngs': len(new_screenshots),
    'new_evidence_files': len(new_evidence), 'new_readme_pages': len(NEW_ROOTS),
    'no_git_commands_builds_or_app_executions': True,
    'tracked_changes_frozen_until_root_push_acknowledgment': True,
})
print(json.dumps(validation, indent=2))
print(json.dumps({'handoff_path': str(handoff_path), 'handoff_sha256': sha(handoff_path)}))
