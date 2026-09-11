#!/usr/bin/env python3
"""Private source/evidence review only. Does not invoke Godot or decode images."""
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REVIEW = Path(__file__).resolve().parent
OWNER = Path('/tmp/partydeck-3d-short-context-regression-20260911-w5prkctr')
REPO = Path('/root/projects/PartyDeck')
PINS = {
    'three_d_scene_check.gd': '3524494dd0f1baa6f1016e2e6bb3ef9f746472202c2018559f0515140bf604d7',
    'candidate.patch': 'f0f2da534a699d053bdaa79aef9b5e3238e02f110e11586cb7d2cbaf471caecb',
    'runs/pair-v1/pair-receipt.json': '4ef0d192b599106b6b6cb5f0a2ad48ab15e8dbed3cdcbc67392ae847bd417388',
    'runs/pair-v1/baseline/run-receipt.json': '3fcdf20053e3c1edaa6bace08d397ac96e80651c3f82dd3454e52d997cf4d760',
    'runs/pair-v1/candidate/run-receipt.json': '19b25318c757b4c26de44a512521eaff69d5f8b550a1c568b63a845aec7a147b',
    'FROZEN.json': '322d21d29051067fa8f0e8355ee5159937ede9921f59680b96db1ab4951c65ff',
    'inputs/ordinary-claim-launch.json': 'e2ebe47a74369422fe9c45feb4836d757a5e3bd5238a1c3aaaa3b980be533671',
    'baseline-project/presentations/three_d/table.gd': 'a9edd383b71832b41d3fd307d3cf4397fe33df099c54471cb16006da0246e061',
    'candidate-project/presentations/three_d/table.gd': 'a91e94b910f763efb9c108d9e7602230736c503c6e53e4bd018a61ad9eebeb4d',
}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def record(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}


def read_json(path):
    return json.loads(path.read_text())


result = {'reviewer': '/root/pixel_d2_sea', 'verifiedAtUtc': datetime.now(timezone.utc).isoformat()}
for relative, expected in PINS.items():
    assert digest(OWNER / relative) == expected, relative
result['pinnedInputs'] = [record(OWNER / relative) for relative in PINS]

freeze = read_json(OWNER / 'FROZEN.json')
listed = set()
for entry in freeze['files']:
    relative = Path(entry['path'])
    assert not relative.is_absolute() and '..' not in relative.parts
    assert entry['path'] not in listed
    listed.add(entry['path'])
    path = OWNER / relative
    assert path.is_file() and not path.is_symlink(), relative
    assert path.stat().st_size == entry['bytes'] and digest(path) == entry['sha256'], relative
    assert not path.stat().st_mode & 0o222, relative
actual = set()
for path in OWNER.rglob('*'):
    assert not path.is_symlink(), path
    assert not path.stat().st_mode & 0o222, path
    if path.is_file() and path != OWNER / 'FROZEN.json':
        actual.add(path.relative_to(OWNER).as_posix())
assert actual == listed
assert len(listed) == freeze['fileCount'] == 531
assert sum(entry['bytes'] for entry in freeze['files']) == freeze['fileBytes'] == 6028952
result['ownerFreeze'] = {'manifest': record(OWNER / 'FROZEN.json'), 'verifiedFiles': len(listed),
                         'verifiedBytes': freeze['fileBytes'], 'allReadOnly': True, 'inventoryExact': True}

pair = read_json(OWNER / 'runs/pair-v1/pair-receipt.json')
runs = [read_json(OWNER / f'runs/pair-v1/{name}/run-receipt.json') for name in ('baseline', 'candidate')]
assert pair['runs'] == runs and pair['result'] == 'passed'
assert runs[0]['externalInputs'] == runs[1]['externalInputs']
run_results = []
for run in runs:
    before = run['sourceBefore']
    assert before == run['sourceAfter']
    project = Path(run['command']['cwd'])
    for entry in before['files']:
        path = project / entry['path']
        assert path.stat().st_size == entry['bytes'] and digest(path) == entry['sha256'], path
    for entry in before['tools']:
        assert digest(REPO / 'godot/tools' / entry['path']) == entry['sha256'], entry
    fingerprint = hashlib.sha256(json.dumps({'files': before['files'], 'tools': before['tools']},
                                            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert fingerprint == before['fingerprint']
    assert before['excluded'] == ['.godot/']
    for path, expected in run['externalInputs'].items():
        assert digest(path) == expected, path
    assert digest(run['command']['log']) == run['command']['logSha256']
    assert run['tableSha256'] == digest(project / 'presentations/three_d/table.gd')
    assert run['inputsUnchanged'] and run['expectedResultObserved']
    for capture in run['captures']:
        assert record(Path(capture['path'])) == capture
    argv = run['command']['argv']
    assert argv[argv.index('--script') + 1] == str(OWNER / 'three_d_scene_check.gd')
    assert argv[argv.index('--resolution') + 1] == '389x215'
    for argument in ['--check-width=389', '--check-height=215', '--check-text-scale=2.0',
                     '--check-short-public-context=true', '--manual-bridge', '--presentation=3d',
                     '--check-fixture=' + str(OWNER / 'inputs/ordinary-claim-launch.json')]:
        assert argument in argv, argument
    assert '--check-touch-drag=true' not in argv and '--check-lobby=true' not in argv
    run_results.append({'name': run['name'], 'sourceFingerprint': fingerprint,
                        'verifiedSourceFiles': len(before['files']), 'verifiedSourceTools': len(before['tools']),
                        'sourceBeforeEqualsAfter': True, 'pairEntryEqualsIndividualReceipt': True,
                        'externalInputs': run['externalInputs'], 'command': {key: run['command'][key] for key in
                            ('argv', 'cwd', 'startedUtc', 'finishedUtc', 'elapsedSeconds', 'exitCode', 'log', 'logSha256')},
                        'captureCount': len(run['captures']), 'capturesHashedOnly': True})
maps = [{entry['path']: entry for entry in run['sourceBefore']['files']} for run in runs]
changed = [key for key in sorted(maps[0].keys() | maps[1].keys()) if maps[0].get(key) != maps[1].get(key)]
assert changed == ['presentations/three_d/table.gd']
assert runs[0]['sourceBefore']['tools'] == runs[1]['sourceBefore']['tools']
normalized_argv = []
for run in runs:
    normalized_argv.append([arg.replace(str(OWNER / f"{run['name']}-project"), '<project>')
                           .replace(str(OWNER / f"runs/pair-v1/{run['name']}"), '<output>')
                           for arg in run['command']['argv']])
assert normalized_argv[0] == normalized_argv[1]
result['executionEvidence'] = {'runs': run_results, 'sourceDifferences': changed,
                               'sameCheckerFixtureToolsAndNormalizedArguments': True,
                               'recordedEngine': {key: pair['engine'][key] for key in ('path', 'sha256', 'version')},
                               'engineExecutedOrRehashedByReviewer': False}
baseline_log = Path(runs[0]['command']['log']).read_text()
fixed_log = Path(runs[1]['command']['log']).read_text()
error_pattern = re.compile(r'(?m)^\s*(?:SCRIPT ERROR|SHADER ERROR|USER ERROR|ERROR):.*$')
assert error_pattern.findall(baseline_log) == ['\nERROR: The short viewport leaves no visible scroll space for public context or actions.']
assert not error_pattern.search(fixed_log)
assert runs[0]['command']['exitCode'] == 1 and runs[1]['command']['exitCode'] == 0
report_path = OWNER / 'runs/pair-v1/candidate/report.json'
report = read_json(report_path)
assert report['result'] == 'passed' and (report['width'], report['height'], report['textScale']) == (389, 215, 2)
context = [entry for entry in report['observations'] if entry.get('check') == 'short-public-context']
assert context == [{'actionsReached': 2, 'allPublicCharactersReached': True, 'check': 'short-public-context',
                    'claim': 'Orbit claimed 1 Crown. Challenge or play on.', 'round': 'ROUND 4',
                    'scrollHeight': 103.0, 'scrollReached': 907}]
result['executionEvidence']['fixedReport'] = record(report_path)
result['executionEvidence']['newObservation'] = context[0]
result['executionEvidence']['recordedInputs'] = [entry for entry in report['observations'] if 'input' in entry]
result['executionEvidence']['baselineExpectedErrorOnly'] = True
result['executionEvidence']['fixedEngineErrors'] = []
captures = read_json(OWNER / 'CAPTURES.json')
assert captures['count'] == len(captures['captures']) == 9
assert [{key: entry[key] for key in ('path', 'bytes', 'sha256')} for entry in captures['captures']] == [
    capture for run in runs for capture in run['captures']]
result['newPixelReview'] = {'manifest': record(OWNER / 'CAPTURES.json'), 'identities': 9,
                           'directlyViewed': 0, 'pixelCoverageByAlias': 0, 'unviewed': 9,
                           'note': 'Hash integrity only; no new capture decoding or prior pixel review repeated.'}

baseline_path = REVIEW / 'baseline-three_d_scene_check.gd'
baseline = baseline_path.read_text()
candidate = (OWNER / 'three_d_scene_check.gd').read_text()
assert digest(baseline_path) == '5d36c98fc638ebeb28c906350950bb6e7b7e5f111d560e2c62461db0c5e3d32e'


def functions(source):
    starts = list(re.finditer(r'^func (\w+)\(', source, re.MULTILINE))
    return {match.group(1): source[match.start(): starts[i + 1].start() if i + 1 < len(starts) else len(source)]
            for i, match in enumerate(starts)}


original_functions, candidate_functions = functions(baseline), functions(candidate)
assert len(original_functions) == 11 and len(candidate_functions) == 14
changed_functions = [name for name in original_functions if original_functions[name] != candidate_functions[name]]
assert changed_functions == ['_run', '_click']
added_functions = [name for name in candidate_functions if name not in original_functions]
assert added_functions == ['_check_short_public_context', '_context_clip', '_scroll_into_view']
optin = '\tif _options.get("short-public-context", "false") == "true" and not await _check_short_public_context(state.game):\n\t\treturn\n'
assert candidate_functions['_run'].replace(optin, '', 1) == original_functions['_run']
original_click = original_functions['_click']
scroll_loop = original_click[original_click.index('\tvar ancestor := target.get_parent()'):original_click.index('\tvar point :=')]
assert candidate_functions['_scroll_into_view'].partition('\n')[2] == scroll_loop + '\n'
assert candidate_functions['_click'].replace('\tawait _scroll_into_view(target)\n', scroll_loop, 1) == original_click
restored = candidate.replace(optin, '', 1)
for name in added_functions:
    restored = restored.replace(candidate_functions[name], '', 1)
restored = restored.replace('\tawait _scroll_into_view(target)\n', scroll_loop, 1)
assert restored == baseline
result['sourcePreservation'] = {'originalFunctionCount': len(original_functions), 'candidateFunctionCount': len(candidate_functions),
                               'changedExistingFunctions': changed_functions, 'newFunctions': added_functions,
                               'unchangedFunctions': [name for name in original_functions if name not in changed_functions],
                               'runEqualsOriginalAfterRemovingOptInCall': True,
                               'clickEqualsOriginalAfterInliningExtractedHelper': True,
                               'extractedHelperBodyExactlyMatchesOldScrollLoop': True,
                               'wholeCheckerEqualsOriginalAfterMechanicalRestoration': True,
                               'restoredSha256': hashlib.sha256(restored.encode()).hexdigest()}

replay = REVIEW / 'patch-replay'
target = replay / 'godot/renderer/tests/three_d_scene_check.gd'
target.parent.mkdir(parents=True, exist_ok=False)
shutil.copyfile(baseline_path, target)
patch = REVIEW / 'reviewed.patch'
shutil.copyfile(OWNER / 'candidate.patch', patch)
commands = []
for argv in [['git', 'apply', '--check', '--whitespace=error-all', str(patch)],
             ['git', 'apply', '--whitespace=error-all', str(patch)]]:
    completed = subprocess.run(argv, cwd=replay, capture_output=True, text=True, check=False)
    commands.append({'argv': argv, 'cwd': str(replay), 'exitCode': completed.returncode,
                     'stdout': completed.stdout, 'stderr': completed.stderr})
    assert completed.returncode == 0, commands[-1]
assert target.read_bytes() == (OWNER / 'three_d_scene_check.gd').read_bytes()
result['patchReplay'] = {'commands': commands, 'result': record(target), 'byteIdenticalToCandidate': True}
result['completedAtUtc'] = datetime.now(timezone.utc).isoformat()
result['result'] = 'passed'
output = REVIEW / 'EVIDENCE-VERIFICATION.json'
output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps({'result': result['result'], 'receipt': record(output), 'ownerFilesVerified': 531,
                  'sourceDifferences': changed, 'patchReplay': 'byte-identical', 'pixelReview': '9 unviewed'}, indent=2))
