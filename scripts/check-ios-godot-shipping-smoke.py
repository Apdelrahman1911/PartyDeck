#!/usr/bin/env python3
"""Private runner checks; a passed UI route does not itself approve renderer pixels or release."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import shlex


CLASS = 'PartyDeckGodotShippingUITests'
METHOD = 'testShippingPickerOpensBothNativeTablesAndReturnsToStandard'
CASE = ('PartyDeckUITests.' + CLASS, METHOD)
TEST_SOURCE = Path('iosApp/PartyDeckUITests/PartyDeckGodotShippingUITests.swift')
TEST_SHA256 = 'd47486de43146200e78f2f20596cbeb44167747400516ec263583c51f016f7ec'
QUALIFICATION = 'PARTYDECK_GODOT_SESSION_QUALIFICATION'
SMOKE = 'PARTYDECK_GODOT_SHIPPING_SMOKE'
ACTIVATION = {'profile': 'shipping', 'accepted_shipping_modes': ['2d', '3d'],
              'qualification_modes': [], 'configured_enabled_native_modes': ['2d', '3d']}
CAPTURES = ['shipping-home', 'shipping-standard-before-entry',
            *[f'shipping-{mode}-{step}' for mode in ('2d', '3d')
              for step in ('picker', 'native-ready', 'standard-return')], 'shipping-home-after-leave']
STAGES = ['primary_exit', 'preflight', 'build_settings', 'settings_check', 'xcodebuild', 'tee',
          'attachments_export', 'summary_export', 'package_verify', 'package_archive']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON field.')
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON value.')))


def identity(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return {'path': str(path.resolve()), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def preflight(repo):
    helper = runpy.run_path(str(repo / 'scripts/prepare-ios-godot-activation.py'))
    plist = repo / 'iosApp/PartyDeck/Info.plist'
    activation = helper['checked_activation'](plist, plist)
    require(activation['configuration'] == ACTIVATION, 'The actual checked-in shipping source must accept both modes.')
    require(identity(repo / TEST_SOURCE)['sha256'] == TEST_SHA256, 'Run the exact independently reviewed shipping test source.')
    paths = [TEST_SOURCE, Path('iosApp/PartyDeckUITests/PartyDeckUITests.swift'),
             Path('iosApp/PartyDeck.xcodeproj/project.pbxproj'), Path('iosApp/Configuration/App.xcconfig'),
             Path('iosApp/PartyDeck.xcodeproj/xcshareddata/xcschemes/PartyDeck.xcscheme'),
             Path('iosApp/PartyDeck/PartyDeckApp.swift'), Path('iosApp/PartyDeck/Info.plist'),
             *[Path('iosApp/PartyDeck/Godot') / name for name in
               ('GodotPresentationConfiguration.swift', 'GodotPresentationPort.swift',
                'GodotPresentationViewController.swift', 'GodotSessionQualificationObservation.swift')]]
    return {'scope': 'source activation and exact test input only', 'activation': activation,
            'source_files': [identity(repo / path) for path in paths],
            'runner_files': [identity(Path(__file__)), identity(Path(__file__).with_name('validate-ios-godot-shipping.sh'))],
            'native_execution_performed': False}


def check_settings(documents, plist):
    require(isinstance(documents, list) and len(documents) == 2, 'Need exactly app and UI-test target settings.')
    targets = {}
    for entry in documents:
        name = entry.get('target')
        require(name in {'PartyDeck', 'PartyDeckUITests'} and name not in targets, 'Unexpected or duplicate target settings.')
        settings = entry['buildSettings']
        raw_conditions = settings.get('SWIFT_ACTIVE_COMPILATION_CONDITIONS', '')
        flags = settings.get('OTHER_SWIFT_FLAGS', '')
        require(type(raw_conditions) is str and type(flags) is str, 'Swift condition and flag settings must be strings.')
        conditions = set(shlex.split(raw_conditions))
        require(settings.get('CONFIGURATION') == 'Debug' and settings.get('PLATFORM_NAME') == 'iphonesimulator'
                and settings.get('ARCHS') == 'arm64' and 'DEBUG' in conditions, 'Require Debug ARM64 Simulator target settings.')
        require(QUALIFICATION not in ' '.join(conditions) and QUALIFICATION not in flags,
                'Qualification observation must not be compiled into either selected target.')
        require(settings.get('PARTYDECK_GODOT_ACTIVATION_EXPECTATION') in (None, ''), 'Shipping has no qualification expectation.')
        if name == 'PartyDeck':
            require(SMOKE not in ' '.join(conditions) and SMOKE not in flags, 'The smoke condition belongs only to UI tests.')
            require(settings.get('INFOPLIST_FILE') == str(plist) and settings.get('GENERATE_INFOPLIST_FILE') == 'NO',
                    'The app must consume the actual checked-in shipping plist.')
        else:
            require(SMOKE in conditions and settings.get('GENERATE_INFOPLIST_FILE') == 'YES'
                    and settings.get('INFOPLIST_FILE') in (None, ''), 'The selected smoke needs its test-only condition and test plist.')
        targets[name] = {'conditions': sorted(conditions), 'configuration': settings['CONFIGURATION'],
                         'platform': settings['PLATFORM_NAME'], 'info_plist': settings.get('INFOPLIST_FILE')}
    return {'scope': 'effective build settings only', 'targets': targets, 'native_execution_performed': False}


def check_named_result(log, summary):
    prefix = r"^Test Case '-\[([^\]\s]+) (test\w+)\]' "
    started = re.findall(prefix + r'started\.$', log, re.MULTILINE)
    finished = re.findall(prefix + r'(passed|failed|skipped) \((\d+(?:\.\d+)?) seconds\)\.$', log, re.MULTILINE)
    require(started == [CASE] and len(finished) == 1 and finished[0][:2] == CASE and finished[0][2] == 'passed'
            and '** TEST SUCCEEDED **' in log and '** TEST FAILED **' not in log,
            'Require the one exact shipping case to start once and pass once; zero, extra, repeated, failed or skipped cases fail.')
    expected = {'totalTestCount': 1, 'passedTests': 1, 'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}
    require(isinstance(summary, dict) and summary.get('result') == 'Passed' and summary.get('testFailures') == []
            and all(type(summary.get(key)) is int and summary[key] == value for key, value in expected.items()),
            'The original XCResult summary must independently report exactly one pass and zero failures/skips.')


def check_captures(manifest, directory):
    require(isinstance(manifest, list) and len(manifest) == 1, 'Require one named-case attachment record.')
    entry = manifest[0]
    require(entry.get('testIdentifier') == f'{CLASS}/{METHOD}()' and entry.get('testIdentifierURL') ==
            f'test://com.apple.xcode/PartyDeck/PartyDeckUITests/{CLASS}/{METHOD}', 'Attachments must belong to the exact shipping testcase.')
    attachments = entry.get('attachments')
    require(isinstance(attachments, list), 'Missing original attachment list.')
    result, files = [], set()
    for name in CAPTURES:
        matches = [item for item in attachments if isinstance(item, dict)
                   and isinstance(item.get('suggestedHumanReadableName'), str)
                   and item['suggestedHumanReadableName'].startswith(name + '_')
                   and item['suggestedHumanReadableName'].endswith('.png')]
        require(len(matches) == 1, 'Every named Home/picker/native/Standard capture must appear exactly once.')
        item = matches[0]
        filename = item.get('exportedFileName')
        require(isinstance(filename, str) and filename == Path(filename).name and filename not in files
                and filename.endswith('.png') and item.get('isAssociatedWithFailure') is False,
                'Require distinct original PNG attachments, not failed/aliased/misbound names.')
        path = directory / filename
        require(path.is_file() and not path.is_symlink(), 'The original named attachment must be retained.')
        with path.open('rb') as stream:
            header = stream.read(24)
        require(len(header) == 24 and header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR'
                and int.from_bytes(header[16:20], 'big') > 0 and int.from_bytes(header[20:24], 'big') > 0,
                'Named captures require nonempty PNG dimensions; full pixel inspection is separate.')
        files.add(filename)
        result.append({'capture': name, 'file': identity(path)})
    return result


def check_result(directory):
    stages = read_json(directory / 'stage-exits.json')
    require(set(stages) == set(STAGES) and all(type(stages[key]) is int and stages[key] == 0 for key in STAGES),
            'Every test, tee, export and package stage must complete successfully; preserve individual exit codes.')
    source = read_json(directory / 'source-preflight.json')
    for item in source['source_files'] + source['runner_files']:
        require(identity(Path(item['path'])) == item, 'A recorded source changed during the shipping test build/run.')
    settings = check_settings(read_json(directory / 'build-settings.json'), Path(source['activation']['source_plist']['path']))
    saved_settings = read_json(directory / 'settings-check.json')
    require(json.dumps(settings, sort_keys=True) == json.dumps(saved_settings, sort_keys=True),
            'Retained build settings must reproduce the exact successful settings-check receipt.')
    link = read_json(directory / 'godot-shipping-link.json')
    require(link.get('stage') == 'production_ios_app_link_only' and link.get('packaged_activation') == ACTIVATION
            and link.get('inputs', {}).get('activation') == source['activation'],
            'The actual linked app must bind both shipping modes to the preflight source.')
    xcresult = directory / 'PartyDeckShipping.xcresult'
    require(xcresult.is_dir() and any(path.is_file() and path.stat().st_size > 0 for path in xcresult.rglob('*')),
            'Preserve the original nonempty XCResult.')
    check_named_result((directory / 'test.log').read_text(errors='replace'), read_json(directory / 'test-summary.json'))
    captures = check_captures(read_json(directory / 'attachments/manifest.json'), directory / 'attachments')
    archive = directory / 'PartyDeck-shipping-simulator.app.tar.gz'
    require(archive.is_file() and archive.stat().st_size > 0, 'Preserve the shipping app archive.')
    return {'scope': 'named shipping UI route and packaged-profile evidence', 'named_ui_route_evidence_complete': True,
            'native_pixel_review_complete': False, 'native_acceptance_or_shipping_promotion': False,
            'stages': stages, 'captures': captures, 'app_archive': identity(archive),
            'inputs': [identity(directory / name) for name in ('source-preflight.json', 'build-settings.json',
                       'settings-check.json', 'test.log', 'test-summary.json', 'attachments/manifest.json', 'godot-shipping-link.json')]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['preflight', 'settings', 'result'])
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--directory', required=True, type=Path)
    args = parser.parse_args()
    name = {'preflight': 'source-preflight.json', 'settings': 'settings-check.json', 'result': 'result.json'}[args.command]
    output = args.directory / name
    require(not output.exists(), 'Preserve the previous check receipt before rerunning.')
    try:
        if args.command == 'preflight':
            result = preflight(args.repo.resolve())
        elif args.command == 'settings':
            result = check_settings(read_json(args.directory / 'build-settings.json'), args.repo.resolve() / 'iosApp/PartyDeck/Info.plist')
        else:
            result = check_result(args.directory)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        result = {'check_failed': True, 'error': str(error), 'named_ui_route_evidence_complete': False,
                  'native_pixel_review_complete': False, 'native_acceptance_or_shipping_promotion': False}
        output.write_text(json.dumps(result, indent=2) + '\n')
        raise SystemExit(1) from error
    output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
