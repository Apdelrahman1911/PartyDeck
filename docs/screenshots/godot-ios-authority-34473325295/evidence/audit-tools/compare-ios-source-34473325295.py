"""Compare exact archived run inputs; do not consult or mutate the live checkout."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

BASE = Path('/tmp/partydeck-engine-ci/34473325295')
HEAD = '0f666e0ab7fdce63d5fa668442dae1c9fda86a1d'
SOURCE = BASE / ('source-' + HEAD[:7])
PREVIOUS_BASE = Path('/tmp/partydeck-engine-ci/34464316979')
PREVIOUS_SOURCE = PREVIOUS_BASE / 'source-ea84bf4'

def read(path): return json.loads(path.read_text())
def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
def record(path): return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}
def write_new(path, value):
    with path.open('x') as stream: stream.write(json.dumps(value, indent=2) + '\n')

names = {'.github/workflows/godot-ios-authority-host.yml'}
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
delta = {
    'runId': 34473325295, 'headSha': HEAD, 'previousRunId': 34464316979,
    'previousHeadSha': 'ea84bf49e799675c181545cc3511460b11e0e23d',
    'recordedAtUtc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Exact archived iOS host sources, workflow and recorded renderer/tool inputs only; not an entire repository diff.',
    'sourceArchiveReceipt': record(BASE / 'source-archive.json'),
    'previousSourceArchiveReceipt': record(PREVIOUS_BASE / 'source-archive.json'),
    'comparedFileCount': len(names), 'changedFiles': changes, 'unchangedFiles': unchanged,
}
write_new(BASE / 'source-delta-from-34464316979.json', delta)
points = [
    ('godot/renderer/scripts/main.gd', 120, 136, 'Reconcile requests invalidate the generation stamp before scheduling scene reconciliation.'),
    ('godot/renderer/scripts/main.gd', 194, 221, 'Applied state is stamped only for the same generation, controller and live presentation after Ready delivery; exhaustion remains noncurrent.'),
    ('godot/ios-host/modules/partydeck_ios_probe/PDGodotRuntime.mm', 286, 328, 'The native diagnostics schema requires and copies a typed sceneStateApplied Boolean.'),
    ('godot/ios-host/modules/partydeck_ios_probe/PDGodotRuntime.mm', 1118, 1123, 'Concealed-current diagnostics require sceneStateApplied together with existing iteration, concealment, revision and foreground checks.'),
    ('godot/ios-host/AuthorityHostUITests/AuthorityHostUITests.swift', 330, 342, 'The final touch read checks sceneStateApplied before native input.'),
    ('godot/ios-host/AuthorityHostUITests/AuthorityHostUITests.swift', 407, 450, 'Current diagnostics require the applied-state flag; failed waits preserve the last rejected value before later capture.'),
    ('godot/ios-host/AuthorityHostUITests/AuthorityHostUITests.swift', 504, 527, 'Metrics use a StaticText query and record that query duration.'),
    ('godot/ios-host/RetainedHostUITests/RetainedHostUITests.swift', 449, 461, 'Retained touch-candidate evidence is attached before final currentness and cover checks; it is not an actual tap count.'),
    ('godot/ios-host/RetainedHostUITests/RetainedHostUITests.swift', 488, 527, 'Retained current diagnostics require the applied-state flag; failed waits preserve their last rejected measurements.'),
    ('godot/ios-host/RetainedHostUITests/RetainedHostUITests.swift', 571, 587, 'Retained metrics use a StaticText query and record its duration.'),
    ('godot/renderer/presentations/three_d/table.gd', 117, 124, 'Foreground 3D still selects UPDATE_WHEN_VISIBLE; this run does not contain the separate demand optimization.'),
]
observations = []
for name, start, end, finding in points:
    path = SOURCE / name
    lines = path.read_text().splitlines()
    observations.append({'source': record(path), 'startLine': start, 'endLine': end,
        'officialSourceUrl': f'https://github.com/Apdelrahman1911/PartyDeck/blob/{HEAD}/{name}#L{start}',
        'finding': finding, 'excerpt': '\n'.join(lines[start - 1:end])})
receipt = {'runId': 34473325295, 'headSha': HEAD,
    'scope': 'Source facts and run-input identity only. No performance benefit, runtime success or fix of a prior 3D stall follows from these observations.',
    'sourceArchive': record(BASE / 'source-archive.json'),
    'producerAudit': record(BASE / 'producer-input-evidence-summary.json'),
    'delta': record(BASE / 'source-delta-from-34464316979.json'),
    'observations': observations,
    'optionalStartupMousePatchIncluded': False,
    'threeDDemandOptimizationIncluded': False,
    'nativeExecutionEvaluatedHere': False}
write_new(BASE / 'source-currentness-observation-audit.json', receipt)
print(json.dumps({'changedFileCount': len(changes), 'comparedFileCount': len(names),
    'changedPaths': [item['path'] for item in changes],
    'receipt': record(BASE / 'source-currentness-observation-audit.json')}), flush=True)
