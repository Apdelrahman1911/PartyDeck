"""Audit original JUnit XML, lint reports and completed job log; no tests rerun."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34503251315')
REPORTS = ROOT / 'android-jvm-reports'
REVIEW = ROOT / 'review'
REVIEW.mkdir(exist_ok=True)
MODULE_PREFIXES = {
    'androidApp': 'androidApp', 'composeApp': 'composeApp', 'core': 'core',
    'games': 'games', 'godot/android-renderer': 'androidRenderer',
    'godot/bridge': 'bridge', 'session': 'session', 'transport': 'transport',
}
LINT_PATHS = {'androidApp/build/reports/lint-results-debug.xml',
              'godot/android-renderer/build/reports/lint-results-debug.xml'}


def identity(path):
    data = path.read_bytes()
    return {'file': str(path.relative_to(ROOT)), 'bytes': len(data), 'sha256': sha256(data).hexdigest()}


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result


job_path = ROOT / 'last-jobs-status.json'
job = next(j for j in json.loads(job_path.read_text())['jobs'] if j['id'] == 102958971991)
build = next(s for s in job['steps'] if s['name'] == 'Test, lint, and package Android')
assert build['conclusion'] == 'success'
start, end = timestamp(build['started_at']), timestamp(build['completed_at'])
keys = ('tests', 'failures', 'errors', 'skipped')
totals = Counter({k: 0 for k in keys})
modules = defaultdict(lambda: Counter({k: 0 for k in keys}))
case_ids, records, excluded_reports = set(), [], []
excluded_totals = Counter({k: 0 for k in keys})
excluded_case_ids = Counter()
for path in sorted(REPORTS.rglob('TEST-*.xml')):
    if '/test-results/' not in path.as_posix():
        continue
    suite = ET.fromstring(path.read_bytes())
    assert suite.tag == 'testsuite'
    rel = path.relative_to(REPORTS).as_posix()
    prefix = rel.split('/build/test-results/')[0]
    canonical = prefix in MODULE_PREFIXES
    module = MODULE_PREFIXES.get(prefix)
    task = rel.split('/build/test-results/')[1].split('/')[0]
    cases = suite.findall('testcase')
    actual = {'tests': len(cases),
              **{k: sum(len(c.findall(tag)) for c in cases)
                 for k, tag in [('failures', 'failure'), ('errors', 'error'), ('skipped', 'skipped')]}}
    assert actual == {k: int(suite.get(k, '0')) for k in keys}, rel
    rows = []
    for case in cases:
        if canonical:
            key = (module, task, case.get('classname'), case.get('name'))
            assert key not in case_ids, key
            case_ids.add(key)
        else:
            historical_prefix = prefix.split('/build-evidence/')[-1]
            key = (MODULE_PREFIXES.get(historical_prefix, historical_prefix), task,
                   case.get('classname'), case.get('name'))
            excluded_case_ids[key] += 1
        rows.append({**case.attrib, 'outcomes': [{'tag': e.tag, 'attributes': e.attrib, 'text': e.text}
                     for e in case if e.tag in ('failure', 'error', 'skipped')]})
    raw_time = suite.get('timestamp')
    within = start <= timestamp(raw_time) <= end if raw_time else None
    if not canonical:
        assert re.fullmatch(r'docs/screenshots/android-\d+/build-evidence/(?:' +
                            '|'.join(re.escape(p) for p in MODULE_PREFIXES) + ')', prefix), rel
        assert within is False, rel
        excluded_totals.update(actual)
        excluded_reports.append({'identity': identity(path), 'prefix': prefix, 'test_task': task,
                                 'suite': suite.get('name'), 'timestamp': raw_time,
                                 'timestamp_within_build_step': within,
                                 'actual_outcomes': actual, 'cases': rows,
                                 'exclusion_reason': 'Historical committed documentation copy outside canonical module output paths.'})
        continue
    assert within is True, rel
    totals.update(actual)
    modules[module].update(actual)
    records.append({'identity': identity(path), 'module': module, 'test_task': task,
                    'suite': suite.get('name'), 'timestamp': raw_time,
                    'timestamp_within_build_step': within, 'actual_outcomes': actual, 'cases': rows})
assert records
assert set(modules) == {'androidApp', 'androidRenderer', 'bridge', 'composeApp', 'core', 'games', 'session', 'transport'}
assert all(totals[k] == 0 for k in ('failures', 'errors', 'skipped')), dict(totals)
lint, excluded_lint = [], []
for path in sorted(REPORTS.rglob('lint-results-debug.xml')):
    root = ET.fromstring(path.read_bytes())
    assert root.tag == 'issues'
    rows = []
    for issue in root.findall('issue'):
        rows.append({k: issue.get(k) for k in ('id', 'severity', 'message', 'category', 'priority')} |
                    {'locations': [dict(loc.attrib) for loc in issue.findall('location')]})
    counts = Counter(row['severity'] for row in rows)
    entry = {'identity': identity(path), 'tool': root.get('by'),
             'severity_counts': dict(counts), 'issues': rows}
    if path.relative_to(REPORTS).as_posix() not in LINT_PATHS:
        excluded_lint.append(entry | {'exclusion_reason': 'Outside canonical module lint output paths.'})
        continue
    assert not (set(counts) & {'Error', 'Fatal'}), rows
    lint.append(entry)
assert len(lint) == 2
assert not excluded_reports and not excluded_lint, "Historical report copies remain in current upload"
log_path = ROOT / 'job-102958971991.log'
log_lines = log_path.read_text().splitlines()
ansi = re.compile(r'\x1b\[[0-9;]*[mK]')
task_lines = [ansi.sub('', line) for line in log_lines if '> Task ' in line and
              re.search(r':(?:jvmTest|testDebugUnitTest|lintDebug)(?:\s|$)', line)]
python_summaries = [line for line in log_lines if re.search(r'\bRan \d+ tests? in ', line)]
python_cases = [line for line in log_lines if re.search(r'Z test_.*\.\.\. (?:ok|FAIL|ERROR|skipped)', line)]
summary = {
    'schema_version': 1, 'audit_result': 'pass with lint warnings',
    'run_id': 34503251315, 'source_revision': job['head_sha'],
    'job_identity': identity(job_path), 'job_log_identity': identity(log_path),
    'build_step': build, 'report_count': len(records), 'case_identity_count': len(case_ids),
    'totals': dict(totals), 'modules': {m: dict(c) for m, c in sorted(modules.items())},
    'all_suite_counts_match_actual_case_elements': True,
    'xml_timestamps_within_current_build_step': sum(r['timestamp_within_build_step'] is True for r in records),
    'reports': records, 'lint': lint,
    'report_selection': {'canonical_module_prefixes': sorted(MODULE_PREFIXES),
        'canonical_lint_paths': sorted(LINT_PATHS),
        'excluded_historical_report_count': len(excluded_reports),
        'excluded_historical_case_occurrences': dict(excluded_totals),
        'excluded_distinct_case_identity_count': len(excluded_case_ids),
        'excluded_repeated_case_identity_count': sum(n > 1 for n in excluded_case_ids.values()),
        'excluded_historical_reports': excluded_reports, 'excluded_lint_reports': excluded_lint,
        'reason': 'This run is expected to exclude historical docs/screenshots and root artifacts paths. Current results count only exact canonical module outputs with timestamps inside this build step; original ZIP path cleanup is checked separately.'},
    'lint_warning_count': sum(l['severity_counts'].get('Warning', 0) for l in lint),
    'lint_error_or_fatal_count': 0,
    'recorded_gradle_test_and_lint_task_lines': task_lines,
    'separate_python_checker_summaries': python_summaries,
    'separate_python_checker_case_lines': python_cases,
    'scope': 'Independent enumeration of canonical retained outputs only; historical documentation copies are separately identified and excluded. No tests or builds rerun. JUnit, lint and checker-unit passes do not establish a passing production native-session smoke.',
}
path = REVIEW / 'test-and-lint-audit.json'
assert not path.exists(), path
path.write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({'receipt': identity(path), 'report_count': len(records), 'totals': dict(totals),
                  'modules': summary['modules'], 'lint_warnings': summary['lint_warning_count'],
                  'xml_timestamps_within_build_step': summary['xml_timestamps_within_current_build_step'],
                  'excluded_historical_reports': len(excluded_reports),
                  'excluded_historical_case_occurrences': dict(excluded_totals),
                  'python_summaries': python_summaries, 'python_case_line_count': len(python_cases)}, indent=2))
