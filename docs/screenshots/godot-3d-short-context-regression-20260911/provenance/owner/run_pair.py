#!/usr/bin/env python3
"""Private baseline/fixed execution; no shared renderer or tool changes."""
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
WORK = Path(__file__).resolve().parent
REPO = Path('/root/projects/PartyDeck')
sys.path.insert(0, str(REPO / 'godot/tools'))
spec = importlib.util.spec_from_file_location('renderer_tools', REPO / 'godot/tools/renderer.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
MEM_FLOOR = 3 * 1024**3
DISK_FLOOR = 1024**3
WORKING_RESERVE = 768 * 1024**2
OUTPUT_BOUND = 32 * 1024**2
LOCKS = [Path('/tmp/partydeck-godot.lock'),
         REPO / 'artifacts/evidence-storage/shm-evidence-arena-20260910/bulk-io.lock']
EXPECTED_FAILURE = 'The short viewport leaves no visible scroll space for public context or actions.'

def utc():
    return datetime.now(timezone.utc).isoformat()

def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()

def resources():
    info = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    work_bytes = 0
    for path in WORK.rglob('*'):
        try:
            if path.is_file():
                work_bytes += path.stat().st_size
        except FileNotFoundError:
            pass  # A short-lived engine cache file may disappear during sampling.
    return {'utc': utc(), 'memAvailableBytes': int(info['MemAvailable'].split()[0]) * 1024,
            'tmpFreeBytes': shutil.disk_usage(WORK).free,
            'privateWorkBytes': work_bytes}

def launch(argv, cwd, output, timeout=90):
    before = resources()
    if before['memAvailableBytes'] < MEM_FLOOR + WORKING_RESERVE + OUTPUT_BOUND \
            or before['tmpFreeBytes'] < DISK_FLOOR + OUTPUT_BOUND:
        raise RuntimeError('Prelaunch resource admission failed: ' + json.dumps(before))
    if before['privateWorkBytes'] >= OUTPUT_BOUND:
        raise RuntimeError('Private work exceeds the 32 MiB bound before launch.')
    print(json.dumps({'event': 'launch-admitted', 'argv': argv, 'resources': before,
                      'memoryMarginBytes': before['memAvailableBytes'] - MEM_FLOOR - WORKING_RESERVE - OUTPUT_BOUND,
                      'diskMarginBytes': before['tmpFreeBytes'] - DISK_FLOOR - OUTPUT_BOUND}), flush=True)
    record = {'argv': argv, 'cwd': str(cwd), 'startedUtc': utc(), 'before': before, 'guardSamples': []}
    started = time.monotonic()
    log_path = output / 'godot.log'
    with log_path.open('w') as log:
        child = subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while child.poll() is None:
                sample = resources()
                record['guardSamples'].append(sample)
                reason = None
                if sample['memAvailableBytes'] < MEM_FLOOR or sample['tmpFreeBytes'] < DISK_FLOOR:
                    reason = 'Live resource floor crossed'
                elif sample['privateWorkBytes'] >= OUTPUT_BOUND:
                    reason = 'Private work reached the 32 MiB bound'
                elif time.monotonic() - started > timeout:
                    reason = 'Bounded child timeout'
                if reason:
                    record['guardFailure'] = reason
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        pass
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    child.wait(timeout=3)
                    break
                time.sleep(0.25)
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=3)
        record['exitCode'] = child.returncode
    record.update({'finishedUtc': utc(), 'elapsedSeconds': round(time.monotonic() - started, 3),
                   'after': resources(), 'log': str(log_path), 'logSha256': digest(log_path)})
    (output / 'command.json').write_text(json.dumps(record, indent=2) + '\n')
    return record, log_path.read_text()

def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: run_pair.py FRESH_RUN_NAME')
    pair = WORK / 'runs' / sys.argv[1]
    pair.mkdir()
    held = []
    result = {'startedUtc': utc(), 'lockPaths': [str(path) for path in LOCKS], 'runs': [],
              'admission': {'memAvailableBytes': MEM_FLOOR + WORKING_RESERVE + OUTPUT_BOUND,
                            'tmpFreeBytes': DISK_FLOOR + OUTPUT_BOUND,
                            'workingReserveBytes': WORKING_RESERVE, 'privateWorkBoundBytes': OUTPUT_BOUND},
              'liveFloors': {'memAvailableBytes': MEM_FLOOR, 'tmpFreeBytes': DISK_FLOOR}}
    try:
        for path in LOCKS:
            handle = path.open('r+')
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BaseException:
                handle.close()
                raise
            held.append(handle)
        result['locksAcquiredUtc'] = utc()
        print(json.dumps({'event': 'both-locks-acquired', 'utc': result['locksAcquiredUtc'],
                          'resources': resources()}), flush=True)
        engine = (REPO / 'godot/qualification/build/toolchain/godot').resolve(strict=True)
        if digest(engine) != renderer.PINS['linux_x86_64']['executable_sha256']:
            raise RuntimeError('Pinned Godot executable hash mismatch.')
        version_output = pair / 'engine-version'
        version_output.mkdir()
        version, version_log = launch([str(engine), '--version'], REPO, version_output, timeout=20)
        if version['exitCode'] != 0 or version_log.strip() != renderer.PINS['version_output']:
            raise RuntimeError('Pinned Godot version mismatch.')
        result['engine'] = {'path': str(engine), 'sha256': digest(engine), 'version': version_log.strip(),
                            'versionCommand': version}
        harness = WORK / 'three_d_scene_check.gd'
        fixture = WORK / 'inputs/ordinary-claim-launch.json'
        for name, table_hash in [('baseline', 'a9edd383b71832b41d3fd307d3cf4397fe33df099c54471cb16006da0246e061'),
                                 ('candidate', 'a91e94b910f763efb9c108d9e7602230736c503c6e53e4bd018a61ad9eebeb4d')]:
            project = WORK / (name + '-project')
            table = project / 'presentations/three_d/table.gd'
            if digest(table) != table_hash or digest(fixture) != 'e2ebe47a74369422fe9c45feb4836d757a5e3bd5238a1c3aaaa3b980be533671':
                raise RuntimeError('Pinned project or authority fixture mismatch.')
            output = pair / name
            output.mkdir()
            before = renderer.source_snapshot(project)
            external = {str(path): digest(path) for path in [harness, fixture, Path(__file__).resolve()]}
            argv = ['xvfb-run', '-a', '-s', '-screen 0 1280x1600x24', str(engine), '--path', str(project),
                    '--rendering-method', 'gl_compatibility', '--display-driver', 'x11', '--audio-driver', 'Dummy',
                    '--resolution', '389x215', '--position', '0,0', '--script', str(harness), '--',
                    '--manual-bridge', '--presentation=3d', '--check-output=' + str(output),
                    '--check-fixture=' + str(fixture), '--check-width=389', '--check-height=215',
                    '--check-text-scale=2.0', '--check-short-public-context=true']
            command, log = launch(argv, project, output)
            after = renderer.source_snapshot(project)
            unchanged = before['fingerprint'] == after['fingerprint'] and all(digest(Path(path)) == sha for path, sha in external.items())
            report = json.loads((output / 'report.json').read_text()) if (output / 'report.json').exists() else None
            expected = command['exitCode'] == 1 and EXPECTED_FAILURE in log if name == 'baseline' else \
                command['exitCode'] == 0 and report is not None and report.get('result') == 'passed' \
                and any(item.get('check') == 'short-public-context' and item.get('allPublicCharactersReached') \
                        and item.get('actionsReached') == 2 for item in report['observations']) \
                and renderer.ENGINE_ERROR.search(renderer.ANSI.sub('', log)) is None
            captures = [{'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)} for path in sorted(output.glob('*.png'))]
            receipt = {'name': name, 'command': command, 'expectedResultObserved': bool(expected),
                       'sourceBefore': before, 'sourceAfter': after, 'externalInputs': external,
                       'inputsUnchanged': unchanged, 'tableSha256': table_hash, 'captures': captures}
            (output / 'run-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
            result['runs'].append(receipt)
            print(json.dumps({'event': 'check-finished', 'name': name, 'exitCode': command['exitCode'],
                              'expectedResultObserved': bool(expected), 'inputsUnchanged': unchanged}), flush=True)
            if not expected or not unchanged or command.get('guardFailure'):
                raise RuntimeError('Unexpected ' + name + ' check result; evidence preserved.')
        result['result'] = 'passed'
    except BlockingIOError:
        result.update({'result': 'deferred', 'error': 'A shared mutex is busy; no waiting with a lock held.'})
    except Exception as error:
        result.update({'result': 'failed', 'error': str(error)})
    finally:
        for handle in reversed(held):
            fcntl.flock(handle, fcntl.LOCK_UN)
            handle.close()
        result.update({'locksReleasedUtc': utc(), 'resourcesAfter': resources()})
        print(json.dumps({'event': 'all-locks-released', 'utc': result['locksReleasedUtc'],
                          'result': result['result'], 'resources': result['resourcesAfter']}), flush=True)
        (pair / 'pair-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['result'] == 'passed' else 75 if result['result'] == 'deferred' else 1

if __name__ == '__main__':
    sys.exit(main())
