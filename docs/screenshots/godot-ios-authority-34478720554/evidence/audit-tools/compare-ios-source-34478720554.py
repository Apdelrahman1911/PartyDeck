"""Compare preserved exact-commit sources without consulting the live checkout."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path

BASE = Path('/tmp/partydeck-engine-ci/34478720554')
HEAD = 'c6ea1dd9f7966517fbee87a06b633d01c432c24d'
SOURCE = BASE / ('source-' + HEAD[:7])
PREVIOUS_BASE = Path('/tmp/partydeck-engine-ci/34473325295')
PREVIOUS_HEAD = '0f666e0ab7fdce63d5fa668442dae1c9fda86a1d'
PREVIOUS_SOURCE = PREVIOUS_BASE / ('source-' + PREVIOUS_HEAD[:7])

def read(path): return json.loads(path.read_text())
def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
def record(path): return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}
def write_new(path, value):
    with path.open('x') as stream: stream.write(json.dumps(value, indent=2) + '\n')

checks = []
def check(label, condition):
    checks.append({'check': label, 'passed': bool(condition)})
    assert condition, label

freeze = read(BASE / 'expected-native-freeze-v6.json')
names = {'.github/workflows/godot-ios-authority-host.yml'}
names.update(freeze['renderer_sources'])
names.update(freeze['files'])
for source in (SOURCE, PREVIOUS_SOURCE):
    host = source / 'godot/ios-host'
    for path in host.rglob('*'):
        if path.is_file() and not any(part in {'build', '__pycache__'} for part in path.relative_to(host).parts):
            names.add(path.relative_to(source).as_posix())
for base in (BASE, PREVIOUS_BASE):
    pack = read(base / 'godot-ios-host-renderer/partydeck-last-light.receipt.json')
    names.update('godot/renderer/' + item['path'] for item in pack['inputs']['files'])
    names.update('godot/tools/' + item['path'] for item in pack['inputs']['tools'])

changes, unchanged = [], []
for name in sorted(names):
    old, new = PREVIOUS_SOURCE / name, SOURCE / name
    old_hash = digest(old) if old.is_file() else None
    new_hash = digest(new) if new.is_file() else None
    if old_hash == new_hash:
        unchanged.append(name)
    else:
        changes.append({'path': name, 'previousSha256': old_hash, 'currentSha256': new_hash})

for name, expected in freeze['renderer_sources'].items():
    check('archived v6 renderer source identity: ' + name, digest(SOURCE / name) == expected)
check('ordered upstream patch set remains exactly coreaudio-dormancy and main-loop-access',
      [item['name'] for item in freeze['upstream_patches']] == ['coreaudio-dormancy', 'main-loop-access'])
check('optional startup mouse patch absent from archived patch set',
      sorted(p.name for p in (SOURCE / 'godot/ios-host/patches').glob('*.patch')) == ['coreaudio-dormancy.patch', 'main-loop-access.patch'])
runtime_name = 'godot/ios-host/modules/partydeck_ios_probe/PDGodotRuntime.mm'
old_runtime = (PREVIOUS_SOURCE / runtime_name).read_text()
new_runtime = (SOURCE / runtime_name).read_text()
old_pack = read(PREVIOUS_BASE / 'godot-ios-host-renderer/partydeck-last-light.receipt.json')['pack']['sha256']
new_pack = read(BASE / 'godot-ios-host-renderer/partydeck-last-light.receipt.json')['pack']['sha256']
check('runtime change is exactly one qualified PCK SHA literal replacement',
      old_runtime.count(old_pack) == new_runtime.count(new_pack) == 1 and old_runtime.replace(old_pack, new_pack) == new_runtime)
check('other native module sources are unchanged',
      [item['path'] for item in changes if item['path'].startswith('godot/ios-host/modules/')] == [runtime_name])
test_name = 'godot/ios-host/RetainedHostUITests/RetainedHostUITests.swift'
old_test, new_test = (PREVIOUS_SOURCE / test_name).read_text(), (SOURCE / test_name).read_text()
old_predicate = '''                self.number("applicationBackgroundCount", $0) > self.number("applicationBackgroundCount", beforeDormantHome)
        }
'''
new_predicate = '''                self.number("applicationBackgroundCount", $0) > self.number("applicationBackgroundCount", beforeDormantHome) &&
                self.flag("applicationActive", self.native($0)) &&
                !self.flag("applicationBackgrounded", self.native($0))
        }
        attach(dormantReturned, "Dormant Home/activate accepted native observation")
'''
check('retained test change is exactly active/backgrounded acceptance predicate and accepted-value attachment',
      old_test.count(old_predicate) == new_test.count(new_predicate) == 1 and old_test.replace(old_predicate, new_predicate) == new_test)
check('default 15-second wait unchanged', 'timeout: TimeInterval = 15,' in old_test and 'timeout: TimeInterval = 15,' in new_test)
check('main scene-currentness and controller sources unchanged',
      all(name in unchanged for name in ['godot/renderer/scripts/main.gd', 'godot/renderer/scripts/renderer_controller.gd']))

delta = {'runId': 34478720554, 'headSha': HEAD, 'previousRunId': 34473325295,
    'previousHeadSha': PREVIOUS_HEAD, 'recordedAtUtc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Exact archived iOS host sources, workflow, renderer/tool inputs and all v6 renderer sources, including newly added tests; not an entire repository diff.',
    'sourceArchiveReceipt': record(BASE / 'source-archive.json'),
    'previousSourceArchiveReceipt': record(PREVIOUS_BASE / 'source-archive.json'),
    'comparedFileCount': len(names), 'changedFiles': changes, 'unchangedFiles': unchanged}
delta_path = BASE / 'source-delta-from-34473325295.json'
write_new(delta_path, delta)
diff_path = BASE / 'native-runtime-and-retained-test-delta.patch'
with diff_path.open('x') as stream:
    for name in [runtime_name, test_name]:
        stream.writelines(difflib.unified_diff((PREVIOUS_SOURCE / name).read_text().splitlines(True),
            (SOURCE / name).read_text().splitlines(True), fromfile='previous/' + name, tofile='current/' + name))

points = [
    (runtime_name, 64, 69, 'Only the qualified PCK literal changed in the native runtime, independently compared with the previous archived source.'),
    (test_name, 93, 108, 'Dormant Home/activate acceptance now requires active and not backgrounded in the same returned dictionary, which is attached before the existing assertions and subsequent shell interaction.'),
    (test_name, 351, 366, 'The next dormant interval uses that accepted dictionary as its baseline; this supports exact payload equality auditing.'),
    (test_name, 507, 530, 'The existing 15-second default predicate wait and original last-rejected-value attachment remain unchanged.'),
    ('godot/renderer/presentations/three_d/table.gd', 46, 61, 'Tree entry resets demand tracking and connects the draw-boundary callback; regular table processing initially remains disabled.'),
    ('godot/renderer/presentations/three_d/table.gd', 143, 159, 'The 3D SubViewport is initialized with UPDATE_DISABLED.'),
    ('godot/renderer/presentations/three_d/table.gd', 597, 631, 'The draw-boundary callback requests UPDATE_ONCE for dirty, pending or changed content and normalizes idle frames to UPDATE_DISABLED. Consumption acknowledgment requires cached node ONCE and server DISABLED.'),
    ('godot/renderer/presentations/three_d/table.gd', 634, 652, 'The demand signature samples viewport and stage geometry, camera transform and projection, and every card identity, transform and visibility; size changes mark it dirty.'),
    ('godot/renderer/presentations/three_d/table.gd', 948, 959, 'Tree exit disconnects the draw callback and clears private state and interaction references.'),
    ('godot/renderer/scripts/main.gd', 194, 221, 'Existing same-generation live-scene currentness checks remain byte-identical to the preceding run.'),
    ('godot/renderer/tests/three_d_redraw_check.gd', 282, 314, 'The archived new desktop test samples actual server modes around forced draws and records viewport texture hashes. This source observation does not establish test execution.'),
    ('godot/renderer/tests/three_d_redraw_check.gd', 373, 395, 'The archived desktop test includes terminal scene removal, disconnected draw callback and empty-Tween checks.'),
    ('godot/renderer/tests/terminal_return_render_check.gd', 22, 41, 'The archived desktop terminal-return test covers both modes, pending-return refresh and cancellation; its declared limits exclude native scheduling and authority acceptance.'),
]
observations = []
for name, start, end, finding in points:
    path = SOURCE / name
    lines = path.read_text().splitlines()
    observations.append({'source': record(path), 'startLine': start, 'endLine': end,
        'officialSourceUrl': f'https://github.com/Apdelrahman1911/PartyDeck/blob/{HEAD}/{name}#L{start}',
        'finding': finding, 'excerpt': '\n'.join(lines[start - 1:end])})
receipt = {'runId': 34478720554, 'headSha': HEAD,
    'scope': 'Exact source identity and bounded source observations only. No performance benefit, native success or fix of a prior stall follows from these observations.',
    'sourceArchive': record(BASE / 'source-archive.json'),
    'producerAudit': record(BASE / 'producer-input-evidence-summary.json'),
    'expectedNativeFreeze': record(BASE / 'expected-native-freeze-v6.json'),
    'delta': record(delta_path), 'runtimeAndTestDiff': record(diff_path),
    'observations': observations, 'checks': checks,
    'optionalStartupMousePatchIncluded': False, 'threeDDemandOptimizationIncluded': True,
    'nativeExecutionEvaluatedHere': False, 'desktopTestsExecutedHere': False}
output = BASE / 'source-currentness-observation-audit.json'
write_new(output, receipt)
print(json.dumps({'changedFileCount': len(changes), 'comparedFileCount': len(names),
    'changedPaths': [item['path'] for item in changes], 'checksPassed': len(checks), 'receipt': record(output)}), flush=True)
