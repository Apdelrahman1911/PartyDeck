"""Audit original runtime streams and capture bindings, for the current completed run."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET
from runtime_audit_helpers_v2 import png_dimensions, exact_app_processes, focused_activity, utc

ROOT = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34503251315')
REPORTS = ROOT / 'android-jvm-reports'
NATIVE = REPORTS / 'build/ci/android'
SOURCE = ROOT.parent / 'source-1cd34a3/source-1cd34a3'
PACKAGE = 'dev.partydeck.app'


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': sha256(data).hexdigest()}


def read(path):
    return json.loads(path.read_text())


def write(name, value):
    path = ROOT / 'review' / name
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    return identity(path)


packages = read(ROOT / 'review/package-audit.json')['packages']
manifest = {row['path']: row for row in read(ROOT / 'android-jvm-reports.files.json')}
variants = {}
capture_metadata = {}
for variant in ('debug', 'optimized-test-signed'):
    runtime = NATIVE / 'godot-session' / variant / 'runtime'
    result_path = runtime / 'godot-session-result.json'
    result = read(result_path) if result_path.exists() else None
    assert result is not None and result['status'] == 'passed' and result['passed']
    assert result['engine_gameplay_requested'] is False
    inputs_path = runtime.parent / 'package-inputs.json'
    inputs = read(inputs_path)
    assert inputs['verified'] and inputs['activation']['verified']
    assert inputs['apkSha256'] == packages[variant]['artifact']['sha256']
    if result:
        assert result['identity']['checker_sha256'] == identity(SOURCE / 'scripts/smoke-android-godot-session.py')['sha256']
        assert result['identity']['helper_sha256'] == identity(SOURCE / 'scripts/smoke-android-ui.py')['sha256']
        assert result['identity']['input_apk_sha256'] == inputs['apkSha256']
    samples = []
    for path in sorted((runtime / 'logs').glob('process-table-*.json')):
        entry = read(path)
        assert entry['argv'] == ['adb', '-s', 'emulator-5554', 'shell', 'ps', '-A', '-n', '-w', '-o', 'PID,UID,NAME']
        assert utc(entry['started_utc']) <= utc(entry['ended_utc'])
        streams = {}
        for name in ('stdout', 'stderr'):
            stream = entry[name]
            assert stream['available']
            original = runtime / stream['file']
            actual = identity(original)
            assert (actual['bytes'], actual['sha256']) == (stream['bytes'], stream['sha256'])
            frozen = manifest[original.relative_to(REPORTS).as_posix()]
            assert (actual['bytes'], actual['sha256']) == (frozen['bytes'], frozen['sha256'])
            streams[name] = actual
        assert entry['returncode'] == 0 and not (runtime / entry['stderr']['file']).read_bytes()
        processes = exact_app_processes((runtime / entry['stdout']['file']).read_bytes())
        samples.append({'receipt': identity(path), 'command': entry, 'streams': streams, 'processes': processes})
    captures, ui_observations = [], []
    for path in sorted((runtime / 'captures').glob('*.json')):
        capture = read(path)
        if 'screenshot' not in capture:
            assert 'observation' in capture and 'file' in capture
            xml = runtime / capture['file']
            assert identity(xml)['sha256'] == capture['sha256']
            ET.fromstring(xml.read_bytes())
            ui_observations.append({'receipt': identity(path), 'xml': identity(xml), 'data': capture})
            continue
        assert capture['status'] == 'captured' and not any(k.endswith('_error') for k in capture)
        png = runtime / capture['screenshot']['file']
        xml = runtime / capture['ui']['file']
        assert png_dimensions(png) == [capture['screenshot']['width'], capture['screenshot']['height']] == [720, 1600]
        assert identity(png)['sha256'] == capture['screenshot']['sha256']
        assert identity(xml)['sha256'] == capture['ui']['sha256']
        tree = ET.fromstring(xml.read_bytes())
        timeline = [capture['started_utc'], capture['before']['started_utc'], capture['before']['ended_utc'],
                    capture['ui']['received_utc'], capture['screenshot_started_utc'], capture['screenshot_received_utc'],
                    capture['after']['started_utc'], capture['after']['ended_utc'], capture['ended_utc']]
        assert list(map(utc, timeline)) == sorted(map(utc, timeline))
        states = {}
        for phase in ('before', 'after'):
            state = capture[phase]
            process_path = runtime / 'captures' / f"{capture['name']}-{phase}-processes.log"
            activity_path = runtime / 'captures' / f"{capture['name']}-{phase}-activity.log"
            assert exact_app_processes(process_path.read_bytes()) == state['processes']
            assert focused_activity(activity_path.read_text()) == state['foreground']
            process_id = identity(process_path)
            matching = [sample for sample in samples if sample['streams']['stdout']['sha256'] == process_id['sha256']
                        and utc(state['started_utc']) <= utc(sample['command']['started_utc'])
                        <= utc(sample['command']['ended_utc']) <= utc(state['ended_utc'])]
            assert matching
            states[phase] = {'activity': identity(activity_path), 'processes': process_id,
                             'state': state, 'matchingProcessReceipts': [m['receipt'] for m in matching]}
        record = {'name': capture['name'], 'stage': capture['stage'], 'receipt': identity(path),
                  'png': identity(png), 'xml': identity(xml), 'states': states}
        captures.append(record)
        capture_metadata[str(png)] = {'category': 'native-session', 'variant': variant,
            'stage': capture['stage'], 'xml': identity(xml), 'json': identity(path),
            'captureResult': 'captured', 'nativeVariantPassed': result['passed']}
    declared_missing = []
    if result:
        for entry in result['artifacts']:
            path = runtime / entry['file']
            if not path.exists():
                declared_missing.append(entry)
            else:
                actual = identity(path)
                assert (actual['bytes'], actual['sha256']) == (entry['bytes'], entry['sha256'])
        assert [item['file'] for item in declared_missing] == ['identity/installed-base.apk']
        assert declared_missing[0]['sha256'] == packages[variant]['artifact']['sha256']
    variants[variant] = {'packageInputs': identity(inputs_path), 'finalResult': identity(result_path) if result else None,
        'finalResultAvailable': result is not None, 'finalCheckStatus': result['status'],
        'processSampleCount': len(samples), 'processSamples': samples,
        'completeCaptureCount': len(captures), 'captures': captures,
        'originalStandardUiObservationCount': len(ui_observations), 'standardUiObservations': ui_observations,
        'missingDeclaredArtifacts': declared_missing,
        'limits': 'All retained commands/captures are audited. The pulled installed APK is explicitly excluded by the upload patterns; its recorded hash matches the separately retained current APK. No missing bytes are reconstructed. Original visual review is separate.'}

# Independently bind key lifecycle stills to the process and focused-activity state.
MAIN = PACKAGE + '/' + PACKAGE + '.MainActivity'
GODOT = PACKAGE + '/' + PACKAGE + '.godot.SessionGodotActivity'
for variant, record in variants.items():
    runtime = NATIVE / 'godot-session' / variant / 'runtime'
    result = read(runtime / 'godot-session-result.json')
    captures = {read(Path(c['receipt']['path']))['name']: read(Path(c['receipt']['path'])) for c in record['captures']}
    assert len(captures) == len(result['captures'])
    assert captures == {c['name']: c for c in result['captures']}
    shell = result['identity']['shell']
    bindings = []
    for mode in ('2d', '3d'):
        entry = result['checks'][mode + '.native-entry']
        selected = {
            mode + '-entry-native-ready': (GODOT, [entry['renderer_pid']]),
            mode + '-home-system-ui': (result['identity']['launcher_component'], [entry['renderer_pid']]),
            mode + '-recents-system-ui': (result['identity']['launcher_component'], [entry['renderer_pid']]),
            mode + '-home-resumed': (GODOT, [entry['renderer_pid']]),
            mode + '-recents-resumed': (GODOT, [entry['renderer_pid']]),
            mode + '-standard-concealed': (MAIN, []),
            mode + '-home-after-session-end': (MAIN, []),
        }
        if variant == 'debug':
            selected[mode + '-death-return-concealed'] = (MAIN, [])
        for name, (foreground, renderer_pids) in selected.items():
            capture = captures[name]
            for phase in ('before', 'after'):
                state = capture[phase]
                assert state['foreground']['component'] == foreground, (variant, name, phase)
                assert state['shell_pids'] == [shell['pid']] and state['renderer_pids'] == renderer_pids
                assert [p for p in state['processes'] if p['name'] == PACKAGE] == [shell]
                assert all(p['uid'] == shell['uid'] for p in state['processes'])
                if foreground == GODOT:
                    assert state['foreground']['task_id'] == entry['task_id']
                elif foreground == MAIN:
                    assert state['foreground']['task_id'] == result['identity']['shell_task_id']
            xml = runtime / capture['ui']['file']
            root = ET.fromstring(xml.read_bytes())
            private = [n.attrib for n in root.iter('node')
                       if n.get('resource-id', '').rsplit('/', 1)[-1].startswith('game-card-')
                       or re.search(r'\b(?:Crown|Moon|Star|Wild)\. Card \d+ of \d+\.', n.get('content-desc', ''))]
            assert not private, (variant, name)
            bindings.append({'capture': name, 'foreground': foreground,
                             'rendererPidsBeforeAndAfter': renderer_pids,
                             'shellPidBeforeAndAfter': shell['pid'], 'uid': shell['uid'],
                             'privateCardSemanticNodeCount': len(private)})
    record['scopedLifecycleStillBindings'] = bindings
    record['finalResultCaptureListExactlyMatchesOriginalSidecars'] = True
summary = {'runId': 34503251315,
    'headSha': '1cd34a36753ed0112e6684f6525592dab8ef2edb',
    'createdAtUtc': datetime.now(timezone.utc).isoformat(),
    'auditResult': 'All retained native process streams and capture bindings verified.',
    'variants': variants,
    'runtimeOutcomeAudit': identity(ROOT / 'review/runtime-result-triage.json'),
    'originalFreeze': identity(ROOT / 'original-collection-frozen.json'),
    'auditScript': identity(Path(__file__)),
    'pureParsingHelper': identity(Path(__file__).with_name('runtime_audit_helpers_v2.py')),
    'scope': 'Original PNG CRC/dimensions, XML/JSON hashes, complete process-command streams, independently parsed focused activities and exact process identities. Native entry, Home/Recents, return and end stills are bound to expected processes and inspected for private-card XML semantics. Pixel observations are recorded separately; sequential captures do not establish continuous transition privacy, engine gameplay or TalkBack speech.'}
audit_identity = write('runtime-capture-audit.json', summary)
print(json.dumps({'audit': audit_identity,
    'variantCounts': {v: {k: x[k] for k in ('processSampleCount', 'completeCaptureCount',
        'originalStandardUiObservationCount', 'finalResultAvailable')} for v, x in variants.items()}}, indent=2))
