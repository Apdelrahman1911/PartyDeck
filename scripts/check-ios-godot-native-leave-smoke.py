#!/usr/bin/env python3
"""Separate native Leave scope. Legacy picker evidence retains its existing checker and labels."""

import argparse
import json
from pathlib import Path
import re
import runpy

COMMON = runpy.run_path(str(Path(__file__).resolve().with_name('check-ios-godot-shipping-smoke.py')))
require, identity, read_json = (COMMON[name] for name in ('require', 'identity', 'read_json'))
check_settings = COMMON['check_settings']
SCOPE = 'native-leave'
CLASS = 'PartyDeckGodotNativeLeaveShippingUITests'
METHODS = {
    '2d': 'testShipping2DNativeLeaveCancelAndConfirm',
    '3d': 'testShipping3DNativeLeaveCancelAndConfirm',
}
CAPTURES_BY_CASE = {
    ('PartyDeckUITests.' + CLASS, method): [
        f'shipping-{mode}-native-leave-{step}'
        for step in ('ready', 'cancelled', 'confirmation', 'confirmed-home')
    ]
    for mode, method in METHODS.items()
}
TEST_SOURCE = Path('iosApp/PartyDeckUITests/PartyDeckGodotNativeLeaveShippingUITests.swift')
TEST_SHA256 = 'df8652de8e306d6f5f037f1beb5f209dda3550e351adaf62daff598e793719bf'


def expected_case_names():
    return [f'{target}/{method}' for target, method in sorted(CAPTURES_BY_CASE)]


def preflight(repo):
    # Both Swift sources compile into this target. Retain the existing source/profile gates
    # and add the separate Leave source and checker to the immutable input inventory.
    result = COMMON['preflight'](repo)
    test = identity(repo / TEST_SOURCE)
    require(test['sha256'] == TEST_SHA256, 'Run the exact independently reviewed native Leave test source.')
    result['source_files'].append(test)
    result['runner_files'].append(identity(Path(__file__)))
    result['test_scope'] = SCOPE
    result['expected_cases'] = expected_case_names()
    result['scope'] = 'shipping native Leave source activation and exact test inputs only'
    return result


def check_named_result(log, summary):
    prefix = r"^Test Case '-\[([^\]\s]+) (test\w+)\]' "
    started = re.findall(prefix + r'started\.$', log, re.MULTILINE)
    finished = re.findall(prefix + r'(passed|failed|skipped) \((\d+(?:\.\d+)?) seconds\)\.$', log, re.MULTILINE)
    cases = set(CAPTURES_BY_CASE)
    require(len(started) == len(cases) and set(started) == cases and len(finished) == len(cases)
            and {(target, method) for target, method, _, _ in finished} == cases
            and all(status == 'passed' for _, _, status, _ in finished)
            and '** TEST SUCCEEDED **' in log and '** TEST FAILED **' not in log,
            'Require both exact native Leave cases to start once and pass once; zero, extra, repeated, failed or skipped cases fail.')
    expected = {'totalTestCount': 2, 'passedTests': 2, 'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}
    require(isinstance(summary, dict) and summary.get('result') == 'Passed' and summary.get('testFailures') == []
            and all(type(summary.get(key)) is int and summary[key] == value for key, value in expected.items()),
            'The native Leave XCResult summary must independently report exactly two passes and zero failures/skips.')


def check_captures(manifest, directory):
    require(isinstance(manifest, list) and len(manifest) == 2, 'Require exactly two native Leave attachment records.')
    result, files = [], set()
    for (target, method), captions in CAPTURES_BY_CASE.items():
        identifier = f'{CLASS}/{method}()'
        matches = [entry for entry in manifest if isinstance(entry, dict) and entry.get('testIdentifier') == identifier]
        require(len(matches) == 1, 'Every native Leave case must own exactly one attachment record.')
        entry = matches[0]
        require(entry.get('testIdentifierURL') ==
                f'test://com.apple.xcode/PartyDeck/PartyDeckUITests/{CLASS}/{method}',
                'Native Leave attachments must bind the exact selected testcase URL.')
        attachments = entry.get('attachments')
        require(isinstance(attachments, list), 'Missing original native Leave attachment list.')
        for caption in captions:
            matches = [item for item in attachments if isinstance(item, dict)
                       and isinstance(item.get('suggestedHumanReadableName'), str)
                       and item['suggestedHumanReadableName'].startswith(caption + '_')
                       and item['suggestedHumanReadableName'].endswith('.png')]
            require(len(matches) == 1, 'Every native Leave checkpoint must appear exactly once under its owning case.')
            item = matches[0]
            filename = item.get('exportedFileName')
            require(isinstance(filename, str) and filename == Path(filename).name and filename not in files
                    and filename.endswith('.png') and item.get('isAssociatedWithFailure') is False,
                    'Native Leave needs distinct original PNGs, not failed, aliased or traversing names.')
            path = directory / filename
            require(path.is_file() and not path.is_symlink(), 'The original native Leave attachment must be retained.')
            with path.open('rb') as stream:
                header = stream.read(24)
            require(len(header) == 24 and header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR'
                    and int.from_bytes(header[16:20], 'big') > 0 and int.from_bytes(header[20:24], 'big') > 0,
                    'Native Leave captures need nonempty PNG dimensions; independent full pixel review is separate.')
            files.add(filename)
            result.append({'case': f'{target}/{method}', 'capture': caption, 'file': identity(path)})
    return result


def check_result(directory):
    stages = read_json(directory / 'stage-exits.json')
    require(set(stages) == set(COMMON['STAGES']) and all(type(stages[key]) is int and stages[key] == 0 for key in stages),
            'Every native Leave test, export and package stage must complete successfully.')
    source = read_json(directory / 'source-preflight.json')
    require(source.get('test_scope') == SCOPE and source.get('expected_cases') == expected_case_names(),
            'Native Leave requires its own preflight scope and cases; legacy picker results cannot be relabeled.')
    require(any(item.get('path') == str((Path(source['activation']['source_plist']['path']).parents[2] / TEST_SOURCE).resolve())
                and item.get('sha256') == TEST_SHA256 for item in source['source_files']),
            'Native Leave preflight must retain the exact selected Swift test source.')
    for item in source['source_files'] + source['runner_files']:
        require(identity(Path(item['path'])) == item, 'A recorded native Leave input changed during the build/run.')
    settings = check_settings(read_json(directory / 'build-settings.json'), Path(source['activation']['source_plist']['path']))
    saved_settings = read_json(directory / 'settings-check.json')
    require(json.dumps(settings, sort_keys=True) == json.dumps(saved_settings, sort_keys=True),
            'Retained build settings must reproduce the successful native Leave settings receipt.')
    link = read_json(directory / 'godot-shipping-link.json')
    require(link.get('stage') == 'production_ios_app_link_only' and link.get('packaged_activation') == COMMON['ACTIVATION']
            and link.get('inputs', {}).get('activation') == source['activation'],
            'The linked app must bind both shipping modes to this native Leave preflight.')
    xcresult = directory / 'PartyDeckShipping.xcresult'
    require(xcresult.is_dir() and any(path.is_file() and path.stat().st_size > 0 for path in xcresult.rglob('*')),
            'Preserve the original nonempty native Leave XCResult.')
    check_named_result((directory / 'test.log').read_text(errors='replace'), read_json(directory / 'test-summary.json'))
    captures = check_captures(read_json(directory / 'attachments/manifest.json'), directory / 'attachments')
    archive = directory / 'PartyDeck-shipping-simulator.app.tar.gz'
    require(archive.is_file() and archive.stat().st_size > 0, 'Preserve the native Leave shipping app archive.')
    return {
        'scope': 'named shipping native Leave cancellation and confirmation routes with packaged-profile evidence',
        'test_scope': SCOPE, 'expected_cases': expected_case_names(),
        'named_native_leave_route_evidence_complete': True, 'native_pixel_review_complete': False,
        'native_acceptance_or_shipping_promotion': False,
        'stages': stages, 'captures': captures, 'app_archive': identity(archive),
        'inputs': [identity(directory / name) for name in ('source-preflight.json', 'build-settings.json',
                   'settings-check.json', 'test.log', 'test-summary.json', 'attachments/manifest.json', 'godot-shipping-link.json')],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['preflight', 'settings', 'result'])
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--directory', required=True, type=Path)
    args = parser.parse_args()
    name = {'preflight': 'source-preflight.json', 'settings': 'settings-check.json', 'result': 'result.json'}[args.command]
    output = args.directory / name
    require(not output.exists(), 'Preserve previous native Leave receipts before another run.')
    try:
        if args.command == 'preflight':
            require(args.repo is not None, 'Native Leave preflight requires its repository root.')
            result = preflight(args.repo.resolve())
        elif args.command == 'settings':
            source = read_json(args.directory / 'source-preflight.json')
            require(source.get('test_scope') == SCOPE and source.get('expected_cases') == expected_case_names(),
                    'Build settings must belong to the native Leave scope.')
            result = check_settings(read_json(args.directory / 'build-settings.json'),
                                    Path(source['activation']['source_plist']['path']))
        else:
            result = check_result(args.directory)
        with output.open('x') as stream:
            json.dump(result, stream, indent=2); stream.write('\n')
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        failure = {'test_scope': SCOPE, 'check_failed': True, 'error': str(error)}
        if not output.exists():
            with output.open('x') as stream:
                json.dump(failure, stream, indent=2); stream.write('\n')
        print(json.dumps(failure))
        return 1
    print(json.dumps({'test_scope': SCOPE, 'check': args.command, 'passed': True}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
