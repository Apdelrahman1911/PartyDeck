"""Count one consumer's actual 24 adaptive scopes and installation outcome.

Reads bounded JSON members directly from the committed original ZIP. It does
not extract APKs, media or result JSON and does not interpret native pixels.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import stat
import zipfile
import zlib

BASE = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34555402070')
RUN = 34555402070
HEAD = 'aa10e0bd9055aa9fd1b5d80021754f06a8eff3c7'
CONTRACT_SHA = '1e70ea0c35928234e824339d0bb3508d7d7e72fee96fcf012202769dc676b7d1'
SOURCE = Path('/tmp/partydeck-adaptive-package-preparation-34555402070-v1-yoj4n4pi/shared-source-preflight.json')
SOURCE_SHA = '0918d3d8b2844a2b585bb2e8acbfd978eea13b4c4aac26bbad33992ac02f56bf'
MAX_JSON_BYTES = 8 * 1024**2
MAX_REPORT_BYTES = 256 * 1024
MAX_METADATA_READ_BYTES = 8 * 1024**2
PROCESS_ADDRESS_SPACE_BOUND = 64 * 1024**2
OUTCOME_CLASSES = ('passed', 'failed', 'unsupported', 'not-reached', 'unrecognized-status', 'malformed-entry')
os.umask(0o077)

def require(value, message):
    if not value:
        raise RuntimeError(message)

def pin(path, expected=None):
    path = Path(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode), 'Expected ordinary pinned file: ' + str(path))
    require(before.st_size <= MAX_METADATA_READ_BYTES, 'Pinned metadata exceeds its bounded read')
    with path.open('rb') as stream:
        raw = stream.read(MAX_METADATA_READ_BYTES + 1)
    require(len(raw) <= MAX_METADATA_READ_BYTES, 'Pinned metadata grew beyond its bounded read')
    digest = hashlib.sha256(raw).hexdigest()
    require(expected is None or digest == expected, 'Pinned evidence differs: ' + str(path))
    after = path.lstat()
    require(fingerprint(before) == fingerprint(after), 'Pinned metadata changed during read')
    return {'path': str(path), 'bytes': len(raw), 'sha256': digest}

def fingerprint(value):
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON object key')
        result[key] = value
    return result

def load(path):
    path = Path(path)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_METADATA_READ_BYTES,
            'JSON metadata path/type/size exceeds its read bound')
    with path.open('rb') as stream:
        raw = stream.read(MAX_METADATA_READ_BYTES + 1)
    require(len(raw) <= MAX_METADATA_READ_BYTES, 'JSON metadata grew beyond its read bound')
    return json.loads(raw, object_pairs_hook=unique_object)

def expected_adaptive_scopes():
    result = []
    for mode in ('2d', '3d'):
        for direction in ('landscape', 'seascape'):
            result.extend(f'{mode}-{direction}.{suffix}' for suffix in (
                'initial-landscape', 'held-rotation', 'portrait-reentry-standard', 'native-leave-home'))
        result.extend(f'{mode}-split.{suffix}' for suffix in (
            'support', 'entry-after-ready', 'stable-split-launch-exit', 'fullscreen-reentry-leave-home'))
    require(len(result) == len(set(result)) == 24, 'Expected adaptive scope set differs')
    return result

def classify(checks, name):
    present = name in checks
    value = checks.get(name)
    reported = value.get('status') if isinstance(value, dict) else None
    outcome = ('not-reached' if not present else 'malformed-entry' if not isinstance(value, dict)
               else reported if isinstance(reported, str) and reported in ('passed', 'failed', 'unsupported')
               else 'unrecognized-status')
    return {'name': name, 'originalEntryPresent': present, 'reportedStatus': reported,
            'outcome': outcome, 'originalJsonPointer': '/checks/' + name.replace('~', '~0').replace('/', '~1')}

def counts(rows):
    tally = Counter(row['outcome'] for row in rows)
    return {name: tally[name] for name in OUTCOME_CLASSES}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-id', required=True, type=int)
    args = parser.parse_args()
    prior_soft, prior_hard = resource.getrlimit(resource.RLIMIT_AS)
    address_limit = min([PROCESS_ADDRESS_SPACE_BOUND] +
                        [value for value in (prior_soft, prior_hard) if value != resource.RLIM_INFINITY])
    resource.setrlimit(resource.RLIMIT_AS, (address_limit, address_limit))
    contract_pin = pin(BASE / 'collection-contract.json', CONTRACT_SHA)
    contract = load(contract_pin['path'])
    require(BASE.resolve(strict=True) == BASE == Path(contract['physicalRoot']), 'Registered physical root differs')
    pin(contract['gatePath'], contract['gateSha256'])
    for key in ('gateFreeze', 'gatePolicy'):
        row = contract[key]
        require(pin(row['path'], row['sha256']) == row, 'Installed gate configuration differs')
    lease = load(Path(contract['gatePath']).parent / 'active-lease.json')
    require(lease['owner'] == contract['owner'] == 'android_platform' and lease['pid'] == os.getppid()
            and lease['owner_physical_root'] == str(BASE) and lease['status'] in ('active', 'admitted')
            and lease['planned_peak_additional_bytes'] >= MAX_REPORT_BYTES + 8192
            and lease['extra_memory_reserve_bytes'] >= 64 * 1024**2,
            'Use the registered direct-parent gate and bounded outcome window')
    observations = []
    def boundary_check(next_output_bytes=0):
        live = load(Path(contract['gatePath']).parent / 'active-lease.json')
        require(live['lease_id'] == lease['lease_id'] and live['owner'] == contract['owner']
                and live['pid'] == os.getppid() and live['owner_physical_root'] == str(BASE)
                and live['status'] in ('active', 'admitted')
                and live['planned_peak_additional_bytes'] == lease['planned_peak_additional_bytes']
                and live['extra_memory_reserve_bytes'] == lease['extra_memory_reserve_bytes'],
                'Original matching V12 lease must remain live through every read/write boundary')
        metadata = BASE.lstat().st_blocks * 512
        selected = 0
        for path in BASE.rglob('*'):
            info = path.lstat()
            require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), 'Unexpected retained entry type')
            first = path.relative_to(BASE).parts[0]
            if first == 'extracted':
                selected += info.st_blocks * 512
            elif first != 'artifact-zips':
                metadata += info.st_blocks * 512
        private = Path(contract['privatePreparationRoot'])
        private_allocation = private.lstat().st_blocks * 512
        for path in private.rglob('*'):
            info = path.lstat()
            require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), 'Unexpected private preparation entry type')
            private_allocation += info.st_blocks * 512
        metadata += private_allocation
        require(metadata + MAX_REPORT_BYTES + 8192 <= contract['metadataAndLogCumulativeAllocationCeilingBytes'],
                'Cumulative canonical/private metadata lacks the bounded outcome report reserve')
        require(selected <= contract['initialSelectedOriginalCumulativeAllocationCeilingBytes'],
                'Initial selected-original allocation exceeds its category cap')
        fs = os.statvfs(BASE)
        available = fs.f_bavail * fs.f_frsize
        memory = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                      if line.startswith('MemAvailable:'))
        anonymous = next(int(line.split()[1]) * 1024 for line in Path('/proc/self/status').read_text().splitlines()
                         if line.startswith('RssAnon:'))
        require(available - next_output_bytes >= contract['minimumDestinationAvailableBytes']
                and memory - next_output_bytes >= contract['minimumSystemMemAvailableBytes']
                and anonymous <= PROCESS_ADDRESS_SPACE_BOUND, 'Outcome resource floor or process bound reached')
        observations.append({'metadataAndPrivateAllocatedBytes': metadata, 'selectedOriginalAllocatedBytes': selected,
                             'actualDestinationAvailableBytes': available, 'systemMemAvailableBytes': memory,
                             'processAnonymousBytes': anonymous})
    boundary_check(MAX_REPORT_BYTES + 8192)
    source_pin = pin(SOURCE, SOURCE_SHA)
    source = load(SOURCE)
    commitment_path = BASE / 'receipts' / f'artifact-{args.artifact_id}.commitment.json'
    commitment_pin = pin(commitment_path)
    commitment = load(commitment_path)
    require(commitment['runId'] == RUN and commitment['headSha'] == HEAD
            and commitment['artifactId'] == args.artifact_id and commitment['zipRetained']
            and commitment['everyMemberCrcAndHashVerified'], 'Complete original commitment is missing')
    archive_receipt_pin = pin(commitment['archiveReceipt'], commitment['archiveReceiptSha256'])
    inventory_pin = pin(commitment['memberInventory'], commitment['memberInventorySha256'])
    archive_receipt, inventory = load(archive_receipt_pin['path']), load(inventory_pin['path'])
    item = archive_receipt['artifact']
    match = re.fullmatch(r'android-adaptive-api36-(debug|optimized-test-signed)-font-(1\.0|2\.0)-34555402070-1', item['name'])
    require(match and item['id'] == args.artifact_id and item['name'] == commitment['artifactName'], 'Consumer matrix identity differs')
    variant, font_scale = match.groups()
    expected_artifact = next(row for row in contract['originalArtifacts'] if row['artifactId'] == args.artifact_id)
    require(expected_artifact['name'] == item['name'] and expected_artifact['apiZipBytes'] == item['size_in_bytes']
            and expected_artifact['apiSha256'] == item['digest'][7:] == inventory['archiveSha256'], 'API original identity differs')
    archive = Path(archive_receipt['physicalArchivePath'])
    require(archive == BASE / 'artifact-zips' / archive.name and stat.S_ISREG(archive.lstat().st_mode)
            and archive.stat().st_size == item['size_in_bytes'], 'Original archive path/type/size differs')
    before = archive.stat()
    indexed = {row['path']: row for row in inventory['files']}
    require(len(indexed) == inventory['fileCount'] and inventory['allMemberCrc32Verified']
            and inventory['allFileSha256Computed'], 'Original member inventory is incomplete')
    member_reads = []
    with zipfile.ZipFile(archive) as package:
        def read_json(name):
            boundary_check()
            expected = indexed[name]
            require(0 < expected['bytes'] <= MAX_JSON_BYTES, 'JSON member exceeds bounded read')
            matches = [entry for entry in package.infolist() if entry.filename == name]
            require(len(matches) == 1, 'Expected exactly one named JSON member')
            info = matches[0]
            require(info.file_size == expected['bytes'] and info.CRC == int(expected['crc32'], 16)
                    and info.header_offset == expected['headerOffset'] and not info.is_dir(), 'ZIP member identity differs')
            with package.open(info) as stream:
                raw = stream.read(MAX_JSON_BYTES + 1)
                require(not stream.read(1), 'Bounded JSON read did not reach EOF')
            require(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256']
                    and zlib.crc32(raw) & 0xffffffff == info.CRC, 'Original JSON byte/hash/CRC differs')
            member_reads.append({'artifactId': args.artifact_id, 'archivePath': str(archive),
                                 'archiveSha256': inventory['archiveSha256'], 'member': expected,
                                 'readToEofShaAndCrcVerified': True, 'standaloneCopyCreated': False})
            parsed = json.loads(raw, object_pairs_hook=unique_object)
            boundary_check()
            return parsed
        result = read_json('godot-adaptive/runtime/godot-adaptive-result.json')
        execution = read_json('godot-adaptive/execution.json')
    require(fingerprint(before) == fingerprint(archive.stat()), 'Original ZIP changed during bounded reads')
    require(result['variant'] == variant and result['font_scale'] == font_scale
            and result['modes'] == ['2d', '3d'] and result['source_revision']['value'] == HEAD,
            'Original outcome run/source/matrix identity differs')
    require(execution['variant'] == variant and str(execution['fontScale']) == font_scale
            and execution['androidApi'] == 36 and execution['modes'] == ['2d', '3d'], 'Original execution matrix differs')
    identity = result['identity']
    helpers = {'candidate_sha256': 'scripts/smoke_android_godot_adaptive.py',
               'accepted_session_sha256': 'scripts/smoke-android-godot-session.py',
               'accepted_ui_sha256': 'scripts/smoke-android-ui.py', 'observations_sha256': 'scripts/adaptive_observations.py'}
    require(all(identity[field] == source['expectedCheckerSha256'][path] for field, path in helpers.items()), 'Exact checker source binding differs')
    require(isinstance(result['checks'], dict), 'Original check map is malformed')
    expected = expected_adaptive_scopes()
    adaptive = [classify(result['checks'], name) for name in expected]
    installation = [classify(result['checks'], 'installation')]
    observed_font_scale = identity.get('actual_font_scale')
    font_matches = str(observed_font_scale) == font_scale if observed_font_scale is not None else None
    require(installation[0]['outcome'] != 'passed' or font_matches is True,
            'Passed installation lacks matching actual platform font scale')
    unexpected = [classify(result['checks'], name) for name in sorted(set(result['checks']) - set(expected) - {'installation'})]
    report = {
        'schemaVersion': 1, 'runId': RUN, 'headSha': HEAD, 'attempt': 1,
        'status': 'original_consumer_outcomes_accounted_independent_review_pending',
        'artifactId': args.artifact_id, 'artifactName': item['name'], 'variant': variant, 'fontScale': font_scale,
        'createdUtc': datetime.now(timezone.utc).isoformat(), 'leaseId': lease['lease_id'],
        'contract': contract_pin, 'sourceCheckerBinding': source_pin, 'script': pin(__file__),
        'originalCommitment': commitment_pin, 'archiveReceipt': archive_receipt_pin, 'memberInventory': inventory_pin,
        'boundedOriginalMemberReads': member_reads,
        'originalRuntimeStatus': result['status'], 'originalRunnerExitCode': execution['runnerExitCode'],
        'originalFailedStage': result.get('failed_stage'), 'originalStoppedStage': result.get('stopped_stage'),
        'callerSourceRevision': result['source_revision'], 'originalLimits': result.get('limits', []),
        'actualFontScaleObservation': {'present': 'actual_font_scale' in identity, 'reported': observed_font_scale,
                                       'matchesExpected': font_matches},
        'resourceBounds': {'processAddressSpaceLimitBytes': address_limit, 'maximumJsonMemberBytes': MAX_JSON_BYTES,
                           'maximumMetadataReadBytes': MAX_METADATA_READ_BYTES, 'maximumReportBytes': MAX_REPORT_BYTES},
        'resourceObservations': observations,
        'runtimeCheckerHashes': {field: identity[field] for field in helpers},
        'inputApkSha256': identity.get('input_apk_sha256'), 'installedApkSha256': identity.get('installed_apk_sha256'),
        'expectedAdaptiveScopeCount': 24, 'reportedAdaptiveScopeCount': sum(row['originalEntryPresent'] for row in adaptive),
        'adaptiveScopeOutcomes': adaptive, 'adaptiveOutcomeCounts': counts(adaptive),
        'expectedInstallationCheckCount': 1, 'installationOutcomes': installation,
        'installationOutcomeCounts': counts(installation), 'unexpectedOriginalCheckEntries': unexpected,
        'nativePixelReview': 'separate_required', 'packageAndInstalledCopyAudit': 'separate_required',
        'originalZipFingerprintUnchanged': True, 'standaloneJsonCopiesCreated': False,
        'mediaReadsDecodesOrViews': 0, 'nativeRunsOrPackageExecution': False,
    }
    boundary_check(MAX_REPORT_BYTES + 8192)
    raw = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    require(len(raw) <= MAX_REPORT_BYTES, 'Outcome report exceeds its bounded allocation')
    output = BASE / 'receipts' / f'consumer-{args.artifact_id}.outcomes-v1.json'
    boundary_check(len(raw) + 8192)
    with output.open('xb') as stream:
        stream.write(raw)
    output.chmod(0o400)
    boundary_check()
    print(json.dumps({'receipt': pin(output), 'artifactId': args.artifact_id,
                      'adaptiveOutcomes': report['adaptiveOutcomeCounts'], 'installationOutcomes': report['installationOutcomeCounts'],
                      'originalRuntimeStatus': report['originalRuntimeStatus'], 'runnerExitCode': report['originalRunnerExitCode']}, indent=2), flush=True)

if __name__ == '__main__':
    main()
