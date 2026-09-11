#!/usr/bin/env python3
"""Host-only negative gate checks. Small PNG/metadata fixtures are never native UI evidence."""

import copy
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest
import zlib


CHECKS = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'check-ios-godot-shipping-smoke.py'))
CASE, CLASS, METHOD = CHECKS['CASE'], CHECKS['CLASS'], CHECKS['METHOD']
SUMMARY = {'result': 'Passed', 'testFailures': [], 'totalTestCount': 1,
           'passedTests': 1, 'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}
START = f"Test Case '-[{CASE[0]} {METHOD}]' started.\n"
FINISH = f"Test Case '-[{CASE[0]} {METHOD}]' passed (1.000 seconds).\n"
LOG = START + FINISH + '** TEST SUCCEEDED **\n'


def fixture_png():
    # An original one-pixel container exercises file checks only; it is not a screenshot or renderer.
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\x00\x00\x00\x00\x00')) + chunk(b'IEND', b''))


class ShippingGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='partydeck-shipping-gate-unit-fixtures-')
        self.directory = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_named_case_rejects_zero_extra_repeat_skip_and_failure(self):
        CHECKS['check_named_result'](LOG, SUMMARY)
        invalid = ['', FINISH, START, LOG + START, LOG + FINISH, LOG + '** TEST FAILED **\n',
                   LOG.replace("' passed", "' skipped"), LOG.replace("' passed", "' failed"),
                   LOG.replace(METHOD, 'testUnrelatedCase')]
        for log in invalid:
            with self.subTest(log=log), self.assertRaises(ValueError):
                CHECKS['check_named_result'](log, SUMMARY)

    def test_summary_is_independent_strict_and_not_boolean(self):
        for key, value in [('totalTestCount', 0), ('passedTests', 0), ('passedTests', True),
                           ('failedTests', 1), ('skippedTests', 1), ('expectedFailures', 1),
                           ('result', 'Failed'), ('testFailures', [{}])]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                CHECKS['check_named_result'](LOG, {**SUMMARY, key: value})

    def settings(self):
        common = {'CONFIGURATION': 'Debug', 'PLATFORM_NAME': 'iphonesimulator', 'ARCHS': 'arm64',
                  'SWIFT_ACTIVE_COMPILATION_CONDITIONS': 'DEBUG', 'OTHER_SWIFT_FLAGS': '',
                  'PARTYDECK_GODOT_ACTIVATION_EXPECTATION': ''}
        return [
            {'target': 'PartyDeck', 'buildSettings': {**common, 'INFOPLIST_FILE': '/repo/iosApp/PartyDeck/Info.plist',
                                                     'GENERATE_INFOPLIST_FILE': 'NO'}},
            {'target': 'PartyDeckUITests', 'buildSettings': {**common, 'GENERATE_INFOPLIST_FILE': 'YES',
                'SWIFT_ACTIVE_COMPILATION_CONDITIONS': 'DEBUG ' + CHECKS['SMOKE']}},
        ]

    def test_settings_reject_observer_in_either_flag_path_and_smoke_in_app(self):
        plist = Path('/repo/iosApp/PartyDeck/Info.plist')
        CHECKS['check_settings'](self.settings(), plist)
        for target in (0, 1):
            for setting in ('SWIFT_ACTIVE_COMPILATION_CONDITIONS', 'OTHER_SWIFT_FLAGS'):
                data = self.settings(); data[target]['buildSettings'][setting] += ' -D' + CHECKS['QUALIFICATION']
                with self.subTest(target=target, setting=setting), self.assertRaises(ValueError):
                    CHECKS['check_settings'](data, plist)
        data = self.settings(); data[0]['buildSettings']['OTHER_SWIFT_FLAGS'] += ' -D' + CHECKS['SMOKE']
        with self.assertRaises(ValueError): CHECKS['check_settings'](data, plist)

    def test_settings_reject_missing_test_condition_wrong_plist_and_wrong_platform(self):
        for target, key, value in [(1, 'SWIFT_ACTIVE_COMPILATION_CONDITIONS', 'DEBUG'),
                                  (0, 'INFOPLIST_FILE', '/tmp/qualification.plist'),
                                  (1, 'INFOPLIST_FILE', '/repo/iosApp/PartyDeck/Info.plist'),
                                  (0, 'PLATFORM_NAME', 'iphoneos'), (1, 'ARCHS', 'x86_64'),
                                  (0, 'PARTYDECK_GODOT_ACTIVATION_EXPECTATION', '/tmp/expectation.json')]:
            data = self.settings(); data[target]['buildSettings'][key] = value
            with self.subTest(target=target, key=key), self.assertRaises(ValueError):
                CHECKS['check_settings'](data, Path('/repo/iosApp/PartyDeck/Info.plist'))

    def test_flag_arrays_cannot_bypass_qualification_rejection(self):
        for target in (0, 1):
            for key in ('SWIFT_ACTIVE_COMPILATION_CONDITIONS', 'OTHER_SWIFT_FLAGS'):
                for value in ([], ['-D' + CHECKS['QUALIFICATION']]):
                    data = self.settings(); data[target]['buildSettings'][key] = value
                    with self.subTest(target=target, key=key, value=value), self.assertRaisesRegex(ValueError, 'must be strings'):
                        CHECKS['check_settings'](data, Path('/repo/iosApp/PartyDeck/Info.plist'))

    def result_prefix(self):
        # Incomplete metadata deliberately stops before any real app/result evidence is possible.
        (self.directory / 'stage-exits.json').write_text(json.dumps(dict.fromkeys(CHECKS['STAGES'], 0)))
        (self.directory / 'source-preflight.json').write_text(json.dumps({
            'source_files': [], 'runner_files': [],
            'activation': {'source_plist': {'path': '/repo/iosApp/PartyDeck/Info.plist'}},
        }))
        (self.directory / 'build-settings.json').write_text(json.dumps(self.settings()))
        saved = CHECKS['check_settings'](self.settings(), Path('/repo/iosApp/PartyDeck/Info.plist'))
        (self.directory / 'settings-check.json').write_text(json.dumps(saved))
        return saved

    def test_final_accounting_revalidates_retained_build_settings(self):
        self.result_prefix()
        data = self.settings(); data[0]['buildSettings']['SWIFT_ACTIVE_COMPILATION_CONDITIONS'] += ' ' + CHECKS['QUALIFICATION']
        (self.directory / 'build-settings.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Qualification observation'):
            CHECKS['check_result'](self.directory)

    def test_final_accounting_rejects_failed_changed_or_type_aliased_settings_receipt(self):
        expected = self.result_prefix()
        changed = copy.deepcopy(expected); changed['targets']['PartyDeck']['conditions'].append(CHECKS['QUALIFICATION'])
        for value in ({'check_failed': True}, changed, {**expected, 'native_execution_performed': 0}):
            (self.directory / 'settings-check.json').write_text(json.dumps(value))
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Retained build settings'):
                CHECKS['check_result'](self.directory)

    def manifest(self):
        attachments = []
        for index, name in enumerate(CHECKS['CAPTURES']):
            filename = f'fixture-container-{index}.png'
            (self.directory / filename).write_bytes(fixture_png())
            attachments.append({'suggestedHumanReadableName': name + '_0_fixture.png',
                                'exportedFileName': filename, 'isAssociatedWithFailure': False})
        return [{'testIdentifier': f'{CLASS}/{METHOD}()',
                 'testIdentifierURL': f'test://com.apple.xcode/PartyDeck/PartyDeckUITests/{CLASS}/{METHOD}',
                 'attachments': attachments}]

    def test_all_nine_named_files_are_required_for_the_exact_case(self):
        manifest = self.manifest()
        self.assertEqual(len(CHECKS['check_captures'](manifest, self.directory)), 9)
        for index in range(9):
            changed = copy.deepcopy(manifest); del changed[0]['attachments'][index]
            with self.subTest(index=index), self.assertRaises(ValueError):
                CHECKS['check_captures'](changed, self.directory)
        for key in ('testIdentifier', 'testIdentifierURL'):
            changed = copy.deepcopy(manifest); changed[0][key] = 'wrong-case'
            with self.subTest(key=key), self.assertRaises(ValueError):
                CHECKS['check_captures'](changed, self.directory)

    def test_duplicate_failed_aliased_and_traversing_attachments_reject(self):
        manifest = self.manifest()
        variants = []
        changed = copy.deepcopy(manifest); changed[0]['attachments'].append(changed[0]['attachments'][0]); variants.append(changed)
        for key, value in [('exportedFileName', '../outside.png'), ('exportedFileName', 'fixture-container-1.png'),
                           ('isAssociatedWithFailure', True)]:
            changed = copy.deepcopy(manifest); changed[0]['attachments'][0][key] = value; variants.append(changed)
        for changed in variants:
            with self.assertRaises(ValueError): CHECKS['check_captures'](changed, self.directory)

    def test_missing_or_non_png_original_rejects(self):
        manifest = self.manifest(); path = self.directory / 'fixture-container-0.png'
        path.write_bytes(b'not a PNG')
        with self.assertRaises(ValueError): CHECKS['check_captures'](manifest, self.directory)
        path.unlink()
        with self.assertRaises(ValueError): CHECKS['check_captures'](manifest, self.directory)

    def test_each_primary_and_preservation_failure_is_fatal(self):
        for stage in CHECKS['STAGES']:
            for failed in (None, 1, True):
                states = dict.fromkeys(CHECKS['STAGES'], 0); states[stage] = failed
                (self.directory / 'stage-exits.json').write_text(json.dumps(states))
                with self.subTest(stage=stage, failed=failed), self.assertRaisesRegex(ValueError, 'Every test, tee'):
                    CHECKS['check_result'](self.directory)


if __name__ == '__main__':
    unittest.main(verbosity=2)
