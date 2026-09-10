"""Read-only exact-source correlation for the retained Close-barrier run."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import re
import tarfile

BASE = Path('/tmp/partydeck-engine-ci/34456443339')
HEAD = 'dad1c11741bd4322bb8b2afb9f18f3db5f50c919'
PRIOR = Path('/tmp/partydeck-engine-ci/34450246541/source-a727868')
SOURCE = BASE / 'source-dad1c11'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def record(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}


def matched_lines(path, pattern):
    return [{'line': number, 'text': line} for number, line in enumerate(path.read_text().splitlines(), 1)
            if re.search(pattern, line)]


checker_paths = ['godot/android-checks/run.py', 'godot/android-checks/evidence.py', 'scripts/smoke-android-ui.py']
unchanged_paths = checker_paths + ['.github/workflows/godot-compare.yml', 'godot/android-checks/emulator.sh',
    'godot/android-renderer/src/main/kotlin/dev/partydeck/godot/android/BoundedDispatchQueue.kt']
changed_paths = [
    'godot/android-renderer/src/main/kotlin/dev/partydeck/godot/android/PartyDeckBridgePlugin.kt',
    'godot/android-host/src/main/kotlin/dev/partydeck/godot/compare/GodotGameActivity.kt',
]
new_paths = [
    'godot/android-renderer/src/main/kotlin/dev/partydeck/godot/android/NativeSignalDispatch.kt',
    'godot/android-renderer/src/test/kotlin/dev/partydeck/godot/android/NativeSignalDispatchTest.kt',
]
selected_paths = unchanged_paths + changed_paths + new_paths + ['godot/tools/renderer.py']
source_receipt_path = BASE / 'source-archive.json'
source_receipt = json.loads(source_receipt_path.read_text())
assert source_receipt['runId'] == 34456443339 and source_receipt['headSha'] == HEAD
assert source_receipt['sourceEndpoint'] == 'repos/Apdelrahman1911/PartyDeck/tarball/' + HEAD
archive = Path(source_receipt['archivePath'])
assert archive.stat().st_size == source_receipt['bytes'] == 245465945
assert digest(archive) == source_receipt['sha256'] == '955de3c9791d1642780b7496096aa4a9dbf351f7ca361f67a5f842e8e595f8cc'
archived_members = {}
count = 0
with tarfile.open(archive, mode='r|gz') as stream:
    for member in stream:
        count += 1
        relative = member.name.partition('/')[2]
        if relative in selected_paths:
            assert member.isfile() and relative not in archived_members
            content = stream.extractfile(member).read()
            assert content == (SOURCE / relative).read_bytes()
            archived_members[relative] = {'member': member.name, 'bytes': len(content),
                                         'sha256': hashlib.sha256(content).hexdigest()}
assert count == source_receipt['memberCount'] == 6013
assert set(archived_members) == set(selected_paths)

comparisons = []
for relative in unchanged_paths:
    assert (PRIOR / relative).read_bytes() == (SOURCE / relative).read_bytes(), relative
    comparisons.append({'relativePath': relative, 'prior': record(PRIOR / relative),
                        'current': record(SOURCE / relative), 'byteIdentical': True})

diff_records = []
for relative in changed_paths:
    before, after = (PRIOR / relative).read_text(), (SOURCE / relative).read_text()
    assert before != after
    patch = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                       fromfile='prior/' + relative, tofile='current/' + relative))
    diff_records.append({'relativePath': relative, 'prior': record(PRIOR / relative),
                         'current': record(SOURCE / relative), 'unifiedDiff': patch})

for relative in new_paths:
    assert not (PRIOR / relative).exists()

bounds = {}
for node in ast.parse((SOURCE / checker_paths[0]).read_text()).body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        name = node.targets[0].id
        if name.endswith('_SECONDS') or name in ['MAX_SCROLLS', 'MAX_MATCH_ACTIONS']:
            bounds[name] = ast.literal_eval(node.value)
assert bounds == {'SETUP_SECONDS': 600, 'MODE_SECONDS': 900, 'ENTRY_SECONDS': 45, 'ACTION_SECONDS': 30,
                  'EXIT_SECONDS': 25, 'CLEANUP_SECONDS': 180, 'MAX_SCROLLS': 16, 'MAX_MATCH_ACTIONS': 300}
host = SOURCE / changed_paths[1]
prior_host = PRIOR / changed_paths[1]
bound_pattern = r'postDelayed|timeoutMillis\s*=|requestExitAndWait\s*='
assert [item['text'] for item in matched_lines(host, bound_pattern)] == [
    item['text'] for item in matched_lines(prior_host, bound_pattern)]
assert 'main.postDelayed(closeFallback, 250)' in host.read_text()
assert 'timeoutMillis = 1_500' in host.read_text()
barrier = SOURCE / new_paths[0]
assert 'val acknowledged: Boolean get() = nativeBarrierElapsedRealtimeMs != null' in barrier.read_text()
assert 'facts.put("closeSignalAcknowledged", closeSignal?.acknowledged == true)' in host.read_text()
assert 'facts.put("closeSignalAcknowledged", false)' not in host.read_text()
assert 'facts.put("closeSignalAcknowledged", true)' not in host.read_text()
checker_text = (SOURCE / checker_paths[1]).read_text()
assert '"processExitRequested", "closeSignalAcknowledged"):' in checker_text
assert '"Missing actual native teardown marker: " + name' in checker_text
producer = json.loads((BASE / 'producer-evidence-summary.json').read_text())
new_test_suites = [suite for suite in producer['junitSuites'] if suite['name'].endswith('.NativeSignalDispatchTest')]
assert len(new_test_suites) == 1 and new_test_suites[0]['actualCases'] == 8

correlation = {
    'runId': 34456443339,
    'headSha': HEAD,
    'priorRunId': 34450246541,
    'priorHeadSha': 'a7278686170243795e505ce4f6a6788e912c01fe',
    'sourceArchiveVerified': True,
    'sourceArchiveReceipt': record(source_receipt_path),
    'sourceArchive': record(archive),
    'selectedExtractedSourcesMatchArchiveMembers': archived_members,
    'checkerSourceHashes': {Path(relative).name: digest(SOURCE / relative) for relative in checker_paths},
    'checkerAndWorkflowUnchanged': True,
    'strictTeardownCheckUnchanged': True,
    'byteIdenticalSourceComparisons': comparisons,
    'changedSourceComparisons': diff_records,
    'newSourceFiles': [record(SOURCE / relative) for relative in new_paths],
    'checkerBounds': bounds,
    'nativeFallbackMs': 250,
    'nativeRendererExitWaitMs': 1500,
    'nativeHostBoundLinesUnchanged': matched_lines(host, bound_pattern),
    'workflowBoundLines': matched_lines(SOURCE / '.github/workflows/godot-compare.yml', r'timeout-minutes|timeout --signal'),
    'strictCheckerLines': matched_lines(SOURCE / checker_paths[1], r'closeSignalAcknowledged|Missing actual native teardown'),
    'barrierSourceLines': matched_lines(barrier, r'.'),
    'pluginObservationLines': matched_lines(SOURCE / changed_paths[0], r'signalDispatch|Close |closeSignalObservation|outgoing.finish'),
    'hostObservationLines': matched_lines(host, r'Close |closeSignalAcknowledged|closeSignalObservation'),
    'executedBarrierUnitSuite': new_test_suites[0],
    'sourceReviewFindings': [
        'Acknowledgment is read from a per-plugin AtomicReference only after the scheduled native-signal barrier executes.',
        'The Close dispatch timestamp is set before emitSignal; the native barrier timestamp is set before queue completion and the posted main callback.',
        'Queue disposal, fallback and process death do not write or clear the native-barrier observation.',
        'The host final document reads the barrier directly instead of treating main-thread completion or its fallback as acknowledgment.',
        'Terminal Close queue admission and native delivery remain distinct. Missing dispatch logs identify an unobserved dispatch stage, not its scheduling cause.',
    ],
    'scope': 'Read-only exact archived source and retained producer-test correlation. No build, native execution, Git command or CI dispatch. Unit-test success does not qualify the failed native cases.',
}
output = BASE / 'source-close-barrier-correlation.json'
with output.open('x') as stream:
    stream.write(json.dumps(correlation, indent=2) + '\n')
print(json.dumps({'output': record(output), 'sourceArchiveVerified': True,
                  'checkerAndWorkflowUnchanged': True, 'checkerBounds': bounds}, indent=2))
