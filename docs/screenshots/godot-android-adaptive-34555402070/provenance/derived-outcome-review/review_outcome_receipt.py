"""Independently audit small derived receipts; original payload reads are forbidden."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import stat

ROOT = Path(__file__).parent
BASE = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34555402070')
CONTROL = BASE.parent / 'shm-evidence-arena-20260910'
RUN = 34555402070
HEAD = 'aa10e0bd9055aa9fd1b5d80021754f06a8eff3c7'
HELPER_SHA = 'ae6a1c6a51b3bd84cb65ce3ff111a3d02239cd9ceeac5056e2cb0b3f0f01a5be'
SOURCE_SHA = '0918d3d8b2844a2b585bb2e8acbfd978eea13b4c4aac26bbad33992ac02f56bf'
CONTRACT_SHA = '1e70ea0c35928234e824339d0bb3508d7d7e72fee96fcf012202769dc676b7d1'
SOURCE_APPROVAL_SHA = 'd6adc477bf0ff4bd8c46dcec48ebb131541e824c103bc6663a940e61799f6dfd'
MAX_METADATA = 8 * 1024**2
OUTCOMES = ('passed', 'failed', 'unsupported', 'not-reached', 'unrecognized-status', 'malformed-entry')
NAMES = tuple(f'{mode}-{direction}.{suffix}' for mode in ('2d', '3d')
              for direction in ('landscape', 'seascape') for suffix in (
                  'initial-landscape', 'held-rotation', 'portrait-reentry-standard', 'native-leave-home')) + tuple(
              f'{mode}-split.{suffix}' for mode in ('2d', '3d') for suffix in (
                  'support', 'entry-after-ready', 'stable-split-launch-exit', 'fullscreen-reentry-leave-home'))
MEMBERS = {'godot-adaptive/runtime/godot-adaptive-result.json', 'godot-adaptive/execution.json'}
read_pins = {}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate metadata JSON key')
        result[key] = value
    return result


def fingerprint(value):
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def read_metadata(path, expected=None, json_value=True):
    path = Path(path)
    resolved = path.resolve(strict=True)
    require(not any(resolved.is_relative_to(BASE / name) for name in ('artifact-zips', 'extracted', 'logs')),
            'Reviewer forbids every original bulk-payload read')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_METADATA, 'Metadata read exceeds its type/size bound')
    with path.open('rb') as stream:
        raw = stream.read(MAX_METADATA + 1)
    require(len(raw) <= MAX_METADATA and fingerprint(before) == fingerprint(path.lstat()), 'Metadata changed during bounded read')
    actual = {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    if isinstance(expected, str):
        require(actual['sha256'] == expected, 'Unexpected metadata SHA: ' + str(path))
    elif expected is not None:
        require(actual == expected, 'Unexpected metadata pin: ' + str(path))
    read_pins[str(path)] = actual
    return actual, json.loads(raw, object_pairs_hook=unique_object) if json_value else raw


def check_rows(rows, names):
    require(len(rows) == len(names) and {row['name'] for row in rows} == set(names), 'Expected scope identity differs')
    for row in rows:
        require(type(row['originalEntryPresent']) is bool and row['outcome'] in OUTCOMES, 'Malformed derived scope entry')
        require(row['originalJsonPointer'] == '/checks/' + row['name'].replace('~', '~0').replace('/', '~1'), 'Scope pointer differs')
        if not row['originalEntryPresent']:
            require(row['outcome'] == 'not-reached' and row['reportedStatus'] is None, 'Unreached scope was reclassified')
        elif isinstance(row['reportedStatus'], str) and row['reportedStatus'] in ('passed', 'failed', 'unsupported'):
            require(row['outcome'] == row['reportedStatus'], 'Reported result status was reclassified')
        else:
            require(row['outcome'] in ('malformed-entry', 'unrecognized-status'), 'Unknown/malformed status was reclassified')
            if row['outcome'] == 'malformed-entry':
                require(row['reportedStatus'] is None, 'Malformed entry unexpectedly reports a status')
    return {name: sum(row['outcome'] == name for row in rows) for name in OUTCOMES}


def read_gate_events(lease_id):
    path = CONTROL / 'allocation-events.jsonl'
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_size <= 4 * 1024**2, 'Gate event prefix exceeds its review bound')
    # Capture a bounded existing prefix; later appends do not invalidate prior lines.
    with path.open('rb') as stream:
        raw_prefix = stream.read(info.st_size)
    require(len(raw_prefix) == info.st_size, 'Gate event source shrank during read')
    selected, offset = [], 0
    for number, raw in enumerate(raw_prefix.splitlines(keepends=True), 1):
        require(len(raw) <= 128 * 1024, 'Gate event line exceeds its bound')
        if lease_id.encode() in raw:
            require(raw.endswith(b'\n'), 'Selected gate event line is incomplete')
            value = json.loads(raw, object_pairs_hook=unique_object)
            if value.get('lease_id') == lease_id:
                selected.append({'path': str(path), 'lineNumber': number, 'byteOffset': offset,
                                 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'event': value})
        offset += len(raw)
    require([row['event']['status'] for row in selected] == ['admitted', 'command_started', 'released'],
            'Outcome execution lacks one completed admitted/command/released chain')
    return selected, {'path': str(path), 'prefixBytesIndependentlyRead': len(raw_prefix),
                      'prefixSha256': hashlib.sha256(raw_prefix).hexdigest(), 'appendOnlyPrefixSnapshot': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifact-id', type=int, required=True)
    parser.add_argument('--receipt-sha256', required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (64 * 1024**2, 64 * 1024**2))
    report_pin, report = read_metadata(BASE / 'receipts' / f'consumer-{args.artifact_id}.outcomes-v1.json', args.receipt_sha256)
    require(report_pin['bytes'] <= 256 * 1024, 'Derived outcome report exceeds helper bound')
    require((report['runId'], report['headSha'], report['attempt'], report['artifactId']) == (RUN, HEAD, 1, args.artifact_id),
            'Exact outcome run identity differs')
    require(report['status'] == 'original_consumer_outcomes_accounted_independent_review_pending', 'Unexpected helper report status')
    contract_pin, contract = read_metadata(BASE / 'collection-contract.json', CONTRACT_SHA)
    require(report['contract'] == contract_pin, 'Outcome contract pin differs')
    expected = next(row for row in contract['originalArtifacts'] if row['artifactId'] == args.artifact_id)
    require(report['artifactName'] == expected['name'] == f"android-adaptive-api36-{report['variant']}-font-{report['fontScale']}-{RUN}-1",
            'Exact consumer matrix/name differs')
    require(report['variant'] in ('debug', 'optimized-test-signed') and report['fontScale'] in ('1.0', '2.0'), 'Unexpected consumer matrix cell')
    helper_pin, _ = read_metadata(report['script']['path'], report['script'], json_value=False)
    require(helper_pin['bytes'] == 17111 and helper_pin['sha256'] == HELPER_SHA, 'Actual helper is not approved v2')
    approval_pin, approval = read_metadata(ROOT / 'OUTCOME-HELPER-V2-APPROVAL.json', SOURCE_APPROVAL_SHA)
    require(approval['candidate']['sha256'] == HELPER_SHA and approval['fixtureCount'] == 17, 'Helper source approval differs')
    installation_pin, installation = read_metadata(BASE / 'receipts' / 'outcome-helper-v2-installation.json')
    require(installation['installedScript'] == helper_pin and installation['independentSourceApproval'] == approval_pin,
            'Helper installation does not bind exact source approval')
    source_pin, source = read_metadata(report['sourceCheckerBinding']['path'], report['sourceCheckerBinding'])
    require(source_pin['sha256'] == SOURCE_SHA and source_pin['bytes'] == 97604
            and (source['runId'], source['headSha'], source['attempt']) == (RUN, HEAD, 1), 'Exact checker source proof differs')
    helper_names = {'candidate_sha256': 'scripts/smoke_android_godot_adaptive.py',
        'accepted_session_sha256': 'scripts/smoke-android-godot-session.py',
        'accepted_ui_sha256': 'scripts/smoke-android-ui.py', 'observations_sha256': 'scripts/adaptive_observations.py'}
    require(report['runtimeCheckerHashes'] == {key: source['expectedCheckerSha256'][value] for key, value in helper_names.items()},
            'Original runtime checker binding differs')
    require(report['callerSourceRevision']['value'] == HEAD, 'Caller source head differs')
    commitment_pin, commitment = read_metadata(report['originalCommitment']['path'], report['originalCommitment'])
    require((commitment['runId'], commitment['headSha'], commitment['artifactId'], commitment['artifactName'])
            == (RUN, HEAD, args.artifact_id, expected['name'])
            and commitment['zipRetained'] is True and commitment['everyMemberCrcAndHashVerified'] is True,
            'Original committed proof differs')
    archive_pin, archive = read_metadata(report['archiveReceipt']['path'], report['archiveReceipt'])
    inventory_pin, inventory = read_metadata(report['memberInventory']['path'], report['memberInventory'])
    require(commitment['archiveReceipt'] == archive_pin['path'] and commitment['archiveReceiptSha256'] == archive_pin['sha256']
            and commitment['memberInventory'] == inventory_pin['path'] and commitment['memberInventorySha256'] == inventory_pin['sha256'],
            'Original commitment dependency pins differ')
    require(archive['artifact']['id'] == args.artifact_id and archive['artifact']['name'] == expected['name']
            and archive['artifact']['size_in_bytes'] == expected['apiZipBytes']
            and archive['artifact']['digest'] == 'sha256:' + expected['apiSha256']
            and inventory['archiveSha256'] == expected['apiSha256'], 'Original API/archive identity differs')
    require(inventory['allMemberCrc32Verified'] is True and inventory['allFileSha256Computed'] is True, 'Reused member proof is incomplete')
    indexed = {row['path']: row for row in inventory['files']}
    require(len(indexed) == len(inventory['files']) == inventory['fileCount'], 'Original member inventory has duplicate/missing names')
    reads = report['boundedOriginalMemberReads']
    require(len(reads) == 2 and {row['member']['path'] for row in reads} == MEMBERS, 'Original result/execution member proof set differs')
    for row in reads:
        require(row['artifactId'] == args.artifact_id and row['archivePath'] == archive['physicalArchivePath']
                and row['archiveSha256'] == expected['apiSha256'] and row['member'] == indexed[row['member']['path']]
                and row['readToEofShaAndCrcVerified'] is True and row['standaloneCopyCreated'] is False,
                'Outcome helper member proof differs from reused committed inventory')
    adaptive = check_rows(report['adaptiveScopeOutcomes'], NAMES)
    install = check_rows(report['installationOutcomes'], ('installation',))
    require(adaptive == report['adaptiveOutcomeCounts'] and install == report['installationOutcomeCounts'], 'Derived outcome tally differs')
    require(report['expectedAdaptiveScopeCount'] == 24 and report['expectedInstallationCheckCount'] == 1
            and report['reportedAdaptiveScopeCount'] == sum(row['originalEntryPresent'] for row in report['adaptiveScopeOutcomes']),
            'Expected/reached accounting differs')
    unexpected = report['unexpectedOriginalCheckEntries']
    extra_names = [row['name'] for row in unexpected]
    require(len(extra_names) == len(set(extra_names)) and not set(extra_names) & (set(NAMES) | {'installation'}), 'Unexpected checks overlap expected scopes')
    check_rows(unexpected, extra_names)
    if install['passed']:
        observed = report['actualFontScaleObservation']
        require(observed['present'] is True and observed['matchesExpected'] is True and str(observed['reported']) == report['fontScale'],
                'Passed installation lacks matching platform observation')
    require(report['resourceBounds'] == {'processAddressSpaceLimitBytes': 64 * 1024**2,
        'maximumJsonMemberBytes': 8 * 1024**2, 'maximumMetadataReadBytes': 8 * 1024**2, 'maximumReportBytes': 256 * 1024},
        'Helper resource bounds differ')
    for observation in report['resourceObservations']:
        require(observation['metadataAndPrivateAllocatedBytes'] + 256 * 1024 + 8192 <= contract['metadataAndLogCumulativeAllocationCeilingBytes']
            and observation['selectedOriginalAllocatedBytes'] <= contract['initialSelectedOriginalCumulativeAllocationCeilingBytes']
            and observation['actualDestinationAvailableBytes'] >= contract['minimumDestinationAvailableBytes']
            and observation['systemMemAvailableBytes'] >= contract['minimumSystemMemAvailableBytes']
            and observation['processAnonymousBytes'] <= 64 * 1024**2, 'Recorded helper resource observation violates its bounds')
    require(6 <= len(report['resourceObservations']) <= 32, 'Unexpected resource observation count')
    gate_pin, _ = read_metadata(contract['gatePath'], contract['gateSha256'], json_value=False)
    gate_events, gate_prefix = read_gate_events(report['leaseId'])
    admitted, started, released = (row['event'] for row in gate_events)
    for event in (admitted, started, released):
        require(event['owner'] == 'android_platform' and event['owner_physical_root'] == str(BASE)
            and event['pid'] == admitted['pid'] and event['planned_peak_additional_bytes'] >= 256 * 1024 + 8192
            and event['extra_memory_reserve_bytes'] >= 64 * 1024**2, 'Gate execution owner or allowance differs')
    require(released['error'] is None and 0 <= released['observed']['window_allocated_bytes'] - released['initial']['window_allocated_bytes']
            <= released['planned_peak_additional_bytes'], 'Outcome execution did not release successfully within its allowance')
    require(datetime.fromisoformat(started['recorded_at_utc']) <= datetime.fromisoformat(report['createdUtc'])
            <= datetime.fromisoformat(released['recorded_at_utc']), 'Outcome receipt was not created during the released window')
    require(report['originalZipFingerprintUnchanged'] is True and report['standaloneJsonCopiesCreated'] is False
            and report['mediaReadsDecodesOrViews'] == 0 and report['nativeRunsOrPackageExecution'] is False,
            'Helper scope differs from the approved bounded reader')
    review = {'schemaVersion': 1, 'status': 'independent_derived_outcome_receipt_and_provenance_verified',
        'reviewer': '/root/delivery_review', 'reviewedAtUtc': datetime.now(timezone.utc).isoformat(),
        'runId': RUN, 'headSha': HEAD, 'attempt': 1, 'artifactId': args.artifact_id,
        'artifactName': report['artifactName'], 'variant': report['variant'], 'fontScale': report['fontScale'],
        'outcomeReceipt': report_pin, 'helperSourceApproval': approval_pin, 'helperInstallation': installation_pin,
        'sourceCheckerBinding': source_pin, 'originalCommitment': commitment_pin, 'memberInventory': inventory_pin,
        'adaptiveOutcomeCounts': adaptive, 'installationOutcomeCounts': install,
        'expectedAdaptiveScopes': 24, 'expectedInstallationChecks': 1,
        'originalRuntimeStatus': report['originalRuntimeStatus'], 'originalRunnerExitCode': report['originalRunnerExitCode'],
        'originalFailedStage': report['originalFailedStage'], 'originalStoppedStage': report['originalStoppedStage'],
        'unexpectedCheckCount': len(unexpected), 'actualFontScaleObservation': report['actualFontScaleObservation'],
        'approvedHelperGateSource': gate_pin, 'successfulGateWindow': gate_events, 'gateEventPrefixObservation': gate_prefix,
        'independentlyReadMetadataPins': list(read_pins.values()), 'reusedOriginalMemberProofs': reads,
        'reviewSource': {'path': str(Path(__file__).resolve()), 'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        'independentChecks': ['Exact run/head/attempt/matrix, helper and source pins',
            'Committed archive API and per-member inventory linkage', '24 explicit adaptive entries plus one installation and exact class tallies',
            'Overall runtime/runner outcome retained separately from counts', 'Released V12 window and recorded helper resource limits'],
        'limits': {'actualOriginalZipBytesIndependentlyRead': 0, 'originalMembersIndependentlyReplayed': False,
            'originalCrcAndShaProofsReused': True, 'approvedHelperFixtureResultsReusedWithoutRerun': True,
            'originalProofReuseBasis': 'Exact approved helper execution and immutable original commitment/member inventories; this reviewer reads metadata only.',
            'nativePixelOrGeometryAcceptance': 'separate', 'packageAndInstalledCopyAcceptance': 'separate',
            'deviceStoreAndPhysicalNetworkAcceptance': 'separate', 'sharedWrites': 0, 'gitMutations': 0}}
    destination = ROOT / f'CONSUMER-{args.artifact_id}-DERIVED-OUTCOME-REVIEW.json'
    raw = (json.dumps(review, indent=2, sort_keys=True) + '\n').encode()
    require(len(raw) < 64 * 1024, 'Private review exceeds its allocation bound')
    with destination.open('xb') as stream:
        stream.write(raw)
    destination.chmod(0o400)
    print(json.dumps({'path': str(destination), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                     'adaptiveOutcomes': adaptive, 'installationOutcomes': install,
                     'originalRuntimeStatus': review['originalRuntimeStatus'], 'originalRunnerExitCode': review['originalRunnerExitCode']}, indent=2))


if __name__ == '__main__':
    main()
