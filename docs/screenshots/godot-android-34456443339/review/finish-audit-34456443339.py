"""Freeze the independently reviewed comparison evidence without Git or builds."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re

BASE = Path('/tmp/partydeck-engine-ci/34456443339')
HEAD = 'dad1c11741bd4322bb8b2afb9f18f3db5f50c919'
DOC = Path('/root/projects/PartyDeck/docs/research/engine-ci.md')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def record(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def planned_record(path, payload):
    return {'path': str(path), 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}


automated_path = BASE / 'native-evidence-automated.json'
producer_path = BASE / 'producer-evidence-summary.json'
correlation_path = BASE / 'source-close-barrier-correlation.json'
crop_receipt_path = BASE / 'input-target-crop-receipt.json'
assert digest(automated_path) == 'cc8713992f98d7856a80104c2451b91bd57f0210d834bc40a784c1735f8c85c6'
assert digest(producer_path) == 'c47a8af5b6c45de9aabd8c1c68dc4246371b7a864867e9a571c062322feb295c'
assert digest(correlation_path) == '7070f1ceed294b39b1e12ab69b11d3ab446d936a3ce054c3cbcb74928956914a'
assert digest(crop_receipt_path) == '74173ee7c738ac92ca5e7cf66d8cc5bf7949b8124c4a2e3c44981cd8618a028a'
automated = json.loads(automated_path.read_text())
assert automated['headSha'] == HEAD and automated['runId'] == 34456443339
assert automated['conclusion'] == 'failure'
assert [case['passed'] for case in automated['androidCases']] == [True, True, False, False]
assert automated['nativeOriginalPngsDecoded'] == 70
status = json.loads((BASE / 'last-run-status.json').read_text())
assert status['id'] == 34456443339 and status['head_sha'] == HEAD and status['status'] == 'completed'
assert status['conclusion'] == 'failure'
jobs = json.loads((BASE / 'last-jobs-status.json').read_text())['jobs']
assert {job['id']: job['conclusion'] for job in jobs} == {
    102803838342: 'success', 102805337294: 'success', 102805337258: 'success',
    102805337388: 'failure', 102805337298: 'failure',
}
assert all(job['status'] == 'completed' for job in jobs)

all_native = {}
for case in automated['androidCases']:
    assert {str(path) for path in (BASE / case['artifact']).rglob('*.png')} == {
        item['path'] for item in case['originalPngs']}
    for original in case['originalPngs']:
        path = Path(original['path'])
        assert original['pngVerifiedAndDecoded'] is True
        assert path.stat().st_size == original['bytes'] and digest(path) == original['sha256']
        assert original['width'] == 720 and original['height'] == 1600
        all_native[str(path)] = {
            'case': case['artifact'], 'wholeCasePassed': case['passed'],
            'wholeCaseStage': case['stage'], 'wholeCaseError': case['error'], **original,
            'captureScope': 'empty_avd_preparation' if '/android/emulator/' in str(path) else 'native_runtime',
        }
assert len(all_native) == 70
findings = []


def reviewed(relative, finding):
    path = str(BASE / relative)
    original = all_native[path]
    findings.append({
        **{key: original[key] for key in ['path', 'sha256', 'bytes', 'width', 'height', 'case', 'wholeCasePassed']},
        'directOriginalVisualReview': True,
        'finding': finding,
    })


resumed = {
    ('2d', '1.0'): 'Native Ready and the concealed five-card hand panel with Reveal my hand are visible. The Star heading is partly cropped at the retained scroll position. No private card faces or ranks are visible.',
    ('2d', '2.0'): 'The large-text scene shows Round 01, Star, 5 cards covered and Reveal my hand. No private card faces or ranks are visible. The lower action area extends beyond the viewport.',
    ('3d', '1.0'): 'Native Ready, public round-one text, five card backs and Show hand are visible. No private card faces or ranks are visible; the seat row is horizontally scrollable.',
    ('3d', '2.0'): 'The large-text scene shows Show hand and public round-one text. Only the upper portion of the table and card backs is visible at the bottom of the scroll viewport. No private card faces or ranks are visible.',
}
winners = {
    ('2d', '1.0'): 'Round 14, Orbit wins, the public Moon card and the final Crown-claim challenge outcome are visible. Return to lobby is fully visible. Lower seat rows are cropped by the scroll viewport.',
    ('2d', '2.0'): 'Round 14, Orbit wins, the public Moon card and the beginning of the final outcome are visible in large text. The lower outcome and Return to lobby are below the captured viewport. Later real input and host records establish the accepted return and successful teardown.',
    ('3d', '1.0'): 'Round 14, Orbit wins, Bluff caught, the public Moon card and Back to room are visible. The Doesn’t match label spans two lines. This frame precedes the failed Close acknowledgment check.',
    ('3d', '2.0'): 'Round 14, Orbit wins, Bluff caught, Moxie burned out and Moon · Doesn’t match are visible in large text. Only the top of the table is visible; Back to room is below the captured viewport. Later input and host records establish an accepted return, followed by the failed Close acknowledgment check.',
}
revealed = {
    ('2d', '1.0'): 'The revealed hand shows readable Moon, Crown and Crown cards, with further cards available by horizontal scrolling. Cover is visible. The Star heading is partly cropped at this vertical scroll position.',
    ('2d', '2.0'): 'The large-text revealed hand shows the full Moon and Crown cards and part of the next Crown. The horizontal hand scrollbar and Cover are visible; lower actions are outside the captured viewport.',
    ('3d', '1.0'): 'All five revealed cards are visible on the table with Moon, Crown, Crown, Star and Star labels. Hide hand and Select cards are visible. The 3D card faces are visibly lower resolution than the surrounding text.',
    ('3d', '2.0'): 'All five revealed card faces are visible on the table. Hide hand remains above the scroll area, and the large Select · Moon control is visible below Your hand · 5 cards. Per-card text selection supplements the small 3D faces.',
}
for mode in ['2d', '3d']:
    for scale in ['1.0', '2.0']:
        prefix = f'godot-android-{mode}-font-{scale}-debug/android/runtime/{mode}/match/'
        reviewed(prefix + '06-recents-privacy.png',
                 'The Android Overview app preview is opaque gray. No private card face, rank or gameplay text is visible in the retained preview.')
        reviewed(prefix + '07-resumed-concealed.png', resumed[(mode, scale)])
        reviewed(prefix + '12-winner.png', winners[(mode, scale)])
        reviewed(prefix + '02-revealed.png', revealed[(mode, scale)])
        if mode == '2d':
            reviewed(prefix + '14-chooser-after-exit.png',
                     'The chooser is visible after the completed match return, with both Play Last Light choices and Ready to compare. Enabled and clickable controls are established by the separately audited XML.')
        else:
            reviewed(f'godot-android-{mode}-font-{scale}-debug/android/runtime/final-screen.png',
                     'The final diagnostic image shows the chooser, both Play Last Light choices and Ready to compare after the failed match-return acknowledgment check. The visible chooser does not qualify the missing acknowledgment or the unattempted native Back route.')

for scale in ['1.0', '2.0']:
    prefix = f'godot-android-2d-font-{scale}-debug/android/runtime/2d/native-exit/'
    reviewed(prefix + '01-fresh-concealed.png',
             'The fresh 2D presentation shows native Ready, Round 01, Star and the concealed five-card panel with Reveal my hand. No private ranks are visible. The native Close table control is above the rendered scene.')
    reviewed(prefix + '14-chooser-after-exit.png',
             'The chooser is visible after the native Close entry, with both Play Last Light choices and Ready to compare. The distinct process identity and zero renderer-event delta are established by the independently audited receipts.')
assert len(findings) == 24 and len({item['path'] for item in findings}) == 24

visual = {
    'runId': 34456443339, 'headSha': HEAD,
    'scope': 'Direct inspection at original resolution of the 24 named native PNGs from this exact run.',
    'directOriginalVisualReviewCount': len(findings), 'images': findings,
    'limits': [
        'Findings describe the named retained frames only; no continuous video or general design/accessibility approval is claimed.',
        'Whole-case failure remains attached to every reviewed image from either 3D case. Images do not qualify the missing Close acknowledgment.',
        'Companion desktop images are hash/provenance checked separately; this receipt makes no direct desktop visual-review claim.',
    ],
}
visual_path = BASE / 'original-visual-review.json'
visual_payload = json_bytes(visual)
visual_record = planned_record(visual_path, visual_payload)

crop_receipt = json.loads(crop_receipt_path.read_text())
assert crop_receipt['runId'] == 34456443339 and crop_receipt['headSha'] == HEAD
assert crop_receipt['derivedCropCount'] == len(crop_receipt['crops']) == 4
crop_findings = {
    'godot-android-2d-font-1.0-debug': 'The crop contains the full Moon card and its readable Moon label inside the outlined hand target. The actual next tap is within this target.',
    'godot-android-2d-font-2.0-debug': 'The large-text crop contains the full Moon card and readable Moon label with generous target area. The actual next tap is within this target.',
    'godot-android-3d-font-1.0-debug': 'The crop contains the small angled Moon card face. The symbol is recognizable, with visibly soft 3D sampling. The actual next tap lies inside its reported projected bounds.',
    'godot-android-3d-font-2.0-debug': 'The crop contains the full Select · Moon button with large readable text. The actual next tap lies inside this text control.',
}
reviewed_crops = []
for crop in crop_receipt['crops']:
    output = crop['output']
    path = Path(output['path'])
    assert path.stat().st_size == output['bytes'] and digest(path) == output['sha256']
    assert crop['unchangedOriginalCropPixelsVerified'] is True
    assert crop['samePresentationRevisionSurfaceViewportAndTargetGeometry'] is True
    assert crop['sameRevealedUnselectedHandState'] is True
    assert crop['originalPath'] in {item['path'] for item in findings}
    reviewed_crops.append({
        **deepcopy(crop), 'directDerivedCropVisualReview': True,
        'finding': crop_findings[crop['artifact']],
    })
crop_visual = {
    'runId': 34456443339, 'headSha': HEAD, 'derivedCropVisualReviewCount': 4,
    'derivationReceipt': record(crop_receipt_path), 'crops': reviewed_crops,
    'scope': 'Direct original-resolution inspection of four unchanged-pixel target crops. These derivatives are not additional native runtime originals.',
    'limits': [
        'Each source frame precedes its associated first card tap by one diagnostic refresh. Presentation, revision, state and target geometry match, but no separate per-input screenshot is claimed.',
        'Other input records were independently checked against their own retained diagnostic geometry; these four crops do not visually cover every input.',
        'The two 3D whole-case failures remain attached to their target crops.',
    ],
}
crop_visual_path = BASE / 'input-target-crop-visual-review.json'
crop_visual_payload = json_bytes(crop_visual)
crop_visual_record = planned_record(crop_visual_path, crop_visual_payload)

reviewed_paths = {item['path'] for item in findings}
native_inventory = [{**item, 'directOriginalVisualReview': path in reviewed_paths}
                    for path, item in sorted(all_native.items())]
desktop = deepcopy(automated['desktop']['captures'])
for item in desktop:
    path = Path(item['path'])
    assert path.stat().st_size == item['bytes'] and digest(path) == item['sha256']
    item['captureScope'] = 'companion_desktop'
    item['directOriginalVisualReview'] = False
capture_counts = Counter(item['captureScope'] for item in native_inventory)
assert capture_counts == {'native_runtime': 66, 'empty_avd_preparation': 4}
assert len(desktop) == 22
inventory = {
    'runId': 34456443339, 'headSha': HEAD,
    'packSha256': automated['packSha256'], 'runtimeApkSha256': automated['packages'][0]['sha256'],
    'scope': 'Exact native-job and companion desktop original inventory; derivative target crops are explicitly separate. Whole-case failure remains attached to every image from either failed native case.',
    'nativePngCount': 70, 'nativeRuntimePngCount': 66, 'nativePreparationPngCount': 4, 'desktopPngCount': 22,
    'directOriginalVisualReviewCount': 24, 'derivedInputTargetCrops': 4,
    'automatedAuditReceipt': record(automated_path), 'visualReviewReceipt': visual_record,
    'inputTargetCropVisualReviewReceipt': crop_visual_record,
    'native': native_inventory, 'desktop': desktop,
    'limits': ['The four preparation images are empty-AVD preparation captures.',
               'No screenshot gallery or publication count is asserted.',
               'Derived input-target crops are excluded from original image counts.'],
}
inventory_path = BASE / 'original-image-inventory.json'
inventory_payload = json_bytes(inventory)

entries = [entry for case in automated['androidCases'] for entry in case['entries']]
counts = {
    'actualJunitCases': automated['junitTotals']['actualCases'],
    'checkerHostTests': automated['checkerHostTests'],
    'packedNativeBoundaryAssertions': automated['packedNativeBoundary']['checks'],
    'matchedDesktopTraceViews': automated['desktop']['traceViews'], 'desktopCaptureHashes': len(desktop),
    'nativeCases': len(automated['androidCases']),
    'nativeCasesPassed': sum(case['passed'] for case in automated['androidCases']),
    'nativeCasesFailed': sum(not case['passed'] for case in automated['androidCases']),
    'attemptedProcessEntries': len(entries),
    'completedRequestedExitRoutes': sum(entry['completedRequestedExitRoute'] for entry in entries),
    'observedOsProcessDeaths': sum(entry['actualOsProcessDeathObserved'] for entry in entries),
    'nativeSceneCaptureCropHashes': sum(entry['verifiedSceneCaptureCount'] for entry in entries),
    'sceneInputGeometryRecords': sum(entry['sceneInputs'] for entry in entries),
    'nativeInputRecords': sum(case['nativeInputCount'] for case in automated['androidCases']),
    'nativeOriginalPngsDecoded': 70, 'nativeRuntimeOriginalPngs': 66, 'nativePreparationOriginalPngs': 4,
    'originalImagesDirectlyReviewed': len(findings), 'derivedInputTargetCropsDirectlyReviewed': len(reviewed_crops),
    'nativeCloseBarriersObserved': sum(entry['closeSignalLogObservation']['nativeBarrierObserved'] for entry in entries),
    'nativeCloseFallbacksObserved': sum(entry['closeSignalLogObservation']['fallbackObserved'] for entry in entries),
    'nativeBackRoutesAttempted': sum(entry['name'] == 'native-exit' for case in automated['androidCases']
                                    if '3d-font' in case['artifact'] for entry in case['entries']),
    'knownShaderCacheWarningPairs': sum(len(entry['knownShaderCacheWarningTextPairs']) for entry in entries),
    'processLogsWithShutdownDriverError': sum(any('eglCodecCommon: removeVertexArrayObject: ERROR:' in item['text']
        for item in entry['rawErrorTextMatches']) for entry in entries),
}
assert counts == {
    'actualJunitCases': 37, 'checkerHostTests': 69, 'packedNativeBoundaryAssertions': 111,
    'matchedDesktopTraceViews': 42, 'desktopCaptureHashes': 22, 'nativeCases': 4,
    'nativeCasesPassed': 2, 'nativeCasesFailed': 2, 'attemptedProcessEntries': 8,
    'completedRequestedExitRoutes': 6, 'observedOsProcessDeaths': 8, 'nativeSceneCaptureCropHashes': 44,
    'sceneInputGeometryRecords': 151, 'nativeInputRecords': 345, 'nativeOriginalPngsDecoded': 70,
    'nativeRuntimeOriginalPngs': 66, 'nativePreparationOriginalPngs': 4, 'originalImagesDirectlyReviewed': 24,
    'derivedInputTargetCropsDirectlyReviewed': 4, 'nativeCloseBarriersObserved': 6,
    'nativeCloseFallbacksObserved': 2, 'nativeBackRoutesAttempted': 0,
    'knownShaderCacheWarningPairs': 6, 'processLogsWithShutdownDriverError': 8,
}
aggregate = deepcopy(automated)
aggregate['scope'] = 'Completed independent audit of retained producer evidence, all four Android cases, exact source/package identities and the named native original/target-crop review. Audit completion does not imply workflow or full native qualification success.'
aggregate['nativeAutomatedAuditReceipt'] = record(automated_path)
aggregate['sourceCloseBarrierCorrelationReceipt'] = record(correlation_path)
aggregate['directOriginalVisualReview'] = findings
aggregate['directOriginalVisualReviewCount'] = len(findings)
aggregate['directOriginalVisualReviewStatus'] = 'Completed direct inspection of the 24 named originals; no general design approval or publication inventory is claimed.'
aggregate['originalVisualReviewReceipt'] = visual_record
aggregate['originalImageInventoryReceipt'] = planned_record(inventory_path, inventory_payload)
aggregate['inputTargetCropVisualReviewReceipt'] = crop_visual_record
aggregate['derivedInputTargetCropsDirectlyReviewed'] = 4
aggregate['verifiedCounts'] = counts
aggregate['scopeLimits'].extend([
    'The 70 native-job PNGs comprise 66 runtime originals and four empty-AVD preparation frames; four reviewed target crops are derivatives, not additional originals.',
    'The target crop source frames precede their associated inputs by one diagnostic refresh; no separate per-input screenshot claim is made.',
    'Both 3D Close requests reach the 250 ms fallback without a recorded dispatch, barrier or main callback. The retained evidence does not establish the scheduling cause.',
])
aggregate_path = BASE / 'evidence-summary.json'
aggregate_payload = json_bytes(aggregate)

expected_inputs = {
    'runId': 34456443339, 'headSha': HEAD,
    'packSha256': '8f24944d61b0430cfec4a32bb1d03d2c7da9f55918264e9cfcded1c675d21539',
    'packBytes': 1546376,
    'runtimeApkSha256': 'e1b9126c6d91996b2cdf3877d7a9150199b75276aea8c2028bda72787c9311c3',
    'scope': 'Requested exact run identifiers, independently matched to archived source, producer packages and every native case.',
}
assert expected_inputs['packSha256'] == aggregate['packSha256'] and expected_inputs['packBytes'] == aggregate['packBytes']
assert expected_inputs['runtimeApkSha256'] == aggregate['packages'][0]['sha256']

section = '''[Godot comparison run 34456443339](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34456443339), at commit `dad1c11741bd4322bb8b2afb9f18f3db5f50c919`, passes 37 actual JUnit cases, 69 checker host tests, 111 packed native-boundary assertions and both desktop renderers with identical 42-view authority traces. All 22 desktop PNG hashes and provenance match. Its exact-source check accepts 136 PCK entries, SHA-256 `8f24944d61b0430cfec4a32bb1d03d2c7da9f55918264e9cfcded1c675d21539`, totaling 1,546,376 bytes; both APKs and the AAB embed that pack. The debug APK, unsigned release APK and AAB archive sizes are **314,330,402**, **311,463,789** and **104,828,379 bytes**. All four API 35 native cases install the verified debug APK, SHA-256 `e1b9126c6d91996b2cdf3877d7a9150199b75276aea8c2028bda72787c9311c3`, after fresh preparation without a reboot. **Both 2D cases pass; both 3D cases fail the strict Close acknowledgment check after their completed matches.**

All four matches execute two viewer plays, two challenges and thirteen round advances, reach the round-14/revision-41 winner, and accept Return to lobby. Independent observations verify the same process and presentation through background/resume, the native cover, and cleared private bindings and selection after resume. All **44 scene capture crop hashes, 151 scene input geometry records and 345 native input records** verify. The 70 decoded native-job PNGs comprise **66 runtime originals and four preparation frames**. Direct review covers 24 named originals and four unchanged-pixel input-target crops. All four Overview previews are opaque and the resumed hands are concealed. Both large-text winner frames leave their return action below the viewport; later real input and host records establish that it was reached. The four target crops match the next tap's presentation, revision, state and geometry, but their source frames precede the taps by one diagnostic refresh; they are not separate per-input captures or additional runtime originals.

**The two passing 2D cases complete all six requested exit routes:** a match return, a fresh scene Exit and a fresh native Close at each text size. Each entry has a distinct process/presentation identity, complete native teardown, the surviving chooser and enabled launch controls. Fresh scene Exit adds one renderer event and no gameplay intent; native Close adds no renderer event. Both 3D cases attempt only the match entry and fail before fresh scene Exit or native Back, so **this run qualifies no 3D Back route**. Android records actual death of all eight attempted engine processes, but process death does not qualify the two missing acknowledgments.

The exact archived change records Close acknowledgment in a per-plugin atomic observation only after the native-signal barrier, independently of the main-thread callback; queue disposal does not erase it. The checker files, comparison workflow, bounded queue and all native host timeout lines are byte-identical to the preceding run. Setup/per-mode/cleanup limits remain **600/900/180 seconds**, the Close fallback remains **250 ms**, and renderer-exit confirmation remains **1,500 ms**. Replaying the archived strict teardown function on the retained final hosts reproduces six passes and the two original failures without a waiver. All six 2D exits log request, dispatch, native barrier and main callback; the normal/200% match barriers arrive **240/209 ms** after their requests.

**Neither failed 3D process records Close dispatch, native barrier or main callback.** Normal text uses PID **3056**, presentation `3c21755b-0868-4ae6-82dc-c4e319474e23`: request/fallback elapsed times are **642134/642384 ms**, native destruction takes **313 ms**, and Android records death at **08:57:16.907 UTC**. At 200%, PID **3078**, presentation `92d20394-b056-4972-bda4-b0d1021ded47`, records request/fallback **820876/821127 ms**, destruction **138 ms**, and death at **09:00:20.128 UTC**. Each final host has `closeReason=return_to_chooser`, 18 accepted intents, 19 received events, no diagnostics timeout, all other destruction markers and `closeSignalAcknowledged=false`. Both failure snapshots report no engine PIDs and both final originals show the chooser. These observations narrow the failed stage but do not establish the scheduling cause.

All eight process logs retain an `eglCodecCommon removeVertexArrayObject` shutdown error, and six retain the paired shader-cache warning at error priority. The workflow remains failed. The evidence does not qualify an optimized Godot runtime, API 36, physical-device GPU/audio/accessibility, LAN, same-process reinitialization or store release; the reviewed images do not establish continuous pixel privacy or general design approval.
'''
document_before = DOC.read_bytes()
document_text = document_before.decode()
anchor = '## Required validation jobs\n'
assert document_text.count(anchor) == 1 and '34456443339' not in document_text
document_after = document_text.replace(anchor, section + '\n' + anchor)
patch = ''.join(difflib.unified_diff(document_text.splitlines(keepends=True), document_after.splitlines(keepends=True),
                                     fromfile='a/docs/research/engine-ci.md', tofile='b/docs/research/engine-ci.md'))
assert patch and patch.count('--- a/') == 1

# Independently reconstruct the proposed document from the unified diff in memory.
old_lines = document_text.splitlines(keepends=True)
reconstructed, cursor, in_hunk = [], 0, False
for line in patch.splitlines(keepends=True):
    if line.startswith('--- ') or line.startswith('+++ '):
        continue
    if line.startswith('@@ '):
        header = re.fullmatch(r'@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@\n', line)
        assert header
        start = int(header.group(1)) - 1
        assert start >= cursor
        reconstructed.extend(old_lines[cursor:start])
        cursor, in_hunk = start, True
        continue
    assert in_hunk
    kind, content = line[0], line[1:]
    if kind in [' ', '-']:
        assert old_lines[cursor] == content
        cursor += 1
    if kind in [' ', '+']:
        reconstructed.append(content)
    assert kind in [' ', '+', '-']
reconstructed.extend(old_lines[cursor:])
assert ''.join(reconstructed) == document_after
assert DOC.read_bytes() == document_before
base_record = {
    **record(DOC), 'auditedRunHead': HEAD, 'applied': False,
    'scope': 'Documentation patch base bytes only. No Git command was run, and current workspace source is not used to attribute the audited run.',
}
patch_validation = {
    'runId': 34456443339, 'headSha': HEAD, 'applied': False,
    'pythonUnifiedDiffRoundTripPassed': True, 'gitApplyCheckPerformed': False,
    'baseSha256': hashlib.sha256(document_before).hexdigest(),
    'proposedDocumentSha256': hashlib.sha256(document_after.encode()).hexdigest(),
    'patchSha256': hashlib.sha256(patch.encode()).hexdigest(),
    'scope': 'Exact unified-diff reconstruction against the retained base bytes; no shared documentation edit or Git command.',
}

outputs = [
    (visual_path, visual_payload), (crop_visual_path, crop_visual_payload),
    (inventory_path, inventory_payload), (aggregate_path, aggregate_payload),
    (BASE / 'expected-inputs.json', json_bytes(expected_inputs)),
    (BASE / 'engine-ci-comparison-followup-section.md', section.encode()),
    (BASE / 'engine-ci-comparison-followup.patch', patch.encode()),
    (BASE / 'engine-ci-comparison-followup-base.json', json_bytes(base_record)),
    (BASE / 'patch-validation.json', json_bytes(patch_validation)),
]
assert all(not path.exists() for path, _ in outputs), 'Refusing to overwrite completed audit outputs.'
for path, payload in outputs:
    with path.open('xb') as stream:
        stream.write(payload)

script_directory = BASE / 'audit-scripts'
script_directory.mkdir(exist_ok=False)
scripts = {}
for label, filename in [
    ('nativeAudit', 'audit-godot-native-34456443339.py'),
    ('producerAudit', 'summarize-godot-producer.py'),
    ('sourceCorrelation', 'correlate-close-barrier-34456443339.py'),
    ('inputTargetCropDerivation', 'crop-native-inputs-34456443339.py'),
    ('finalization', 'finish-audit-34456443339.py'),
    ('collector', 'monitor-godot-comparison-independent.py'),
]:
    origin = Path('/tmp/partydeck-engine-ci') / filename
    destination = script_directory / filename
    with destination.open('xb') as stream:
        stream.write(origin.read_bytes())
    assert digest(destination) == digest(origin)
    scripts[label] = record(destination)
assert digest(Path('/tmp/partydeck-engine-ci/audit-godot-native-34450246541.py')) == '38dd408d1f6df3e832a8e4cbb444cec8556aafb99d24a8687a70c7c9f8968617'
assert digest(Path('/tmp/partydeck-engine-ci/finish-audit-34450246541.py')) == '67b7c53722009e04809f8db070df815b1ae893d8eeb690a283dd2118fdb435cb'
source_receipt = json.loads((BASE / 'source-archive.json').read_text())
freeze_files = [path for path, _ in outputs] + [
    producer_path, automated_path, correlation_path, crop_receipt_path,
    BASE / 'source-archive.json', BASE / 'source-pack-check.log',
    BASE / 'last-run-status.json', BASE / 'last-jobs-status.json', BASE / 'artifacts.json',
    BASE / 'native-audit.log', BASE / 'input-crop-derivation.log', BASE / 'input-crop-derivation-02.log',
]
downloads = sorted(BASE.glob('*.downloaded.json'))
job_logs = sorted(BASE.glob('job-*.log'))
assert len(downloads) == 6 and len(job_logs) == 5
freeze = {
    'schemaVersion': 1, 'frozenAtUtc': datetime.now(timezone.utc).isoformat(),
    'runId': 34456443339, 'headSha': HEAD, 'workflowConclusion': status['conclusion'],
    'scope': 'Completed independent retained-evidence audit. Audit completion does not imply workflow or full native qualification success.',
    'storageDirectory': str(BASE.resolve()), 'temporaryAlias': str(BASE),
    'files': [record(path) for path in freeze_files],
    'artifactDownloadReceipts': [record(path) for path in downloads],
    'jobLogs': [record(path) for path in job_logs], 'scripts': scripts,
    'sourceArchive': {key: source_receipt[key] for key in ['archivePath', 'bytes', 'sha256']},
    'identity': {'packSha256': aggregate['packSha256'], 'packBytes': aggregate['packBytes'],
                 'packages': aggregate['packages'], 'sourceCloseBarrierCorrelation': record(correlation_path)},
    'verifiedCounts': counts,
    'nativeCaseResults': [{key: case[key] for key in ['artifact', 'passed', 'stage', 'error']}
                          for case in aggregate['androidCases']],
    'patchValidation': {**patch_validation, 'receipt': record(BASE / 'patch-validation.json')},
    'localAuditAttempts': {
        'firstCropHelper': {'receipt': record(BASE / 'input-crop-derivation.log'),
                           'result': 'Missing optional Pillow import before any crop output; local helper only, not a CI or native failure.'},
        'completedCropHelper': {'receipt': record(BASE / 'input-crop-derivation-02.log'),
                               'result': 'Completed with standard-library PNG encoding; original pixel identity independently decoded and checked.'},
    },
    'limits': aggregate['scopeLimits'],
    'invariants': [
        'Frozen receipts and helper copies will not be silently rewritten. Any later correction requires a separate supplemental record.',
        'No raw GitHub artifact ZIP digest audit is claimed. The source tarball identity and selected extracted source members are independently verified.',
        'Current workspace source is not used to attribute the dad1c11 run.',
        'No builds, devices, CI dispatches, Git commands or shared source/documentation edits were performed by this independent audit.',
        'The prior frozen native audit and finalization helpers remain byte-identical.',
    ],
}
freeze_path = BASE / 'audit-frozen.json'
with freeze_path.open('xb') as stream:
    stream.write(json_bytes(freeze))
print(json.dumps({'freeze': record(freeze_path), 'aggregate': record(aggregate_path),
                  'originalVisualReview': record(visual_path), 'inputTargetCropVisualReview': record(crop_visual_path),
                  'documentationPatch': record(BASE / 'engine-ci-comparison-followup.patch'),
                  'verifiedCounts': counts}, indent=2))
