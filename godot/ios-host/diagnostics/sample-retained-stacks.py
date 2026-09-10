#!/usr/bin/env python3
"""Opt-in external sampling of the existing test-launched Simulator app.

This wrapper never launches the app, requests UI state, changes test deadlines,
or converts a diagnostic error into a different retained-runner exit status.
Darwin libproc declarations/layout come from Apple's published XNU headers.
sample syntax comes from Apple's sample(1); installed usage is also retained.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time

SAMPLE = Path('/usr/bin/sample')
BUNDLE_ID = 'dev.partydeck.godot.iosretained'
EXECUTABLE = 'RetainedHost'
POLL_SECONDS = 0.25
SAMPLE_SECONDS = 30
SAMPLE_INTERVAL_MS = 10
SAMPLE_WALL_SECONDS = 60
WATCH_SECONDS = 1200
MAX_LIFETIMES = 3
MAX_CAPTURES = 8
MAX_PENDING = 8
MAX_PIDS = 8192
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 512
MAX_CONTAINER_LOOKUPS = 12
EXPECTED_CASES = {
    'testActiveAndDormantBackgroundTransitionsStayConcealed',
    'testRepeated2DAnd3DKeepOneDormantEngine',
    'testStaleFirstReadyAndCloseCompletionReentry',
}


def stamp():
    return {'utc': datetime.now(timezone.utc).isoformat(),
            'wallTimeNs': time.time_ns(), 'monotonicNs': time.monotonic_ns()}


def record(path):
    path = Path(path)
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = os.fstat(stream.fileno())
    stat = path.stat()
    for name in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'):
        if getattr(before, name) != getattr(after, name) or getattr(after, name) != getattr(stat, name):
            raise RuntimeError('A diagnostic input changed identity while it was hashed.')
    return {'path': str(path), 'bytes': stat.st_size, 'sha256': digest,
            'device': stat.st_dev, 'inode': stat.st_ino}


def write_new(path, document):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(document, indent=2) + '\n')


def process_key(value):
    return (value['pid'], value['startSeconds'], value['startMicroseconds'],
            value['uid'], value['executablePath'])


def same_executable(left, right):
    return all(left[key] == right[key] for key in ('bytes', 'sha256', 'device', 'inode'))


def same_process(actual, expected):
    return bool(actual and actual['uid'] == os.getuid() and expected['uid'] == os.getuid()
                and process_key(actual) == process_key(expected))


class ProcBsdInfo(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        'flags', 'status', 'exitStatus', 'pid', 'ppid', 'uid', 'gid', 'ruid',
        'rgid', 'svuid', 'svgid', 'reserved')]
    _fields_ += [('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32)]
    _fields_ += [(name, ctypes.c_uint32) for name in
                 ('nfiles', 'pgid', 'jobCount', 'terminalDevice', 'terminalGroup')]
    _fields_ += [('nice', ctypes.c_int32), ('startSeconds', ctypes.c_uint64),
                 ('startMicroseconds', ctypes.c_uint64)]


class DarwinProcesses:
    def __init__(self):
        if platform.system() != 'Darwin' or platform.machine() != 'arm64':
            raise RuntimeError('Sampling requires the existing ARM64 macOS runner.')
        if ctypes.sizeof(ProcBsdInfo) != 136:
            raise RuntimeError('Unexpected public proc_bsdinfo structure layout.')
        self.lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        self.lib.proc_listallpids.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.lib.proc_listallpids.restype = ctypes.c_int
        self.lib.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                         ctypes.c_void_p, ctypes.c_int]
        self.lib.proc_pidinfo.restype = ctypes.c_int
        self.lib.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        self.lib.proc_pidpath.restype = ctypes.c_int
        own = self.identity(os.getpid())
        if not own or own['uid'] != os.getuid() or own['startSeconds'] <= 0:
            raise RuntimeError('The installed libproc did not validate this observer process.')
        self.self_check = own

    def bsd(self, pid):
        value = ProcBsdInfo()
        size = self.lib.proc_pidinfo(pid, 3, 0, ctypes.byref(value), ctypes.sizeof(value))
        return value if size == ctypes.sizeof(value) and value.pid == pid else None

    def identity(self, pid):
        before = self.bsd(pid)
        if before is None:
            return None
        buffer = ctypes.create_string_buffer(4096)
        size = self.lib.proc_pidpath(pid, buffer, ctypes.sizeof(buffer))
        after = self.bsd(pid)
        if size <= 0 or after is None or (before.startSeconds, before.startMicroseconds) != (after.startSeconds, after.startMicroseconds):
            return None
        return {'pid': pid, 'ppid': after.ppid, 'uid': after.uid,
                'startSeconds': after.startSeconds, 'startMicroseconds': after.startMicroseconds,
                'executablePath': os.fsdecode(buffer.value),
                'name': bytes(after.name).split(b'\0', 1)[0].decode(errors='replace')}

    def retained(self):
        values = (ctypes.c_int * MAX_PIDS)()
        count = self.lib.proc_listallpids(values, ctypes.sizeof(values))
        if count <= 0 or count >= MAX_PIDS:
            raise RuntimeError('Process inventory unavailable or exceeded its fixed bound.')
        found = []
        for pid in values[:count]:
            if pid <= 0:
                continue
            info = self.bsd(pid)
            if info is None or info.uid != os.getuid():
                continue
            name = bytes(info.name or info.comm).split(b'\0', 1)[0]
            if name != EXECUTABLE.encode():
                continue
            identity = self.identity(pid)
            if identity and identity['uid'] == os.getuid():
                found.append(identity)
        return found


CASE_RE = re.compile(r"^Test Case '-\[RetainedHostUITests\.RetainedHostUITests (test\w+)\]' (started|passed|failed)")
ACTION_RE = re.compile(r'^\s*t =\s*([0-9.]+)s Tap "(start-3d|switch-table)" (?:Button|Any)\s*$')


class TestLog:
    def __init__(self, path):
        self.path = Path(path)
        self.offset = 0
        self.line = 0
        self.identity = None
        self.pending = b''
        self.case = None

    def read(self):
        if not self.path.is_file():
            return []
        stat = self.path.stat()
        identity = (stat.st_dev, stat.st_ino)
        if self.identity is not None and (identity != self.identity or stat.st_size < self.offset):
            raise RuntimeError('The original XCTest log changed identity or was truncated.')
        self.identity = identity
        with self.path.open('rb') as stream:
            stream.seek(self.offset)
            chunk = stream.read(256 * 1024)
        self.offset += len(chunk)
        lines = (self.pending + chunk).split(b'\n')
        self.pending = lines.pop()
        if len(self.pending) > 256 * 1024:
            raise RuntimeError('An unterminated test-log line exceeded the parser bound.')
        events = []
        for raw in lines:
            self.line += 1
            text = raw.decode(errors='replace').rstrip('\r')
            case = CASE_RE.match(text)
            if case and case[1] in EXPECTED_CASES:
                self.case = case[1] if case[2] == 'started' else None
                events.append({'kind': 'case_' + case[2], 'case': case[1], 'line': self.line,
                               'rawLineSha256': hashlib.sha256(raw + b'\n').hexdigest(), **stamp()})
            action = ACTION_RE.match(text)
            if action and self.case:
                events.append({'kind': 'three_d_action', 'case': self.case,
                               'action': action[2], 'reportedTestSeconds': float(action[1]),
                               'line': self.line, 'rawLine': text,
                               'rawLineSha256': hashlib.sha256(raw + b'\n').hexdigest(), **stamp()})
        return events


def bounded_child_files():
    # Called only in the single-threaded observer's diagnostic child, never in
    # the retained runner. Each regular diagnostic file is capped independently.
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_BYTES, MAX_FILE_BYTES))


def stop_owned_tool(process):
    # Only a Popen child created in its own session is eligible. No signal is
    # ever sent to the sampled app PID.
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass  # The owned child may have exited since poll().
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)


def selected_device(evidence):
    path = evidence / 'simulator.json'
    if not path.is_file():
        return None
    value = json.loads(path.read_text())
    udid = value['device']['udid']
    if not re.fullmatch(r'[0-9A-Fa-f-]{36}', udid):
        raise RuntimeError('Invalid selected Simulator identity.')
    return udid


def report_pid(path):
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_FILE_BYTES:
        return None
    with path.open('rb') as stream:
        text = stream.read(65536).decode(errors='replace')
    value = re.search(r'^Process:\s+RetainedHost\s+\[(\d+)\]\s*$', text, re.MULTILINE)
    return int(value[1]) if value else None


class Observer:
    def __init__(self, host_root, output, command_started_ns):
        self.root = Path(host_root).resolve()
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=False, mode=0o700)
        # Raw stacks stay outside every upload glob until exact app identity and
        # the report PID are verified after the sample process has finished.
        self.staging = Path(tempfile.mkdtemp(prefix=f'.{self.output.name}-raw-', dir=self.output.parent))
        self.evidence = self.root / 'build/retained-host-test/evidence'
        self.built_app = self.root / 'build/retained-host-test/DerivedData/Build/Products/Debug-iphonesimulator/RetainedHost.app'
        self.log = TestLog(self.evidence / 'test.log')
        self.command_started_ns = command_started_ns
        self.events = 0
        self.events_dropped = 0
        self.tools = []
        self.targets = {}
        self.pending = []
        self.captures = []
        self.active = None
        self.disabled = False
        self.watch_started = None
        self.next_discovery = 0.0
        self.container = None
        self.container_lookups = 0
        self.reported_reasons = set()
        self.processes = None
        self.sample_available = False
        self.start = stamp()
        source = Path(__file__).read_bytes()
        with (self.output / 'sampler-source.py').open('xb') as stream:
            stream.write(source)

    def event(self, kind, **details):
        if self.events >= MAX_EVENTS:
            self.events_dropped += 1
            return
        self.events += 1
        with (self.output / 'events.jsonl').open('a') as stream:
            stream.write(json.dumps({'kind': kind, **stamp(), **details}) + '\n')

    def once(self, reason, **details):
        if reason not in self.reported_reasons:
            self.reported_reasons.add(reason)
            self.event(reason, **details)

    def auxiliary(self, label, command):
        path = self.output / (label + '.txt')
        started = stamp()
        process = None
        error = None
        with path.open('xb') as output:
            try:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                    stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
                    preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_FSIZE, (65536, 65536)))
                process.wait(timeout=5)
            except Exception as caught:
                error = f'{type(caught).__name__}: {caught}'[:2048]
                if process is not None:
                    stop_owned_tool(process)
        result = {'command': command, 'started': started, 'finished': stamp(),
                  'returnCode': process.returncode if process else None,
                  'error': error, 'output': record(path)}
        self.tools.append(result)
        return result

    def initialize(self):
        self.processes = DarwinProcesses()
        if not SAMPLE.is_file() or not os.access(SAMPLE, os.X_OK):
            raise RuntimeError('/usr/bin/sample is unavailable.')
        usage = self.auxiliary('installed-sample-usage', [str(SAMPLE)])
        usage_text = Path(usage['output']['path']).read_text(errors='replace')
        if usage['error']:
            raise RuntimeError('Installed sample usage invocation failed.')
        manuals = []
        for path in [Path('/usr/share/man/man1/sample.1'), Path('/usr/share/man/man1/sample.1.gz')]:
            if path.is_file() and path.stat().st_size <= 2 * 1024 * 1024:
                copy = self.output / ('installed-' + path.name)
                with copy.open('xb') as stream:
                    stream.write(path.read_bytes())
                manuals.append(record(copy))
        write_new(self.output / 'context.json', {
            'scope': 'Opt-in external statistical samples; no native behavior or test-gate changes.',
            'sourceHead': os.environ.get('GITHUB_SHA'), 'runId': os.environ.get('GITHUB_RUN_ID'),
            'runAttempt': os.environ.get('GITHUB_RUN_ATTEMPT'), 'system': platform.system(),
            'machine': platform.machine(), 'macVersion': platform.mac_ver()[0],
            'observerProcessCheck': self.processes.self_check, 'sampleExecutable': record(SAMPLE),
            'installedUsageMentionsFileOption': '-file' in usage_text,
            'installedManPages': manuals, 'samplerSource': record(self.output / 'sampler-source.py'),
            'clock': vars(time.get_clock_info('monotonic')),
            'clockScope': 'Observer UTC and monotonic timestamps are recorded together. No identical origin with Foundation systemUptime is assumed.',
            'limits': {'sampleSeconds': SAMPLE_SECONDS, 'intervalMilliseconds': SAMPLE_INTERVAL_MS,
                'sampleWallSeconds': SAMPLE_WALL_SECONDS, 'watchSecondsFromTestLog': WATCH_SECONDS,
                'sampledAppLifetimes': MAX_LIFETIMES, 'sampleInvocations': MAX_CAPTURES,
                'concurrentSampleInvocations': 1, 'pendingRequests': MAX_PENDING,
                'bytesPerSampleFile': MAX_FILE_BYTES, 'events': MAX_EVENTS,
                'containerLookups': MAX_CONTAINER_LOOKUPS},
            'samplingEffect': 'sample briefly suspends threads at sampling points. This is a diagnostic run; sampling overhead is not measured.',
            'rawOutputPolicy': 'Private sibling staging outside the artifact path. Promote only after exact lifetime/UID/path/executable and report-PID verification; otherwise discard raw bytes and retain bounded failure metadata.',
        })
        self.sample_available = True

    def disable(self, reason):
        self.disabled = True
        self.event('observer_disabled', reason=str(reason)[:2048])
        self.finish_capture('observer_disabled')

    def request(self, reason, case, marker=None):
        if len(self.pending) >= MAX_PENDING:
            self.once('pending_request_limit_reached')
            return
        self.pending.append({'reason': reason, 'case': case, 'marker': marker,
                             'requested': stamp(), 'requestedMonotonic': time.monotonic()})

    def discover(self):
        udid = selected_device(self.evidence)
        if udid is None or self.log.case is None:
            return
        candidates = []
        for item in self.processes.retained():
            if item['uid'] != os.getuid():
                continue
            path = Path(item['executablePath'])
            start_ns = item['startSeconds'] * 1_000_000_000 + item['startMicroseconds'] * 1000
            if path.name != EXECUTABLE or path.parent.name != EXECUTABLE + '.app':
                continue
            parts = [part.lower() for part in path.parts]
            if udid.lower() not in parts or 'coresimulator' not in parts or start_ns < self.command_started_ns:
                continue
            key = process_key(item)
            if key in self.targets and self.targets[key]['case'] != self.log.case:
                continue
            candidates.append(item)
        if len(candidates) != 1:
            if len(candidates) > 1:
                self.once('ambiguous_selected_simulator_app', candidatePids=[item['pid'] for item in candidates])
            return
        identity = candidates[0]
        key = process_key(identity)
        if key in self.targets:
            return
        if len(self.targets) >= MAX_LIFETIMES:
            self.once('sampled_app_lifetime_limit_reached')
            return
        process_path = Path(identity['executablePath']).resolve()
        if self.container is None or self.container / EXECUTABLE != process_path:
            if self.container_lookups >= MAX_CONTAINER_LOOKUPS:
                self.once('container_lookup_limit_reached')
                return
            self.container_lookups += 1
            response = self.auxiliary(f'container-{self.container_lookups:02}',
                ['xcrun', 'simctl', 'get_app_container', udid, BUNDLE_ID, 'app'])
            if response['returnCode'] != 0 or response['error']:
                return
            candidate = Path(Path(response['output']['path']).read_text().strip())
            if not candidate.is_absolute() or not candidate.is_dir():
                self.once('invalid_app_container_response')
                return
            self.container = candidate.resolve()
        executable = self.container / EXECUTABLE
        if executable != process_path:
            self.once('process_path_does_not_match_selected_app_container')
            return
        import plistlib
        plist = plistlib.loads((self.container / 'Info.plist').read_bytes())
        if plist.get('CFBundleIdentifier') != BUNDLE_ID or plist.get('CFBundleExecutable') != EXECUTABLE:
            self.once('installed_bundle_identity_mismatch')
            return
        installed = record(executable)
        built = record(self.built_app / EXECUTABLE)
        after = self.processes.identity(identity['pid'])
        if not same_process(after, identity) or installed['sha256'] != built['sha256'] or installed['bytes'] != built['bytes']:
            self.once('process_or_compiled_executable_changed_during_binding')
            return
        target = {'case': self.log.case, 'identity': after, 'selectedSimulatorUdid': udid,
                  'installedExecutable': installed, 'builtExecutable': built, 'boundAt': stamp()}
        self.targets[key] = target
        self.event('test_launched_app_bound', target=target)
        # Early coverage is intentionally independent of AX readiness and of
        # log delivery for switch-table. Exact sampling spans require the report.
        self.request('new_test_app_pid', self.log.case)

    def begin_capture(self, request, target):
        number = len(self.captures) + 1
        report = self.staging / f'sample-{number:02}.txt'
        console = self.staging / f'sample-{number:02}-console.txt'
        before = self.processes.identity(target['identity']['pid'])
        if not same_process(before, target['identity']):
            self.event('capture_rejected_process_lifetime_changed', request=request)
            return
        executable = record(Path(before['executablePath']))
        if not same_executable(executable, target['installedExecutable']):
            self.event('capture_rejected_executable_changed', request=request)
            return
        after_hash = self.processes.identity(before['pid'])
        if not same_process(after_hash, before):
            self.event('capture_rejected_process_lifetime_changed_after_hash', request=request)
            return
        command = [str(SAMPLE), str(before['pid']), str(SAMPLE_SECONDS), str(SAMPLE_INTERVAL_MS),
                   '-mayDie', '-fullPaths', '-file', str(report)]
        capture = {'number': number, 'request': request, 'target': target,
                   'identityBefore': before, 'executableBefore': executable,
                   'identityAfterPrelaunchHash': after_hash,
                   'command': command, 'toolLaunchedAt': stamp(),
                   'queuedSeconds': time.monotonic() - request['requestedMonotonic']}
        self.captures.append(capture)
        output = console.open('xb')
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output,
                stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=bounded_child_files)
        except Exception as error:
            output.close()
            console.unlink(missing_ok=True)
            capture.update(returnCode=None, captureStatus='unqualified', nativeQualification=False,
                           creationErrorType=type(error).__name__, toolFinishedAt=stamp(),
                           rawOutputDisposition='discarded_tool_launch_failed')
            write_new(self.output / f'sample-{number:02}.json', capture)
            raise
        self.active = {'process': process, 'output': output, 'report': report,
                       'console': console, 'capture': capture, 'started': time.monotonic(),
                       'bindingFailure': None}
        self.finish_capture()  # Includes an immediate post-launch identity check.
        self.event('sample_tool_launched', number=number, pid=before['pid'], request=request)

    def discard_raw(self, active):
        failures = []
        for name in ('report', 'console'):
            try:
                active[name].unlink(missing_ok=True)
            except OSError as error:
                failures.append({'fileKind': name, 'errorType': type(error).__name__})
        return failures

    def check_active_identity(self, active):
        capture = active['capture']
        capture['identityMonitorChecks'] = capture.get('identityMonitorChecks', 0) + 1
        capture['lastIdentityMonitorAt'] = stamp()
        try:
            identity = self.processes.identity(capture['identityBefore']['pid'])
            if not same_process(identity, capture['identityBefore']):
                active['bindingFailure'] = 'process_identity_changed_during_capture'
        except Exception as error:
            active['bindingFailure'] = 'identity_probe_failed_during_capture'
            capture['identityProbeErrorType'] = type(error).__name__
        return active['bindingFailure']

    def finish_capture(self, reason=None):
        active = self.active
        if active is None:
            return
        process = active['process']
        if process.poll() is None:
            identity_failure = self.check_active_identity(active)
            reason = reason or identity_failure
            if reason is None and time.monotonic() - active['started'] < SAMPLE_WALL_SECONDS:
                return
            reason = reason or 'sample_wall_limit'
        if reason:
            stop_owned_tool(process)
        process.wait()
        active['output'].close()
        capture = active['capture']
        after = None
        after_hash = None
        same_lifetime = False
        executable_after = None
        executable_stable = False
        header_pid = None
        try:
            probed = self.processes.identity(capture['identityBefore']['pid'])
            same_lifetime = same_process(probed, capture['identityBefore'])
            if same_lifetime:
                after = probed  # Never record a replacement process's identity.
                executable_after = record(Path(after['executablePath']))
                probed_after_hash = self.processes.identity(after['pid'])
                same_lifetime = same_process(probed_after_hash, after)
                if same_lifetime:
                    after_hash = probed_after_hash
                executable_stable = same_executable(executable_after, capture['executableBefore'])
            header_pid = report_pid(active['report'])
        except Exception as error:
            capture['finalVerificationErrorType'] = type(error).__name__
            same_lifetime = False
        verified = bool(same_lifetime and executable_stable and not active['bindingFailure']
                        and header_pid == capture['identityBefore']['pid'])
        preserved = {'report': None, 'console': None}
        if verified:
            for name in preserved:
                source = active[name]
                destination = self.output / source.name
                source.rename(destination)
                preserved[name] = record(destination)
        discarded = self.discard_raw(active)
        capture.update(toolFinishedAt=stamp(), returnCode=process.returncode,
            collectorTerminationReason=reason, identityAfter=after,
            identityAfterFinalHash=after_hash, identityMonitorFailure=active['bindingFailure'],
            sameProcessLifetimeBeforeAndAfter=same_lifetime,
            executableAfter=executable_after, executableIdentityStable=executable_stable,
            report=preserved['report'], console=preserved['console'], reportHeaderPidMatches=header_pid == capture['identityBefore']['pid'],
            rawOutputDisposition='promoted_after_identity_verification' if verified else 'discarded_unverified_binding_or_report',
            rawDiscardFailures=discarded,
            captureStatus='captured_requires_stack_review' if process.returncode == 0 and not reason and verified else 'unqualified',
            nativeQualification=False,
            scope='Observer launch/finish timestamps are not the exact sampling span. Review the original report and test markers; aggregate sampled stacks are not exclusive CPU duration.')
        write_new(self.output / f"sample-{capture['number']:02}.json", capture)
        self.active = None
        self.event('sample_tool_finished', number=capture['number'], status=capture['captureStatus'])

    def tick(self):
        if self.disabled or not self.sample_available:
            return
        self.finish_capture()
        events = self.log.read()
        if self.log.identity and self.watch_started is None:
            self.watch_started = time.monotonic()
        if self.watch_started is not None and time.monotonic() - self.watch_started >= WATCH_SECONDS:
            self.disable('observer_watch_limit; retained runner continues unchanged')
            return
        for event in events:
            self.event('original_test_log_marker', marker=event)
            if event['kind'] == 'three_d_action':
                self.request(event['action'], event['case'], event)
        if time.monotonic() >= self.next_discovery:
            self.next_discovery = time.monotonic() + 0.5
            self.discover()
        if self.active or not self.pending:
            return
        if len(self.captures) >= MAX_CAPTURES:
            self.once('sample_invocation_limit_reached')
            self.pending.clear()
            return
        request = self.pending[0]
        # A marker may be read before PID binding. Wait briefly, never attach to
        # a process associated with a different case, and preserve missed bounds.
        targets = [target for target in self.targets.values() if target['case'] == request['case']]
        if request['case'] != self.log.case or time.monotonic() - request['requestedMonotonic'] > SAMPLE_WALL_SECONDS:
            self.pending.pop(0)
            self.event('sample_request_missed_window', request=request)
        elif len(targets) == 1:
            self.pending.pop(0)
            self.begin_capture(request, targets[0])

    def close(self, runner_code):
        self.finish_capture('retained_runner_finished')
        for request in self.pending:
            self.event('sample_request_not_started', request=request)
        self.pending.clear()
        shutil.rmtree(self.staging)
        originals = {}
        for name in ['inputs.json', 'result.json', 'simulator.json', 'test.log']:
            path = self.evidence / name
            if path.is_file():
                originals[name] = record(path)
        files = [record(path) for path in sorted(self.output.iterdir()) if path.is_file()]
        write_new(self.output / 'summary.json', {
            'schemaVersion': 1, 'started': self.start, 'finished': stamp(),
            'wrappedRunnerExitCode': runner_code, 'disabled': self.disabled,
            'sampleAvailable': self.sample_available, 'eventCount': self.events,
            'eventsDroppedAtBound': self.events_dropped, 'sampledAppLifetimes': len(self.targets),
            'sampleInvocations': len(self.captures), 'targets': list(self.targets.values()),
            'captures': self.captures, 'auxiliaryCommands': self.tools,
            'originalRetainedEvidence': originals, 'files': files,
            'nativeQualification': False,
            'scope': 'Separate optional diagnostic artifact. The wrapped runner owns every test result and gate. Missing, partial, rejected or failed samples cannot qualify native behavior or prove absence of a stall.',
        })


def safe_disable(observer, reason):
    """A diagnostic filesystem/tool error must not escape into the test gate."""
    if observer is None:
        return
    observer.disabled = True
    try:
        observer.disable(reason)
    except Exception as error:
        print(f'[retained sample] Diagnostic cleanup error: {type(error).__name__}: {error}', file=sys.stderr)
        if observer.active:
            observer.active['capture'].update(captureStatus='unqualified', nativeQualification=False,
                                              collectorError=str(reason)[:2048])
            try:
                stop_owned_tool(observer.active['process'])
                observer.active['output'].close()
                observer.discard_raw(observer.active)
                observer.active = None
            except Exception as cleanup_error:
                print(f'[retained sample] Diagnostic tool stop error: {cleanup_error}', file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('The original retained runner command is required after --.')
    observer = None
    received_signal = None
    forwarded_signal = False

    def requested_stop(number, _frame):
        nonlocal received_signal
        received_signal = number

    previous_handlers = {number: signal.signal(number, requested_stop)
                         for number in [signal.SIGINT, signal.SIGTERM]}
    try:
        command_started = time.time_ns()
        runner = subprocess.Popen(command, start_new_session=True)
        try:
            observer = Observer(args.host_root, args.output, command_started)
            observer.initialize()
        except Exception as error:
            print(f'[retained sample] Diagnostic unavailable: {type(error).__name__}: {error}', file=sys.stderr)
            safe_disable(observer, f'{type(error).__name__}: {error}')
        while runner.poll() is None:
            if received_signal and not forwarded_signal:
                forwarded_signal = True
                safe_disable(observer, 'wrapper cancellation')
                try:
                    os.killpg(runner.pid, received_signal)
                except ProcessLookupError:
                    pass  # runner.wait() still owns the original exit result.
            if observer and not observer.disabled:
                try:
                    observer.tick()
                except Exception as error:
                    print(f'[retained sample] Diagnostic stopped: {type(error).__name__}: {error}', file=sys.stderr)
                    safe_disable(observer, f'{type(error).__name__}: {error}')
            time.sleep(POLL_SECONDS)
        code = runner.wait()
        if observer:
            try:
                observer.close(code)
            except Exception as error:
                print(f'[retained sample] Diagnostic finalization failed: {type(error).__name__}: {error}', file=sys.stderr)
        return code if code >= 0 else 128 - code
    finally:
        if observer and observer.active:
            try:
                stop_owned_tool(observer.active['process'])
                observer.active['output'].close()
                observer.discard_raw(observer.active)
            except Exception as error:
                print(f'[retained sample] Diagnostic tool final stop error: {error}', file=sys.stderr)
        if observer:
            try:
                shutil.rmtree(observer.staging)
            except FileNotFoundError:
                pass
            except Exception as error:
                print(f'[retained sample] Diagnostic staging cleanup error: {type(error).__name__}', file=sys.stderr)
        for number, handler in previous_handlers.items():
            signal.signal(number, handler)


if __name__ == '__main__':
    raise SystemExit(main())
