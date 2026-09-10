import ast
import collections
import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path('/root/projects/PartyDeck')
FRAME = Path('/tmp/partydeck-frame-reconciliation-packed-v1')
FRAME_SOURCE = Path('/tmp/partydeck-frame-reconciliation-v1')
FRAME_REVIEW = Path('/tmp/partydeck-frame-reconciliation-source-review-v1')
REVEAL = Path('/tmp/partydeck-2d-initial-reveal-investigation')
CI = Path('/tmp/partydeck-engine-ci/34446327045')
PCK = '0ed324c19016f28987d6294f915c107f62234670b149f73bab585af93e29ae6d'
REV = 'b7f2f4f2c2d03b8e599d4b0fc73bf2d35f6640eb'
OUT = Path('/tmp/partydeck-gallery-visual-review/after-1129')
OUT.mkdir(parents=True, exist_ok=True)
tree = ast.parse(Path('/tmp/partydeck-gallery-queued-source-audit.py').read_text())
helpers = {'sha', 'read', 'jsonl', 'original', 'png', 'sheets'}
module = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in helpers], type_ignores=[])
exec(compile(module, 'source-audit helpers only', 'exec'))
audit = {'frame': {}, 'focused': [], 'reveal': {}, 'desktop': {}, 'native_previews': [], 'review_sheets': []}

pack = CI / 'godot-comparison-runtime-apk/renderer/partydeck-last-light.pck'
assert sha(pack) == PCK and pack.stat().st_size == 1546216
namespace = {}
exec(compile((REPO / 'godot/tools/partydeck_pck.py').read_text(), 'PCK byte inspector', 'exec'), namespace)
pack_inventory = namespace['read_pack'](pack)
pack_receipt = read(pack.with_suffix('.receipt.json'))
assert pack_inventory == pack_receipt['pack']
audit['pack_identity'] = {'retained_matching_pack': original(pack),
    'later_ci_export_receipt': original(pack.with_suffix('.receipt.json')),
    'receipt_scope': 'Later exact CI export receipt; not the original dirty-tree local export receipt.',
    'all_pack_members_verified': len(pack_inventory['entries'])}


def desktop(source, expected_revision, dirty, name):
    report = read(source / 'report.json')
    assert report['sourceCommit'] == expected_revision and report['workingTreeDirty'] == dirty
    assert report['status'] == 'passed' and report['sameAuthorityTrace'] is True
    assert report['rendererArtifact']['sha256'] == PCK
    results = [read(source / mode / 'result.json') for mode in ['2d', '3d']]
    assert report['results'] == results and results[0]['authorityTrace'] == results[1]['authorityTrace']
    captures = []
    for mode, result in zip(['2d', '3d'], results):
        assert result['rendererExitCode'] == 0 and len(result['authorityTrace']) == 42
        assert [result[k] for k in ['viewerPlays', 'viewerChallenges', 'roundsAdvanced']] == [2, 2, 13]
        trace_sha = hashlib.sha256(json.dumps(result['authorityTrace'], separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        assert trace_sha == result['authorityTraceSha256'] == '79b5b2a6415a365d531da3488b7b87f1b2309f2b1208899ee5b4618da16be674'
        nested = {r['path']: r for r in result['captures']}
        records = []
        for p in sorted((source / mode).glob('*.png')):
            receipt = read(p.with_suffix('.receipt.json'))
            assert receipt == nested[str(p.relative_to(source))]
            for k in ['sourceCommit', 'workingTreeDirty', 'sourceFingerprintSha256', 'rendererArtifact', 'runStartedUtc']:
                assert receipt[k] == report[k]
            r = png(p)
            assert r['sha256'] == receipt['sha256']
            assert (r['width_px'], r['height_px']) == (receipt['width'], receipt['height']) == (430, 932)
            assert receipt['textScale'] == 1.0 and receipt['reduceMotion'] is True and receipt['seed'] == 2
            view = next(v for v in result['authorityTrace'] if v['revision'] == receipt['authorityRevision'])
            assert view['viewSha256'] == receipt['authorityViewSha256']
            old = REPO / 'docs/screenshots/godot-desktop-34439587132' / p.relative_to(source)
            if sha(old) == r['sha256']:
                r['previously_reviewed_identical_original'] = str(old.relative_to(REPO))
            r.update(mode=mode, receipt_source=str(p.with_suffix('.receipt.json')))
            records.append(r)
        audit['review_sheets'].extend(sheets(name + '-' + mode, records, source, width=430))
        captures.extend(records)
        assert not re.search(r'(?m)^\s*(SCRIPT ERROR|ERROR|Parse Error|Failed to load script)', (source / mode / 'godot.log').read_text())
    assert len(captures) == 22
    return {'source_directory': str(source), 'source_revision': expected_revision, 'working_tree_dirty': dirty,
        'source_revision_exact': not dirty, 'source_fingerprint_sha256': report['sourceFingerprintSha256'],
        'report': original(source / 'report.json'), 'captures': captures, 'authority_trace_sha256': trace_sha,
        'evidence': [original(p) for p in sorted(source.rglob('*')) if p.is_file() and p.suffix != '.png']}


audit['frame'] = desktop(FRAME / 'authority', '86ca7f56f7ebbc3e64e4d49da82d5d667535098e', True, 'frame-authority')
assert audit['frame']['source_fingerprint_sha256'] == '835e074f96bd9edd9bc351d2dec436381b2a5160e1f1a845b1367eda86eb45af'
assert read(FRAME / 'basis.json')['packSha256'] == PCK
assert read(FRAME / 'handoff.json')['capturedImages'] == 37
assert sha(FRAME / 'native_bridge_check.gd') == read(FRAME / 'basis.json')['checkerSha256']
for root in [FRAME, FRAME_SOURCE]:
    report = read(root / 'native-bridge/report.json')
    assert report['result'] == 'passed' and len(report['checks']) == 111
    assert not re.search(r'(?m)^\s*(SCRIPT ERROR|ERROR|Parse Error|Failed to load script)', (root / 'runtime.log').read_text())
source_basis = read(FRAME_SOURCE / 'basis.json')
for rel, expected in source_basis['sourceSha256'].items():
    assert sha(FRAME_SOURCE / 'source' / rel) == expected
    assert sha(CI / 'source-b7f2f4f/godot/renderer' / rel) == expected
for r in read(FRAME_REVIEW / 'provenance.json')['files']:
    p = FRAME_REVIEW / r['path']
    assert sha(p) == r['sha256'] and p.stat().st_size == r['bytes']
audit['frame']['supporting_evidence'] = [original(p) for p in sorted(FRAME.rglob('*')) if p.is_file()
    and not p.is_relative_to(FRAME / 'authority') and not p.is_relative_to(FRAME / 'focused-3d')]
audit['frame']['source_evidence'] = [original(p) for p in sorted(FRAME_SOURCE.rglob('*')) if p.is_file()]
audit['frame']['review_evidence'] = [original(p) for p in sorted(FRAME_REVIEW.rglob('*')) if p.is_file()]

for case, expected_count in [('large-text-touch', 7), ('six-long-names-large-text', 8)]:
    source = FRAME / 'focused-3d' / case
    basis = read(source / 'basis.json')
    report = read(source / 'report.json')
    hashes = read(source / 'image-hashes.json')
    assert basis['packSha256'] == PCK
    assert sha(FRAME / 'focused-3d/three_d_scene_check.gd') == basis['checkerSha256']
    assert sha(source / 'fixture.json') == basis['fixtureSha256']
    assert report['result'] == 'passed' and [report[k] for k in ['width', 'height', 'textScale']] == [320, 740, 2]
    assert not re.search(r'(?m)^\s*(SCRIPT ERROR|ERROR|Parse Error|Failed to load script)', (source / 'runtime.log').read_text())
    observed = {Path(o['capture']).name: o['diagnostics'] for o in report['observations'] if 'capture' in o}
    captures = []
    for p in sorted(source.glob('*.png')):
        r = png(p)
        assert r['sha256'] == hashes[p.name] and (r['width_px'], r['height_px']) == (320, 740)
        diagnostic = read(p.with_suffix('.json'))
        assert diagnostic == observed[p.name]
        if p.stem in ['01-concealed', '03-covered-again', '04-resumed-covered']:
            assert all(diagnostic[k] == 0 for k in ['privateFaceCount', 'privateLabelCount', 'selectedCount'])
        if p.stem == '02-revealed-selected':
            assert diagnostic['selectedCount'] == 2
        if p.stem == '02a-selection-limit':
            assert diagnostic['selectedCount'] == 3
        if p.stem == '02b-deselected-last':
            assert diagnostic['selectedCount'] == 2
        r.update(case=case, metrics_source=str(p.with_suffix('.json')), diagnostics=diagnostic)
        captures.append(r)
    assert len(captures) == len(hashes) == expected_count
    gesture = read(source / 'gesture-diagnostics.json')
    assert gesture['selectedCount'] == 0 and gesture['authorityEvents'] == 1 and gesture['touchscreenReported'] is True
    audit['focused'].append({'case': case, 'source_directory': str(source), 'captures': captures,
        'evidence': [original(p) for p in sorted(source.iterdir()) if p.is_file() and p.suffix != '.png'],
        'fixture_source': str(source / 'fixture.json'), 'report_source': str(source / 'report.json')})
    audit['review_sheets'].extend(sheets('frame-focused-' + case, captures, source, width=480))
audit['focused_checker'] = original(FRAME / 'focused-3d/three_d_scene_check.gd')

receipt = REVEAL / 'receipt-v1/provenance.json'
assert sha(receipt) == 'bf1ab4dcd4dc30cb7d8e4154d72712c90fef2dffd573c34cd7f882979e1f4df8'
assert sha(REVEAL / 'receipt-v1/investigation.md') == '0674e1e92a175923923068abcaa051c818668df392c7301d86eae7ac9a0323d6'
provenance = read(receipt)
assert len(provenance['files']) == 100 and provenance['newOriginalScreenshotCount'] == 17
for r in provenance['files']:
    p = REVEAL / r['path']
    assert sha(p) == r['sha256'] and p.stat().st_size == r['bytes'], str(p)
for r in provenance['nativeOriginals']:
    assert (REVEAL / r['path']).read_bytes() == Path(r['originalPath']).read_bytes()
snapshot = read(REVEAL / 'frame-v1-source-manifest.json')
differences = []
for r in snapshot['files']:
    before = REVEAL / 'frame-v1-source' / r['path']
    after = REVEAL / 'compact-surface-source' / r['path']
    assert sha(before) == r['sha256'] and before.stat().st_size == r['bytes']
    if sha(after) != r['sha256']:
        differences.append(r['path'])
assert differences == ['presentations/two_d/table.gd']
assert sha(REVEAL / 'compact-surface-source/presentations/two_d/table.gd') == '8d8650c8b6b6c5c5052b798e540d0b618dc2d916d7fdda0c95011eac6412f993'
for r in read(REVEAL / 'authority-libraries.json')['libraries']:
    p = REVEAL / 'authority-libraries' / r['name']
    assert sha(p) == r['sha256'] and p.stat().st_size == r['bytes']
launch = read(REVEAL / 'launch-font-1.0.json')
host_launch = read(REVEAL / 'launch-native-host-font-1.0.json')
assert launch['payload']['game'] == host_launch['payload']['game']
assert launch['payload']['controls']['canReturnToLobby'] is False
assert host_launch['payload']['controls']['canReturnToLobby'] is True
assert {k:v for k,v in launch['payload']['controls'].items() if k != 'canReturnToLobby'} == {k:v for k,v in host_launch['payload']['controls'].items() if k != 'canReturnToLobby'}
known_inputs = {sha(REVEAL / r['path']): str(REVEAL / r['path']) for r in provenance['files'] if not r['path'].endswith('.png')}
known_inputs.update({sha(FRAME_SOURCE / 'source' / rel): str(FRAME_SOURCE / 'source' / rel) for rel in source_basis['sourceSha256']})
input_verifications = []
for case in provenance['caseResults']:
    source = REVEAL / case['case']
    result = read(source / 'result.json')
    assert result['completed'] == case['completed'] and result['exitCode'] == case['exitCode']
    for r in result['inputs']:
        p = Path(r['path'])
        if p.is_file() and sha(p) == r['sha256']:
            input_verifications.append({'recorded_path': str(p), 'matched_path': str(p), 'sha256': r['sha256']})
        else:
            assert r['sha256'] in known_inputs, r
            input_verifications.append({'recorded_path': str(p), 'matched_path': known_inputs[r['sha256']], 'sha256': r['sha256']})
    for r in result['evidence']:
        p = source / r['path']
        assert sha(p) == r['sha256'] and p.stat().st_size == r['sizeBytes']
captures = []
for r in provenance['newOriginalScreenshots']:
    p = REVEAL / r['path']
    capture = png(p)
    assert capture['sha256'] == r['sha256'] and [capture['width_px'], capture['height_px']] == r['dimensions']
    diagnostic = read(p.with_suffix('.json'))
    extra = {}
    if p.stem in ['01-early', '02-late']:
        observation = next(o for o in read(p.parent / 'observations.json') if o['name'] == p.stem)
        reveal = next(c for c in diagnostic['controls'] if c['group'] == 'partydeck_action_reveal')
        assert observation['revealRect'] == reveal['rect'] and observation['clipRect'] == reveal['clipRect']
        assert observation['scrollOffset'] == 0
        assert observation['processFrameCallbacksSinceLaunch'] == (4 if p.stem == '01-early' else 60)
        if r['case'] == 'baseline-font-1.0':
            assert reveal['rect'] == [32, 512, 339, 56] and observation['bottomOverflow'] == 4
            assert not observation['revealFullyVisible'] and not observation['coverFullyVisible']
        elif r['case'] == 'compact-surface-font-1.0':
            assert reveal['rect'] == [32, 488, 339, 56] and observation['bottomOverflow'] == 0
            assert observation['revealFullyVisible'] and observation['coverFullyVisible']
            assert observation['clipRect'][1] + observation['clipRect'][3] - observation['coverRect'][1] - observation['coverRect'][3] == 8
        else:
            assert capture['sha256'] == 'b1ae240dd4575fc003a9b14c5b8f5b232c767cbbe9facb5a2a6e2c7930721e0b'
        extra['observation'] = observation
    capture.update(case=r['case'], case_passed=r['casePassed'], metrics_source=str(p.with_suffix('.json')),
        diagnostics=diagnostic, **extra)
    captures.append(capture)
assert len(captures) == 17
audit['reveal'] = {'source_directory': str(REVEAL), 'provenance': original(receipt),
    'captures': captures, 'cases': provenance['caseResults'], 'verified_inventory_files': 100,
    'source_snapshot_files_verified': 151, 'source_differences': differences,
    'input_verifications': input_verifications,
    'existing_native_copies_verified': provenance['nativeOriginals'],
    'evidence': [original(REVEAL / r['path']) for r in provenance['files'] if not r['path'].endswith('.png')
        and not r['path'].startswith('receipt-v1/native-originals/')] + [original(receipt)]}
for case in provenance['caseResults']:
    rs = [r for r in captures if r['case'] == case['case']]
    audit['review_sheets'].extend(sheets('reveal-' + case['case'], rs, REVEAL, width=480))

assert sha(CI / 'producer-evidence-summary.json') == 'b1990ff97f30d847105def6f79edf57ea2c7d75b4c54da602e5b23393e145988'
audit['desktop'] = desktop(CI / 'godot-comparison-builds/godot/qualification/build/ci/desktop', REV, False, 'ci-desktop')
for mode in ['2d', '3d']:
    for scale in ['1.0', '2.0']:
        source = CI / f'godot-android-{mode}-font-{scale}-debug/android/runtime'
        captures = [png(p) for p in sorted(source.rglob('*.png'))]
        audit['native_previews'].append({'mode': mode, 'font_scale': float(scale), 'source_directory': str(source), 'captures': captures})
        audit['review_sheets'].extend(sheets(f'native-{mode}-{scale}', captures, source, width=480))
assert sum(len(c['captures']) for c in audit['native_previews']) == 74
Path('/tmp/partydeck-gallery-1279-local-source-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
print(json.dumps({'local_authority_pngs': len(audit['frame']['captures']),
    'focused_pngs': sum(len(c['captures']) for c in audit['focused']), 'reveal_pngs': len(audit['reveal']['captures']),
    'ci_desktop_pngs': len(audit['desktop']['captures']), 'native_preview_pngs': 74,
    'local_authority_pixels_matching_prior': sum('previously_reviewed_identical_original' in r for r in audit['frame']['captures']),
    'ci_desktop_pixels_matching_prior': sum('previously_reviewed_identical_original' in r for r in audit['desktop']['captures']),
    'internal_review_sheets': len(audit['review_sheets']), 'tracked_files_written': 0}, indent=2))
