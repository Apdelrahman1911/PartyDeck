"""Bind the reviewer's 18 actual original-image observations and inventory all PNGs."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from runtime_audit_helpers_v2 import png_dimensions

ROOT = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34503251315')
REPORTS = ROOT / 'android-jvm-reports'
NATIVE = REPORTS / 'build/ci/android'
HEAD = '1cd34a36753ed0112e6684f6525592dab8ef2edb'


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': sha256(data).hexdigest()}


def read(path):
    return json.loads(path.read_text())


def save(name, value):
    path = ROOT / 'review' / name
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    return identity(path)


audit = read(ROOT / 'review/runtime-capture-audit.json')
assert audit['runId'] == 34503251315 and audit['headSha'] == HEAD
manifest = {v['path']: v for v in read(ROOT / 'android-jvm-reports.files.json')}
metadata = {}
for variant, result in audit['variants'].items():
    for capture in result['captures']:
        original = read(Path(capture['receipt']['path']))
        metadata[capture['png']['path']] = {
            'category': 'native-session', 'variant': variant, 'stage': capture['stage'],
            'captureName': capture['name'], 'xml': capture['xml'], 'json': capture['receipt'],
            'captureResult': original['status'], 'nativeVariantPassed': result['finalCheckStatus'] == 'passed',
            'captureStartedUtc': original['started_utc'], 'captureEndedUtc': original['ended_utc'],
            'before': original['before'], 'after': original['after'],
        }

# These observations were made by the reviewer using view_image at original detail
# immediately before this script was written; this script does not perform a visual review.
viewed = {}
for variant in ('debug', 'optimized-test-signed'):
    for mode in ('2d', '3d'):
        viewed[variant + '/' + mode + '-entry-native-ready'] = (
            'Visible 2D table, Table ready/native return controls, public claim and concealed hand panel. No private card face is visible.'
            if mode == '2d' else
            'Visible 3D table, Table ready/native return controls and five face-down hand cards. No private card face is visible.')
        viewed[variant + '/' + mode + '-recents-system-ui'] = (
            'Recents shows the PartyDeck task covered by Your cards stay private, with native return controls visible. Engine pixels and private card faces are covered.')
        viewed[variant + '/' + mode + '-home-system-ui'] = (
            'Android launcher Home is visible. No PartyDeck table or private card face is visible.')
        viewed[variant + '/' + mode + '-standard-concealed'] = (
            'Returned Standard table shows the concealed Your hand panel, Show hand and disabled Select cards. No private card face is visible.')
for mode in ('2d', '3d'):
    viewed['debug/' + mode + '-death-return-concealed'] = (
        'After the recorded guarded renderer signal, Standard shows the concealed hand panel, Show hand and disabled Select cards. No private card face is visible.')
design_notes = {key: 'Round 1 reveal is partially clipped at the public-panel lower boundary in this still. This may be the scroll viewport; interaction visibility is not established by this image.'
                for key in ('debug/3d-standard-concealed', 'debug/3d-death-return-concealed',
                            'optimized-test-signed/2d-standard-concealed')}
visual_rows = []
for path, data in metadata.items():
    key = data['variant'] + '/' + data['captureName']
    if key in viewed:
        actual = identity(Path(path))
        frozen = manifest[Path(path).relative_to(REPORTS).as_posix()]
        assert (actual['bytes'], actual['sha256']) == (frozen['bytes'], frozen['sha256'])
        visual_rows.append({'key': key, 'png': actual, 'xml': data['xml'], 'captureJson': data['json'],
                            'dimensions': png_dimensions(Path(path)), 'viewedOriginal': True,
                            'tool': 'view_image', 'requestedDetail': 'original',
                            'observation': viewed[key], 'designObservation': design_notes.get(key)})
assert {v['key'] for v in visual_rows} == set(viewed) and len(visual_rows) == 18
visual = save('original-visual-review.json', {
    'runId': 34503251315, 'headSha': HEAD, 'recordedAtUtc': datetime.now(timezone.utc).isoformat(),
    'reviewer': '/root/review_release', 'originalViewCount': len(visual_rows), 'derivedViewCount': 0,
    'images': visual_rows, 'runtimeCaptureAudit': identity(ROOT / 'review/runtime-capture-audit.json'),
    'scope': 'The reviewer directly viewed these 18 current original PNGs at original detail. This script binds those recorded observations to the frozen bytes; it does not create images or automate pixel judgments. Other PNGs are inventoried without claiming they were viewed.',
    'limits': ['Selected stills establish only their visible state, not continuous transition privacy.',
               'API35 engine gameplay was not invoked. No TalkBack speech/traversal, physical-device or distribution-signing claim.',
               'Three partial public-panel label observations were handed to review_design without asserting an interaction defect.'],
    'auditScript': identity(Path(__file__)),
})
for variant in ('debug', 'optimized-test-signed'):
    directory = NATIVE / variant
    result_path = directory / 'smoke-result.json'
    result = read(result_path)
    assert result['passed']
    for png in directory.glob('*.png'):
        xml = png.with_suffix('.xml')
        if not xml.exists():
            assert png.name == 'final-screen.png'
            xml = directory / 'last-ui.xml'
        ET.fromstring(xml.read_bytes())
        metadata[str(png)] = {'category': 'ordinary-ui', 'variant': variant,
            'xml': identity(xml), 'json': identity(result_path), 'ordinaryVariantPassed': result['passed'],
            'association': 'Named PNG/XML pair; final-screen.png uses the retained last-ui.xml.'}
images = []
for png in sorted(REPORTS.rglob('*.png')):
    actual = identity(png)
    frozen = manifest[png.relative_to(REPORTS).as_posix()]
    assert (actual['bytes'], actual['sha256']) == (frozen['bytes'], frozen['sha256'])
    data = metadata.get(str(png))
    if data is None and 'ui-snapshots' in png.parts:
        data = {'category': 'compose-jvm-snapshot', 'xml': None, 'json': None}
    elif data is None:
        assert png.is_relative_to(NATIVE / 'preparation'), png
        xml, receipt = png.parent / 'last-ui.xml', png.parent / 'preparation-attempt.json'
        data = {'category': 'emulator-preparation', 'xml': identity(xml) if xml.exists() else None,
                'json': identity(receipt) if receipt.exists() else None}
    key = data.get('variant', '') + '/' + png.stem
    viewed_original = data['category'] == 'native-session' and key in viewed
    images.append({'png': actual, 'dimensions': png_dimensions(png), **data,
                   'viewedOriginal': viewed_original,
                   'visualObservation': viewed.get(key) if viewed_original else None,
                   'designObservation': design_notes.get(key) if viewed_original else None})
assert sum(v['viewedOriginal'] for v in images) == len(visual_rows)
mapping = save('capture-gallery-mapping.json', {
    'runId': 34503251315, 'headSha': HEAD, 'sourceRoot': str(REPORTS),
    'originalFreeze': identity(ROOT / 'original-collection-frozen.json'),
    'runtimeAudit': identity(ROOT / 'review/runtime-capture-audit.json'),
    'runtimeTriage': identity(ROOT / 'review/runtime-result-triage.json'),
    'packageAudit': identity(ROOT / 'review/package-audit.json'), 'originalVisualReview': visual,
    'images': images, 'imageCount': len(images), 'categories': dict(Counter(v['category'] for v in images)),
    'viewedOriginalCount': len(visual_rows), 'viewedDerivedCount': 0,
    'outcomes': {'ordinaryDebug': 'passed', 'ordinaryOptimized': 'passed',
                 'nativeDebug': '21 checks passed, including two guarded renderer-death checks',
                 'nativeOptimized': '19 checks passed; two renderer-death checks explicitly skipped'},
    'limits': ['Only the 18 listed originals were viewed by this reviewer; remaining rows attest integrity/provenance.',
               'Sequential PNG/XML captures are not atomic and do not establish continuous privacy.',
               'Native Ready/lifecycle and Standard actions do not establish API35 engine gameplay or TalkBack speech.',
               'Compose JVM snapshots and emulator preparation images retain their separate origins.',
               'No derived image was created or viewed.'],
})
print(json.dumps({'visualReview': visual, 'galleryMapping': mapping, 'imageCount': len(images),
                  'categories': dict(Counter(v['category'] for v in images)), 'viewedOriginalCount': len(visual_rows)}, indent=2))
