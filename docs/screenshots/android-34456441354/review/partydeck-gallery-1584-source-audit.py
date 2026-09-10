"""Read frozen ordinary Android evidence; create inventories outside the gallery."""
import copy
import hashlib
import json
import re
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path('/root/projects/PartyDeck')
GALLERY = REPO / 'docs/screenshots'
BASE = REPO / 'artifacts/evidence-storage/android-production-native-34456441354'
API36 = Path('/tmp/partydeck-api36-independent-_pxljpkr/run-34457458638')
BASE_REPORTS = BASE / 'extracted/10144559609-android-jvm-reports'
API36_REPORTS = API36 / 'android-jvm-reports'
OUT = Path('/tmp/partydeck-gallery-1584-source-audit.json')
assert not OUT.exists()


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def evidence(path):
    path = Path(path)
    return {'source_original': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def verify_receipt(record):
    path = Path(record['path'])
    assert path.is_file() and sha(path) == record['sha256'], path
    assert path.stat().st_size == record['bytes'], path
    return evidence(path)


def contained(bounds, viewport):
    return viewport[0] <= bounds[0] < bounds[2] <= viewport[2] and viewport[1] <= bounds[1] < bounds[3] <= viewport[3]


def inside(point, bounds):
    return bounds[0] <= point[0] < bounds[2] and bounds[1] <= point[1] < bounds[3]


# Root has acknowledged that this exact prior freeze is published.
assert sha('/tmp/partydeck-gallery-1460-freeze.json') == '3d64379d527603f8908a37bffbf3882eb769dc019a593856f955af52f19e213c'
for record in read('/tmp/partydeck-gallery-1460-freeze.json'):
    path = REPO / record['path']
    assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256']
assert sha(GALLERY / 'manifest.json') == 'd257e913639a50150d3df666d81d60e47fd91f50116f9ff2e0fca144ecde0e4c'
old = read(GALLERY / 'manifest.json')
assert len(old['screenshots']) == 1460 and len(old['evidence']) == 3942
prior_hashes = {}
for record in old['screenshots']:
    prior_hashes.setdefault(record['sha256'], []).append(record['path'])
baseline = []
for path in sorted([p for p in GALLERY.rglob('*') if p.is_file()] + [REPO / 'godot/reviews/design-review.md']):
    baseline.append({'path': str(path.relative_to(REPO)), 'bytes': path.stat().st_size, 'sha256': sha(path)})
assert len(baseline) == 5482
snapshots = {
    '/tmp/partydeck-gallery-1584-baseline-files.json': (json.dumps(baseline, indent=2) + '\n').encode(),
    '/tmp/partydeck-gallery-before-1584.json': (GALLERY / 'manifest.json').read_bytes(),
    '/tmp/partydeck-gallery-before-1584-README.md': (GALLERY / 'README.md').read_bytes(),
    '/tmp/partydeck-gallery-before-1584-design-review.md': (REPO / 'godot/reviews/design-review.md').read_bytes(),
}
for name, content in snapshots.items():
    path = Path(name)
    assert not path.exists()
    path.write_bytes(content)

base_final_path = BASE / 'review/final-native-review-receipt.json'
api36_final_path = API36 / 'final-receipt.json'
assert sha(base_final_path) == 'c76db1070a6ffda93b78d8be966a27fc6579c9f9d5000130f714dcfe4931a202'
assert sha(api36_final_path) == '90646e74f95150462306d51bafcff50dbbf389b70bf1776e7e07395aea19728a'
base_final, api36_final = read(base_final_path), read(api36_final_path)
assert base_final['verdict'] == 'PASS' and base_final['job_conclusion'] == 'success'
assert api36_final['checks_passed'] == 23 and api36_final['checks_failed'] == 0
base_inventory = read(BASE / 'review/original-native-image-inventory.json')
assert sha(BASE / 'review/original-native-image-inventory.json') == 'd17286ee6cd1cae4861c015b3ca22bc6f6d63fee0a246f68dd0f61076ed0c916'
base_native_audit = read(BASE / 'review/native-runtime-audit.json')
assert sha(BASE / 'review/native-runtime-audit.json') == '90689999989d6b164acbcd60208f4fb213340d7b95a57011eeb31dd99dd5d178'
base_images_by_resolved_path = {str(Path(record['path']).resolve()): record for record in base_inventory['original_images']}
api36_images = read(API36 / 'screenshot-identities.json')
assert len(api36_images) == 60
for record in api36_images + read(API36 / 'runtime-evidence-identities.json'):
    verify_receipt(record)

batches = []
for run, api, root, reports, final in [
    ('34456441354', 35, BASE, BASE_REPORTS, base_final),
    ('34457458638', 36, API36, API36_REPORTS, api36_final),
]:
    native = reports / 'build/ci/android'
    revision = final['commit'] if api == 35 else final['head_sha']
    runtime = read(native / 'runtime-variants.json')
    display = read(native / 'display-configuration.json')
    preparation = read(native / 'preparation/preparation-result.json')
    assert runtime['passed'] and runtime['sameEmulatorBoot']
    assert runtime['debugExitCode'] == runtime['optimizedTestSignedExitCode'] == 0
    assert runtime['godotSessionSmoke']['requested'] is False
    assert display['actualAndroidApi'] == display['expectedAndroidApi'] == api
    assert display['guestApiVerified'] and display['displayVerified']
    assert display['expectedPhysicalSize'] == [720, 1600] and display['expectedDensityDpi'] == 280
    assert (native / 'android-api.log').read_text().strip() == str(api)
    assert preparation['passed'] and not preparation['reboot_attempted']
    assert len(preparation['attempts']) == 1
    assert preparation['attempts'][0]['passed'] and preparation['attempts'][0]['app_absent']

    archive = (Path(final['original_artifacts'][0]['archive_path']) if api == 35
               else Path(final['reports_archive']['path']))
    archive_digest = (final['original_artifacts'][0]['archive_sha256'] if api == 35
                      else final['reports_archive']['sha256'])
    assert sha(archive) == archive_digest
    published_digest = (final['original_artifacts'][0]['github_digest'] if api == 35
                        else read(root / 'artifact-download.json')['artifact']['digest'])
    assert published_digest == 'sha256:' + archive_digest
    members = []
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None
        for info in package.infolist():
            if info.is_dir():
                continue
            path = reports / info.filename
            assert path.is_file() and path.stat().st_size == info.file_size, path
            assert package.read(info) == path.read_bytes(), path
            members.append(info.filename)
    assert len(members) == 413

    captures, excluded, cases = [], [], []
    pngs = sorted(native.rglob('*.png'))
    assert len(pngs) == 63
    for path in pngs:
        relative = str(path.relative_to(native))
        if api == 35:
            original_identity = base_images_by_resolved_path[str(path.resolve())]
            original_path = Path(original_identity['path'])
            assert original_path.resolve() == path.resolve()
        else:
            original_path = path
            original_identity = next((record for record in api36_images if record['path'] == str(path)), None)
        record = evidence(original_path)
        with Image.open(path) as picture:
            picture.verify()
        with Image.open(path) as picture:
            picture.load()
            assert picture.format == 'PNG' and picture.size == (720, 1600)
        record.update(original_filename=path.name, width_px=720, height_px=1600,
                      relative_path=relative, source_revision=revision, source_revision_exact=True, ci_run=run)
        if original_identity is not None:
            assert record['sha256'] == original_identity['sha256'] and record['bytes'] == original_identity['bytes']
        if relative.startswith('preparation/'):
            record['reason'] = 'Pre-install Android Launcher; emulator preparation, not an app capture. Original retained outside gallery.'
            record['visual_classification'] = 'Launcher viewed in an internal final/preparation sheet.'
            excluded.append(record)
        else:
            record.update(variant=relative.split('/')[0], stage=path.stem,
                          font_scale=2.0 if path.stem.startswith('large-text-') or path.stem == 'final-screen' else 1.0,
                          prior_byte_identical_originals=prior_hashes.get(record['sha256'], []))
            dump = path.parent / ('last-ui.xml' if path.stem == 'final-screen' else path.stem + '.xml')
            assert dump.is_file() and ET.parse(dump).getroot().tag == 'hierarchy'
            record['ui_dump_source'] = str(dump)
            captures.append(record)
    assert len(captures) == 62 and len(excluded) == 1

    for variant in ['debug', 'optimized-test-signed']:
        folder = native / variant
        smoke = read(folder / 'smoke-result.json')
        assert smoke['passed'] and smoke['variant'] == variant
        assert not any(re.search(r'error|failure|diagnostic', key, re.I) for key in smoke)
        observations = smoke['observations']
        assert len(observations['screenshots']) == 30
        assert observations['large_text_font_scale'] == 2.0
        assert observations['persisted_switches'] == {
            'settings-sound': False, 'settings-haptics': False, 'settings-reduce-motion': True}
        assert observations['soft_ime_captures'] == ['join-name-soft-ime', 'large-text-join-name-soft-ime']
        assert {record['stage'] for record in captures if record['variant'] == variant} == set(observations['screenshots']) | {'final-screen'}
        geometry = [json.loads(line) for line in (folder / 'input-geometry.log').read_text().splitlines() if line.strip()]
        for item in geometry:
            bounds, viewport, coordinates = item['bounds'], item['viewport'], item['coordinates']
            assert item['display_size'] == [720, 1600] and item['rotation'] == 0
            assert contained(viewport, [0, 0, 720, 1600])
            if item['action'] == 'tap':
                point = [coordinates['x'], coordinates['y']]
                assert contained(bounds, viewport) and inside(point, bounds) and inside(point, viewport)
            else:
                assert item['action'] == 'swipe'
                assert all(inside(coordinates[end], viewport) for end in ['start', 'end'])
        assert [item['label'] for item in geometry if item['action'] == 'tap'] == [
            step[7:] for step in smoke['steps'] if step.startswith('Tapped ')]
        rules_taps = [item for item in geometry if item['label'] == 'rules-practice']
        assert [item['stage'] for item in rules_taps] == ['rules', 'large-text-rules']
        assert not any(item['action'] == 'tap' and item['label'] == 'game-play' and item['stage'] == 'large text' for item in geometry)
        if api == 35:
            package_identity = copy.deepcopy(final['packages'][variant])
            verify_receipt(package_identity)
            assert package_identity['sha256'] == smoke['apk_sha256']
            identity_scope = 'Gallery independently hashed the downloaded APK bytes and matched the executed-input receipt; original package reviewer evidence is retained.'
        else:
            package_identity = {'sha256': smoke['apk_sha256'], 'package_bytes_downloaded_for_gallery_review': False}
            assert smoke['apk_sha256'] == final['variants'][variant]['apk_sha256_from_executed_input_receipt']
            if variant == 'optimized-test-signed':
                signing = read(native / 'packages/runtime-package.json')
                assert smoke['apk_sha256'] in json.dumps(signing)
            identity_scope = 'Executed-input receipt identity; full package artifact was not downloaded. Optimized signing receipt agrees.'
        after_play = ET.parse(folder / 'practice-after-play.xml').getroot()
        cases.append({
            'variant': variant, 'passed': True, 'captures': 31, 'named_stages': list(observations['screenshots']),
            'recorded_steps': len(smoke['steps']), 'smoke_receipt': evidence(folder / 'smoke-result.json'),
            'apk_sha256': smoke['apk_sha256'], 'package_identity': package_identity, 'package_identity_scope': identity_scope,
            'input_record_count': len(geometry), 'input_actions': dict(Counter(item['action'] for item in geometry)),
            'input_geometry': evidence(folder / 'input-geometry.log'), 'all_input_geometry_valid': True,
            'tap_steps_match_geometry_in_order': True, 'rules_practice_taps': rules_taps,
            'large_text_play_submitted': False, 'observations': observations,
            'after_play_visible_text': [node.attrib['text'] for node in after_play.iter('node') if node.attrib.get('text')],
        })
    assert [case['input_record_count'] for case in cases] == ([67, 64] if api == 35 else [65, 63])

    native_evidence = [evidence(path) | {'relative_path': str(path.relative_to(native))}
                       for path in sorted(native.rglob('*'))
                       if path.is_file() and path.suffix != '.png' and 'avd' not in path.relative_to(native).parts]
    assert len(native_evidence) == 135
    junit = []
    for path in sorted(reports.rglob('TEST-*.xml')):
        suite = ET.parse(path).getroot()
        assert int(suite.attrib.get('failures', 0)) == int(suite.attrib.get('errors', 0)) == 0
        junit.append(evidence(path) | {'relative_path': str(path.relative_to(reports)),
                                      'recorded_tests': int(suite.attrib['tests']), 'actual_testcase_elements': len(suite.findall('testcase'))})
    assert len(junit) == 38

    metadata, source_files = [], []
    seen = set()

    def add_metadata(path):
        path = Path(path)
        assert path.is_file()
        if str(path.resolve()) in seen:
            return
        seen.add(str(path.resolve()))
        relative = str(path.relative_to(root)) if path.is_relative_to(root) else path.name
        metadata.append(evidence(path) | {'relative_path': 'provenance/' + relative})

    if api == 35:
        add_metadata(base_final_path)
        for record in final['receipt_references'] + [final['job_metadata'], final['original_job_log'], base_native_audit['builder']]:
            verify_receipt(record)
            add_metadata(record['path'])
        for artifact in final['original_artifacts']:
            assert sha(artifact['inventory_path']) == artifact['inventory_sha256']
            add_metadata(artifact['inventory_path'])
            add_metadata(artifact['source_metadata'])
        for relative in ['review/expected-routes.txt', 'review/contact-sheet-generation.log']:
            add_metadata(root / relative)
        source_receipt = read(root / 'source/source-receipt.json')
        assert source_receipt['commit'] == revision
        for record in source_receipt['files']:
            path = root / 'source' / record['path']
            assert sha(path) == record['sha256'] and path.stat().st_size == record['bytes']
            source_files.append(evidence(path) | {'repository_path': record['path']})
        # The exact same commit's immutable tarball provides an independent source match.
        pending_sources = {record['repository_path']: record for record in source_files}
        with tarfile.open('/tmp/partydeck-engine-ci/34456443339/source-dad1c11.tar.gz', 'r|gz') as archive_file:
            for member in archive_file:
                relative = member.name.partition('/')[2]
                if relative in pending_sources:
                    record = pending_sources.pop(relative)
                    stream = archive_file.extractfile(member)
                    assert stream is not None and stream.read() == Path(record['source_original']).read_bytes()
        assert not pending_sources
    else:
        for path in sorted(root.iterdir()):
            if path.is_file() and path.suffix in {'.json', '.md', '.py', '.log'}:
                add_metadata(path)
        for key in ['research_receipt', 'checkpoint_sources']:
            verify_receipt(final[key])
            add_metadata(final[key]['path'])
        for record in read(final['checkpoint_sources']['path']):
            assert record['source_revision'] == revision
            path = Path(record['snapshot_path'])
            assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256']
            source_files.append(evidence(path) | {'repository_path': record['repository_path']})
        for request in read(root / 'collection-requests.json'):
            assert request['exit_code'] == 0 and sha(request['file']) == request['sha256']
    harness = next(record for record in source_files if record['repository_path'] == 'scripts/smoke-android-ui.py')
    assert harness['sha256'] == '7d6cef007b3d4fb64c6aaaf2e55c3039dc02853332607ccba4a239bc8cd1e5f3'
    harness_text = Path(harness['source_original']).read_text()
    assert harness_text.index('smoke.diagnostics()') < harness_text.index('restore_errors = smoke.restore_environment()')
    final_diag_font = 2.0
    crash_pattern = r'FATAL EXCEPTION|\bFatal signal\b|\bANR in dev\.partydeck\.app\b|\bam_anr\b.*dev\.partydeck\.app|\bam_crash\b.*dev\.partydeck\.app'
    crash_matches = [{'path': str(path), 'line': number}
                     for path in native.rglob('*.log')
                     for number, line in enumerate(path.read_text(errors='replace').splitlines(), 1)
                     if re.search(crash_pattern, line, re.I)]
    failure_files = [str(path) for path in native.rglob('*') if path.is_file() and re.search(r'failure|error|invalid[-_]screencap', path.name, re.I)]
    assert not crash_matches and not failure_files
    batches.append({
        'run': run, 'api': api, 'source_revision': revision, 'source_revision_exact': True,
        'owner_frozen_receipt': evidence(base_final_path if api == 35 else api36_final_path),
        'source_root': str(native), 'report_root': str(reports),
        'archive': evidence(archive), 'archive_matches_published_digest': True,
        'archive_crc_passed': True, 'all_extracted_archive_members_byte_matched': len(members),
        'runtime': runtime, 'display': display, 'preparation': preparation,
        'captures': captures, 'excluded': excluded, 'cases': cases,
        'native_evidence': native_evidence, 'metadata': metadata, 'source_files': source_files, 'junit_reports': junit,
        'final_diagnostic_font_scale': final_diag_font,
        'final_diagnostics_precede_environment_restore_in_exact_harness': True,
        'crash_marker_scan': {'pattern': crash_pattern, 'matches': crash_matches}, 'failure_files': failure_files,
        'earlier_owner_visual_review': copy.deepcopy(base_native_audit['visual_review']) if api == 35 else {
            'scope': 'Owner verified screenshot identities and dimensions; did not visually review every original.'},
        'limits': final['qualification_limits'] if api == 35 else final['limits'],
    })

# Compose all 60 API36 route originals at unchanged dimensions for later visual inspection.
sheet_root = Path('/tmp/partydeck-gallery-visual-review/queued-android')
sheet_root.mkdir(parents=True, exist_ok=True)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 22)
review_sheets = []
api36_batch = batches[1]
for case in api36_batch['cases']:
    variant = case['variant']
    for offset in range(0, 30, 3):
        stages = case['named_stages'][offset:offset + 3]
        path = sheet_root / f'34457458638-{variant}-{offset // 3 + 1:02d}.png'
        assert not path.exists()
        sheet = Image.new('RGB', (2160, 1652), '#ffffff')
        draw = ImageDraw.Draw(sheet)
        originals = []
        for index, stage in enumerate(stages):
            original = Path(api36_batch['source_root']) / variant / (stage + '.png')
            with Image.open(original) as picture:
                sheet.paste(picture.convert('RGB'), (index * 720, 52))
            draw.text((index * 720 + 8, 6), variant + ' / ' + stage, font=font, fill='#111111')
            originals.append(str(original))
        sheet.save(path)
        review_sheets.append({'path': str(path), 'originals': originals, 'derived_review_sheet_only': True})

result = {
    'generated_utc': datetime.now(timezone.utc).isoformat(), 'reviewer': 'review_design',
    'baseline_published_commit_acknowledged_by_root': 'c0efda7',
    'batches': batches, 'new_originals': sum(len(batch['captures']) for batch in batches),
    'preparation_exclusions': sum(len(batch['excluded']) for batch in batches),
    'review_sheets': review_sheets,
    'scope': 'Read-only archive/source/image/input reconciliation; API35 owner visual review retained, later API36 image inspection recorded separately.',
    'new_application_executions': 0, 'new_builds_or_tests': 0, 'git_commands_run': 0,
}
assert result['new_originals'] == 124 and len(review_sheets) == 20
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'path': str(OUT), 'sha256': sha(OUT), 'new_originals': 124, 'preparation_exclusions': 2,
                  'review_sheets': len(review_sheets), 'batches': [
                      {'run': batch['run'], 'api': batch['api'], 'metadata': len(batch['metadata']),
                       'runtime_evidence': len(batch['native_evidence']), 'source_files': len(batch['source_files']),
                       'junit_reports': len(batch['junit_reports']), 'input_records': sum(case['input_record_count'] for case in batch['cases'])}
                      for batch in batches]}, indent=2))
