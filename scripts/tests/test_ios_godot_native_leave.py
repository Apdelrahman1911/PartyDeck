#!/usr/bin/env python3
"""Metadata-only negative gates. In-memory PNG headers are not native screenshots or UI evidence."""

import copy
import io
from pathlib import Path
import runpy
import unittest
from unittest import mock

CHECKS = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'check-ios-godot-native-leave-smoke.py'))
COMMON = CHECKS['COMMON']
SUMMARY = {'result': 'Passed', 'testFailures': [], 'totalTestCount': 2,
           'passedTests': 2, 'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}


def case_log(cases, status='passed'):
    return ''.join(f"Test Case '-[{target} {method}]' started.\n"
                   f"Test Case '-[{target} {method}]' {status} (1.000 seconds).\n"
                   for target, method in cases) + '** TEST SUCCEEDED **\n'


def manifest():
    result = []
    for ordinal, ((_, method), captions) in enumerate(CHECKS['CAPTURES_BY_CASE'].items()):
        result.append({
            'testIdentifier': f"{CHECKS['CLASS']}/{method}()",
            'testIdentifierURL': f"test://com.apple.xcode/PartyDeck/PartyDeckUITests/{CHECKS['CLASS']}/{method}",
            'attachments': [
                {'suggestedHumanReadableName': caption + '_fixture.png',
                 'exportedFileName': f'case-{ordinal}-checkpoint-{index}.png', 'isAssociatedWithFailure': False}
                for index, caption in enumerate(captions)
            ],
        })
    return result


class NativeLeaveGateTests(unittest.TestCase):
    def captures(self, value, header=None, present=True, symlink=False):
        if header is None:
            # Only the common file-header gate reads this. No decoder or bitmap is created.
            header = b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + (1).to_bytes(4, 'big') * 2
        identity = lambda path: {'path': str(path), 'bytes': len(header), 'sha256': '0' * 64}
        with mock.patch.object(Path, 'is_file', return_value=present), \
             mock.patch.object(Path, 'is_symlink', return_value=symlink), \
             mock.patch.object(Path, 'open', side_effect=lambda *args, **kwargs: io.BytesIO(header)), \
             mock.patch.dict(CHECKS['check_captures'].__globals__, {'identity': identity}):
            return CHECKS['check_captures'](value, Path('/synthetic-native-leave-attachments'))

    def test_exact_two_cases_pass_in_either_order_but_missing_repeat_skip_and_other_scopes_fail(self):
        cases = list(CHECKS['CAPTURES_BY_CASE'])
        for order in (cases, list(reversed(cases))):
            CHECKS['check_named_result'](case_log(order), SUMMARY)
        invalid = [case_log([]), case_log(cases[:1]), case_log([cases[0], cases[0]]),
                   case_log(cases + [COMMON['CASE']]), case_log([COMMON['CASE']]),
                   case_log(cases, 'skipped'), case_log(cases, 'failed'),
                   case_log(cases) + '** TEST FAILED **\n',
                   case_log(cases).replace('started.', 'not-started.'),
                   case_log(cases).replace(cases[0][1], 'testUnrelatedCase')]
        for log in invalid:
            with self.subTest(log=log), self.assertRaises(ValueError):
                CHECKS['check_named_result'](log, SUMMARY)

    def test_xcresult_summary_is_independent_strict_and_never_boolean_counts(self):
        log = case_log(CHECKS['CAPTURES_BY_CASE'])
        variants = [('totalTestCount', 1), ('totalTestCount', 3), ('passedTests', 1),
                    ('failedTests', 1), ('skippedTests', 1), ('expectedFailures', 1),
                    ('failedTests', False), ('skippedTests', False), ('expectedFailures', False),
                    ('result', 'Failed'), ('testFailures', [{}])]
        for key, value in variants:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                CHECKS['check_named_result'](log, {**SUMMARY, key: value})
        with self.assertRaises(ValueError):
            CHECKS['check_named_result'](log, {key: value for key, value in SUMMARY.items() if key != 'expectedFailures'})

    def test_legacy_picker_keeps_one_case_nine_captions_and_cannot_accept_native_leave(self):
        legacy = {**SUMMARY, 'totalTestCount': 1, 'passedTests': 1}
        COMMON['check_named_result'](case_log([COMMON['CASE']]), legacy)
        self.assertEqual(len(COMMON['CAPTURES']), 9)
        with self.assertRaises(ValueError):
            COMMON['check_named_result'](case_log(CHECKS['CAPTURES_BY_CASE']), SUMMARY)
        with self.assertRaises(ValueError):
            CHECKS['check_named_result'](case_log([COMMON['CASE']]), legacy)
        with self.assertRaises(ValueError):
            COMMON['check_captures'](manifest(), Path('/synthetic-native-leave-attachments'))

    def test_all_eight_captures_must_bind_their_own_mode_and_case(self):
        value = manifest()
        accepted = self.captures(value)
        self.assertEqual(len(accepted), 8)
        self.assertEqual(len({item['file']['path'] for item in accepted}), 8)
        for owner in range(2):
            for index in range(4):
                changed = copy.deepcopy(value)
                del changed[owner]['attachments'][index]
                with self.subTest(owner=owner, index=index), self.assertRaises(ValueError):
                    self.captures(changed)
        changed = copy.deepcopy(value)
        changed[0]['attachments'], changed[1]['attachments'] = changed[1]['attachments'], changed[0]['attachments']
        with self.assertRaises(ValueError):
            self.captures(changed)

    def test_duplicate_records_wrong_case_urls_and_legacy_attachment_record_fail(self):
        value = manifest()
        variants = [[], value[:1], value + [value[0]], [value[0], value[0]]]
        for key in ('testIdentifier', 'testIdentifierURL'):
            changed = copy.deepcopy(value); changed[1][key] = changed[0][key]; variants.append(changed)
        variants.append([{'testIdentifier': f"{COMMON['CLASS']}/{COMMON['METHOD']}()",
                          'testIdentifierURL': 'legacy-picker', 'attachments': []}])
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.captures(changed)

    def test_duplicate_cross_case_alias_traversal_and_failure_associated_names_fail(self):
        value = manifest()
        variants = []
        changed = copy.deepcopy(value); changed[0]['attachments'].append(changed[0]['attachments'][0]); variants.append(changed)
        for key, bad in [('exportedFileName', '../outside.png'),
                         ('exportedFileName', value[1]['attachments'][0]['exportedFileName']),
                         ('isAssociatedWithFailure', True), ('isAssociatedWithFailure', 0),
                         ('suggestedHumanReadableName', 'shipping-2d-native-leave-ready-without-delimiter.png')]:
            changed = copy.deepcopy(value); changed[0]['attachments'][0][key] = bad; variants.append(changed)
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.captures(changed)

    def test_missing_symlink_non_png_and_empty_dimensions_cannot_count_as_captures(self):
        value = manifest()
        for options in ({'present': False}, {'symlink': True}, {'header': b'not PNG'},
                        {'header': b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + b'\x00' * 8}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.captures(value, **options)

    def test_retained_result_requires_new_scope_and_exact_cases_before_payload_reads(self):
        base = {'test_scope': CHECKS['SCOPE'], 'expected_cases': CHECKS['expected_case_names']()}
        variants = [{}, {**base, 'test_scope': 'picker'},
                    {**base, 'expected_cases': [f"{COMMON['CASE'][0]}/{COMMON['CASE'][1]}"]},
                    {**base, 'expected_cases': base['expected_cases'][:1]}]
        for source in variants:
            def read(path):
                if path.name == 'stage-exits.json': return dict.fromkeys(COMMON['STAGES'], 0)
                if path.name == 'source-preflight.json': return source
                self.fail('Scope rejection must occur before reading later result payloads.')
            with self.subTest(source=source), mock.patch.dict(CHECKS['check_result'].__globals__, {'read_json': read}), \
                 self.assertRaisesRegex(ValueError, 'legacy picker results cannot be relabeled'):
                CHECKS['check_result'](Path('/synthetic-native-leave-result'))

    def test_scope_stamp_without_selected_test_source_inventory_fails(self):
        source = {'test_scope': CHECKS['SCOPE'], 'expected_cases': CHECKS['expected_case_names'](),
                  'activation': {'source_plist': {'path': '/synthetic/iosApp/PartyDeck/Info.plist'}},
                  'source_files': []}
        def read(path):
            if path.name == 'stage-exits.json': return dict.fromkeys(COMMON['STAGES'], 0)
            if path.name == 'source-preflight.json': return source
            self.fail('Missing selected source must reject before later payload reads.')
        with mock.patch.dict(CHECKS['check_result'].__globals__, {'read_json': read}), \
             self.assertRaisesRegex(ValueError, 'exact selected Swift test source'):
            CHECKS['check_result'](Path('/synthetic-native-leave-result'))

    def test_every_primary_and_preservation_stage_remains_required(self):
        for stage in COMMON['STAGES']:
            for bad in (None, 1, True):
                stages = dict.fromkeys(COMMON['STAGES'], 0); stages[stage] = bad
                with self.subTest(stage=stage, bad=bad), \
                     mock.patch.dict(CHECKS['check_result'].__globals__, {'read_json': lambda path: stages}), \
                     self.assertRaisesRegex(ValueError, 'Every native Leave test'):
                    CHECKS['check_result'](Path('/synthetic-native-leave-result'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
