"""Read actual decoded manifests and independently parse retained Standard XML."""
import ast
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34503251315')
NATIVE = ROOT / 'android-jvm-reports/build/ci/android'
PACKAGE = 'dev.partydeck.app'
HEAD = '1cd34a36753ed0112e6684f6525592dab8ef2edb'


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': sha256(data).hexdigest()}


def read(path):
    return json.loads(path.read_text())


def save(name, value):
    path = ROOT / 'review' / name
    with path.open('x') as stream:
        json.dump({'runId': 34503251315, 'headSha': HEAD,
                   'createdAtUtc': datetime.now(timezone.utc).isoformat(),
                   'auditScript': identity(Path(__file__)), **value}, stream, indent=2)
        stream.write('\n')
    return identity(path)


# Reuse only our pure aapt2-text parser definition, without executing the tool runner.
parser_source = ROOT / 'audit-scripts/audit-ci-packages.py'
definition = next(n for n in ast.parse(parser_source.read_text()).body
                  if isinstance(n, ast.FunctionDef) and n.name == 'dump_tree')
namespace = {'re': re, 'json': json}
exec(compile(ast.Module(body=[definition], type_ignores=[]), str(parser_source), 'exec'), namespace)
packages = read(ROOT / 'review/package-audit.json')['packages']
expected = {'dev.partydeck.GODOT_ACTIVATION_PROFILE': 'qualification',
            'dev.partydeck.GODOT_PRESENTATION_MODES': '2d,3d'}
build_path = NATIVE / 'godot-activation-build.json'
assert read(build_path) == {'schemaVersion': 1, 'profile': 'qualification', 'modesCsv': '2d,3d'}
activation_rows = {}
for variant in ('debug', 'unsigned-release', 'optimized-test-signed'):
    dump_path = ROOT / 'review/package-tools' / (variant + '-manifest.stdout')
    assert identity(dump_path) == packages[variant]['commands']['manifest']['stdout']
    manifest = namespace['dump_tree'](dump_path.read_text())
    app = next(v for v in manifest['children'] if v['tag'] == 'application')
    metadata = [v['attrs'] for v in app['children'] if v['tag'] == 'meta-data'
                and v['attrs'].get('name') in expected]
    assert len(metadata) == len(expected)
    assert {v['name']: v['value'] for v in metadata} == expected
    row = {'actualApk': packages[variant]['artifact'], 'independentBinaryManifestDump': identity(dump_path),
           'actualMetadata': {v['name']: v['value'] for v in metadata}}
    if variant != 'unsigned-release':
        directory = NATIVE / 'godot-session' / variant
        inputs = read(directory / 'package-inputs.json')
        xml_path = directory / 'packaged-manifest.xml'
        assert identity(xml_path)['sha256'] == inputs['activation']['manifestSha256']
        xml = ET.fromstring(xml_path.read_bytes())
        ns = '{http://schemas.android.com/apk/res/android}'
        entries = [n for n in xml.findall('application/meta-data') if n.get(ns + 'name') in expected]
        assert len(entries) == len(expected)
        assert {n.get(ns + 'name'): n.get(ns + 'value') for n in entries} == expected
        intent = directory / 'activation-build-expectation.json'
        assert intent.read_bytes() == build_path.read_bytes()
        assert identity(intent)['sha256'] == inputs['activation']['expectationSha256']
        assert inputs['apkSha256'] == packages[variant]['artifact']['sha256']
        assert inputs['packSha256'] == inputs['embeddedPackSha256'] == packages[variant]['pck']['sha256']
        assert inputs['activation']['manifestCommandExitCode'] == 0 and inputs['activation']['verified']
        if variant == 'optimized-test-signed':
            assert inputs['originalUnsignedSha256'] == packages['unsigned-release']['artifact']['sha256']
            assert [inputs['certificateSha256']] == packages[variant]['signer_certificate_sha256']
        row.update(originalPreExecutionManifest=identity(xml_path), buildIntent=identity(intent),
                   packageInputs=identity(directory / 'package-inputs.json'))
    activation_rows[variant] = row
activation = save('packaged-activation-audit.json', {
    'result': 'pass', 'buildIntent': identity(build_path), 'variants': activation_rows,
    'pureBinaryManifestParserSource': identity(parser_source),
    'scope': 'Independent decoding outputs from actual APK inspection agree with original pre-execution manifests and build intent: qualification profile, 2d and 3d modes. Current APK, pack and optimized signing identities match. No APK executed by this reviewer.',
})


def tag(nodes, name):
    found = [n for n in nodes if n.get('resource-id', '').rsplit('/', 1)[-1] == name]
    assert len(found) == 1, name
    return found[0]


def labels(node):
    return {n.get(k) for n in node.iter('node') for k in ('text', 'content-desc') if n.get(k)}


def card(node):
    descriptions = [m for n in node.iter('node')
                    if (m := re.fullmatch(r'(Crown|Moon|Star|Wild)\. Card (\d+) of (\d+)\.', n.get('content-desc', '')))]
    assert len(descriptions) == 1
    m = descriptions[0]
    return {'rank': m[1], 'index': int(m[2]) - 1, 'hand_count': int(m[3]),
            **{k: node.get(k) == 'true' for k in ('checkable', 'checked', 'clickable')}}


standard_rows = {}
for variant in ('debug', 'optimized-test-signed'):
    runtime = NATIVE / 'godot-session' / variant / 'runtime'
    result = read(runtime / 'godot-session-result.json')
    rows = []
    for path in sorted((runtime / 'captures').glob('*.json')):
        receipt = read(path)
        if 'observation' not in receipt:
            continue
        xml_path = runtime / receipt['file']
        assert identity(xml_path)['sha256'] == receipt['sha256']
        root = ET.fromstring(xml_path.read_bytes())
        nodes = [n for n in root.iter('node') if n.get('package') == PACKAGE]
        text = {n.get(k) for n in nodes for k in ('text', 'content-desc') if n.get(k)}
        value = receipt['observation']
        mode = path.stem.split('-', 1)[0]
        checked = []
        if set(value) == {'checkable', 'checked', 'clickable', 'hand_count', 'index', 'rank'}:
            assert card(tag(nodes, 'game-card-' + str(value['index']))) == value
            checked = ['indexed card rank/count', 'checkable/checked/clickable attributes']
        elif set(value) == {'maximum', 'selected'}:
            matches = {(int(m[1]), int(m[2])) for v in text
                       if (m := re.fullmatch(r'(\d+) of (\d+) selected', v))}
            assert matches == {(value['selected'], value['maximum'])}
            checked = ['selected count and maximum']
        elif set(value) == {'enabled', 'label'}:
            button = tag(nodes, 'game-play')
            assert (button.get('enabled') == 'true') == value['enabled'] and value['label'] in labels(button)
            checked = ['Play label and enabled attribute']
        elif set(value) == {'limit', 'text'}:
            assert value['text'] in text
            checked = ['selection-limit feedback text; no speech/live-region assertion']
        elif set(value) == {'play_enabled'}:
            assert (tag(nodes, 'game-play').get('enabled') == 'true') == value['play_enabled']
            checked = ['hidden-hand Play enabled attribute']
        elif set(value) == {'private_nodes'}:
            private = [n for n in nodes if n.get('resource-id', '').rsplit('/', 1)[-1].startswith('game-card-')
                       or re.search(r'\b(?:Crown|Moon|Star|Wild)\. Card \d+ of \d+\.', n.get('content-desc', ''))]
            assert len(private) == value['private_nodes'] == 0
            checked = ['absence of private-card nodes/descriptions']
        elif set(value) == {'before', 'label'}:
            button = tag(nodes, 'game-play')
            assert value['label'] in labels(button) and button.get('enabled') == 'true'
            continuity = result['checks'][mode + '.standard-action']['observable_continuity']
            assert value['before'] == {k: continuity[k] for k in ('first_card', 'public')}
            checked = ['enabled Play input label', 'baseline identity bound to the original result check']
        elif value.get('kind') == 'recipient hand decreased by one':
            cards = [card(n) for n in nodes if re.fullmatch(r'game-card-\d+', n.get('resource-id', '').rsplit('/', 1)[-1])]
            observed = sorted([{k: v[k] for k in ('hand_count', 'index', 'rank')} for v in cards], key=lambda v: v['index'])
            assert observed == value['visible_indexed_cards']
            assert value['after_count'] == value['before_count'] - 1
            assert all(v['hand_count'] == value['after_count'] for v in observed)
            assert value['before_count'] == result['checks'][mode + '.standard-action']['observable_continuity']['first_card']['hand_count']
            checked = ['retained indexed card/count labels', 'one-card decrease relative to bound baseline']
        elif value.get('kind') == 'same-round public result':
            assert {value[k] for k in ('challenge', 'claim', 'verdict')} | {'ROUND ' + str(value['round'])} <= text
            assert value['round'] == result['checks'][mode + '.standard-action']['observable_continuity']['public']['round']
            checked = ['public challenge/claim/verdict/round text', 'same round as bound baseline']
        else:
            raise AssertionError((variant, path.name, value))
        rows.append({'receipt': identity(path), 'xml': identity(xml_path), 'observed': value,
                     'independentlyChecked': checked})
    assert len(rows) == read(ROOT / 'review/runtime-capture-audit.json')['variants'][variant]['originalStandardUiObservationCount']
    standard_rows[variant] = rows
standard = save('standard-ui-xml-audit.json', {
    'result': 'pass', 'observationCounts': {v: len(rows) for v, rows in standard_rows.items()},
    'variants': standard_rows,
    'scope': 'Independent XML parsing of every original Standard observation. Checks rank/index/count descriptions, selection flags/count/limit text, Play labels/enabled state, concealment semantics and visible post-Play outcome labels. Before-state identities are tied to original result checks, whose captures are separately hash/process bound. This is UI evidence; no authority receipt, TalkBack speech/traversal, focus recording, live-region delivery or native-engine gameplay is inferred.',
})
print(json.dumps({'activationAudit': activation, 'standardUiAudit': standard,
                  'standardObservations': {v: len(rows) for v, rows in standard_rows.items()}}, indent=2))
