"""First review of current original runtime outcomes and Python case results."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import zipfile

ROOT = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34503251315')
REPORTS = ROOT / 'android-jvm-reports'
NATIVE = REPORTS / 'build/ci/android'
SOURCE = ROOT.parent / 'source-1cd34a3/source-1cd34a3'
HEAD = '1cd34a36753ed0112e6684f6525592dab8ef2edb'


def identity(path):
    with path.open('rb') as stream:
        digest = sha256()
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def read(path):
    return json.loads(path.read_text())


def utc(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def save(name, value):
    path = ROOT / 'review' / name
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    return identity(path)


job_path = ROOT / 'job-102958971991.log'
job_lines = job_path.read_text().splitlines()
job_receipt = read(ROOT / 'job-102958971991.collected.json')
assert identity(job_path)['sha256'] == job_receipt['sha256']
assert job_receipt['conclusion'] == 'success' and job_receipt['headSha'] == HEAD
job = next(v for v in read(ROOT / 'last-jobs-status.json')['jobs'] if v['id'] == 102958971991)
assert job['head_sha'] == HEAD and job['conclusion'] == 'success'
host_step = next(v for v in job['steps'] if v['name'] == 'Test the Android UI qualification checker')
assert host_step['conclusion'] == 'success'
cases = []
for number, line in enumerate(job_lines, 1):
    match = re.fullmatch(r'(\S+) (test_\S+) \(([^)]+)\) \.\.\. (ok|FAIL|ERROR|skipped.*)', line)
    if not match:
        continue
    cases.append({'line': number, 'utc': match[1], 'test': match[2], 'case': match[3], 'outcome': match[4]})
assert cases
assert len({(v['test'], v['case']) for v in cases}) == len(cases)
assert all(v['outcome'] == 'ok' for v in cases)
assert all(utc(host_step['started_at']) <= utc(v['utc']) < utc(host_step['completed_at'])
           or utc(v['utc']).replace(microsecond=0) == utc(host_step['completed_at']) for v in cases)
summaries = [{'line': i, 'text': line, 'count': int(m[1])}
             for i, line in enumerate(job_lines, 1)
             if (m := re.search(r'\bRan (\d+) tests? in ', line))]
assert len(summaries) == 1 and summaries[0]['count'] == len(cases)
following = job_lines[summaries[0]['line']:summaries[0]['line'] + 4]
assert any(re.fullmatch(r'\S+ OK', line) for line in following)
host_receipt = save('python-checker-case-audit.json', {
    'runId': 34503251315, 'headSha': HEAD, 'createdAtUtc': datetime.now(timezone.utc).isoformat(),
    'jobLog': identity(job_path), 'step': host_step, 'caseCount': len(cases),
    'outcomes': dict(Counter(v['outcome'] for v in cases)), 'uniqueCases': True,
    'summaries': summaries, 'followingSummaryLines': following, 'cases': cases,
    'scope': 'Independent enumeration of current completed-job host test lines; no tests rerun. Step API times have whole-second precision.',
})

integrity = read(ROOT / 'android-jvm-reports.integrity.json')
archive_path = Path(integrity['archivePath'])
archive_identity = identity(archive_path)
assert archive_identity['bytes'] == integrity['archiveBytes'] == integrity['apiBytes']
assert 'sha256:' + archive_identity['sha256'] == integrity['apiDigest'] == integrity['archiveDigest']
selected_originals = []
with zipfile.ZipFile(archive_path) as archive:
    members = archive.namelist()
    assert len(members) == len(set(members))
    excluded = [v for v in members if v.startswith(('docs/screenshots/', 'artifacts/'))]
    assert not excluded

    def original(path):
        relative = path.relative_to(REPORTS).as_posix()
        raw = archive.read(relative)
        assert path.read_bytes() == raw, relative
        result = identity(path)
        selected_originals.append(result)
        return result

    display_path = NATIVE / 'display-configuration.json'
    display = read(display_path)
    assert display['guestApiVerified'] and display['displayVerified']
    assert display['actualAndroidApi'] == display['expectedAndroidApi'] == 35
    assert (NATIVE / 'android-api.log').read_text().strip() == '35'
    original(display_path)
    original(NATIVE / 'android-api.log')
    runtime_path = NATIVE / 'runtime-variants.json'
    runtime = read(runtime_path)
    original(runtime_path)
    assert runtime['passed'] and runtime['sameEmulatorBoot']
    assert runtime['debugExitCode'] == runtime['optimizedTestSignedExitCode'] == 0
    native = runtime['godotSessionSmoke']
    assert native['requested'] and native['allRequestedPhasesPassed']
    assert native['debugPhaseExitCode'] == native['optimizedTestSignedPhaseExitCode'] == 0
    assert native['debugRendererDeathRequested'] and not native['optimizedRendererDeathRequested']
    expected_checks = {'installation'} | {mode + '.' + name for mode in ('2d', '3d') for name in (
        'practice-baseline', 'standard-hand', 'native-entry', 'home-interruption', 'recents-interruption',
        'standard-return', 'renderer-death', 'leave-cancel', 'standard-action', 'leave-end')}
    variants = {}
    for variant in ('debug', 'optimized-test-signed'):
        directory = NATIVE / 'godot-session' / variant
        result_path = directory / 'runtime/godot-session-result.json'
        result = read(result_path)
        original(result_path)
        command_path = directory / 'command.log'
        original(command_path)
        commands = command_path.read_text().splitlines()
        assert not any(line.startswith('FAILED ') for line in commands)
        assert commands[-1].startswith('Android Godot session smoke: passed; ')
        inputs_path = directory / 'package-inputs.json'
        inputs = read(inputs_path)
        original(inputs_path)
        ordinary_path = NATIVE / variant / 'smoke-result.json'
        ordinary = read(ordinary_path)
        original(ordinary_path)
        assert ordinary['passed'] and result['status'] == 'passed' and result['passed']
        assert not result.get('error') and not result.get('diagnostic_or_restore_errors')
        assert result['source_revision']['value'] == inputs['sourceRevision'] == HEAD
        assert result['variant_label'] == inputs['variant'] == variant
        assert result['engine_gameplay_requested'] is False and result['requested_modes'] == ['2d', '3d']
        assert result['identity']['actual_font_scale'] == '1.0'
        assert result['identity']['checker_sha256'] == identity(SOURCE / 'scripts/smoke-android-godot-session.py')['sha256']
        assert result['identity']['helper_sha256'] == identity(SOURCE / 'scripts/smoke-android-ui.py')['sha256']
        assert inputs['verified'] and inputs['activation']['verified']
        assert (result['identity']['input_apk_sha256'] == result['identity']['installed_apk_sha256']
                == inputs['apkSha256'] == ordinary['apk_sha256'])
        assert result['identity']['input_apk_bytes'] == result['identity']['installed_apk_bytes']
        assert set(result['checks']) == expected_checks
        start, end = utc(result['started_utc']), utc(result['ended_utc'])
        duration = (end - start).total_seconds()
        assert 0 < duration < 20 * 60
        skipped = []
        for name, check in result['checks'].items():
            assert start <= utc(check['started_utc']) <= utc(check['ended_utc']) <= end
            if variant == 'optimized-test-signed' and name.endswith('.renderer-death'):
                assert check['status'] == 'skipped' and 'Explicit --skip-renderer-death' in check['reason']
                skipped.append(name)
            else:
                assert check['status'] == 'passed', (variant, name)
        signals = result['intentional_signals']
        if variant == 'debug':
            assert signals == [result['checks'][mode + '.renderer-death']['signal'] for mode in ('2d', '3d')]
            for signal in signals:
                assert signal['returncode'] == 0 and signal['stdout'] == 'PARTYDECK_RENDERER_SIGNALLED\n' and signal['stderr'] == ''
                assert signal['signal'] == 'SIGKILL' and signal['renderer']['name'] == 'dev.partydeck.app:godot'
                assert signal['shell']['name'] == 'dev.partydeck.app'
                assert signal['shell']['uid'] == signal['renderer']['uid']
                assert signal['shell']['pid'] != signal['renderer']['pid']
                assert signal['shell']['start_ticks'] > 0 and signal['renderer']['start_ticks'] > 0
        else:
            assert signals == []
        crash_path = directory / 'runtime/logs/crash.log'
        logcat_path = directory / 'runtime/logs/logcat.log'
        original(crash_path)
        original(logcat_path)
        assert crash_path.read_bytes() == b''
        crash_matches = [line for line in logcat_path.read_text().splitlines()
                         if re.search(r'SIGABRT|NoSuchMethodError|JNI DETECTED|FATAL EXCEPTION|>>> dev\.partydeck\.app(?::godot)? <<<|Process: dev\.partydeck\.app(?::godot)?, PID:', line)]
        assert not crash_matches
        assert all(v['status'] == 'captured' for v in result['captures'])
        variants[variant] = {
            'result': identity(result_path), 'packageInputs': identity(inputs_path),
            'ordinaryUiResult': identity(ordinary_path), 'commandLog': identity(command_path),
            'status': result['status'], 'phaseExitCode': 0, 'startedUtc': result['started_utc'],
            'endedUtc': result['ended_utc'], 'recordedSessionDurationSeconds': duration,
            'checks': result['checks'], 'checkStatuses': dict(Counter(c['status'] for c in result['checks'].values())),
            'explicitlySkippedChecks': sorted(skipped), 'intentionalSignals': signals,
            'crashLog': identity(crash_path), 'logcat': identity(logcat_path),
            'matchingCrashSignatures': crash_matches, 'engineGameplayRequested': False,
            'declaredCapturedCount': len(result['captures']),
            'diagnosticOrRestoreErrors': result.get('diagnostic_or_restore_errors', []),
        }

context_lines = [line for line in job_lines if re.search(r'Z   PARTYDECK_(ANDROID_API|ANDROID_GODOT_SESSION_SMOKE|SOURCE_REVISION): ', line)]
assert context_lines
for line in context_lines:
    name, value = line.split('Z   ', 1)[1].split(': ', 1)
    assert value == {'PARTYDECK_ANDROID_API': '35', 'PARTYDECK_ANDROID_GODOT_SESSION_SMOKE': '1',
                     'PARTYDECK_SOURCE_REVISION': HEAD}[name]
triage = save('runtime-result-triage.json', {
    'runId': 34503251315, 'headSha': HEAD, 'createdAtUtc': datetime.now(timezone.utc).isoformat(),
    'outcome': 'All requested ordinary and native phases passed; no first failure found in retained original results/logs.',
    'originalReportZip': archive_identity, 'reportMemberCount': len(members),
    'excludedHistoricalPathCount': len(excluded),
    'selectedFilesComparedByteForByteWithOriginalZip': selected_originals,
    'runtimeSummary': identity(runtime_path), 'display': identity(display_path), 'guestApi': 35,
    'jobLog': identity(job_path), 'jobContextLines': context_lines,
    'sourceReuse': identity(ROOT / 'shared-source-reuse.json'),
    'sourceInputs': identity(ROOT / 'review/source-inputs-audit.json'), 'variants': variants,
    'scope': 'First original-evidence triage. Final result records, checked-source identities, ZIP bytes and job context agree. Full package inspection, independent process/capture binding and original pixel review follow separately. Debug signal acknowledgments are retained final-result command output; guarded-kill.log files themselves contain scripts. Current APK input and installed hashes agree in receipts but require retained package byte verification.',
    'limits': ['API35 engine gameplay was not invoked.',
               'Optimized renderer death remains explicitly unqualified.',
               'Normal-text single-emulator practice does not establish TalkBack speech/traversal, continuous pixel privacy, physical LAN, physical devices or distribution signing.'],
    'auditScript': identity(Path(__file__)),
})
print(json.dumps({'pythonAudit': host_receipt, 'pythonCases': len(cases), 'runtimeTriage': triage,
                  'nativeCheckStatuses': {v: row['checkStatuses'] for v, row in variants.items()},
                  'recordedSessionSeconds': {v: row['recordedSessionDurationSeconds'] for v, row in variants.items()}}, indent=2))
