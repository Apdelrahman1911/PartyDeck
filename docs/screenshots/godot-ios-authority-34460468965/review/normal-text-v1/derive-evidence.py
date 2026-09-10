#!/usr/bin/env python3
"""Read preserved CI evidence and record the two normal-text failure diagnoses."""
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
RUN = Path('/tmp/partydeck-engine-ci/34460468965').resolve()
SRC = RUN / 'source-31d148f'
ART = RUN / 'godot-ios-authority-gameplay'
DECODED = Path('/root/projects/PartyDeck/artifacts/evidence-storage/34460468965-xcresult-decoded')
LOG = DECODED / 'app-stdout-stderr.log'
IDS = {'825DF5F4-1C07-4D87-B2D2-2299833D253A': '2d', '7EB80C48-1878-4637-AB8D-D64F245C89A3': '3d'}


def ref(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def save(name, value):
    path = OUT / name
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')
    return ref(path)


assert ref(LOG)['sha256'] == 'fc3456d75d3366a24c2a09f438d04e5f37905d8937364d8a45f32d9b8b795a82'
assert ref(RUN / 'authority-attachment-evidence-summary.json')['sha256'] == 'f320420a83a84243a3125090769d6661bee8c09fbd6fe968f5ce39f97cd84cc8'
attachments = json.loads((RUN / 'authority-attachment-evidence-summary.json').read_text())
index = json.loads((DECODED / 'decoded-object-index.json').read_text())
proposal = json.loads((OUT / 'proposal-provenance.json').read_text())
inputs = json.loads((ART / 'evidence/authority-host-inputs.json').read_text())
records = []
timestamp = ''
decisive_lines = {206711, 208131, 213334, 213689, 214044, 214399, 215819,
                  302139, 466452, 466807, 470215, 472154, 472509, 472864}
excerpts = []
decoded_values = 0
for line_number, line in enumerate(LOG.open(errors='strict'), 1):
    if re.match(r'^\d{4}-\d\d-\d\d \d\d:\d\d:', line):
        timestamp = line.split(' AuthorityHost')[0]
    if 'XC_kAXXCAttributeValue' not in line or 'acceptedOpponentActions' not in line:
        continue
    # NSString log records use escaped quotes; accept the recorded escape depth.
    raw = line[line.index('{'):line.rindex('}') + 1]
    document = raw
    for attempt in range(3):
        try:
            value = json.loads(document)
            break
        except json.JSONDecodeError:
            if attempt == 2:
                raise
            document = document.replace(chr(92) * (2 - attempt) + chr(34), chr(34))
    decoded_values += 1
    diagnostic = value.get('native', {}).get('rendererDiagnostics', {})
    if diagnostic.get('presentationId') not in IDS:
        continue
    assert value['mode'] == IDS[diagnostic['presentationId']]
    records.append({'source_line': line_number, 'preceding_log_timestamp': timestamp,
                    'raw_line_sha256': hashlib.sha256(line.encode()).hexdigest(), 'metrics': value})
    if line_number in decisive_lines:
        excerpts.append(f'SOURCE LINE {line_number}; preceding log timestamp {timestamp}\n' + line)
assert decoded_values == 648 and len(records) == 312
assert sum(record['metrics']['mode'] == '2d' for record in records) == 236
assert sum(record['metrics']['mode'] == '3d' for record in records) == 76
by_line = {record['source_line']: record for record in records}


def action(line, name):
    controls = by_line[line]['metrics']['native']['rendererDiagnostics']['controls']
    return next(control for control in controls if control['group'] == 'partydeck_action_' + name)


assert by_line[213334]['metrics']['revision'] == by_line[214399]['metrics']['revision'] == '10'
assert not action(213334, 'challenge')['enabled'] and action(214399, 'challenge')['enabled']
assert action(213334, 'next_round')['visible'] and not action(214399, 'next_round')['visible']
assert by_line[472154]['metrics']['revision'] == by_line[472864]['metrics']['revision'] == '5'
assert not action(472154, 'next_round')['enabled'] and not action(472864, 'next_round')['enabled']
assert by_line[472154]['metrics']['native']['iterations'] == 387
assert by_line[472864]['metrics']['native']['iterations'] == 388
assert all(int(record['metrics']['revision']) == sum(record['metrics'][key] for key in
    ['acceptedViewerPlays', 'acceptedViewerChallenges', 'roundsAdvanced', 'acceptedOpponentActions']) for record in records)
metrics_ref = save('normal-text-ax-metrics.json', {
    'source': ref(LOG), 'source_object_chain': index['appStreams'],
    'decode_scope': 'All 648 logged metrics parsed; 312 values selected by the two exact normal-text presentation IDs.',
    'timestamp_scope': 'Timestamp is the preceding native log header, not a newly measured test timestamp.',
    'records': records,
})
(OUT / 'decisive-original-ax-lines.log').write_text('\n'.join(excerpts))

source_files = [item['path'] for item in proposal['files']] + [
    'godot/renderer/scripts/renderer_controller.gd',
    'godot/renderer/presentations/two_d/table.gd',
    'godot/renderer/presentations/three_d/table.gd',
    'godot/ios-host/AuthorityHost/AuthorityModel.swift',
    'godot/bridge/src/commonMain/kotlin/dev/partydeck/godot/bridge/QualificationAuthorityDriver.kt',
    'godot/bridge/src/commonTest/kotlin/dev/partydeck/godot/bridge/IosQualificationFacadeTest.kt',
]
native_source = 'godot/ios-host/modules/partydeck_ios_probe/PDGodotRuntime.mm'
assert ref(SRC / native_source)['sha256'] == inputs['engine_receipt']['native_module_sources']['partydeck_ios_probe/PDGodotRuntime.mm']
for item in proposal['files']:
    assert ref(SRC / item['path'])['sha256'] == item['base_sha256']
swift = 'godot/ios-host/AuthorityHostUITests/AuthorityHostUITests.swift'
before, after = (SRC / swift).read_text(), (OUT / 'proposed' / swift).read_text()
assert before[before.index('    private func referenceMatch'):before.index('    private func launch')] == after[after.index('    private func referenceMatch'):after.index('    private func launch')]
source_ref = save('source-and-proposal-validation.json', {
    'exact_commit': '31d148f9b6bbfa15d1746e1029858b86714362a3',
    'source_archive_root': str(SRC), 'sources': [ref(SRC / path) for path in source_files],
    'native_source_matches_original_engine_input_receipt': True,
    'all_patch_base_files_still_match_archived_source': True,
    'entire_reference_match_method_byte_identical': True,
    'patch_dry_run': {'command': 'patch --dry-run --batch -p1 -i scene-state-currentness.patch',
                      'working_directory': str(OUT / 'base'), 'exit_code': 0},
    'build_test_app_or_device_execution': False,
})
case_names = {'AuthorityHostUITests/testReferenceMatchIn2D()', 'AuthorityHostUITests/testReferenceMatchIn3D()'}
cases = [{key: test[key] for key in ['identifier', 'result', 'duration', 'issues', 'attachmentCount', 'measurementCount', 'geometryCount', 'observedControlCount']}
         for test in attachments['tests'] if test['identifier'] in case_names]
selected_attachments = ['BC7CD14E-0600-4584-8A9D-BD565E769E46.json',
                        '10C14244-9B9E-4F1F-82F3-A400B35B5094.json',
                        '38B770BB-325C-4F49-B609-BC108E358BB8.json',
                        'CA941E0C-FF1A-4037-90F1-5895B3288460.json']
receipt = {
    'result': 'DIAGNOSED; ORIGINAL TWO TEST FAILURES RETAINED; PROPOSAL NOT EXECUTED',
    'run_id': 34460468965, 'job_id': 102822443867, 'run_attempt': 1,
    'commit': '31d148f9b6bbfa15d1746e1029858b86714362a3', 'scope': 'AuthorityHost normal-text 2D and 3D cases only',
    'cases': cases,
    'normal_2d': {
        'failure': 'AuthorityHostUITests.swift:78 expected revision 41, observed 42.',
        'decisive_source_lines': [213334, 213689, 214044, 214399, 215819, 302139],
        'divergence': 'At revision 10 / round 4 / PLAYING, diagnostic 81 still lists the prior outcome controls with Challenge disabled. Diagnostic 82 at the same revision lists Challenge enabled. The checker chooses reveal/play from the earlier snapshot before tapControl waits for the chosen target to settle.',
        'final_observed': {'phase': 'FINISHED', 'revision': '42', 'round': 14, 'plays': 2, 'challenges': 0, 'rounds_advanced': 13, 'opponent_actions': 27, 'accepted_renderer_events': 16},
        'required_reference_assertions_preserved': {'revision': '41', 'round': 14, 'plays': 2, 'challenges': 2, 'rounds_advanced': 13},
        'revision_accounting': 'Every recorded normal-text revision equals plays + challenges + roundsAdvanced + acceptedOpponentActions. There is no unexplained extra revision in the recorded trace.',
        'lifecycle_evidence': 'Initial, pause and Home/resume observations all remain revision 0 with domain counters unchanged before the first play.',
        'qualification': 'No reference-match pass or completed return-to-lobby qualification; the original test failed.',
    },
    'normal_3d': {
        'failure': 'AuthorityHostUITests.swift:519, called by tapControl enabled guard at line 319.',
        'decisive_source_lines': [470215, 472154, 472509, 472864],
        'last_successful_input': 'Actual next_round touch at revision 2; the authority then records revision 5, round 2, roundsAdvanced 1 and acceptedOpponentActions 3.',
        'failing_target': 'next_round', 'diagnostic_sequences': ['159', '160'], 'native_iterations': [387, 388],
        'observed_control': 'Next Round remains visible but disabled while current authority and diagnostic revision both equal 5. No second Next Round touch is sent.',
        'cause': 'The checker accepts a diagnostic revision without proof that scene bindings have applied that state; the captured disabled control matches the pending prior outcome node. A later native iteration by itself is not a sufficient currentness predicate.',
        'limit': 'The failing enabled guard precedes the original explicit target attachment. Raw AX values supply the state; this normal-text trace ends before a later enabled sample, so recovery is not qualified.',
    },
    'common_source_cause': [
        'AuthorityModel.receive delivers current authority commands and opponent advancement without changing domain state for local reveal/hide/lifecycle operations.',
        'PDGodotRuntime.mm:1602-1607 sends view commands in drain; lines1650-1655 may immediately request diagnostics without an intervening scene reconciliation.',
        'main.gd:99-127 stores controller state and schedules _process; scene apply_state occurs at line168.',
        'main.gd:260-304 combines controller revision/foreground/hand flags with currently attached button nodes. It reports no pending/applied marker.',
        'AuthorityHost currentDiagnostics:407-417 checks revision equality and sequence but cannot distinguish those mixed snapshots; referenceMatch:98 branches before tapControl does its layout checks.',
    ],
    'proposal': {'patch': ref(OUT / 'scene-state-currentness.patch'), 'provenance': ref(OUT / 'proposal-provenance.json'),
                 'semantics': 'Add a strictly validated sceneStateApplied Boolean; require it for current scene assertions while retaining immediate pending/background diagnostics and all exact match assertions. Keep geometry settling as a separate requirement.',
                 'integration': 'The shared diagnostic producer and both exact-key native decoders must update together. Rebuild the PCK/native inputs and rerun meaningful qualification before any success claim.',
                 'retained_host_scope': 'RetainedHost checker changes are outside this proposal and require its separate exact-run diagnosis.',
                 'status': 'Only a /tmp proposal plus static patch applicability; no correction applied to shared source and no native/build/test execution.'},
    'evidence': [ref(ART / 'evidence/authority-source-commit.txt'), ref(ART / 'evidence/authority-host-test.log'),
                 ref(ART / 'evidence/authority-host-inputs.json'), ref(RUN / 'job-102822443867.log'),
                 ref(RUN / 'authority-attachment-evidence-summary.json'), ref(RUN / 'authority-package-evidence-summary.json'),
                 ref(DECODED / 'decoded-object-index.json'), ref(LOG), metrics_ref, source_ref,
                 ref(OUT / 'decisive-original-ax-lines.log')] + [ref(ART / 'artifacts/authority-attachments' / filename) for filename in selected_attachments],
    'artifact_identity_limit': 'Packed scripts are transformed .gdc entries. Source provenance uses the exact archived source/export fingerprint and actual bundled PCK hash, not reverse compilation.',
    'preservation': 'Original CI ZIP, app archive, XCResult, failures, screenshots, exported input/measurement attachments and logs are unchanged. No duplicate download.',
}
receipt_ref = save('normal-text-failure-diagnosis.json', receipt)
print(json.dumps({'receipt': receipt_ref, 'metrics': metrics_ref, 'patch': receipt['proposal']['patch']}, indent=2))
