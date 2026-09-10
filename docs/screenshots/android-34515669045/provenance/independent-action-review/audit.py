"""Independent bounded review of original Android action XML/JSON; no app execution."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
EVIDENCE = Path('/root/projects/PartyDeck/artifacts/evidence-storage')
CURRENT = EVIDENCE / '34515669045'
OLD = EVIDENCE / '34506173394'
SOURCE = EVIDENCE / 'source-0f00f17/source-0f00f17'
OLD_SOURCE = EVIDENCE / 'source-d06f83a/source-d06f83a'
PACKAGE = 'dev.partydeck.app'
MAIN = PACKAGE + '/' + PACKAGE + '.MainActivity'
NATIVE = PACKAGE + '/' + PACKAGE + '.godot.SessionGodotActivity'

def pin(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

def read(path):
    return json.loads(path.read_bytes())

def key(node):
    return node.get('resource-id', '').rsplit('/', 1)[-1]

def nodes(root, tag):
    return [node for node in root.iter('node') if node.get('package') == PACKAGE and key(node) == tag]

def single(root, tag):
    matches = nodes(root, tag)
    assert len(matches) == 1, (tag, len(matches))
    return matches[0]

def rect(node):
    match = re.fullmatch(r'\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]', node.get('bounds', ''))
    assert match
    return tuple(map(int, match.groups()))

def visible(root, node, display=(720, 1600)):
    x1, y1, x2, y2 = rect(node)
    if not (0 <= x1 < x2 <= display[0] and 0 <= y1 < y2 <= display[1]):
        return False
    parents = {child: parent for parent in root.iter() for child in parent}
    ancestor = parents.get(node)
    while ancestor is not None:
        if ancestor.get('scrollable') == 'true' or ancestor.get('class') in ['android.widget.ScrollView', 'android.widget.HorizontalScrollView', 'androidx.core.widget.NestedScrollView']:
            ax1, ay1, ax2, ay2 = rect(ancestor)
            if not (ax1 <= x1 and ay1 <= y1 and x2 <= ax2 and y2 <= ay2):
                return False
        ancestor = parents.get(ancestor)
    return True

def text_values(root, parent):
    return [node.get('text', '') for node in parent.iter('node') if node.get('package') == PACKAGE and visible(root, node)]

def card_rows(root):
    rows = []
    for node in root.iter('node'):
        match = re.fullmatch(r'game-card-(\d+)', key(node))
        if node.get('package') != PACKAGE or not match:
            continue
        descriptions = [child.get('content-desc') for child in node.iter('node') if child.get('package') == PACKAGE and child.get('content-desc')]
        assert len(descriptions) == 1
        # Parse cardinality only; private card values are neither retained nor printed.
        cardinality = re.fullmatch(r'(?:Crown|Moon|Star|Wild)\. Card (\d+) of (\d+)\.', descriptions[0])
        assert cardinality and int(cardinality[1]) == int(match[1]) + 1
        rows.append({'index': int(match[1]), 'handCount': int(cardinality[2]), 'checked': node.get('checked'), 'visible': visible(root, node)})
    return rows

def xml(runtime, receipt):
    relative = Path(receipt['file'])
    assert not relative.is_absolute() and '..' not in relative.parts
    path = runtime / relative
    identity = pin(path)
    assert identity['sha256'] == receipt['sha256']
    return ET.fromstring(path.read_bytes()), identity

def native_observation(runtime, receipt, expected=None):
    root, identity = xml(runtime, receipt)
    node = single(root, 'godot_qualification_observation')
    assert node.get('class') == 'android.widget.TextView' and node.get('text') == 'Table ready.'
    assert node.get('enabled') == node.get('clickable') == 'true' and visible(root, node)
    value = json.loads(node.get('content-desc'))
    assert value == (receipt['observation'] if expected is None else expected)
    assert value['sceneStateApplied'] is True
    assert value['requestedUptimeMs'] <= value['capturedUptimeMs'] < value['requestedUptimeMs'] + 2000
    assert value['expiresUptimeMs'] == value['capturedUptimeMs'] + 12000
    assert sum(control['selected'] for control in value['controls']) == value['selectedCount']
    return value, identity

def tap(runtime, record, role, slot):
    value, identity = native_observation(runtime, record['input_xml'], record['before'])
    intent = record['input_xml']['observation']
    assert (intent['action'], intent['role'], intent['slot']) == ('tap', role, slot)
    assert intent['observation'] == value and intent['coordinates']['point'] == record['point']
    controls = [control for control in value['controls'] if (control['role'], control['slot']) == (role, slot)]
    assert len(controls) == 1
    control = controls[0]
    assert control['visible'] is True and control['enabled'] is True
    x, y, w, h = control['rect']; cx, cy, cw, ch = control['clip']
    assert w > 0 and h > 0 and cx <= x and cy <= y and x + w <= cx + cw and y + h <= cy + ch
    surface, viewport = value['surface'], value['viewport']
    sx, sy = surface[2] / viewport[0], surface[3] / viewport[1]
    assert w * sx >= 8 and h * sy >= 8
    point = [int(surface[0] + (x + w / 2) * sx), int(surface[1] + (y + h / 2) * sy)]
    assert point == record['point']
    assert surface[0] < point[0] < surface[0] + surface[2] and surface[1] < point[1] < surface[1] + surface[3]
    return value, {'role': role, 'slot': slot, 'point': point, 'original': identity, 'receiptSequence': record['input_xml']['sequence'], 'receivedUtc': record['input_xml']['received_utc']}

def capture(runtime, result, name, native_pid=None):
    captures = [item for item in result['captures'] if item['name'] == name]
    assert len(captures) == 1
    captured = captures[0]
    assert captured['status'] == 'captured'
    shell = result['identity']['shell']; task = result['identity']['shell_task_id']
    for side in ['before', 'after']:
        state = captured[side]
        assert state['shell_pids'] == [shell['pid']] and shell in state['processes']
        assert state['foreground']['task_id'] == task
        if native_pid is None:
            assert state['renderer_pids'] == [] and state['foreground']['component'] == MAIN
        else:
            assert state['renderer_pids'] == [native_pid] and state['foreground']['component'] == NATIVE
            assert {'name': PACKAGE + ':godot', 'pid': native_pid, 'uid': shell['uid']} in state['processes']
    root, identity = xml(runtime, captured['ui'])
    return root, {'original': identity, 'receivedUtc': captured['ui']['received_utc'], 'receiptSequence': captured['ui']['sequence'], 'before': captured['before'], 'after': captured['after']}

def outcome(runtime, result, mode):
    check = result['checks'][mode + '.engine-play-standard-outcome']
    baseline = result['checks'][mode + '.engine-practice-baseline']['baseline']
    accepted = check['accepted_outcome']
    root, identity = xml(runtime, accepted['outcome_xml'])
    assert not nodes(root, 'problem-panel')
    texts = text_values(root, single(root, 'game-table'))
    visible_rounds = [int(match[1]) for text in texts if (match := re.fullmatch(r'ROUND (\d+)', text))]
    assert not visible_rounds or visible_rounds == [baseline['public']['round']]
    reported = accepted['outcome']
    rows = card_rows(root)
    if reported['kind'] == 'same-round public result':
        public = text_values(root, single(root, 'game-round-result'))
        assert [int(match[1]) for text in public if (match := re.fullmatch(r'ROUND (\d+)', text))] == [baseline['public']['round']]
        for field, pattern in [('verdict', r'(?:Bluff caught\.|The claim was true\.)'), ('challenge', r'.+ challenged .+\.'), ('claim', r'.+ claimed [1-3] (?:Crown|Moon|Star)s?\.')]:
            assert [text for text in public if re.fullmatch(pattern, text)] == [reported[field]]
        assert reported['round'] == baseline['public']['round']
    else:
        assert reported['kind'] == 'recipient hand decreased by one'
        shown = [row for row in rows if row['visible']]
        assert shown and {row['handCount'] for row in shown} == {4}
        assert all(row['checked'] == 'false' for row in shown)
        assert (reported['before_count'], reported['after_count']) == (5, 4)
    return {'original': identity, 'kind': reported['kind'], 'baselineRound': baseline['public']['round'], 'reportedRound': reported.get('round'), 'concretePublicResult': reported if reported['kind'] == 'same-round public result' else None,
            'cardNodes': rows, 'remainingUncheckedStandardCardsDirectlyObserved': bool(rows) and all(row['checked'] == 'false' for row in rows if row['visible']),
            'receiptSequence': accepted['outcome_xml']['sequence'], 'receivedUtc': accepted['outcome_xml']['received_utc']}

report = {'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'runId': 34515669045, 'headSha': '0f00f17a398be96aef7bdb58d03074a9914f8232', 'reviewer': '/root/game_domain', 'currentScenarios': [], 'oldRunComparison': [], 'source': []}
binding_path = CURRENT / 'shared-source-reuse.json'
assert pin(binding_path)['sha256'] == 'a6204d793930511beb7d1c3e1b24aeaeef6f6d83f9e35c7c444290a2da20247f'
report['collectorSourceBinding'] = pin(binding_path)
report['collectorActionMap'] = pin(CURRENT / 'review/engine-action-original-xml-audit.json')
assert report['collectorActionMap']['sha256'] == '8bd58c373cfb82d6d458e4fe7ce28a5ecf503f5eb357f77b52ce80e60851a844'
report['currentSourceFreeze'] = pin(SOURCE.parent / 'collection-frozen.json')
report['oldRunFreeze'] = pin(OLD / 'collection-frozen.json')
assert read(OLD / 'collection-frozen.json')['headSha'] == 'd06f83aa8f6905be515faf0f58690634714e5a2d'
for variant in ['debug', 'optimized-test-signed']:
    runtime = CURRENT / 'android-jvm-reports/build/ci/android/godot-session' / variant / 'runtime'
    result_path = runtime / 'godot-session-result.json'; result = read(result_path)
    assert result['passed'] is True and result['engine_gameplay_requested'] is True
    assert result['identity']['checker_sha256'] == pin(SOURCE / 'scripts/smoke-android-godot-session.py')['sha256']
    for mode in ['2d', '3d']:
        prefix = mode + '-engine'
        checks = result['checks']; baseline = checks[mode + '.engine-practice-baseline']['baseline']
        for suffix in ['engine-practice-baseline', 'engine-reveal-selection', 'engine-play-standard-outcome', 'engine-leave-end']:
            assert checks[mode + '.' + suffix]['status'] == 'passed'
        assert baseline['public']['turn'] == 'Your turn' and baseline['first_card']['hand_count'] == 5
        public, public_receipt = capture(runtime, result, prefix + '-baseline-public')
        public_texts = text_values(public, single(public, 'game-table'))
        assert 'Your turn' in public_texts and [int(match[1]) for text in public_texts if (match := re.fullmatch(r'ROUND (\d+)', text))] == [baseline['public']['round']]
        assert not nodes(public, 'game-round-result') and not nodes(public, 'game-winner')
        hand, hand_receipt = capture(runtime, result, prefix + '-baseline-first-card')
        baseline_cards = card_rows(hand)
        assert {row['index'] for row in baseline_cards if row['visible']} == set(range(5))
        assert all(row['handCount'] == 5 and row['checked'] == 'false' for row in baseline_cards)
        entry = next(item for item in result['captures'] if item['name'] == prefix + '-entry-native-ready')
        native_pid = entry['before']['renderer_pids'][0]
        _, entry_receipt = capture(runtime, result, prefix + '-entry-native-ready', native_pid)
        reveal = checks[mode + '.engine-reveal-selection']; play = checks[mode + '.engine-play-standard-outcome']
        concealed, concealed_pin = native_observation(runtime, reveal['concealed'])
        pre_reveal, reveal_tap = tap(runtime, reveal['reveal'], 'reveal', -1)
        revealed, revealed_pin = native_observation(runtime, reveal['revealed'])
        pre_select, selection_tap = tap(runtime, reveal['selection'], 'select', 0)
        selected, selected_pin = native_observation(runtime, reveal['selected'])
        pre_play, play_tap = tap(runtime, play['play'], 'play', -1)
        processed, processed_pin = native_observation(runtime, play['renderer_after_input'])
        assert concealed['handConcealed'] and concealed['selectedCount'] == concealed['privateFaceCount'] == concealed['privateLabelCount'] == 0
        assert not revealed['handConcealed'] and revealed['selectedCount'] == 0 and revealed['privateFaceCount'] > 0 and revealed['privateLabelCount'] > 0
        assert {control['slot'] for control in revealed['controls'] if control['role'] == 'select'} == set(range(5))
        assert selected['selectedCount'] == 1 and {control['slot'] for control in selected['controls'] if control['role'] == 'select' and control['selected']} == {0}
        assert processed['handConcealed'] and processed['selectedCount'] == processed['privateFaceCount'] == processed['privateLabelCount'] == 0
        assert [int(value['input']) for value in [pre_reveal, revealed, pre_select, selected, pre_play, processed]] == [0, 2, 2, 4, 4, 6]
        assert len({value['projectionRevision'] for value in [concealed, pre_reveal, revealed, pre_select, selected, pre_play]}) == 1
        assert play['play_attempts'] == 1
        action_receipts = []
        for path in sorted((runtime / 'captures').glob(prefix + '-*.json')):
            value = read(path).get('observation', {})
            if value.get('action') in ['tap', 'swipe']:
                action_receipts.append({'original': pin(path), 'action': value['action'], 'role': value['role'], 'slot': value['slot']})
        assert [(row['action'], row['role'], row['slot']) for row in action_receipts] == [('tap', 'reveal', -1), ('tap', 'select', 0), ('tap', 'play', -1)]
        owner_paths = sorted((runtime / 'logs').glob(prefix + '-*-owner.json'))
        owners = [read(path) for path in owner_paths]
        assert owners and all(owner == owners[0] for owner in owners)
        assert owners[0]['renderer'] == {'name': PACKAGE + ':godot', 'pid': native_pid, 'uid': result['identity']['shell']['uid']}
        assert owners[0]['task'] == result['identity']['shell_task_id']
        _, selected_capture = capture(runtime, result, prefix + '-selected', native_pid)
        standard = outcome(runtime, result, mode)
        assert standard['kind'] == 'same-round public result' and standard['cardNodes'] == []
        concealed_root, concealed_standard_pin = xml(runtime, play['accepted_outcome']['concealed_return_xml'])
        assert not card_rows(concealed_root)
        later_root, later_capture = capture(runtime, result, prefix + '-standard-after-play')
        assert not card_rows(later_root)
        assert play_tap['receiptSequence'] < play['renderer_after_input']['sequence'] < play['accepted_outcome']['concealed_return_xml']['sequence'] < standard['receiptSequence'] < later_capture['receiptSequence']
        assert standard['receivedUtc'] <= later_capture['receivedUtc']
        home, home_capture = capture(runtime, result, prefix + '-home')
        assert visible(home, single(home, 'home-practice'))
        assert all(not nodes(home, tag) for tag in ['game-table', 'game-hand', 'leave-confirm'])
        report['currentScenarios'].append({'variant': variant, 'mode': mode, 'originalResult': pin(result_path), 'baselineRound': baseline['public']['round'],
            'baselinePublic': public_receipt, 'baselineHand': hand_receipt, 'baselineCards': baseline_cards,
            'nativeEntry': entry_receipt, 'nativeSelectedCapture': selected_capture,
            'actions': [reveal_tap, selection_tap, play_tap], 'allEngineInputReceipts': action_receipts,
            'observations': [{'stage': stage, 'original': identity, 'input': value['input'], 'projectionRevision': value['projectionRevision'], 'generation': value['generation'], 'selectedCount': value['selectedCount'], 'handConcealed': value['handConcealed'], 'selectedSlots': [c['slot'] for c in value['controls'] if c['role'] == 'select' and c['selected']]} for stage, identity, value in [('concealed', concealed_pin, concealed), ('revealed', revealed_pin, revealed), ('selected', selected_pin, selected), ('processed', processed_pin, processed)]],
            'owner': owners[0], 'ownerReceiptCount': len(owners), 'ownerReceipts': [pin(path) for path in owner_paths],
            'immediateStandardOutcome': standard, 'concealedStandardReturn': concealed_standard_pin,
            'laterStandardCapture': later_capture, 'teardownHome': home_capture,
            'oneEnginePlayAttempt': True, 'correctiveSwipes': 0,
            'sameSampledShellTaskAndNativeActionOwner': True, 'nativeChildAbsentAfterStandardAndAtHome': True,
            'remainingUncheckedStandardCardsDirectlyObserved': False})
        old_runtime = OLD / 'android-jvm-reports/build/ci/android/godot-session' / variant / 'runtime'
        old_result_path = old_runtime / 'godot-session-result.json'; old_result = read(old_result_path)
        report['oldRunComparison'].append({'variant': variant, 'mode': mode, 'runId': 34506173394, 'headSha': 'd06f83aa8f6905be515faf0f58690634714e5a2d', 'originalResult': pin(old_result_path), 'outcome': outcome(old_runtime, old_result, mode), 'acceptanceTransferredToCurrent': False})

for relative, spans in [
    ('scripts/smoke-android-godot-session.py', [(255, 311), (1288, 1328), (1330, 1409)]),
    ('scripts/android_godot_session_observation.py', [(14, 20), (192, 195), (214, 238), (303, 337)]),
    ('androidApp/src/main/kotlin/dev/partydeck/app/godot/SessionGodotActivity.kt', [(566, 573), (787, 813)]),
    ('androidApp/src/main/kotlin/dev/partydeck/app/godot/GodotQualificationObservation.kt', [(193, 201)]),
    ('composeApp/src/commonMain/kotlin/dev/partydeck/app/ui/game/GameResults.kt', [(98, 119), (137, 147)]),
]:
    path = SOURCE / relative; old_path = OLD_SOURCE / relative; lines = path.read_text().splitlines()
    report['source'].append({'current': pin(path), 'old': pin(old_path), 'byteIdentical': path.read_bytes() == old_path.read_bytes(), 'excerpts': {str(i): lines[i-1] for start, end in spans for i in range(start, end+1)}})
assert len(report['currentScenarios']) == 4
report['conclusion'] = 'Four current native action sequences and their immediate same-round Standard public results plus teardown are supported by original XML/JSON. Remaining unchecked Standard cards are not directly observed in these public-result cases.'
report['limits'] = [
    'The exposed numeric generation and projectionRevision are renderer observation fields, not authority/session revision receipts.',
    'Current-session continuity is supported by a fresh human-turn baseline, exact sampled shell/task/native owner, ordered receipts, same-round public result, and teardown. No internal authority session ID or acceptance receipt is exposed.',
    'All current return/outcome XMLs contain zero card nodes. The visible unchecked-card loop is vacuous in these four public-result outcomes; old-run hand-count/selection observations are not transferred.',
    'The baseline five unchecked cards and native selection clearing are directly observed; neither establishes the unobserved remaining Standard hand.',
    'Pre-input ownership/currentness is sampled. No atomic delivery-before-expiry, continuous per-frame transform, pixel privacy, TalkBack, or physical-device guarantee is inferred.',
    'The two 3D public results include later opponent actions. They show same-round authority-owned UI progress after the one human engine Play, not a direct internal acceptance receipt for that input.',
    'This review is limited to API36 normal-text qualification practice scenarios. Build/JUnit/package verification is separately owned by network_transport; no app/build/test, download, or media viewing was performed.',
]
path = OUT / 'original-action-review.json'
with path.open('x') as output:
    json.dump(report, output, indent=2)
    output.write('\n')
print(json.dumps({'review': pin(path), 'scenarios': [{'variant': row['variant'], 'mode': row['mode'], 'ownerReceipts': row['ownerReceiptCount'], 'baselineRound': row['baselineRound'], 'outcome': row['immediateStandardOutcome']['kind'], 'remainingUncheckedCardsObserved': row['remainingUncheckedStandardCardsDirectlyObserved']} for row in report['currentScenarios']]}))
