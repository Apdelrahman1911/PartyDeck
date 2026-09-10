"""Correlate the completed Authority execution receipt with original log and XCResult."""
from pathlib import Path
import hashlib
import json
import re

BASE = Path('/tmp/partydeck-engine-ci/34478720554')
EVIDENCE = BASE / 'godot-ios-authority-gameplay/evidence'

def read(path): return json.loads(path.read_text())
def record(path):
    with path.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest}

checks = []
def check(label, condition):
    checks.append({'check': label, 'passed': bool(condition)})
    assert condition, label

execution = read(EVIDENCE / 'authority-host-test-result.json')
build = read(EVIDENCE / 'authority-host-build-result.json')
attachments = read(BASE / 'authority-attachment-evidence-summary.json')
package = read(BASE / 'authority-package-evidence-summary.json')
check('completed execution stage', execution['stage'] == 'native_authority_gameplay_execution')
check('same compiled executable in build, execution and original app',
      execution['executable_sha256'] == build['executable_sha256'] == package['executable']['sha256'])
check('execution consumes the audited engine/framework/PCK inputs',
      execution['inputs'] == build['inputs'] and execution['engine'] == build['engine'])
check('compiled and executed bounded gameplay reported', all(execution[key] is True for key in
      ['swift_authority_host_compiled', 'ios_authority_runtime_executed', 'last_light_gameplay_qualified', 'simulator_only']))
check('broader integration and device qualification remain false', all(execution[key] is False for key in
      ['dormant_engine_reentry_qualified', 'kmp_factory_qualified', 'device_metal_qualified']))
check('four reference fixture variants reported', execution['reference_full_matches'] == {
      'executed': True, 'randomness': 'reference_seed_2',
      'presentations': [{'mode': mode, 'text_scale': scale} for mode in ['2d', '3d'] for scale in [1, 2]]})
check('secure default result is launch and renderer exit only', execution['secure_default'] == {
      'launch_and_renderer_exit_executed': True, 'full_match_qualified': False})
test_log = (EVIDENCE / 'authority-host-test.log').read_text()
pattern = r"^Test Case '-\[AuthorityHostUITests\.AuthorityHostUITests (test\w+)\]' (passed|failed|skipped) \(([\d.]+) seconds\)\.$"
logged = [{'case': name, 'status': status, 'seconds': float(seconds)}
          for name, status, seconds in re.findall(pattern, test_log, re.MULTILINE)]
check('execution case names, results and printed durations match original native log', logged == execution['native_tests'])
check('original XCTest command completed successfully', '** TEST SUCCEEDED **' in test_log)
original_cases = {item['name'][:-2]: item for item in attachments['tests']}
check('five distinct cases match original XCResult', len(logged) == len(original_cases) == 5 and
      {item['case'] for item in logged} == set(original_cases))
for item in logged:
    original = original_cases[item['case']]
    check('original successful case without issues: ' + item['case'],
          item['status'] == 'passed' and original['result'] == 'Success' and not original['issues'])
    check('duration agrees to XCTest printed precision: ' + item['case'], abs(original['duration'] - item['seconds']) <= 0.001)
    check('bounded original attachment checks completed: ' + item['case'],
          bool(original['independentChecks']) and all(original['independentChecks'].values()))
summary = {'runId': 34478720554, 'headSha': 'c6ea1dd9f7966517fbee87a06b633d01c432c24d',
    'scope': 'All five original Simulator Authority fixture cases passed. This is not retained-engine, production KMP-factory, secure full-match, device Metal or physical-device qualification.',
    'executionReceipt': record(EVIDENCE / 'authority-host-test-result.json'),
    'buildReceipt': record(EVIDENCE / 'authority-host-build-result.json'),
    'originalTestLog': record(EVIDENCE / 'authority-host-test.log'),
    'attachmentAudit': record(BASE / 'authority-attachment-evidence-summary.json'),
    'packageAudit': record(BASE / 'authority-package-evidence-summary.json'),
    'nativeTests': execution['native_tests'], 'checks': checks}
output = BASE / 'authority-execution-evidence-summary.json'
with output.open('x') as stream: stream.write(json.dumps(summary, indent=2) + '\n')
print(json.dumps({'checksPassed': len(checks), 'receipt': record(output)}), flush=True)
