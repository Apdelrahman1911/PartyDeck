"""Assemble reviewed evidence and an unapplied documentation patch for one run."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

BASE = Path('/tmp/partydeck-engine-ci/34450246541')
HEAD = 'a7278686170243795e505ce4f6a6788e912c01fe'
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
assert digest(automated_path) == '3fc852ba023691132e767093e32741e435a998ec644fbb968ba40eaeeef7d522'
assert digest(producer_path) == 'cb00bfcb0362fca39657dab04cad6cf0b6672a4ad29c76489c8a69b576da4972'
automated = json.loads(automated_path.read_text())
assert automated['headSha'] == HEAD and automated['runId'] == 34450246541
assert automated['conclusion'] == 'failure'
assert [case['passed'] for case in automated['androidCases']] == [True, True, False, True]
assert automated['nativeOriginalPngsDecoded'] == 75

all_native = {}
for case in automated['androidCases']:
    actual_paths = {str(path) for path in (BASE / case['artifact']).rglob('*.png')}
    assert actual_paths == {item['path'] for item in case['originalPngs']}
    for original in case['originalPngs']:
        path = Path(original['path'])
        assert original['pngVerifiedAndDecoded'] is True
        assert path.stat().st_size == original['bytes'] and digest(path) == original['sha256']
        assert original['width'] == 720 and original['height'] == 1600
        all_native[str(path)] = {
            'case': case['artifact'],
            'wholeCasePassed': case['passed'],
            'wholeCaseStage': case['stage'],
            'wholeCaseError': case['error'],
            **original,
            'captureScope': 'empty_avd_preparation' if '/android/emulator/' in str(path) else 'native_runtime',
        }
assert len(all_native) == 75

findings = []


def reviewed(relative, finding):
    path = str(BASE / relative)
    original = all_native[path]
    findings.append({
        **{key: original[key] for key in ['path', 'sha256', 'bytes', 'width', 'height', 'case', 'wholeCasePassed']},
        'directOriginalVisualReview': True,
        'finding': finding,
    })


for mode, scale in [('2d', '1.0'), ('2d', '2.0'), ('3d', '1.0'), ('3d', '2.0')]:
    prefix = f'godot-android-{mode}-font-{scale}-debug/android/runtime/{mode}/match/'
    reviewed(prefix + '06-recents-privacy.png',
             'Android Overview preview is opaque gray, with no private card faces or labels visible in the retained frame.')
    resumed_findings = {
        ('2d', '1.0'): 'The resumed scene shows a concealed five-card panel and Reveal my hand. The Star heading is partly cropped at the current scroll position; no private card faces or labels are visible.',
        ('2d', '2.0'): 'The resumed large-text scene shows five covered cards and Reveal my hand. No private card faces or labels are visible in the retained frame.',
        ('3d', '1.0'): 'The resumed table shows five card backs and Show hand. No private card faces or labels are visible in the retained frame.',
        ('3d', '2.0'): 'The resumed large-text scene shows Show hand and public round-one text. The scroll viewport crops the lower table and card backs; no private ranks or faces are visible in the retained frame.',
    }
    reviewed(prefix + '07-resumed-concealed.png', resumed_findings[(mode, scale)])

reviewed('godot-android-2d-font-1.0-debug/android/runtime/2d/match/12-winner.png',
         'Round 14, Orbit wins, the public Moon card and final challenge outcome are visible. Return to lobby is fully visible at the bottom; lower seat rows are cropped by the scroll viewport.')
reviewed('godot-android-2d-font-2.0-debug/android/runtime/2d/match/12-winner.png',
         'The large-text frame shows Round 14, Orbit wins, the public Moon card and the beginning of the final outcome. The lower outcome text is cropped, and Return to lobby is below the captured viewport. Subsequent input and teardown records establish the return.')
reviewed('godot-android-3d-font-1.0-debug/android/runtime/3d/match/12-winner.png',
         "Round 14, Orbit wins, Bluff caught, the public Moon card and Back to room are visible. The Doesn't match label is rendered as two lines beneath the card. This winner frame precedes the failed close-acknowledgment check.")
reviewed('godot-android-3d-font-2.0-debug/android/runtime/3d/match/12-winner.png',
         'The large-text frame shows Round 14, Orbit wins, Bluff caught and the final public outcome. Only the upper table edge is visible; Back to room is below the captured viewport. Subsequent input and teardown records establish the return.')

for mode, scale in [('2d', '1.0'), ('2d', '2.0'), ('3d', '2.0')]:
    reviewed(f'godot-android-{mode}-font-{scale}-debug/android/runtime/{mode}/match/14-chooser-after-exit.png',
             'The comparison chooser is visible after the match exit, with both Play Last Light choices and Ready to compare. Enabled and clickable status is established by the separately audited XML.')
reviewed('godot-android-3d-font-1.0-debug/android/runtime/final-screen.png',
         'The final diagnostic frame shows the comparison chooser, both Play Last Light choices and Ready to compare after the failed match-return acknowledgment check. The visible chooser does not qualify the missing acknowledgment or an unattempted native Back route.')
reviewed('godot-android-3d-font-2.0-debug/android/runtime/3d/native-exit/01-fresh-concealed.png',
         'A fresh round-one 3D presentation shows native Ready, Show hand and public turn text. The large-text viewport crops the lower table and card backs; no private card faces or ranks are visible.')
reviewed('godot-android-3d-font-2.0-debug/android/runtime/3d/native-exit/14-chooser-after-exit.png',
         'The comparison chooser is visible after the native Back entry, with both Play Last Light choices and Ready to compare. The successful native_back reason, unchanged event count and actual process death are established separately by the receipts and logs.')
reviewed('godot-android-2d-font-1.0-debug/android/runtime/2d/match/02-revealed.png',
         'The revealed hand shows complete Moon, Crown and Crown cards, with further cards clipped by horizontal scrolling. Cover is visible and the Star heading is partly cropped at the top of the scroll viewport. Play and challenge controls are visible below the hand.')
reviewed('godot-android-3d-font-1.0-debug/android/runtime/3d/match/02-revealed.png',
         'The revealed table shows all five labeled cards: Moon, Crown, Crown, Star and Star. Hide hand and the muted Select cards control are visible. The public seat strip is horizontally scrollable and crops the rightmost visible seat details.')

assert len(findings) == len({item['path'] for item in findings}) == 20
visual = {
    'reviewedAtUtc': datetime.now(timezone.utc).isoformat(),
    'reviewer': '/root/engine_ci',
    'method': 'Direct view_image of each named original PNG at original resolution; no montage or transformed image substituted. Eight Overview/resume originals were inspected before continuation and twelve named originals afterward.',
    'runId': 34450246541,
    'headSha': HEAD,
    'count': len(findings),
    'images': findings,
    'limits': [
        'Findings describe the named retained frames only; no continuous video or general design/accessibility approval is claimed.',
        'Whole-case failure remains attached to reviewed images from the 3D normal-text case. No original image turns the missing close acknowledgment into a passing lifecycle.',
    ],
}
visual_path = BASE / 'original-visual-review.json'
visual_payload = json_bytes(visual)
visual_record = planned_record(visual_path, visual_payload)

review_by_path = {item['path']: item for item in findings}
native_inventory = []
for path, item in sorted(all_native.items()):
    native_inventory.append({**item, 'directOriginalVisualReview': path in review_by_path})
desktop = deepcopy(automated['desktop']['captures'])
for item in desktop:
    path = Path(item['path'])
    assert path.stat().st_size == item['bytes'] and digest(path) == item['sha256']
    item['captureScope'] = 'companion_desktop'
    item['directOriginalVisualReview'] = False
capture_counts = Counter(item['captureScope'] for item in native_inventory)
assert capture_counts == {'native_runtime': 71, 'empty_avd_preparation': 4}
assert len(desktop) == 22
inventory = {
    'runId': 34450246541,
    'headSha': HEAD,
    'packSha256': automated['packSha256'],
    'runtimeApkSha256': automated['packages'][0]['sha256'],
    'scope': 'Exact original native-job and companion desktop screenshot inventory. Whole-case failure remains attached to every image from the failed native case. Preparation captures are explicitly separate from the runtime subset.',
    'nativePngCount': 75,
    'nativeRuntimePngCount': 71,
    'nativePreparationPngCount': 4,
    'desktopPngCount': 22,
    'directOriginalVisualReviewCount': 20,
    'automatedAuditReceipt': record(automated_path),
    'visualReviewReceipt': visual_record,
    'native': native_inventory,
    'desktop': desktop,
    'limits': [
        'The four preparation images belong to successful empty-AVD preparation and are not app runtime captures.',
        'No screenshot gallery or publication count is asserted. Design review owns any separate publication inventory.',
        'The interrupted-collection-01 partial extraction is excluded from this inventory and from the audit.',
    ],
}
inventory_path = BASE / 'original-image-inventory.json'
inventory_payload = json_bytes(inventory)

archived_host = BASE / 'source-a727868/godot/android-host/src/main/kotlin/dev/partydeck/godot/compare/GodotGameActivity.kt'
expected_host_sha = 'b6dc98d69013253a9c601f80dd417c52cd003bdd9c13adc2d8fd335a76e0f027'
assert digest(archived_host) == expected_host_sha
source_receipt_path = BASE / 'source-archive.json'
source_receipt = json.loads(source_receipt_path.read_text())
assert source_receipt['headSha'] == HEAD and source_receipt['memberCount'] == 5018
correlation = {
    'runId': 34450246541,
    'headSha': HEAD,
    'archivedHostSource': record(archived_host),
    'expectedReviewedBackCorrectionSha256': expected_host_sha,
    'archivedSourceMatchesReviewedBackCorrection': True,
    'sourceArchiveReceipt': record(source_receipt_path),
    'scope': 'Source identity correlation only. The executed 3D/200% case verifies native Back; the normal-text case fails earlier and does not exercise Back. Current workspace source is not used to attribute this run.',
}
correlation_path = BASE / 'source-back-correction-correlation.json'
correlation_payload = json_bytes(correlation)

entries = [entry for case in automated['androidCases'] for entry in case['entries']]
counts = {
    'actualJunitCases': automated['junitTotals']['actualCases'],
    'checkerHostTests': automated['checkerHostTests'],
    'packedNativeBoundaryAssertions': automated['packedNativeBoundary']['checks'],
    'matchedDesktopTraceViews': automated['desktop']['traceViews'],
    'desktopCaptureHashes': len(desktop),
    'nativeCases': len(automated['androidCases']),
    'nativeCasesPassed': sum(case['passed'] for case in automated['androidCases']),
    'nativeCasesFailed': sum(not case['passed'] for case in automated['androidCases']),
    'attemptedProcessEntries': len(entries),
    'completedRequestedExitRoutes': sum(entry['completedRequestedExitRoute'] for entry in entries),
    'observedOsProcessDeaths': sum(entry['actualOsProcessDeathObserved'] for entry in entries),
    'nativeSceneCaptureCropHashes': sum(entry['verifiedSceneCaptureCount'] for entry in entries),
    'sceneInputGeometryRecords': sum(entry['sceneInputs'] for entry in entries),
    'nativeInputRecords': sum(case['nativeInputCount'] for case in automated['androidCases']),
    'nativeOriginalPngsDecoded': 75,
    'nativeRuntimeOriginalPngs': 71,
    'nativePreparationOriginalPngs': 4,
    'originalImagesDirectlyReviewed': len(findings),
    'knownShaderCacheWarningPairs': sum(len(entry['knownShaderCacheWarningTextPairs']) for entry in entries),
    'processLogsWithShutdownDriverError': sum(any('eglCodecCommon: removeVertexArrayObject: ERROR:' in item['text'] for item in entry['rawErrorTextMatches']) for entry in entries),
}
assert counts['attemptedProcessEntries'] == 10 and counts['completedRequestedExitRoutes'] == 9
assert counts['nativeSceneCaptureCropHashes'] == 46 and counts['sceneInputGeometryRecords'] == 151
assert counts['nativeInputRecords'] == 347 and counts['observedOsProcessDeaths'] == 10

aggregate = deepcopy(automated)
aggregate['scope'] = 'Completed independent audit of downloaded producer evidence, all four Android native cases, exact source/package identities and the named original-image review. Audit completion does not imply workflow or full native qualification success.'
aggregate['nativeAutomatedAuditReceipt'] = record(automated_path)
aggregate['sourceBackCorrectionCorrelationReceipt'] = planned_record(correlation_path, correlation_payload)
aggregate['directOriginalVisualReview'] = findings
aggregate['directOriginalVisualReviewCount'] = len(findings)
aggregate['directOriginalVisualReviewStatus'] = 'Completed direct inspection of the 20 named originals; separate design review owns any publication inventory.'
aggregate['originalVisualReviewReceipt'] = visual_record
aggregate['originalImageInventoryReceipt'] = planned_record(inventory_path, inventory_payload)
aggregate['verifiedCounts'] = counts
aggregate['collectionInterruption'] = {
    'receipt': record(BASE / 'interrupted-collection-01/interruption.json'),
    'excludedPartialExtraction': str(BASE / 'interrupted-collection-01/godot-comparison-builds'),
    'scope': 'Local collector termination and one resumed collection. The partial extraction is retained but excluded; it is not attributed to the CI workflow failure.',
}
aggregate['scopeLimits'].append('The 75 native-job PNGs comprise 71 runtime images and four empty-AVD preparation images. No gallery publication count is asserted.')
aggregate_path = BASE / 'evidence-summary.json'
aggregate_payload = json_bytes(aggregate)

section = '''The sixth [Godot comparison run 34450246541](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34450246541), at commit `a7278686170243795e505ce4f6a6788e912c01fe`, passes 29 actual JUnit cases, 69 checker host tests, 111 packed native-boundary assertions and both desktop renderers with identical 42-view authority traces. All 22 desktop PNG hashes and provenance match. Its exact-source check accepts 136 PCK entries, SHA-256 `0440dc8a1e099031eb7e0a08304411908e8580f932673599f149d2088c0e7afe`; both APKs and the AAB embed that pack. The debug APK, unsigned release APK and AAB archive sizes are **314,313,954**, **311,447,341** and **104,824,621 bytes**, respectively. All four native cases install the verified debug APK, SHA-256 `12699a84297d915344341e3cc794d43f04879fd719578a8a670f9df190d326b1`, after fresh API 35 preparation without a reboot. **Both 2D cases and 3D at 200% text pass; 3D at normal text fails its first match-return teardown.**

All four matches execute two viewer plays, two challenges and thirteen round advances, reach the round-14/revision-41 winner, and accept Return to lobby. Independent observations verify the same process and presentation through background/resume, the native cover, and cleared private bindings and selection after resume. All 46 scene capture crop hashes, 151 scene input geometry records and 347 native input records verify. The 75 decoded native-job PNGs comprise **71 runtime originals and four empty-AVD preparation frames**. Direct review of 20 originals includes all four obscured Overview previews, concealed resumed scenes and winners; three successful post-match chooser frames; the failed case's final chooser; the successful 3D Back entry and chooser; and both normal-text revealed hands. The two large-text winner frames leave their return action below the viewport; later input and teardown records establish those successful returns. These selected frames do not establish continuous pixel privacy or general design/accessibility approval.

**The three passing cases complete all nine requested exit routes.** Each has a full match return, a fresh scene Exit and a fresh native Close or Back, with distinct process/presentation identities and complete teardown receipts. The corrected **3D/200% native Back** entry uses PID **10913**, presentation `3af66d2a-ece0-41df-a0e0-6720c2cc6b82`, and records `closeReason=native_back` with `closeSignalAcknowledged=true`. Its received-event count stays at one and it accepts no gameplay intent. The Android event log records an actual Back press and process death; native destruction takes **195 ms**, the same chooser process resumes, and fresh XML confirms both launch controls are enabled. This verifies the requested local Back route for that executed case.

**The 3D normal-text case fails because `closeSignalAcknowledged` remains false after Return to lobby.** Its only entry uses PID **3062**, presentation `f220c15d-1a45-4fc5-aa21-effec3d836b6`. The final host has the expected `return_to_chooser` reason, 18 accepted intents, no diagnostic timeout and all other bridge/destruction/process-exit markers. Native destruction takes **210 ms**; the chooser resumes at **07:45:43.978 UTC**, and Android records PID 3062 dying at **07:45:44.001 UTC**. Both failure snapshots report no engine PIDs, and the original final frame shows the chooser. Those observations do not establish the missing acknowledgment. The case has no successful `teardown.json` and never attempts fresh scene Exit or native Back, so normal-text Back remains unqualified by this run. This failure is distinct from the preceding run's wrong Back reason and extra renderer event.

All ten attempted engine processes have observed OS death, but only nine requested exit routes qualify. Every process log retains an `eglCodecCommon removeVertexArrayObject` error during shutdown, and eight retain the paired shader-cache warning at error priority. The workflow therefore remains failed, with no clean-driver-log, optimized Godot runtime, API 36, physical-device GPU/audio/accessibility, LAN, same-process reinitialization or store qualification claim.
'''
document_before = DOC.read_bytes()
document_text = document_before.decode()
anchor = '## Required validation jobs\n'
assert document_text.count(anchor) == 1 and '34450246541' not in document_text
document_after = document_text.replace(anchor, section + '\n' + anchor)
patch = ''.join(difflib.unified_diff(document_text.splitlines(keepends=True), document_after.splitlines(keepends=True),
                                     fromfile='a/docs/research/engine-ci.md', tofile='b/docs/research/engine-ci.md'))
assert patch and patch.count('--- a/') == 1
base_record = {
    **record(DOC),
    'workspaceHeadWhenPrepared': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=DOC.parents[2], text=True).strip(),
    'auditedRunHead': HEAD,
    'applied': False,
    'scope': 'Documentation patch base only; current workspace HEAD is not used to attribute the audited run.',
}

outputs = [
    (visual_path, visual_payload),
    (inventory_path, inventory_payload),
    (correlation_path, correlation_payload),
    (aggregate_path, aggregate_payload),
    (BASE / 'engine-ci-comparison-followup-section.md', section.encode()),
    (BASE / 'engine-ci-comparison-followup.patch', patch.encode()),
    (BASE / 'engine-ci-comparison-followup-base.json', json_bytes(base_record)),
]
assert all(not path.exists() for path, _ in outputs), 'Refusing to overwrite existing audit outputs.'
for path, payload in outputs:
    with path.open('xb') as stream:
        stream.write(payload)
print(json.dumps({'created': [planned_record(path, payload) for path, payload in outputs], 'verifiedCounts': counts}, indent=2))
